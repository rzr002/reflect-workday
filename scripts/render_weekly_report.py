#!/usr/bin/env python3
"""Validate and render one Monday-to-Sunday reflection table."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


DATA_MARKER = "__REFLECT_WORKDAY_DATA__"
MAX_DAILY_ITEMS = 3
MAX_DAILY_SUMMARY = 100
MAX_ITEM_LENGTH = 80


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--reflection", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"需要 JSON object: {path}")
    return value


def iso_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} 必须是 ISO datetime")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} 必须是 ISO datetime") from exc
    return parsed


def natural_week_dates(evidence: dict[str, Any]) -> list[str]:
    period = evidence.get("period")
    if not isinstance(period, dict):
        raise ValueError("evidence.period 必须是 object")
    start = iso_datetime(period.get("start_inclusive"), "period.start_inclusive")
    end = iso_datetime(period.get("end_exclusive"), "period.end_exclusive")
    if start.time().isoformat() != "00:00:00" or end.time().isoformat() != "00:00:00":
        raise ValueError("周报范围必须从周一 00:00 到下周一 00:00")
    if start.date().weekday() != 0 or end.date() - start.date() != timedelta(days=7):
        raise ValueError("周报范围必须完整覆盖周一到周日")
    return [(start.date() + timedelta(days=offset)).isoformat() for offset in range(7)]


def validate_short_list(value: Any, field: str, max_items: int = MAX_DAILY_ITEMS) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} 必须是非空字符串数组")
    if len(value) > max_items:
        label = "工作主题" if field.endswith("themes") else "关键结果"
        scope = "整周" if field == "themes" else "每天"
        raise ValueError(f"{scope}最多 {max_items} 个{label}")
    if any(len(item.strip()) > MAX_ITEM_LENGTH for item in value):
        raise ValueError(f"{field} 的每项最多 {MAX_ITEM_LENGTH} 个字符")


def validate_weekly_reflection(reflection: dict[str, Any], expected_dates: list[str]) -> None:
    headline = reflection.get("headline")
    if not isinstance(headline, str) or not headline.strip() or len(headline.strip()) > MAX_DAILY_SUMMARY:
        raise ValueError("headline 必须是 1 至 100 个字符")
    themes = reflection.get("themes", [])
    validate_short_list(themes, "themes", max_items=5)

    days = reflection.get("days")
    if not isinstance(days, list) or [day.get("date") if isinstance(day, dict) else None for day in days] != expected_dates:
        raise ValueError("weekly reflection 必须按顺序包含周一到周日七天")
    for index, day in enumerate(days):
        summary = day.get("summary")
        if not isinstance(summary, str) or not summary.strip() or len(summary.strip()) > MAX_DAILY_SUMMARY:
            raise ValueError(f"days[{index}].summary 必须是 1 至 100 个字符")
        validate_short_list(day.get("themes", []), f"days[{index}].themes")
        validate_short_list(day.get("results", []), f"days[{index}].results")


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
        reflection = load_object(args.reflection)
        expected_dates = natural_week_dates(evidence)
        validate_weekly_reflection(reflection, expected_dates)
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
