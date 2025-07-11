"""
Unit tests for llm.summarize
"""

import unittest
from unittest.mock import patch

from llm.summarize import call_claude_via_mcp, summarize_trials


class TestSummarizeTrials(unittest.TestCase):
    """Test the summarize_trials function."""

    def test_empty_trials_list(self):
        """Test summarization with empty trials list."""
        result = summarize_trials([])

        self.assertEqual(result, "No clinical trials found for the specified mutation.")

    def test_single_trial_summary(self):
        """Test summarization with a single trial."""
        mock_trial = {
            "protocolSection": {
                "identificationModule": {
                    "briefTitle": "Test Trial for BRAF V600E",
                    "nctId": "NCT12345678",
                },
                "phaseModule": {"phase": "Phase 2"},
                "statusModule": {"overallStatus": "RECRUITING"},
                "conditionsModule": {"conditions": ["Melanoma", "Skin Cancer"]},
                "armsInterventionsModule": {
                    "interventions": [{"name": "Dabrafenib"}, {"name": "Trametinib"}]
                },
                "descriptionModule": {
                    "briefSummary": "This is a test trial for BRAF V600E mutation."
                },
                "contactsLocationsModule": {
                    "locations": [
                        {"facility": "Test Hospital", "city": "Boston", "country": "United States"}
                    ]
                },
            }
        }

        result = summarize_trials([mock_trial])

        # Verify basic structure
        self.assertIn("# Clinical Trials Summary", result)
        self.assertIn("Found 1 clinical trial matching", result)
        self.assertIn("## Phase 2 Trials (1)", result)
        self.assertIn("### Test Trial for BRAF V600E", result)
        self.assertIn("NCT12345678", result)
        self.assertIn("RECRUITING", result)
        self.assertIn("Melanoma, Skin Cancer", result)
        self.assertIn("Dabrafenib, Trametinib", result)
        self.assertIn("Test Hospital (Boston, United States)", result)

    def test_multiple_trials_different_phases(self):
        """Test summarization with multiple trials in different phases."""
        mock_trials = [
            {
                "protocolSection": {
                    "identificationModule": {"briefTitle": "Phase 1 Trial", "nctId": "NCT11111111"},
                    "phaseModule": {"phase": "Phase 1"},
                    "statusModule": {"overallStatus": "RECRUITING"},
                    "conditionsModule": {"conditions": ["Cancer"]},
                    "armsInterventionsModule": {"interventions": [{"name": "Drug A"}]},
                    "descriptionModule": {"briefSummary": "Phase 1 trial summary"},
                    "contactsLocationsModule": {"locations": []},
                }
            },
            {
                "protocolSection": {
                    "identificationModule": {"briefTitle": "Phase 2 Trial", "nctId": "NCT22222222"},
                    "phaseModule": {"phase": "Phase 2"},
                    "statusModule": {"overallStatus": "COMPLETED"},
                    "conditionsModule": {"conditions": ["Melanoma"]},
                    "armsInterventionsModule": {"interventions": [{"name": "Drug B"}]},
                    "descriptionModule": {"briefSummary": "Phase 2 trial summary"},
                    "contactsLocationsModule": {"locations": []},
                }
            },
        ]

        result = summarize_trials(mock_trials)

        # Verify both phases are present
        self.assertIn("Found 2 clinical trials matching", result)
        self.assertIn("## Phase 1 Trials (1)", result)
        self.assertIn("## Phase 2 Trials (1)", result)
        self.assertIn("Phase 1 Trial", result)
        self.assertIn("Phase 2 Trial", result)
        self.assertIn("NCT11111111", result)
        self.assertIn("NCT22222222", result)

    def test_unknown_phase_handling(self):
        """Test handling of trials with missing or unknown phase."""
        mock_trial = {
            "protocolSection": {
                "identificationModule": {
                    "briefTitle": "Unknown Phase Trial",
                    "nctId": "NCT99999999",
                },
                # Missing phaseModule
                "statusModule": {"overallStatus": "RECRUITING"},
                "conditionsModule": {"conditions": ["Test Condition"]},
                "armsInterventionsModule": {"interventions": [{"name": "Test Drug"}]},
                "descriptionModule": {"briefSummary": "Unknown phase trial"},
                "contactsLocationsModule": {"locations": []},
            }
        }

        result = summarize_trials([mock_trial])

        # Verify unknown phase is handled
        self.assertIn("## Unknown Phase Trials (1)", result)
        self.assertIn("Unknown Phase Trial", result)

    def test_missing_fields_handling(self):
        """Test handling of trials with missing optional fields."""
        mock_trial = {
            "protocolSection": {
                "identificationModule": {"briefTitle": "Minimal Trial", "nctId": "NCT00000000"}
                # Missing most optional modules
            }
        }

        result = summarize_trials([mock_trial])

        # Verify basic structure is still present
        self.assertIn("# Clinical Trials Summary", result)
        self.assertIn("Found 1 clinical trial matching", result)
        self.assertIn("Minimal Trial", result)
        self.assertIn("NCT00000000", result)
        self.assertIn("Unknown Phase", result)

    def test_long_summary_truncation(self):
        """Test that long summaries are truncated appropriately."""
        long_summary = "A" * 300  # 300 characters, should be truncated

        mock_trial = {
            "protocolSection": {
                "identificationModule": {
                    "briefTitle": "Long Summary Trial",
                    "nctId": "NCT55555555",
                },
                "phaseModule": {"phase": "Phase 1"},
                "statusModule": {"overallStatus": "RECRUITING"},
                "conditionsModule": {"conditions": ["Cancer"]},
                "armsInterventionsModule": {"interventions": [{"name": "Drug"}]},
                "descriptionModule": {"briefSummary": long_summary},
                "contactsLocationsModule": {"locations": []},
            }
        }

        result = summarize_trials([mock_trial])

        # Verify summary is truncated
        self.assertIn("A" * 197 + "...", result)
        self.assertNotIn("A" * 300, result)

    def test_condition_and_intervention_limits(self):
        """Test that conditions and interventions are limited to 5 items."""
        mock_trial = {
            "protocolSection": {
                "identificationModule": {
                    "briefTitle": "Many Conditions Trial",
                    "nctId": "NCT66666666",
                },
                "phaseModule": {"phase": "Phase 2"},
                "statusModule": {"overallStatus": "RECRUITING"},
                "conditionsModule": {
                    "conditions": [
                        "Condition1",
                        "Condition2",
                        "Condition3",
                        "Condition4",
                        "Condition5",
                        "Condition6",
                        "Condition7",
                    ]
                },
                "armsInterventionsModule": {
                    "interventions": [
                        {"name": "Drug1"},
                        {"name": "Drug2"},
                        {"name": "Drug3"},
                        {"name": "Drug4"},
                        {"name": "Drug5"},
                        {"name": "Drug6"},
                    ]
                },
                "descriptionModule": {"briefSummary": "Test trial"},
                "contactsLocationsModule": {"locations": []},
            }
        }

        result = summarize_trials([mock_trial])

        # Verify only first 5 conditions and interventions are included
        self.assertIn("Condition1", result)
        self.assertIn("Condition5", result)
        self.assertNotIn("Condition6", result)
        self.assertIn("Drug1", result)
        self.assertIn("Drug5", result)
        self.assertNotIn("Drug6", result)

    def test_location_limit(self):
        """Test that locations are limited to 3 items."""
        mock_trial = {
            "protocolSection": {
                "identificationModule": {
                    "briefTitle": "Many Locations Trial",
                    "nctId": "NCT77777777",
                },
                "phaseModule": {"phase": "Phase 3"},
                "statusModule": {"overallStatus": "RECRUITING"},
                "conditionsModule": {"conditions": ["Cancer"]},
                "armsInterventionsModule": {"interventions": [{"name": "Drug"}]},
                "descriptionModule": {"briefSummary": "Test trial"},
                "contactsLocationsModule": {
                    "locations": [
                        {"facility": "Hospital1", "city": "City1", "country": "Country1"},
                        {"facility": "Hospital2", "city": "City2", "country": "Country2"},
                        {"facility": "Hospital3", "city": "City3", "country": "Country3"},
                        {"facility": "Hospital4", "city": "City4", "country": "Country4"},
                    ]
                },
            }
        }

        result = summarize_trials([mock_trial])

        # Verify only first 3 locations are included
        self.assertIn("Hospital1", result)
        self.assertIn("Hospital3", result)
        self.assertNotIn("Hospital4", result)

    def test_malformed_trial_data(self):
        """Test handling of malformed trial data."""
        # Test with completely malformed data
        result = summarize_trials([{}])

        # Should still produce a summary without crashing
        self.assertIn("# Clinical Trials Summary", result)
        self.assertIn("Found 1 clinical trial matching", result)
        self.assertIn("Untitled Trial", result)
        self.assertIn("Unknown", result)


class TestCallClaudeViaMcp(unittest.TestCase):
    """Test the call_claude_via_mcp function."""

    @patch("llm.summarize.call_llm")
    def test_call_claude_via_mcp(self, mock_call_llm):
        """Test that call_claude_via_mcp calls the call_llm function."""
        mock_call_llm.return_value = "Test response"

        result = call_claude_via_mcp("Test prompt")

        self.assertEqual(result, "Test response")
        mock_call_llm.assert_called_once_with("Test prompt")


if __name__ == "__main__":
    unittest.main()
