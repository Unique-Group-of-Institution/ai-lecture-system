"""Build the canonical, renderer-ready lecture payload from grounded generation evidence.

This module deliberately contains no model writes and no external AI calls. It turns the
already-authorized, immutable generation snapshot into a deterministic educational structure.
Provenance is retained on every teaching slide so the later PPTX adapter cannot invent content.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


SUBJECT_ALIASES = {
    "physics": "physics",
    "phys": "physics",
    "chemistry": "chemistry",
    "chem": "chemistry",
    "biology": "biology",
    "bio": "biology",
    "mathematics": "mathematics",
    "math": "mathematics",
    "computer science": "computer-science",
    "computer-science": "computer-science",
    "computer": "computer-science",
}


@dataclass(frozen=True)
class BuilderSource:
    page_snapshot_id: int
    page_number: int
    start_offset: int
    end_offset: int
    text: str


@dataclass(frozen=True)
class BuilderSlide:
    title: str
    claims: tuple[str, ...]
    narration: tuple[str, ...]
    sources: tuple[BuilderSource, ...]


def _subject(value: str) -> str:
    key = " ".join(value.strip().lower().replace("_", " ").split())
    if key not in SUBJECT_ALIASES:
        raise ValueError(f"Unsupported subject for canonical lecture JSON: {value!r}")
    return SUBJECT_ALIASES[key]


def _clean_lines(items: Iterable[str], maximum: int) -> list[str]:
    result = []
    for item in items:
        text = " ".join(str(item).split())
        if text and text not in result:
            result.append(text[:maximum])
    return result


def _source_dict(source: BuilderSource) -> dict:
    return {
        "pageSnapshotId": source.page_snapshot_id,
        "pageNumber": source.page_number,
        "startOffset": source.start_offset,
        "endOffset": source.end_offset,
        "text": source.text,
    }


def build_lecture_json(*, course_class: str, subject: str, unit: str, lecture: int,
                       title: str, lms_scope: str, textbook_pages: str,
                       introduction: str, learning_objectives: Iterable[str],
                       previous_knowledge: str | None,
                       slides: Iterable[BuilderSlide], recap: Iterable[str],
                       review_questions: Iterable[str], next_lecture_bridge: str | None = None) -> dict:
    """Return the canonical Lecture JSON object consumed by the Node slide engine."""
    canonical_slides = []
    for slide in slides:
        claims = _clean_lines(slide.claims, 500)
        if not claims:
            raise ValueError("Every teaching slide must contain at least one grounded claim.")
        sources = [_source_dict(source) for source in slide.sources]
        if not sources:
            raise ValueError("Every teaching slide must contain provenance.")
        canonical_slides.append({
            "type": "concept",
            "title": slide.title.strip()[:200],
            "lead": claims[0],
            "bullets": claims[1:8] or claims[:1],
            "narration": " ".join(_clean_lines(slide.narration, 2500))[:2500],
            "sources": sources,
        })

    slos = _clean_lines(learning_objectives, 500)
    if not 3 <= len(slos) <= 6:
        raise ValueError("Canonical lecture JSON requires 3-6 learning objectives.")
    if len(canonical_slides) < 2:
        raise ValueError("Canonical lecture JSON requires at least two teaching slides.")

    payload = {
        "metadata": {
            "class": str(course_class).strip(),
            "subject": _subject(subject),
            "unit": str(unit).strip(),
            "lecture": int(lecture),
            "title": str(title).strip(),
            "lmsScope": str(lms_scope).strip(),
            "textbookPages": str(textbook_pages).strip(),
        },
        "introduction": " ".join(str(introduction).split())[:2000],
        "slos": slos,
        "slides": canonical_slides,
        "recap": _clean_lines(recap, 500),
        "reviewQuestions": _clean_lines(review_questions, 500),
    }
    if previous_knowledge:
        payload["previousKnowledge"] = " ".join(str(previous_knowledge).split())[:1500]
    if next_lecture_bridge:
        payload["nextLectureBridge"] = " ".join(str(next_lecture_bridge).split())[:1000]
    return payload
