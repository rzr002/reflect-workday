# Reflect Workday

**Recall what you worked on before you write your weekly update.**

Reflect Workday is a Codex skill for people whose work spans multiple tasks, projects, or development machines. It turns short Codex and Git evidence into a daily timeline or weekly review, ready for you to add meetings, thinking, and work that left no digital trace.

**[Generate a sample report](#demo)** · [Install in Codex](#install) · [中文说明](README.md) · [Privacy](docs/privacy.md)

Python **3.9+** · No third-party dependencies in the core scripts · Local HTML reports · [MIT](LICENSE)

> The report is a set of visible clues plus your own recollection. It is not a timesheet or a performance score.

- **Recall yesterday:** put Codex tasks and Git commits on a shared timeline.
- **Prepare a weekly update:** review the last seven days or a Monday-to-Sunday table of themes and outcomes.
- **Combine development machines:** collect short evidence from approved OpenSSH hosts and deduplicate it locally.

<a id="demo"></a>
## Generate a sample report

Requires only Python and Git. This demo uses bundled synthetic data; it needs no skill installation, work records, or remote connection.

```bash
git clone https://github.com/rzr002/reflect-workday.git
cd reflect-workday
python3 scripts/render_report.py \
  --evidence examples/daily/evidence.json \
  --reflection examples/daily/reflection.json \
  --template assets/reflection.html \
  --output /tmp/reflect-workday-daily.html
```

Open `/tmp/reflect-workday-daily.html` in a browser to see the daily timeline below. To review your own work, continue with [installation](#install).

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

<a id="install"></a>
## Install

If you have not run the demo, clone the repository first:

```bash
git clone https://github.com/rzr002/reflect-workday.git
cd reflect-workday
```

From the repository directory, link the skill into your personal skills directory on macOS or Linux. If the target already exists, this command only displays it for inspection.

```bash
mkdir -p "$HOME/.agents/skills"
if [ -e "$HOME/.agents/skills/reflect-workday" ] || [ -L "$HOME/.agents/skills/reflect-workday" ]; then
  ls -ld "$HOME/.agents/skills/reflect-workday"
else
  ln -s "$PWD" "$HOME/.agents/skills/reflect-workday"
fi
```

Keep the cloned directory in place because the link points to it. Review the source and local changes of an existing installation before replacing it.

Restart Codex, then try:

```text
Use $reflect-workday to summarize what I did yesterday as a read-only timeline.
```

```text
Use $reflect-workday to summarize last Monday through Sunday as a concise weekly table.
```

For multiple hosts, copy `hosts.example.json` to an ignored local file and replace only the SSH aliases and scan paths. Never add credentials to the manifest.

## Generate a sample weekly report

From the cloned repository directory:

```bash
python3 scripts/render_weekly_report.py \
  --evidence tests/fixtures/weekly-evidence.json \
  --reflection tests/fixtures/weekly-reflection.json \
  --template assets/weekly-reflection.html \
  --output /tmp/reflect-workday-weekly.html
```

Open `/tmp/reflect-workday-weekly.html` in a browser. This also uses synthetic data only.

## Test

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests -p 'test_*.py' -v
```

## License

[MIT](LICENSE)

## Feedback and related projects

[Report a problem](https://github.com/rzr002/reflect-workday/issues) with expected behavior and a synthetic example, or read the [contribution guide](CONTRIBUTING.md) to help improve the templates. For private reports, follow [SECURITY.md](SECURITY.md).

- [WorkSkill](https://github.com/rzr002/workskill): preserve work methods in a wiki and propose reusable skills.
- [Personal Workbench](https://github.com/rzr002/personal-workbench): organize and route existing personal and team skills.

Each project works independently. There is no automatic transfer of reports or personal records between them.
