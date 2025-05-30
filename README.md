# Mutation Clinical Trial Matching MCP

A Model Context Protocol (MCP) server that enables Claude Desktop to search for matches in clincialtrials.gov based on mutations. 

## Status

This is currently first phase of development. It works to retreive trials based on given mutations in the claude query. However, there are still bugs and further refinements and additions to be implemented.

## Overview

This project follows the Agentic Coding principles to create a system that integrates Claude Desktop with the clinicaltrials.gov API. The server allows for natural language queries about genetic mutations and returns summarized information about relevant clinical trials.

```mermaid
flowchart LR
    Claude[Claude Desktop] <-->|MCP Protocol| Server[MCP Server]
    
    subgraph Flow[PocketFlow]
        QueryNode[Query Node] -->|trials_data| SummarizeNode[Summarize Node]
    end
    
    Server -->|mutation| Flow
    QueryNode -->|API Request| API[Clinicaltrials.gov API]
    API -->|Trial Data| QueryNode
    Flow -->|summary| Server
    Server -->|Return| Claude
```

Each node in the flow follows the PocketFlow Node pattern with `prep`, `exec`, and `post` methods:

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
   - `utils/node.py`: Implements base Node and BatchNode classes with prep/exec/post pattern
   - `clinicaltrials/nodes.py`: Defines specialized nodes for querying and summarizing
   - `clinicaltrials_mcp_server.py`: Orchestrates the flow execution

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

## Node Pattern Implementation

This project implements the PocketFlow Node pattern, which provides a modular, maintainable approach to building AI workflows:

### Core Node Classes (`utils/node.py`)

- **Node**: Base class with `prep`, `exec`, and `post` methods for processing data
- **BatchNode**: Extension for batch processing multiple items
- **Flow**: Orchestrates execution of nodes in sequence

### Implementation Nodes (`clinicaltrials/nodes.py`)

1. **QueryTrialsNode**:
   ```python
   # Queries clinicaltrials.gov API
   def prep(self, shared): return shared["mutation"]
   def exec(self, mutation): return query_clinical_trials(mutation)
   def post(self, shared, mutation, result):
       shared["trials_data"] = result
       shared["studies"] = result.get("studies", [])
       return "summarize"
   ```

2. **SummarizeTrialsNode**:
   ```python
   # Formats trial data into readable summaries
   def prep(self, shared): return shared["studies"]
   def exec(self, studies): return format_trial_summary(studies)
   def post(self, shared, studies, summary):
       shared["summary"] = summary
       return None  # End of flow
   ```

### Flow Execution

The MCP server creates and runs the flow:

```python
# Create nodes
query_node = QueryTrialsNode()
summarize_node = SummarizeTrialsNode()

# Create flow
flow = Flow(start=query_node)
flow.add_node("summarize", summarize_node)

# Run flow with shared context
shared = {"mutation": mutation}
result = flow.run(shared)
```

This pattern separates preparation, execution, and post-processing, making the code more maintainable and testable. For more details, see the [design document](docs/design.md).

## Usage

1. Install dependencies with uv:
   ```
   uv pip install -r requirements.txt
   ```

2. Configure Claude Desktop:
   - The config at `~/Library/Application Support/Claude/claude_desktop_config.json` should already be set up

3. Start Claude Desktop and ask questions like:
   - "What clinical trials are available for EGFR L858R mutations?"
   - "Are there any trials for BRAF V600E mutations?"
   - "Tell me about trials for ALK rearrangements"

4. Use resources by asking:
   - "Can you tell me more about the KRAS G12C mutation?"

---

