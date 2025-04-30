"""
Functions to parse and structure clinicaltrials.gov results.
"""

from typing import List, Dict, Any, Optional

def parse_clinical_trials(raw_results: Optional[dict]) -> List[Dict[str, Any]]:
    """
    Parse and structure raw clinicaltrials.gov v2 API results into a list of trial summaries.

    Args:
        raw_results (dict): Raw JSON results from clinicaltrials.gov API.

    Returns:
        List[Dict[str, Any]]: List of trial summaries with key details.
    """
    if not raw_results:
        return []
    trials = []
    studies = raw_results.get('studies', [])
    for study in studies:
        try:
            section = study.get('protocolSection', {})
            id_info = section.get('identificationModule', {})
            description = section.get('descriptionModule', {})
            conditions_mod = section.get('conditionsModule', {})
            intervention_mod = section.get('interventionBrowseModule', {})
            nct_id = id_info.get('nctId', '')
            title = id_info.get('briefTitle', '')
            brief_summary = description.get('briefSummary', '')
            condition_list = conditions_mod.get('conditions', [])
            intervention_meshes = intervention_mod.get('meshes', [])
            intervention_names = [i.get('term', '') for i in intervention_meshes]
            # Locations are not always present in v2, so we omit for now
            url = f"https://clinicaltrials.gov/ct2/show/{nct_id}" if nct_id else ''
            trials.append({
                'nct_id': nct_id,
                'title': title,
                'brief_summary': brief_summary,
                'conditions': condition_list,
                'interventions': intervention_names,
                'locations': [],
                'url': url
            })
        except Exception as e:
            print(f"Error parsing study: {e}")
            continue
    return trials
