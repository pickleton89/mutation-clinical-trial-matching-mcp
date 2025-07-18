"""
Tests for response validation system.
"""

import os
import sys
import unittest
from unittest.mock import patch

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.response_validation import (
    ArrayValidator,
    RangeValidator,
    RegexValidator,
    ResponseSchema,
    SchemaRegistry,
    TypeValidator,
    ValidationError,
    ValidationResult,
    get_schema_registry,
    register_schema,
    response_validator,
    validate_response,
)


class TestValidationError(unittest.TestCase):
    """Test ValidationError class."""

    def test_validation_error_creation(self):
        """Test ValidationError creation."""
        error = ValidationError(
            field_path="user.name",
            expected_type="string",
            actual_value=123,
            error_message="Expected string, got integer",
        )

        self.assertEqual(error.field_path, "user.name")
        self.assertEqual(error.expected_type, "string")
        self.assertEqual(error.actual_value, 123)
        self.assertEqual(error.error_message, "Expected string, got integer")
        self.assertEqual(error.severity, "error")  # Default severity

    def test_validation_error_with_severity(self):
        """Test ValidationError with custom severity."""
        error = ValidationError(
            field_path="optional_field",
            expected_type="string",
            actual_value=None,
            error_message="Optional field missing",
            severity="warning",
        )

        self.assertEqual(error.severity, "warning")


