# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Repository Cleanup Phase 1**: Cleaned up repository organization and structure for better maintainability
  - Removed duplicate `clinicaltrials_async_mcp_server.py` file (identical to primary server)
  - Moved documentation files from root to proper locations:
    - `IMPLEMENTATION_PLAN.md` → `docs/implementation_plan.md`
    - `future_work.md` → `docs/future_work.md`
    - `rules.md` → `docs/rules.md`
  - Removed redundant `requirements.txt` file (using `pyproject.toml` for dependency management)
  - Enhanced `.gitignore` with additional Python-specific entries for build artifacts and cache directories
- **Documentation Updates Phase 2**: Improved documentation structure and content following best practices
  - **CHANGELOG.md Restructure**: Completely restructured changelog following Keep a Changelog format
    - Merged duplicate [Unreleased] sections into single, organized structure
    - Added proper semantic versioning with v0.1.0 and v0.0.1 releases
    - Organized entries by Added/Changed/Removed/Fixed categories
    - Added reference links to Keep a Changelog and Semantic Versioning standards
  - **README.md Enhancements**: Updated README with production-ready status and comprehensive sections
    - Updated status section to reflect production readiness with feature checklist
    - Added professional badges (License, Python version, Tests, Code Style)
    - Created comprehensive Contributing section with development setup and guidelines
    - Enhanced License section with proper MIT license reference
    - Improved overall structure and professional presentation

## [0.1.0] - 2025-07-09

### Added
- **Server Migration to Async Primary**: Complete architectural migration from sync to async server with enterprise features
  - **Primary Server Migration**: Transformed `clinicaltrials_async_mcp_server.py` into the primary server (`clinicaltrials_mcp_server_primary.py`)
    - Enhanced with all enterprise monitoring tools from the original sync server
    - Added 11 comprehensive tools including async variants and new capabilities
    - Integrated proper MCP error handling with structured error codes and validation
    - Implemented automatic cache warming on startup for improved performance
    - Added comprehensive health checks with cache analytics integration
  - **Deprecation Strategy**: Established clear migration path for users
    - Original `clinicaltrials_mcp_server.py` now shows deprecation notice with migration instructions
    - Legacy sync server preserved as `clinicaltrials_mcp_server_sync_legacy.py`
    - Updated `pyproject.toml` to point to new primary server
    - Clear performance benefits messaging (80% faster, batch processing, distributed caching)
  - **Enhanced Tool Suite**: Primary server now provides comprehensive enterprise capabilities
    - **Core Functions**: `summarize_trials_async()` (primary), `summarize_multiple_trials_async()` (batch), `summarize_trials()` (backward compatibility)
    - **Health Monitoring**: `get_health_status()` with cache analytics, circuit breaker states, and feature flags
    - **Metrics Export**: `get_metrics_json()` and `get_metrics_prometheus()` for monitoring systems
    - **Circuit Breaker Monitoring**: `get_circuit_breaker_status()` with detailed state information
    - **Cache Management**: `get_cache_analytics()`, `get_cache_report()`, `warm_cache()`, `invalidate_cache()`
  - **Migration Documentation**: Created comprehensive guides for smooth transition
    - `docs/server_migration_guide.md` with step-by-step migration instructions
    - Updated `CLAUDE.md` with new server commands and architecture notes
    - Detailed rollback procedures and troubleshooting guide
    - Performance benchmarks and feature comparisons
  - **Startup Enhancements**: Added intelligent startup tasks for optimal performance
    - Automatic cache warming with common and trending mutations
    - Configuration validation on startup with clear error messages
    - Proper resource cleanup and async client management
