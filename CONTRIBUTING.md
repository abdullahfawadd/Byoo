# Contributing

Use pnpm from the repository root and uv for the Python service. Confirm database changes from an empty PostGIS database as well as with representative existing rows. Use migrations for durable changes and keep seed data deterministic.

Run the relevant unit and integration tests, then verify the consumer and operations paths against the same API. For financial changes, cover retry, concurrency, authorization, rounding and reconciliation. Record screenshot viewport, device/API level and test outcomes with the change. Keep secrets in local ignored environment files or the hosting secret store.
