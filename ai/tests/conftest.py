import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas" / "telemetry"


@pytest.fixture(scope="session")
def schema() -> dict:
    return json.loads((SCHEMA_DIR / "v1.schema.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def validator(schema) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())
