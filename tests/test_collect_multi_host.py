from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "collect_multi_host.py"


class CollectMultiHostTests(unittest.TestCase):
    def test_plan_is_default_and_does_not_invoke_ssh(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_manifest(root, hosts=[self._host("alpha", "host-a")])
            sentinel = root / "ssh-called"
            self._write_fake_ssh(root, sentinel)
            result = self._run(root, manifest)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(sentinel.exists())
            plan = json.loads(result.stdout)
            self.assertEqual(plan["mode"], "plan")
            self.assertEqual(plan["hosts"][0]["host_id"], "alpha")
            self.assertIn("BatchMode=yes", plan["hosts"][0]["ssh_command"])

    def test_manifest_does_not_require_remote_collector_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            host = self._host("alpha", "host-a")
            host.pop("collector_path")
            manifest = self._write_manifest(root, hosts=[host])
            self._write_fake_ssh(root, root / "ssh-called")
            result = self._run(root, manifest)

            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertNotIn("collector_path", plan["hosts"][0])
            self.assertIn("python3 -", plan["hosts"][0]["ssh_command"])
            self.assertEqual(plan["hosts"][0]["collector_transport"], "ssh_stdin_not_saved")

    def test_manifest_can_select_an_absolute_remote_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            host = self._host("alpha", "host-a")
            host["python_path"] = "/opt/conda/bin/python3"
            manifest = self._write_manifest(root, hosts=[host])
            self._write_fake_ssh(root, root / "ssh-called")
            result = self._run(root, manifest)

            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertIn("/opt/conda/bin/python3 -", plan["hosts"][0]["ssh_command"])

    def test_execute_merges_duplicates_and_preserves_partial_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_manifest(
                root,
                hosts=[
                    self._host("alpha", "host-a"),
                    self._host("beta", "host-b"),
                    self._host("gamma", "host-c"),
                ],
            )
            sentinel = root / "ssh-called"
            self._write_fake_ssh(root, sentinel)
            output = root / "merged.json"
            result = self._run(root, manifest, "--execute", "--output", str(output))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(sentinel.exists())
            evidence = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(evidence["events"]), 2)
            self.assertEqual(evidence["events"][0]["host_ids"], ["alpha", "beta"])
            self.assertEqual(evidence["events"][1]["host_ids"], ["alpha", "beta"])
            self.assertEqual(evidence["events"][0].get("start_utc"), "2026-08-31T01:00:00+00:00")
            self.assertEqual(evidence["events"][0].get("source_timezones"), ["Asia/Shanghai"])
            statuses = {item["host_id"]: item for item in evidence["sources"]["hosts"]}
            self.assertEqual(statuses["alpha"]["status"], "collected")
            self.assertEqual(statuses["alpha"].get("source_timezone"), "Asia/Shanghai")
            self.assertEqual(statuses["beta"]["status"], "collected")
            self.assertEqual(statuses["gamma"]["status"], "not_collected")
            self.assertEqual(statuses["gamma"]["error_code"], "authentication_failed")
            self.assertNotIn("ssh_alias", output.read_text(encoding="utf-8"))

    def test_manifest_rejects_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            host = self._host("alpha", "host-a")
            host["password"] = "do-not-store-this"
            manifest = self._write_manifest(root, hosts=[host])
            self._write_fake_ssh(root, root / "ssh-called")
            result = self._run(root, manifest)

            self.assertEqual(result.returncode, 2)
            self.assertIn("不得包含密码", result.stderr)
            self.assertNotIn("do-not-store-this", result.stderr)

    def test_all_failures_return_safe_specific_codes_and_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_manifest(
                root,
                hosts=[
                    self._host("auth", "host-c"),
                    self._host("keycheck", "host-d"),
                    self._host("offline", "host-e"),
                    self._host("slow", "host-f"),
                ],
            )
            self._write_fake_ssh(root, root / "ssh-called")
            output = root / "failed.json"
            result = self._run(
                root,
                manifest,
                "--execute",
                "--timeout",
                "5",
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            evidence = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(evidence["collection_status"], "failed")
            statuses = {item["host_id"]: item for item in evidence["sources"]["hosts"]}
            self.assertEqual(statuses["auth"]["error_code"], "authentication_failed")
            self.assertEqual(statuses["keycheck"]["error_code"], "host_key_failed")
            self.assertEqual(statuses["offline"]["error_code"], "unreachable")
            self.assertEqual(statuses["slow"]["error_code"], "timeout")
            serialized = output.read_text(encoding="utf-8")
            self.assertNotIn("Permission denied", serialized)
            self.assertNotIn("10.0.0.7", serialized)
            self.assertNotIn("host-c", serialized)

    def test_clock_skew_is_reported_without_discarding_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_manifest(root, hosts=[self._host("skewed", "host-g")])
            self._write_fake_ssh(root, root / "ssh-called")
            output = root / "skewed.json"
            result = self._run(root, manifest, "--execute", "--output", str(output))

            self.assertEqual(result.returncode, 0, result.stderr)
            evidence = json.loads(output.read_text(encoding="utf-8"))
            status = evidence["sources"]["hosts"][0]
            self.assertEqual(status["status"], "collected")
            self.assertEqual(status.get("warning_codes"), ["clock_skew"])

    def _run(self, root: Path, manifest: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PATH"] = f"{root}{os.pathsep}{environment.get('PATH', '')}"
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--manifest",
                str(manifest),
                "--person",
                "测试用户",
                "--git-author",
                "Test User",
                "--start",
                "2026-08-31",
                "--end",
                "2026-09-01",
                "--timezone",
                "Asia/Shanghai",
                *extra,
            ],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )

    def _write_manifest(self, root: Path, hosts: list[dict[str, object]]) -> Path:
        path = root / "hosts.json"
        path.write_text(json.dumps({"schema_version": 1, "hosts": hosts}), encoding="utf-8")
        return path

    def _host(self, host_id: str, alias: str) -> dict[str, object]:
        return {
            "host_id": host_id,
            "ssh_alias": alias,
            "collector_path": "/opt/reflect-workday/scripts/collect_activity.py",
            "sessions_root": "/home/user/.codex/sessions",
            "repo_roots": ["/work/projects"],
        }

    def _write_fake_ssh(self, root: Path, sentinel: Path) -> None:
        script = root / "ssh"
        script.write_text(
            textwrap.dedent(
                f"""\
                #!{sys.executable}
                import json
                import pathlib
                import sys
                import time
                from datetime import datetime, timezone

                pathlib.Path({str(sentinel)!r}).write_text("called", encoding="utf-8")
                alias = next((value for value in sys.argv if value in {{"host-a", "host-b", "host-c", "host-d", "host-e", "host-f", "host-g"}}), "")
                if alias == "host-c":
                    sys.stderr.write("Permission denied (publickey,password).\\n")
                    raise SystemExit(255)
                if alias == "host-d":
                    sys.stderr.write("REMOTE HOST IDENTIFICATION HAS CHANGED! Host key verification failed.\\n")
                    raise SystemExit(255)
                if alias == "host-e":
                    sys.stderr.write("ssh: Could not resolve hostname private-host: nodename nor servname provided.\\n")
                    raise SystemExit(255)
                if alias == "host-f":
                    time.sleep(6)
                evidence = {{
                    "schema_version": 2,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "person": {{"display_name": "测试用户", "git_author": "Test User"}},
                    "period": {{
                        "start_inclusive": "2026-08-31T00:00:00+08:00",
                        "end_exclusive": "2026-09-01T00:00:00+08:00",
                        "timezone": "Asia/Shanghai"
                    }},
                    "sources": {{
                        "codex": {{"files_scanned": 1, "events": 1, "errors": []}},
                        "git": {{"repositories_scanned": 1, "events": 1, "errors": []}}
                    }},
                    "events": [
                        {{
                            "id": "codex:turn-1", "source": "codex", "shape": "interval",
                            "start": "2026-08-31T09:00:00+08:00", "end": "2026-08-31T09:30:00+08:00",
                            "project": "demo", "title": "检查配置", "outcome": None,
                            "evidence": "observed"
                        }},
                        {{
                            "id": "git:repo123:abc123", "source": "git", "shape": "point",
                            "start": "2026-08-31T10:00:00+08:00", "end": None,
                            "project": "demo", "title": "提交修复", "outcome": "Test User 提交 abc123",
                            "evidence": "observed", "repo_fingerprint": "repo123",
                            "commit_hash": "abc123"
                        }}
                    ],
                    "limitations": ["测试线索"]
                }}
                if alias == "host-b":
                    evidence["events"][0]["outcome"] = "配置正常"
                if alias == "host-g":
                    evidence["generated_at"] = "2000-01-01T00:00:00+00:00"
                sys.stdout.write(json.dumps(evidence, ensure_ascii=False))
                """
            ),
            encoding="utf-8",
        )
        script.chmod(0o700)


if __name__ == "__main__":
    unittest.main()
