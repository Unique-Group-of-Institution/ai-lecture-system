# Local Whisper and Audio-QC Benchmark

T020 uses a fully local, zero-cost pipeline. Teacher audio, decoded PCM,
transcripts, QC JSON and logs stay beneath `data/lectures/t020-local/`, which is
Git-ignored. Never pass an HTTP(S) URL as an input and never commit the local
tool, model or media files.

## Selected implementation

- Whisper implementation: `whisper.cpp` 1.9.2, official Windows x64 CPU build.
- Model: multilingual `small-q5_1`, 190,085,487 bytes, Q5_1 quantized compute.
- Model SHA-256:
  `ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb`.
- Decoder: Gyan.dev FFmpeg 9.0 Release Essentials portable Windows x64 build.
- FFmpeg archive SHA-256:
  `e6b54767a6065919048f1a098eb27211ca4e12b4348a05d88777a5855d0b6e71`.
- Compute: CPU only, four threads. The legacy AMD/Intel GPUs do not provide a
  supported CUDA path.

The quantized multilingual small model balances Urdu/English quality against
the target PC's 8 GB RAM. The CLI avoids uncertain Python 3.14 native-wheel
compatibility and uses no paid service. FFmpeg is portable, is not placed on
`PATH`, and is used only to create a separate PCM derivative.

## Safe Windows workflow

Keep the teacher input outside the repository and assign its exact,
human-authorized path only in the current PowerShell process:

```powershell
$authorizedAudio = "<exact-authorized-local-audio-path>"
$localRoot = Join-Path $PWD "data\lectures\t020-local"
$ffmpeg = Join-Path $localRoot "tools\ffmpeg-9.0-essentials_build\ffmpeg-9.0-essentials_build\bin\ffmpeg.exe"
$temporaryWav = Join-Path $localRoot "decoded\authorized-input-16k-mono-s16.wav"
$conversionOut = Join-Path $localRoot "logs\ffmpeg-conversion.stdout.log"
$conversionErr = Join-Path $localRoot "logs\ffmpeg-conversion.stderr.log"

& $ffmpeg -nostdin -hide_banner -nostats -loglevel info -n `
  -i $authorizedAudio -map_metadata -1 -vn -ac 1 -ar 16000 `
  -c:a pcm_s16le $temporaryWav 1> $conversionOut 2> $conversionErr
```

The `-n` option refuses overwrite. The command does not normalize, filter,
trim or cut audio. Validate that the derivative is signed 16-bit PCM, 16 kHz,
mono, and duration-matched before benchmarking.

Run the tracked orchestrator with explicit local dependency paths:

```powershell
python scripts\benchmark_audio.py `
  --input $temporaryWav `
  --output-dir (Join-Path $localRoot "runs\run-001") `
  --whisper-cli (Join-Path $localRoot "tools\whisper-bin-x64-v1.9.2\Release\whisper-cli.exe") `
  --model (Join-Path $localRoot "models\ggml-small-q5_1.bin") `
  --threads 4
```

The orchestrator refuses missing dependencies, source/output collisions,
existing output artifacts, and output outside `data/lectures/`. It redirects
Whisper streams to local files, verifies input size and modification time, and
emits transcript-free aggregate QC JSON.

## T020 benchmark summary

The authorized local pilot was 568.789 seconds. PCM conversion took 1.523
seconds and produced 18,201,336 bytes. The `small-q5_1` CPU transcription took
1,616.126 seconds (real-time factor 2.8413) and peaked at 670,408,704 bytes of
working-set memory.

Whisper detected language code `hi`; this build did not include a language
probability in its JSON. It produced 29 ordered, valid timestamped segments.
Aggregate technical QC found zero clipped samples and nine flags: six long
silences, two long transcript gaps and one possible-background-noise flag.
These are technical suggestions only. No semantic correction, caption edit,
cut or teacher-content judgment was made.

Only these privacy-safe aggregate metrics belong in Git. The real transcript,
timestamps, media, filenames and logs remain local and ignored.
