import csv
from pathlib import Path
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

DATA_PATH = Path(__file__).parent / "data" / "labeled_transactions.csv"
CONFIDENCE_THRESHOLD = 0.3
UNCATEGORIZED = "Uncategorized"

_pipeline: Optional[Pipeline] = None


def _load_training_data() -> tuple[list[str], list[str]]:
    merchants, categories = [], []
    with DATA_PATH.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            merchants.append(row["merchant"])
            categories.append(row["category"])
    return merchants, categories


def train_classifier() -> Pipeline:
    """Fit the merchant->category pipeline on the bundled seed dataset and
    cache it in memory. Called once at API startup."""
    global _pipeline
    merchants, categories = _load_training_data()
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=2000, C=5)),
    ])
    pipeline.fit(merchants, categories)
    _pipeline = pipeline
    return pipeline


def predict_category(merchant: str) -> tuple[str, float]:
    """Predict a category for a merchant string. Falls back to
    'Uncategorized' when the model isn't confident, rather than forcing a
    low-confidence guess."""
    if _pipeline is None:
        train_classifier()

    probabilities = _pipeline.predict_proba([merchant])[0]
    best_index = probabilities.argmax()
    confidence = float(probabilities[best_index])

    if confidence < CONFIDENCE_THRESHOLD:
        return UNCATEGORIZED, confidence

    label = _pipeline.classes_[best_index]
    return label, confidence
