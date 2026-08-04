"""
validate_model_v2.py — Step 4 standalone validation gate for ultron_v2.onnx
(trained via prepare_data_streaming.py + train_ultron_model_v2.py).

Identical procedure to validate_model.py (real openwakeword.model.Model
runtime, predict_clip() streaming simulation, same three test sets) — only
the model path changed, so this is a fair apples-to-apples comparison
against the July 2026 attempt's failure on the same gate.
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
MODEL_PATH = BACKEND / "wake_word_models" / "ultron_v2.onnx"
PIPER_EXE = BACKEND / "piper_models" / "piper.exe"
PIPER_MODEL = BACKEND / "piper_models" / "en_US-lessac-medium.onnx"

THRESHOLD = 0.5

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
    scores = [p["ultron_v2"] for p in preds]
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
        print(f"ERROR: {MODEL_PATH} not found. Run train_ultron_model_v2.py first.")
        sys.exit(1)

    from openwakeword.model import Model

    print(f"Loading {MODEL_PATH} via openwakeword.model.Model (onnx runtime, "
          f"the same class backend/voice/wake_word.py will use)...")
    oww_model = Model(
        wakeword_models=[str(MODEL_PATH)],
        class_mapping_dicts=[{"0": "ultron_v2"}],
        inference_framework="onnx",
    )
    print(f"Loaded. Registered models: {list(oww_model.models.keys())}, "
          f"class mapping: {oww_model.class_mapping}")

    # 1. Positive set: ALL 50 real recordings (not just a sample of 5 — we
    # want the fullest possible real-evidence picture given the prior
    # failure mode was "looks perfect on 5, meaningless in practice").
    pos_files = sorted(POSITIVE_SRC.glob("*.wav"))
    pos_scores = run_set(oww_model, "POSITIVE (all 50 real 'Ultron' recordings)", pos_files)

    # 2. Negative set (seen during training)
    neg_files = sorted(NEGATIVE_SRC.glob("*.wav"))
    neg_seen_sample = [
        neg_files[0], neg_files[10], neg_files[50], neg_files[100], neg_files[200],
        neg_files[20], neg_files[75], neg_files[150], neg_files[220], neg_files[247],
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
    print("STEP 4 VALIDATION SUMMARY (ultron_v2.onnx)")
    print("=" * 70)
    print(f"Threshold: {THRESHOLD}")
    print(f"Positive scores ({len(pos_scores)}):        {[f'{s:.3f}' for s in pos_scores]}")
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
    elif pos_pass >= 0.9 * len(pos_scores) and all_neg_seen_ok and all_neg_novel_ok:
        print("\nVERDICT: STRONG PASS WITH MINOR RECALL GAPS - negatives cleanly "
              "rejected (including novel), but a small number of real positive "
              "clips were missed.")
    elif all_neg_seen_ok and not all_neg_novel_ok:
        print("\nVERDICT: PARTIAL - model rejects trained-on negatives but "
              "produced false positive(s) on NOVEL unseen phrases. Offline "
              "validation does NOT reflect real-world generalization. "
              "Do not wire this into the app without further work.")
    else:
        print("\nVERDICT: FAIL - model does not reliably separate positive "
              "from negative samples. Do NOT proceed to Step 5.")


if __name__ == "__main__":
    main()
