# Using Context7 MCP for Pocket Flow Guidance

> **Quick Start**
> 1. Ensure Context7 MCP is enabled in Windsurf Settings.
> 2. Use natural language or explicit function calls to retrieve Pocket Flow documentation.
> 3. Save important patterns as "memories" for easy reference.

---

## Introduction

This guide explains how to use the Context7 MCP server to access up-to-date documentation and guidance from the Pocket Flow repository during development.

## Benefits

- **Seamless Integration:** No extra setup if using Windsurf
- **Up-to-date Documentation:** Always access the latest Pocket Flow guidelines
- **Context-aware Assistance:** Guidance tailored to your project
- **Memory Integration:** Save important patterns as memories for future reference

## Prerequisites

- Access to Windsurf with Context7 MCP support
- Basic understanding of the Pocket Flow framework

## Configuring Context7 MCP in Windsurf

Windsurf comes with built-in support for Context7 MCP, but you may need to ensure it's properly configured. Follow these steps:

### Step-by-Step Instructions

1. **Open Windsurf Settings**:
   - Launch Windsurf
   - Click the gear icon (⚙️) in the top-right corner
   - Or use `Cmd+,` (Mac) or `Ctrl+,` (Windows)

2. **Navigate to MCP Servers Section**:
   - In the Settings sidebar, look for "Integrations" or "Extensions"
   - Click on "MCP Servers" or "Model Context Protocol"
   - This opens the MCP server configuration panel

3. **Verify Context7 MCP Server**:
   - In the list of available MCP servers, look for "context7" or "Context7"
   - If it's already listed and has a checkmark or toggle switch in the "Enabled" state, it's already configured

4. **Add Context7 MCP Server (if not present)**:
   - If Context7 is not listed, click the "Add Server" or "+" button
   - In the dialog that appears, enter the following information:
     - **Name**: `context7`
     - **Description**: `Provides access to documentation from various libraries and repositories`
     - **Endpoint URL**: `https://api.context7.ai/v1` (or the URL provided by your Windsurf administrator)
   - Click "Save" or "Add" to confirm

5. **Enable the Server**:
   - If the server is added but not enabled, click the toggle switch or checkbox next to Context7 to enable it
   - Some configurations may require you to restart Windsurf for changes to take effect

6. **Test the Configuration**:
   - Return to the main Windsurf interface
   - Start a new conversation
   - Type: `Can you verify that the Context7 MCP server is available?`
   - The assistant should confirm that Context7 is available and ready to use

### Verifying Context7 MCP Availability

When working with Windsurf, you can verify the Context7 MCP server is properly configured by checking the MCP servers section in your system prompt, which should include Context7.

## Using Context7 MCP with Pocket Flow

### Accessing Pocket Flow Documentation

You can access Pocket Flow documentation using either natural language prompting or explicit function calls.

#### Natural Language Prompting

You can use natural language prompts to ask for guidance on Pocket Flow. This approach is more intuitive and aligns with the Agentic Coding principles where humans design and agents code.

##### Example Natural Language Prompts

- **Resolving Library ID**: `Can you use the context7 MCP server to find the library ID for the Pocket Flow repository?`
- **Retrieving Documentation**: `Can you retrieve documentation about the Node pattern from the Pocket Flow repository using Context7 MCP?`
- **Implementing a Specific Pattern**: `How should I implement the BatchNode pattern according to Pocket Flow guidelines? Can you use Context7 to show me examples?`

#### Explicit Function Calls

If you prefer a more structured approach, you can use explicit function calls to access Pocket Flow documentation.

##### Step 1: Resolve the Library ID

Before retrieving documentation, you need to resolve the Pocket Flow library ID using the `resolve-library-id` function:

```
resolve-library-id(libraryName: "the-pocket/pocketflow")
```

This will return available Context7-compatible library IDs, such as:
- `/the-pocket/pocketflow`
- `/the-pocket/pocketflow-tutorial-codebase-knowledge`
- `/the-pocket-world/pocket-flow-framework`

##### Step 2: Retrieve Documentation

Once you have the library ID, use the `get-library-docs` function to retrieve documentation:

```
get-library-docs(
  context7CompatibleLibraryID: "/the-pocket/pocketflow",
  tokens: 5000,
  topic: "project structure"
)
```

Parameters:
- `context7CompatibleLibraryID`: The exact library ID from step 1
- `tokens`: Maximum number of tokens to retrieve (default: 5000)
- `topic`: Optional topic to focus on (e.g., "getting started", "project structure", "node pattern")

### Creating Memories from Pocket Flow Documentation

One powerful way to enhance your development workflow is to save important Pocket Flow patterns and guidelines as memories in your Windsurf environment. This allows you to maintain consistent access to key principles without repeatedly querying the Context7 MCP server.

#### Benefits of Creating Memories

1. **Persistent Access**: Memories persist across sessions, providing continuous access to important guidelines
2. **Project-Specific Context**: Memories can be tailored to your specific project needs
3. **Reduced Latency**: Accessing memories is faster than making new Context7 MCP requests
4. **Consistent Reference**: Ensures all team members work from the same set of guidelines

#### What to Memorize

Consider creating memories for:

1. **Core Patterns**: The Node pattern, Flow orchestration, and BatchNode implementation
2. **Project Structure**: Directory organization and file naming conventions
3. **Best Practices**: Error handling, testing approaches, and optimization techniques
4. **Implementation Examples**: Specific code examples relevant to your project

#### Example Memory Creation

After retrieving documentation using Context7 MCP, you can ask to create a memory:

```
Can you create a memory with this Pocket Flow Node pattern implementation for our project?
```

Or more specifically:

```
Please save the BatchNode implementation pattern from Pocket Flow as a memory for our project.
```

### Accessing Memories

Once created, you can reference these memories during development:

```
Can you remind me of our Pocket Flow Node pattern implementation guidelines?
```

### Updating Memories

As you refine your understanding or when Pocket Flow updates, you can update memories:

```
Please update our Pocket Flow implementation memory with this new information about error handling.
```

## Troubleshooting

If you encounter issues with Context7 MCP:

1. **Check Library ID**: Ensure you're using the correct Context7-compatible library ID
2. **Refine Topic**: Try more specific or different topics
3. **Increase Token Count**: If you're getting truncated responses, increase the token count
4. **Try Alternative Libraries**: Some content may be available in related libraries

## Conclusion

The Context7 MCP server provides a powerful way to access Pocket Flow documentation and guidance during development. By following this guide, you can leverage this capability to ensure your implementation follows the recommended patterns and best practices of the Pocket Flow framework.
