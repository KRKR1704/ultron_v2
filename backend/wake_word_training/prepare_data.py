"""
prepare_data.py — Build the positive/negative training+validation embedding
sets for the custom "ultron" OpenWakeWord model.

Positive data: the 50 real recordings in wake_word_samples/, augmented
locally (pitch/gain/noise/filter variation via audiomentations) to multiply
into more training variety — since there's no piper-sample-generator-based
synthetic-voice pipeline in this scaled-down local approach.

Negative data: the Piper-synthesized clips from generate_negatives.py, plus
locally-generated silence/noise clips.

Both are converted to OpenWakeWord's native (16, 96) embedding-frame
representation via the bundled melspectrogram + embedding ONNX models, then
windowed into (16, 96) examples exactly matching the runtime model's input
shape (verified against openwakeword's shipped hey_jarvis_v0.1.onnx).
"""

import glob
import wave
from pathlib import Path

import numpy as np
from audiomentations import (
    AddGaussianSNR, Compose, Gain, HighPassFilter, LowPassFilter,
    PitchShift, TanhDistortion,
)

from openwakeword.utils import AudioFeatures

HERE = Path(__file__).parent
BACKEND = HERE.parent
POSITIVE_SRC = BACKEND / "wake_word_samples"
NEGATIVE_SRC = HERE / "negative_raw"
OUT_DIR = HERE / "features"

WINDOW_FRAMES = 16       # must match Model input_shape[0] (verified via hey_jarvis_v0.1.onnx: [1,16,96])
TARGET_PAD_SAMPLES = 48000  # ~3s @ 16kHz -> enough embedding frames to extract a 16-frame window
SR = 16000

_feat = AudioFeatures(
    melspec_model_path=str(Path(__import__("openwakeword").__file__).parent / "resources" / "models" / "melspectrogram.onnx"),
    embedding_model_path=str(Path(__import__("openwakeword").__file__).parent / "resources" / "models" / "embedding_model.onnx"),
    inference_framework="onnx",
)


