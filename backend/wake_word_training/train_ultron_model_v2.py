"""
train_ultron_model_v2.py — Train the custom "ultron" OpenWakeWord model on
the streaming-matched feature set (see prepare_data_streaming.py), exporting
to ultron_v2.onnx so the existing (known-broken) ultron.onnx is left intact
until this one is validated.

Differs from train_ultron_model.py in two ways beyond the input/output paths:

1. Reads features_streaming/ (built via the real chunked AudioFeatures path
   + RMS word-span labeling) instead of features/ (the old offline
   embed_clips() pipeline responsible for the train/inference mismatch
   documented in AUDIT_REPORT.md).

2. Class imbalance handling. The streaming pipeline only labels windows as
   positive when the full word has just finished streaming in (see
   prepare_data_streaming.py's _POST_WORD_FIRE_WINDOW_FRAMES) — a narrow
   slice of each clip's 80ms-chunked windows — versus every windowed chunk
   of every negative/silence clip. This produced 173 positive vs 10,634
   negative training windows (~61:1). Unweighted BCE over that imbalance
   lets the model minimize loss by mostly predicting "negative" — high
   accuracy, poor recall, not a real detector. Fixed with a
   WeightedRandomSampler that balances positive/negative sampling per
   epoch, and best-checkpoint selection by balanced accuracy
   ((recall + specificity) / 2) instead of raw accuracy, which is
   misleading under this imbalance.
"""

import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

from openwakeword.train import Model

HERE = Path(__file__).parent
FEATURES = HERE / "features_streaming"
OUTPUT_DIR = HERE.parent / "wake_word_models"
MODEL_NAME = "ultron_v2"

EPOCHS = 50
BATCH_SIZE = 64
LR = 0.0005


def load_split():
    pos_train = np.load(FEATURES / "positive_train.npy")
    neg_train = np.load(FEATURES / "negative_train.npy")
    pos_val = np.load(FEATURES / "positive_val.npy")
    neg_val = np.load(FEATURES / "negative_val.npy")

    X_train = np.concatenate([pos_train, neg_train], axis=0)
    y_train = np.concatenate([np.ones(len(pos_train)), np.zeros(len(neg_train))])

    X_val = np.concatenate([pos_val, neg_val], axis=0)
    y_val = np.concatenate([np.ones(len(pos_val)), np.zeros(len(neg_val))])

    return X_train, y_train, X_val, y_val


def evaluate(model: Model, X_val: torch.Tensor, y_val: torch.Tensor) -> dict:
    model.model.eval()
    with torch.no_grad():
        preds = model.model(X_val).squeeze(-1)
    pred_labels = (preds >= 0.5).float()

    pos_mask = y_val == 1
    neg_mask = y_val == 0

    tp = ((pred_labels == 1) & pos_mask).sum().item()
    fn = ((pred_labels == 0) & pos_mask).sum().item()
    tn = ((pred_labels == 0) & neg_mask).sum().item()
    fp = ((pred_labels == 1) & neg_mask).sum().item()

    recall = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    fp_rate = fp / (fp + tn) if (fp + tn) else 0.0
    accuracy = (tp + tn) / len(y_val) if len(y_val) else 0.0
    balanced_acc = (recall + specificity) / 2

    model.model.train()
    return {
        "recall": recall, "specificity": specificity, "fp_rate": fp_rate,
        "accuracy": accuracy, "balanced_acc": balanced_acc,
        "tp": tp, "fn": fn, "tn": tn, "fp": fp,
    }


def main():
    print("Loading streaming-matched prepared features...")
    X_train, y_train, X_val, y_val = load_split()
    print(f"Train: {X_train.shape[0]} examples ({int(y_train.sum())} positive, "
          f"{int((1 - y_train).sum())} negative) — imbalance ratio "
          f"{(1 - y_train).sum() / max(1, y_train.sum()):.1f}:1")
    print(f"Val:   {X_val.shape[0]} examples ({int(y_val.sum())} positive, "
          f"{int((1 - y_val).sum())} negative)")

    model = Model(n_classes=1, input_shape=(16, 96), model_type="dnn", layer_dim=128, n_blocks=2)
    model.optimizer = torch.optim.Adam(model.model.parameters(), lr=LR)

    X_train_t = torch.from_numpy(X_train).float()
    y_train_t = torch.from_numpy(y_train).float()
    X_val_t = torch.from_numpy(X_val).float()
    y_val_t = torch.from_numpy(y_val).float()

    # Balanced sampling: each epoch sees positive/negative examples with
    # roughly equal probability despite the ~61:1 raw imbalance.
    class_counts = np.array([len(y_train) - y_train.sum(), y_train.sum()])  # [neg, pos]
    class_weights = 1.0 / class_counts
    sample_weights = class_weights[y_train.astype(int)]
    sampler = WeightedRandomSampler(
        weights=torch.from_numpy(sample_weights).double(),
        num_samples=len(y_train),
        replacement=True,
    )

    loader = DataLoader(TensorDataset(X_train_t, y_train_t), batch_size=BATCH_SIZE, sampler=sampler)

    print(f"Training for {EPOCHS} epochs, batch size {BATCH_SIZE}, lr {LR}, "
          f"balanced sampling...")

    start = time.time()
    best_balanced_acc = -1.0
    best_state = None

    for epoch in range(1, EPOCHS + 1):
        epoch_loss = 0.0
        n_batches = 0
        for xb, yb in loader:
            model.optimizer.zero_grad()
            preds = model.model(xb).squeeze(-1)
            loss = model.loss(preds, yb)
            loss.backward()
            model.optimizer.step()
            epoch_loss += loss.item()
            n_batches += 1

        metrics = evaluate(model, X_val_t, y_val_t)
        print(
            f"Epoch {epoch:3d}/{EPOCHS}  loss={epoch_loss / n_batches:.4f}  "
            f"val_acc={metrics['accuracy']:.4f}  val_bal_acc={metrics['balanced_acc']:.4f}  "
            f"val_recall={metrics['recall']:.4f}  val_specificity={metrics['specificity']:.4f}  "
            f"(tp={metrics['tp']:.0f} fn={metrics['fn']:.0f} tn={metrics['tn']:.0f} fp={metrics['fp']:.0f})"
        )

        if metrics["balanced_acc"] > best_balanced_acc:
            best_balanced_acc = metrics["balanced_acc"]
            best_state = {k: v.clone() for k, v in model.model.state_dict().items()}

    elapsed = time.time() - start
    print(f"\nTraining complete in {elapsed:.1f}s ({elapsed/60:.1f} min)")

    model.model.load_state_dict(best_state)
    final_metrics = evaluate(model, X_val_t, y_val_t)
    print(f"\nBest checkpoint (by balanced accuracy) validation metrics: {final_metrics}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    onnx_path = OUTPUT_DIR / f"{MODEL_NAME}.onnx"
    model.export_to_onnx(str(onnx_path), class_mapping=MODEL_NAME)
    print(f"\nExported model to {onnx_path}")


if __name__ == "__main__":
    main()
