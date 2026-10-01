# Teacherless Lecture Pipeline

The teacherless path is additive. It does not replace or alter the existing teacher-recording pipeline.

## Boundaries

- Existing `LectureProps` / `LectureAssembly` continue to consume approved slide revisions and teacher recordings.
- The new `TeacherlessLectureProps` contract consumes a scene manifest and optional scene audio references.
- A scene manifest is deterministic presentation data: concept text, formulas, diagrams, callouts and frame-driven animation instructions.
- No `RecordingTake`, `RecordingCompletion`, teacher recording approval, or voice-clone record is required by this renderer.
- Source grounding, narration generation and text-to-speech are upstream concerns and will later produce this manifest/audio; this task deliberately does not add an AI provider or external upload.

## Scene contract

Each scene has a stable ID, educational kind, duration, title, elements and animations. IDs are unique within a lecture. Durations are frame-quantized from milliseconds at 30 fps.

Supported deterministic animations are `fadeIn`, `draw`, `highlight` and `stepReveal`. The foundation validates animation payloads before rendering. Unsupported animation types, duplicate/invalid IDs and non-positive/too-short durations fail closed.

## Verification fixture

`remotion/src/teacherlessSmokeProps.ts` contains synthetic-only content. It is not an institutional lecture and must not be used as production source material.

The next implementation layer can map approved source-grounded lecture content to this contract and attach generated narration audio without introducing a dependency on teacher recordings.

## Current compiler path

The Django compiler in `lectures/teacherless.py` converts an approved `GenerationRequest` into a Remotion-ready manifest. It reuses the immutable source-grounded narration and provenance already stored by the existing generation service.

```
Approved Generation
  -> approved SlideRevision
  -> canonical narration + SourceReference
  -> Teacherless manifest v1
  -> Remotion TeacherlessLecture
  -> MP4
```

The compiler is deliberately deterministic. It does not translate, paraphrase, invent facts, call an AI provider, or fetch web content. Its narration field is therefore marked `SOURCE` and `READY_FOR_TTS`.

The same manifest produces an SRT using the scene timeline. Estimated timing is only a planning/render fixture until actual TTS audio is attached; production audio duration must replace the estimate before final synchronization.

## Production gates

1. Source rights and extraction review must pass.
2. Source-grounded generation must be approved.
3. Teacherless compiler creates the manifest and provenance map.
4. A future TTS adapter creates narration audio and returns exact duration.
5. Visual planning replaces any `Source diagram / visual asset required` placeholders with deterministic diagrams or approved visual assets.
6. Remotion renders the teacherless lecture.
7. Final QA verifies audio/video duration, captions, provenance, scene coverage and branding.
8. UGI intro/outro assets are inserted only when the authorized physical assets are configured; no placeholder is treated as the official intro/outro.

This separation keeps source truth, narration generation, voice generation and rendering independently testable.
