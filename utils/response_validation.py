"""
Response Validation System for API Schema Management.

This module provides comprehensive response validation capabilities:
- Schema definition and validation for API responses
- Graceful handling of schema evolution
- Validation middleware for automatic response checking
- Detailed logging of validation warnings and errors
"""

import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Individual validation error details."""

    field_path: str
    expected_type: str
    actual_value: Any
    error_message: str
    severity: str = "error"  # "error", "warning", "info"


@dataclass
class ValidationResult:
    """Result of response validation."""

    is_valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]
    schema_version: str | None = None

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


class FieldValidator(ABC):
    """Abstract base class for field validators."""

    @abstractmethod
    def validate(self, value: Any, field_path: str) -> list[ValidationError]:
        """
        Validate a field value.

        Args:
            value: The value to validate
            field_path: The path to the field in the response

        Returns:
            List of validation errors
        """


class TypeValidator(FieldValidator):
    """Validates that a field matches expected type(s)."""

    def __init__(self, expected_types: type | list[type], required: bool = True):
        self.expected_types = (
            expected_types if isinstance(expected_types, list) else [expected_types]
        )
        self.required = required

    def validate(self, value: Any, field_path: str) -> list[ValidationError]:
        errors = []

        if value is None:
            if self.required:
                errors.append(
                    ValidationError(
                        field_path=field_path,
                        expected_type=f"Required field of type {self.expected_types}",
                        actual_value=value,
                        error_message=f"Required field '{field_path}' is missing or null",
                    )
                )
            return errors

        if not any(isinstance(value, t) for t in self.expected_types):
            type_names = [t.__name__ for t in self.expected_types]
            errors.append(
                ValidationError(
                    field_path=field_path,
                    expected_type=" or ".join(type_names),
                    actual_value=value,
                    error_message=f"Field '{field_path}' expected {' or '.join(type_names)}, got {type(value).__name__}",
                )
            )

        return errors


class RegexValidator(FieldValidator):
    """Validates that a string field matches a regex pattern."""

    def __init__(self, pattern: str, required: bool = True):
        self.pattern = re.compile(pattern)
        self.pattern_str = pattern
        self.required = required

    def validate(self, value: Any, field_path: str) -> list[ValidationError]:
        errors = []

        if value is None:
            if self.required:
                errors.append(
                    ValidationError(
                        field_path=field_path,
                        expected_type=f"String matching pattern {self.pattern_str}",
                        actual_value=value,
                        error_message=f"Required field '{field_path}' is missing or null",
                    )
                )
            return errors

        if not isinstance(value, str):
            errors.append(
                ValidationError(
                    field_path=field_path,
                    expected_type="string",
                    actual_value=value,
                    error_message=f"Field '{field_path}' must be a string for regex validation",
                )
            )
            return errors

        if not self.pattern.match(value):
            errors.append(
                ValidationError(
                    field_path=field_path,
                    expected_type=f"String matching pattern {self.pattern_str}",
                    actual_value=value,
                    error_message=f"Field '{field_path}' does not match required pattern {self.pattern_str}",
                )
            )

        return errors


class RangeValidator(FieldValidator):
    """Validates that a numeric field is within a specified range."""

    def __init__(
        self, min_value: float | None = None, max_value: float | None = None, required: bool = True
    ):
        self.min_value = min_value
        self.max_value = max_value
        self.required = required

    def validate(self, value: Any, field_path: str) -> list[ValidationError]:
        errors = []

        if value is None:
            if self.required:
                errors.append(
                    ValidationError(
                        field_path=field_path,
                        expected_type="number",
                        actual_value=value,
                        error_message=f"Required field '{field_path}' is missing or null",
                    )
                )
            return errors

        if not isinstance(value, int | float):
            errors.append(
                ValidationError(
                    field_path=field_path,
                    expected_type="number",
                    actual_value=value,
                    error_message=f"Field '{field_path}' must be a number for range validation",
                )
            )
            return errors

        if self.min_value is not None and value < self.min_value:
            errors.append(
                ValidationError(
                    field_path=field_path,
                    expected_type=f"number >= {self.min_value}",
                    actual_value=value,
                    error_message=f"Field '{field_path}' value {value} is below minimum {self.min_value}",
                )
            )

        if self.max_value is not None and value > self.max_value:
            errors.append(
                ValidationError(
                    field_path=field_path,
                    expected_type=f"number <= {self.max_value}",
                    actual_value=value,
                    error_message=f"Field '{field_path}' value {value} is above maximum {self.max_value}",
                )
            )

        return errors


class ArrayValidator(FieldValidator):
    """Validates array fields with optional item validation."""

    def __init__(
        self,
        item_validator: FieldValidator | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        required: bool = True,
    ):
        self.item_validator = item_validator
        self.min_length = min_length
        self.max_length = max_length
        self.required = required

    def validate(self, value: Any, field_path: str) -> list[ValidationError]:
        errors = []

        if value is None:
            if self.required:
                errors.append(
                    ValidationError(
                        field_path=field_path,
                        expected_type="array",
                        actual_value=value,
                        error_message=f"Required field '{field_path}' is missing or null",
                    )
                )
            return errors

        if not isinstance(value, list):
            errors.append(
                ValidationError(
                    field_path=field_path,
                    expected_type="array",
                    actual_value=value,
                    error_message=f"Field '{field_path}' must be an array",
                )
            )
            return errors

        # Validate length constraints
        if self.min_length is not None and len(value) < self.min_length:
            errors.append(
                ValidationError(
                    field_path=field_path,
                    expected_type=f"array with at least {self.min_length} items",
                    actual_value=value,
                    error_message=f"Field '{field_path}' has {len(value)} items, minimum required is {self.min_length}",
                )
            )

        if self.max_length is not None and len(value) > self.max_length:
            errors.append(
                ValidationError(
                    field_path=field_path,
                    expected_type=f"array with at most {self.max_length} items",
                    actual_value=value,
                    error_message=f"Field '{field_path}' has {len(value)} items, maximum allowed is {self.max_length}",
                )
            )

        # Validate individual items
        if self.item_validator:
            for i, item in enumerate(value):
                item_path = f"{field_path}[{i}]"
                item_errors = self.item_validator.validate(item, item_path)
                errors.extend(item_errors)

        return errors


class ResponseSchema:
    """Defines the expected schema for API responses."""

    def __init__(self, name: str, version: str = "1.0"):
        self.name = name
        self.version = version
        self.fields: dict[str, FieldValidator] = {}

    def add_field(self, field_path: str, validator: FieldValidator):
        """Add a field validator to the schema."""
        self.fields[field_path] = validator

    def validate(self, response: dict[str, Any]) -> ValidationResult:
        """
        Validate a response against this schema.

        Args:
            response: The response data to validate

        Returns:
            ValidationResult with detailed validation information
        """
        all_errors = []
        all_warnings = []

        for field_path, validator in self.fields.items():
            try:
                value = self._get_nested_value(response, field_path)
                errors = validator.validate(value, field_path)

                # Separate errors and warnings
                for error in errors:
                    if error.severity == "warning":
                        all_warnings.append(error)
                    else:
                        all_errors.append(error)

            except Exception as e:
                all_errors.append(
                    ValidationError(
                        field_path=field_path,
                        expected_type="unknown",
                        actual_value="validation_error",
                        error_message=f"Validation error for field '{field_path}': {str(e)}",
                    )
                )

        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            schema_version=self.version,
        )

    def _get_nested_value(self, data: dict[str, Any], field_path: str) -> Any:
        """Get a nested value from data using dot notation."""
        keys = field_path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current


class SchemaRegistry:
    """Registry for managing multiple API response schemas."""

    def __init__(self):
        self.schemas: dict[str, ResponseSchema] = {}

    def register_schema(self, schema: ResponseSchema):
        """Register a new response schema."""
        self.schemas[schema.name] = schema
        logger.info(f"Registered response schema: {schema.name} v{schema.version}")

    def get_schema(self, name: str) -> ResponseSchema | None:
        """Get a schema by name."""
        return self.schemas.get(name)

    def validate_response(self, response: dict[str, Any], schema_name: str) -> ValidationResult:
        """
        Validate a response against a registered schema.

        Args:
            response: The response data to validate
            schema_name: Name of the schema to validate against

        Returns:
            ValidationResult with detailed validation information
        """
        schema = self.get_schema(schema_name)
        if not schema:
            return ValidationResult(
                is_valid=False,
                errors=[
                    ValidationError(
                        field_path="schema",
                        expected_type="registered_schema",
                        actual_value=schema_name,
                        error_message=f"Schema '{schema_name}' not found in registry",
                    )
                ],
                warnings=[],
            )

        return schema.validate(response)


# Global schema registry
_schema_registry = SchemaRegistry()


def get_schema_registry() -> SchemaRegistry:
    """Get the global schema registry."""
    return _schema_registry


def register_schema(schema: ResponseSchema):
    """Register a schema with the global registry."""
    _schema_registry.register_schema(schema)


def validate_response(response: dict[str, Any], schema_name: str) -> ValidationResult:
    """Validate a response using the global registry."""
    return _schema_registry.validate_response(response, schema_name)


def response_validator(schema_name: str, log_warnings: bool = True, log_errors: bool = True):
    """
    Decorator to automatically validate function responses.

    Args:
        schema_name: Name of the schema to validate against
        log_warnings: Whether to log validation warnings
        log_errors: Whether to log validation errors

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Only validate if result is a dictionary (JSON response)
            if isinstance(result, dict):
                validation_result = validate_response(result, schema_name)

                if log_errors and validation_result.has_errors:
                    for error in validation_result.errors:
                        logger.error(
                            f"Response validation error in {getattr(func, '__name__', 'unknown')}: {error.error_message}",
                            extra={
                                "function": getattr(func, "__name__", "unknown"),
                                "field_path": error.field_path,
                                "expected_type": error.expected_type,
                                "actual_value": str(error.actual_value),
                                "schema_name": schema_name,
                                "action": "response_validation_error",
                            },
                        )

                if log_warnings and validation_result.has_warnings:
                    for warning in validation_result.warnings:
                        logger.warning(
                            f"Response validation warning in {getattr(func, '__name__', 'unknown')}: {warning.error_message}",
                            extra={
                                "function": getattr(func, "__name__", "unknown"),
                                "field_path": warning.field_path,
                                "expected_type": warning.expected_type,
                                "actual_value": str(warning.actual_value),
                                "schema_name": schema_name,
                                "action": "response_validation_warning",
                            },
                        )

            return result

        return wrapper

    return decorator


