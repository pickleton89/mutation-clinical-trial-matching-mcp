# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
- **Package Manager**: Always use `uv` for package management and environment setup
- **Install Dependencies**: `uv pip install -r requirements.txt`
- **Environment Creation**: `uv venv .venv`
- **Environment Activation**: `source .venv/bin/activate` (macOS/Linux) or `.venv\Scripts\activate` (Windows)

### Testing
- **Run All Tests**: `python -m unittest discover tests/`
- **Run Specific Test**: `python -m unittest tests.test_nodes.TestQueryTrialsNode.test_query_trials_node`
- **Test Files**: Located in `tests/` directory, following `test_*.py` pattern

### MCP Server
- **Start Server**: `python clinicaltrials_mcp_server.py`
- **Server Entry Point**: `clinicaltrials_mcp_server.py`
- **Protocol**: Uses FastMCP SDK for MCP protocol implementation

## Architecture Overview

### Core Pattern: PocketFlow Nodes
This project follows the PocketFlow Node pattern with a three-phase execution model:

1. **prep(shared)**: Extracts data from shared context
2. **exec(prep_result)**: Performs the main operation
3. **post(shared, prep_result, exec_result)**: Updates shared context and returns next node ID

### Key Components

#### 1. MCP Server (`clinicaltrials_mcp_server.py`)
- Main entry point implementing MCP protocol
- Exposes `summarize_trials(mutation: str)` tool to Claude Desktop
- Orchestrates the flow execution for clinical trial queries

#### 2. Node Implementation (`utils/node.py`)
- **Node**: Base class for single-item processing
- **BatchNode**: Base class for batch processing
- **Flow**: Orchestrates sequential node execution

#### 3. Clinical Trials Nodes (`clinicaltrials/nodes.py`)
- **QueryTrialsNode**: Queries clinicaltrials.gov API
- **SummarizeTrialsNode**: Formats trial data into readable summaries

#### 4. Query Module (`clinicaltrials/query.py`)
- Handles API calls to clinicaltrials.gov
- Includes error handling and input validation

#### 5. Summarizer (`llm/summarize.py`)
- Processes clinical trial data into markdown format
- Organizes trials by phase and extracts key information

### Data Flow
```
User Query → MCP Server → QueryTrialsNode → clinicaltrials.gov API → SummarizeTrialsNode → Formatted Summary
```

### Shared Context Structure
```python
shared = {
    "mutation": "BRAF V600E",              # Input mutation
    "trials_data": {...},                 # Raw API response
    "studies": [{...}, {...}],            # Extracted studies
    "summary": "# Clinical Trials..."     # Final summary
}
```

## Key Dependencies

- **pocketflow>=0.0.1**: PocketFlow framework for Node pattern
- **mcp[cli]>=1.0.0**: Official MCP SDK for Claude Desktop integration
- **requests==2.31.0**: HTTP requests for API calls
- **python-dotenv==1.1.0**: Environment variable management

## Development Guidelines

### Adding New Nodes
1. Inherit from `Node` or `BatchNode` in `utils/node.py`
2. Implement `prep()`, `exec()`, and `post()` methods
3. Add to flow in `clinicaltrials_mcp_server.py`
4. Add corresponding tests in `tests/`

### Error Handling
- API errors handled in `clinicaltrials/query.py`
- Node validation in `prep()` methods
- Flow errors handled in `utils/node.py`

### Testing Strategy
- Unit tests for individual nodes in `tests/test_nodes.py`
- API integration tests in `tests/test_query.py`
- Summarization tests in `tests/test_summarize.py`

## Claude Desktop Integration

Configure in `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
"mutation-clinical-trials-mcp": {
  "command": "/path/to/venv/bin/python",
  "args": ["/path/to/project/clinicaltrials_mcp_server.py"]
}
```

## Common Query Patterns

- "What clinical trials are available for EGFR L858R mutations?"
- "Are there any trials for BRAF V600E mutations?"
- "Tell me about trials for ALK rearrangements"

## Project Structure Notes

- `clinicaltrials/`: Core clinical trials functionality
- `llm/`: LLM integration for summarization
- `utils/`: Base utilities and Node pattern implementation
- `tests/`: Unit tests following unittest framework
- `docs/`: Comprehensive documentation including design patterns