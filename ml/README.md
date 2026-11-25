# Byoo pool viability

Run these commands from the `ml` directory with Python 3.12 and uv. The service loads the checked-in XGBoost artifact. Training is a separate offline operation.

```sh
uv sync --locked
uv run --locked uvicorn service.main:app --host 127.0.0.1 --port 8000
```

Set `API_URL` to the Node backend origin, which defaults to `http://localhost:4000`. Supply its matching `INTERNAL_API_TOKEN` when candidate reads require a bearer token. The service reads environment variables from its process. For example, `uv run --env-file ../.env uvicorn service.main:app --port 8000` loads the local development values. Bind the service on a private network for hosting. The gateway owns end-user authorization and operational state transitions.

## Reproduce the release

```sh
uv run --locked python -m training.generate --seed 42
uv run --locked python -m training.train
uv run --locked pytest -q
```

The generator writes CSV and Parquet, split files and a checksum manifest. Training verifies checksums, fits a standardized logistic regression, random forest and XGBoost on the training split, compares three configurations per model by validation ROC-AUC, then selects each classification threshold by validation F1. All models and thresholds are frozen before holdout scoring. XGBoost supplies the service probability. BR-05 uses the separate 0.35 and 0.85 policy boundaries. [Dataset card](../data/synthetic/data_card.md)

The model directory holds XGBoost's portable UBJSON booster, the fitted logistic and random forest joblib files, ordered feature names, dependency versions, artifact hashes, class counts, validation trials, thresholds, synthetic validation and holdout results. Feature importance uses normalized absolute standardized coefficients for logistic, impurity reduction for forest, and gain for XGBoost. Prediction explanations use the three largest absolute local XGBoost log-odds contributions. These describe the fitted model's calculation and do not establish causation. [Model registry](models/xgb-isb-v1/metrics.json)

For each model, PR-AUC is average precision. The confusion matrix is arranged as `[[TN, FP], [FN, TP]]`, and all reported precision, recall and F1 values treat attainment as positive. Calibration uses ten equal-width probability bins, reporting each bin's count, mean predicted probability and observed positive rate. Brier score is mean squared probability error. The tests also load the exported booster and independently reproduce its holdout scores.

## HTTP

| Route | Behavior |
|---|---|
| GET /health | Process liveness |
| GET /health/ready | 200 with loaded model version, 503 if the registry cannot load |
| POST /v1/ai/predict-viability | Observation inputs to probability, 0–100 health score, explanation, UTC timestamp and model version |
| POST /v1/ai/optimize-radius | Observation inputs plus optional explicit clocks and sector density to a BR-05 advisory decision |
| GET /v1/ai/hot-opportunities | Scores current forming candidates read from the backend, ranks by probability, breaks ties by pool ID and returns the top five by default. Optional sector, productSku and limit (1–100). Upstream failures return 503. |
| GET /v1/ai/metrics | Release metadata, validation and holdout results, calibration and feature importance |

```json
{
  "sector": "G-9", "productSku": "RICE-5KG", "currentRadiusKm": 2.5,
  "currentQuantity": 12, "targetMoq": 40, "participantCount": 8,
  "joinVelocity": 0.03, "recentJoinVelocity": 0.025, "competingActivePools": 2,
  "elapsedHours": 10, "remainingHours": 38, "radiusExpansionsCount": 0,
  "weekday": 2, "hourOfDay": 18
}
```

For operational radius evaluation supply timezone-aware `createdAt`, `expiresAt`, `now`, and `lastJoinAt` whenever available. An elapsed cutoff requires a qualifying last-join timestamp to recommend threshold attainment. The strict cutoff is the earlier of the stored expiry and creation plus 72 hours. The evaluator tests on-time MOQ, expiry and unconditional max-radius cancellation in that order, followed by the two-hour expansion window. `stepKm` is the selected 0.5, 1.0 or 2.0 km policy step and `proposedRadiusKm` is the capped result. The worker verifies the live row under lock and applies any transaction and refunds.

Use `BYOO_MODEL_DIR` to select another compatible artifact registry. Failed model loads make readiness and prediction return 503. The Node gateway can explicitly mark its fallback estimate with `fallback: true`. Hot opportunities depend on live candidates and never substitute historical training examples.

For a service-only Linux image, run `docker build -t byoo-ml .` from this directory. Dataset release files are required for training and verification only.
