"""
Functions to parse and structure clinicaltrials.gov results.
"""

from typing import List, Dict, Any, Optional

def parse_clinical_trials(raw_results: Optional[dict]) -> List[Dict[str, Any]]:
    """
    Parse and structure raw clinicaltrials.gov results into a list of trial summaries.

    Args:
        raw_results (dict): Raw JSON results from clinicaltrials.gov API.

    Returns:
        List[Dict[str, Any]]: List of trial summaries with key details.
    """
    if not raw_results:
        return []
    trials = []
    studies = raw_results.get('FullStudiesResponse', {}).get('FullStudies', [])
    for study in studies:
        try:
            study_struct = study['Study']['ProtocolSection']
            id_info = study_struct.get('IdentificationModule', {})
            description = study_struct.get('DescriptionModule', {})
            conditions = study_struct.get('ConditionsModule', {})
            arms = study_struct.get('ArmsInterventionsModule', {})
            locations = study_struct.get('ContactsLocationsModule', {})
            nct_id = id_info.get('NCTId', '')
            title = id_info.get('BriefTitle', '')
            brief_summary = description.get('BriefSummary', '')
            condition_list = conditions.get('ConditionList', {}).get('Condition', [])
            intervention_list = arms.get('InterventionList', {}).get('Intervention', [])
            intervention_names = [i.get('InterventionName', '') for i in intervention_list]
            location_list = locations.get('LocationList', {}).get('Location', [])
            location_names = [loc.get('LocationFacility', '') for loc in location_list]
            url = f"https://clinicaltrials.gov/ct2/show/{nct_id}" if nct_id else ''
            trials.append({
                'nct_id': nct_id,
                'title': title,
                'brief_summary': brief_summary,
                'conditions': condition_list,
                'interventions': intervention_names,
                'locations': location_names,
                'url': url
            })
        except Exception as e:
            print(f"Error parsing study: {e}")
            continue
    return trials
