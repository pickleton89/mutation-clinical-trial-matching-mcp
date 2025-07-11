"""
Unit tests for clinicaltrials.config module
"""

import os
import unittest
from unittest.mock import patch

from clinicaltrials.config import (
    APIConfig,
    get_config,
    load_config,
    reset_global_config,
    validate_config,
)


class TestAPIConfig(unittest.TestCase):
    """Test the APIConfig dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = APIConfig()

        # Check some key defaults
        self.assertEqual(config.clinicaltrials_api_url, "https://clinicaltrials.gov/api/v2/studies")
        self.assertEqual(config.anthropic_api_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.retry_initial_delay, 1.0)
        self.assertEqual(config.retry_backoff_factor, 2.0)
        self.assertEqual(config.cache_size, 100)
        self.assertEqual(config.anthropic_model, "claude-3-opus-20240229")


class TestLoadConfig(unittest.TestCase):
    """Test configuration loading from environment variables."""

    def setUp(self):
        """Set up test environment."""
        reset_global_config()

    def test_load_config_defaults(self):
        """Test loading configuration with default values."""
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()

            # Should have default values
            self.assertEqual(
                config.clinicaltrials_api_url, "https://clinicaltrials.gov/api/v2/studies"
            )
            self.assertEqual(config.max_retries, 3)
            self.assertEqual(config.cache_size, 100)
            self.assertEqual(config.anthropic_api_key, "")

    def test_load_config_from_env(self):
        """Test loading configuration from environment variables."""
        test_env = {
            "ANTHROPIC_API_KEY": "test-key-123",
            "CLINICALTRIALS_API_URL": "https://test.clinicaltrials.gov/api/v2/studies",
            "MAX_RETRIES": "5",
            "CACHE_SIZE": "200",
            "RETRY_INITIAL_DELAY": "2.0",
            "RETRY_JITTER": "false",
        }

        with patch.dict(os.environ, test_env, clear=True):
            config = load_config()

            self.assertEqual(config.anthropic_api_key, "test-key-123")
            self.assertEqual(
                config.clinicaltrials_api_url, "https://test.clinicaltrials.gov/api/v2/studies"
            )
            self.assertEqual(config.max_retries, 5)
            self.assertEqual(config.cache_size, 200)
            self.assertEqual(config.retry_initial_delay, 2.0)
            self.assertEqual(config.retry_jitter, False)

    def test_load_config_boolean_parsing(self):
        """Test boolean environment variable parsing."""
        test_cases = [
            ("true", True),
            ("false", False),
            ("1", True),
            ("0", False),
            ("yes", True),
            ("no", False),
            ("on", True),
            ("off", False),
            ("TRUE", True),
            ("FALSE", False),
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"RETRY_JITTER": env_value}, clear=True):
                config = load_config()
                self.assertEqual(config.retry_jitter, expected, f"Failed for {env_value}")


class TestValidateConfig(unittest.TestCase):
    """Test configuration validation."""

    def test_validate_config_valid(self):
        """Test validation of valid configuration."""
        config = APIConfig()
        config.anthropic_api_key = "test-key-123"

        errors = validate_config(config)
        self.assertEqual(errors, [])

    def test_validate_config_missing_api_key(self):
        """Test validation with missing API key."""
        config = APIConfig()
        config.anthropic_api_key = ""

        errors = validate_config(config)
        self.assertIn("ANTHROPIC_API_KEY is required", errors)

    def test_validate_config_invalid_urls(self):
        """Test validation with invalid URLs."""
        config = APIConfig()
        config.anthropic_api_key = "test-key-123"
        config.clinicaltrials_api_url = "not-a-url"
        config.anthropic_api_url = "also-not-a-url"

        errors = validate_config(config)
        self.assertIn("CLINICALTRIALS_API_URL must be a valid URL", errors)
        self.assertIn("ANTHROPIC_API_URL must be a valid URL", errors)

    def test_validate_config_negative_values(self):
        """Test validation with negative values."""
        config = APIConfig()
        config.anthropic_api_key = "test-key-123"
        config.clinicaltrials_timeout = -1
        config.max_retries = -1
        config.cache_size = -1

        errors = validate_config(config)
        self.assertIn("CLINICALTRIALS_TIMEOUT must be positive", errors)
        self.assertIn("MAX_RETRIES must be non-negative", errors)
        self.assertIn("CACHE_SIZE must be positive", errors)

    def test_validate_config_logical_constraints(self):
        """Test validation of logical constraints."""
        config = APIConfig()
        config.anthropic_api_key = "test-key-123"
        config.retry_initial_delay = 10.0
        config.retry_max_delay = 5.0

        errors = validate_config(config)
        self.assertIn("RETRY_INITIAL_DELAY cannot be greater than RETRY_MAX_DELAY", errors)

    def test_validate_config_zero_values(self):
        """Test validation with zero values where positive required."""
        config = APIConfig()
        config.anthropic_api_key = "test-key-123"
        config.anthropic_max_tokens = 0
        config.retry_initial_delay = 0
        config.cache_ttl = 0

        errors = validate_config(config)
        self.assertIn("ANTHROPIC_MAX_TOKENS must be positive", errors)
        self.assertIn("RETRY_INITIAL_DELAY must be positive", errors)
        self.assertIn("CACHE_TTL must be positive", errors)


class TestGetConfig(unittest.TestCase):
    """Test the get_config function."""

    def setUp(self):
        """Set up test environment."""
        reset_global_config()

    def test_get_config_valid(self):
        """Test getting valid configuration."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"}, clear=True):
            config = get_config()
            self.assertEqual(config.anthropic_api_key, "test-key-123")

    def test_get_config_invalid(self):
        """Test getting invalid configuration raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as context:
                get_config()

            self.assertIn("Configuration validation failed", str(context.exception))
            self.assertIn("ANTHROPIC_API_KEY is required", str(context.exception))

    def test_get_config_multiple_errors(self):
        """Test that multiple validation errors are reported."""
        with patch.dict(
            os.environ,
            {
                "CLINICALTRIALS_API_URL": "not-a-url",
                "ANTHROPIC_API_URL": "also-not-a-url",
                "CLINICALTRIALS_TIMEOUT": "-1",
            },
            clear=True,
        ):
            with self.assertRaises(ValueError) as context:
                get_config()

            error_msg = str(context.exception)
            self.assertIn("ANTHROPIC_API_KEY is required", error_msg)
            self.assertIn("CLINICALTRIALS_API_URL must be a valid URL", error_msg)
            self.assertIn("ANTHROPIC_API_URL must be a valid URL", error_msg)
            self.assertIn("CLINICALTRIALS_TIMEOUT must be positive", error_msg)


class TestGlobalConfig(unittest.TestCase):
    """Test global configuration management."""

    def setUp(self):
        """Set up test environment."""
        reset_global_config()

    def test_global_config_lazy_loading(self):
        """Test that global config is lazy-loaded."""
        from clinicaltrials.config import _config

        self.assertIsNone(_config)

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"}, clear=True):
            from clinicaltrials.config import get_global_config

            config = get_global_config()
            self.assertEqual(config.anthropic_api_key, "test-key-123")

    def test_global_config_reset(self):
        """Test that global config can be reset."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"}, clear=True):
            from clinicaltrials.config import get_global_config

            config1 = get_global_config()

            reset_global_config()

            config2 = get_global_config()
            # Should be the same values but different instances after reset
            self.assertEqual(config1.anthropic_api_key, config2.anthropic_api_key)


if __name__ == "__main__":
    unittest.main()
