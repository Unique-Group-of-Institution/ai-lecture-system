"""Create a one-second synthetic silent WAV for the local Remotion smoke render."""

import wave
from pathlib import Path


def main() -> None:
    target = Path(__file__).resolve().parents[1] / "remotion" / "public" / "smoke" / "silence.wav"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as raw:
        with wave.open(raw, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16_000)
            output.writeframes(b"\x00\x00" * 16_000)
    print("Created synthetic one-second silent WAV in ignored Remotion public storage.")


if __name__ == "__main__":
    main()
