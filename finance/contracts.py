"""Validator for the documented JSON Schema subset used by our versioned contracts.

No $ref, regex or arbitrary remote schema loading. Domain checks remain mandatory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from finance.domain import FinanceError, Json, canonical, require, utc


def schema_check(value: Any, schema: Json, path: str = "command") -> None:
    if "const" in schema:
        require(
            type(value) is type(schema["const"]) and value == schema["const"],
            "INVALID_CONTRACT",
            f"{path}: wrong constant",
        )
    if "enum" in schema:
        require(value in schema["enum"], "INVALID_CONTRACT", f"{path}: value outside enum")
    type_tests = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "integer": lambda v: type(v) is int,
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: type(v) is bool,
        "null": lambda v: v is None,
        "number": lambda v: type(v) in (int, float),
    }
    if "type" in schema:
        expected = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        require(
            any(type_tests[t](value) for t in expected), "INVALID_CONTRACT", f"{path}: invalid type"
        )
    if isinstance(value, dict):
        require(
            set(schema.get("required", [])) <= value.keys(),
            "INVALID_CONTRACT",
            f"{path}: missing fields",
        )
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            require(
                value.keys() <= properties.keys(), "INVALID_CONTRACT", f"{path}: unknown fields"
            )
        for name, subschema in properties.items():
            if name in value:
                schema_check(value[name], subschema, path + "." + name)
    if isinstance(value, list):
        if schema.get("uniqueItems"):
            require(
                len({canonical(v) for v in value}) == len(value),
                "INVALID_CONTRACT",
                f"{path}: duplicate entries",
            )
        for item in value:
            if "items" in schema:
                schema_check(item, schema["items"], path + "[]")
    if isinstance(value, str):
        require(
            len(value) >= schema.get("minLength", 0)
            and len(value) <= schema.get("maxLength", 1000000),
            "INVALID_CONTRACT",
            f"{path}: length outside bounds",
        )
        if schema.get("format") == "date-time":
            utc(value)
    if type(value) in (int, float):
        require(
            value >= schema.get("minimum", float("-inf"))
            and value <= schema.get("maximum", float("inf")),
            "INVALID_CONTRACT",
            f"{path}: outside numeric bounds",
        )
    for subschema in schema.get("allOf", []):
        schema_check(value, subschema, path)
    if "oneOf" in schema:
        accepted = 0
        for subschema in schema["oneOf"]:
            try:
                schema_check(value, subschema, path)
                accepted += 1
            except FinanceError:
                pass
        require(accepted == 1, "INVALID_CONTRACT", f"{path}: oneOf mismatch")
    if "if" in schema:
        try:
            schema_check(value, schema["if"], path)
        except FinanceError:
            branch = "else"
        else:
            branch = "then"
        if branch in schema:
            schema_check(value, schema[branch], path)


def execution_contract(value: Json) -> None:
    path = Path(__file__).resolve().parent.parent / "contracts/execution-command.schema.json"
    schema_check(value, json.loads(path.read_text(encoding="utf-8")))
