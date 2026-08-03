"""
train_ultron_model.py — Train a custom OpenWakeWord "ultron" model on the
locally-prepared feature set (see prepare_data.py).

Uses openwakeword.train.Model directly (the same architecture/export path
the library's own pretrained models use — verified the (16, 96) input shape
against the shipped hey_jarvis_v0.1.onnx) with a plain, transparent PyTorch
training loop rather than the library's auto_train()/train_model() harness,
which is tuned for much larger (tens-of-thousands-of-steps) datasets than
this scaled-down local one.
"""

import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from openwakeword.train import Model

HERE = Path(__file__).parent
FEATURES = HERE / "features"
OUTPUT_DIR = HERE.parent / "wake_word_models"
MODEL_NAME = "ultron"

EPOCHS = 30
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
    fp_rate = fp / (fp + tn) if (fp + tn) else 0.0
    accuracy = (tp + tn) / len(y_val) if len(y_val) else 0.0

    model.model.train()
    return {"recall": recall, "fp_rate": fp_rate, "accuracy": accuracy, "tp": tp, "fn": fn, "tn": tn, "fp": fp}


def main():
    print("Loading prepared features...")
    X_train, y_train, X_val, y_val = load_split()
    print(f"Train: {X_train.shape[0]} examples ({int(y_train.sum())} positive, "
          f"{int((1 - y_train).sum())} negative)")
    print(f"Val:   {X_val.shape[0]} examples ({int(y_val.sum())} positive, "
          f"{int((1 - y_val).sum())} negative)")

    model = Model(n_classes=1, input_shape=(16, 96), model_type="dnn", layer_dim=128, n_blocks=2)
    model.optimizer = torch.optim.Adam(model.model.parameters(), lr=LR)

    X_train_t = torch.from_numpy(X_train).float()
    y_train_t = torch.from_numpy(y_train).float()
    X_val_t = torch.from_numpy(X_val).float()
    y_val_t = torch.from_numpy(y_val).float()

    loader = DataLoader(TensorDataset(X_train_t, y_train_t), batch_size=BATCH_SIZE, shuffle=True)

    print(f"\nModel summary:\n{model.summary()}\n")
    print(f"Training for {EPOCHS} epochs, batch size {BATCH_SIZE}, lr {LR}...")

    start = time.time()
    best_val_acc = -1.0
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
            f"val_acc={metrics['accuracy']:.4f}  val_recall={metrics['recall']:.4f}  "
            f"val_fp_rate={metrics['fp_rate']:.4f}  "
            f"(tp={metrics['tp']:.0f} fn={metrics['fn']:.0f} tn={metrics['tn']:.0f} fp={metrics['fp']:.0f})"
        )

        if metrics["accuracy"] > best_val_acc:
            best_val_acc = metrics["accuracy"]
            best_state = {k: v.clone() for k, v in model.model.state_dict().items()}

    elapsed = time.time() - start
    print(f"\nTraining complete in {elapsed:.1f}s ({elapsed/60:.1f} min)")

    # Restore best checkpoint by validation accuracy before export
    model.model.load_state_dict(best_state)
    final_metrics = evaluate(model, X_val_t, y_val_t)
    print(f"\nBest checkpoint validation metrics: {final_metrics}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    onnx_path = OUTPUT_DIR / f"{MODEL_NAME}.onnx"
    model.export_to_onnx(str(onnx_path), class_mapping=MODEL_NAME)
    print(f"\nExported model to {onnx_path}")


if __name__ == "__main__":
    main()
