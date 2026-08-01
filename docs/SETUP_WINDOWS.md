# Windows Setup

## Required base software

- Windows 10 or 11.
- Python 3.11 or newer.
- Git for Windows.
- FFmpeg.
- LibreOffice.
- Microsoft Edge or Chrome.
- Claude Code and/or ChatGPT desktop/Codex.

Local Whisper and the application framework are installed in later reviewed tasks after the system profile is known.

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

