"""Generate one observable FORMING snapshot per independently simulated pool."""

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from pooling import DATA_DIR, DATASET_VERSION, DEMAND, DENSITY, DERIVED, INPUTS, MOQ, SEED, SPLITS, density_band, features

PKT = timezone(timedelta(hours=5))
STARTS = {"train": (datetime(2024, 1, 8, tzinfo=PKT), 210),
          "validation": (datetime(2024, 8, 12, tzinfo=PKT), 42),
          "test": (datetime(2024, 10, 1, tzinfo=PKT), 42)}
SHOPPING = np.array([.48, .33, .25, .23, .23, .29, .42, .68, .88, .97, 1.04, 1.08,
                     1.12, 1.09, 1.02, 1.05, 1.2, 1.46, 1.69, 1.82, 1.74, 1.51, 1.25, .81])


def simulate(rng, observed, pool_index):
    sector = rng.choice(list(DENSITY), p=[.16, .145, .14, .10, .13, .07, .075, .105, .075])
    sku = rng.choice(list(DEMAND), p=[.22, .23, .18, .13, .12, .12])
    moq = MOQ[sku]
    elapsed = 0 if rng.random() < .06 else int(rng.integers(1, 72))
    created = observed - timedelta(hours=elapsed)
    initial_deadline = int(rng.choice([48, 72], p=[.74, .26]))
    deadline = initial_deadline
    competitors = int(min(8, rng.poisson(1.5 * DENSITY[sector])))
    # Local shopper interest and a partially persistent daily shock are hidden simulator state.
    base = .68 * DENSITY[sector] * DEMAND[sku] / (1 + .105 * competitors)
    base *= rng.lognormal(-.08, .49)
    daily = rng.lognormal(-.055, .33, 3)
    hours = np.arange(72)
    hour = (hours + created.hour) % 24
    day = ((hours + created.hour) // 24 + created.weekday()) % 7
    base_rates = base * SHOPPING[hour] * np.where(day >= 5, 1.20, 1) * daily[hours // 24]
    radius, units, households, expansions = 2.5, 0, 0, 0
    quantities = []
    observation = None
    for age in range(73):
        if age == elapsed:
            if age >= deadline or units >= moq:
                return None
            observation = {
                "poolId": f"SYN-{pool_index:05d}", "createdAt": created.isoformat(),
                "observedAt": observed.isoformat(),
                "effectiveCutoff": (created + timedelta(hours=deadline)).isoformat(),
                "sector": str(sector), "productSku": str(sku), "currentRadiusKm": radius,
                "currentQuantity": units, "targetMoq": moq, "participantCount": households,
                "joinVelocity": (units / moq) / max(.1, elapsed),
                "recentJoinVelocity": sum(quantities[-2:]) / moq / max(1, min(2, elapsed)),
                "competingActivePools": competitors, "elapsedHours": elapsed,
                "remainingHours": deadline - elapsed, "radiusExpansionsCount": expansions,
                "weekday": observed.weekday(), "hourOfDay": observed.hour,
                "initialLifetimeHours": initial_deadline,
            }
        if units >= moq or age >= deadline:
            if observation is None:
                return None
            observation.update({"outcomeAt": (created + timedelta(hours=age)).isoformat(),
                                "finalQuantity": min(units, moq), "reachedMoq": int(units >= moq)})
            return observation
        # Illustrative historical operator, before observation only. Forecast labels condition
        # on keeping the AS-OF radius and cutoff fixed after the snapshot.
        if age < elapsed and age == deadline - 2:
            fill = units / moq
            if .28 <= fill < .95 and radius < 10:
                step = 2 if fill < .50 and density_band(str(sector)) == "LOW" else 1 if fill < .75 else .5
                radius = min(10., radius + step)
                expansions += 1
                deadline = min(72, deadline + 4)
        arrival_rate = base_rates[age] * (radius / 2.5) ** .55
        # Poisson thinning gives independent counts of households pledging 1, 2 or 3 units.
        singles, pairs, triples = rng.poisson(arrival_rate * PLEDGE_WEIGHTS)
        hourly_units = int(singles + 2 * pairs + 3 * triples)
        quantities.append(hourly_units)
        units += hourly_units
        households += int(singles + pairs + triples)
    raise AssertionError("trajectory exceeded the 72-hour cap")


PLEDGE_WEIGHTS = np.array([.67, .26, .07])


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(frame):
    metadata = {"poolId", "createdAt", "observedAt", "effectiveCutoff", "outcomeAt",
                "finalQuantity", "reachedMoq", "initialLifetimeHours", "split"}
    assert set(frame.columns) == set(INPUTS + DERIVED) | metadata
    assert len(frame) == sum(SPLITS.values()) and frame.poolId.is_unique
    assert frame.isna().sum().sum() == 0 and frame.observedAt.is_monotonic_increasing
    assert (frame.currentQuantity < frame.targetMoq).all()
    assert (frame.currentQuantity >= frame.participantCount).all()
    assert ((frame.elapsedHours + frame.remainingHours) <= 72).all()
    assert frame.currentRadiusKm.between(2.5, 10).all()
    assert ((frame.finalQuantity >= frame.targetMoq).astype(int) == frame.reachedMoq).all()
    assert (frame.outcomeAt <= frame.effectiveCutoff).all()
    assert (frame.observedAt < frame.outcomeAt).all()
    assert set(frame.sector) == set(DENSITY) and set(frame.productSku) == set(MOQ)
    assert np.allclose(frame.joinVelocity, frame.fillRatio / frame.elapsedHours.clip(lower=.1))
    assert np.allclose(frame[DERIVED], features(frame)[DERIVED])
    groups = [frame[frame.split == key] for key in SPLITS]
    assert [len(group) for group in groups] == list(SPLITS.values())
    assert all(set(group.reachedMoq.unique()) == {0, 1} for group in groups)
    for previous, following in zip(groups, groups[1:]):
        assert previous.outcomeAt.max() < following.createdAt.min()
    return {key: {"rows": len(group), "positive": int(group.reachedMoq.sum()),
                  "negative": int((group.reachedMoq == 0).sum()),
                  "firstObservation": group.observedAt.min(), "lastObservation": group.observedAt.max(),
                  "lastOutcome": group.outcomeAt.max()} for key, group in zip(SPLITS, groups)}


def generate(seed=SEED):
    rng = np.random.default_rng(seed)
    rows = []
    for split, count in SPLITS.items():
        start, days = STARTS[split]
        seconds = sorted(rng.integers(days * 86400, size=count))
        for offset in seconds:
            observed = start + timedelta(seconds=int(offset))
            row = None
            while row is None:
                row = simulate(rng, observed, len(rows) + 1)
            rows.append({**row, "split": split})
    frame = pd.DataFrame(rows)
    frame[DERIVED] = features(frame)[DERIVED]
    checks = validate(frame)
    synthetic, processed = DATA_DIR / "synthetic", DATA_DIR / "processed"
    synthetic.mkdir(exist_ok=True, parents=True)
    processed.mkdir(exist_ok=True, parents=True)
    raw = synthetic / "pool_lifecycle_14000"
    frame.to_csv(raw.with_suffix(".csv"), index=False, lineterminator="\n")
    frame.to_parquet(raw.with_suffix(".parquet"), index=False, compression="zstd")
    paths = [raw.with_suffix(".csv"), raw.with_suffix(".parquet")]
    for split in SPLITS:
        path = processed / f"{split}.csv"
        frame[frame.split == split].to_csv(path, index=False, lineterminator="\n")
        paths.append(path)
    manifest = {"datasetVersion": DATASET_VERSION, "seed": seed, "rows": len(frame),
                "missingValues": int(frame.isna().sum().sum()), "uniquePools": frame.poolId.nunique(),
                "splits": checks, "sha256": {p.relative_to(DATA_DIR).as_posix(): sha256(p) for p in paths}}
    (synthetic / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=SEED)
    generate(parser.parse_args().seed)
