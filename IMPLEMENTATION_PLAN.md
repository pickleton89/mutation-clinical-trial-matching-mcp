# Implementation Plan: Code Quality Improvements

This document provides a comprehensive step-by-step plan to address the code review feedback and improve the overall quality of the mutation clinical trial matching MCP project.

## Overview

Based on the code review feedback, we have identified 7 key areas for improvement, organized by priority:

- **High Priority**: Critical issues that could cause runtime problems
- **Medium Priority**: Code quality and maintainability improvements
- **Low Priority**: Packaging and project structure enhancements

## High Priority Items

### 1. Clean up main.py - Remove Truncated Shell Prompt and Fix Syntax Errors

**Issue**: `main.py` contains truncated shell prompt causing syntax errors
**Impact**: Prevents the file from being imported or executed
**Effort**: 15 minutes

**Steps**:
1. Open `main.py` and identify the truncated shell prompt
2. Remove any extraneous text that doesn't belong in the Python code
3. Ensure proper Python syntax throughout the file
4. Test by running: `uv run python main.py`
5. Verify no syntax errors remain

**Validation**:
- File can be imported without errors
- No syntax errors when running the file
- Code follows Python conventions

### 2. Replace Print Statements with Proper Logging Module

**Issue**: `clinicaltrials/query.py` uses print statements instead of logging
**Impact**: Makes debugging difficult and clutters output
**Effort**: 30 minutes

**Steps**:
1. Add logging import to `clinicaltrials/query.py`
2. Create a logger instance: `logger = logging.getLogger(__name__)`
3. Replace all `print()` statements with appropriate logging levels:
   - Error messages → `logger.error()`
   - Warning messages → `logger.warning()`
   - Info messages → `logger.info()`
   - Debug messages → `logger.debug()`
4. Configure logging in `clinicaltrials_mcp_server.py` to set appropriate log levels
5. Test logging output with different log levels

**Code Changes**:
```python
# At top of clinicaltrials/query.py
import logging

logger = logging.getLogger(__name__)

# Replace print statements like:
# print(f"Error: {error}")
# With:
logger.error(f"Error: {error}")
```

**Validation**:
- No print statements remain in query.py
- Logging works at different levels (DEBUG, INFO, WARNING, ERROR)
- Log messages are properly formatted

### 3. Implement Actual Test Assertions in Stubbed Test Files

**Issue**: Test files contain empty functions without assertions
**Impact**: No actual testing occurs, reducing code reliability
**Effort**: 2-3 hours

**Steps**:

#### 3.1 Implement `tests/test_query.py`
1. Create test cases for `query_clinical_trials()` function
2. Mock HTTP requests using `unittest.mock.patch`
3. Test successful API responses
4. Test error handling scenarios
5. Test input validation

```python
import unittest
from unittest.mock import patch, Mock
from clinicaltrials.query import query_clinical_trials

class TestQueryClinicalTrials(unittest.TestCase):
    @patch('clinicaltrials.query.requests.get')
    def test_successful_query(self, mock_get):
        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = {"studies": []}
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = query_clinical_trials("BRAF V600E")
        self.assertIsInstance(result, dict)
        self.assertIn("studies", result)
```

#### 3.2 Implement `tests/test_parse.py`
1. If `parse.py` is kept, create tests for parsing functions
2. Test various input formats
3. Test edge cases and error conditions
4. If `parse.py` is removed, delete this test file

#### 3.3 Implement `tests/test_summarize.py`
1. Create test cases for summarization functions
2. Test markdown formatting
3. Test trial categorization by phase
4. Test edge cases with empty or malformed data

**Validation**:
- All tests pass when run with `uv run python -m unittest discover tests/`
- Test coverage includes happy path and error scenarios
- Tests are maintainable and well-documented

## Medium Priority Items

### 4. Fix Type Annotations Inconsistencies

**Issue**: `query_clinical_trials()` declares `Optional[Dict[str, Any]]` but never returns `None`
**Impact**: Type checking tools may give false positives/negatives
**Effort**: 15 minutes

**Steps**:
1. Review `query_clinical_trials()` function return behavior
2. Determine if function should return `None` or always return `Dict`
3. Update type annotation to match actual behavior
4. Update docstring to reflect return type
5. Run type checking: `uv run mypy clinicaltrials/query.py`

**Options**:
- Option A: Change return type to `Dict[str, Any]` (if never returns None)
- Option B: Modify function to return `None` in error cases

**Validation**:
- Type annotations match actual function behavior
- mypy reports no type errors
- Function behavior is consistent with documentation

