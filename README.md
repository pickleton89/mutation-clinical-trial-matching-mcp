# Mutation Clinical Trial Matching MCP

A Model Context Protocol (MCP) server that enables Claude Desktop to search for matches in clincialtrials.gov based on mutations. 

## Status

This is currently first phase of development. It works to retreive trials based on given mutations in the claude query. However, there are still bugs and further refinements and additions to be implemented.

## Overview

This project follows the Agentic Coding principles to create a system that integrates Claude Desktop with the clinicaltrials.gov API. The server allows for natural language queries about genetic mutations and returns summarized information about relevant clinical trials.

```mermaid
flowchart LR
    Claude[Claude Desktop] <-->|MCP Protocol| Server[MCP Server]
    Server -->|Query| API[Clinicaltrials.gov API]
    API -->|Trial Data| Server
    Server -->|Format| Summary[Summarize Data]
    Summary -->|Structured Response| Server
    Server -->|Return| Claude
```

## Project Structure

This project is organized according to the Agentic Coding paradigm:

1. **Requirements** (Human-led):
   - Search and summarize clinical trials related to specific genetic mutations
   - Provide mutation information as contextual resources
   - Integrate seamlessly with Claude Desktop

2. **Flow Design** (Collaborative):
   - User queries Claude Desktop about a genetic mutation
   - Claude calls our MCP server tool
   - Server queries clinicaltrials.gov API
   - Server processes and summarizes the results
   - Server returns formatted results to Claude

3. **Utilities** (Collaborative):
   - `clinicaltrials/query.py`: Handles API calls to clinicaltrials.gov
   - `utils/call_llm.py`: Utilities for working with Claude

4. **Node Design** (AI-led):
   - `llm/summarize.py`: Formats clinical trial data into readable summaries
   - `clinicaltrials_mcp_server.py`: Implements the MCP server interface

5. **Implementation** (AI-led):
   - FastMCP SDK for handling the protocol details
   - Error handling at all levels
   - Resources for common mutations

## Components

### MCP Server (`clinicaltrials_mcp_server.py`)

The main server that implements the Model Context Protocol interface, using the official Python SDK. It:

- Registers and exposes tools for Claude to use
- Provides resources with information about common mutations
- Handles the communication with Claude Desktop

### Query Module (`clinicaltrials/query.py`)

Responsible for querying the clinicaltrials.gov API with:
- Robust error handling
- Input validation
- Detailed logging

### Summarizer (`llm/summarize.py`) 

Processes and formats the clinical trials data:
- Organizes trials by phase
- Extracts key information (NCT ID, summary, conditions, etc.)
- Creates a readable markdown summary

## Usage

1. Install dependencies:
   ```
   uv pip install -r requirements.txt
   ```

2. Configure Claude Desktop:
   - The config at `/Users/jeffkiefer/Library/Application Support/Claude/claude_desktop_config.json` should already be set up

3. Start Claude Desktop and ask questions like:
   - "What clinical trials are available for EGFR L858R mutations?"
   - "Are there any trials for BRAF V600E mutations?"
   - "Tell me about trials for ALK rearrangements"

4. Use resources by asking:
   - "Can you tell me more about the KRAS G12C mutation?"

---

## Integrating with Claude Desktop (context7)

You can configure this project as a Claude Desktop MCP tool. Use path placeholders in your configuration, and substitute them with your actual paths:

```json
"mutation-clinical-trials-mcp": {
  "command": "{PATH_TO_VENV}/bin/python",
  "args": [
    "{PATH_TO_PROJECT}/clinicaltrials_mcp_server.py"
  ],
  "description": "Matches genetic mutations to relevant clinical trials and provides summaries."
}
```

**Path Variables:**
- `{PATH_TO_VENV}`: Full path to your virtual environment directory.
- `{PATH_TO_PROJECT}`: Full path to the directory containing your project files.

**Installation Instructions:**
1. Clone the repository to your local machine.
2. Create a virtual environment:  
   ```bash
   python -m venv .venv
   ```
3. Activate the virtual environment and install dependencies:  
   ```bash
   source .venv/bin/activate    # macOS/Linux  
   .venv\Scripts\activate       # Windows  
   pip install -r requirements.txt
   ```
4. Determine the full path to your virtual environment and project directory.
5. Update your configuration with these specific paths.

**Examples:**
- On macOS/Linux:
  ```json
  "command": "/Users/username/projects/mutation_trial_matcher/.venv/bin/python"
  ```
- On Windows:
  ```json
  "command": "C:\\Users\\username\\projects\\mutation_trial_matcher\\.venv\\Scripts\\python.exe"
  ```

**Path Finding Tips:**
- To find the exact path to your Python interpreter in the virtual environment, run:
  - `which python` (macOS/Linux)
  - `where python` (Windows, after activating the venv)
- For the project path, use the full path to the directory containing `clinicaltrials_mcp_server.py`.

---

## Future Improvements

1. Add additional tools for:
   - Filtering trials by location, phase, or status
   - Getting detailed information about a specific trial by NCT ID

2. Expand resources with:
   - More mutation types
   - Treatment options for each mutation type
   - Survival statistics

3. Improve summarization with:
   - Categorization by intervention type
   - Highlighting novel treatment approaches

## Dependencies

- Python 3.7+
- mcp[cli] - Official Model Context Protocol SDK
- requests - For API calls
- python-dotenv - For environment variable management

## Troubleshooting

If Claude Desktop disconnects from the MCP server:
- Check logs at: `/Users/jeffkiefer/Library/Logs/Claude/mcp-server-clinicaltrials-mcp.log`
- Restart Claude Desktop
- Verify the server is running correctly

## Acknowledgements

This project was built using the [PocketFlow-Template-Python](https://github.com/The-Pocket/PocketFlow-Template-Python) as a starting point. Special thanks to the original contributors of that project for providing the foundation and structure that made this implementation possible.

The project follows the Agentic Coding methodology as outlined in the original template.

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Development Process

This project was developed using an AI-assisted coding approach, following the Agentic Coding principles where humans design and AI agents implement. The original program on main built on 2025-04-30. The implementation was created through pair programming with:

- Windsurf
   - ChatGPT 4.1
   - Claude 3.7 Sonnet

These AI assistants were instrumental in translating high-level design requirements into functional code, helping with API integration, and structuring the project according to best practices.
