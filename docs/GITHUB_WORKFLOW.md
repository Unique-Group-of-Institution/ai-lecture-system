# GitHub Workflow

## Repository

- Owner: `Unique-Group-of-Institution`
- Repository: `ai-lecture-system`
- Visibility: private
- Canonical URL: `https://github.com/Unique-Group-of-Institution/ai-lecture-system`
- Default branch: `main`

Do not mirror or fall back to a personal repository. Project source, teacher
content and generated media must not be made public.

## Pull-request workflow

1. Claim one READY task, then create a short-lived branch from `main`. Use
   `task/<task-id>-<description>` for tracked tasks (for example,
   `task/t003-free-git-safety`) or `feature/<description>` for approved work
   without a task ID.
2. Make only task-scoped changes and run workspace validation and all tests.
3. Push the branch and open a pull request into `main`.
4. Wait for the required `workspace-ci` pull-request check to pass before
   review or merge.
5. Have the human product owner or an independent agent review the task and
   move it from `REVIEW` to `DONE` when accepted.
6. Merge without force-pushing and delete only the short-lived branch.

## Install local Git safety

Run this safe, repeatable command once in every Windows clone:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_git_safety.ps1
```

It sets the repository-local configuration `core.hooksPath=.githooks`. The
version-controlled `pre-push` hook then rejects any push whose destination is
`refs/heads/main`, while allowing task and feature branches. Do not bypass the
hook with `--no-verify`.

Local hooks are not equivalent to server-side branch protection: they apply
only to clones where they have been installed and can be changed by a local
operator. Every clone must run the setup command. Pull requests and passing CI
remain mandatory even though GitHub cannot enforce those rules on the current
private-repository plan.

On 2026-08-03 GitHub rejected server-side protection with HTTP 403 because the
organization plan does not support it for this private repository. The product
owner approved the local hook plus pull-request workflow as the zero-cost Phase
1 substitute. A paid plan upgrade is explicitly deferred; the repository must
remain private and institutional. Required approving reviews remain off while
there is only one GitHub operator. This does not relax the project rule that an
implementer cannot mark their own task `DONE`.

The existing `.github/workflows/ci.yml` runs for both `pull_request` events and
pushes to `main`, with read-only repository contents permission.
