# Product Marketing Context

**Document version:** v1
**Last updated:** 2026-09-08
**Basis:** Current public implementation. Audience and conversion goals are working assumptions, not customer research.

## Product overview

Reflect Workday is a Codex skill that reconstructs a daily timeline or weekly review from short Codex and Git evidence, with optional collection from approved OpenSSH hosts. Reports are self-contained local HTML. Core scripts use the Python standard library; the project is MIT licensed.

## Audience and problem

People working across Codex tasks, repositories, or development machines need to recall their work before preparing a personal review or weekly update. Digital evidence helps them remember, while meetings, thinking, and other missing context require their own recollection. There is no verified customer research or adoption evidence yet.

## Positioning and differentiation

- Make scattered task and commit evidence visible in a daily timeline.
- Show concurrent tasks in separate lanes.
- Provide either a trailing-seven-day review or a Monday-to-Sunday summary.
- Collect short evidence from explicitly approved hosts and deduplicate locally.
- Keep missing evidence unknown and combine it with the person's recollection.

## Alternatives and related projects

Manual weekly notes and reading Git logs are workflow alternatives; no comparative performance study is available. WorkSkill preserves work methods as wiki entries and skill candidates. Personal Workbench organizes and routes registered skills. Each project works independently; do not imply automatic report or data transfer.

## Objections and boundaries

- Is it a timesheet? No. Agent run windows and commit timestamps do not measure human labor time.
- Is it employee monitoring? No. Reports are for personal recall, not performance ratings.
- Does it collect complete conversations? Retained evidence consists of short visible clues rather than full transcripts or tool output.
- Is a local report automatically safe to publish? No. Real task titles and project labels may still be confidential.
- Can visitors try it without granting access? Yes. Bundled synthetic daily and weekly examples render without collecting work records.

## Voice and evidence

Concrete, calm, bilingual Chinese/English. Start with the weekly-recall problem and a visible report. Do not claim complete recall, exact time tracking, guaranteed privacy, time saved, or unmeasured usage. No verified customer quotes are available.

Proof sources: `examples/daily/`, `tests/fixtures/weekly-evidence.json`, `scripts/render_report.py`, `scripts/render_weekly_report.py`, `docs/privacy.md`, and synthetic screenshots in `docs/images/`.

## Goal

Primary README action: generate and open the synthetic daily report. Secondary action: install the skill and request a real daily or weekly review. Request feedback using synthetic examples. Visits and clones indicate discovery, not successful report generation; there is no usage telemetry.

## Changelog

- v1 (2026-09-08) — Capture weekly-recall positioning, synthetic-demo onboarding, and evidence/privacy boundaries.