class TestValidationResult(unittest.TestCase):
    """Test ValidationResult class."""

    def test_validation_result_valid(self):
        """Test ValidationResult for valid response."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[], schema_version="1.0")

        self.assertTrue(result.is_valid)
        self.assertFalse(result.has_errors)
        self.assertFalse(result.has_warnings)
        self.assertEqual(result.schema_version, "1.0")

    def test_validation_result_with_errors(self):
        """Test ValidationResult with errors."""
        error = ValidationError("field", "string", 123, "Type error")
        result = ValidationResult(is_valid=False, errors=[error], warnings=[])

        self.assertFalse(result.is_valid)
        self.assertTrue(result.has_errors)
        self.assertFalse(result.has_warnings)
        self.assertEqual(len(result.errors), 1)

    def test_validation_result_with_warnings(self):
        """Test ValidationResult with warnings."""
        warning = ValidationError("field", "string", None, "Optional field missing", "warning")
        result = ValidationResult(is_valid=True, errors=[], warnings=[warning])

        self.assertTrue(result.is_valid)
        self.assertFalse(result.has_errors)
        self.assertTrue(result.has_warnings)
        self.assertEqual(len(result.warnings), 1)


class TestTypeValidator(unittest.TestCase):
    """Test TypeValidator class."""

    def test_type_validator_valid(self):
        """Test TypeValidator with valid input."""
        validator = TypeValidator(str)
        errors = validator.validate("test string", "field")

        self.assertEqual(len(errors), 0)

    def test_type_validator_invalid_type(self):
        """Test TypeValidator with invalid type."""
        validator = TypeValidator(str)
        errors = validator.validate(123, "field")

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field_path, "field")
        self.assertEqual(errors[0].expected_type, "str")
        self.assertEqual(errors[0].actual_value, 123)

    def test_type_validator_multiple_types(self):
        """Test TypeValidator with multiple allowed types."""
        validator = TypeValidator([str, int])

        # Valid string
        errors = validator.validate("test", "field")
        self.assertEqual(len(errors), 0)

        # Valid integer
        errors = validator.validate(123, "field")
        self.assertEqual(len(errors), 0)

        # Invalid type
        errors = validator.validate([], "field")
        self.assertEqual(len(errors), 1)
        self.assertIn("str or int", errors[0].expected_type)

    def test_type_validator_required_field(self):
        """Test TypeValidator with required field."""
        validator = TypeValidator(str, required=True)
        errors = validator.validate(None, "field")

        self.assertEqual(len(errors), 1)
        self.assertIn("Required field", errors[0].error_message)

    def test_type_validator_optional_field(self):
        """Test TypeValidator with optional field."""
        validator = TypeValidator(str, required=False)
        errors = validator.validate(None, "field")

        self.assertEqual(len(errors), 0)


class TestRegexValidator(unittest.TestCase):
    """Test RegexValidator class."""

    def test_regex_validator_valid(self):
        """Test RegexValidator with valid input."""
        validator = RegexValidator(r"^\d{3}-\d{3}-\d{4}$")  # Phone number pattern
        errors = validator.validate("123-456-7890", "phone")

        self.assertEqual(len(errors), 0)

    def test_regex_validator_invalid_pattern(self):
        """Test RegexValidator with invalid pattern."""
        validator = RegexValidator(r"^\d{3}-\d{3}-\d{4}$")
        errors = validator.validate("invalid-phone", "phone")

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field_path, "phone")
        self.assertIn("does not match required pattern", errors[0].error_message)

    def test_regex_validator_non_string(self):
        """Test RegexValidator with non-string input."""
        validator = RegexValidator(r"^\d+$")
        errors = validator.validate(123, "field")

        self.assertEqual(len(errors), 1)
        self.assertIn("must be a string", errors[0].error_message)

    def test_regex_validator_none_required(self):
        """Test RegexValidator with None value when required."""
        validator = RegexValidator(r"^\d+$", required=True)
        errors = validator.validate(None, "field")

        self.assertEqual(len(errors), 1)
        self.assertIn("Required field", errors[0].error_message)


class TestRangeValidator(unittest.TestCase):
    """Test RangeValidator class."""

    def test_range_validator_valid(self):
        """Test RangeValidator with valid input."""
        validator = RangeValidator(min_value=0, max_value=100)
        errors = validator.validate(50, "score")

        self.assertEqual(len(errors), 0)

    def test_range_validator_below_minimum(self):
        """Test RangeValidator with value below minimum."""
        validator = RangeValidator(min_value=10, max_value=100)
        errors = validator.validate(5, "score")

        self.assertEqual(len(errors), 1)
        self.assertIn("below minimum", errors[0].error_message)

    def test_range_validator_above_maximum(self):
        """Test RangeValidator with value above maximum."""
        validator = RangeValidator(min_value=0, max_value=100)
        errors = validator.validate(150, "score")

        self.assertEqual(len(errors), 1)
        self.assertIn("above maximum", errors[0].error_message)

    def test_range_validator_min_only(self):
        """Test RangeValidator with minimum only."""
        validator = RangeValidator(min_value=0)

        # Valid
        errors = validator.validate(100, "field")
        self.assertEqual(len(errors), 0)

        # Invalid
        errors = validator.validate(-10, "field")
        self.assertEqual(len(errors), 1)

    def test_range_validator_max_only(self):
        """Test RangeValidator with maximum only."""
        validator = RangeValidator(max_value=100)

        # Valid
        errors = validator.validate(50, "field")
        self.assertEqual(len(errors), 0)

        # Invalid
        errors = validator.validate(150, "field")
        self.assertEqual(len(errors), 1)

    def test_range_validator_non_numeric(self):
        """Test RangeValidator with non-numeric input."""
        validator = RangeValidator(min_value=0, max_value=100)
        errors = validator.validate("not a number", "field")

        self.assertEqual(len(errors), 1)
        self.assertIn("must be a number", errors[0].error_message)


class TestArrayValidator(unittest.TestCase):
    """Test ArrayValidator class."""

    def test_array_validator_valid(self):
        """Test ArrayValidator with valid input."""
        validator = ArrayValidator()
        errors = validator.validate([1, 2, 3], "items")

        self.assertEqual(len(errors), 0)

    def test_array_validator_non_array(self):
        """Test ArrayValidator with non-array input."""
        validator = ArrayValidator()
        errors = validator.validate("not an array", "items")

        self.assertEqual(len(errors), 1)
        self.assertIn("must be an array", errors[0].error_message)

    def test_array_validator_length_constraints(self):
        """Test ArrayValidator with length constraints."""
        validator = ArrayValidator(min_length=2, max_length=5)

        # Valid length
        errors = validator.validate([1, 2, 3], "items")
        self.assertEqual(len(errors), 0)

        # Too short
        errors = validator.validate([1], "items")
        self.assertEqual(len(errors), 1)
        self.assertIn("minimum required is 2", errors[0].error_message)

        # Too long
        errors = validator.validate([1, 2, 3, 4, 5, 6], "items")
        self.assertEqual(len(errors), 1)
        self.assertIn("maximum allowed is 5", errors[0].error_message)

    def test_array_validator_with_item_validator(self):
        """Test ArrayValidator with item validator."""
        item_validator = TypeValidator(int)
        validator = ArrayValidator(item_validator=item_validator)

        # Valid items
        errors = validator.validate([1, 2, 3], "numbers")
        self.assertEqual(len(errors), 0)

        # Invalid items
        errors = validator.validate([1, "two", 3], "numbers")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field_path, "numbers[1]")
        self.assertIn("expected int", errors[0].error_message)


class TestResponseSchema(unittest.TestCase):
    """Test ResponseSchema class."""

    def test_response_schema_creation(self):
        """Test ResponseSchema creation."""
        schema = ResponseSchema("test_schema", "2.0")

        self.assertEqual(schema.name, "test_schema")
        self.assertEqual(schema.version, "2.0")
        self.assertEqual(len(schema.fields), 0)

    def test_response_schema_add_field(self):
        """Test adding fields to schema."""
        schema = ResponseSchema("test_schema")
        validator = TypeValidator(str)

        schema.add_field("user.name", validator)

        self.assertIn("user.name", schema.fields)
        self.assertEqual(schema.fields["user.name"], validator)

    def test_response_schema_validate_success(self):
        """Test successful schema validation."""
        schema = ResponseSchema("test_schema")
        schema.add_field("name", TypeValidator(str))
        schema.add_field("age", TypeValidator(int))

        response = {"name": "John", "age": 30}
        result = schema.validate(response)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.schema_version, "1.0")

    def test_response_schema_validate_errors(self):
        """Test schema validation with errors."""
        schema = ResponseSchema("test_schema")
        schema.add_field("name", TypeValidator(str))
        schema.add_field("age", TypeValidator(int))

        response = {"name": 123, "age": "not a number"}
        result = schema.validate(response)

        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 2)

        # Check error details
        field_paths = [error.field_path for error in result.errors]
        self.assertIn("name", field_paths)
        self.assertIn("age", field_paths)

    def test_response_schema_nested_fields(self):
        """Test schema validation with nested fields."""
        schema = ResponseSchema("test_schema")
        schema.add_field("user.profile.name", TypeValidator(str))
        schema.add_field("user.profile.age", TypeValidator(int))

        response = {"user": {"profile": {"name": "John", "age": 30}}}
        result = schema.validate(response)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_response_schema_missing_nested_field(self):
        """Test schema validation with missing nested field."""
        schema = ResponseSchema("test_schema")
        schema.add_field("user.profile.name", TypeValidator(str))

        response = {"user": {"other": "data"}}
        result = schema.validate(response)

        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)


class TestSchemaRegistry(unittest.TestCase):
    """Test SchemaRegistry class."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = SchemaRegistry()

    def test_register_schema(self):
        """Test registering a schema."""
        schema = ResponseSchema("test_schema")
        self.registry.register_schema(schema)

        retrieved = self.registry.get_schema("test_schema")
        self.assertEqual(retrieved, schema)

    def test_get_nonexistent_schema(self):
        """Test getting non-existent schema."""
        result = self.registry.get_schema("nonexistent")
        self.assertIsNone(result)

    def test_validate_response_success(self):
        """Test successful response validation."""
        schema = ResponseSchema("test_schema")
        schema.add_field("name", TypeValidator(str))
        self.registry.register_schema(schema)

        response = {"name": "John"}
        result = self.registry.validate_response(response, "test_schema")

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_response_schema_not_found(self):
        """Test response validation with non-existent schema."""
        response = {"name": "John"}
        result = self.registry.validate_response(response, "nonexistent")

        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Schema 'nonexistent' not found", result.errors[0].error_message)


