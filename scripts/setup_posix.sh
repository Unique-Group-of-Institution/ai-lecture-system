#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ./mcp-server
.venv/bin/python scripts/system_probe.py
.venv/bin/python scripts/check_workspace.py

echo "Setup complete. Open dashboard/index.html."

