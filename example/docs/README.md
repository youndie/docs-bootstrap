# docs — Riverside Public Library lending system

Three services that lend books: a catalogue, a lending service, and the web application the staff
use at the desk. The documentation is layered; links run top to bottom.

```
[ Research (why the architecture is what it is) ]
                     │
[ Feature (business + BDD) ] ──▶ [ Client screen / flow ]
                                        │
                                        ▼
                              [ API endpoint (contract, auth tier) ]
                                        │
                                        ▼
                              [ Service (ownership, deploy) ]
```

| Layer | Directory | Answers | Source of truth |
|---|---|---|---|
| Research | `research/` | *why* it is built this way; what is verified, what is a hypothesis | the code each fact names |
| Feature | `features/` | *what* the system does and *why*; BDD scenarios | this repository |
| Client | `screens/` | what the user sees: states, actions, navigation | this repository + the screen's code |
| API | `api/` | URL, method, auth tier, where the contract lives | the route tables in each service |
| Service | `services/` | who owns the data, dependencies, deploy, local setup | this repository + the service's code |

**Backlog** — [backlog.md](../backlog.md): the index and the decisions; the items themselves are
one file each in [`backlog/`](backlog/), cited as
[B-02](backlog/B-02-store-hold-positions.md).

## About this example

This is the reference example for [SPEC.md](../../SPEC.md), and it is meant to be checked rather
than admired: **every path in every code-anchors table resolves to a file next to this directory**
(`catalog-api/`, `loans-service/`, `librarian-web/`), and every id in every frontmatter block
resolves to a document listed below.

The services are miniature on purpose — domain, routes and one job apiece. What is missing is
missing everywhere and said out loud in the documents that would otherwise imply it: there is no
server bootstrap, no migrations, no build files, no `/health` route and no scheduler. A document
that would have had to invent a path says so instead.

The anchors deliberately mix the three notations the format allows — full path from the repository
root, path from the module root, and `.../abbreviated` — because matching is by suffix and all
three resolve. Whichever a document uses, an agent reaches the file in one hop.

## Conventions

- **`id`** in the frontmatter is unique and equals the filename.
- Cross-layer links are ids in the frontmatter and ordinary markdown links in the body. If a
  feature lists a screen in `client_entries`, that screen's `parent_feature` points back.
- One document, one entity. A feature spanning three services is **one** file with three entries
  in `involved_services`.
- An empty list is an answer. `feature-overdue-notices` carries `client_entries: []` because the
  feature genuinely has no screen anywhere — a missing field would have meant "nobody looked".
- BDD scenarios are written from the code, not from memory: every status code and error string
  below was read out of the route that returns it.
- **The primary consumer is a coding agent.** Every document carries code anchors. Do not duplicate
  what lives in code (DTO fields, config keys); give the path. A copy rots, a path does not.
- Language: English. Code identifiers, URLs and HTTP headers verbatim as in the code.

## Templates

`templates/` holds a copy of the document templates, so the format travels with the repository.
Sections marked `<!-- optional -->` can be deleted.

## Checks

Run from the `example/` directory. In a real project the scripts live in the same repository as the
documents; here they are one level up, because the example shares them with docs-bootstrap itself.

```bash
pip install pyyaml
python3 ../scripts/backlog_index.py --check
python3 ../scripts/docs_check.py
python3 ../scripts/coverage_map.py --check
python3 ../scripts/bdd_report.py
python3 ../scripts/code_anchors.py --repos ..
```

## Coverage map

The list below is **checked** against the files on disk: a document missing here, or an entry with
no file behind it, fails `coverage_map.py`. The grouping and the descriptions are written by a
person — the machine only guards the membership.

### Research (1)

- [x] [research-architecture](research/research-architecture.md) — the ownership seam, the derived queue, and the three decisions the backlog argues with

### Services (3/3)

- [x] [catalog-api](services/catalog-api.md) — books and copies; owns where a copy is, never who has it
- [x] [loans-service](services/loans-service.md) — loans, the holds queue, and the overdue notice job
- [x] [librarian-web](services/librarian-web.md) — the two staff screens; holds no policy of its own

### Features (3)

At the desk:
- [x] [feature-borrow-and-return](features/feature-borrow-and-return.md) — the 21-day loan, its two renewals, and the return that promotes a hold

Waiting for a book:
- [x] [feature-holds-queue](features/feature-holds-queue.md) — one queue per book, three days on the hold shelf, and what a position actually promises

Getting the book back:
- [x] [feature-overdue-notices](features/feature-overdue-notices.md) — three emails, then a block; no screen anywhere

### Screens / flows (2)

- [x] [screen-checkout-desk](screens/screen-checkout-desk.md) — the screen a librarian keeps open all day: scan a card, scan a barcode
- [x] [screen-catalog-search](screens/screen-catalog-search.md) — search, availability, and the only place a hold is created

### API (2)

- [x] [endpoint-catalog](api/endpoint-catalog.md) — catalog-api in full, including the three internal routes the schema cannot show
- [x] [endpoint-loans](api/endpoint-loans.md) — loans and holds; the only route reference this service has
