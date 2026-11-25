import hashlib
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, HTTPException, Query
from pydantic import ValidationError

from pooling import FEATURES, INPUTS, ML_DIR, MODEL_VERSION, Sector, Sku, Snapshot, features
from service.radius import Evaluation, evaluate


def describe(feature: str, value: float):
    labels = {
        "currentRadiusKm": ("Search radius", "km"), "currentQuantity": ("Current pledges", "units"),
        "targetMoq": ("Target quantity", "units"), "participantCount": ("Participating households", ""),
        "joinVelocity": ("Average fill velocity", "MOQ/hour"), "recentJoinVelocity": ("Recent fill velocity", "MOQ/hour"),
        "competingActivePools": ("Competing pools", ""), "elapsedHours": ("Time since creation", "hours"),
        "remainingHours": ("Time remaining", "hours"), "radiusExpansionsCount": ("Earlier radius expansions", ""),
        "weekday": ("Local weekday (Monday = 0)", ""), "hourOfDay": ("Local clock hour", ""),
        "sectorDensity": ("Sector density index", ""), "productDemand": ("Product demand index", ""),
        "averagePledge": ("Average pledge", "units"), "weekend": ("Weekend observation", ""),
        "evening": ("Evening observation", ""),
    }
    if feature in {"fillRatio", "lifecycleFraction"}:
        label = "Quantity already pledged" if feature == "fillRatio" else "Pool lifetime elapsed"
        return f"{label} ({value:.0%})"
    if feature.startswith(("sector_", "sku_")):
        label = "Sector" if feature.startswith("sector_") else "Product"
        return f"{label} indicator for {feature.split('_', 1)[1]} ({'present' if value else 'absent'})"
    label, unit = labels[feature]
    return f"{label} ({value:.3g}{' ' + unit if unit else ''})"


class Registry:
    def __init__(self, model_dir: Path):
        self.metadata = json.loads((model_dir / "metrics.json").read_text(encoding="utf-8"))
        model_file = model_dir / "xgboost.ubj"
        digest = hashlib.sha256(model_file.read_bytes()).hexdigest()
        if (digest != self.metadata["artifactSha256"][model_file.name]
                or self.metadata["features"] != FEATURES):
            raise ValueError("model checksum or feature registry mismatch")
        self.model = xgb.Booster(params={"nthread": 1})
        self.model.load_model(model_file)
        self.model.set_param({"nthread": 1})

    def predict(self, snapshots: list[Snapshot], explain=False):
        frame = features(pd.DataFrame([s.model_dump(include=set(INPUTS), mode="json") for s in snapshots]))
        matrix = xgb.DMatrix(frame, nthread=1)
        probabilities = self.model.predict(matrix)
        contributions = self.model.predict(matrix, pred_contribs=True) if explain else None
        predictions = []
        timestamp = datetime.now(timezone.utc).isoformat()
        for index, value in enumerate(probabilities):
            probability = float(value)
            explanation = []
            if contributions is not None:
                values = contributions[index, :-1]  # last entry is the baseline log-odds
                for n in np.argsort(-np.abs(values), kind="stable")[:3]:
                    direction = "increased" if values[n] > 0 else "decreased"
                    explanation.append(f"{describe(FEATURES[n], frame.iloc[index, n])} {direction} the estimated odds.")
            predictions.append({"probability": probability, "healthScore": round(probability * 100),
                                "modelVersion": self.metadata["modelVersion"], "timestamp": timestamp,
                                "explanation": explanation, "fallback": False})
        return predictions


@asynccontextmanager
async def lifespan(app):
    model_dir = Path(os.environ.get("BYOO_MODEL_DIR", ML_DIR / "models" / MODEL_VERSION))
    try:
        app.state.registry = Registry(model_dir)
    except (OSError, KeyError, ValueError, xgb.core.XGBoostError) as error:
        app.state.registry = None
        # Preserve the cause for service operators without exposing host paths to clients.
        logging.getLogger("uvicorn.error").error("Could not load Byoo model registry: %s", error)
    yield


app = FastAPI(title="Byoo pool viability", version="1.0.0", lifespan=lifespan)


def registry() -> Registry:
    loaded = getattr(app.state, "registry", None)
    if loaded is None:
        raise HTTPException(503, "The trained pool viability model is unavailable")
    return loaded


@app.get("/health")
def health():
    return {"status": "ok", "service": "byoo-ml"}


@app.get("/health/ready")
def ready():
    return {"status": "ready", "modelVersion": registry().metadata["modelVersion"]}


@app.get("/v1/ai/metrics")
def metrics():
    return registry().metadata


@app.post("/v1/ai/predict-viability")
def predict_viability(snapshot: Snapshot):
    return registry().predict([snapshot], explain=True)[0]


@app.post("/v1/ai/optimize-radius")
def optimize_radius(snapshot: Evaluation):
    prediction = registry().predict([snapshot])[0]
    return {**evaluate(snapshot, prediction["probability"]), "modelVersion": prediction["modelVersion"],
            "timestamp": prediction["timestamp"], "fallback": False}


def fetch_candidates():
    token = os.environ.get("INTERNAL_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = os.environ.get("API_URL", "http://localhost:4000").rstrip("/") + "/v1/ai/candidates"
    try:
        response = httpx.get(url, headers=headers, timeout=4)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            payload = payload.get("candidates", payload.get("data", payload.get("items")))
        if not isinstance(payload, list):
            raise ValueError("expected a candidate array")
        result = []
        for row in payload:
            data = row.get("features", row)
            snapshot = Snapshot.model_validate({key: data[key] for key in INPUTS})
            if not isinstance(row["poolId"], str) or not row["poolId"]:
                raise ValueError("invalid candidate pool ID")
            if snapshot.remainingHours > 0 and snapshot.currentQuantity < snapshot.targetMoq:
                result.append((row["poolId"], snapshot))
        return result
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, ValidationError) as err:
        raise HTTPException(503, "Current forming pool candidates are unavailable") from err


@app.get("/v1/ai/hot-opportunities")
def opportunities(sector: Sector | None = None, productSku: Sku | None = None,
                  limit: int = Query(5, ge=1, le=100)):
    engine = registry()
    pairs = [(pool_id, pool) for pool_id, pool in fetch_candidates()
             if (sector is None or pool.sector == sector) and (productSku is None or pool.productSku == productSku)]
    if not pairs:
        return []
    predictions = engine.predict([pool for _, pool in pairs])
    rows = [{"poolId": pool_id, "sector": pool.sector, "productSku": pool.productSku,
             **{key: pred[key] for key in ("probability", "healthScore", "modelVersion")}}
            for (pool_id, pool), pred in zip(pairs, predictions)]
    return sorted(rows, key=lambda row: (-row["probability"], row["poolId"]))[:limit]
