# AI Lecture System — Agent Workspace

This repository is the shared source of truth for building the Phase-1 AI Lecture System with a human product owner, Claude Code, and ChatGPT/Codex.

The workspace is local-first and does not require paid model APIs. AI coding subscriptions are development tools; the production lecture pipeline uses local storage, local Whisper, FFmpeg, LibreOffice, and Python automation.

## Start here on Windows

1. Extract or clone this repository.
2. Open PowerShell in the repository root.
3. Run:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\scripts\setup_windows.ps1
   ```

4. Open `dashboard/index.html` in Microsoft Edge or Chrome.
5. Fill `docs/SYSTEM_PROFILE.md`.
6. Give Claude Code or Codex the reusable task prompt below.

## Reusable task prompt

> Open the project. Read AGENTS.md or CLAUDE.md, PROJECT_RULES.md, docs/STATUS.md, docs/DECISIONS.md, and tasks/tasks.json. Claim the next READY task, implement only that scope, run the required checks, update the task and project status, and stop for approval before migrations, deletion, external publication, credential changes, or paid dependencies.

## Human-friendly commands

```powershell
python scripts\taskctl.py list
python scripts\taskctl.py next
python scripts\taskctl.py claim T002 --owner claude
python scripts\taskctl.py status T002 REVIEW --actor claude --note "System profile captured"
python scripts\check_workspace.py
python scripts\build_dashboard.py
```

## Current target

Build one complete vertical slice:

`one teacher → one lecture request → approved scenes → scene audio → transcript/QC → corrected audio → slides → MP4 → admin approval`

See `docs/PHASE_1_SCOPE.md` and `docs/ARCHITECTURE.md` before adding features.

