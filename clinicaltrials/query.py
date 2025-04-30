"""
Functions to query clinicaltrials.gov for trials matching a mutation.
"""

import requests
from typing import Optional, Dict, Any

def query_clinical_trials(mutation: str, min_rank: int = 1, max_rank: int = 10, timeout: int = 10) -> Optional[Dict[str, Any]]:
    """
    Query clinicaltrials.gov for clinical trials related to a given mutation.

    Args:
        mutation (str): The mutation or keyword to search for (e.g., 'EGFR L858R').
        min_rank (int): The minimum rank of results to return (default: 1).
        max_rank (int): The maximum rank of results to return (default: 10).
        timeout (int): Timeout for the HTTP request in seconds (default: 10).

    Returns:
        Optional[Dict[str, Any]]: Parsed JSON response from clinicaltrials.gov, or None if an error occurred.
    """
    base_url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query": mutation,
        "pageSize": max_rank - min_rank + 1,
        "format": "json"
    }
    try:
        response = requests.get(base_url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error querying clinicaltrials.gov: {e}")
        return None
