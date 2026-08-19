# docs — <project name>

<One sentence: what this project is.> The documentation is layered; links run top to bottom.

```
[ Research (why the architecture is what it is) ]   <!-- optional -->
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
| Research | `research/` | *why* it is built this way; what is verified, what is a hypothesis | the artefacts each fact names |
| Feature | `features/` | *what* the system does and *why*; BDD scenarios | this repository |
| Client | `screens/` | what the user sees: states, actions, navigation | this repository + the screen's code |
| API | `api/` | URL, method, auth tier, where the contract lives | the shared modules |
| Service | `services/` | who owns the data, dependencies, deploy, local setup | this repository + the service's agent instructions |

Delete the layers this project does not have. A missing directory is a valid answer; a renamed one
is not — see [SPEC.md](../SPEC.md).

**Backlog** — [backlog.md](../backlog.md): the index and the decisions; the items themselves are
one file each in [`backlog/`](backlog/), cited as `[B-12](backlog/B-12-some-slug.md)`.

## Conventions

- **`id`** in the frontmatter is unique and equals the filename.
- Cross-layer links are ids in the frontmatter and ordinary markdown links in the body.
- One document, one entity. A feature spanning three services is **one** file with three entries
  in `involved_services`.
- BDD scenarios are written from the code, not from memory: check the actual status codes and
  error strings before writing a scenario.
- **The primary consumer is a coding agent.** Every document carries code anchors — paths to the
  feature directory, the handler, the view model — so that the reader reaches the code in one hop.
  Do not duplicate what lives in code (DTO fields, config keys); give the path. A copy rots, a
  path does not.
- Language: <pick one and say so>. Code identifiers, URLs and HTTP headers verbatim as in the code.

## Templates

`templates/` holds a copy of the document templates, so the format travels with the repository.
Sections marked `<!-- optional -->` can be deleted.

## Checks

```bash
pip install pyyaml
python3 scripts/backlog_index.py --check
python3 scripts/docs_check.py
python3 scripts/coverage_map.py --check
python3 scripts/bdd_report.py
python3 scripts/code_anchors.py --repos ..
```

## Coverage map

The list below is **checked** against the files on disk: a document missing here, or an entry with
no file behind it, fails `coverage_map.py`. The grouping and the descriptions are written by a
person — the machine only guards the membership.

### Research (N)

- [x] [research-architecture](research/research-architecture.md) — verified facts, decisions, risks

### Services (N/N)

- [x] [<service-id>](services/<service-id>.md) — one line on what it owns

### Features (N)

<Group heading>:
- [x] [feature-<name>](features/feature-<name>.md) — one line

### Screens / flows (N)

- [x] [screen-<name>](screens/screen-<name>.md) — one line

### API (N)

- [x] [endpoint-<name>](api/endpoint-<name>.md) — one line
