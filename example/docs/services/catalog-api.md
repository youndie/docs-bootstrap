---
id: catalog-api
title: catalog-api
type: service
repo_url: https://github.com/example-library/catalog-api
module: src/catalog_api
tech_stack: [Python, PostgreSQL]
owner: unassigned
depends_on:
  - PostgreSQL
publishes:
  - "catalog-api (container image)"
  - "public OpenAPI schema (openapi.public_schema)"
---

# catalog-api

## 1. Responsibility

Owns the bibliographic record (`Book`) and the physical copy (`Copy`) — barcode, which book it
belongs to, and where it is: `on_shelf`, `on_loan`, `held`, `in_repair`, `lost`.

It deliberately does **not** know who has a book. A copy that leaves the building is `on_loan` and
that is the whole of catalog-api's knowledge; the member, the due date and the queue belong to
[loans-service](loans-service.md). The split is what lets the catalogue be read by anyone and the
loan record by nobody.

It also does not decide *when* a copy may move. `TRANSITIONS` says which moves are legal;
loans-service decides which one to ask for.

## 2. API contracts

* **Published schema:** built at runtime by `public_schema()` from the route tables. The single
  input is the `hidden` flag on each `Route` — no allow-list, no annotations.
* **Contracts:** there is no shared package. `_as_json` and `_copy_json` are the serialisers and
  therefore the contract; the dataclasses behind them are `Book` and `Copy`.
* **Complete route reference:** [endpoint-catalog](../api/endpoint-catalog.md) — including the
  three hidden routes, which the schema by definition cannot show you.
* **Auth tiers:** two. `/api/**` trusts the staff session added by the reverse proxy; `/internal/**`
  requires `X-Service-Token` equal to `CATALOG_SERVICE_TOKEN`.

## 2a. Code anchors

| File | What is there |
|---|---|
| `catalog-api/src/catalog_api/routes/books.py` | search and lookup, the `Route` tuple, `ROUTES` |
| `catalog-api/src/catalog_api/routes/availability.py` | shelf counts and the internal copy routes |
| `catalog-api/src/catalog_api/domain/book.py` | `Book`, `Copy`, `TRANSITIONS`, `Catalog.search`, and the seed data |
| `src/catalog_api/openapi.py` | what becomes public and what does not |
| `src/catalog_api/config.py` | every environment variable the service reads |

There are no migrations in this repository and no server bootstrap: `ROUTES` is a table, and the
process that mounts it is deployment's business.

## 3. Dependencies

| Kind | Name | What for |
|---|---|---|
| Database | PostgreSQL | books and copies |
| Service | — | catalog-api calls nobody. It is a leaf, and that is deliberate: the catalogue must stay readable when lending is down |
| External | reverse proxy | terminates the staff session; the service does no authentication of its own |

## 4. Infrastructure and deploy

* **Image:** `catalog-api`
* **Health:** none. `ROUTES` is the complete list of routes and there is no `/health` in it — a
  liveness probe has to use `GET /api/books?q=aa` and accept the cost.
* Build and chart files are not part of this example repository.

## 5. Local setup

```bash
python3 -c "import sys; sys.path.insert(0, 'catalog-api/src'); \
  from catalog_api.openapi import public_schema; print(public_schema())"
```

Nothing else has to be running. The seed catalogue at the bottom of `domain/book.py` (three books,
four copies) is what the service serves until a database is wired in.

## 6. Configuration

| Key | Description | Required |
|---|---|---|
| `CATALOG_DATABASE_URL` | PostgreSQL DSN | yes |
| `CATALOG_PAGE_SIZE` | books per search page, default 25 | no |
| `CATALOG_MAX_PAGE_SIZE` | see the quirks — nothing reads it | no |
| `CATALOG_MIN_QUERY_LENGTH` | shortest accepted search term, default 2 | no |
| `CATALOG_SERVICE_TOKEN` | shared secret for `/internal/**` | yes |

The full list, with its defaults, is `config.py`; it is short enough to read and it is the only
place in the service that touches the environment.

## 7. Quirks

* **`CATALOG_MAX_PAGE_SIZE` is read and never used.** It is set in `Config.__init__`, stored, and
  referenced nowhere: no route lets a caller ask for a page size, so there is no maximum to
  enforce. It looks like a limit, it deploys like a limit, and changing it does nothing.
* **`lost` bypasses the transition table.** `Catalog.set_status` returns early for `lost` before
  consulting `TRANSITIONS`, because a copy can be discovered missing from any state. Every other
  target is validated, so this is easy to read as an oversight — it is not.
* **Search is a substring scan of the seed dictionary.** `Catalog.search` case-folds the query and
  looks in title and author, then sorts alphabetically. There is no relevance, no ISBN field and no
  index — `POST /internal/books/reindex` maintains nothing, despite its name and its docstring.
