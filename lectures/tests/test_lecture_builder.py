from django.test import SimpleTestCase

from lectures.lecture_builder import BuilderSlide, BuilderSource, build_lecture_json


class LectureBuilderTests(SimpleTestCase):
    def test_builds_canonical_grounded_payload(self):
        source = BuilderSource(11, 4, 0, 24, "Evaporation occurs at the surface.")
        payload = build_lecture_json(
            course_class="10",
            subject="Physics",
            unit="10 - Thermal Properties",
            lecture=5,
            title="Evaporation",
            lms_scope="Evaporation - complete topic",
            textbook_pages="13-15",
            introduction="A wet floor dries without boiling.",
            learning_objectives=["Define evaporation.", "Explain surface escape.", "Describe factors."],
            previous_knowledge="Molecules are always moving.",
            slides=(BuilderSlide("Evaporation", (source.text,), (source.text,), (source,)),
                    BuilderSlide("Cooling", ("Energetic molecules escape.",), ("Energetic molecules escape.",), (source,))),
            recap=["Evaporation is a surface process.", "It can cause cooling."],
            review_questions=["Define evaporation.", "Why does wind increase it?"],
        )
        self.assertEqual(payload["metadata"]["subject"], "physics")
        self.assertEqual(payload["slides"][0]["sources"][0]["pageSnapshotId"], 11)
        self.assertEqual(payload["slides"][0]["type"], "concept")

    def test_rejects_too_few_objectives(self):
        with self.assertRaises(ValueError):
            build_lecture_json(
                course_class="10", subject="physics", unit="1", lecture=1, title="Test",
                lms_scope="scope", textbook_pages="1", introduction="Enough introduction.",
                learning_objectives=["Only one"], slides=(), recap=["One", "Two"],
                review_questions=["One", "Two"],
            )
