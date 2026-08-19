---
id: endpoint-<kebab-name>
title: <Endpoint group / feature>
type: api_endpoints
status: active
services:
  - <service-id>
contract_source:
  - <repo>:<module> <ContractClass>
parent_feature: feature-<...>
---

# API: <name>

> The **complete** route reference for this feature — public and internal alike. URL shapes and
> payloads live in the contract classes named in `contract_source` (the truth); a generated schema
> needs a running service and credentials, so it is not the source here.

## Routes — all of them, no exceptions

| Method and path | Service | Auth tier | In the generated schema? | Purpose |
|---|---|---|---|---|
| `POST /api/...` | <service> | end-user token | yes | … |
| `POST /internal/...` | <service> | service role `<role>` | **no** (hidden) | … |

The "in the generated schema?" column doubles as "reachable from the public console?" whenever
client SDKs are generated from that schema.

## Handlers (code anchors)

The server side of every route:

| Route | Handler |
|---|---|
| `POST /api/...` | `<repo>/<module>/<path>/<Feature>Routes.<ext>` |

## Request and response bodies

Link to the DTOs in the shared module. **Do not copy the fields** — a copied field list is stale
within a sprint, a path is not.

## Errors

| Condition | Status | Body |
|---|---|---|
| … | `400` | `{"error": "..."}` |
