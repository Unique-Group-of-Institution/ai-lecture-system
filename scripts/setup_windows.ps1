$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "Creating local Python environment..." -ForegroundColor Cyan
python -m venv .venv
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -e ".\mcp-server"
& $PythonExe ".\scripts\system_probe.py"
& $PythonExe ".\scripts\check_workspace.py"

Write-Host "" 
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Open dashboard\index.html in Microsoft Edge or Chrome."
Write-Host "Claude Code will ask you to approve the project MCP server on first use."
Write-Host "After MCP health is verified, edit .codex\config.toml and set enabled = true."

