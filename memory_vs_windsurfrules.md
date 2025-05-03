# AI Assistant Reference and Project Rules

## Problem Statement

Many projects, such as those using the PocketFlow framework, rely on a `.windsurfrules` file to define project structure, coding conventions, and workflow rules. However, this file is limited to 6000 characters in Windsurf, and any content beyond that is ignored by Cascade. This presents a challenge when trying to use comprehensive rule sets—such as those from the PocketFlow template repository—that exceed this limit. This document provides guidance on how to preserve and leverage all project rules by utilizing the AI assistant’s memory feature alongside the `.windsurfrules` file.

## How the AI Assistant Uses Project References

- **Accessing Reference Files:**
  - The assistant can fetch and read public files (e.g., `.windsurfrules` on GitHub) using stable URLs.
  - These files provide essential project structure, coding conventions, and workflow guidelines.

- **Creating and Using Memory:**
  - The assistant can store important rules and context from these files in its memory.
  - This memory persists across conversations and can be referenced whenever needed, ensuring continuity even in long-term or multi-session projects.

- **Maintaining Project Consistency:**
  - By combining file-based rules and persistent memory, the assistant helps maintain consistent project organization, coding standards, and workflow.

## Using the PocketFlow Template .windsurfrules in Your Project

If you try to use the `.windsurfrules` file from the [PocketFlow Template Python repository](https://github.com/The-Pocket/PocketFlow-Template-Python/blob/main/.windsurfrules), you may notice that it exceeds the 6000-character limit imposed on `.windsurfrules` (and `global_rules.md`) files in Windsurf. Any content above 6000 characters will be truncated and Cascade will not be aware of it. This means you cannot copy the entire file directly into your own project's `.windsurfrules` if it is too long, or you risk losing important rules or context.

**Recommended Solution: Store the Rules in AI Memory**

To retain all the valuable rules and guidelines from the template, you should:

1. **Copy the contents** of the template `.windsurfrules` file.
2. **Ask the AI assistant** to store these rules in memory. For example, you can say:
   > "Please store the following PocketFlow rules in memory for use in this project: ..."
3. The assistant will create a persistent memory entry, making the rules accessible across multiple conversations and sessions.
4. **Reference the memory** in your documentation or workflow, so you and collaborators know the rules are available via the assistant, even if they aren't all in the file.

**Tip:** You can also summarize or split the rules into logical sections and store them as multiple memory entries for easier access and organization.

This approach ensures you keep the full set of project rules and conventions, even when file size limits prevent you from including everything in `.windsurfrules` directly.


## Additional Background Information

### Memory vs. .windsurfrules File: Comparison

The table below summarizes the key differences between using the AI assistant’s memory and the `.windsurfrules` file for storing project rules and conventions:

| Feature           | Memory (AI)                                 | .windsurfrules File                                          |
|-------------------|---------------------------------------------|--------------------------------------------------------------|
| **Source**        | Created by AI based on file contents        | Original project configuration                               |
| **Persistence**   | AI-managed database, spans conversations    | Version-controlled file                                      |
| **Accessibility** | Available in all relevant AI interactions   | Accessible via URL/GitHub                                    |
| **Content**       | Interpreted guidelines, context, examples   | Raw configuration rules                                      |
| **Updates**       | Can be updated by AI or user                | Updated via Git commits                                      |
| **Scope**         | Project-specific context and rules          | Project structure and conventions                            |
| **Format**        | Free-form, can be split into multiple entries| Structured, single-file, concise                             |
| **Purpose**       | Conversation context, reference, reasoning  | Project setup and validation                                 |
| **Character Limit** | No strict limit (can be extensive)        | Capped at 6000 characters (content above this is ignored)    |

**Key Points:**
- **Source of Truth:** `.windsurfrules` is the definitive, version-controlled source; memory is an AI interpretation and extension.
- **Content Depth & Organization:** Memory can include detailed explanations and be split into multiple entries, while `.windsurfrules` must be concise and fit in a single file.
- **Update Process:** Memory can be updated dynamically by the AI or user; `.windsurfrules` requires a Git commit.
- **Character Limit:** Memory has no strict limit, but `.windsurfrules` is capped at 6000 characters—content above this will be truncated and ignored by Cascade.

**Summary:**  
While `.windsurfrules` is ideal for essential, versioned project structure rules, the AI's memory feature allows for more detailed, persistent, and context-rich guidance. Used together, they ensure both strict adherence to project requirements and flexible, informed assistance throughout the project lifecycle.