# Teacher Recording Portal (T040)

## Scope and safety boundary

T040 is the local teacher portal for reviewing the current approved slides and canonical
narration, recording one browser-audio take per slide, choosing a take, and marking the
recording bundle complete. It does not assemble or render video, export files, clone a voice,
connect to CRM, or upload to YouTube.

Only the assigned course teacher can list or open a recording workflow, submit takes, select
a take, play its media, or complete the bundle. Recording cannot begin until the exact current
T022 slide and narration revisions have teacher approval. Any later slide revision invalidates
that approval and makes earlier takes historical rather than eligible for completion.

## Windows setup

From PowerShell in the repository root, use the existing virtual environment and a
process-only development secret:

```powershell
$env:AI_LECTURE_SECRET_KEY = 'replace-with-a-long-local-development-value'
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/teacher/recordings/` in a current Edge, Chrome, Firefox, or
Safari browser and sign in with the teacher's local institutional Django account. Localhost is
treated as a secure browser context; a non-local HTTP hostname may prevent microphone access.
The user must grant microphone permission in the browser.

The administrator prepares course assignments, approved slide/narration revisions, and the
workflow state through the separately governed T010, T022, and T030 boundaries. Administrators
cannot record or substitute the teacher's approval through this portal.

## Recording workflow

1. Choose the assigned class, subject, course, and chapter.
2. Review every displayed approved slide and canonical narration.
3. Select **Begin slide recording** to enter `RECORDING_PENDING`.
4. Record and stop one slide at a time. The stopped browser blob is sent only to this local
   Django server.
5. Record a retake when needed. Each accepted take receives a new number and file; it never
   overwrites an earlier raw take.
6. Play back the locally stored takes and select the intended take for each slide.
7. Select **Mark recording complete**. Completion succeeds only if every current approved
   slide has a selected take created by the assigned teacher.

If an upload fails, the browser tab retains that captured blob for **Retry upload**. Do not
close or reload the tab until the retry succeeds or the teacher intentionally records again.
A failed or interrupted server write removes its operation-owned staging and promoted files;
an accepted raw take is never deleted by the portal.

## Local storage and limits

Accepted media stays under the ignored directory `data\recordings` by default. Database rows
store a generated relative storage key, media metadata, duration, SHA-256 digest, teacher,
slide revision, and canonical narration snapshot. The media endpoint requires an authenticated,
assigned teacher and returns private, non-cacheable content.

Defaults can be changed for a local installation with these process environment variables:

```powershell
$env:AI_LECTURE_RECORDING_ROOT = 'E:\private-ai-lecture-data\recordings'
$env:AI_LECTURE_RECORDING_MAX_BYTES = '26214400'
$env:AI_LECTURE_RECORDING_MIN_DURATION_MS = '250'
$env:AI_LECTURE_RECORDING_MAX_DURATION_MS = '1200000'
```

Keep any custom root on local, access-controlled storage. Never place it in a synchronized or
public folder. Back up the Django database and the complete recording root together while the
application is stopped; either one alone is not a valid recovery set. Do not rename, edit, or
delete raw take files manually. No cleanup command is provided because source recordings must
be preserved.

Accepted browser containers are WebM/Opus, Ogg/Opus, MP4/M4A, and WAV when the declared media
type, safe filename extension, bounded size, and container signature agree. The default upload
limit is 25 MiB and the default duration range is 250 milliseconds through 20 minutes per take.

## Windows verification

Use synthetic fixtures only. The focused and complete commands are:

```powershell
$env:AI_LECTURE_SECRET_KEY = 'synthetic-process-only-test-key'
.\.venv\Scripts\python.exe manage.py test lectures.test_recording -v 2
.\.venv\Scripts\python.exe manage.py test -v 2
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe scripts\check_workspace.py
```

Some managed Windows sandboxes deny access to directories created by Python's
`TemporaryDirectory`. In that environment, run the complete synthetic suite in an approved
unsandboxed local process. Do not weaken ACLs or delete inaccessible temp trees to make a test
pass.