# Pre-defined schemas for common APIs
def register_clinical_trials_schema():
    """Register schema for ClinicalTrials.gov API responses."""
    schema = ResponseSchema("clinical_trials_api", "1.0")

    # Top-level fields
    schema.add_field("totalCount", TypeValidator(int, required=False))
    schema.add_field("studies", ArrayValidator(required=True))

    # Study fields (validate first study if present)
    schema.add_field("studies.0.protocolSection", TypeValidator(dict, required=False))
    schema.add_field(
        "studies.0.protocolSection.identificationModule", TypeValidator(dict, required=False)
    )
    schema.add_field(
        "studies.0.protocolSection.identificationModule.nctId", TypeValidator(str, required=False)
    )
    schema.add_field(
        "studies.0.protocolSection.identificationModule.briefTitle",
        TypeValidator(str, required=False),
    )
    schema.add_field("studies.0.protocolSection.statusModule", TypeValidator(dict, required=False))
    schema.add_field(
        "studies.0.protocolSection.statusModule.overallStatus", TypeValidator(str, required=False)
    )
    schema.add_field("studies.0.protocolSection.designModule", TypeValidator(dict, required=False))
    schema.add_field(
        "studies.0.protocolSection.designModule.phases", ArrayValidator(required=False)
    )

    register_schema(schema)


def register_anthropic_api_schema():
    """Register schema for Anthropic API responses."""
    schema = ResponseSchema("anthropic_api", "1.0")

    # Top-level fields
    schema.add_field("content", ArrayValidator(required=True))
    schema.add_field("model", TypeValidator(str, required=True))
    schema.add_field("usage", TypeValidator(dict, required=False))

    # Content fields
    schema.add_field("content.0.text", TypeValidator(str, required=False))
    schema.add_field("content.0.type", TypeValidator(str, required=False))

    # Usage fields
    schema.add_field("usage.input_tokens", TypeValidator(int, required=False))
    schema.add_field("usage.output_tokens", TypeValidator(int, required=False))

    register_schema(schema)


# Initialize default schemas
register_clinical_trials_schema()
register_anthropic_api_schema()
