"""
Functions to summarize clinical trial results using Claude via MCP.
"""

from typing import List, Dict

from utils.call_llm import call_llm


def call_claude_via_mcp(prompt: str) -> str:
    """
    Send the prompt to Claude via MCP (call_llm utility) and return the summary.
    """
    return call_llm(prompt)


def summarize_trials(trials: List[Dict]) -> str:
    """
    Format trial data into a prompt and send to Claude via MCP for summarization.

    Args:
        trials (List[Dict]): List of structured clinical trial dictionaries.
    """
    if not trials:
        return "No clinical trials found for the specified mutation."

    # Instead of calling Claude, we'll generate a structured summary directly
    # This avoids the circular dependency where MCP server calls Claude which calls MCP server

    summary = "# Clinical Trials Summary\n\n"

    # Add overview
    trial_count = len(trials)
    summary += f"Found {trial_count} clinical trial{'s' if trial_count != 1 else ''} matching the mutation.\n\n"

    # Group trials by phase if available
    phases = {}
    for trial in trials:
        phase = trial.get("phase", "Unknown")
        if phase not in phases:
            phases[phase] = []
        phases[phase].append(trial)

    # Add summary by phase
    for phase, phase_trials in phases.items():
        summary += f"## {phase} Phase Trials ({len(phase_trials)})\n\n"

        for trial in phase_trials:
            summary += f"### {trial.get('title', 'Untitled Trial')}\n"
            summary += f"- **NCT ID:** [{trial.get('nct_id', 'Unknown')}]({trial.get('url', '#')})\n"

            if trial.get("brief_summary"):
                summary += f"- **Summary:** {trial['brief_summary']}\n"

            if trial.get("conditions"):
                summary += f"- **Conditions:** {', '.join(trial['conditions'])}\n"

            if trial.get("interventions"):
                summary += f"- **Interventions:** {', '.join(trial['interventions'])}\n"

            if trial.get("status"):
                summary += f"- **Status:** {trial['status']}\n"

            if trial.get("locations"):
                summary += f"- **Locations:** {', '.join(trial['locations'])}\n"

            summary += "\n"

    return summary