def _load_wav_int16(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
        sr = w.getframerate()
    audio = np.frombuffer(raw, dtype=np.int16)
    if sr != SR:
        raise ValueError(f"{path}: expected {SR}Hz, got {sr}Hz")
    return audio


def _pad_to(audio: np.ndarray, target_len: int) -> np.ndarray:
    if len(audio) >= target_len:
        return audio[:target_len]
    pad_total = target_len - len(audio)
    pad_left = pad_total // 2
    pad_right = pad_total - pad_left
    return np.concatenate([
        np.zeros(pad_left, dtype=np.int16), audio, np.zeros(pad_right, dtype=np.int16),
    ])


# ── Positive augmentation pipelines (each clip run through several variants) ──
_AUGMENTERS = [
    Compose([]),  # unaugmented original
    Compose([PitchShift(min_semitones=-3, max_semitones=1, p=1.0)]),
    Compose([PitchShift(min_semitones=0, max_semitones=3, p=1.0)]),
    Compose([Gain(min_gain_db=-8, max_gain_db=-2, p=1.0)]),
    Compose([Gain(min_gain_db=2, max_gain_db=6, p=1.0)]),
    Compose([AddGaussianSNR(min_snr_db=15, max_snr_db=30, p=1.0)]),
    Compose([LowPassFilter(min_cutoff_freq=2000, max_cutoff_freq=4000, p=1.0)]),
    Compose([HighPassFilter(min_cutoff_freq=100, max_cutoff_freq=300, p=1.0)]),
    Compose([TanhDistortion(min_distortion=0.05, max_distortion=0.2, p=1.0)]),
    Compose([PitchShift(min_semitones=-2, max_semitones=2, p=1.0), AddGaussianSNR(min_snr_db=20, max_snr_db=35, p=1.0)]),
    Compose([Gain(min_gain_db=-5, max_gain_db=5, p=1.0), AddGaussianSNR(min_snr_db=15, max_snr_db=25, p=1.0)]),
]


def _augment(audio_int16: np.ndarray, augmenter: Compose) -> np.ndarray:
    audio_f32 = audio_int16.astype(np.float32) / 32768.0
    out = augmenter(samples=audio_f32, sample_rate=SR)
    out = np.clip(out * 32768.0, -32768, 32767).astype(np.int16)
    return out


def _windows_from_embedding(emb: np.ndarray, stride: int = 2) -> list[np.ndarray]:
    """emb: (frames, 96) -> list of (WINDOW_FRAMES, 96) windows, strided."""
    frames = emb.shape[0]
    if frames < WINDOW_FRAMES:
        return []
    windows = []
    for start in range(0, frames - WINDOW_FRAMES + 1, stride):
        windows.append(emb[start:start + WINDOW_FRAMES])
    return windows


def build_positive_features() -> np.ndarray:
    files = sorted(glob.glob(str(POSITIVE_SRC / "*.wav")))
    print(f"Loading {len(files)} positive source recordings...")
    all_windows = []
    for f in files:
        raw = _load_wav_int16(f)
        for augmenter in _AUGMENTERS:
            aug = _augment(raw, augmenter) if len(augmenter.transforms) else raw
            padded = _pad_to(aug, TARGET_PAD_SAMPLES)
            emb = _feat.embed_clips(padded[None, :].astype(np.int16))[0]  # (frames, 96)
            # A handful of windows per augmented clip, centered on the word
            windows = _windows_from_embedding(emb, stride=2)
            all_windows.extend(windows)
    result = np.stack(all_windows).astype(np.float32)
    print(f"Positive: {len(files)} source clips x {len(_AUGMENTERS)} augmentations "
          f"-> {result.shape[0]} windowed training examples, shape {result.shape}")
    return result


def build_negative_features() -> np.ndarray:
    files = sorted(glob.glob(str(NEGATIVE_SRC / "*.wav")))
    print(f"Loading {len(files)} negative source recordings...")
    all_windows = []
    for f in files:
        raw = _load_wav_int16(f)
        padded = _pad_to(raw, TARGET_PAD_SAMPLES)
        emb = _feat.embed_clips(padded[None, :].astype(np.int16))[0]
        windows = _windows_from_embedding(emb, stride=1)  # denser stride: more negative diversity
        all_windows.extend(windows)

    # Add pure silence/low-noise negatives too
    rng = np.random.default_rng(42)
    for _ in range(40):
        silence = (rng.normal(0, 50, TARGET_PAD_SAMPLES)).astype(np.int16)
        emb = _feat.embed_clips(silence[None, :])[0]
        windows = _windows_from_embedding(emb, stride=4)
        all_windows.extend(windows)

    result = np.stack(all_windows).astype(np.float32)
    print(f"Negative: {len(files)} synthesized clips + 40 silence/noise clips "
          f"-> {result.shape[0]} windowed training examples, shape {result.shape}")
    return result


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pos = build_positive_features()
    neg = build_negative_features()

    rng = np.random.default_rng(1234)
    pos_idx = rng.permutation(len(pos))
    neg_idx = rng.permutation(len(neg))

    pos_val_n = max(1, int(0.15 * len(pos)))
    neg_val_n = max(1, int(0.15 * len(neg)))

    pos_train, pos_val = pos[pos_idx[pos_val_n:]], pos[pos_idx[:pos_val_n]]
    neg_train, neg_val = neg[neg_idx[neg_val_n:]], neg[neg_idx[:neg_val_n]]

    np.save(OUT_DIR / "positive_train.npy", pos_train)
    np.save(OUT_DIR / "positive_val.npy", pos_val)
    np.save(OUT_DIR / "negative_train.npy", neg_train)
    np.save(OUT_DIR / "negative_val.npy", neg_val)

    print()
    print(f"Train: {len(pos_train)} positive, {len(neg_train)} negative")
    print(f"Val:   {len(pos_val)} positive, {len(neg_val)} negative")
    print(f"Saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
