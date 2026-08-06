from __future__ import annotations

import json
import io
import sys
import tempfile
import unittest
import wave
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

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
from scripts.benchmark_audio import main as benchmark_main


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
        with self.assertRaisesRegex(AudioQCError, "outside approved"):
            validate_output_root(self.repo / "public", self.repo)

    def test_refuses_source_overwrite_and_output_escape(self) -> None:
        private_component = self.root.name
        with self.assertRaises(AudioQCError) as collision:
            validate_source_and_outputs(self.source, [self.source], self.output)
        self.assertNotIn(private_component, str(collision.exception))
        self.assertNotIn(self.source.name, str(collision.exception))
        self.assertIn("<authorized-local-input>", str(collision.exception))

        with self.assertRaises(AudioQCError) as escape:
            validate_source_and_outputs(self.source, [self.root / "elsewhere.json"], self.output)
        self.assertNotIn(private_component, str(escape.exception))
        self.assertNotIn("elsewhere.json", str(escape.exception))

    def test_refuses_existing_output(self) -> None:
        existing = self.output / "result.json"
        existing.write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(AudioQCError, "overwrite an existing"):
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
        private_component = self.root.name
        missing = self.root / "private-teacher-folder" / "missing.exe"
        with self.assertRaises(AudioQCError) as error:
            require_file(missing, "whisper-cli executable")
        message = str(error.exception)
        self.assertNotIn(private_component, message)
        self.assertNotIn("private-teacher-folder", message)
        self.assertNotIn("missing.exe", message)

    def test_cli_missing_input_error_does_not_print_private_path(self) -> None:
        executable = self.root / "whisper-cli.exe"
        model = self.root / "model.bin"
        executable.write_bytes(b"synthetic")
        model.write_bytes(b"synthetic")
        private_input = self.root / "private-teacher-folder" / "recording.m4a"
        stderr = io.StringIO()
        argv = [
            "benchmark_audio.py",
            "--input",
            str(private_input),
            "--output-dir",
            str(Path(__file__).resolve().parents[1] / "data" / "lectures" / "synthetic-test"),
            "--whisper-cli",
            str(executable),
            "--model",
            str(model),
        ]
        with patch.object(sys, "argv", argv), redirect_stderr(stderr):
            self.assertEqual(benchmark_main(), 2)
        error = stderr.getvalue()
        self.assertNotIn("private-teacher-folder", error)
        self.assertNotIn("recording.m4a", error)
        self.assertNotIn(str(private_input), error)

    def test_cli_argument_error_does_not_echo_private_argument(self) -> None:
        private_argument = str(self.root / "private-teacher-folder" / "recording.m4a")
        stderr = io.StringIO()
        with patch.object(sys, "argv", ["benchmark_audio.py", "--unknown", private_argument]):
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as exit_error:
                benchmark_main()
        self.assertEqual(exit_error.exception.code, 2)
        error = stderr.getvalue()
        self.assertNotIn("private-teacher-folder", error)
        self.assertNotIn("recording.m4a", error)
        self.assertNotIn(private_argument, error)


if __name__ == "__main__":
    unittest.main()