- **Phase 3 Advanced Features Implementation**: Enterprise-grade reliability, comprehensive monitoring, and validation capabilities
  - **Circuit Breaker Pattern**: Implemented comprehensive circuit breaker system in `utils/circuit_breaker.py`
    - Three-state pattern (CLOSED, OPEN, HALF_OPEN) with configurable failure thresholds and recovery timeouts
    - Thread-safe implementation with proper locking mechanisms and statistics tracking
    - Integrated with both ClinicalTrials.gov and Anthropic API clients for improved resilience
    - Includes metrics integration for monitoring state changes, failure rates, and performance
    - Decorator interface for easy integration and registry system for managing multiple circuit breakers
  - **Request Metrics System**: Built comprehensive metrics collection system in `utils/metrics.py`
    - Supports counters, gauges, and histograms with percentile calculations (p50, p95, p99)
    - Tagged metrics for detailed categorization and filtering by API, operation, and error type
    - Timer context manager for automatic duration tracking with success/failure differentiation
    - Exports metrics in both Prometheus and JSON formats for monitoring system integration
    - Thread-safe collector with configurable retention policies and deque-based efficient storage
    - Global API functions and timed decorator for easy integration across the codebase
  - **Response Validation Framework**: Created schema-based validation system in `utils/response_validation.py`
    - Multiple validator types: TypeValidator, RegexValidator, RangeValidator, ArrayValidator for comprehensive validation
    - Nested field validation with dot notation for complex API response structures
    - Schema registry for managing multiple API schemas with versioning support
    - Response validator decorator for automatic validation with configurable error/warning logging
    - Pre-defined schemas for ClinicalTrials.gov and Anthropic APIs with proper field definitions
    - Graceful handling of schema evolution with detailed error reporting and severity levels
  - **MCP Server Monitoring Tools**: Enhanced MCP server with comprehensive observability endpoints
    - `get_health_status()` - Service health check with circuit breaker status and metrics summary
    - `get_metrics_json()` - All metrics exported in JSON format for programmatic access
    - `get_metrics_prometheus()` - Prometheus-formatted metrics for monitoring system integration
    - `get_circuit_breaker_status()` - Detailed circuit breaker information with state history
  - **Comprehensive Test Suite**: Added 86 new test cases across 3 test files (136 total tests)
    - `tests/test_circuit_breaker.py` - 17 tests covering all circuit breaker functionality and edge cases
    - `tests/test_metrics.py` - 25 tests for metrics collection, export formats, and timer functionality
    - `tests/test_response_validation.py` - 44 tests for validation framework, schemas, and decorator usage
    - All tests pass with proper mocking, edge case handling, and comprehensive assertions
- **Phase 2 Core Resilience Implementation**: Comprehensive API resilience and configuration system
  - **Retry Logic with Exponential Backoff**: Implemented robust retry mechanism in `utils/retry.py`
    - Configurable parameters: max_retries (default: 3), initial_delay (1s), backoff_factor (2x), max_delay (60s)
    - Handles transient failures: timeouts, connection errors, HTTP 5xx, and 429 rate limits
    - Includes jitter to prevent thundering herd effects and detailed structured logging
    - Applied to both `clinicaltrials.query` and `utils.call_llm` functions
  - **Configuration System**: Created comprehensive environment variable management in `clinicaltrials/config.py`
    - Supports 18 configurable parameters with sensible defaults and validation
    - APIConfig dataclass with type safety and environment variable loading
    - Global configuration management with lazy loading and test-friendly reset capability
    - Startup validation with clear error messages and graceful test environment handling
  - **Environment Documentation**: Complete setup guide and troubleshooting in `docs/environment_setup.md`
    - Documented all environment variables with examples and use cases
    - Created `.env.example` file with comprehensive configuration options
    - Included security considerations, development vs production guidelines, and troubleshooting section
  - **HTTP Session Management**: Enhanced connection pooling and User-Agent standardization
    - Migrated from individual requests to `requests.Session()` objects for connection reuse
    - Configuration-driven User-Agent headers with proper identification
    - Graceful initialization handling for test environments
  - **Comprehensive Test Coverage**: Added 24 new test cases for retry logic and configuration system
    - `tests/test_retry.py`: 9 test cases covering exponential backoff, jitter, exception handling, and timing
    - `tests/test_config.py`: 15 test cases covering validation, environment loading, and error scenarios
    - Updated existing tests to work with new configuration system
    - All 50 tests passing with proper mocking and environment isolation
- **Production-Ready Packaging**: Enhanced `pyproject.toml` with complete project metadata and packaging configuration
  - Added comprehensive project metadata: description, authors, keywords, classifiers, and URLs
  - Configured proper package discovery for multi-package project structure
  - Added development dependencies (pytest, mypy, ruff, coverage) and tool configurations
  - Created script entry point for `clinicaltrials-mcp-server` command
  - Project now installs successfully with proper dependency management
- **Structured Error Handling**: Implemented comprehensive MCP-compliant error handling in server and flow execution
  - Added proper `McpError` with `ErrorData` for all error scenarios in MCP server
  - Enhanced Flow class with graceful error propagation and structured error information
  - Categorized errors with specific codes: input validation (-1), execution failure (-2), unexpected results (-3), etc.
  - Improved debugging with detailed error logging and context preservation
- **Type Annotation Fixes**: Corrected type annotation inconsistencies in `query_clinical_trials` function
  - Changed return type from `Optional[Dict[str, Any]]` to `Dict[str, Any]` to match actual behavior
  - Updated documentation to reflect that function always returns dictionary (success or error)
  - Verified compatibility across all call sites and maintained backward compatibility
- **Comprehensive Test Suite**: Implemented full test coverage replacing stubbed test files with 26 comprehensive test cases
  - `tests/test_query.py`: 13 test cases covering API queries, input validation, parameter correction, error handling, and network failures
  - `tests/test_summarize.py`: 10 test cases covering trial summarization, phase grouping, content truncation, and malformed data handling
  - All tests use proper mocking for external dependencies and comprehensive assertions for edge cases
  - Achieved 100% test coverage of critical functions with production-ready test patterns
