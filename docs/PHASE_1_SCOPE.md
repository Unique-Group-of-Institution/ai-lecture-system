# Phase-1 Scope

## Goal

Prove one complete lecture workflow for one teacher, one course, one chapter and one lecture without paid AI APIs.

## Included

- Teacher and admin login.
- Teacher selection of class, subject and chapter.
- Local access to authorized textbook and Unique notes content with source-page references.
- Teacher generation guidelines.
- Source-grounded draft slides and one narration script per slide.
- Teacher approval of slides and narration before recording.
- Browser-based slide-by-slide teacher audio recording.
- Immutable raw audio plus derived clean audio.
- Safe technical audio cleanup.
- The approved narration script as the primary caption/transcript source.
- Slide-level retake or correction workflow.
- Editable PPTX generation.
- Slide-level audio/slide synchronization and draft video assembly.
- SRT captions after teacher approval.
- MP4 rendering.
- AI-assisted admin editing and review.
- Teacher review of the assembled video.
- Admin final approval and local YouTube-ready export package.
- Separately gated upload requiring explicit admin approval.

## Deferred

- Voice cloning or synthetic teacher voice.
- Full-recording Whisper transcription in the primary workflow; local Whisper remains optional future QC.
- Further Whisper model and Urdu-script testing.
- Automatic publishing without admin confirmation.
- Advanced character animation or virtual presenters.
- Mobile apps.
- Multi-campus scaling.
- Analytics dashboards.
- Cloud hosting and paid AI APIs.
- All LMS integration, including LMS APIs, uploads and publication. These are future-phase work.

## Publication boundary

Phase 1 prepares a local YouTube-ready package. The AI Lecture System must
generate the final lecture package and record teacher review plus admin final
approval before copying only approved publication files to the existing uploader
watch folder at `F:\Youtube Setup\youtube-uploader\input_folder`. Starting the
upload is a separate privileged action requiring explicit admin approval. The
uploader and its credentials remain outside this project's management boundary.

## Pilot definition of success

- A teacher can select authorized chapter content, guide generation and approve grounded slides/scripts.
- A teacher can record and retake audio slide-by-slide without re-recording the full lecture.
- Slide/audio mismatch can be corrected at slide level.
- Final MP4, PPTX, SRT and metadata package are produced locally.
- Teacher script/slide approval, teacher video review and admin final approval are recorded.
- Only explicitly admin-approved publication files are eligible for uploader handoff.
