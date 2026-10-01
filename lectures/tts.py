from __future__ import annotations

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
