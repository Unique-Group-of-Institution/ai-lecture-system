# Windows Setup

## Required base software

- Windows 10 or 11.
- Python 3.12 or newer (Python 3.14 is used on the target system).
- Git for Windows.
- FFmpeg.
- LibreOffice.
- Microsoft Edge or Chrome.
- Claude Code and/or ChatGPT desktop/Codex.

Local Whisper and the application framework are installed in later reviewed tasks after the system profile is known.

## Local audio benchmark

T020 uses pinned portable tools under the ignored `data\lectures\t020-local`
directory; it does not install packages globally or modify `PATH`. See
`docs/LOCAL_AUDIO_BENCHMARK.md` for checksums, placement, source-safe PCM
conversion and the repeatable benchmark command. Model weights, tool archives,
executables, teacher audio, transcripts and QC artifacts must never be committed.

The tracked benchmark/QC code has no additional Python dependency. Keep using
the project environment described below. Automated tests generate synthetic WAV
and Urdu/English JSON fixtures and do not require FFmpeg, Whisper or teacher media.

## Django database foundation

Create and activate a dedicated virtual environment, then install the project and initialize the
local SQLite database:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
$env:AI_LECTURE_SECRET_KEY = "choose-a-local-development-value"
python manage.py migrate
python manage.py check
python manage.py test
```

`AI_LECTURE_SECRET_KEY` is required and must be supplied through the process environment. The
example above is a placeholder, not a production secret. Choose a private local value and set it
again in each new PowerShell session. Do not put a real value in tracked files or commit a populated
`.env` file. CI uses a synthetic test-only value configured in the workflow.

The default database is `db.sqlite3` in the repository root and is ignored by Git. For disposable
validation, set `AI_LECTURE_SQLITE_PATH` to a temporary `.sqlite3` path before running migrations.
Production credentials and production database settings do not belong in this local settings file.

## Local chapter-content tools

T021 accepts only PDF, PNG and JPG/JPEG sources. Originals and extracted text stay beneath ignored
`data\content-library`; quarantined wheels, OCR binaries and language models stay beneath ignored
`data\content-tools`. Never point storage at a personal folder. Real institutional or teacher
documents require separate authorization for their exact paths.

Install the verified wheels only in the project environment with the tracked hash lock:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index `
  --find-links data\content-tools\downloads --require-hashes `
  -r requirements-content.lock
```

The local OCR runtime is Tesseract 5.4.0.20240606 with official `tessdata_fast` 4.1.0 `urd`, `eng`
and `osd` data. It is invoked by explicit project-local paths with `urd+eng`; it is not installed,
added to `PATH`, or permitted to upload content. Equations, diagrams, RTL layout and complex pages
may OCR imperfectly, so low-confidence pages require teacher review against the retained original.

Optional process-only settings are `AI_LECTURE_CONTENT_ROOT`, `AI_LECTURE_CONTENT_MAX_BYTES`,
`AI_LECTURE_TESSERACT_PATH`, `AI_LECTURE_TESSDATA_PATH` and
`AI_LECTURE_OCR_TIMEOUT_SECONDS`. Keep their paths inside ignored project-local storage.

## Bootstrap

Open PowerShell in the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
```

The script creates `.venv`, installs the free MCP SDK, writes `docs/SYSTEM_PROBE.json`, runs tests and regenerates the dashboard.

## Claude Code

Open Claude Code from the repository root. It will discover `CLAUDE.md` and `.mcp.json`. Review and approve the local project MCP server when prompted. Use `/mcp` to inspect its status.

## Codex

Open this repository as the primary local project. Codex discovers `AGENTS.md` automatically. After the setup script passes, edit `.codex/config.toml` and change:

```toml
enabled = true
```

Restart the Codex session and inspect MCP status.

## First project task

Complete `docs/SYSTEM_PROFILE.md`, then run:

```powershell
python scripts\taskctl.py claim T002 --owner claude
python scripts\system_probe.py
python scripts\taskctl.py status T002 REVIEW --actor claude --note "System profile completed" --verification "docs/SYSTEM_PROFILE.md and docs/SYSTEM_PROBE.json"
```
