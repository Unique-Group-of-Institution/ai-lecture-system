from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".githooks" / "pre-push"


def find_git_shell() -> str | None:
    shell = shutil.which("sh")
    if shell:
        return shell

    git = shutil.which("git")
    if not git:
        return None

    git_root = Path(git).resolve().parents[1]
    bundled_shell = git_root / "bin" / "sh.exe"
    return str(bundled_shell) if bundled_shell.is_file() else None


GIT_SHELL = find_git_shell()


@unittest.skipUnless(GIT_SHELL, "A POSIX shell is required to exercise the Git hook")
class GitSafetyHookTests(unittest.TestCase):
    def run_hook(self, remote_ref: str) -> subprocess.CompletedProcess[str]:
        update = (
            "refs/heads/task/test 1111111111111111111111111111111111111111 "
            f"{remote_ref} 0000000000000000000000000000000000000000\n"
        )
        return subprocess.run(
            [GIT_SHELL, str(HOOK), "origin", "https://example.invalid/repository.git"],
            cwd=ROOT,
            input=update,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_rejects_direct_push_to_main(self) -> None:
        result = self.run_hook("refs/heads/main")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Direct pushes to main are blocked", result.stderr)

    def test_allows_push_to_task_branch(self) -> None:
        result = self.run_hook("refs/heads/task/test")

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
