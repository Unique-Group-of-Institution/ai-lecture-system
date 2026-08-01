#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCP_SRC = ROOT / "mcp-server" / "src"
for path in (ROOT, MCP_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

try:
    from lecture_workspace_mcp.server import main
except ModuleNotFoundError as exc:
    if exc.name == "mcp":
        print(
            "The free MCP Python package is not installed. Run scripts/setup_windows.ps1 "
            "or scripts/setup_posix.sh first.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    raise


if __name__ == "__main__":
    main()

