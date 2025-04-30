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
        if not isinstance(study, dict):
            print(f"Skipping non-dict study entry (type={type(study)}): {study}")
            continue
        try:
            section = study.get('protocolSection', {})
            if not isinstance(section, dict):
                print(f"Skipping study with non-dict protocolSection: {section}")
                continue
            id_info = section.get('identificationModule', {})
            description = section.get('descriptionModule', {})
            conditions_mod = section.get('conditionsModule', {})
            intervention_mod = section.get('interventionBrowseModule', {})
            nct_id = id_info.get('nctId', '')
            title = id_info.get('briefTitle', '')
            brief_summary = description.get('briefSummary', '')
            condition_list = conditions_mod.get('conditions', [])
            intervention_meshes = intervention_mod.get('meshes', [])
            intervention_names = [i.get('term', '') for i in intervention_meshes if isinstance(i, dict)]
            # Extract locations if present
            locations_mod = section.get('contactsLocationsModule', {})
            location_list = []
            if isinstance(locations_mod, dict):
                for loc in locations_mod.get('locations', []):
                    if not isinstance(loc, dict):
                        print(f"Skipping non-dict location: {loc}")
                        continue
                    facility = loc.get('facility', {})
                    # Accept both dict and string facility types
                    if isinstance(facility, dict):
                        name = facility.get('name', '')
                        if name:
                            location_list.append(name)
                    elif isinstance(facility, str):
                        location_list.append(facility)
            url = f"https://clinicaltrials.gov/ct2/show/{nct_id}" if nct_id else ''
            trials.append({
                'nct_id': nct_id,
                'title': title,
                'brief_summary': brief_summary,
                'conditions': condition_list,
                'interventions': intervention_names,
                'locations': location_list,
                'url': url
            })
        except Exception as e:
            print(f"Error parsing study: {e}")
            continue
    return trials
