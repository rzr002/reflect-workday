#!/usr/bin/env python3
"""Collect privacy-trimmed Codex and Git activity headlines for reflection."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ROLLOUT_ID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$",
    re.I,
)
SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|secret|password)(\s*[:=]\s*)[^\s,;]+"
)
TOKEN_RE = re.compile(r"\b(?:sk|ak)-[A-Za-z0-9_-]{10,}\b", re.I)
LONG_ID_RE = re.compile(r"(?<![A-Za-z0-9])\d{12,}(?![A-Za-z0-9])")
IP_RE = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?::\d{2,5})?(?!\d)")
INTERNAL_URL_RE = re.compile(r"https?://[^\s)\]}]+", re.I)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]{1,160})\]\([^\s)]+\)")
ABSOLUTE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])/(?:[A-Za-z0-9_.~-]+/){3,}([A-Za-z0-9_.~-]+)"
)
BOILERPLATE = ("<environment_context>", "<permissions instructions>", "<collaboration_mode>")
NOISE_TITLES = {"你好", "您好", "hi", "hello", "只回复 ok"}


def parse_args() -> argparse.Namespace:
    default_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--person", required=True, help="Display name")
    parser.add_argument("--git-author", help="Git --author pattern; defaults to person")
    parser.add_argument("--start", required=True, help="Inclusive ISO date or datetime")
    parser.add_argument("--end", required=True, help="Exclusive ISO date or datetime")
    parser.add_argument("--timezone", default="Asia/Shanghai", help="IANA timezone")
    parser.add_argument("--sessions-root", type=Path, default=default_home / "sessions")
    parser.add_argument("--repo-root", action="append", type=Path, default=[])
    parser.add_argument("--max-title-chars", type=int, default=160)
    parser.add_argument("--portable", action="store_true", help="Omit source paths for transfer")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def parse_boundary(raw: str, zone: ZoneInfo) -> datetime:
    text = raw.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return datetime.combine(date.fromisoformat(text), time.min, zone)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=zone) if parsed.tzinfo is None else parsed.astimezone(zone)


def parse_time(raw: Any) -> datetime | None:
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), timezone.utc)
        except (ValueError, OSError):
            return None
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def redact(text: str, limit: int) -> str:
    value = text.replace("\x00", " ").strip()
    value = MARKDOWN_LINK_RE.sub(lambda match: match.group(1), value)
    value = SECRET_RE.sub(lambda match: match.group(1) + match.group(2) + "[已隐藏]", value)
    value = TOKEN_RE.sub("[凭据已隐藏]", value)
    value = LONG_ID_RE.sub("[长编号已隐藏]", value)
    value = IP_RE.sub("[内部地址已隐藏]", value)
    value = INTERNAL_URL_RE.sub("[链接已隐藏]", value)
    value = ABSOLUTE_PATH_RE.sub(lambda match: f"…/{match.group(1)}", value)
    value = re.sub(r"\s+", " ", value)
    if len(value) > limit:
        value = value[:limit].rstrip(" ,，。；;:") + "…"
    return value


def headline(text: Any, limit: int) -> str | None:
    if not isinstance(text, str) or text.lstrip().startswith(BOILERPLATE):
        return None
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("#>*- ").strip()
        if not line or line.startswith(("```", "<")):
            continue
        return redact(line, limit) or None
    return None


def filename_session_id(path: Path) -> str | None:
    match = ROLLOUT_ID_RE.search(path.name)
    return match.group(1).lower() if match else None


def candidate_session_files(root: Path, start: datetime) -> Iterable[Path]:
    threshold = start.timestamp() - 86400
    for path in sorted(root.rglob("*.jsonl")):
        try:
            if path.stat().st_mtime < threshold:
                continue
        except OSError:
            continue
        yield path


def project_name(cwd: Any) -> str:
    if not isinstance(cwd, str) or not cwd:
        return "unknown"
    path = Path(cwd.rstrip("/"))
    return path.name or "unknown"


def collect_codex(
    root: Path, start: datetime, end: datetime, zone: ZoneInfo, title_limit: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events: dict[str, dict[str, Any]] = {}
    stats: Counter[str] = Counter()
    errors: list[str] = []

    if not root.is_dir():
        return [], {"root": str(root), "files_scanned": 0, "events": 0, "errors": ["session 目录不存在"]}

    for path in candidate_session_files(root, start):
        stats["files_scanned"] += 1
        try:
            handle = path.open("r", encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"{path.name}: {exc}")
            continue

        with handle:
            meta: dict[str, Any] | None = None
            current_turn: str | None = None
            primary = False
            for number, line in enumerate(handle, 1):
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    stats["malformed_lines"] += 1
                    continue
                payload = item.get("payload")
                item_type = item.get("type")
                if item_type == "session_meta" and isinstance(payload, dict):
                    meta = payload
                    lineage = str(payload.get("id") or "").lower()
                    file_id = filename_session_id(path)
                    primary = not payload.get("parent_thread_id") and bool(file_id) and file_id == lineage
                    continue
                if not primary or meta is None or item_type != "event_msg" or not isinstance(payload, dict):
                    continue

                payload_type = payload.get("type")
                when = parse_time(item.get("timestamp"))
                local_when = when.astimezone(zone) if when else None

                if payload_type == "task_started":
                    current_turn = str(payload.get("turn_id") or "") or None
                    if current_turn:
                        record = events.setdefault(
                            current_turn,
                            {
                                "turn_id": current_turn,
                                "project": project_name(meta.get("cwd")),
                                "title": None,
                                "outcome": None,
                                "start": None,
                                "end": None,
                                "last_activity": None,
                            },
                        )
                        if local_when and start <= local_when < end:
                            record["start"] = local_when
                            record["last_activity"] = local_when
                    continue

                if payload_type == "task_complete":
                    turn_id = str(payload.get("turn_id") or current_turn or "")
                    if not turn_id:
                        continue
                    record = events.setdefault(
                        turn_id,
                        {
                            "turn_id": turn_id,
                            "project": project_name(meta.get("cwd")),
                            "title": None,
                            "outcome": None,
                            "start": None,
                            "end": None,
                            "last_activity": None,
                        },
                    )
                    started = parse_time(payload.get("started_at"))
                    completed = parse_time(payload.get("completed_at"))
                    if started and completed:
                        local_start = started.astimezone(zone)
                        local_end = completed.astimezone(zone)
                        if local_start < end and local_end >= start:
                            record["start"] = max(start, local_start)
                            record["end"] = min(end, local_end)
                            record["last_activity"] = min(end, local_end)
                    continue

                if payload_type not in {"user_message", "agent_message"} or local_when is None:
                    continue
                if not (start <= local_when < end):
                    continue
                turn_id = str(payload.get("turn_id") or current_turn or "")
                if not turn_id:
                    digest = hashlib.blake2b(f"{path}:{number}".encode(), digest_size=10).hexdigest()
                    turn_id = f"unpaired-{digest}"
                record = events.setdefault(
                    turn_id,
                    {
                        "turn_id": turn_id,
                        "project": project_name(meta.get("cwd")),
                        "title": None,
                        "outcome": None,
                        "start": None,
                        "end": None,
                        "last_activity": None,
                    },
                )
                text = headline(payload.get("message"), title_limit)
                if payload_type == "user_message" and text and record["title"] is None:
                    record["title"] = text
                if payload_type == "agent_message" and payload.get("phase") != "commentary" and text:
                    record["outcome"] = text
                if record["start"] is None:
                    record["start"] = local_when
                record["last_activity"] = local_when

    output: list[dict[str, Any]] = []
    for turn_id, record in events.items():
        title = record["title"]
        if not title or title.casefold() in NOISE_TITLES:
            continue
        event_start = record["start"]
        if not isinstance(event_start, datetime) or not (start <= event_start < end):
            continue
        event_end = record["end"] or record["last_activity"]
        if isinstance(event_end, datetime) and event_end <= event_start:
            event_end = None
        output.append(
            {
                "id": f"codex:{turn_id}",
                "source": "codex",
                "shape": "interval" if event_end else "point",
                "start": event_start.isoformat(),
                "end": event_end.isoformat() if event_end else None,
                "project": record["project"],
                "title": title,
                "outcome": record["outcome"],
                "evidence": "observed",
            }
        )
    output.sort(key=lambda item: (item["start"], item["id"]))
    stats["events"] = len(output)
    return output, {
        "root": str(root),
        "files_scanned": stats["files_scanned"],
        "malformed_lines": stats["malformed_lines"],
        "events": len(output),
        "errors": errors[:20],
    }


SKIP_DIRS = {
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "node_modules",
    "target",
    "vendor",
}


def discover_repositories(roots: list[Path]) -> tuple[list[Path], list[str]]:
    repositories: set[Path] = set()
    errors: list[str] = []
    for root in roots:
        expanded = root.expanduser()
        if not expanded.exists():
            errors.append(f"项目根目录不存在: {expanded}")
            continue
        if (expanded / ".git").exists():
            repositories.add(expanded.resolve())
        for current, dirs, _files in os.walk(expanded, onerror=lambda exc: errors.append(str(exc))):
            current_path = Path(current)
            if ".git" in dirs or (current_path / ".git").is_file():
                repositories.add(current_path.resolve())
                dirs[:] = []
                continue
            dirs[:] = [name for name in dirs if name not in SKIP_DIRS and not name.startswith(".")]
    return sorted(repositories), errors


def normalize_repository_identity(raw: str) -> str:
    value = raw.strip()
    if "://" in value:
        try:
            parsed = urlsplit(value)
            host = (parsed.hostname or "").lower()
            port = f":{parsed.port}" if parsed.port else ""
            value = f"{host}{port}/{parsed.path.lstrip('/')}"
        except ValueError:
            pass
    else:
        match = re.fullmatch(r"(?:[^@/\s]+@)?([^:/\s]+):(.+)", value)
        if match:
            value = f"{match.group(1).lower()}/{match.group(2)}"
    return value.rstrip("/").removesuffix(".git")


def repository_fingerprint(repo: Path) -> str:
    command = ["git", "-C", str(repo), "config", "--get", "remote.origin.url"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        identity = f"origin:{normalize_repository_identity(result.stdout)}"
    else:
        identity = f"local:{repo.resolve()}"
    return hashlib.blake2b(identity.encode(), digest_size=8).hexdigest()


def collect_git(
    roots: list[Path], author: str, start: datetime, end: datetime, zone: ZoneInfo, title_limit: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    repos, errors = discover_repositories(roots)
    commits: dict[tuple[str, str], dict[str, Any]] = {}
    for repo in repos:
        repo_fingerprint = repository_fingerprint(repo)
        command = [
            "git",
            "-C",
            str(repo),
            "log",
            "--all",
            f"--since={start.isoformat()}",
            f"--until={end.isoformat()}",
            f"--author={author}",
            "--no-show-signature",
            "--pretty=format:%H%x1f%aI%x1f%an%x1f%s%x1f%D%x1e",
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"{repo.name}: {exc}")
            continue
        if result.returncode != 0:
            errors.append(f"{repo.name}: git log 失败")
            continue
        for raw_record in result.stdout.split("\x1e"):
            fields = raw_record.strip("\n").split("\x1f")
            if len(fields) != 5:
                continue
            commit_hash, authored_raw, author_name, subject, refs = fields
            authored = parse_time(authored_raw)
            if authored is None:
                continue
            local_authored = authored.astimezone(zone)
            if not (start <= local_authored < end):
                continue
            record = commits.setdefault(
                (repo_fingerprint, commit_hash),
                {
                    "id": f"git:{repo_fingerprint}:{commit_hash}",
                    "source": "git",
                    "shape": "point",
                    "start": local_authored.isoformat(),
                    "end": None,
                    "project": repo.name,
                    "title": redact(subject, title_limit),
                    "outcome": f"{author_name} 提交 {commit_hash[:7]}",
                    "evidence": "observed",
                    "repo_fingerprint": repo_fingerprint,
                    "commit_hash": commit_hash,
                    "repositories": [],
                    "refs": redact(refs, 100) if refs else None,
                },
            )
            if repo.name not in record["repositories"]:
                record["repositories"].append(repo.name)
    output = sorted(commits.values(), key=lambda item: (item["start"], item["id"]))
    return output, {
        "roots": [str(path) for path in roots],
        "repositories_scanned": len(repos),
        "events": len(output),
        "errors": errors[:40],
    }


def portable_source(source: dict[str, Any]) -> dict[str, Any]:
    sensitive_paths: list[str] = []
    if isinstance(source.get("root"), str):
        sensitive_paths.append(source["root"])
    if isinstance(source.get("roots"), list):
        sensitive_paths.extend(str(path) for path in source["roots"] if isinstance(path, str))
    portable = {key: value for key, value in source.items() if key not in {"root", "roots"}}
    if isinstance(portable.get("errors"), list):
        sanitized_errors = []
        for error in portable["errors"]:
            message = str(error)
            for path in sorted(sensitive_paths, key=len, reverse=True):
                message = message.replace(path, "…")
            sanitized_errors.append(redact(message, 200))
        portable["errors"] = sanitized_errors
    return portable


def main() -> int:
    args = parse_args()
    try:
        zone = ZoneInfo(args.timezone)
        start = parse_boundary(args.start, zone)
        end = parse_boundary(args.end, zone)
        if end <= start:
            raise ValueError("end 必须晚于 start")
        codex_events, codex_source = collect_codex(
            args.sessions_root.expanduser(), start, end, zone, args.max_title_chars
        )
        git_author = args.git_author or args.person
        git_events, git_source = collect_git(
            args.repo_root, git_author, start, end, zone, args.max_title_chars
        )
        events = sorted(codex_events + git_events, key=lambda item: (item["start"], item["id"]))
        sources = {"codex": codex_source, "git": git_source}
        if args.portable:
            sources = {name: portable_source(source) for name, source in sources.items()}
        evidence = {
            "schema_version": 2,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "person": {"display_name": args.person, "git_author": git_author},
            "period": {
                "start_inclusive": start.isoformat(),
                "end_exclusive": end.isoformat(),
                "timezone": args.timezone,
            },
            "sources": sources,
            "events": events,
            "limitations": [
                "Codex 只保留主会话的任务首行和结果首句；子代理与 fork 文本不进入叙事。",
                "Codex 任务区间是 agent 运行窗口，不等于用户持续工作时间。",
                "Git commit 是时间点，不能据此推算编码时长。",
                "没有数字线索的时间可能是会议、沟通、思考、休息、摸鱼或尚未想起。",
            ],
        }
        serialized = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
        if args.output == Path("-"):
            sys.stdout.write(serialized)
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized, encoding="utf-8")
            print(args.output)
        return 0
    except (OSError, ValueError, ZoneInfoNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
