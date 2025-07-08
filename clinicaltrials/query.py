"""
Functions to query clinicaltrials.gov for trials matching a mutation.
"""

import logging
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)

def query_clinical_trials(mutation: str, min_rank: int = 1, max_rank: int = 10, timeout: int = 10) -> Dict[str, Any]:
    """
    Query clinicaltrials.gov for clinical trials related to a given mutation.

    Args:
        mutation (str): The mutation or keyword to search for (e.g., 'EGFR L858R').
        min_rank (int): The minimum rank of results to return (default: 1).
        max_rank (int): The maximum rank of results to return (default: 10).
        timeout (int): Timeout for the HTTP request in seconds (default: 10).

    Returns:
        Dict[str, Any]: Parsed JSON response from clinicaltrials.gov, or error dictionary with 'error' and 'studies' keys if an error occurred.
    """
    # Input validation
    if not mutation or not isinstance(mutation, str) or len(mutation.strip()) == 0:
        logger.error("Error: Mutation must be a non-empty string")
        return {"error": "Mutation must be a non-empty string", "studies": []}
    
    if not isinstance(min_rank, int) or min_rank < 1:
        logger.warning(f"Invalid min_rank {min_rank}. Setting to 1.")
        min_rank = 1
    
    if not isinstance(max_rank, int) or max_rank < min_rank:
        logger.warning(f"Invalid max_rank {max_rank}. Setting to {min_rank + 9}.")
        max_rank = min_rank + 9
    
    # Prepare request
    base_url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "format": "json",
        "query.term": mutation,
        "pageSize": max_rank - min_rank + 1
    }
    
    try:
        logger.info(f"Querying clinicaltrials.gov for mutation: {mutation}")
        headers = {"Accept": "application/json"}
        response = requests.get(base_url, params=params, headers=headers, timeout=timeout)
        
        # Check for non-200 status codes
        if response.status_code != 200:
            logger.error(f"API Error (Status {response.status_code}): {response.text}")
            return {"error": f"API Error (Status {response.status_code})", "studies": []}
        
        # Try to parse JSON
        try:
            result = response.json()
            study_count = len(result.get("studies", []))
            logger.info(f"Found {study_count} studies for mutation {mutation}")
            return result
        except ValueError as json_err:
            logger.error(f"JSON parsing error: {json_err}")
            logger.debug("Response content: %s", response.text[:500] + "..." if len(response.text) > 500 else response.text)
            return {"error": f"Failed to parse API response: {json_err}", "studies": []}
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout ({timeout}s) when querying clinicaltrials.gov")
        return {"error": "The request to clinicaltrials.gov timed out", "studies": []}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {e}")
        return {"error": "Failed to connect to clinicaltrials.gov", "studies": []}
    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return {"error": f"Error querying clinicaltrials.gov: {e}", "studies": []}