### 5. Remove Unused clinicaltrials/parse.py or Integrate It Properly

**Issue**: `parse.py` contains unused functions
**Impact**: Dead code increases maintenance burden
**Effort**: 30 minutes

**Steps**:
1. Search codebase for any references to `parse.py` functions
2. Review CHANGELOG to understand why parsing was removed
3. Choose one of two options:

**Option A: Remove parse.py**
1. Delete `clinicaltrials/parse.py`
2. Delete `tests/test_parse.py`
3. Update any imports that reference parse functions

**Option B: Integrate parse.py**
1. Identify where parsing functionality should be used
2. Integrate parsing into the node flow
3. Update tests to cover parsing functionality
4. Update documentation

**Validation**:
- No unused code remains in the codebase
- All imports are valid
- Tests pass after changes

### 6. Improve Error Handling in MCP Server

**Issue**: MCP server prints errors but doesn't provide structured error responses
**Impact**: Difficult to debug and poor user experience
**Effort**: 45 minutes

**Steps**:
1. Review current error handling in `clinicaltrials_mcp_server.py`
2. Implement structured error responses using MCP error formats
3. Add proper logging for server errors
4. Create error response schemas
5. Test error scenarios

**Code Changes**:
```python
import logging
from mcp.server.models import ErrorData

logger = logging.getLogger(__name__)

# Instead of just printing errors:
try:
    # ... operation
except Exception as e:
    logger.error(f"Operation failed: {e}")
    raise McpError(
        error=ErrorData(
            code="OPERATION_FAILED",
            message=str(e)
        )
    )
```

**Validation**:
- Errors are properly logged and returned to client
- Error responses follow MCP protocol standards
- Error messages are helpful for debugging

## Low Priority Items

### 7. Verify pyproject.toml Configuration is Complete

**Issue**: Ensure proper packaging configuration
**Impact**: Affects project installation and dependency management
**Effort**: 20 minutes

**Steps**:
1. Review current `pyproject.toml` configuration
2. Ensure all required fields are present:
   - Project metadata (name, version, description)
   - Dependencies and optional dependencies
   - Build system configuration
   - Development dependencies
3. Verify uv.lock is in sync: `uv lock --check`
4. Test installation: `uv install -e .`

**Required Fields**:
```toml
[project]
name = "mutation-clinical-trial-matching-mcp"
version = "0.1.0"
description = "MCP server for clinical trial matching"
authors = [...]
dependencies = [...]

[project.optional-dependencies]
dev = [...]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Validation**:
- Project can be installed with `uv install -e .`
- Dependencies are properly declared
- Lock file is in sync with pyproject.toml

## Implementation Order

### Phase 1: Critical Fixes (High Priority)
1. Clean up main.py (15 min)
2. Replace print statements with logging (30 min)
3. Implement test assertions (2-3 hours)

**Total Phase 1 Effort**: ~3.5 hours

### Phase 2: Code Quality (Medium Priority)
1. Fix type annotations (15 min)
2. Handle unused parse.py (30 min)
3. Improve MCP server error handling (45 min)

**Total Phase 2 Effort**: ~1.5 hours

### Phase 3: Project Structure (Low Priority)
1. Verify pyproject.toml configuration (20 min)

**Total Phase 3 Effort**: ~20 minutes

## Testing Strategy

After each phase, run the following validation commands:

```bash
# Run all tests
uv run python -m unittest discover tests/

# Type checking
uv run mypy clinicaltrials/ llm/ utils/

# Linting (if configured)
uv run ruff check .

# Start MCP server to test functionality
uv run python clinicaltrials_mcp_server.py
```

## Success Criteria

- [ ] All tests pass with meaningful assertions
- [ ] No print statements in production code
- [ ] Proper logging configuration
- [ ] Type annotations are consistent
- [ ] No unused code remains
- [ ] MCP server provides structured error responses
- [ ] Project can be properly packaged and installed
- [ ] Code follows Python best practices

## Risk Assessment

- **Low Risk**: Logging improvements, type annotation fixes
- **Medium Risk**: Test implementation (may uncover existing bugs)
- **High Risk**: Removing unused code (may break undocumented dependencies)

## Dependencies

- Some items depend on others (e.g., fixing main.py before running tests)
- Test implementation may reveal issues requiring additional fixes
- Error handling improvements may require MCP protocol understanding

## Maintenance Notes

- After implementation, establish pre-commit hooks for code quality
- Consider setting up CI/CD pipeline for automated testing
- Document any architectural decisions made during implementation