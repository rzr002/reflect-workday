from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "render_weekly_report.py"
TEMPLATE = SKILL_DIR / "assets" / "weekly-reflection.html"


class WeeklyReportTests(unittest.TestCase):
    def test_natural_week_renders_seven_concise_days(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence = self._write_json(root / "evidence.json", self._evidence())
            reflection = self._write_json(root / "weekly-reflection.json", self._reflection())
            output = root / "index.html"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--evidence",
                    str(evidence),
                    "--reflection",
                    str(reflection),
                    "--template",
                    str(TEMPLATE),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            html = output.read_text(encoding="utf-8")
            self.assertIn('data-report-kind="weekly"', html)
            self.assertNotIn("__REFLECT_WORKDAY_DATA__", html)
            self.assertIn("2025-03-10", html)
            self.assertIn("2025-03-16", html)

    def test_weekly_reflection_requires_every_monday_to_sunday_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence = self._write_json(root / "evidence.json", self._evidence())
            value = self._reflection()
            value["days"].pop()
            reflection = self._write_json(root / "weekly-reflection.json", value)
            output = root / "index.html"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--evidence",
                    str(evidence),
                    "--reflection",
                    str(reflection),
                    "--template",
                    str(TEMPLATE),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("周一到周日", result.stderr)

    def test_daily_copy_is_bounded_for_a_scannable_week_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence = self._write_json(root / "evidence.json", self._evidence())
            value = self._reflection()
            value["days"][0]["themes"] = ["一", "二", "三", "四"]
            reflection = self._write_json(root / "weekly-reflection.json", value)
            output = root / "index.html"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--evidence",
                    str(evidence),
                    "--reflection",
                    str(reflection),
                    "--template",
                    str(TEMPLATE),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("最多 3 个工作主题", result.stderr)

    def test_week_can_keep_five_cross_day_themes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence = self._write_json(root / "evidence.json", self._evidence())
            value = self._reflection()
            value["themes"] = ["接口", "测试", "发布", "文档", "协作"]
            reflection = self._write_json(root / "weekly-reflection.json", value)
            output = root / "index.html"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--evidence",
                    str(evidence),
                    "--reflection",
                    str(reflection),
                    "--template",
                    str(TEMPLATE),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

    def _evidence(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "collection_status": "complete",
            "person": {"display_name": "示例用户", "git_author": "Example User"},
            "period": {
                "start_inclusive": "2025-03-10T00:00:00+08:00",
                "end_exclusive": "2025-03-17T00:00:00+08:00",
                "timezone": "Asia/Shanghai",
            },
            "sources": {
                "hosts": [
                    {"host_id": "dev-a", "status": "collected", "events": 1},
                    {"host_id": "dev-b", "status": "collected", "events": 0},
                ]
            },
            "events": [
                {
                    "id": "codex:example",
                    "source": "codex",
                    "shape": "interval",
                    "start": "2025-03-10T09:00:00+08:00",
                    "end": "2025-03-10T09:30:00+08:00",
                    "project": "sample-service",
                    "title": "核对接口契约",
                    "outcome": "确认兼容方案",
                    "evidence": "observed",
                    "host_ids": ["dev-a"],
                }
            ],
            "limitations": [],
        }

    def _reflection(self) -> dict[str, object]:
        start = date(2025, 3, 10)
        days = []
        for offset in range(7):
            day = start + timedelta(days=offset)
            days.append(
                {
                    "date": day.isoformat(),
                    "summary": "暂无可见线索" if offset else "梳理接口兼容方案",
                    "themes": [] if offset else ["接口契约"],
                    "results": [] if offset else ["确认兼容处理方式"],
                }
            )
        return {
            "headline": "围绕接口兼容与交付准备推进",
            "note": "这是一周的数字线索摘要，不是完整工时记录。",
            "themes": ["接口兼容"],
            "days": days,
        }

    def _write_json(self, path: Path, value: dict[str, object]) -> Path:
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
