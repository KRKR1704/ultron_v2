"""
validate_model.py — Step 4 standalone validation gate for the custom "ultron"
OpenWakeWord model.

Deliberately does NOT reuse prepare_data.py's offline windowed-embedding
pipeline (which has a leakage risk: augmented windows from the same source
recording can land in both the train and val split). Instead this loads the
exported ultron.onnx through openwakeword's actual runtime Model class and
its predict_clip() streaming simulation — the exact code path
backend/voice/wake_word.py will use in production — so the numbers reported
here reflect real end-to-end behavior, not just offline classifier accuracy.

Three test sets:
  1. Positive: 5 raw "Ultron" recordings from wake_word_samples/ (unaugmented).
  2. Negative (seen): 5 Piper-synthesized clips that WERE part of training
     (as the task instructions describe) -- confirms the model at least
     rejects what it was trained to reject.
  3. Negative (novel/unseen): fresh phrases never used anywhere in training,
     synthesized on the spot -- the more meaningful false-positive test,
     since set (2) is not a true generalization check.

Prints every individual score plus a pass/fail verdict, and is honest if the
model does not clearly separate positive from negative.
"""

import subprocess
import struct
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
BACKEND = HERE.parent
POSITIVE_SRC = BACKEND / "wake_word_samples"
NEGATIVE_SRC = HERE / "negative_raw"
MODEL_PATH = BACKEND / "wake_word_models" / "ultron.onnx"
PIPER_EXE = BACKEND / "piper_models" / "piper.exe"
PIPER_MODEL = BACKEND / "piper_models" / "en_US-lessac-medium.onnx"

THRESHOLD = 0.5

