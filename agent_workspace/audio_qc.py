from __future__ import annotations

import json
import math
import struct
import subprocess
import threading
import time
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


class AudioQCError(RuntimeError):
    """Raised when a benchmark would violate a safety or integrity rule."""


@dataclass(frozen=True)
class SegmentMetric:
    start_seconds: float
    end_seconds: float
    confidence: float | None = None


@dataclass(frozen=True)
class QCFlag:
    category: str
    start_seconds: float
    end_seconds: float
    metric: float | int | None = None


def resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def require_file(path: str | Path, label: str) -> Path:
    candidate = resolved(path)
    if not candidate.is_file():
        raise AudioQCError(f"Missing {label}: {candidate}")
    return candidate


def validate_output_root(output_dir: str | Path, repository_root: str | Path) -> Path:
    output = resolved(output_dir)
    allowed = resolved(repository_root) / "data" / "lectures"
    if output == allowed or allowed not in output.parents:
        raise AudioQCError(f"Output must be below the ignored local root: {allowed}")
    return output


def validate_source_and_outputs(
    source: str | Path, outputs: Sequence[str | Path], output_root: str | Path
) -> tuple[Path, list[Path]]:
    source_path = require_file(source, "audio input")
    root = resolved(output_root)
    checked: list[Path] = []
    for output in outputs:
        target = resolved(output)
        if target == source_path:
            raise AudioQCError("Refusing to overwrite the source recording")
        if root != target and root not in target.parents:
            raise AudioQCError(f"Output escapes the approved local directory: {target}")
        if target.exists():
            raise AudioQCError(f"Refusing to overwrite existing artifact: {target}")
        checked.append(target)
    return source_path, checked


def validate_segments(segments: Sequence[SegmentMetric], duration: float) -> tuple[bool, bool]:
    ordered = True
    valid = duration > 0
    previous_end = 0.0
    for segment in segments:
        if segment.start_seconds < previous_end - 0.05:
            ordered = False
        if (
            segment.start_seconds < 0
            or segment.end_seconds < segment.start_seconds
            or segment.end_seconds > duration + 0.1
        ):
            valid = False
        previous_end = max(previous_end, segment.end_seconds)
    return ordered, valid


def technical_flags(
    segments: Sequence[SegmentMetric],
    duration: float,
    *,
    overall_rms_dbfs: float | None = None,
    clipped_samples: int = 0,
) -> list[QCFlag]:
    flags: list[QCFlag] = []
    previous_end = 0.0
    for segment in segments:
        if segment.start_seconds < previous_end - 0.05 or segment.end_seconds < segment.start_seconds:
            flags.append(
                QCFlag("timestamp_discontinuity", segment.start_seconds, segment.end_seconds)
            )
        gap = segment.start_seconds - previous_end
        if gap >= 3.0:
            flags.append(QCFlag("long_transcript_gap", previous_end, segment.start_seconds, gap))
        if segment.confidence is not None and segment.confidence < 0.5:
            flags.append(
                QCFlag(
                    "low_confidence_segment",
                    segment.start_seconds,
                    segment.end_seconds,
                    segment.confidence,
                )
            )
        previous_end = max(previous_end, segment.end_seconds)
    if duration - previous_end >= 3.0:
        flags.append(QCFlag("long_transcript_gap", previous_end, duration, duration - previous_end))
    if overall_rms_dbfs is not None and overall_rms_dbfs < -35.0:
        flags.append(QCFlag("unusually_low_volume", 0.0, duration, overall_rms_dbfs))
    if clipped_samples:
        flags.append(QCFlag("possible_clipping", 0.0, duration, clipped_samples))
    return flags


def parse_whisper_json(path: str | Path) -> tuple[str | None, list[SegmentMetric]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    language = payload.get("result", {}).get("language")
    segments: list[SegmentMetric] = []
    for item in payload.get("transcription", []):
        probabilities = [
            float(token["p"])
            for token in item.get("tokens", [])
            if isinstance(token.get("p"), (int, float)) and 0 <= float(token["p"]) <= 1
        ]
        confidence = sum(probabilities) / len(probabilities) if probabilities else None
        offsets = item.get("offsets", {})
        segments.append(
            SegmentMetric(
                start_seconds=float(offsets["from"]) / 1000.0,
                end_seconds=float(offsets["to"]) / 1000.0,
                confidence=confidence,
            )
        )
    return language, segments


def wav_metrics(path: str | Path) -> tuple[float, float, int]:
    total_squares = 0.0
    total_samples = 0
    clipped = 0
    with wave.open(str(path), "rb") as stream:
        if stream.getnchannels() != 1 or stream.getsampwidth() != 2:
            raise AudioQCError("QC requires mono signed 16-bit PCM")
        duration = stream.getnframes() / stream.getframerate()
        while frames := stream.readframes(65_536):
            count = len(frames) // 2
            samples = struct.unpack(f"<{count}h", frames)
            total_squares += sum(float(value) * value for value in samples)
            clipped += sum(1 for value in samples if abs(value) >= 32_760)
            total_samples += count
    rms = math.sqrt(total_squares / total_samples) if total_samples else 0.0
    dbfs = 20 * math.log10(rms / 32_768.0) if rms else -120.0
    return duration, dbfs, clipped


def write_private_qc(
    path: str | Path,
    *,
    language: str | None,
    duration: float,
    segments: Sequence[SegmentMetric],
    flags: Sequence[QCFlag],
    rms_dbfs: float,
    clipped_samples: int,
) -> None:
    ordered, valid = validate_segments(segments, duration)
    category_counts: dict[str, int] = {}
    for flag in flags:
        category_counts[flag.category] = category_counts.get(flag.category, 0) + 1
    payload = {
        "schema_version": 1,
        "language_code": language,
        "audio_duration_seconds": duration,
        "segment_count": len(segments),
        "timestamps_ordered": ordered,
        "timestamps_valid": valid,
        "aggregate": {
            "overall_rms_dbfs": rms_dbfs,
            "clipped_sample_count": clipped_samples,
            "flag_count": len(flags),
            "category_counts": category_counts,
        },
        "flags": [asdict(flag) for flag in flags],
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_private_process(command: Sequence[str], stdout_path: Path, stderr_path: Path) -> dict[str, Any]:
    """Run a local command without allowing its output into the caller's terminal."""
    start = time.perf_counter()
    with stdout_path.open("x", encoding="utf-8") as stdout, stderr_path.open(
        "x", encoding="utf-8"
    ) as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, text=True)
        peak = 0
        stop = threading.Event()

        def sample_memory() -> None:
            nonlocal peak
            try:
                import ctypes

                class Counters(ctypes.Structure):
                    _fields_ = [
                        ("cb", ctypes.c_ulong),
                        ("PageFaultCount", ctypes.c_ulong),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t),
                    ]

                while not stop.wait(0.25):
                    counters = Counters()
                    counters.cb = ctypes.sizeof(counters)
                    if ctypes.windll.psapi.GetProcessMemoryInfo(
                        int(process._handle), ctypes.byref(counters), counters.cb
                    ):
                        peak = max(peak, int(counters.PeakWorkingSetSize))
            except (AttributeError, ImportError, OSError):
                return

        monitor = threading.Thread(target=sample_memory, daemon=True)
        monitor.start()
        return_code = process.wait()
        stop.set()
        monitor.join(timeout=1)
    return {
        "exit_code": return_code,
        "runtime_seconds": time.perf_counter() - start,
        "peak_working_set_bytes": peak or None,
    }
