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
