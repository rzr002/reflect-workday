# Reflect Workday

A privacy-first Codex skill that reconstructs a workday or week from short Codex and Git evidence.

[中文说明](README.md) · [Privacy](docs/privacy.md) · [Architecture](docs/architecture.md) · [GitHub publishing](docs/publishing.md) · [Contributing](CONTRIBUTING.md)

> The report is a set of visible clues plus your own recollection. It is not a timesheet or a performance score.

## Preview

### Daily timeline

![Synthetic daily reflection](docs/images/daily-timeline.png)

### Monday-to-Sunday summary

![Synthetic weekly reflection](docs/images/weekly-report.png)

Both screenshots use synthetic data only.

## Highlights

- Renders a read-only daily timeline with separate lanes for concurrent tasks.
- Produces either a trailing-seven-day view or a concise Monday-to-Sunday table.
- Merges and deduplicates evidence from approved OpenSSH hosts.
- Keeps only short task headlines, first-result sentences, timestamps, project labels, and Git commit subjects.
- Leaves days without visible evidence explicitly unknown.
- Produces self-contained local HTML with no network dependency.

## Privacy model

Reflect Workday does not read or store SSH passwords, tokens, private keys, shell history, full Codex conversations, reasoning, tool output, or source code. Remote collection returns only a trimmed `evidence.json`; raw sessions remain on the remote host.

Generated evidence may still contain private work titles and repository labels. Treat reports as private unless you review and redact them yourself. See [docs/privacy.md](docs/privacy.md).

## Requirements

- A Codex environment with skills support
- Python 3.9+
- Git for commit evidence
- OpenSSH for optional multi-host collection
- Node.js and Playwright only for development-time layout checks

The core Python scripts use the standard library only.

## Install

```bash
git clone https://github.com/rzr002/reflect-workday.git
cd reflect-workday
mkdir -p "$HOME/.agents/skills"
ln -s "$(pwd)" "$HOME/.agents/skills/reflect-workday"
```

Restart Codex, then try:

```text
Use $reflect-workday to summarize what I did yesterday as a read-only timeline.
```

```text
Use $reflect-workday to summarize last Monday through Sunday as a concise weekly table.
```

For multiple hosts, copy `hosts.example.json` to an ignored local file and replace only the SSH aliases and scan paths. Never add credentials to the manifest.

## Test

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests -p 'test_*.py' -v
```

## License

[MIT](LICENSE)
