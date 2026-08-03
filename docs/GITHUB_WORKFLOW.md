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

1. Create a short-lived branch from `main` for one claimed task.
2. Make only task-scoped changes and run workspace validation and all tests.
3. Push the branch and open a pull request into `main`.
4. Wait for the `workspace-ci` pull-request check to pass.
5. Have the human product owner or an independent agent review the task and
   move it from `REVIEW` to `DONE` when accepted.
6. Merge without force-pushing and delete only the short-lived branch.

Protection of `main` from force pushes and deletion is required but not yet
active. On 2026-08-03 GitHub rejected the protection request with HTTP 403,
stating that GitHub Pro is required unless the repository is made public. The
repository must remain private, so T003 is blocked pending a plan that supports
private-repository branch protection. Required approving reviews should remain
off while there is only one GitHub operator, because GitHub does not allow an
author to approve their own pull request. This does not relax the project rule
that an implementer cannot mark their own task `DONE`.

The existing `.github/workflows/ci.yml` runs for both `pull_request` events and
pushes to `main`, with read-only repository contents permission.
