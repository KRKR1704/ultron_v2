"""
prepare_data_streaming.py — Build the positive/negative training feature set
for the custom "ultron" OpenWakeWord model using the SAME streaming/chunked
feature-extraction path backend/voice/wake_word.py uses at runtime.

This replaces prepare_data.py's approach, which called AudioFeatures's
OFFLINE BATCH method (embed_clips()) to build training features. That
produced a model that scored ~0.99 on every real clip when validated through
the actual runtime path (openwakeword.model.Model.predict()) — see
AUDIT_REPORT.md Fix Pass History for the full diagnosis. Root cause,
confirmed by reading openwakeword/utils.py's AudioFeatures class directly:

  - The streaming path (AudioFeatures._streaming_features(), called by
    Model.predict() as `self.preprocessor(x)`) maintains a PERSISTENT
    feature_buffer that is SEEDED, at construction/reset() time, with
    embeddings computed from ~4 seconds of RANDOM NOISE:
    `self.feature_buffer = self._get_embeddings(np.random.randint(-1000,
    1000, 16000*4)...)`. New embedding frames are appended to this buffer
    incrementally, 1280 samples (80ms) at a time, as real audio streams in.
  - The offline path (embed_clips(), what prepare_data.py used) has no such
    buffer or noise-seeded history — it computes embeddings for a
    single, self-contained, zero-padded clip in one batch call.
  - Same underlying melspectrogram/embedding ONNX models in both cases —
    the mismatch is purely in the surrounding buffering/history, exactly
    the pitfall openwakeword's own _streaming_melspectrogram() docstring
    warns about ("padding with 0 or very small values seems to demonstrate
    the differences well").

This script instead:
  1. Creates a fresh AudioFeatures object per clip and calls .reset() before
     processing it — mirroring openwakeword.model.Model.reset(), which
     validate_model.py's own Step 3/4 gate already calls before scoring each
     test file (`oww_model.reset()` in max_score()). Same procedure as the
     validation gate, not just a similar one — so train-time and
     validation-time data undergo identical preprocessing.
  2. Pads each clip with 1 second of zero-silence on each side, matching
     openwakeword.model.Model.predict_clip()'s own default `padding=1` —
     the exact "streaming simulation" the Step 3/4 gate uses.
  3. Feeds the padded clip through AudioFeatures.__call__() (NOT
     embed_clips()) in 1280-sample (80ms) chunks — the exact chunk size
     backend/voice/wake_word.py uses for real microphone audio — then reads
     AudioFeatures.get_features(16) after each chunk to capture the current
     16-frame sliding window, exactly mirroring what Model.predict() does
     internally on every call.
  4. Labels each window by whether it overlaps the clip's actual
     spoken-word span, detected via simple short-time RMS-energy
     endpointing on the raw waveform (see _detect_word_span()) — NOT by
     blindly labeling every window from a "positive" source recording as
     positive. This matters: with 1s+1s of padding around a ~1-2s word
     recording, most windows extracted from a positive source clip are
     pure silence/padding. Mislabeling those as positive would teach the
     model "silence sometimes means wake word", which — on top of the
     feature-extraction mismatch — is a second, independent way the prior
     attempt's training data could have taught the wrong thing.

Not real VAD, and the endpointing is intentionally simple (a fixed
RMS-ratio threshold, no ML) — appropriate for short, single-word,
relatively-quiet-room recordings, consistent with this project's
scaled-down local approach throughout. Flagged plainly rather than
overstated.
"""

import glob
from pathlib import Path

import numpy as np

from openwakeword.utils import AudioFeatures

HERE = Path(__file__).parent
BACKEND = HERE.parent
POSITIVE_SRC = BACKEND / "wake_word_samples"
NEGATIVE_SRC = HERE / "negative_raw"
OUT_DIR = HERE / "features_streaming"

SR = 16000
CHUNK_SAMPLES = 1280       # 80ms — exact chunk size backend/voice/wake_word.py feeds Model.predict()
WINDOW_FRAMES = 16         # matches the classifier's (16, 96) input shape
PAD_SECONDS = 1            # matches openwakeword.model.Model.predict_clip()'s default padding
PAD_SAMPLES = SR * PAD_SECONDS

# Word-span endpoint detection (simple RMS energy threshold, not real VAD)
_ENDPOINT_FRAME_MS = 20
_ENDPOINT_THRESH_RATIO = 0.15   # fraction of peak RMS to count as "the word"
_ENDPOINT_MARGIN_MS = 100       # safety margin added around the detected span

# A window is labeled positive only if the FULL word span fits inside it
# (word hasn't scrolled out) AND the window's most recent frame is within
# this many frames (~80ms each) of the word's end — i.e., "the word just
# finished streaming in", which is when a real-time detector should fire.
_POST_WORD_FIRE_WINDOW_FRAMES = 4


def _load_wav_int16(path: str) -> np.ndarray:
    import wave
    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
        sr = w.getframerate()
        ch = w.getnchannels()
    if sr != SR:
        raise ValueError(f"{path}: expected {SR}Hz, got {sr}Hz")
    if ch != 1:
        raise ValueError(f"{path}: expected mono, got {ch} channels")
    return np.frombuffer(raw, dtype=np.int16)


