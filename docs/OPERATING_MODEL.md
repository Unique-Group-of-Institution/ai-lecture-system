# Human + Agent Operating Model

## Responsibility split

| Actor | Owns |
|---|---|
| Product owner | Priority, institutional policy, teacher content and final approval |
| Implementing agent | One claimed task, code, tests, docs and handoff |
| Reviewing agent | Acceptance criteria, risk review, regression checks and review verdict |
| MCP server | Controlled project and lecture operations with structured results |
| Git repository | Durable source of truth and history |

## Task lifecycle

`BACKLOG → READY → IN_PROGRESS → REVIEW → DONE`

Exceptional state: `BLOCKED`.

Rules:

- Only READY tasks can be claimed.
- Dependencies must be DONE before a task becomes claimable.
- An implementing agent cannot mark its own task DONE.
- Every status change records actor, timestamp and note.

## Daily human workflow

1. Open `dashboard/index.html` in Edge.
2. Review current READY, IN_PROGRESS and REVIEW tasks.
3. Tell one agent to take the next READY task.
4. Review only decisions or approval gates raised by the agent.
5. Ask the second agent to review the completed task.
6. Approve DONE or return it to IN_PROGRESS with a note.

## Agent handoff requirement

After material work, update `handoffs/LATEST.md` with:

- task ID and owner;
- files changed;
- checks run;
- unresolved risks;
- exact recommended next action.

