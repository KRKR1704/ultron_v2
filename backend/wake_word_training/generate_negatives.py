"""
generate_negatives.py — Synthesize negative (NOT "ultron") training clips
using the Piper TTS binary already installed for this project
(backend/piper_models/piper.exe + en_US-lessac-medium).

Scaled-down local alternative to OpenWakeWord's official pipeline (which
downloads ~2000 hours of pre-computed negative features from HuggingFace).
Produces a modest local negative set instead: phonetically-similar "hard
negative" words, common assistant/chat phrases, generic sentences, and
silence — varying Piper's synthesis parameters per clip for some acoustic
diversity despite using a single voice model.
"""

import subprocess
import struct
import wave
from pathlib import Path

PIPER_EXE = Path(__file__).parent.parent / "piper_models" / "piper.exe"
MODEL = Path(__file__).parent.parent / "piper_models" / "en_US-lessac-medium.onnx"
OUT_DIR = Path(__file__).parent / "negative_raw"

# ── Hard negatives: phonetically close to "Ultron" ────────────────────────────
HARD_NEGATIVES = [
    "ultra", "ultra violet", "ultra sound", "electron", "electron microscope",
    "matron", "patron", "neutron", "neutron star", "cauldron", "squadron",
    "environ", "chevron", "citron", "positron", "cyclotron", "synchrotron",
    "oltron", "altron", "eltron", "aldron", "alter on", "old tron",
]

# ── Assistant / wake-word-adjacent phrases ────────────────────────────────────
ASSISTANT_PHRASES = [
    "hey siri", "ok google", "alexa", "hey google", "hey cortana",
    "computer", "jarvis", "hey jarvis", "wake up", "are you there",
    "hello there", "good morning", "good evening",
]

# ── Generic commands / chit-chat (things a user might actually say) ──────────
GENERIC_PHRASES = [
    "what time is it", "turn on the lights", "how are you today",
    "can you help me", "search for the weather", "play some music",
    "what is on my calendar", "set a timer for five minutes",
    "tell me a joke", "what is the capital of France",
    "remind me to call mom", "open my email", "how far is the moon",
    "what is two plus two", "read me the news", "turn off the tv",
    "increase the volume", "decrease the brightness", "take a photo",
    "start a video call", "send a message to john", "what is my schedule",
    "close the door", "lock the front door", "what is the temperature outside",
    "give me directions home", "find a nearby restaurant",
    "what is the meaning of life", "tell me about the weather tomorrow",
    "can you order a pizza", "what day is it today",
    "i would like a coffee please", "the quick brown fox jumps over the lazy dog",
    "she sells seashells by the seashore", "please pass the salt",
    "i am going to the store", "let's watch a movie tonight",
    "the weather looks nice today", "my favorite color is blue",
    "he walked to the park this morning", "we should get lunch sometime",
    "the meeting starts at noon", "traffic was heavy on the highway",
    "i need to buy groceries", "the printer is out of paper",
    "can you turn down the music", "what's for dinner tonight",
    "i left my keys at home", "the train arrives in ten minutes",
]

# ── Random isolated common words (numbers, days, colors) ─────────────────────
WORDS = [
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "red", "blue", "green", "yellow", "purple", "orange", "black", "white",
    "yes", "no", "maybe", "please", "thank you", "sorry", "excuse me",
    "hello", "goodbye", "welcome", "stop", "start", "pause", "continue",
]

ALL_PHRASES = HARD_NEGATIVES + ASSISTANT_PHRASES + GENERIC_PHRASES + WORDS

# Vary Piper's synthesis params across clips for some acoustic diversity
# from a single voice model.
_PARAM_VARIANTS = [
    {"noise_scale": "0.667", "length_scale": "1.0", "noise_w": "0.8"},
    {"noise_scale": "0.9", "length_scale": "0.85", "noise_w": "0.6"},
    {"noise_scale": "0.5", "length_scale": "1.2", "noise_w": "1.0"},
    {"noise_scale": "0.8", "length_scale": "1.0", "noise_w": "0.4"},
]


def _pcm_to_wav(pcm: bytes, sample_rate=22050, channels=1, sample_width=2) -> bytes:
    data_size = len(pcm)
    byte_rate = sample_rate * channels * sample_width
    block_align = channels * sample_width
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + data_size, b"WAVE", b"fmt ",
        16, 1, channels, sample_rate, byte_rate, block_align, sample_width * 8,
        b"data", data_size,
    )
    return header + pcm


def _resample_to_16k_mono(wav_bytes_22050: bytes) -> bytes:
    """Piper outputs 22050Hz; downsample to 16kHz to match wake-word pipeline."""
    import audioop
    import io
    with wave.open(io.BytesIO(wav_bytes_22050), "rb") as w:
        pcm = w.readframes(w.getnframes())
        rate = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
    converted, _ = audioop.ratecv(pcm, sw, ch, rate, 16000, None)
    return _pcm_to_wav(converted, sample_rate=16000, channels=ch, sample_width=sw)


def synthesize(text: str, out_path: Path, variant_idx: int) -> bool:
    params = _PARAM_VARIANTS[variant_idx % len(_PARAM_VARIANTS)]
    try:
        result = subprocess.run(
            [
                str(PIPER_EXE), "--model", str(MODEL),
                "--noise_scale", params["noise_scale"],
                "--length_scale", params["length_scale"],
                "--noise_w", params["noise_w"],
                "--output-raw",
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0 or not result.stdout:
            print(f"  FAILED: {text!r} -> {result.stderr[:200]}")
            return False
        wav_22050 = _pcm_to_wav(result.stdout, sample_rate=22050)
        wav_16k = _resample_to_16k_mono(wav_22050)
        out_path.write_bytes(wav_16k)
        return True
    except Exception as err:
        print(f"  ERROR synthesizing {text!r}: {err}")
        return False


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ok, fail = 0, 0
    for i, phrase in enumerate(ALL_PHRASES):
        # Generate 2 variants of each phrase for a bit more volume/diversity
        for v in range(2):
            out_path = OUT_DIR / f"neg_{i:03d}_{v}.wav"
            if synthesize(phrase, out_path, variant_idx=i * 2 + v):
                ok += 1
            else:
                fail += 1
    print(f"\nGenerated {ok} negative clips ({fail} failed) from {len(ALL_PHRASES)} phrases into {OUT_DIR}")


if __name__ == "__main__":
    main()
