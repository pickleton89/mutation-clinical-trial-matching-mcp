"""
Tests for the unified MCP server.

This test module validates that the new unified server architecture works correctly
in both sync and async modes while maintaining backward compatibility.
"""

import json
import os
import warnings
from unittest.mock import Mock, patch

import pytest

from servers.config import ServerConfig, detect_async_mode
from servers.main import UnifiedMCPServer, create_server


class TestUnifiedServerConfig:
    """Test the unified server configuration system."""

    def test_server_config_defaults(self):
        """Test that server config has sensible defaults."""
        config = ServerConfig()

        assert config.async_mode is None  # Should auto-detect
        assert config.service_name == "clinical-trials-mcp"
        assert config.version == "0.2.1"
        assert config.default_min_rank == 1
        assert config.default_max_rank_sync == 10
        assert config.default_max_rank_async == 20
        assert config.max_mutations_sync == 5
        assert config.max_mutations_async == 10
        assert config.enable_cache_warming is True
        assert config.enable_metrics is True

    def test_environment_overrides(self):
        """Test that environment variables override configuration."""
        with patch.dict(os.environ, {
            'MCP_ASYNC_MODE': 'true',
            'MCP_SERVICE_NAME': 'test-service',
            'MCP_MAX_RANK': '15',
            'MCP_TIMEOUT': '20.0',
            'MCP_ENABLE_CACHE_WARMING': 'false'
        }):
            config = ServerConfig()

            assert config.async_mode is True
            assert config.service_name == 'test-service'
            assert config.default_max_rank_async == 15
            assert config.default_timeout_async == 20.0
            assert config.enable_cache_warming is False

    def test_get_max_rank_by_mode(self):
        """Test that max rank varies by execution mode."""
        config = ServerConfig()

        assert config.get_max_rank(async_mode=True) == 20
        assert config.get_max_rank(async_mode=False) == 10

    def test_get_effective_service_name(self):
        """Test that service name includes mode suffix."""
        config = ServerConfig()

        assert config.get_effective_service_name(True) == "clinical-trials-mcp-async"
        assert config.get_effective_service_name(False) == "clinical-trials-mcp-sync"

    def test_features_dict_by_mode(self):
        """Test that feature dictionary varies by execution mode."""
        config = ServerConfig()

        async_features = config.get_features_dict(True)
        sync_features = config.get_features_dict(False)

        assert async_features["async_support"] is True
        assert async_features["distributed_caching"] is True
        assert async_features["cache_warming"] is True

        assert sync_features["async_support"] is False
        assert sync_features["distributed_caching"] is False
        assert sync_features["cache_warming"] is False

        # Both modes should support these
        assert async_features["unified_architecture"] is True
        assert sync_features["unified_architecture"] is True


class TestUnifiedServerInitialization:
    """Test unified server initialization and mode detection."""

    def test_explicit_async_mode(self):
        """Test server initialization with explicit async mode."""
        server = UnifiedMCPServer(async_mode=True)
        assert server.async_mode is True
        assert "async" in server.service_name

    def test_explicit_sync_mode(self):
        """Test server initialization with explicit sync mode."""
        server = UnifiedMCPServer(async_mode=False)
        assert server.async_mode is False
        assert "sync" in server.service_name

    def test_environment_mode_detection(self):
        """Test that environment variables control mode detection."""
        with patch.dict(os.environ, {'MCP_ASYNC_MODE': 'false'}):
            server = UnifiedMCPServer()
            assert server.async_mode is False

    @patch('servers.main.asyncio.get_running_loop')
    def test_auto_detection_with_event_loop(self, mock_get_loop):
        """Test auto-detection when event loop is running."""
        mock_loop = Mock()
        mock_loop.is_running.return_value = True
        mock_get_loop.return_value = mock_loop

        with patch.dict(os.environ, {}, clear=True):
            server = UnifiedMCPServer()
            # Should default to async mode
            assert server.async_mode is True

    def test_flow_initialization(self):
        """Test that flows are properly initialized."""
        server = UnifiedMCPServer(async_mode=True)
        server.initialize_flows()

        assert server.single_flow is not None
        assert server.batch_flow is not None
        assert len(server.single_flow.nodes) >= 2  # Query + Summarize nodes
        assert len(server.batch_flow.nodes) >= 2   # Batch Query + Summarize nodes


