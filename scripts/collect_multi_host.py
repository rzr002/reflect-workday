#!/usr/bin/env python3
"""Plan or collect privacy-trimmed workday evidence from SSH aliases."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from collect_activity import parse_boundary


HOST_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
SSH_ALIAS_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
FORBIDDEN_KEYS = {"password", "passphrase", "privatekey", "identityfile", "token", "secret"}
CLOCK_SKEW_SECONDS = 300


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--person", required=True)
    parser.add_argument("--git-author")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--execute", action="store_true", help="Run the displayed SSH plan")
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def has_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = re.sub(r"[^a-z]", "", str(key).casefold())
            if normalized in FORBIDDEN_KEYS or has_forbidden_key(nested):
                return True
    elif isinstance(value, list):
        return any(has_forbidden_key(item) for item in value)
    return False


def load_manifest(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("主机清单 schema_version 必须为 1")
    if has_forbidden_key(value):
        raise ValueError("主机清单不得包含密码、令牌或私钥配置")
    hosts = value.get("hosts")
    if not isinstance(hosts, list) or not hosts:
        raise ValueError("主机清单至少需要一台主机")
    seen_ids: set[str] = set()
    validated: list[dict[str, Any]] = []
    for raw in hosts:
        if not isinstance(raw, dict):
            raise ValueError("每台主机必须是 JSON object")
        host_id = raw.get("host_id")
        alias = raw.get("ssh_alias")
        python_path = raw.get("python_path", "python3")
        sessions_root = raw.get("sessions_root")
        repo_roots = raw.get("repo_roots", [])
        if not isinstance(host_id, str) or HOST_ID_RE.fullmatch(host_id) is None:
            raise ValueError("host_id 只能使用小写字母、数字和连字符")
        if host_id in seen_ids:
            raise ValueError(f"host_id 重复: {host_id}")
        if not isinstance(alias, str) or SSH_ALIAS_RE.fullmatch(alias) is None:
            raise ValueError(f"{host_id}: ssh_alias 必须是具体的 OpenSSH 别名")
        if not isinstance(python_path, str) or (
            python_path != "python3" and not PurePosixPath(python_path).is_absolute()
        ):
            raise ValueError(f"{host_id}: python_path 必须是 python3 或绝对路径")
        if not isinstance(sessions_root, str) or not PurePosixPath(sessions_root).is_absolute():
            raise ValueError(f"{host_id}: sessions_root 必须是绝对路径")
        if not isinstance(repo_roots, list) or any(
            not isinstance(item, str) or not PurePosixPath(item).is_absolute() for item in repo_roots
        ):
            raise ValueError(f"{host_id}: repo_roots 必须是绝对路径数组")
        seen_ids.add(host_id)
        validated.append(
            {
                "host_id": host_id,
                "ssh_alias": alias,
                "python_path": python_path,
                "sessions_root": sessions_root,
                "repo_roots": repo_roots,
            }
        )
    return validated


def remote_command(host: dict[str, Any], args: argparse.Namespace) -> list[str]:
    command = [
        host["python_path"],
        "-",
        "--person",
        args.person,
        "--git-author",
        args.git_author or args.person,
        "--start",
        args.start,
        "--end",
        args.end,
        "--timezone",
        args.timezone,
        "--sessions-root",
        host["sessions_root"],
        "--portable",
        "--output",
        "-",
    ]
    for root in host["repo_roots"]:
        command.extend(["--repo-root", root])
    return command


def ssh_command(host: dict[str, Any], args: argparse.Namespace) -> list[str]:
    return [
        "ssh",
        "-T",
        "-o",
        "BatchMode=yes",
        host["ssh_alias"],
        shlex.join(remote_command(host, args)),
    ]


def build_plan(hosts: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    return {
        "mode": "plan",
        "period": {"start": args.start, "end": args.end, "timezone": args.timezone},
        "hosts": [
            {
                "host_id": host["host_id"],
                "ssh_alias": host["ssh_alias"],
                "python_path": host["python_path"],
                "sessions_root": host["sessions_root"],
                "repo_roots": host["repo_roots"],
                "ssh_command": shlex.join(ssh_command(host, args)),
                "collector_transport": "ssh_stdin_not_saved",
            }
            for host in hosts
        ],
        "notice": "计划模式不会连接主机；确认后再加 --execute。",
    }


def classify_failure(stderr: str) -> str:
    lowered = stderr.casefold()
    if "permission denied" in lowered or "authentication failed" in lowered:
        return "authentication_failed"
    if "host key verification failed" in lowered or "remote host identification has changed" in lowered:
        return "host_key_failed"
    if any(
        marker in lowered
        for marker in ("could not resolve hostname", "connection timed out", "connection refused", "no route to host")
    ):
        return "unreachable"
    return "collection_failed"


def has_clock_skew(generated_at: Any) -> bool:
    if not isinstance(generated_at, str):
        return False
    try:
        remote_time = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if remote_time.tzinfo is None:
        remote_time = remote_time.replace(tzinfo=timezone.utc)
    return abs((datetime.now(timezone.utc) - remote_time.astimezone(timezone.utc)).total_seconds()) > CLOCK_SKEW_SECONDS


def utc_iso(raw: Any, source_timezone: str) -> str | None:
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(source_timezone))
    return parsed.astimezone(timezone.utc).isoformat()


def collect_host(
    host: dict[str, Any], args: argparse.Namespace
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    try:
        result = subprocess.run(
            ssh_command(host, args),
            input=Path(__file__).with_name("collect_activity.py").read_text(encoding="utf-8"),
            capture_output=True,
            text=True,
            timeout=args.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, {
            "host_id": host["host_id"],
            "status": "not_collected",
            "error_code": "timeout",
        }
    except OSError:
        return None, {
            "host_id": host["host_id"],
            "status": "not_collected",
            "error_code": "ssh_unavailable",
        }
    if result.returncode != 0:
        return None, {
            "host_id": host["host_id"],
            "status": "not_collected",
            "error_code": classify_failure(result.stderr),
        }
    try:
        evidence = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, {
            "host_id": host["host_id"],
            "status": "not_collected",
            "error_code": "invalid_evidence",
        }
    if not isinstance(evidence, dict) or not isinstance(evidence.get("events"), list):
        return None, {
            "host_id": host["host_id"],
            "status": "not_collected",
            "error_code": "invalid_evidence",
        }
    source_timezone = evidence.get("period", {}).get("timezone")
    status = {
        "host_id": host["host_id"],
        "status": "collected",
        "events": len(evidence["events"]),
    }
    if isinstance(source_timezone, str):
        status["source_timezone"] = source_timezone
    if has_clock_skew(evidence.get("generated_at")):
        status["warning_codes"] = ["clock_skew"]
    return evidence, status


def event_key(event: dict[str, Any], host_id: str) -> tuple[str, ...]:
    source = str(event.get("source") or "unknown")
    if source == "codex":
        return (source, str(event.get("id") or ""))
    if source == "git":
        fingerprint = str(event.get("repo_fingerprint") or f"project:{event.get('project', 'unknown')}")
        commit_hash = str(event.get("commit_hash") or str(event.get("id") or "").rsplit(":", 1)[-1])
        return (source, fingerprint, commit_hash)
    return (source, host_id, str(event.get("id") or ""))


def normalized_period(args: argparse.Namespace) -> dict[str, str]:
    zone = ZoneInfo(args.timezone)
    start = parse_boundary(args.start, zone)
    end = parse_boundary(args.end, zone)
    if end <= start:
        raise ValueError("end 必须晚于 start")
    return {
        "start_inclusive": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "timezone": args.timezone,
    }


def merge_results(
    results: list[tuple[str, dict[str, Any] | None, dict[str, Any]]], args: argparse.Namespace
) -> dict[str, Any]:
    events: dict[tuple[str, ...], dict[str, Any]] = {}
    limitations: list[str] = []
    collected = 0
    for host_id, evidence, status in results:
        if evidence is None:
            continue
        collected += 1
        for limitation in evidence.get("limitations", []):
            if isinstance(limitation, str) and limitation not in limitations:
                limitations.append(limitation)
        source_timezone = evidence.get("period", {}).get("timezone")
        if not isinstance(source_timezone, str):
            source_timezone = args.timezone
        for raw_event in evidence["events"]:
            if not isinstance(raw_event, dict):
                continue
            key = event_key(raw_event, host_id)
            if key not in events:
                event = dict(raw_event)
                event["host_ids"] = [host_id]
                event["source_timezones"] = [source_timezone]
                event["start_utc"] = utc_iso(event.get("start"), source_timezone)
                event["end_utc"] = utc_iso(event.get("end"), source_timezone)
                events[key] = event
                continue
            event = events[key]
            event["host_ids"].append(host_id)
            if source_timezone not in event["source_timezones"]:
                event["source_timezones"].append(source_timezone)
            if not event.get("outcome") and raw_event.get("outcome"):
                event["outcome"] = raw_event["outcome"]
            if not event.get("end") and raw_event.get("end"):
                event["end"] = raw_event["end"]
                event["end_utc"] = utc_iso(raw_event["end"], source_timezone)
    statuses = [status for _host_id, _evidence, status in results]
    if collected < len(results):
        limitations.append("部分主机未采集；未采集主机不能解释为空白工作日。")
    collection_status = "complete" if collected == len(results) else "partial" if collected else "failed"
    ordered_events = sorted(events.values(), key=lambda event: (str(event.get("start") or ""), str(event.get("id") or "")))
    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collection_status": collection_status,
        "person": {"display_name": args.person, "git_author": args.git_author or args.person},
        "period": normalized_period(args),
        "sources": {"hosts": statuses},
        "events": ordered_events,
        "limitations": limitations,
    }


def main() -> int:
    args = parse_args()
    try:
        hosts = load_manifest(args.manifest)
        normalized_period(args)
        if not args.execute:
            print(json.dumps(build_plan(hosts, args), ensure_ascii=False, indent=2))
            return 0
        if args.output is None:
            raise ValueError("--execute 必须同时提供 --output")
        results = []
        for host in hosts:
            evidence, status = collect_host(host, args)
            results.append((host["host_id"], evidence, status))
        merged = merge_results(results, args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(args.output)
        return 0 if merged["collection_status"] != "failed" else 1
    except (OSError, ValueError, json.JSONDecodeError, ZoneInfoNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
