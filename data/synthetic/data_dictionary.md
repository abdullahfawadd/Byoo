# Pool snapshot data dictionary

CSV and Parquet use the same columns. Each row describes one independently simulated Islamabad buying pool while it was forming. CSV timestamps include the Pakistan Standard Time offset (+05:00). The model reads the observation inputs listed below and recomputes their derived features with the same function used by the online service.

| Column | Type / unit | Definition |
|---|---|---|
| poolId | string | Unique synthetic identifier for one simulated trajectory. Metadata only. |
| createdAt | timestamp | Pool creation time. Metadata for temporal checks. |
| observedAt | timestamp | Time of the observation. Determines split assignment. |
| effectiveCutoff | timestamp | Expiry known at observation, capped at creation plus 72 hours. |
| sector | category | G-9, G-10, G-11, F-10, I-8, F-7, F-8, E-11, or BLUE_AREA. One-hot encoded. |
| productSku | category | RICE-5KG, ATTA-10KG, OIL-5L, TEA-900G, GHEE-5KG, or DAAL-5KG. One-hot encoded. |
| currentRadiusKm | km | Spatial reach at observation, initially 2.5 km and capped at 10 km. |
| currentQuantity | units | Total pledged units at observation. Every training snapshot is below MOQ. |
| targetMoq | units | SKU minimum order quantity, respectively 40, 60, 50, 50, 40, 40 in the SKU order above. |
| participantCount | households | Number of distinct participating households observed so far. Each simulated household contributes one pledge. |
| joinVelocity | fraction of MOQ per hour | Current fill ratio divided by the larger of 0.1 and hours since creation. |
| recentJoinVelocity | fraction of MOQ per hour | Units pledged in the preceding two hours divided by MOQ and the observed window length. A pool with no history has value zero. |
| competingActivePools | count | Simulated surrounding pools competing for household demand at observation. |
| elapsedHours | hours | Time from creation through observation. The generator advances in hourly intervals. |
| remainingHours | hours | Time from observation to its effective cutoff. |
| radiusExpansionsCount | count | Prior simulated expansions, through observation. |
| weekday | integer 0–6 | Monday is zero. Based on local observation time. |
| hourOfDay | integer 0–23 | Local observation hour. |
| initialLifetimeHours | hours | Original 48- or 72-hour lifespan. Stored to audit the simulator. |
| sectorDensity | relative index | Fixed scenario prior for local shopping density. Higher values raise simulated arrival rates. |
| productDemand | relative index | Fixed SKU popularity prior used by the scenario. |
| fillRatio | fraction | Current quantity divided by target MOQ. |
| averagePledge | units per household | Current quantity divided by participant count, or zero before the first pledge. |
| weekend | indicator | One for Saturday or Sunday, zero otherwise. |
| evening | indicator | One for local hours 17 through 22, zero otherwise. |
| lifecycleFraction | fraction | Elapsed share of time between creation and the current effective cutoff. |
| split | category | Fixed chronological train, validation, or test partition. Metadata only. |
| outcomeAt | timestamp | First hourly boundary reaching MOQ, or the expiry boundary for an unsuccessful pool. Evaluation only. |
| finalQuantity | units | Accepted units at the observation cutoff or earlier threshold attainment, capped at MOQ. Evaluation only. |
| reachedMoq | binary label | One when cumulative pledged units reach target MOQ by the inclusive cutoff. Zero otherwise. |

The feature matrix has a fixed order. Sector and SKU expand to nine and six binary columns respectively. One-time identifiers, calendar timestamps, split assignments, final quantities, outcome times, and labels are excluded from estimator inputs. The exact ordered feature names accompany every trained model in its metrics registry.
