from pathlib import Path
from unittest.mock import patch
import tempfile
import zipfile

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from lectures.slide_engine import _contained, _validate_pptx


class SlideEngineSafetyTests(SimpleTestCase):
    def test_containment_rejects_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            root.mkdir()
            with self.assertRaises(ValidationError):
                _contained(root / ".." / "outside", root)

    def test_pptx_validation_accepts_minimal_package(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deck.pptx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("[Content_Types].xml", "<Types></Types>")
                archive.writestr("ppt/presentation.xml", "<p:presentation></p:presentation>")
            with override_settings(SLIDE_ENGINE_MAX_PPTX_BYTES=1024 * 1024):
                _validate_pptx(path)

    def test_pptx_validation_rejects_non_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deck.pptx"
            path.write_bytes(b"not-a-pptx")
            with self.assertRaises(Exception):
                _validate_pptx(path)