class TestUnifiedServerTools:
    """Test that unified server tools work correctly."""

    @pytest.fixture
    def async_server(self):
        """Create an async server for testing."""
        return UnifiedMCPServer(async_mode=True)

    @pytest.fixture
    def sync_server(self):
        """Create a sync server for testing."""
        return UnifiedMCPServer(async_mode=False)

    def test_async_tool_setup(self, async_server):
        """Test that async tools are properly set up."""
        # Check that the server has the FastMCP app
        assert async_server.app is not None
        assert "Clinical Trials Unified MCP Server" in str(async_server.app)

    def test_sync_tool_setup(self, sync_server):
        """Test that sync tools are properly set up."""
        # Check that the server has the FastMCP app
        assert sync_server.app is not None
        assert "Clinical Trials Unified MCP Server" in str(sync_server.app)

    @patch('servers.main.UnifiedMCPServer._summarize_trials_async_impl')
    @pytest.mark.asyncio
    async def test_async_summarize_implementation(self, mock_impl, async_server):
        """Test that async summarize implementation is called correctly."""
        mock_impl.return_value = "Test summary"

        result = await async_server._summarize_trials_async_impl("BRAF V600E")

        mock_impl.assert_called_once_with("BRAF V600E")
        assert result == "Test summary"

    @patch('servers.main.UnifiedMCPServer._summarize_trials_sync_impl')
    def test_sync_summarize_implementation(self, mock_impl, sync_server):
        """Test that sync summarize implementation is called correctly."""
        mock_impl.return_value = "Test summary"

        result = sync_server._summarize_trials_sync_impl("BRAF V600E")

        mock_impl.assert_called_once_with("BRAF V600E")
        assert result == "Test summary"

    @patch('servers.main.get_all_circuit_breaker_stats')
    @patch('servers.main.get_metrics')
    def test_sync_health_status(self, mock_metrics, mock_cb_stats, sync_server):
        """Test sync health status generation."""
        mock_cb_stats.return_value = {}
        mock_metrics.return_value = {"counters": {}, "gauges": {}, "histograms": {}}

        result = sync_server._get_sync_health_status()
        health = json.loads(result)

        assert health["status"] == "healthy"
        assert health["mode"] == "sync"
        assert health["features"]["async_support"] is False
        assert health["features"]["unified_architecture"] is True

    @patch('servers.main.get_all_circuit_breaker_stats')
    @patch('servers.main.get_metrics')
    @patch('utils.cache_strategies.get_cache_analytics')
    @pytest.mark.asyncio
    async def test_async_health_status(self, mock_cache_analytics, mock_metrics, mock_cb_stats, async_server):
        """Test async health status generation."""
        mock_cb_stats.return_value = {}
        mock_metrics.return_value = {"counters": {}, "gauges": {}, "histograms": {}}

        # Mock cache analytics
        mock_analytics_instance = Mock()
        mock_analytics_instance.get_comprehensive_stats.return_value = {"cache_hits": 100}
        mock_cache_analytics.return_value = mock_analytics_instance

        result = await async_server._get_async_health_status()
        health = json.loads(result)

        assert health["status"] == "healthy"
        assert health["mode"] == "async"
        assert health["features"]["async_support"] is True
        assert health["features"]["distributed_caching"] is True
        assert health["features"]["unified_architecture"] is True


