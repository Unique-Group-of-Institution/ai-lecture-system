from __future__ import annotations

import base64
import hashlib
import os
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class NarrationAudioArtifact:
    scene_id: str
    storage_key: str
    duration_ms: int
    sha256: str
    provider_key: str
    language: str


class TeacherlessTTSProvider(Protocol):
    key: str

    def synthesize(
        self,
        *,
        scene_id: str,
        text: str,
        language: str,
        output_path: Path,
    ) -> NarrationAudioArtifact:
        """Create one immutable local audio artifact for a teacherless scene."""
        ...


class TTSConfigurationError(RuntimeError):
    pass


def validate_audio_artifact(artifact: NarrationAudioArtifact) -> None:
    if not artifact.scene_id or not artifact.storage_key or artifact.duration_ms < 250:
        raise TTSConfigurationError("Invalid narration audio artifact.")
    if len(artifact.sha256) != 64:
        raise TTSConfigurationError("Narration audio artifact hash is invalid.")
    if not artifact.provider_key or not artifact.language:
        raise TTSConfigurationError("Narration audio provider metadata is incomplete.")


MAX_NARRATION_TEXT = 4000
MAX_NARRATION_BYTES = 40 * 1024 * 1024
SAMPLE_RATE_HZ = 22050

_POWERSHELL_SCRIPT = """
Add-Type -AssemblyName System.Speech
$text = [System.IO.File]::ReadAllText($env:UGI_TTS_TEXT_FILE, [System.Text.Encoding]::UTF8)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
    {rate},
    [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
    [System.Speech.AudioFormat.AudioChannel]::Mono)
$synth.SetOutputToWaveFile($env:UGI_TTS_OUT_FILE, $fmt)
$synth.Speak($text)
$synth.Dispose()
""".format(rate=SAMPLE_RATE_HZ)


class WindowsSystemSpeechProvider:
    """Offline, zero-cost narration synthesis through the Windows voice already installed."""

    key = "windows-system-speech"

    def synthesize(
        self,
        *,
        scene_id: str,
        text: str,
        language: str,
        output_path: Path,
    ) -> NarrationAudioArtifact:
        if not scene_id or not text.strip():
            raise TTSConfigurationError("Narration synthesis needs a scene id and text.")
        if len(text) > MAX_NARRATION_TEXT:
            raise TTSConfigurationError("Narration text exceeds the scene limit.")
        if not language:
            raise TTSConfigurationError("Narration language is required.")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        text_file = output_path.with_suffix(".input.txt")
        text_file.write_text(text, encoding="utf-8")
        encoded = base64.b64encode(_POWERSHELL_SCRIPT.encode("utf-16-le")).decode("ascii")
        environment = dict(os.environ)
        environment["UGI_TTS_TEXT_FILE"] = str(text_file)
        environment["UGI_TTS_OUT_FILE"] = str(output_path)
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                capture_output=True,
                env=environment,
                timeout=120,
            )
            if completed.returncode or not output_path.is_file():
                detail = completed.stderr.decode("utf-8", "replace").strip()[:2000]
                raise TTSConfigurationError(f"Windows speech synthesis failed: {detail or completed.returncode}")
            if output_path.stat().st_size > MAX_NARRATION_BYTES:
                raise TTSConfigurationError("Narration audio exceeds the safe size limit.")
            with wave.open(str(output_path), "rb") as handle:
                frames = handle.getnframes()
                rate = handle.getframerate()
                width = handle.getsampwidth()
                if handle.getnchannels() != 1 or width != 2 or frames < 1:
                    raise TTSConfigurationError("Narration audio is not a valid mono PCM stream.")
            duration_ms = int(frames / rate * 1000)
            digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
        finally:
            text_file.unlink(missing_ok=True)
        artifact = NarrationAudioArtifact(
            scene_id=scene_id,
            storage_key=output_path.name,
            duration_ms=duration_ms,
            sha256=digest,
            provider_key=self.key,
            language=language,
        )
        validate_audio_artifact(artifact)
        return artifact