class TestResponseValidatorDecorator(unittest.TestCase):
    """Test response_validator decorator."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a test schema
        schema = ResponseSchema("test_api")
        schema.add_field("status", TypeValidator(str))
        schema.add_field("data", TypeValidator(dict))
        register_schema(schema)

    @patch("utils.response_validation.logger")
    def test_response_validator_success(self, mock_logger):
        """Test response validator with valid response."""

        @response_validator("test_api")
        def api_function():
            return {"status": "success", "data": {"key": "value"}}

        result = api_function()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["key"], "value")

        # Should not log any errors
        mock_logger.error.assert_not_called()

    @patch("utils.response_validation.logger")
    def test_response_validator_with_errors(self, mock_logger):
        """Test response validator with validation errors."""

        @response_validator("test_api")
        def api_function():
            return {"status": 123, "data": "not a dict"}

        result = api_function()

        # Function should still return result
        self.assertEqual(result["status"], 123)

        # Should log validation errors
        mock_logger.error.assert_called()

    @patch("utils.response_validation.logger")
    def test_response_validator_with_warnings(self, mock_logger):
        """Test response validator with warnings."""

        @response_validator("test_api", log_warnings=True)
        def api_function():
            return {"status": "success", "data": {"key": "value"}}

        result = api_function()

        # Function should return result normally
        self.assertEqual(result["status"], "success")

    def test_response_validator_non_dict_response(self):
        """Test response validator with non-dict response."""

        @response_validator("test_api")
        def api_function():
            return "not a dict"

        result = api_function()

        # Should return result without validation
        self.assertEqual(result, "not a dict")


class TestGlobalAPI(unittest.TestCase):
    """Test global API functions."""

    def test_validate_response_global(self):
        """Test global validate_response function."""
        # Create and register a schema
        schema = ResponseSchema("global_test")
        schema.add_field("value", TypeValidator(int))
        register_schema(schema)

        # Test validation
        response = {"value": 42}
        result = validate_response(response, "global_test")

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_get_schema_registry_global(self):
        """Test global get_schema_registry function."""
        registry = get_schema_registry()

        self.assertIsInstance(registry, SchemaRegistry)

        # Should return same instance
        registry2 = get_schema_registry()
        self.assertIs(registry, registry2)


class TestPreDefinedSchemas(unittest.TestCase):
    """Test pre-defined schemas."""

    def test_clinical_trials_schema_registered(self):
        """Test that clinical trials schema is registered."""
        registry = get_schema_registry()
        schema = registry.get_schema("clinical_trials_api")

        self.assertIsNotNone(schema)
        assert schema is not None  # Type narrowing
        self.assertEqual(schema.name, "clinical_trials_api")
        self.assertEqual(schema.version, "1.0")

    def test_anthropic_api_schema_registered(self):
        """Test that Anthropic API schema is registered."""
        registry = get_schema_registry()
        schema = registry.get_schema("anthropic_api")

        self.assertIsNotNone(schema)
        assert schema is not None  # Type narrowing
        self.assertEqual(schema.name, "anthropic_api")
        self.assertEqual(schema.version, "1.0")

    def test_clinical_trials_schema_validation(self):
        """Test clinical trials schema validation."""
        valid_response = {
            "totalCount": 100,
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": "NCT12345678",
                            "briefTitle": "Test Trial",
                        },
                        "statusModule": {"overallStatus": "Recruiting"},
                        "designModule": {"phases": ["Phase 1", "Phase 2"]},
                    }
                }
            ],
        }

        result = validate_response(valid_response, "clinical_trials_api")

        # Should not fail validation (warnings are acceptable)
        self.assertTrue(result.is_valid or len(result.errors) == 0)

    def test_anthropic_api_schema_validation(self):
        """Test Anthropic API schema validation."""
        valid_response = {
            "content": [{"type": "text", "text": "This is a response"}],
            "model": "claude-3-opus-20240229",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        result = validate_response(valid_response, "anthropic_api")

        # Should pass validation
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)


if __name__ == "__main__":
    unittest.main()
