#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_workspace.audio_qc import (  # noqa: E402
    AudioQCError,
    parse_whisper_json,
    require_file,
    run_private_process,
    technical_flags,
    validate_output_root,
    validate_source_and_outputs,
    wav_metrics,
    write_private_qc,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a private local Whisper/audio-QC benchmark")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--whisper-cli", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()

    try:
        output = validate_output_root(args.output_dir, ROOT)
        executable = require_file(args.whisper_cli, "whisper-cli executable")
        model = require_file(args.model, "Whisper model")
        prefix = output / "transcript"
        artifacts = [
            prefix.with_suffix(".txt"),
            prefix.with_suffix(".json"),
            prefix.with_suffix(".srt"),
            output / "whisper.stdout.log",
            output / "whisper.stderr.log",
            output / "technical-qc.json",
            output / "benchmark-summary.json",
        ]
        source, _ = validate_source_and_outputs(args.input, artifacts, output)
        output.mkdir(parents=True, exist_ok=True)
        before = (source.stat().st_size, source.stat().st_mtime_ns)
        metrics = run_private_process(
            [
                str(executable),
                "-m",
                str(model),
                "-f",
                str(source),
                "-l",
                "auto",
                "-t",
                str(args.threads),
                "-otxt",
                "-ojf",
                "-osrt",
                "-of",
                str(prefix),
            ],
            output / "whisper.stdout.log",
            output / "whisper.stderr.log",
        )
        if metrics["exit_code"] != 0:
            raise AudioQCError("Whisper failed; inspect the private local stderr log")
        after = (source.stat().st_size, source.stat().st_mtime_ns)
        if before != after:
            raise AudioQCError("Input integrity changed during processing")
        duration, rms_dbfs, clipped = wav_metrics(source)
        language, segments = parse_whisper_json(prefix.with_suffix(".json"))
        flags = technical_flags(
            segments,
            duration,
            overall_rms_dbfs=rms_dbfs,
            clipped_samples=clipped,
        )
        write_private_qc(
            output / "technical-qc.json",
            language=language,
            duration=duration,
            segments=segments,
            flags=flags,
            rms_dbfs=rms_dbfs,
            clipped_samples=clipped,
        )
        summary = {
            **metrics,
            "audio_duration_seconds": duration,
            "real_time_factor": metrics["runtime_seconds"] / duration,
            "language_code": language,
            "segment_count": len(segments),
            "qc_flag_count": len(flags),
            "source_integrity_unchanged": True,
        }
        (output / "benchmark-summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        print("Local benchmark completed; private artifacts remain in the requested output directory.")
        return 0
    except AudioQCError as exc:
        print(f"Benchmark refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
