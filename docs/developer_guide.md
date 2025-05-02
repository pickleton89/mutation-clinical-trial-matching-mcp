# Developer Guide: Mutation Clinical Trial Matching MCP

This guide is intended for developers who want to contribute to or extend the Mutation Clinical Trial Matching MCP project. It follows the Agentic Coding principles where humans design and agents code.

## Agentic Coding Approach

This project follows the Agentic Coding paradigm, which emphasizes collaboration between human system design and AI implementation:

| Steps                  | Human      | AI        | Comment                                                                 |
|:-----------------------|:----------:|:---------:|:------------------------------------------------------------------------|
| 1. Requirements | ★★★ High  | ★☆☆ Low   | Humans understand the requirements and context.                    |
| 2. Flow          | ★★☆ Medium | ★★☆ Medium |  Humans specify the high-level design, and the AI fills in the details. |
| 3. Utilities   | ★★☆ Medium | ★★☆ Medium | Humans provide available external APIs and integrations, and the AI helps with implementation. |
| 4. Node          | ★☆☆ Low   | ★★★ High  | The AI helps design the node types and data handling based on the flow.          |
| 5. Implementation      | ★☆☆ Low   | ★★★ High  |  The AI implements the flow based on the design. |
| 6. Optimization        | ★★☆ Medium | ★★☆ Medium | Humans evaluate the results, and the AI helps optimize. |
| 7. Reliability         | ★☆☆ Low   | ★★★ High  |  The AI writes test cases and addresses corner cases.     |

## Getting Started

### Prerequisites

- Python 3.9 or higher
- uv package manager (recommended)
- Claude Desktop (for testing)

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd mutation_clinical_trial_matching_mcp
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   uv venv .venv
   uv pip install -r requirements.txt
   ```

3. Activate the virtual environment:
   ```bash
   source .venv/bin/activate  # On macOS/Linux
   .venv\Scripts\activate     # On Windows
   ```

## Project Structure

```
mutation_clinical_trial_matching_mcp/
├── clinicaltrials/              # Clinical trials domain logic
│   ├── __init__.py
│   ├── nodes.py                 # PocketFlow nodes for clinical trials
│   ├── query.py                 # API client for clinicaltrials.gov
│   └── resources.py             # Mutation information resources
├── docs/                        # Documentation
│   ├── api.md                   # API documentation
│   ├── design.md                # Design document
│   ├── developer_guide.md       # This guide
│   └── implementation_guide.md  # Implementation details
├── llm/                         # LLM-related functionality
│   ├── __init__.py
│   └── summarize.py             # Trial summarization logic
├── tests/                       # Test cases
│   ├── __init__.py
│   ├── test_nodes.py            # Tests for node functionality
│   ├── test_query.py            # Tests for API client
│   └── test_summarize.py        # Tests for summarization
├── utils/                       # Utility functions
│   ├── __init__.py
│   ├── call_llm.py              # LLM API client
│   └── node.py                  # Base node classes
├── clinicaltrials_mcp_server.py # MCP server implementation
├── main.py                      # Entry point
├── README.md                    # Project overview
└── requirements.txt             # Dependencies
```

## Extending the Project

### Adding a New Node

To add a new node to the flow, follow these steps:

1. **Design the Node**: Determine the node's purpose, inputs, and outputs
2. **Create the Node Class**: Implement the node in the appropriate domain file
3. **Update the Flow**: Integrate the node into the existing flow
4. **Add Tests**: Write tests for the new node

Example of adding a new FilterTrialsNode:

```python
# clinicaltrials/nodes.py
class FilterTrialsNode(Node[List[Dict[str, Any]], List[Dict[str, Any]]]):
    """Node for filtering clinical trials based on criteria."""
    
    def __init__(self, filter_criteria=None):
        self.filter_criteria = filter_criteria or {}
    
    def prep(self, shared):
        return shared["studies"]
        
    def exec(self, studies):
        filtered_studies = []
        for study in studies:
            if self._matches_criteria(study):
                filtered_studies.append(study)
        return filtered_studies
        
    def post(self, shared, studies, filtered_studies):
        shared["filtered_studies"] = filtered_studies
        return "summarize"
        
    def _matches_criteria(self, study):
        # Implementation of filtering logic
        return True  # Replace with actual filtering logic
```

### Updating the Flow

To integrate the new node into the flow:

```python
# clinicaltrials_mcp_server.py
def handle_search_request(mutation, filter_criteria=None):
    # Create nodes
    query_node = QueryTrialsNode()
    filter_node = FilterTrialsNode(filter_criteria)
    summarize_node = SummarizeTrialsNode()
    
    # Create flow
    flow = Flow(start=query_node)
    flow.add_node("filter", filter_node)
    flow.add_node("summarize", summarize_node)
    
    # Run flow with shared context
    shared = {"mutation": mutation}
    result = flow.run(shared)
    
    return result["summary"]
```

## Testing

### Running Tests

```bash
python -m unittest discover tests
```

### Writing Tests

When writing tests, follow these principles:

1. **Test Each Node Independently**: Test the prep, exec, and post methods of each node
2. **Mock External Dependencies**: Use mocks for API calls and external services
3. **Test the Flow**: Test the complete flow with mocked nodes
4. **Test Error Handling**: Ensure errors are handled gracefully

Example test for the FilterTrialsNode:

```python
# tests/test_nodes.py
import unittest
from unittest.mock import MagicMock
from clinicaltrials.nodes import FilterTrialsNode

class TestFilterTrialsNode(unittest.TestCase):
    def test_filter_node(self):
        # Setup
        node = FilterTrialsNode({"phase": "Phase 3"})
        shared = {"studies": [
            {"protocolSection": {"designModule": {"phases": ["Phase 3"]}}},
            {"protocolSection": {"designModule": {"phases": ["Phase 2"]}}}
        ]}
        
        # Execute
        next_node = node.process(shared)
        
        # Assert
        self.assertEqual(next_node, "summarize")
        self.assertEqual(len(shared["filtered_studies"]), 1)
        self.assertEqual(
            shared["filtered_studies"][0]["protocolSection"]["designModule"]["phases"][0], 
            "Phase 3"
        )
```

## Best Practices

### Follow the Node Pattern

Always adhere to the PocketFlow Node pattern:
- Implement `prep`, `exec`, and `post` methods
- Keep nodes focused on a single responsibility
- Use the shared context for data passing

### Error Handling

Implement robust error handling:
- Catch and log exceptions
- Provide meaningful error messages
- Return graceful fallbacks when possible

### Documentation

Document your code thoroughly:
- Add docstrings to all classes and methods
- Update design documents when making significant changes
- Keep the README up to date

### Testing

Write comprehensive tests:
- Unit tests for individual components
- Integration tests for the complete flow
- Edge case tests for error handling

## Deployment

### Local Development

For local development and testing:

```bash
python clinicaltrials_mcp_server.py
```

### Claude Desktop Integration

To integrate with Claude Desktop:

1. Configure the MCP tool in Claude Desktop's configuration file
2. Point to your local server implementation
3. Test the integration with sample queries

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for your changes
5. Ensure all tests pass
6. Submit a pull request

## Resources

- [PocketFlow Documentation](https://github.com/the-pocket/pocketflow)
- [ClinicalTrials.gov API Documentation](https://clinicaltrials.gov/api/gui)
- [Model Context Protocol Specification](https://github.com/anthropics/anthropic-cookbook/tree/main/mcp)
- [Claude Desktop Documentation](https://claude.ai/docs/desktop)
