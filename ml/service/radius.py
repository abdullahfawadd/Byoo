from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import AwareDatetime, model_validator

from pooling import Snapshot, density_band


class Evaluation(Snapshot):
    createdAt: AwareDatetime | None = None
    expiresAt: AwareDatetime | None = None
    now: AwareDatetime | None = None
    lastJoinAt: AwareDatetime | None = None
    sectorDensity: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    status: str = "FORMING"

    @model_validator(mode="after")
    def coherent_clock(self):
        if (self.createdAt is None) != (self.expiresAt is None):
            raise ValueError("supply createdAt and expiresAt together")
        if self.createdAt and self.expiresAt < self.createdAt:
            raise ValueError("expiresAt precedes createdAt")
        if self.lastJoinAt and self.createdAt and self.lastJoinAt < self.createdAt:
            raise ValueError("lastJoinAt precedes createdAt")
        return self


def evaluate(pool: Evaluation, probability: float):
    now = pool.now or datetime.now(timezone.utc)
    created = pool.createdAt or now - timedelta(hours=pool.elapsedHours)
    hard_cap = created + timedelta(hours=72)
    expiry = pool.expiresAt or now + timedelta(hours=pool.remainingHours)
    cutoff = min(expiry, hard_cap)
    remaining = (cutoff - now).total_seconds() / 3600
    fill = pool.currentQuantity / pool.targetMoq
    velocity = fill / max(.1, (now - created).total_seconds() / 3600)
    # Without a last-join timestamp, a still-open filled snapshot proves on-time
    # attainment. After the deadline the worker must supply evidence of an on-time join.
    joined_in_time = pool.lastJoinAt <= min(now, cutoff) if pool.lastJoinAt else now <= cutoff
    radius, step, proposed_cutoff = pool.currentRadiusKm, 0., cutoff
    decision = "NO_CHANGE_AWAITING_JOINS"
    reason = "The pool is awaiting further pledges."
    if pool.status != "FORMING":
        decision, reason = "NO_OP_NOT_FORMING", "Only forming pools are eligible for lifecycle evaluation."
    elif fill >= 1 and joined_in_time:
        decision, reason = "TRANSITIONED_TO_THRESHOLD_MET", "The latest qualifying pledge reached MOQ by the cutoff."
    elif remaining <= 0:
        decision, reason = "CANCELLED_EXPIRED", "The effective cutoff passed before on-time MOQ attainment."
    elif radius >= 10 and (probability < .35 or velocity < .15):
        decision, reason = "CANCELLED_MAX_RADIUS_UNVIABLE", "At 10 km, probability is below 0.35 or fill velocity is below 0.15 per hour."
    elif remaining <= 2 and radius < 10 and .35 <= probability < .85:
        density = pool.sectorDensity or density_band(pool.sector)
        step = 2. if fill < .50 and density == "LOW" else 1. if fill < .75 else .5
        radius = min(10., radius + step)
        proposed_cutoff = min(hard_cap, expiry + timedelta(hours=4))
        decision, reason = "RADIUS_EXPANDED", f"Within the last two hours, {fill:.0%} fill and {density.lower()} density select a {step:g} km step."
    return {
        "currentRadiusKm": pool.currentRadiusKm, "probability": probability, "stepKm": step,
        "proposedRadiusKm": radius, "expansionAllowed": decision == "RADIUS_EXPANDED",
        "cancellationRecommended": decision.startswith("CANCELLED_"), "decision": decision,
        "effectiveCutoff": cutoff.isoformat(), "proposedExpiresAt": proposed_cutoff.isoformat(),
        "explanation": [reason],
    }