# Phrases that do NOT appear anywhere in generate_negatives.py's phrase lists
# or in the hard-negative/assistant/generic/word lists used for training.
NOVEL_NEGATIVE_PHRASES = [
    "activate the defense protocol",
    "please close the window",
    "let's order some food tonight",
    "run a full system diagnostic",
    "can you dim the lights please",
    "i think it might rain later",
    "schedule a meeting for tomorrow",
    "the robot walked across the room",
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
    import audioop
    import io
    with wave.open(io.BytesIO(wav_bytes_22050), "rb") as w:
        pcm = w.readframes(w.getnframes())
        rate = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
    converted, _ = audioop.ratecv(pcm, sw, ch, rate, 16000, None)
    return _pcm_to_wav(converted, sample_rate=16000, channels=ch, sample_width=sw)


def synthesize_novel_negative(text: str, out_path: Path) -> bool:
    result = subprocess.run(
        [str(PIPER_EXE), "--model", str(PIPER_MODEL),
         "--noise_scale", "0.75", "--length_scale", "0.95", "--noise_w", "0.7",
         "--output-raw"],
        input=text.encode("utf-8"), capture_output=True, timeout=30,
    )
    if result.returncode != 0 or not result.stdout:
        print(f"  FAILED to synthesize {text!r}: {result.stderr[:200]}")
        return False
    wav_22050 = _pcm_to_wav(result.stdout, sample_rate=22050)
    wav_16k = _resample_to_16k_mono(wav_22050)
    out_path.write_bytes(wav_16k)
    return True


def max_score(oww_model, wav_path: Path) -> float:
    oww_model.reset()
    preds = oww_model.predict_clip(str(wav_path))
    scores = [p["ultron"] for p in preds]
    return max(scores) if scores else 0.0


def run_set(oww_model, label: str, files: list[Path]) -> list[float]:
    print(f"\n--- {label} ({len(files)} clips) ---")
    scores = []
    for f in files:
        s = max_score(oww_model, f)
        scores.append(s)
        print(f"  {f.name:40s} max_score={s:.4f}")
    return scores


def main():
    if not MODEL_PATH.exists():
        print(f"ERROR: {MODEL_PATH} not found. Run train_ultron_model.py first.")
        sys.exit(1)

    from openwakeword.model import Model

    print(f"Loading {MODEL_PATH} via openwakeword.model.Model (onnx runtime, "
          f"the same class backend/voice/wake_word.py will use)...")
    oww_model = Model(
        wakeword_models=[str(MODEL_PATH)],
        class_mapping_dicts=[{"0": "ultron"}],
        inference_framework="onnx",
    )
    print(f"Loaded. Registered models: {list(oww_model.models.keys())}, "
          f"class mapping: {oww_model.class_mapping}")

    # 1. Positive set: 5 real recordings, spread across the 50 available
    pos_files = sorted(POSITIVE_SRC.glob("*.wav"))
    pos_sample = [pos_files[i] for i in (0, 10, 20, 30, 49)]
    pos_scores = run_set(oww_model, "POSITIVE (real 'Ultron' recordings)", pos_sample)

    # 2. Negative set (seen during training, per task instructions)
    neg_files = sorted(NEGATIVE_SRC.glob("*.wav"))
    neg_seen_sample = [
        neg_files[0],    # hard negative: "ultra"
        neg_files[10],   # hard negative
        neg_files[50],   # assistant phrase
        neg_files[100],  # generic phrase
        neg_files[200],  # word
    ]
    neg_seen_scores = run_set(oww_model, "NEGATIVE - seen in training (Piper hard negatives/phrases)", neg_seen_sample)

    # 3. Negative set (novel, never seen anywhere in training)
    novel_dir = HERE / "novel_negatives"
    novel_dir.mkdir(exist_ok=True)
    novel_files = []
    print(f"\nSynthesizing {len(NOVEL_NEGATIVE_PHRASES)} novel (never-trained-on) negative phrases...")
    for i, phrase in enumerate(NOVEL_NEGATIVE_PHRASES):
        out_path = novel_dir / f"novel_{i:02d}.wav"
        if synthesize_novel_negative(phrase, out_path):
            novel_files.append(out_path)
    neg_novel_scores = run_set(oww_model, "NEGATIVE - NOVEL, never used in training", novel_files)

    # ── Verdict ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("STEP 4 VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Threshold: {THRESHOLD}")
    print(f"Positive scores:            {[f'{s:.3f}' for s in pos_scores]}")
    print(f"Negative (seen) scores:     {[f'{s:.3f}' for s in neg_seen_scores]}")
    print(f"Negative (novel) scores:    {[f'{s:.3f}' for s in neg_novel_scores]}")

    pos_pass = sum(1 for s in pos_scores if s >= THRESHOLD)
    neg_seen_pass = sum(1 for s in neg_seen_scores if s < THRESHOLD)
    neg_novel_pass = sum(1 for s in neg_novel_scores if s < THRESHOLD)

    print(f"\nPositive detected (score >= {THRESHOLD}): {pos_pass}/{len(pos_scores)}")
    print(f"Negative (seen) rejected (score < {THRESHOLD}): {neg_seen_pass}/{len(neg_seen_scores)}")
    print(f"Negative (novel) rejected (score < {THRESHOLD}): {neg_novel_pass}/{len(neg_novel_scores)}")

    all_pos_ok = pos_pass == len(pos_scores)
    all_neg_seen_ok = neg_seen_pass == len(neg_seen_scores)
    all_neg_novel_ok = neg_novel_pass == len(neg_novel_scores)

    if all_pos_ok and all_neg_seen_ok and all_neg_novel_ok:
        print("\nVERDICT: PASS - clean separation on all three test sets "
              "(including phrases never used in training).")
    elif all_pos_ok and all_neg_seen_ok and not all_neg_novel_ok:
        print("\nVERDICT: PARTIAL - model correctly detects positives and "
              "rejects trained-on negatives, but produced false positive(s) "
              "on NOVEL unseen phrases. This means the offline 100% validation "
              "accuracy during training does NOT reflect real-world generalization. "
              "Do not wire this into the app without further work (more/varied "
              "negative data, live-mic Step 6 testing with real speech).")
    else:
        print("\nVERDICT: FAIL - model does not reliably separate positive "
              "from negative samples. Do NOT proceed to Step 5.")


if __name__ == "__main__":
    main()
