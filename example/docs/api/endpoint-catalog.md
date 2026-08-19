---
id: endpoint-catalog
title: Catalogue and availability
type: api_endpoints
status: active
services:
  - catalog-api
contract_source:
  - catalog-api:src/catalog_api/routes ROUTES
  - catalog-api:src/catalog_api/domain/book.py Book, Copy, TRANSITIONS
parent_feature: feature-borrow-and-return
---

# API: Catalogue and availability

> The **complete** route reference for [catalog-api](../services/catalog-api.md) — the three routes
> a browser can reach and the three only loans-service can. There is no shared contract package:
> the response shape is whatever `_as_json` and `_copy_json` build, and those two functions are the
> contract.

The routes serve [feature-borrow-and-return](../features/feature-borrow-and-return.md) (resolving a
barcode at the desk) and [feature-holds-queue](../features/feature-holds-queue.md) (the copy that
goes to the hold shelf); the reading client is
[screen-catalog-search](../screens/screen-catalog-search.md).

## Routes — all of them, no exceptions

| Method and path | Service | Auth tier | In the published schema? | Purpose |
|---|---|---|---|---|
| `GET /api/books?q=&page=` | catalog-api | staff session | yes | search by title or author |
| `GET /api/books/{book_id}` | catalog-api | staff session | yes | one bibliographic record |
| `GET /api/books/{book_id}/availability` | catalog-api | staff session | yes | copy counts and the barcodes on the shelf |
| `POST /internal/books/reindex` | catalog-api | service token | **no** (hidden) | rebuild the search index |
| `GET /internal/copies/{barcode}` | catalog-api | service token | **no** (hidden) | resolve a barcode to a book and a status |
| `POST /internal/copies/{barcode}/status` | catalog-api | service token | **no** (hidden) | move one copy between statuses |

The column is not editorial: `openapi.py` walks the same `ROUTES` tuples and skips everything with
`hidden = True`. A route added without that flag is public, including one that was meant not to be.

**Auth tiers.** `staff session` is the cookie the reverse proxy adds; the service itself trusts the
proxy. `service token` is the `X-Service-Token` header compared against `CATALOG_SERVICE_TOKEN`.
There is no per-user authorisation of any kind — every librarian can do everything.

## Handlers (code anchors)

| Route | Handler |
|---|---|
| `GET /api/books` | `catalog-api/src/catalog_api/routes/books.py` → `search_books` |
| `GET /api/books/{book_id}` | `.../routes/books.py` → `get_book` |
| `POST /internal/books/reindex` | `.../routes/books.py` → `reindex` |
| `GET /api/books/{book_id}/availability` | `catalog-api/src/catalog_api/routes/availability.py` → `book_availability` |
| `GET /internal/copies/{barcode}` | `.../routes/availability.py` → `get_copy` |
| `POST /internal/copies/{barcode}/status` | `.../routes/availability.py` → `set_copy_status` |
| the published schema | `src/catalog_api/openapi.py` → `public_schema` |

## Request and response bodies

Do not read a field list here; read the serialisers. `_as_json` in `routes/books.py` builds every
book object (`id`, `title`, `author`, `year`), `_copy_json` in `routes/availability.py` builds
every copy object, and the dataclasses behind them are `Book` and `Copy` in `domain/book.py`.

The only request body in the group is `{"status": "<one of domain.book.STATUSES>"}` on the copy
status route.

`GET /api/books` answers `{"items": [...], "page": <int>, "total": <int>}`. `total` is the number
of matches, not the number of pages, and `page` is echoed back unchanged.

## Errors

| Condition | Status | Body |
|---|---|---|
| `q` shorter than `CATALOG_MIN_QUERY_LENGTH` (2), or absent | `400` | `{"error": "query must be at least 2 characters"}` |
| `page` not a positive integer | `400` | `{"error": "page must be a number"}` |
| unknown `book_id` | `404` | `{"error": "book not found"}` |
| unknown barcode | `404` | `{"error": "copy not found"}` |
| `status` outside `STATUSES` | `400` | `{"error": "unknown copy status"}` |
| the transition is not in `TRANSITIONS` | `409` | `{"error": "copy status conflict"}` |

The `400` text is built from the configured minimum, so a deployment with
`CATALOG_MIN_QUERY_LENGTH=3` returns a different string. Two is the default and what every
environment runs.

## Quirks

* **`lost` accepts any origin.** `set_status` short-circuits before the transition table for
  `lost`, because a copy can be discovered missing from any state. Every other target is checked.
* **The reindex route does not reindex.** Its docstring says "Rebuilds the search index. Returns
  before the work is finished"; the body counts the books and returns `202`. There is no queue and
  no background task behind it. Search is a scan over `CATALOG.books`, so nothing is broken by
  this — but a caller waiting for the index to catch up waits forever.