def _detect_word_span(audio: np.ndarray) -> tuple[int, int]:
    """
    Return (start_sample, end_sample) of the loudest contiguous region of
    *audio* via short-time RMS energy thresholding. Falls back to the whole
    clip if the signal is too quiet to threshold meaningfully.
    """
    frame_len = int(SR * _ENDPOINT_FRAME_MS / 1000)
    n_frames = len(audio) // frame_len
    if n_frames == 0:
        return 0, len(audio)

    rms = np.array([
        np.sqrt(np.mean(audio[i * frame_len:(i + 1) * frame_len].astype(np.float64) ** 2))
        for i in range(n_frames)
    ])
    peak = rms.max()
    if peak < 10:  # near-total silence
        return 0, len(audio)

    threshold = peak * _ENDPOINT_THRESH_RATIO
    above = np.where(rms >= threshold)[0]
    if len(above) == 0:
        return 0, len(audio)

    margin_frames = int(_ENDPOINT_MARGIN_MS / _ENDPOINT_FRAME_MS)
    start_frame = max(0, above[0] - margin_frames)
    end_frame = min(n_frames - 1, above[-1] + margin_frames)
    return start_frame * frame_len, (end_frame + 1) * frame_len


def _stream_clip_windows(audio_padded: np.ndarray) -> list[np.ndarray]:
    """
    Feed *audio_padded* through a FRESH AudioFeatures instance, chunk by
    chunk (1280 samples), exactly as Model.predict() does — and collect the
    (16, 96) sliding-window feature array after every chunk.

    Returns a list of windows, one per 80ms chunk processed, in order —
    index i corresponds to "the state of the sliding window after i+1
    chunks (i.e., (i+1)*1280 samples) of audio_padded have streamed in".
    """
    feat = AudioFeatures(inference_framework="onnx")
    feat.reset()

    windows = []
    n_chunks = len(audio_padded) // CHUNK_SAMPLES
    for i in range(n_chunks):
        chunk = audio_padded[i * CHUNK_SAMPLES:(i + 1) * CHUNK_SAMPLES]
        feat(chunk)  # AudioFeatures.__call__ == _streaming_features — updates internal buffers
        windows.append(feat.get_features(WINDOW_FRAMES)[0].copy())  # (16, 96)

    return windows


def build_positive_features() -> np.ndarray:
    files = sorted(glob.glob(str(POSITIVE_SRC / "*.wav")))
    print(f"Loading {len(files)} positive source recordings from {POSITIVE_SRC}...")
    if not files:
        raise SystemExit(f"No .wav files found in {POSITIVE_SRC} — record samples first "
                          f"(see record_positives.py).")

    pos_windows: list[np.ndarray] = []
    neg_windows_from_positive_clips: list[np.ndarray] = []

    for f in files:
        raw = _load_wav_int16(f)
        word_start, word_end = _detect_word_span(raw)
        word_start_frame = word_start / CHUNK_SAMPLES
        word_end_frame = word_end / CHUNK_SAMPLES

        padded = np.concatenate([
            np.zeros(PAD_SAMPLES, dtype=np.int16), raw, np.zeros(PAD_SAMPLES, dtype=np.int16),
        ])
        # Word span shifts by PAD_SAMPLES once we prepend the leading pad
        word_start_frame += PAD_SAMPLES / CHUNK_SAMPLES
        word_end_frame += PAD_SAMPLES / CHUNK_SAMPLES

        clip_windows = _stream_clip_windows(padded)

        for chunk_idx, window in enumerate(clip_windows):
            current_frame = chunk_idx + 1  # frames processed so far (1-indexed, matches get_features "now")
            window_start_frame = current_frame - WINDOW_FRAMES

            full_word_in_window = word_start_frame >= window_start_frame
            just_finished = word_end_frame <= current_frame <= word_end_frame + _POST_WORD_FIRE_WINDOW_FRAMES

            if full_word_in_window and just_finished:
                pos_windows.append(window)
            else:
                neg_windows_from_positive_clips.append(window)

    pos_result = np.stack(pos_windows).astype(np.float32)
    print(f"Positive: {len(files)} source clips -> {pos_result.shape[0]} positive windows "
          f"(streamed via the real AudioFeatures path, labeled via RMS endpointing)")
    print(f"  + {len(neg_windows_from_positive_clips)} implicit negative windows "
          f"(silence/lead-in/trail-off from the same positive source clips)")
    return pos_result, np.stack(neg_windows_from_positive_clips).astype(np.float32)


def build_negative_features() -> np.ndarray:
    files = sorted(glob.glob(str(NEGATIVE_SRC / "*.wav")))
    print(f"Loading {len(files)} negative source recordings from {NEGATIVE_SRC}...")
    if not files:
        raise SystemExit(f"No .wav files found in {NEGATIVE_SRC} — run generate_negatives.py first.")

    all_windows: list[np.ndarray] = []
    for f in files:
        raw = _load_wav_int16(f)
        padded = np.concatenate([
            np.zeros(PAD_SAMPLES, dtype=np.int16), raw, np.zeros(PAD_SAMPLES, dtype=np.int16),
        ])
        all_windows.extend(_stream_clip_windows(padded))

    # Pure silence/low-noise negatives too — same random-noise character as
    # the streaming buffer's own init/reset seed, so the model also learns
    # this specific "background noise" texture is not the wake word.
    rng = np.random.default_rng(42)
    for _ in range(20):
        silence = rng.normal(0, 50, PAD_SAMPLES * 2 + SR).astype(np.int16)
        all_windows.extend(_stream_clip_windows(silence))

    result = np.stack(all_windows).astype(np.float32)
    print(f"Negative: {len(files)} synthesized clips + 20 silence/noise clips "
          f"-> {result.shape[0]} windowed training examples")
    return result


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pos, neg_from_pos = build_positive_features()
    neg = build_negative_features()
    neg = np.concatenate([neg, neg_from_pos], axis=0)

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
