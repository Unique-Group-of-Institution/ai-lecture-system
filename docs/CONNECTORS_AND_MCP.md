# Connectors and MCP Plan

## Phase-1 connectors

1. GitHub for repository, issues, pull requests and review.
2. Local project MCP server for tasks, decisions and later lecture operations.
3. Playwright MCP later for teacher/admin portal browser testing.

Do not add Asana, Notion, Airtable or CRM systems until GitHub task management proves insufficient.

## Local MCP rollout

The committed server configuration is intentionally safe:

- Claude Code reads `.mcp.json` and asks the user to trust the project server.
- Codex configuration exists in `.codex/config.toml` but starts disabled.
- Run the setup script, verify `python scripts/run_mcp.py`, then set `enabled = true` for Codex.
- Never store credentials in either MCP configuration file.

## Initial MCP tools

- `workspace_health`
- `get_project_status`
- `get_next_task`
- `claim_task`
- `update_task_status`
- `record_decision`
- `read_project_document`

Lecture-domain tools will be added through reviewed tasks, not exposed pre-emptively.

