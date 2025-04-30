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
    prompt = (
        "You are a clinical research expert. Summarize the following clinical trials relevant to a genetic mutation for a physician audience. "
        "Highlight the most important findings, interventions, and statuses."
        "\n\nClinical Trials:\n"
    )
    for idx, trial in enumerate(trials, 1):
        prompt += f"\n**Trial {idx}:**\n"
        prompt += f"- **NCT ID:** [{trial['nct_id']}]({trial['url']})\n"
        prompt += f"- **Title:** {trial['title']}\n"
        if trial['brief_summary']:
            prompt += f"- **Summary:** {trial['brief_summary']}\n"
        if trial['conditions']:
            prompt += f"- **Conditions:** {', '.join(trial['conditions'])}\n"
        if trial['interventions']:
            prompt += f"- **Interventions:** {', '.join(trial['interventions'])}\n"
        if trial['locations']:
            prompt += f"- **Locations:** {', '.join(trial['locations'])}\n"
    prompt += ("\n\nPlease provide a concise, clinically relevant summary suitable for a physician, focusing on actionable insights and important distinctions between the trials.")
    # Send to Claude via MCP
    summary = call_claude_via_mcp(prompt)
    return summary
