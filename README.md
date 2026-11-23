# Byoo

**Better buying, together.** Byoo is an Islamabad-based academic product for combining neighborhood orders to reach wholesale minimums. It models authorization, escrow, wholesale fulfillment, neighborhood collection and refunds in a simulated ledger.

## Workspace

| Path | Purpose |
|---|---|
| `apps/mobile` | Expo Router Android client |
| `apps/web` | Next.js consumer explorer and account |
| `apps/admin` | Next.js platform and simulated LBI operations |
| `apps/api` | Express, Prisma, PostGIS, Redis jobs and WebSockets |
| `ml` | Simulation, training, evaluation and FastAPI inference |
| `data` | Synthetic lifecycle records and chronological splits |
| `packages` | Shared wire contracts and Electric Market design tokens |
| `docs` | v1.1 source references, v1.2, architecture and verification |

## Get started

Requirements are Node.js 24 LTS or supported 26 LTS, pnpm 11, Python 3.12, uv, and Docker with Compose. Android device QA also needs an SDK and emulator or USB-connected Android device.

```sh
pnpm install --frozen-lockfile
docker compose up -d --wait
```

Use the environment settings in [deployment setup](docs/deployment/guide.md). The [service contracts](docs/api/contract.md), [architecture](docs/architecture/overview.md) and [verification notes](docs/testing/status.md) describe the implemented interfaces and observed checks. The catalog and example participants are demonstrations. Money and fulfillment activities are simulated.
