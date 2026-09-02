#!/usr/bin/env python3
"""Render one self-contained workday reflection HTML file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DATA_MARKER = "__REFLECT_WORKDAY_DATA__"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--reflection", type=Path)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"需要 JSON object: {path}")
    return value


def safe_embedded_json(value: Any) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def main() -> int:
    args = parse_args()
    try:
        evidence = load_object(args.evidence)
        reflection = load_object(args.reflection) if args.reflection else {}
        template = args.template.read_text(encoding="utf-8")
        if template.count(DATA_MARKER) != 1:
            raise ValueError(f"模板必须且只能包含一个 {DATA_MARKER}")
        payload = {"evidence": evidence, "reflection": reflection}
        html = template.replace(DATA_MARKER, safe_embedded_json(payload))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(html, encoding="utf-8")
        print(args.output)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
