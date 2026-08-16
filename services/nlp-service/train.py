"""
NLP Service — DistilBERT Fine-tuning Script
Doc 4.1.1: Fine-tune distilbert-base-uncased on phishing email datasets

Data expected at:
  data/raw/prepared/phishing/     ← phishing emails (label=1)
  data/raw/prepared/legitimate/   ← legitimate emails (label=0)

Run: python train.py
Output: models/phishing_distilbert/
"""

import os
import json
import glob
import argparse
from pathlib import Path

import torch
import numpy as np
from torch.utils.data import Dataset
from transformers import (
    DistilBertTokenizerFast,
    DistilBertForSequenceClassification,
    TrainingArguments,
    Trainer,
)
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from app.preprocessor.clean import clean

# ─── Paths ────────────────────────────────────────────────────
DATA_DIR = Path("data/raw/prepared")
MODEL_OUT = Path("models/phishing_distilbert")
MODEL_NAME = "distilbert-base-uncased"
MAX_LENGTH = 512           # doc 4.1.1: truncated to 512 tokens


# ─── Dataset ──────────────────────────────────────────────────
class PhishingDataset(Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


# ─── Load Data ────────────────────────────────────────────────
def load_data(data_dir: Path):
    texts, labels = [], []

    phishing_dir = data_dir / "phishing"
    legit_dir = data_dir / "legitimate"

    if not phishing_dir.exists() or not legit_dir.exists():
        print(f"Data not found at {data_dir}")
        print("Run: python data/prepare.py first")
        return [], []

    for path in phishing_dir.glob("*.txt"):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                texts.append(clean(f.read()))
                labels.append(1)
        except Exception:
            continue

    for path in legit_dir.glob("*.txt"):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                texts.append(clean(f.read()))
                labels.append(0)
        except Exception:
            continue

    print(f"Loaded {labels.count(1)} phishing, {labels.count(0)} legitimate samples")
    return texts, labels


# ─── Metrics ──────────────────────────────────────────────────
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    probs = torch.softmax(torch.tensor(logits), dim=-1).numpy()[:, 1]

    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, preds, average="binary"
    )
    acc = accuracy_score(labels, preds)
    try:
        auc = roc_auc_score(labels, probs)
    except Exception:
        auc = 0.0

    return {
        "accuracy": round(acc, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "auc": round(auc, 4),
    }


# ─── Main ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    args = parser.parse_args()

    texts, labels = load_data(DATA_DIR)
    if not texts:
        return

    print(f"Total: {len(texts)} samples")

    train_texts, val_texts, train_labels, val_labels = train_test_split(
        texts, labels, test_size=0.15, random_state=42, stratify=labels
    )
    print(f"Train: {len(train_texts)} | Val: {len(val_texts)}")

    print("Tokenising...")
    tokenizer = DistilBertTokenizerFast.from_pretrained(MODEL_NAME)

    train_enc = tokenizer(
        train_texts, truncation=True, padding=True, max_length=MAX_LENGTH
    )
    val_enc = tokenizer(
        val_texts, truncation=True, padding=True, max_length=MAX_LENGTH
    )

    train_dataset = PhishingDataset(train_enc, train_labels)
    val_dataset = PhishingDataset(val_enc, val_labels)

    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=2
    )

    MODEL_OUT.mkdir(parents=True, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=str(MODEL_OUT),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.lr,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_dir="logs",
        logging_steps=50,
        warmup_steps=100,
        weight_decay=0.01,
        fp16=torch.cuda.is_available(),
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
    )

    print("Training...")
    trainer.train()

    metrics = trainer.evaluate()
    print("Eval metrics:", json.dumps(metrics, indent=2))

    trainer.save_model(str(MODEL_OUT))
    tokenizer.save_pretrained(str(MODEL_OUT))
    print(f"Model saved to {MODEL_OUT}")

    with open(MODEL_OUT / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)


if __name__ == "__main__":
    main()