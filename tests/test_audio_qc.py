from __future__ import annotations

import json
import tempfile
import unittest
import wave
from pathlib import Path

from agent_workspace.audio_qc import (
    AudioQCError,
    SegmentMetric,
    parse_whisper_json,
    require_file,
    technical_flags,
    validate_output_root,
    validate_segments,
    validate_source_and_outputs,
    wav_metrics,
    write_private_qc,
)


class AudioQCTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.output = self.repo / "data" / "lectures" / "t020-local" / "run"
        self.output.mkdir(parents=True)
        self.source = self.root / "authorized.wav"
        with wave.open(str(self.source), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16_000)
            stream.writeframes(b"\x00\x00" * 32_000)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_output_root_must_be_in_ignored_lecture_tree(self) -> None:
        self.assertEqual(validate_output_root(self.output, self.repo), self.output.resolve())
        with self.assertRaisesRegex(AudioQCError, "Output must be below"):
            validate_output_root(self.repo / "public", self.repo)

    def test_refuses_source_overwrite_and_output_escape(self) -> None:
        with self.assertRaisesRegex(AudioQCError, "overwrite the source"):
            validate_source_and_outputs(self.source, [self.source], self.output)
        with self.assertRaisesRegex(AudioQCError, "escapes"):
            validate_source_and_outputs(self.source, [self.root / "elsewhere.json"], self.output)

    def test_refuses_existing_output(self) -> None:
        existing = self.output / "result.json"
        existing.write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(AudioQCError, "overwrite existing"):
            validate_source_and_outputs(self.source, [existing], self.output)

    def test_timestamp_ordering(self) -> None:
        ordered = [SegmentMetric(0, 1), SegmentMetric(1.1, 2)]
        self.assertEqual(validate_segments(ordered, 2), (True, True))
        overlap = [SegmentMetric(0, 1.5), SegmentMetric(1, 2)]
        self.assertEqual(validate_segments(overlap, 2), (False, True))

    def test_unicode_urdu_english_json_is_parsed_without_loss(self) -> None:
        path = self.output / "unicode.json"
        payload = {
            "result": {"language": "ur"},
            "transcription": [
                {
                    "offsets": {"from": 0, "to": 1000},
                    "text": "طبیعیات physics",
                    "tokens": [{"text": "طبیعیات", "p": 0.9}],
                }
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        language, segments = parse_whisper_json(path)
        self.assertEqual(language, "ur")
        self.assertAlmostEqual(segments[0].confidence or 0, 0.9)

    def test_qc_flag_generation_contains_no_transcript(self) -> None:
        segments = [SegmentMetric(4, 5, 0.2), SegmentMetric(4.5, 6, 0.9)]
        flags = technical_flags(segments, 10, overall_rms_dbfs=-40, clipped_samples=2)
        categories = {flag.category for flag in flags}
        self.assertTrue(
            {
                "long_transcript_gap",
                "low_confidence_segment",
                "timestamp_discontinuity",
                "unusually_low_volume",
                "possible_clipping",
            }.issubset(categories)
        )
        qc_path = self.output / "qc.json"
        write_private_qc(
            qc_path,
            language="ur",
            duration=10,
            segments=segments,
            flags=flags,
            rms_dbfs=-40,
            clipped_samples=2,
        )
        self.assertNotIn("text", qc_path.read_text(encoding="utf-8"))

    def test_synthetic_wav_metrics(self) -> None:
        duration, rms_dbfs, clipped = wav_metrics(self.source)
        self.assertEqual(duration, 2.0)
        self.assertEqual(rms_dbfs, -120.0)
        self.assertEqual(clipped, 0)

    def test_missing_dependencies_fail_safely(self) -> None:
        with self.assertRaisesRegex(AudioQCError, "Missing whisper-cli"):
            require_file(self.root / "missing.exe", "whisper-cli executable")


if __name__ == "__main__":
    unittest.main()
