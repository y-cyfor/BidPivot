#!/usr/bin/env python3
"""Generate TypeScript interfaces from the backend OpenAPI schema.

Usage:
    python scripts/generate-openapi-types.py
    python scripts/generate-openapi-types.py --url http://127.0.0.1:8000/openapi.json
    python scripts/generate-openapi-types.py --input /tmp/openapi.json

The generated file is committed so frontend builds do not require a running API.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

OUTPUT = Path("vben-admin/apps/bidpivot-frontend/src/types/openapi.ts")


def ts_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "Unnamed"


def ts_type(schema: dict | None) -> str:
    if not schema:
        return "unknown"
    if "$ref" in schema:
        return ts_name(schema["$ref"].rsplit("/", 1)[-1])
    if "const" in schema:
        return json.dumps(schema["const"], ensure_ascii=False)
    if "enum" in schema:
        return " | ".join(json.dumps(v, ensure_ascii=False) for v in schema["enum"])
    for key in ("anyOf", "oneOf"):
        if key in schema:
            options = []
            has_null = False
            for option in schema[key]:
                if option.get("type") == "null":
                    has_null = True
                    continue
                options.append(ts_type(option))
            rendered = " | ".join(dict.fromkeys(options)) or "unknown"
            return f"({rendered}) | null" if has_null else rendered
    if "allOf" in schema:
        return " & ".join(ts_type(part) for part in schema["allOf"]) or "unknown"

    kind = schema.get("type")
    if kind == "array":
        item = ts_type(schema.get("items"))
        return f"({item})[]" if "|" in item or "&" in item else f"{item}[]"
    if kind == "object":
        properties = schema.get("properties")
        if properties:
            required = set(schema.get("required", []))
            lines = []
            for key, value in properties.items():
                optional = "" if key in required else "?"
                lines.append(f"  {json.dumps(key)}{optional}: {ts_type(value)};")
            return "{\n" + "\n".join(lines) + "\n}"
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            return f"Record<string, {ts_type(additional)}>"
        return "Record<string, unknown>"
    if kind == "integer" or kind == "number":
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "null":
        return "null"
    return "string"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/openapi.json")
    parser.add_argument("--input")
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()

    if args.input:
        spec = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        with urllib.request.urlopen(args.url, timeout=30) as response:
            spec = json.load(response)

    schemas = spec.get("components", {}).get("schemas", {})
    lines = [
        "// AUTO-GENERATED from the BidPivot OpenAPI schema.",
        "// Run `python scripts/generate-openapi-types.py` after changing API schemas.",
        "",
    ]
    emitted: set[str] = set()
    for original, schema in schemas.items():
        name = ts_name(original)
        if name in emitted:
            continue
        emitted.add(name)
        if schema.get("type") != "object" or not schema.get("properties"):
            lines.append(f"export type {name} = {ts_type(schema)};")
            lines.append("")
            continue
        required = set(schema.get("required", []))
        lines.append(f"export interface {name} {{")
        for key, value in schema["properties"].items():
            optional = "" if key in required else "?"
            lines.append(f"  {json.dumps(key)}{optional}: {ts_type(value)};")
        lines.append("}")
        lines.append("")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {len(emitted)} schemas to {output}")


if __name__ == "__main__":
    main()
