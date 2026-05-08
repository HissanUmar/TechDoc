from agentic_framework.schemas import (
    SchemaValidator,
    REQ_EXTRACT_SCHEMA,
    ARCH_DESIGN_SCHEMA,
    VALIDATION_RESULT_SCHEMA,
)


def test_schema_validator_valid_requirements():
    val = SchemaValidator()
    data = {"requirements": ["req1", "req2"]}
    res = val.validate(data, "requirements")
    assert res["valid"] is True
    assert res["errors"] == []


def test_schema_validator_invalid_requirements():
    val = SchemaValidator()
    data = {"other": "field"}
    res = val.validate(data, "requirements")
    assert res["valid"] is False
    assert len(res["errors"]) > 0


def test_schema_validator_valid_architecture():
    val = SchemaValidator()
    data = {
        "architecture": "microservices",
        "components": [
            {"name": "API", "role": "gateway"},
            {"name": "DB", "role": "persistence"},
        ],
    }
    res = val.validate(data, "architecture")
    assert res["valid"] is True


def test_schema_validator_unknown_schema():
    val = SchemaValidator()
    res = val.validate({"x": 1}, "unknown")
    assert res["valid"] is False
    assert "Unknown schema" in res["errors"][0]


def test_schema_validator_register_custom():
    val = SchemaValidator()
    custom = {
        "type": "object",
        "properties": {"custom_field": {"type": "string"}},
        "required": ["custom_field"],
    }
    val.register_schema("custom", custom)
    res = val.validate({"custom_field": "value"}, "custom")
    assert res["valid"] is True


def test_validation_result_schema():
    val = SchemaValidator()
    data = {"valid": True, "errors": []}
    res = val.validate(data, "validation")
    assert res["valid"] is True
