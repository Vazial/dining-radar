"""Machine validation of acceptance responses against an OpenAPI schema fragment."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def assert_matches_openapi_schema(
    instance: object,
    contract_path: Path,
    schema_ref: str,
) -> None:
    """Load a YAML OpenAPI document and validate one response against its schema."""
    try:
        import jsonschema
        import yaml
    except ModuleNotFoundError as error:
        raise AssertionError(
            "acceptance schema validation requires test-only YAML and JSON Schema "
            "capabilities (PyYAML and jsonschema)"
        ) from error

    document = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    schema = _resolve_local_ref(document, schema_ref)
    validator_type = jsonschema.validators.validator_for(schema)
    validator_type.check_schema(schema)
    validator_type(schema).validate(instance)


def _resolve_local_ref(document: dict[str, Any], schema_ref: str) -> dict[str, Any]:
    if not schema_ref.startswith("#/"):
        raise AssertionError(f"only local OpenAPI refs are supported: {schema_ref}")
    current: object = document
    for raw_part in schema_ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            raise AssertionError(f"OpenAPI ref does not resolve: {schema_ref}")
        current = current[part]
    if not isinstance(current, dict):
        raise AssertionError(f"OpenAPI ref is not a schema object: {schema_ref}")
    return current
