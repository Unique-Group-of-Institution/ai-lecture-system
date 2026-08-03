# Admin PC and Publication System Profile

Captured for Task T002 on 2026-08-03. Automated fields were verified with
`python scripts/system_probe.py`; hardware and workflow fields were verified by
the product owner.

## Computer

- Operating system and edition: Windows 10
- Windows version/build: 10.0.19045 (build 19045)
- Processor model: Intel Core i5-6500 at 3.20 GHz
- RAM: 8 GB
- GPU model: AMD Radeon HD 5450 and Intel HD Graphics 530
- GPU VRAM: Approximately 1 GB shared graphics memory
- Free storage: Approximately 68.3 GiB (73,340,895,232 bytes) on the workspace drive at probe time
- Preferred project drive/folder: `E:\LMS Project\AI-Lecture-System-Agent-Workspace`
- Internet reliability: Stable

## Installed tools

- Python version: 3.14.5 (64-bit)
- Git version: 2.54.0.windows.1
- FFmpeg version: Not installed
- LibreOffice version: Not installed
- Node.js version: v24.16.0
- Claude Code installed: Yes; version 2.1.185, but unavailable for project use while the account is on the free plan
- Codex CLI installed: Yes; version 0.146.0 and authenticated through ChatGPT

## LMS

- LMS name: Not selected; LMS integration is deferred beyond Phase 1
- LMS version: Not applicable in Phase 1
- Hosted locally or online: Not applicable in Phase 1
- Admin access available: Not required in Phase 1
- API documentation available: Not required in Phase 1
- Supported video upload method: Deferred to a future phase
- Course/chapter identifiers available: Not required for a Phase-1 LMS integration

## YouTube workflow

- Channel ownership confirmed: Not recorded by T002; publication remains admin-approved
- Existing uploader/software: `F:\Youtube Setup\youtube-uploader`
- Current watch-folder path: `F:\Youtube Setup\youtube-uploader\input_folder`
- Handoff rule: Generate and approve the final lecture package locally first, then copy only approved publication files into the watch folder
- Metadata format required: To be confirmed when the publication-package contract is implemented
- Credential boundary: Do not inspect, print, modify, copy, or expose `.env`, `token.json`, or other uploader credentials

## Approval

- Completed by: codex, from product-owner-supplied details and local probe evidence
- Date: 2026-08-03
- Reviewed by: Pending human or independent-agent review of T002
