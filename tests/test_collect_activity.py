from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import collect_activity  # noqa: E402


class CollectActivityTests(unittest.TestCase):
    def test_portable_source_redacts_even_a_short_configured_root(self) -> None:
        portable = collect_activity.portable_source(
            {"root": "/x", "files_scanned": 0, "events": 0, "errors": ["无法读取 /x"]}
        )

        self.assertNotIn("/x", json.dumps(portable, ensure_ascii=False))

    def test_portable_stdout_omits_source_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sessions = root / "private" / "codex" / "sessions"
            sessions.mkdir(parents=True)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "collect_activity.py"),
                    "--person",
                    "测试用户",
                    "--start",
                    "2026-08-31",
                    "--end",
                    "2026-09-01",
                    "--timezone",
                    "Asia/Shanghai",
                    "--sessions-root",
                    str(sessions),
                    "--repo-root",
                    str(root / "missing" / "private" / "repo"),
                    "--portable",
                    "--output",
                    "-",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertNotIn("root", evidence["sources"]["codex"])
        self.assertNotIn("roots", evidence["sources"]["git"])
        self.assertNotIn(temp_dir, result.stdout)

    def test_same_commit_hash_in_different_repository_identities_is_not_collapsed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first"
            second = root / "second"
            self._create_repository(first)
            subprocess.run(["git", "clone", "-q", str(first), str(second)], check=True)
            subprocess.run(
                ["git", "-C", str(first), "remote", "add", "origin", "ssh://git@example.test/team/first.git"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(second), "remote", "set-url", "origin", "ssh://git@example.test/team/second.git"],
                check=True,
            )
            zone = ZoneInfo("Asia/Shanghai")
            events, _stats = collect_activity.collect_git(
                [root],
                "Test User",
                datetime(2026, 8, 31, tzinfo=zone),
                datetime(2026, 9, 1, tzinfo=zone),
                zone,
                160,
            )

        self.assertEqual(len(events), 2)
        self.assertEqual(len({event["commit_hash"] for event in events}), 1)
        self.assertEqual(len({event["repo_fingerprint"] for event in events}), 2)

    def _create_repository(self, path: Path) -> None:
        path.mkdir()
        subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(path), "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.test"], check=True)
        (path / "note.txt").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(path), "add", "note.txt"], check=True)
        environment = os.environ.copy()
        environment.update(
            {
                "GIT_AUTHOR_DATE": "2026-08-31T08:00:00+08:00",
                "GIT_COMMITTER_DATE": "2026-08-31T08:00:00+08:00",
            }
        )
        subprocess.run(
            ["git", "-C", str(path), "commit", "-q", "-m", "测试提交"],
            check=True,
            env=environment,
        )


if __name__ == "__main__":
    unittest.main()
