"""Optional schema validation using datasift-py."""

from __future__ import annotations

import os
from typing import Any

from datasift_diff.schema_loader import load_schema

_VALIDATOR_AVAILABLE: bool | None = None


def _check_datasift() -> bool:
    global _VALIDATOR_AVAILABLE
    if _VALIDATOR_AVAILABLE is None:
        try:
            import datasift  # noqa: F401

            _VALIDATOR_AVAILABLE = True
        except ImportError:
            _VALIDATOR_AVAILABLE = False
    return _VALIDATOR_AVAILABLE


class ValidationError(Exception):
    """Raised when schema validation fails."""


class SchemaValidator:
    """Thin wrapper around datasift-py for schema validation."""

    def __init__(self, schema: dict[str, Any] | None = None) -> None:
        self.schema = schema or {}
        self.available = _check_datasift()
        self._validator: Any = None
        if self.available and self.schema:
            self._build_validator()

    @classmethod
    def from_file(cls, path: str | os.PathLike[str]) -> "SchemaValidator":
        schema = load_schema(path)
        return cls(schema=schema)

    def _build_validator(self) -> None:
        try:
            import datasift

            self._validator = datasift.SchemaValidator(self.schema)
        except Exception as e:
            raise ValidationError(f"Failed to build validator: {e}") from e

    def validate(self, records: list[dict[str, Any]]) -> list[str]:
        if not self.available or not self._validator:
            return []
        errors: list[str] = []
        for i, record in enumerate(records):
            try:
                self._validator.validate(record)
            except Exception as e:
                errors.append(f"Record #{i}: {e}")
        return errors

    def is_available(self) -> bool:
        return self.available


def validate_before_diff(
    old: list[dict[str, Any]],
    new: list[dict[str, Any]],
    schema: dict[str, Any] | None = None,
    schema_file: str | os.PathLike[str] | None = None,
) -> None:
    """Validate both datasets before diffing."""
    if schema_file is not None:
        validator = SchemaValidator.from_file(schema_file)
    else:
        validator = SchemaValidator(schema)

    if not validator.is_available():
        return

    old_errors = validator.validate(old)
    new_errors = validator.validate(new)
    all_errors = old_errors + new_errors
    if all_errors:
        raise ValidationError(
            "Schema validation failed:\n" + "\n".join(all_errors)
        )