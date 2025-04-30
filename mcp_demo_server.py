#!/usr/bin/env python3
"""
MCP server for querying and summarizing clinical trials related to genetic mutations.
Built using the official Model Context Protocol Python SDK.
"""
import traceback
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials

# Create an MCP server
mcp = FastMCP("Clinical Trials MCP")

# Common mutations information
COMMON_MUTATIONS = {
    "EGFR L858R": "A point mutation in exon 21 of the EGFR gene. It substitutes a leucine with an arginine at position 858, resulting in constitutive activation of the EGFR kinase domain. Common in non-small cell lung cancer (NSCLC), particularly in never-smokers, women, and East Asian populations.",
    "EGFR T790M": "A point mutation in exon 20 of the EGFR gene, substituting threonine with methionine at position 790. It's the most common mechanism of acquired resistance to first-generation EGFR tyrosine kinase inhibitors (TKIs) such as erlotinib and gefitinib.",
    "EGFR exon 19 deletion": "A deletion in exon 19 of the EGFR gene, most commonly removing amino acids 746-750. Along with L858R, it's one of the most common activating EGFR mutations in NSCLC and predicts sensitivity to EGFR TKIs.",
    "BRAF V600E": "A point mutation in the BRAF gene causing a substitution of valine with glutamic acid at position 600. Common in melanoma, colorectal cancer, and papillary thyroid cancer. It leads to constitutive activation of the MAPK pathway.",
    "KRAS G12C": "A point mutation in the KRAS gene, substituting glycine with cysteine at position 12. Common in lung adenocarcinoma and colorectal cancer. It was previously considered 'undruggable' but new targeted therapies like sotorasib have been developed.",
    "ALK rearrangement": "A chromosomal rearrangement involving the ALK gene, most commonly EML4-ALK fusion in NSCLC. It leads to constitutive activation of ALK kinase and is targetable with ALK inhibitors like crizotinib, alectinib, and brigatinib."
}

# Add resources for common mutations information
for mutation_name, mutation_info in COMMON_MUTATIONS.items():
    resource_id = f"mutation://{mutation_name.lower().replace(' ', '-')}"
    
    @mcp.resource(resource_id)
    def get_mutation_info() -> str:
        return f"# {mutation_name}\n\n{mutation_info}"

# Add a tool to summarize clinical trials for a mutation with improved error handling
@mcp.tool()
def summarize_trials_for_mutation(mutation: str) -> Dict[str, Any]:
    """
    Summarize clinical trials related to a specific genetic mutation.
    
    Args:
        mutation: The genetic mutation to search for (e.g., 'EGFR L858R')
    
    Returns:
        A summary of relevant clinical trials formatted in markdown
    """
    try:
        print(f"Querying for: {mutation}")
        
        # Input validation
        if not mutation or not isinstance(mutation, str) or len(mutation.strip()) == 0:
            return {"isError": True, "content": [{"type": "text", "text": "Error: Please provide a valid mutation name or identifier."}]}
        
        # Call the existing query function
        trials_data = query_clinical_trials(mutation)
        
        # Check for API errors
        if "error" in trials_data:
            error_message = trials_data["error"]
            return {
                "isError": True,
                "content": [{
                    "type": "text", 
                    "text": f"Error querying clinical trials: {error_message}"
                }]
            }
        
        # Process study data
        if "studies" in trials_data and trials_data["studies"]:
            # Use the existing summarize function
            summary = summarize_trials(trials_data["studies"])
            
            # Add a note if this is a common mutation we have information about
            normalized_mutation = mutation.upper()
            for common_mutation in COMMON_MUTATIONS:
                if common_mutation.upper() in normalized_mutation or normalized_mutation in common_mutation.upper():
                    resource_id = f"mutation://{common_mutation.lower().replace(' ', '-')}"
                    summary += f"\n\n> **Note:** Additional information about {common_mutation} is available in the resource: `{resource_id}`"
            
            return {"isError": False, "content": [{"type": "text", "text": summary}]}
        else:
            return {
                "isError": False,
                "content": [{
                    "type": "text", 
                    "text": "No clinical trials found matching this mutation. Try a different search term or check your spelling."
                }]
            }
    
    except Exception as e:
        # Catch any unexpected errors
        error_trace = traceback.format_exc()
        print(f"Unexpected error in summarize_trials_for_mutation: {e}\n{error_trace}")
        return {
            "isError": True,
            "content": [{
                "type": "text", 
                "text": f"An unexpected error occurred: {str(e)}\n\nPlease try again or contact support."
            }]
        }

# Adding resources for mutation information is handled in the for loop above
# We don't need to implement list_resources explicitly as FastMCP handles that automatically

# Start the server when this script is run directly
if __name__ == "__main__":
    print(f"Starting Clinical Trials MCP server with {len(COMMON_MUTATIONS)} mutation resources...")
    # This will automatically handle all the MCP protocol details
    mcp.run()
