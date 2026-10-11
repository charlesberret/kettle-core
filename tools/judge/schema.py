"""Validate score files against ``schemas/scores.schema.json``.

The checker understands the keywords this schema uses (type, properties,
required, additionalProperties, items, pattern, minLength) and ignores
documentation keywords. It is not a general JSON Schema implementation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "scores.schema.json"


class SchemaError(ValueError):
    pass


def load_schema(path: Path | None = None) -> dict:
    path = path or SCHEMA_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def validate(instance, schema: dict | None = None, path: str = "$") -> None:
    """Raise ``SchemaError`` when ``instance`` does not match ``schema``."""
    schema = load_schema() if schema is None else schema
    types = schema.get("type")
    if isinstance(types, str):
        types = [types]
    if types and not any(_is_type(instance, typ) for typ in types):
        joined = " or ".join(types)
        raise SchemaError(f"{path} is not {joined}")
    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaError(f"{path} is not one of {schema['enum']}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise SchemaError(f"{path} is shorter than {schema['minLength']}")
        if "pattern" in schema and re.fullmatch(schema["pattern"], instance) is None:
            raise SchemaError(f"{path} does not match {schema['pattern']}")
    if isinstance(instance, dict) and (
        "properties" in schema or "required" in schema or "additionalProperties" in schema
    ):
        props = schema.get("properties") or {}
        for key in schema.get("required") or []:
            if key not in instance:
                raise SchemaError(f"{path}.{key} is required")
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            child = f"{path}.{key}"
            if key in props:
                validate(value, props[key], child)
            elif additional is False:
                raise SchemaError(f"{child} is not allowed")
            elif isinstance(additional, dict):
                validate(value, additional, child)
    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            validate(item, schema["items"], f"{path}[{index}]")


def _is_type(instance, typ: str) -> bool:
    if typ == "object":
        return isinstance(instance, dict)
    if typ == "array":
        return isinstance(instance, list)
    if typ == "string":
        return isinstance(instance, str)
    if typ == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if typ == "boolean":
        return isinstance(instance, bool)
    if typ == "null":
        return instance is None
    if typ == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    raise SchemaError(f"unsupported schema type {typ}")
