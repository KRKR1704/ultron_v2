"""
record_positives.py — Interactive mic recorder to rebuild wake_word_samples/.

The original 50 real "Ultron" recordings from the 2026-07-23 training attempt
were never committed (*.wav is gitignored) and don't exist in this
environment. This script re-records them: it walks you through saying
"Ultron" N times, saving each clip in the exact format prepare_data.py
requires (16kHz, mono, 16-bit PCM WAV) into backend/wake_word_samples/.

Run this yourself, interactively, in a real terminal (not something Claude
drives for you — it needs you to actually speak on cue):

    cd backend/wake_word_training
    ../../.venv/Scripts/python.exe record_positives.py

Resumable: existing clips in wake_word_samples/ are detected on startup and
numbering continues from there, so you can stop and restart across sessions.

For each clip you'll be prompted, given a countdown, recorded for a fixed
window, then given the chance to listen back and accept or retry. Vary your
delivery across the 50 — normal pace, quieter, faster, slightly different
tone — the original approach's augmentation pipeline (pitch/gain/noise/
filter) adds more variety on top, but natural variation in the source
recordings still helps the model generalize.
"""

import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

HERE = Path(__file__).parent
BACKEND = HERE.parent
OUT_DIR = BACKEND / "wake_word_samples"

SR = 16000
CHANNELS = 1
CLIP_SECONDS = 2.0
TARGET_COUNT = 50


def _existing_count() -> int:
    return len(sorted(OUT_DIR.glob("ultron_*.wav")))


def _next_path(n: int) -> Path:
    return OUT_DIR / f"ultron_{n:03d}.wav"


def _record_clip() -> np.ndarray:
    audio = sd.rec(int(CLIP_SECONDS * SR), samplerate=SR, channels=CHANNELS, dtype="int16")
    sd.wait()
    return audio.reshape(-1)


def _play(audio: np.ndarray) -> None:
    sd.play(audio, samplerate=SR)
    sd.wait()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    n = _existing_count()
    if n > 0:
        print(f"Found {n} existing clip(s) in {OUT_DIR} — resuming from #{n + 1}.")
    print(f"Target: {TARGET_COUNT} clips. Say the single word \"Ultron\" clearly when")
    print(f"recording starts — you'll have {CLIP_SECONDS:.1f}s per take, then you can")
    print("listen back and accept (Enter) or retry (r).")
    print("Vary delivery a little across takes: normal, quieter, faster/slower, etc.")
    print("Press Ctrl+C at any time to stop early — clips saved so far are kept.\n")

    try:
        while n < TARGET_COUNT:
            input(f"[{n + 1}/{TARGET_COUNT}] Press Enter, then say \"Ultron\" after the beep...")
            for i in (3, 2, 1):
                print(f"  {i}...")
                time.sleep(0.5)
            print("  *beep* recording...")
            sd.play(0.2 * np.sin(2 * np.pi * 880 * np.arange(int(0.12 * SR)) / SR), samplerate=SR)
            sd.wait()

            audio = _record_clip()
            peak = int(np.abs(audio).max())
            print(f"  captured, peak amplitude {peak} (silence if near 0)")

            _play(audio)
            choice = input("  Accept this clip? [Enter=accept, r=retry, q=quit]: ").strip().lower()
            while choice == "r":
                print("  Retrying...")
                for i in (3, 2, 1):
                    print(f"  {i}...")
                    time.sleep(0.5)
                print("  *beep* recording...")
                audio = _record_clip()
                peak = int(np.abs(audio).max())
                print(f"  captured, peak amplitude {peak}")
                _play(audio)
                choice = input("  Accept this clip? [Enter=accept, r=retry, q=quit]: ").strip().lower()

            if choice == "q":
                break

            n += 1
            path = _next_path(n)
            sf.write(str(path), audio, SR, subtype="PCM_16")
            print(f"  saved {path.name}\n")

    except KeyboardInterrupt:
        print("\nStopped early.")

    final_count = _existing_count()
    print(f"\nDone. {final_count}/{TARGET_COUNT} clips in {OUT_DIR}.")
    if final_count < TARGET_COUNT:
        print("Run this script again to continue — it resumes automatically.")
    else:
        print("Target reached. Ready for prepare_data.py.")


if __name__ == "__main__":
    main()
