# Phase-1 Architecture

## Corrected production workflow

```mermaid
flowchart TD
    A["Syllabus and lecture request"] --> B["AI scene script and draft slides"]
    B --> C{"Teacher approves scenes?"}
    C -- No --> B
    C -- Yes --> D["Teacher records audio per scene"]
    D --> E["Local Whisper transcript and audio QC"]
    E --> F{"Teacher approves audio?"}
    F -- Patch or retake --> D
    F -- Yes --> G["Final timing, PPTX, captions and MP4"]
    G --> H{"Admin final approval"}
    H -- Revise scene --> B
    H -- Approve --> I["Local LMS and YouTube watch folders"]
```

## Components

| Component | Phase-1 responsibility |
|---|---|
| Teacher portal | Lecture request, scene approval, scene recording, transcript review and corrections |
| Admin portal | Course/syllabus setup, quality review, render control and export approval |
| Application database | Users, courses, chapters, requests, versions, scenes, audio assets and approvals |
| Agent workspace | Shared tasks, decisions, handoffs and safe AI-development workflow |
| Custom MCP server | Controlled tools for project state first; lecture-domain tools are added incrementally |
| Slide engine | Scene JSON to editable PPTX and preview images |
| Audio engine | Format conversion, mild cleanup, Whisper transcript, QC flags and patch assembly |
| Render engine | Slide images, approved scene audio, captions and FFmpeg video composition |
| Distribution | Local output package and watched folders; no automatic publication without approval |

## Trust boundaries

1. Raw syllabus and teacher audio remain local.
2. AI-generated scripts and slides are drafts until teacher approval.
3. Transcript flags are suggestions until teacher approval.
4. Audio cuts cannot alter meaning without an approved correction record.
5. Final export requires admin approval.
6. External publication is a separate privileged operation.

## Shared-agent architecture

Claude Code and Codex do not rely on each other's chat history. They coordinate through:

- Git-tracked project instructions;
- `tasks/tasks.json` state and history;
- architecture decisions;
- status and handoff documents;
- the project MCP server;
- separate task ownership and later separate Git branches/worktrees.

