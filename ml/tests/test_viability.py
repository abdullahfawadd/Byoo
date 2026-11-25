import hashlib
import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pooling import DATA_DIR, DERIVED, FEATURES, INPUTS, ML_DIR, MODEL_VERSION, Snapshot, features
from service import main
from service.radius import Evaluation, evaluate
from training.generate import validate
from training.train import scores


@pytest.fixture
def snapshot():
    return dict(sector="G-9", productSku="RICE-5KG", currentRadiusKm=2.5,
                currentQuantity=12, targetMoq=40, participantCount=8, joinVelocity=.03,
                recentJoinVelocity=.025, competingActivePools=2, elapsedHours=10.,
                remainingHours=38., radiusExpansionsCount=0, weekday=2, hourOfDay=18)


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


def test_data_and_splits():
    raw = DATA_DIR / "synthetic"
    manifest = json.loads((raw / "manifest.json").read_text())
    for name, expected in manifest["sha256"].items():
        assert hashlib.sha256((DATA_DIR / name).read_bytes()).hexdigest() == expected
    csv = pd.read_csv(raw / "pool_lifecycle_14000.csv")
    parquet = pd.read_parquet(raw / "pool_lifecycle_14000.parquet")
    pd.testing.assert_frame_equal(csv, parquet, check_dtype=False)
    assert validate(csv) == manifest["splits"]
    assert not set(FEATURES) & {"poolId", "split", "createdAt", "observedAt", "effectiveCutoff",
                                "outcomeAt", "finalQuantity", "reachedMoq"}
    assert np.allclose(csv[DERIVED], features(csv)[DERIVED])


def test_registry_reproduces_holdout(client):
    metadata = client.get("/v1/ai/metrics").json()
    holdout = pd.read_csv(DATA_DIR / "processed" / "test.csv")
    expected = metadata["models"]["xgboost"]
    batch = [Snapshot.model_validate(row) for row in holdout[INPUTS].to_dict("records")]
    probabilities = np.array([v["probability"] for v in main.registry().predict(batch)])
    observed = scores(holdout.reachedMoq.to_numpy(), probabilities, expected["classificationThreshold"])
    for key in ["rocAuc", "prAuc", "accuracy", "precision", "recall", "f1", "brierScore"]:
        assert observed[key] == pytest.approx(expected["holdout"][key], abs=1e-7)
    assert observed["confusionMatrix"] == expected["holdout"]["confusionMatrix"]
    assert set(metadata["models"]) == {"logistic", "randomForest", "xgboost"}


def test_api_and_validation(client, snapshot):
    assert client.get("/health").status_code == client.get("/health/ready").status_code == 200
    response = client.post("/v1/ai/predict-viability", json=snapshot)
    assert response.status_code == 200
    result = response.json()
    assert 0 <= result["probability"] <= 1 and result["healthScore"] == round(100 * result["probability"])
    assert result["modelVersion"] == MODEL_VERSION and result["fallback"] is False
    assert len(result["explanation"]) == 3
    assert client.post("/v1/ai/optimize-radius", json=snapshot).json()["decision"] == "NO_CHANGE_AWAITING_JOINS"
    for change in [{"productSku": "UNKNOWN"}, {"sector": "G-99"}, {"participantCount": 30},
                   {"targetMoq": 0}, {"hourOfDay": 24}, {"currentRadiusKm": 10.5}]:
        assert client.post("/v1/ai/predict-viability", json=snapshot | change).status_code == 422


@pytest.mark.parametrize(("updates", "p", "expected", "step", "radius"), [
    ({"remainingHours": 2, "sectorDensity": "LOW"}, .35, "RADIUS_EXPANDED", 2, 4.5),
    ({"remainingHours": 2, "currentQuantity": 20}, .84, "RADIUS_EXPANDED", 1, 3.5),
    ({"remainingHours": 1, "currentQuantity": 30, "currentRadiusKm": 9.8}, .84, "RADIUS_EXPANDED", .5, 10),
    ({"remainingHours": 2}, .85, "NO_CHANGE_AWAITING_JOINS", 0, 2.5),
    ({"remainingHours": 2.001}, .5, "NO_CHANGE_AWAITING_JOINS", 0, 2.5),
    ({"currentRadiusKm": 10.}, .99, "CANCELLED_MAX_RADIUS_UNVIABLE", 0, 10),
    ({"currentRadiusKm": 10., "elapsedHours": 1}, .34, "CANCELLED_MAX_RADIUS_UNVIABLE", 0, 10),
    ({"currentRadiusKm": 10., "elapsedHours": 2}, .35, "NO_CHANGE_AWAITING_JOINS", 0, 10),
    ({"remainingHours": 0, "currentRadiusKm": 10.}, .01, "CANCELLED_EXPIRED", 0, 10),
    ({"remainingHours": -1, "status": "DISPATCHED"}, .01, "NO_OP_NOT_FORMING", 0, 2.5),
])
def test_radius_bounds(snapshot, updates, p, expected, step, radius):
    result = evaluate(Evaluation(**(snapshot | updates)), p)
    assert (result["decision"], result["stepKm"], result["proposedRadiusKm"]) == (expected, step, radius)


def test_cutoff_precedence(snapshot):
    data = snapshot | dict(createdAt="2024-01-01T00:00:00Z", expiresAt="2024-01-04T12:00:00Z",
                           now="2024-01-04T00:01:00Z", lastJoinAt="2024-01-04T00:00:00Z", currentQuantity=40)
    assert evaluate(Evaluation(**data), .01)["decision"] == "TRANSITIONED_TO_THRESHOLD_MET"
    assert evaluate(Evaluation(**(data | {"lastJoinAt": "2024-01-04T00:00:01Z"})), .99)["decision"] == "CANCELLED_EXPIRED"
    future = data | dict(now="2024-01-03T23:00:00Z", currentQuantity=20, lastJoinAt=None)
    assert evaluate(Evaluation(**future), .5)["proposedExpiresAt"] == "2024-01-04T00:00:00+00:00"
    with pytest.raises(ValidationError):
        Evaluation(**(future | {"now": "2024-01-03T23:00:00"}))


def test_opportunities_from_candidates(client, snapshot, monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return [{"poolId": "p2", **snapshot}, {"poolId": "p1", "features": snapshot},
                    {"poolId": "expired", **snapshot, "remainingHours": 0}]

    def get(url, headers, timeout):
        assert url == "http://internal-api/v1/ai/candidates"
        assert headers["Authorization"] == "Bearer test-token"
        return Response()

    monkeypatch.setenv("API_URL", "http://internal-api")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-token")
    monkeypatch.setattr(main.httpx, "get", get)
    rows = client.get("/v1/ai/hot-opportunities").json()
    assert [r["poolId"] for r in rows] == ["p1", "p2"]
    assert client.get("/v1/ai/hot-opportunities?sector=E-11").json() == []
    assert len(client.get("/v1/ai/hot-opportunities?limit=1").json()) == 1


def test_unavailable_model(monkeypatch, tmp_path, snapshot):
    monkeypatch.setenv("BYOO_MODEL_DIR", str(tmp_path))
    with TestClient(main.app) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/health/ready").status_code == c.post("/v1/ai/predict-viability", json=snapshot).status_code == 503
