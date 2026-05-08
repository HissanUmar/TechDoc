"""JSON schemas for inter-agent contracts and a simple validator."""

import logging
from typing import Any, Dict

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

logger = logging.getLogger(__name__)


# -- Agent Output Schemas ------------------------------------------------

REQ_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "requirements": {
            "type": "array",
            "items": {"type": "string"}
        },
    },
    "required": ["requirements"],
    "additionalProperties": True,
}

ARCH_DESIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "architecture": {"type": "string"},
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                },
                "required": ["name"],
            }
        },
    },
    "required": ["architecture"],
    "additionalProperties": True,
}

VALIDATION_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "valid": {"type": "boolean"},
        "errors": {
            "type": "array",
            "items": {"type": "string"}
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"}
        },
    },
    "required": ["valid"],
    "additionalProperties": True,
}


# -- Schema Validator -------------------------------------------------------

class SchemaValidator:
    """Validates outputs against JSON schemas."""

    def __init__(self) -> None:
        self.schemas = {
            "requirements": REQ_EXTRACT_SCHEMA,
            "architecture": ARCH_DESIGN_SCHEMA,
            "validation": VALIDATION_RESULT_SCHEMA,
        }

    def validate(self, data: Any, schema_name: str) -> Dict[str, Any]:
        """Validate data against a named schema.

        Returns a dict with keys:
          - valid: bool, whether validation passed
          - errors: list of error messages if invalid
          - schema_name: name of schema used
        """
        if schema_name not in self.schemas:
            return {
                "valid": False,
                "errors": [f"Unknown schema: {schema_name}"],
                "schema_name": schema_name,
            }

        schema = self.schemas[schema_name]

        if not JSONSCHEMA_AVAILABLE:
            # Fallback: just check that data is a dict with expected keys
            if not isinstance(data, dict):
                return {
                    "valid": False,
                    "errors": [f"Data is not a dict"],
                    "schema_name": schema_name,
                }
            required = schema.get("required", [])
            missing = [k for k in required if k not in data]
            if missing:
                return {
                    "valid": False,
                    "errors": [f"Missing required keys: {missing}"],
                    "schema_name": schema_name,
                }
            return {"valid": True, "errors": [], "schema_name": schema_name}

        try:
            jsonschema.validate(instance=data, schema=schema)
            return {"valid": True, "errors": [], "schema_name": schema_name}
        except jsonschema.ValidationError as e:
            return {
                "valid": False,
                "errors": [str(e)],
                "schema_name": schema_name,
            }
        except Exception as e:
            logger.exception("Unexpected error during validation")
            return {
                "valid": False,
                "errors": [f"Validation error: {e}"],
                "schema_name": schema_name,
            }

    def register_schema(self, name: str, schema: Dict[str, Any]) -> None:
        """Register a new schema."""
        self.schemas[name] = schema