- **Logging Implementation**: Replaced all print statements with proper logging module for improved debugging and maintainability
  - Added structured logging with timestamps and level-based formatting in `clinicaltrials/query.py`
  - Configured centralized logging in `clinicaltrials_mcp_server.py` with stderr output for MCP compatibility
  - Implemented appropriate log levels: ERROR for errors, WARNING for parameter validation, INFO for operations, DEBUG for troubleshooting
  - All 11 print statements in query.py and 5 in MCP server replaced with proper logging calls
- **Windsurf Memory Documentation**: Created `docs/memory_vs_windsurfrules.md` to document handling of `.windsurfrules` character limits and the use of Windsurf memory as a workaround. Includes comparison table and clear instructions.
- **README Enhancements**: Updated `README.md` with a new section "Handling the .windsurfrules Character Limit" that:
  - Explains the 6,000 character limit problem.
  - Describes two solutions: using Windsurf memory and using Context7 MCP.
  - Links to `docs/memory_vs_windsurfrules.md` and `docs/context7_guide.md` for further instructions.
- **Branding Improvements**: Improved branding and clarity by replacing "AI assistant" with "Windsurf" in both documentation files.
- **Medical Disclaimer**: Added a disclaimer to the end of the README stating that the project is a prototype, not for medical use, and may make mistakes due to LLM limitations.
- **Modern Python Packaging**: Created `pyproject.toml` with project metadata and dependencies for modern Python project management
- **Dependency Lock**: Generated `uv.lock` universal lockfile for consistent dependency versions across all platforms

### Changed
- Enhanced documentation structure for clarity and ease of onboarding regarding project rules and memory usage.
- **BREAKING**: Migrated from pip/requirements.txt to uv project workflow
- Updated all development commands in `CLAUDE.md` to use `uv run` prefix
- Changed dependency management from `requirements.txt` to `pyproject.toml`
- Updated testing commands to use `uv run python -m unittest discover tests/`
- Updated MCP server startup to use `uv run python clinicaltrials_mcp_server.py`

### Removed
- **Dead Code Cleanup**: Removed unused `clinicaltrials/parse.py` and `tests/test_parse.py` files as identified in code review
- Dependency on manual virtual environment management (now handled automatically by uv)

### Fixed
- Updated the CLI workflow in `main.py` to pass the raw `clinicaltrials.gov` studies directly to `summarize_trials`, matching the data structure used by the Claude desktop MCP client.
- Removed the call to `parse_clinical_trials` from the CLI path to ensure consistent summarization output between CLI and MCP workflows.
- Resolved a lint warning by removing an unused import in `main.py`.

## [0.0.1] - 2025-04-30

### Added
- Initial clinical trial matcher, including core data parsing utilities, summarization features, and facility data extraction.
- Pure Python MCP server for clinical trials data, supporting JSON-RPC endpoints and persistent data handling.
- Clinical trials search functionality with mutation information and improved error handling for user queries.
- Enhanced API to support v2 and v2.0.3, updated query parameters, and improved asynchronous server handling for better performance.
- Acknowledgements, licensing, and development process details in the README, giving credit to contributors and clarifying project status.
- Integrated Claude Desktop with detailed setup instructions and configuration options for seamless local AI workflows.
- Robust JSON-RPC server message framing, echo methods, and enhanced manifest metadata for improved API communication and testing.
- Multiple test and minimal MCP server implementations to support rapid prototyping and integration testing.
- Keep-alive tasks and threads to ensure server stability and resilience against input/output errors.
- PocketFlow Node pattern with `prep`, `exec`, and `post` methods to better align with agentic coding principles.
- Base `Node` and `BatchNode` classes in `utils/node.py` to support modular flow-based architecture.
- Specialized node implementations in `clinicaltrials/nodes.py` for querying and summarizing clinical trials.
- Comprehensive unit tests for the Node pattern implementation in `tests/test_nodes.py`.

### Changed
- Improved error handling for closed stdin and JSON-RPC message parsing, adding debug logging and clarifying comments throughout the server codebase.
- Refactored server files for asynchronous operation, improved prompt formatting, and enhanced location-based parsing and facility support.
- Updated and clarified documentation to reflect new features, API changes, and project development phase.
- Refactored `clinicaltrials_mcp_server.py` to use the new Node pattern while maintaining the same external API.
- Updated project structure to follow a more modular, flow-based architecture for improved maintainability and testability.
- Reverted recent changes to `clinicaltrials_mcp_server.py` to restore previous stable behavior.
- Refactored the server to use the FastMCP framework, simplifying JSON-RPC handling and improving maintainability.

### Removed
- Unused variables and outdated prototype server files to streamline the codebase.
- Template and setup files from the initial project structure to focus on core functionality.
- Test and prototype MCP server implementations to clean up the codebase and focus on the main server logic.