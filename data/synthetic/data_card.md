# Synthetic Islamabad buying pools

The `isb-pools-synthetic-v1` release contains 14,000 independent observations generated with NumPy seed 42. It supports offline comparisons of MOQ forecasts and a reproducible local demo. Every pool, household arrival, and pledge is simulated. The files contain no personally identifiable information.

## Simulation

The generator samples one of nine Islamabad sectors and one of six packaged grocery SKUs, then assigns a 48- or 72-hour initial deadline. Each pool receives a hidden demand level, day-specific variation and a number of competing pools. Hourly Poisson arrivals respond to those variables, sector density, SKU demand, evening and weekend peaks, and the current radius. Households pledge one, two or three units with probabilities 0.67, 0.26 and 0.07. Sector and SKU weights are scenario assumptions. They have no census, survey or sales-data provenance.

The observation schedule includes new and partially filled pools. The simulator discards trajectories already closed at observation. A historical operator can expand still-forming pools near a prior expiry, moving the deadline by up to four hours within the 72-hour cap. The simulator freezes radius and cutoff at observation, draws remaining arrivals, and records whether the pool reaches MOQ. This estimates success under the current conditions. The operational worker separately evaluates BR-05, which may intervene later. Completing checkout, settlement, handover, and dispute resolution are separate business outcomes.

## Splits and audit

| Partition | Observations | Observation window (PKT, end exclusive) | Purpose |
|---|---:|---|---|
| Training | 10,000 | 2024-01-08 to 2024-08-05 | Fit parameters and the logistic scaler |
| Validation | 2,000 | 2024-08-12 to 2024-09-23 | Choose hyperparameters and classification thresholds |
| Test | 2,000 | 2024-10-01 to 2024-11-12 | Score frozen models |

Each pool occurs once. Embargo gaps ensure all outcomes in an earlier partition are known before any pool in the following partition is created. Identifiers, final outcomes, raw timestamps and split information are excluded from model inputs. The generator checks schema-derived features, timestamps, class presence, radius and lifetime limits, duplicate IDs and missing cells. The release manifest records actual split boundaries, label counts, missing-value counts and SHA-256 hashes of both full files and all three split CSVs. [Release manifest](manifest.json)

## Interpretation

The simulator encodes assumed density and demand patterns, so held-out measurements establish performance only for this scenario. The generated population is conditional on a pool still forming. The generative process omits household correlations, changes in competition during a pool's life, late checkout reversals, and feedback from future expansion. It cannot estimate the causal effect of widening a radius. Collect timestamped production snapshots with their as-of covariates and resolved on-time MOQ labels before evaluating real-world validity or recalibrating probabilities.

The generation, training, registry and test commands are in the ML service guide. [Service guide](../../ml/README.md)
