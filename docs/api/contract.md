# Byoo v1 service contracts

REST uses JSON under `/v1`, returns the resource directly, and returns errors as `{error:{code,message,requestId}}`. Dates are ISO 8601 UTC. Money is integer paisa. `Idempotency-Key` is client-generated for joining, checkout and settlement. `@byoo/contracts` provides common TypeScript wire types.

| Method and path | Input | Result |
|---|---|---|
| POST /auth/request-otp | phone | challengeId, expiresIn, resendAfter |
| POST /auth/verify-otp | phone, challengeId, otp, client (web/mobile) | user, accessToken and refreshToken for mobile |
| GET /auth/me | session | User |
| POST /auth/profile | name, sector, preferences | User |
| POST /auth/refresh | mobile refreshToken or cookie | User and rotated mobile tokens |
| POST /auth/logout | session | success |
| GET /catalog/categories | | Category[] |
| GET /catalog/products | q, category | Product[] |
| GET /catalog/products/:id | | Product |
| GET /pools/nearby | sector, optional lat/lng, q, category | Pool[] |
| GET /pools/:id | | Pool |
| POST /pools/seed | productId, sector, quantity, durationHours, optional lat/lng | Pool |
| POST /pools/join | poolId, quantity, optional lat/lng | Order |
| GET /pools/mine | | Order[] |
| GET /pools/:id/participants | | count |
| GET /pools/:id/tracker | | pool, events |
| POST /escrow/checkout | orderId, method JAZZCASH or EASYPAISA | Order |
| GET /escrow/transactions | | Order[] |
| GET /escrow/orders/:id | | Order |
| GET /orders/:id/handover | own eligible order | code, expiresAt |
| POST /orders/:id/dispute | category, description, optional evidenceUrl | Dispute |
| GET /disputes | | Dispute[] |
| GET /notifications | | Notification[] |
| POST /notifications/:id/read | | Notification |
| POST /notifications/device | token | success |
| POST /onboarding/events | event, step, sessionId | success |

Browser apps proxy the API at the same origin with Next.js rewrites. The API provides HttpOnly cookies with Secure in hosted environments and checks request origins on browser mutations. Android explicitly sets `client: "mobile"` on verification and stores its own tokens using SecureStore. Demo OTP is configured on the API and stays out of responses and logs.

| Method and path | Input | Result |
|---|---|---|
| GET /lbi/pools/pending | LBI role | Pool[] |
| GET /lbi/orders | LBI role | Fulfillment[] |
| POST /lbi/pools/:id/approve | optional notes | Fulfillment or NO_ELIGIBLE_SUPPLIER error |
| POST /lbi/pools/:id/reject | reason | Pool |
| POST /lbi/orders/:id/confirm | | Fulfillment |
| POST /lbi/orders/:id/dispatch | | Fulfillment |
| POST /lbi/verify-hub-arrival | fulfillmentId, packagingIntact, sealVerified, quantityMatches, inspectedUnits | Fulfillment |
| POST /lbi/verify-handover | orderId, code | Order |
| POST /lbi/settle | poolId, idempotency header | reconciliation |
| GET /admin/dashboard | platform admin | Dashboard |
| GET /admin/analytics | platform admin | Analytics |
| GET /admin/suppliers | platform admin | SupplierOffer[] |
| GET /admin/ledger | platform admin | LedgerOverview |
| GET /admin/disputes | platform admin | Dispute[] |
| POST /admin/disputes/:id/review | notes | Dispute |
| POST /admin/disputes/:id/resolve | notes, resolution NO_REFUND/FULL_REFUND/PARTIAL_REFUND, damagedQuantity optional | Dispute |
| GET /admin/audit-logs | platform admin | AuditRecord[] |
| GET /admin/ai/metrics | platform admin | AIOverview |

`GET /v1/health` is liveness and `GET /v1/health/ready` checks infrastructure. Socket.IO uses `pool:subscribe` and `pool:update`. Refresh authoritative data after reconnect and committed changes.

## Machine learning

`POST /v1/ai/predict-viability` and `POST /v1/ai/optimize-radius` accept camelCase `AiFeatures`. Prediction returns probability (0–1), healthScore (0–100), modelVersion, timestamp, explanation and fallback. Optimization also returns decision, radii, expansion eligibility, cancellation recommendation and step. The Node API applies the DB state, cutoff and lock independently. `GET /v1/ai/hot-opportunities` reads eligible candidates from `GET /v1/ai/candidates` using a shared internal bearer where configured. Metrics include an explicit synthetic label.
