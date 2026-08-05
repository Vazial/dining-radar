"""Machine validation of acceptance responses against an OpenAPI schema fragment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# An arbitrary, stable identifier for "the currently loaded contract document"
# (not a reachable URL). Registering the whole document under this URI, then
# validating through a `{"$ref": DOCUMENT_URI + schema_ref}` wrapper rather
# than an extracted fragment, is what lets sibling "#/components/schemas/..."
# references inside the target schema resolve correctly. A bare extracted
# fragment has no `$id` of its own, so a JSON Schema validator constructed
# directly from it always treats *that fragment* as the document at the ""
# base URI -- shadowing the real document -- and any "#/..." reference to a
# sibling schema then fails with PointerToNowhere.
_DOCUMENT_URI = "urn:tdr-acceptance-openapi-document"


def assert_matches_openapi_schema(
    instance: object,
    contract_path: Path,
    schema_ref: str,
) -> None:
    """Load a YAML OpenAPI document and validate one response against its schema."""
    try:
        import jsonschema
        import referencing
        import referencing.jsonschema
        import yaml
    except ModuleNotFoundError as error:
        raise AssertionError(
            "acceptance schema validation requires test-only YAML, JSON Schema, "
            "and reference-resolution capabilities (PyYAML, jsonschema, referencing)"
        ) from error

    document = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    # OpenAPI 3.0's `nullable: true` predates JSON Schema 2020-12's native
    # `type: [X, "null"]` union support and is not understood by a plain
    # Draft 2020-12 validator, which would otherwise reject the contract's
    # own documented null field values (e.g. an unsupplied Candidate field).
    document = _expand_openapi_nullable(document)
    target = _resolve_local_ref(document, schema_ref)
    validator_type = jsonschema.validators.validator_for(target)
    validator_type.check_schema(target)

    resource = referencing.Resource.from_contents(
        document, default_specification=referencing.jsonschema.DRAFT202012
    )
    registry = referencing.Registry().with_resource(uri=_DOCUMENT_URI, resource=resource)
    wrapper_schema = {"$ref": f"{_DOCUMENT_URI}{schema_ref}"}
    validator_type(wrapper_schema, registry=registry).validate(instance)


def _expand_openapi_nullable(node: Any) -> Any:
    """Rewrite every ``nullable: true`` OpenAPI 3.0 schema node as a plain
    ``anyOf`` null-union a JSON Schema Draft 2020-12 validator understands.

    A schema-level ``type`` rewrite is not enough on its own: this contract
    also uses ``nullable: true`` together with ``allOf``/``$ref`` (e.g. the
    ``proposal`` property, whose own node has no ``type`` keyword at all --
    the object shape comes only from the referenced ``CandidateConcept``
    schema), so wrapping the whole node in ``anyOf`` is the only rewrite that
    is correct regardless of which keywords the nullable node itself uses.
    """
    if isinstance(node, dict):
        expanded = {key: _expand_openapi_nullable(value) for key, value in node.items()}
        if expanded.pop("nullable", False):
            expanded = {"anyOf": [expanded, {"type": "null"}]}
        return expanded
    if isinstance(node, list):
        return [_expand_openapi_nullable(item) for item in node]
    return node


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