class TestBackwardCompatibility:
    """Test backward compatibility with legacy servers."""

    def test_legacy_async_server_import(self):
        """Test that legacy async server import still works."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            from servers.legacy_compat import AsyncServerCompat
            server = AsyncServerCompat()

            # Should emit deprecation warning
            assert len(w) > 0
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message)

            # Should have mcp app
            assert server.mcp is not None

    def test_legacy_sync_server_import(self):
        """Test that legacy sync server import still works."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            from servers.legacy_compat import SyncServerCompat
            server = SyncServerCompat()

            # Should emit deprecation warning
            assert len(w) > 0
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message)

            # Should have mcp app
            assert server.mcp is not None

    def test_primary_server_compatibility(self):
        """Test that servers.primary still works with deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # This should work but emit warnings
            import servers.primary

            # Should have emitted deprecation warnings
            assert any(issubclass(warning.category, DeprecationWarning) for warning in w)

            # Should have mcp instance
            assert servers.primary.mcp is not None

    def test_sync_server_compatibility(self):
        """Test that servers.legacy.sync_server still works with deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # This should work but emit warnings
            import servers.legacy.sync_server

            # Should have emitted deprecation warnings
            assert any(issubclass(warning.category, DeprecationWarning) for warning in w)

            # Should have mcp instance
            assert servers.legacy.sync_server.mcp is not None


class TestGlobalServerInstance:
    """Test the global server instance management."""

    def test_create_server_singleton(self):
        """Test that create_server returns the same instance."""
        server1 = create_server(async_mode=True)
        server2 = create_server()  # Should return the same instance

        assert server1 is server2
        assert server1.async_mode is True

    def test_create_server_with_overrides(self):
        """Test that create_server respects async_mode parameter."""
        # Clear the global instance first
        import servers.main
        servers.main.unified_server = None

        server = create_server(async_mode=False)
        assert server.async_mode is False


class TestServerModeDetection:
    """Test server mode detection logic."""

    def test_detect_async_mode_default(self):
        """Test that detect_async_mode defaults to async."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear any existing config
            import servers.config
            servers.config._config = None

            mode = detect_async_mode()
            assert mode is True  # Should default to async

    def test_detect_async_mode_environment(self):
        """Test that detect_async_mode respects environment."""
        with patch.dict(os.environ, {'MCP_ASYNC_MODE': 'false'}):
            # Clear any existing config
            import servers.config
            servers.config._config = None

            mode = detect_async_mode()
            assert mode is False


class TestErrorHandling:
    """Test error handling in unified server."""

    @pytest.fixture
    def server(self):
        """Create a server for testing."""
        return UnifiedMCPServer(async_mode=True)

    def test_invalid_mutation_sync(self):
        """Test error handling for invalid mutation in sync mode."""
        server = UnifiedMCPServer(async_mode=False)

        with pytest.raises(Exception):  # Should raise McpError
            server._summarize_trials_sync_impl("")

    @pytest.mark.asyncio
    async def test_invalid_mutation_async(self, server):
        """Test error handling for invalid mutation in async mode."""
        with pytest.raises(Exception):  # Should raise McpError
            await server._summarize_trials_async_impl("")

    def test_batch_limit_sync(self):
        """Test batch mutation limit in sync mode."""
        server = UnifiedMCPServer(async_mode=False)

        # Should handle too many mutations gracefully
        mutations = ",".join([f"MUTATION{i}" for i in range(10)])  # 10 mutations, sync limit is 5
        result = server._summarize_multiple_trials_sync_impl(mutations)

        assert "Error: Too many mutations" in result

    @pytest.mark.asyncio
    async def test_batch_limit_async(self, server):
        """Test batch mutation limit in async mode."""
        # Should handle too many mutations gracefully
        mutations = ",".join([f"MUTATION{i}" for i in range(15)])  # 15 mutations, async limit is 10
        result = await server._summarize_multiple_trials_async_impl(mutations)

        assert "Error: Too many mutations" in result


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
