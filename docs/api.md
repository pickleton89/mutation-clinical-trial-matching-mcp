# API Documentation: Mutation Clinical Trial Matching MCP

## Overview

This document details the API interfaces, components, and data structures used in the Mutation Clinical Trial Matching MCP server.

## MCP Server Interface

The MCP server exposes the following tools to Claude Desktop:

### `search_clinical_trials`

Searches for clinical trials related to a specific genetic mutation.

**Parameters:**
- `mutation` (string): The genetic mutation to search for (e.g., "BRAF V600E", "EGFR L858R")

**Returns:**
- A markdown-formatted summary of relevant clinical trials

**Example:**
```json
{
  "mutation": "BRAF V600E"
}
```

### `get_mutation_info`

Retrieves information about a specific genetic mutation.

**Parameters:**
- `mutation` (string): The genetic mutation to get information about

**Returns:**
- A markdown-formatted summary of information about the mutation

**Example:**
```json
{
  "mutation": "KRAS G12C"
}
```

## Internal API

### ClinicalTrials.gov API Interface

The system interacts with the clinicaltrials.gov API through the following function:

#### `query_clinical_trials`

**Location:** `clinicaltrials/query.py`

**Parameters:**
- `mutation` (string): The genetic mutation to search for
- `min_rank` (int, optional): Minimum rank for results (default: 1)
- `max_rank` (int, optional): Maximum rank for results (default: 100)
- `timeout` (int, optional): Request timeout in seconds (default: 30)

**Returns:**
- Dictionary containing the API response with clinical trial data

**Example Response Structure:**
```python
{
  "studies": [
    {
      "protocolSection": {
        "identificationModule": {
          "nctId": "NCT12345678",
          "officialTitle": "Study Title"
        },
        "statusModule": {
          "overallStatus": "Recruiting",
          "startDateStruct": {
            "date": "January 1, 2023"
          }
        },
        "descriptionModule": {
          "briefSummary": "Study description..."
        },
        "conditionsModule": {
          "conditions": ["Condition 1", "Condition 2"]
        },
        "designModule": {
          "phases": ["Phase 1", "Phase 2"]
        },
        "contactsLocationsModule": {
          "locations": [
            {
              "facility": {
                "name": "Facility Name",
                "city": "City",
                "state": "State",
                "country": "Country"
              }
            }
          ]
        }
      }
    }
  ]
}
```

## Data Structures

### Shared Context

The shared context is a dictionary passed between nodes in the flow:

```python
shared = {
    "mutation": "BRAF V600E",              # Input mutation string
    "trials_data": {...},                  # Raw API response from clinicaltrials.gov
    "studies": [{...}, {...}, ...],        # List of study dictionaries extracted from trials_data
    "summary": "# Clinical Trials..."      # Final formatted summary in markdown
}
```

### Trial Summary Format

The final summary returned to Claude Desktop follows this markdown structure:

```markdown
# Clinical Trials for [MUTATION]

## Phase 3 Trials

### [NCT ID]: [TITLE]
- **Status**: [STATUS]
- **Conditions**: [CONDITIONS]
- **Summary**: [BRIEF SUMMARY]
- **Locations**: [LOCATIONS]

## Phase 2 Trials
...

## Phase 1 Trials
...

## Other Trials
...
```

## Error Handling

The API implements the following error responses:

| Error Code | Description | Cause |
|------------|-------------|-------|
| 400 | Bad Request | Invalid mutation format |
| 404 | Not Found | No trials found for the mutation |
| 408 | Request Timeout | ClinicalTrials.gov API timeout |
| 500 | Internal Server Error | Unexpected server error |

Each error response includes a descriptive message and suggestions for resolution.