## Integrating with Claude Desktop 

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
2. Install uv if you don't have it already:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh    # macOS/Linux
   # or
   iwr -useb https://astral.sh/uv/install.ps1 | iex    # Windows PowerShell
   ```
3. Create a virtual environment and install dependencies in one step:
   ```bash
   uv venv .venv
   uv pip install -r requirements.txt
   ```
4. Activate the virtual environment when needed:
   ```bash
   source .venv/bin/activate    # macOS/Linux
   .venv\Scripts\activate       # Windows
   ```
5. Determine the full path to your virtual environment and project directory.
6. Update your configuration with these specific paths.

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

For a comprehensive list of planned enhancements and future work, please see the [future_work.md](docs/future_work.md) document.


## Dependencies

This project relies on the following key dependencies:

- **Python 3.7+** - Base runtime environment
- **PocketFlow** (`pocketflow>=0.0.1`) - Framework for building modular AI workflows with the Node pattern
- **MCP SDK** (`mcp[cli]>=1.0.0`) - Official Model Context Protocol SDK for building Claude Desktop tools
- **Requests** (`requests==2.31.0`) - HTTP library for making API calls to clinicaltrials.gov
- **Python-dotenv** (`python-dotenv==1.1.0`) - For loading environment variables from .env files

All dependencies can be installed using uv as described in the installation instructions.

## Troubleshooting

If Claude Desktop disconnects from the MCP server:
- Check logs at: `~/Library/Logs/Claude/mcp-server-clinicaltrials-mcp.log`
- Restart Claude Desktop
- Verify the server is running correctly

## Development Process

This project was developed using an AI-assisted coding approach, following the Agentic Coding principles where humans design and AI agents implement. The original program on main built on 2025-04-30. The implementation was created through pair programming with:

- Windsurf
   - ChatGPT 4.1
   - Claude 3.7 Sonnet

These AI assistants were instrumental in translating high-level design requirements into functional code, helping with API integration, and structuring the project according to best practices.

## Handling the `.windsurfrules` Character Limit

The PocketFlow `.windsurfrules` file from the template repository contains comprehensive project rules, but Windsurf enforces a 6,000 character limit on rules files. This means you cannot include the entire set of guidelines directly in your project, and important rules may be omitted or truncated.

To address this, there are two recommended solutions:

### 1. Using Windsurf 🪁 Memory to Store Rules

You can leverage Windsurf’s memory feature to store the full set of PocketFlow rules, even if they exceed the `.windsurfrules` file limit. This approach allows you to reference all project conventions and best practices in conversation with Windsurf, ensuring nothing is lost due to truncation. For step-by-step instructions and a detailed comparison of memory vs. rules files, see [docs/memory_vs_windsurfrules.md](docs/memory_vs_windsurfrules.md).

### 2. Using Context7 to Access Guidelines

**Important Note**: This project is based on the [PocketFlow-Template-Python](https://github.com/The-Pocket/PocketFlow-Template-Python) repository, which includes a comprehensive `.windsurfrules` file. However, Windsurf has a 6,000 character limit for rules files, meaning the complete PocketFlow guidelines cannot be fully loaded into Windsurf's memory.

To address this limitation, we've created detailed instructions on using the Context7 MCP server to access PocketFlow guidelines during development. This approach allows you to leverage the full power of PocketFlow's design patterns and best practices without being constrained by the character limit.

For comprehensive instructions on using Context7 with PocketFlow, please refer to our [Context7 Guide](docs/context7_guide.md). This guide includes:

- Step-by-step instructions for configuring Context7 MCP in Windsurf
- Natural language prompts for accessing PocketFlow documentation
- Examples of retrieving specific implementation patterns
- How to save important patterns as memories for future reference

By following this guide, you can maintain alignment with PocketFlow's Agentic Coding principles while developing and extending this project.

## Acknowledgements

This project was built using the [PocketFlow-Template-Python](https://github.com/The-Pocket/PocketFlow-Template-Python) as a starting point. Special thanks to the original contributors of that project for providing the foundation and structure that made this implementation possible.

The project follows the Agentic Coding methodology as outlined in the original template.

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
⚠️ **Disclaimer**

This project is a prototype and is intended for research and demonstration purposes only. It should not be used to make medical decisions or as a substitute for professional medical advice, diagnosis, or treatment. Due to the limitations of large language models (LLMs), the information provided by this tool may be incomplete, inaccurate, or outdated. Users should exercise caution and consult qualified healthcare professionals before making any decisions based on the outputs of this system.

---
