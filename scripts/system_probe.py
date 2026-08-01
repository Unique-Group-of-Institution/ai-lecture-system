#!/usr/bin/env python3
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command_version(command: str, args: list[str]) -> dict[str, str | bool]:
    path = shutil.which(command)
    if not path:
        return {"available": False, "path": "", "version": ""}
    try:
        result = subprocess.run(
            [path, *args], capture_output=True, text=True, timeout=10, check=False
        )
        text = (result.stdout or result.stderr).strip().splitlines()
        version = text[0] if text else "available"
    except (OSError, subprocess.TimeoutExpired) as exc:
        version = f"version check failed: {exc}"
    return {"available": True, "path": path, "version": version[:300]}


def main() -> int:
    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": sys.version.splitlines()[0],
        },
        "disk": {
            "workspace": str(ROOT),
            "free_bytes": shutil.disk_usage(ROOT).free,
            "total_bytes": shutil.disk_usage(ROOT).total,
        },
        "tools": {
            "git": command_version("git", ["--version"]),
            "ffmpeg": command_version("ffmpeg", ["-version"]),
            "node": command_version("node", ["--version"]),
            "libreoffice": command_version("libreoffice", ["--version"]),
            "claude": command_version("claude", ["--version"]),
            "codex": command_version("codex", ["--version"]),
        },
        "manual_fields_still_required": [
            "RAM",
            "GPU model and VRAM",
            "LMS name/version",
            "LMS upload or API method",
            "YouTube watch-folder path",
        ],
    }
    output = ROOT / "docs" / "SYSTEM_PROBE.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

