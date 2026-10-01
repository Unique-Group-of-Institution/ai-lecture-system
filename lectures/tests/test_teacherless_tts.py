import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from django.test import SimpleTestCase

from lectures.teacherless import NARRATION_HOLD_MS, apply_narration_audio
from lectures.tts import NarrationAudioArtifact, TTSConfigurationError, WindowsSystemSpeechProvider


class _StubProvider:
    key = "stub-provider"

    def synthesize(self, *, scene_id: str, text: str, language: str, output_path: Path) -> NarrationAudioArtifact:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"RIFFstub")
        return NarrationAudioArtifact(
            scene_id=scene_id,
            storage_key=output_path.name,
            duration_ms=3200,
            sha256="0" * 64,
            provider_key=self.key,
            language=language,
        )


def _manifest() -> dict:
    return {
        "narration": {"languageMode": "SOURCE", "ttsProvider": None, "status": "READY_FOR_TTS"},
        "qa": {"estimatedDurationMs": 5000, "estimatedDurationMinutes": 0.08},
        "scenes": [
            {"id": "source-scene-001", "durationMs": 2000, "narration": {"text": "First scene.", "language": "SOURCE"}},
            {"id": "source-scene-002", "durationMs": 3000, "narration": {"text": "Second scene.", "language": "SOURCE"}},
        ],
    }


class TeacherlessTtsTests(SimpleTestCase):
    def test_apply_narration_audio_sets_src_retimes_and_recomputes_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = apply_narration_audio(_manifest(), _StubProvider(), Path(tmp))
            self.assertEqual(manifest["narration"]["ttsProvider"], "stub-provider")
            self.assertEqual(manifest["narration"]["status"], "AUDIO_READY")
            first, second = manifest["scenes"]
            self.assertEqual(first["narrationAudioSrc"], "audio/source-scene-001.wav")
            self.assertEqual(first["narration"]["estimatedDurationMs"], 3200)
            self.assertEqual(first["durationMs"], 3200 + NARRATION_HOLD_MS)
            self.assertGreater(second["durationMs"], 3200)
            self.assertEqual(manifest["qa"]["estimatedDurationMs"], first["durationMs"] + second["durationMs"])
            self.assertTrue((Path(tmp) / "source-scene-001.wav").is_file())

    def test_apply_narration_audio_keeps_scenes_without_narration(self):
        manifest = _manifest()
        del manifest["scenes"][1]["narration"]
        with tempfile.TemporaryDirectory() as tmp:
            result = apply_narration_audio(manifest, _StubProvider(), Path(tmp))
            self.assertNotIn("narrationAudioSrc", result["scenes"][1])
            self.assertEqual(result["scenes"][1]["durationMs"], 3000)

    def test_stub_provider_satisfies_protocol_shape(self):
        provider = _StubProvider()
        self.assertIsInstance(provider.key, str)
        with tempfile.TemporaryDirectory() as tmp:
            artifact = provider.synthesize(scene_id="s", text="t", language="SOURCE", output_path=Path(tmp) / "s.wav")
            self.assertEqual(replace(artifact, sha256="0" * 64).scene_id, "s")


class WindowsSystemSpeechProviderTests(SimpleTestCase):
    def setUp(self):
        if sys.platform != "win32":
            self.skipTest("Windows System.Speech is only available on Windows.")

    def test_synthesize_rejects_empty_inputs(self):
        provider = WindowsSystemSpeechProvider()
        with self.assertRaises(TTSConfigurationError):
            provider.synthesize(scene_id="", text="hello", language="SOURCE", output_path=Path("unused.wav"))
        with self.assertRaises(TTSConfigurationError):
            provider.synthesize(scene_id="s", text="   ", language="SOURCE", output_path=Path("unused.wav"))

    def test_synthesize_produces_valid_wav_artifact(self):
        provider = WindowsSystemSpeechProvider()
        with tempfile.TemporaryDirectory() as tmp:
            artifact = provider.synthesize(
                scene_id="t091-test",
                text="Electric current is measured in amperes.",
                language="SOURCE",
                output_path=Path(tmp) / "t091-test.wav",
            )
        self.assertEqual(artifact.provider_key, "windows-system-speech")
        self.assertGreaterEqual(artifact.duration_ms, 250)
        self.assertEqual(len(artifact.sha256), 64)
