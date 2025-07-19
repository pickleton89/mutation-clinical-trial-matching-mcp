"""
Functions to summarize clinical trial results using Claude via MCP.
"""

from utils.llm_service import get_sync_llm_service


def call_claude_via_mcp(prompt: str) -> str:
    """
    Send the prompt to Claude via MCP (call_llm utility) and return the summary.
    """
    llm_service = get_sync_llm_service()
    return llm_service.call_llm(prompt)


def summarize_trials(trials: list[dict]) -> str:
    """
    Format trial data into a prompt and send to Claude via MCP for summarization.

    Args:
        trials (List[Dict]): List of structured clinical trial dictionaries from clinicaltrials.gov API.
    """
    if not trials:
        return "No clinical trials found for the specified mutation."

    # Instead of calling Claude, we'll generate a structured summary directly
    # This avoids the circular dependency where MCP server calls Claude which calls MCP server

    summary = "# Clinical Trials Summary\n\n"

    # Add overview
    trial_count = len(trials)
    summary += f"Found {trial_count} clinical trial{'s' if trial_count != 1 else ''} matching the mutation.\n\n"

    # Extract and organize phases
    phases = {}
    for trial in trials:
        # Extract data from the nested structure
        protocol = trial.get("protocolSection", {})

        # Get phase information
        phase_info = protocol.get("phaseModule", {}).get("phase", "Unknown Phase")
        if not phase_info:
            phase_info = "Unknown Phase"

        # Initialize this phase if not already present
        if phase_info not in phases:
            phases[phase_info] = []

        # Add trial to the appropriate phase
        phases[phase_info].append(trial)

    # Add summary by phase
    for phase, phase_trials in phases.items():
        summary += f"## {phase} Trials ({len(phase_trials)})\n\n"

        for trial in phase_trials:
            # Extract core information
            protocol = trial.get("protocolSection", {})

            # Get identification data
            id_module = protocol.get("identificationModule", {})
            title = id_module.get("briefTitle", "Untitled Trial")
            nct_id = id_module.get("nctId", "Unknown")

            # Get status
            status_module = protocol.get("statusModule", {})
            status = status_module.get("overallStatus", "Unknown")

            # Get conditions
            conditions_module = protocol.get("conditionsModule", {})
            conditions = conditions_module.get("conditions", [])

            # Get interventions
            interventions_module = protocol.get("armsInterventionsModule", {})
            interventions = [
                intervention.get("name", "")
                for intervention in interventions_module.get("interventions", [])
            ]

            # Get summary
            description_module = protocol.get("descriptionModule", {})
            brief_summary = description_module.get("briefSummary", "")

            # Get locations
            contacts_module = protocol.get("contactsLocationsModule", {})
            locations = [
                f"{location.get('facility', '')} ({location.get('city', '')}, {location.get('country', '')})"
                for location in contacts_module.get("locations", [])[:3]
            ]  # Limit to 3 locations

            # Format the trial information
            summary += f"### {title}\n"
            summary += f"- **NCT ID:** [{nct_id}](https://clinicaltrials.gov/study/{nct_id})\n"

            if brief_summary:
                # Truncate summary if it's too long
                if len(brief_summary) > 200:
                    brief_summary = brief_summary[:197] + "..."
                summary += f"- **Summary:** {brief_summary}\n"

            if conditions:
                summary += (
                    f"- **Conditions:** {', '.join(conditions[:5])}\n"  # Limit to 5 conditions
                )

            if interventions:
                summary += f"- **Interventions:** {', '.join(interventions[:5])}\n"  # Limit to 5 interventions

            if status:
                summary += f"- **Status:** {status}\n"

            if locations:
                summary += f"- **Locations:** {', '.join(locations)}\n"

            summary += "\n"

    return summary
