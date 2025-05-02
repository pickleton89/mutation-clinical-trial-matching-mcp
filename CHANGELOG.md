# Changelog

All notable changes to this project will be documented in this file.

---

## [Unreleased]
- Ongoing development and improvements.

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


