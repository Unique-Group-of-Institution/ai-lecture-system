from django.test import SimpleTestCase

from lectures.teacherless import _estimate_duration_ms, _scene_kind, manifest_to_srt


class TeacherlessFoundationTests(SimpleTestCase):
    def test_teacherless_duration_is_word_based_and_bounded(self):
        self.assertGreaterEqual(_estimate_duration_ms("one two three"), 2000)
        self.assertGreaterEqual(_estimate_duration_ms(""), 2000)

    def test_teacherless_scene_kind_is_deterministic(self):
        self.assertEqual(_scene_kind("Ohm's law formula", "I = V / R"), "formula")
        self.assertEqual(_scene_kind("Circuit diagram", "battery and wire"), "diagram")
        self.assertEqual(_scene_kind("Numerical example", "calculate the current"), "workedExample")
        self.assertEqual(_scene_kind("Recap", "key points"), "recap")
        self.assertEqual(_scene_kind("Definition", "electric current is charge flow"), "concept")

    def test_teacherless_srt_has_monotonic_scene_ranges(self):
        manifest = {
            "scenes": [
                {"durationMs": 2000, "narration": {"text": "First scene."}},
                {"durationMs": 3000, "narration": {"text": "Second scene."}},
            ]
        }
        srt = manifest_to_srt(manifest)
        self.assertIn("00:00:00,000 --> 00:00:02,000", srt)
        self.assertIn("00:00:02,000 --> 00:00:05,000", srt)
        self.assertIn("First scene.", srt)
        self.assertIn("Second scene.", srt)
