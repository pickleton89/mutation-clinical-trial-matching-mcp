# Changelog

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
- Created `docs/memory_vs_windsurfrules.md` to document handling of `.windsurfrules` character limits and the use of Windsurf  memory as a workaround. Includes comparison table and clear instructions.
- Updated `README.md` with a new section "Handling the .windsurfrules Character Limit" that:
  - Explains the 6,000 character limit problem.
  - Describes two solutions: using Windsurf  memory and using Context7 MCP.
  - Links to `docs/memory_vs_windsurfrules.md` and `docs/context7_guide.md` for further instructions.
- Improved branding and clarity by replacing "AI assistant" with "Windsurf " in both documentation files.
- Added a disclaimer to the end of the README stating that the project is a prototype, not for medical use, and may make mistakes due to LLM limitations.
- Created `pyproject.toml` with project metadata and dependencies for modern Python project management
- Generated `uv.lock` universal lockfile for consistent dependency versions across all platforms

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

All notable changes to this project will be documented in this file.

---

## [Unreleased]
- Ongoing development and improvements.

## [2025-05-02] - CLI and MCP Client Alignment
### Fixed
- Updated the CLI workflow in `main.py` to pass the raw `clinicaltrials.gov` studies directly to `summarize_trials`, matching the data structure used by the Claude desktop MCP client.
- Removed the call to `parse_clinical_trials` from the CLI path to ensure consistent summarization output between CLI and MCP workflows.
- Resolved a lint warning by removing an unused import in `main.py`.

## [2025-05-02] - Documentation Refactor & Clarity Improvements
### Changed
- Major refactor of `docs/context7_guide.md` ([commit be35e0f4](https://github.com/pickleton89/mutation-clinical-trial-matching-mcp/commit/be35e0f48311a21532bea89ebdc04310054ab11f)):
  - Improved internal logic consistency and document structure for easier understanding.
  - Added a "Quick Start" summary and reorganized sections for optimal flow.
  - Flattened heading hierarchy and replaced deep heading levels with clear, concise subsections.
  - Merged and deduplicated "Benefits" and "Best Practices" sections.
  - Clarified token limit guidance, memory creation, and library ID variability.
  - Grouped "Natural Language Prompting" and "Explicit Function Calls" as parallel options.
  - Updated all content to align with Pocket Flow and Agentic Coding best practices.
- General documentation now better supports onboarding and reference for new contributors.

## [2025-05-02] - Documentation Enhancement
### Added
- Created comprehensive API documentation in `docs/api.md` detailing the MCP server interface, ClinicalTrials.gov API integration, data structures, and error handling.
- Added detailed implementation guide in `docs/implementation_guide.md` following the 7-step Agentic Coding approach with code examples.
- Created developer guide in `docs/developer_guide.md` for contributors, explaining project structure, extension patterns, testing, and deployment.
- Added design patterns documentation in `docs/design_patterns.md` detailing PocketFlow patterns (Node, Flow, BatchNode), Agent pattern, and implementation examples.
- Created Context7 MCP guide in `docs/context7_guide.md` explaining how to use the Context7 MCP server to access Pocket Flow documentation and guidance during development.
- Enhanced project documentation to align with Pocket Flow framework guidelines.

## [2025-05-02]
### Added
- Created `CHANGELOG.md` to track the narrative of project changes, decisions, and milestones.
- Initial setup for structured changelog entries.
- Implemented PocketFlow Node pattern with `prep`, `exec`, and `post` methods to better align with agentic coding principles.
- Added base `Node` and `BatchNode` classes in `utils/node.py` to support modular flow-based architecture.
- Created specialized node implementations in `clinicaltrials/nodes.py` for querying and summarizing clinical trials.
- Added comprehensive unit tests for the Node pattern implementation in `tests/test_nodes.py`.

### Changed
- Refactored `clinicaltrials_mcp_server.py` to use the new Node pattern while maintaining the same external API.
- Updated project structure to follow a more modular, flow-based architecture for improved maintainability and testability.

## [2025-05-01]
### Added
- Added a minimal MCP server and test files with basic echo functionality to support lightweight server testing and validation.
- Implemented a basic MCP server with an echo method and request/response handling for foundational JSON-RPC communication.
- Developed a simple echo server with JSON-RPC message handling and content-length framing, enabling robust inter-process communication.
- Introduced a pure JSON MCP server for Claude Desktop integration, focusing on echo functionality and ease of local AI integration.

### Changed
- Reverted recent changes to `clinicaltrials_mcp_server.py` to restore previous stable behavior.
- Refactored the server to use the FastMCP framework, simplifying JSON-RPC handling and improving maintainability.
- Removed test and prototype MCP server implementations to clean up the codebase and focus on the main server logic.

---

## [2025-05-01]
### Added
- Integrated Claude Desktop with detailed setup instructions and configuration options for seamless local AI workflows.
- Implemented robust JSON-RPC server message framing, echo methods, and enhanced manifest metadata for improved API communication and testing.
- Added multiple test and minimal MCP server implementations to support rapid prototyping and integration testing.
- Introduced keep-alive tasks and threads to ensure server stability and resilience against input/output errors.

### Changed
- Improved error handling for closed stdin and JSON-RPC message parsing, adding debug logging and clarifying comments throughout the server codebase.
- Removed unused variables and outdated prototype server files to streamline the codebase.

## [2025-04-30]
### Added
- Launched the initial clinical trial matcher, including core data parsing utilities, summarization features, and facility data extraction.
- Developed a pure Python MCP server for clinical trials data, supporting JSON-RPC endpoints and persistent data handling.
- Added clinical trials search functionality with mutation information and improved error handling for user queries.
- Enhanced the API to support v2 and v2.0.3, updated query parameters, and improved asynchronous server handling for better performance.
- Included acknowledgements, licensing, and development process details in the README, giving credit to contributors and clarifying project status.

### Changed
- Refactored server files for asynchronous operation, improved prompt formatting, and enhanced location-based parsing and facility support.
- Updated and clarified documentation to reflect new features, API changes, and project development phase.
- Removed template and setup files from the initial project structure to focus on core functionality.



---

## How to use this changelog
- Use the date headings (e.g., [2025-05-02]) for each update.
- Under each date, group changes by type (Added, Changed, Fixed, Removed, etc.).
- Write brief, clear, and narrative-style descriptions of what was done and why.


