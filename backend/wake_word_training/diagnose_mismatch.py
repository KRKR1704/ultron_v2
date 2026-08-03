"""
diagnose_mismatch.py — One-off diagnostic for the Step 4 validation failure.

Compares two ways of getting a score for the same wav file:
  (A) offline: exactly prepare_data.py's embed_clips() on the padded clip,
      windowed, fed directly to the raw onnx classifier via onnxruntime
      (bypassing openwakeword.model.Model entirely).
  (B) runtime: openwakeword.model.Model.predict_clip() -- the streaming,
      chunked path that failed validation.

If (A) separates positive/negative cleanly but (B) doesn't, the bug is in
how the streaming/runtime AudioFeatures embeddings differ from the offline
batch embeddings used to build the training set -- not in the classifier
weights themselves.
"""

import wave
from pathlib import Path

import numpy as np
import onnxruntime as ort

from openwakeword.utils import AudioFeatures
from openwakeword.model import Model

HERE = Path(__file__).parent
BACKEND = HERE.parent
POSITIVE_SRC = BACKEND / "wake_word_samples"
NEGATIVE_SRC = HERE / "negative_raw"
MODEL_PATH = BACKEND / "wake_word_models" / "ultron.onnx"

WINDOW_FRAMES = 16
TARGET_PAD_SAMPLES = 48000
SR = 16000

_feat = AudioFeatures(
    melspec_model_path=str(Path(__import__("openwakeword").__file__).parent / "resources" / "models" / "melspectrogram.onnx"),
    embedding_model_path=str(Path(__import__("openwakeword").__file__).parent / "resources" / "models" / "embedding_model.onnx"),
    inference_framework="onnx",
)

_session = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
_input_name = _session.get_inputs()[0].name


def _load_wav_int16(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


def _pad_to(audio: np.ndarray, target_len: int) -> np.ndarray:
    if len(audio) >= target_len:
        return audio[:target_len]
    pad_total = target_len - len(audio)
    pad_left = pad_total // 2
    pad_right = pad_total - pad_left
    return np.concatenate([np.zeros(pad_left, dtype=np.int16), audio, np.zeros(pad_right, dtype=np.int16)])


def offline_score(path: Path) -> float:
    """Exactly mirrors prepare_data.py's feature path, then classifies every
    window with the raw onnx session, returning the max score."""
    raw = _load_wav_int16(str(path))
    padded = _pad_to(raw, TARGET_PAD_SAMPLES)
    emb = _feat.embed_clips(padded[None, :].astype(np.int16))[0]  # (frames, 96)
    frames = emb.shape[0]
    if frames < WINDOW_FRAMES:
        return -1.0
    scores = []
    for start in range(0, frames - WINDOW_FRAMES + 1, 2):
        window = emb[start:start + WINDOW_FRAMES][None, :, :].astype(np.float32)
        out = _session.run(None, {_input_name: window})
        scores.append(float(out[0].squeeze()))
    return max(scores)


def runtime_score(oww_model: Model, path: Path) -> float:
    oww_model.reset()
    preds = oww_model.predict_clip(str(path))
    return max(p["ultron"] for p in preds) if preds else 0.0


def main():
    oww_model = Model(
        wakeword_models=[str(MODEL_PATH)],
        class_mapping_dicts=[{"ultron": {"0": "ultron"}}],
        inference_framework="onnx",
    )
    print("class_mapping actually applied:", oww_model.class_mapping)

    pos_files = sorted(POSITIVE_SRC.glob("*.wav"))[:5]
    neg_files = sorted(NEGATIVE_SRC.glob("*.wav"))[:5]

    print(f"\n{'file':40s} {'offline':>10s} {'runtime':>10s}")
    for f in pos_files:
        off = offline_score(f)
        run = runtime_score(oww_model, f)
        print(f"POS  {f.name:35s} {off:10.4f} {run:10.4f}")
    for f in neg_files:
        off = offline_score(f)
        run = runtime_score(oww_model, f)
        print(f"NEG  {f.name:35s} {off:10.4f} {run:10.4f}")


if __name__ == "__main__":
    main()
