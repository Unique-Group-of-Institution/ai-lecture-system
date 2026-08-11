"""Pure subprocess targets for bounded local content inspection.

This module deliberately has no Django imports so Windows ``spawn`` workers can
load it without initializing the application registry.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from pypdf import PdfReader


def pdf_inspection_worker(pdf_path: str, response_path: str, limits: dict[str, float | int]) -> None:
    response: dict[str, object]
    try:
        reader = PdfReader(pdf_path, strict=True)
        page_count = len(reader.pages)
        if not 1 <= page_count <= limits["max_pages"]:
            raise ValueError("page count")
        dimensions = []
        for page in reader.pages:
            width, height = float(page.mediabox.width), float(page.mediabox.height)
            if (
                not math.isfinite(width)
                or not math.isfinite(height)
                or width <= 0
                or height <= 0
                or width > limits["max_width"]
                or height > limits["max_height"]
            ):
                raise ValueError("page dimensions")
            pixels = int(width * limits["render_scale"] / 72) * int(height * limits["render_scale"] / 72)
            if pixels > limits["max_pixels"]:
                raise ValueError("render pixels")
            dimensions.append([width, height])
        response = {"ok": True, "page_count": page_count, "dimensions": dimensions}
    except Exception:
        response = {"ok": False}
    Path(response_path).write_text(json.dumps(response, separators=(",", ":")), encoding="utf-8")


def render_worker(pdf_path: str, page_index: int, scale: float, output_path: str) -> None:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(pdf_path)
    document[page_index].render(scale=scale).to_pil().save(output_path, format="PNG")


def pdf_text_worker(pdf_path: str, output_dir: str, max_page_bytes: int) -> None:
    reader = PdfReader(pdf_path, strict=True)
    target = Path(output_dir)
    for index, page in enumerate(reader.pages, start=1):
        encoded = (page.extract_text() or "").strip().encode("utf-8")
        if len(encoded) > max_page_bytes:
            raise RuntimeError("PDF page text exceeds safe output limit.")
        (target / f"native-{index:04d}.txt").write_bytes(encoded)
