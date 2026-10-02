import asyncio, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = json.load(open(os.path.join(ROOT, "ch12-scenes.json"), encoding="utf-8"))
AUDIO_DIR = os.path.join(ROOT, "public", "ch12", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

import edge_tts

async def synth(text, path, voice):
    tts = edge_tts.Communicate(text, voice)
    await tts.save(path)

def probe_duration(path):
    out = subprocess.run(
        "npx remotion ffprobe -v error -show_entries "
        "format=duration -of default=noprint_wrappers=1 " + f'"{path}"',
        capture_output=True, text=True, cwd=ROOT, shell=True)
    m = re.search(r"duration=([\d.]+)", out.stdout)
    if not m:
        raise RuntimeError(out.stdout + out.stderr)
    return float(m.group(1))

durations = {}
for scene in DATA["scenes"]:
    name = f"scene{scene['id']:02d}.mp3"
    path = os.path.join(AUDIO_DIR, name)
    if not os.path.exists(path) or os.path.getsize(path) < 2000:
        asyncio.run(synth(scene["vo"], path, DATA["voice"]))
    dur = probe_duration(path)
    durations[str(scene["id"])] = round(dur, 3)
    print(f"scene {scene['id']:02d}: {dur:.2f}s", flush=True)

with open(os.path.join(ROOT, "ch12-durations.json"), "w", encoding="utf-8") as f:
    json.dump(durations, f, indent=2)
print("TOTAL:", round(sum(durations.values()), 1), "s")
