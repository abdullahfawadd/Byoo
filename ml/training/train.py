"""Tune on validation, then score the frozen candidates once on the temporal holdout."""

import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import version

import joblib
import numpy as np
import pandas as pd
import xgboost
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss,
                             confusion_matrix, f1_score, precision_recall_curve,
                             precision_score, recall_score, roc_auc_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from pooling import DATA_DIR, DATASET_VERSION, FEATURES, ML_DIR, MODEL_VERSION, SEED, SPLITS, features
from training.generate import sha256, validate

MODEL_DIR = ML_DIR / "models" / MODEL_VERSION


def candidates():
    return {
        "logistic": [
            ({"C": c}, make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=1500, random_state=SEED)))
            for c in [.1, 1., 10.]
        ],
        "randomForest": [
            ({"maxDepth": depth, "minLeaf": leaf},
             RandomForestClassifier(n_estimators=100, max_depth=depth, min_samples_leaf=leaf,
                                    n_jobs=2, random_state=SEED))
            for depth, leaf in [(6, 12), (10, 8), (14, 5)]
        ],
        "xgboost": [
            ({"maxDepth": depth, "nEstimators": trees, "learningRate": rate},
             XGBClassifier(max_depth=depth, n_estimators=trees, learning_rate=rate,
                           objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                           min_child_weight=5, subsample=.85, colsample_bytree=.90,
                           n_jobs=2, random_state=SEED))
            for depth, trees, rate in [(2, 180, .06), (3, 150, .055), (4, 120, .05)]
        ],
    }


def scores(y, probability, threshold):
    pred = probability >= threshold
    intervals = np.minimum((probability * 10).astype(int), 9)
    bins, ece = [], 0.
    for i in range(10):
        mask = intervals == i
        count = int(mask.sum())
        observed = float(np.mean(y[mask])) if count else None
        mean = float(np.mean(probability[mask])) if count else None
        if count:
            ece += count / len(y) * abs(mean - observed)
        bins.append({"lower": i / 10, "upper": (i + 1) / 10, "count": count,
                     "meanProbability": mean, "observedPositiveRate": observed})
    return {
        "rocAuc": float(roc_auc_score(y, probability)),
        "prAuc": float(average_precision_score(y, probability)),
        "accuracy": float(accuracy_score(y, pred)), "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)), "f1": float(f1_score(y, pred, zero_division=0)),
        "confusionMatrix": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
        "brierScore": float(brier_score_loss(y, probability)), "calibration": bins,
        "expectedCalibrationError": float(ece), "n": len(y),
    }


def tune(key, options, x, y, xval, yval):
    best, trials = None, []
    for params, model in options:
        model.fit(x, y)
        prob = model.predict_proba(xval)[:, 1]
        auc = float(roc_auc_score(yval, prob))
        trials.append({"parameters": params, "validationRocAuc": auc})
        if best is None or auc > best[0]:
            best = (auc, model, params, prob)
    _, model, params, prob = best
    precision, recall, thresholds = precision_recall_curve(yval, prob)
    val_f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    threshold = float(thresholds[np.argmax(val_f1)])
    importance = (np.abs(model[-1].coef_[0]) if key == "logistic" else model.feature_importances_)
    total = float(importance.sum())
    ranking = sorted(zip(FEATURES, importance), key=lambda pair: -pair[1])
    card = {"selectedParameters": params, "validationTrials": trials, "classificationThreshold": threshold,
            "validation": scores(yval, prob, threshold),
            "featureImportance": [{"feature": name, "weight": float(weight) / total} for name, weight in ranking]}
    return model, card


def train():
    manifest = json.loads((DATA_DIR / "synthetic" / "manifest.json").read_text(encoding="utf-8"))
    if manifest["datasetVersion"] != DATASET_VERSION or manifest["seed"] != SEED:
        raise ValueError("canonical training requires the registered data version and seed")
    for relative, expected in manifest["sha256"].items():
        if sha256(DATA_DIR / relative) != expected:
            raise ValueError(f"dataset checksum mismatch: {relative}")
    frames = {key: pd.read_csv(DATA_DIR / "processed" / f"{key}.csv") for key in SPLITS}
    validate(pd.concat(frames.values(), ignore_index=True))
    x, xv = features(frames["train"]), features(frames["validation"])
    y, yv = frames["train"].reachedMoq.to_numpy(), frames["validation"].reachedMoq.to_numpy()
    fitted = {key: tune(key, options, x, y, xv, yv) for key, options in candidates().items()}
    xt, yt = features(frames["test"]), frames["test"].reachedMoq.to_numpy()
    MODEL_DIR.mkdir(exist_ok=True, parents=True)
    cards, artifacts = {}, {}
    for key, (model, card) in fitted.items():
        probabilities = model.predict_proba(xt)[:, 1]
        card["holdout"] = scores(yt, probabilities, card["classificationThreshold"])
        path = MODEL_DIR / (key + (".ubj" if key == "xgboost" else ".joblib"))
        if key == "xgboost":
            model.save_model(path)
        else:
            joblib.dump(model, path, compress=3)
        artifacts[path.name] = sha256(path)
        cards[key] = card
    result = {
        "modelVersion": MODEL_VERSION, "datasetVersion": DATASET_VERSION, "seed": SEED,
        "trainedAt": datetime.now(timezone.utc).isoformat(), "servingModel": "xgboost",
        "trainingData": "independent synthetic Islamabad pools", "features": FEATURES,
        "splitSizes": SPLITS, "splits": manifest["splits"], "models": cards,
        "featureImportance": cards["xgboost"]["featureImportance"], "artifactSha256": artifacts,
        "datasetSha256": manifest["sha256"], "packages": {"xgboost": xgboost.__version__,
            **{k: version(k) for k in ["numpy", "pandas", "scikit-learn", "pyarrow", "joblib"]}},
        "featureContractSha256": hashlib.sha256((ML_DIR / "pooling.py").read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
    }
    (MODEL_DIR / "metrics.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("Model           ROC-AUC    Avg precision    F1       Brier    Holdout N")
    for key, card in cards.items():
        m = card["holdout"]
        print(f"{key:<14}  {m['rocAuc']:.4f}     {m['prAuc']:.4f}          {m['f1']:.4f}   {m['brierScore']:.4f}   {m['n']}")


if __name__ == "__main__":
    train()
