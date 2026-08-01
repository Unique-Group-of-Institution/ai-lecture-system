# AI Lecture Workspace MCP Server

This is the local control-plane server shared by Claude Code and Codex. It exposes narrow project-management tools rather than unrestricted shell access.

## Install

Use the root setup script:

```powershell
.\scripts\setup_windows.ps1
```

## Run directly

```powershell
.\.venv\Scripts\python.exe .\scripts\run_mcp.py
```

STDIO transport does not print a normal web page. Use Claude Code `/mcp` or Codex MCP status to verify the connection.

## Security boundary

- Read access is limited to approved project documents.
- Write access is limited to task state and the architecture decision log.
- There is no arbitrary shell, delete, publish or credential tool.
- Lecture-domain tools will be added only after database and approval rules are tested.

