# T050 Local Video Assembly and Review

## Boundary

T050 uses official Remotion `4.0.514` as the primary composition engine only
for the local, non-commercial Phase-1 evaluation. It assembles the exact T040
recording completion, approved T022 slides and canonical narration. It does not
upload, publish, clone a voice, call a paid API, or render in a cloud service.

The evaluation licence basis and exact pins are in
`docs/REMOTION_LOCAL_RENDERING.md`. Production or commercial operation is a
hard stop until licence eligibility is reassessed.

## Immutable inputs, edits and versions

- Each input snapshots the recording completion, approval fingerprint, ordered
  revision, title, claims, narration and hashes, selected take, duration and hash.
- Each draft has a new safe reference, manifest and MP4. Older renders and raw
  recordings are never overwritten or deleted.
- Branding, caption layout and bounded transition/hold timing may create a new
  version.
- Spoken-content removal stores slide, exact canonical transcript excerpt/hash,
  start/end milliseconds and reason. The assigned teacher must approve that
  evidence before a derived render can exist.
- Slide, narration, completion, take, media hash or current-render drift prevents
  review, approval and export.

## Approval flow and exact T030 jobs

1. An admin requests a render from a `RECORDING_READY` bundle.
2. The trusted command moves it to `DRAFT_VIDEO_PENDING` and renders only the
   fixed `LectureAssembly` composition.
3. Admin review submission creates exact `DRAFT_VIDEO_READINESS` input using the
   stored recording reference. The trusted command completes it with the exact
   render reference before `DRAFT_VIDEO_READY`.
4. Only the assigned teacher approves the video or requests revision.
5. Only an admin grants final approval, after teacher approval of that render.
6. Export creates exact `EXPORT_READINESS` input. The trusted command creates the
   package and completes it with the exact package reference before `EXPORT_READY`.

HTTP worker routes stay fail-closed. Browser requests cannot provide worker
identity, paths, commands, codecs, composition IDs, browser flags, FFmpeg paths
or Remotion arguments.

## Windows setup and operation

Install from the tracked lock only:

```powershell
Set-Location remotion
npm ci --ignore-scripts --audit=false --fund=false
node ..\scripts\check_remotion_lock.mjs
npm run versions
npm run browser:ensure
Set-Location ..
```

Apply migrations and start Django with process-only settings:

```powershell
$env:AI_LECTURE_SECRET_KEY = 'replace-with-a-long-local-development-value'
$env:AI_LECTURE_DEPLOYMENT_MODE = 'local-evaluation'
$env:AI_LECTURE_LOCAL_EXECUTION_HOST = '127.0.0.1'
$env:AI_LECTURE_VIDEO_RENDER_ADAPTER = '1'
$env:AI_LECTURE_REMOTION_EVALUATION_ACK = 'evaluation-only-2026-08-20'
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe runserver 127.0.0.1:8000
```

Open `/admin/video-assembly/` or `/teacher/video-review/`. In a second local
PowerShell with the same variables, process bounded work:

```powershell
.\.venv\Scripts\python.exe manage.py process_t050_video --limit 10
```

The command accepts no actor, path, command, composition, codec or capability.
It uses one fixed local worker identity. SQLite stays single-worker; concurrent
operation requires PostgreSQL and a separately approved deployment.

## Local export and recovery

Each versioned ignored export directory contains `lecture.mp4`, editable
`slides.pptx`, Urdu/English `captions.srt`, `metadata.json`, and a SHA-256
`package-manifest.json`. It remains under `data/exports/t050-video`; nothing is
copied to the uploader watch folder and no upload starts.

Back up the database, `data/recordings`, `data/lectures/t050-video` and
`data/exports/t050-video` together while stopped. A failure retains its status,
destination, manifest, partial/failure evidence, raw inputs, and every older
version. An administrator can use the authenticated, CSRF-protected failed-render
recovery endpoint with a bounded reason. Recovery revalidates current workflow
and approval state, slides, narration, selected takes, recording bytes and hashes,
then creates a new immutable version, destination, reference and audit record; it
never changes `FAILED` back to `PENDING`.

Export staging is operation-owned and removed on failure; final directories are
renamed into place only after every file and hash exists. Never promote a `.part`
file manually. Any missing deployment-mode, loopback-host, acknowledgement or
adapter setting disables both render and export worker authority without changing
stored evidence. Railway always fails closed for processing. No cleanup command
deletes source recordings or teacher content.
