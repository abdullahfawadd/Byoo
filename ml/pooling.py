"""Observation-time inputs shared by the simulator and online inference."""

from enum import StrEnum
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR.parent / "data"
DATASET_VERSION = "isb-pools-synthetic-v1"
MODEL_VERSION = "xgb-isb-v1"
SEED = 42
SPLITS = {"train": 10000, "validation": 2000, "test": 2000}


class Sector(StrEnum):
    G9 = "G-9"
    G10 = "G-10"
    G11 = "G-11"
    F10 = "F-10"
    I8 = "I-8"
    F7 = "F-7"
    F8 = "F-8"
    E11 = "E-11"
    BLUE = "BLUE_AREA"


class Sku(StrEnum):
    RICE = "RICE-5KG"
    ATTA = "ATTA-10KG"
    OIL = "OIL-5L"
    TEA = "TEA-900G"
    GHEE = "GHEE-5KG"
    DAAL = "DAAL-5KG"


# Scenario priors for the simulation, not census or sales estimates.
DENSITY = {"G-9": 1.24, "G-10": 1.16, "G-11": 1.14, "F-10": 0.97,
           "I-8": 1.12, "F-7": 0.93, "F-8": 0.96, "E-11": 0.80, "BLUE_AREA": 0.69}
DEMAND = {"RICE-5KG": 1.14, "ATTA-10KG": 1.24, "OIL-5L": 1.08,
          "TEA-900G": 0.94, "GHEE-5KG": 0.87, "DAAL-5KG": 0.90}
MOQ = {"RICE-5KG": 40, "ATTA-10KG": 60, "OIL-5L": 50,
       "TEA-900G": 50, "GHEE-5KG": 40, "DAAL-5KG": 40}


def density_band(sector: str) -> str:
    density = DENSITY[sector]
    return "LOW" if density < 0.9 else "HIGH" if density >= 1.1 else "MEDIUM"


class Snapshot(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    sector: Sector
    productSku: Sku
    currentRadiusKm: float = Field(ge=2.5, le=10)
    currentQuantity: int = Field(ge=0)
    targetMoq: int = Field(gt=0)
    participantCount: int = Field(ge=0)
    joinVelocity: float = Field(ge=0)
    recentJoinVelocity: float = Field(ge=0)
    competingActivePools: int = Field(ge=0)
    elapsedHours: float = Field(ge=0)
    # A worker can evaluate an overdue pool. Radius evaluation handles that case first.
    remainingHours: float
    radiusExpansionsCount: int = Field(ge=0)
    weekday: int = Field(ge=0, le=6)
    hourOfDay: int = Field(ge=0, le=23)

    @model_validator(mode="after")
    def finite_pledges(self):
        if self.participantCount > self.currentQuantity:
            raise ValueError("participantCount cannot exceed pledged units")
        return self


INPUTS = list(Snapshot.model_fields)
DERIVED = ["sectorDensity", "productDemand", "fillRatio", "averagePledge",
           "weekend", "evening", "lifecycleFraction"]
NUMERIC = INPUTS[2:] + DERIVED
FEATURES = NUMERIC + [f"sector_{key}" for key in DENSITY] + [f"sku_{key}" for key in DEMAND]


def features(frame: pd.DataFrame) -> pd.DataFrame:
    """Use this exact column order and transformation for all three estimators."""
    result = frame[INPUTS[2:]].copy()
    elapsed = frame.elapsedHours
    remaining = frame.remainingHours.clip(lower=0)
    result["remainingHours"] = remaining
    result["sectorDensity"] = frame.sector.map(DENSITY)
    result["productDemand"] = frame.productSku.map(DEMAND)
    result["fillRatio"] = frame.currentQuantity / frame.targetMoq
    result["joinVelocity"] = result.fillRatio / elapsed.clip(lower=.1)
    result["averagePledge"] = frame.currentQuantity / frame.participantCount.clip(lower=1)
    result["weekend"] = frame.weekday >= 5
    result["evening"] = frame.hourOfDay.between(17, 22)
    result["lifecycleFraction"] = elapsed / (elapsed + remaining).clip(lower=0.1)
    for sector in DENSITY:
        result[f"sector_{sector}"] = frame.sector == sector
    for sku in DEMAND:
        result[f"sku_{sku}"] = frame.productSku == sku
    result = result[FEATURES].astype("float32")
    if not np.isfinite(result.to_numpy()).all():
        raise ValueError("observation produced missing or non-finite model features")
    return result
