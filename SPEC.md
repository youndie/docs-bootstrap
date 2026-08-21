# SPEC — the docs-bootstrap document format

`spec_version: 1`

This file is the contract. Tools that read a `docs/` tree produced by this skill — the checkers in
`scripts/`, a site builder, a documentation generator — parse what is described here and nothing
else. Everything not listed is free-form prose.

Two rules explain most of the decisions below:

> **`main` describes what exists. An open pull request describes what will be.**

> **The primary consumer is a coding agent.** Every document carries code anchors — paths, not
> retellings. A path stays correct as long as the file lives; a copy of the file's contents rots
> the day someone edits it.

---

## 1. Layout

```
docs/
├─ README.md          entry point and coverage map
├─ research/          research-architecture.md  why the architecture is what it is (optional, §3.5)
├─ features/          feature-<name>.md         what the system does and why, + BDD
├─ screens/           screen-<name>.md          UI screens
│                     bot-flow-<name>.md        conversational flows
├─ api/               endpoint-<name>.md        complete route reference per feature
├─ services/          <service-id>.md           ownership, deps, deploy, local setup
├─ backlog/           B-<NN>-<slug>.md          one product backlog item per file
└─ templates/         copies of the templates, so the format travels with the repo
backlog.md            backlog index (generated) + everything that is not an item
workflow.md           the docs-first process, if the project follows one
```

**Layers are optional, the naming is not.** A single-service project has no `screens/`; a library
has no `api/`. A missing directory is a valid answer. A directory named `endpoints/` is not — the
tooling looks for these names.

`templates/` is deliberately inside `docs/`: a newcomer, human or agent, finds the format without
leaving the repository. Tools skip it (see §7).

---

## 2. Frontmatter

Every document starts with a YAML block. Three fields are required everywhere:

| Field | Rule |
|---|---|
| `id` | **equals the filename without extension**. `features/feature-checkout.md` → `id: feature-checkout` |
| `title` | human-readable name |
| `type` | one of `feature`, `client_screen`, `client_flow`, `api_endpoints`, `service`, `research`, `backlog_item` |

`status` is required on every type except `service` and `backlog_item` (which has its own
vocabulary, §3.6) and takes one of `draft`, `active`, `deprecated`.

`id` equalling the filename is not bureaucracy: cross-layer links are written as ids, and a
resolver that has to open every file to learn its id cannot report a broken link cheaply.

### 2.1 Cross-layer links

Links between layers are ids in frontmatter **and** ordinary markdown links in the body. The
frontmatter is for machines building the graph; the body is for the reader who is already here.

```
feature ──client_entries──▶ screen ──calls_api──▶ endpoint ──services──▶ service
   └──────────api──────────────────────────────────▶
   └──────────involved_services───────────────────────────────────────────▶
```

| Field | On | Points to |
|---|---|---|
| `involved_services` | feature | service ids |
| `client_entries` | feature | screen / flow ids |
| `api` | feature | endpoint ids |
| `parent_feature` | screen, flow, endpoint | feature id |
| `calls_api` | screen, flow | endpoint ids |
| `services` | endpoint | service ids |
| `depends_on` | service | service ids or external system names |
| `epic` | backlog item | feature id |
| `blocked_by` | backlog item | backlog item ids |

**An empty list is an answer; a missing field is a question.** `client_entries: []` states that the
feature has no client surface. Omitting the field states nothing, and the checker says so — as a
warning, not an error.

---

## 3. Document types

### 3.1 feature

```yaml
---
id: feature-<kebab-name>
title: <name>
type: feature
status: draft | active | deprecated
owner: unassigned
involved_services: [<service-id>]
client_entries: [<screen-id>]
api: [<endpoint-id>]
tags: []
---
```

A feature is one document even when it spans four services. Sections: overview, business rules,
flow, **code anchors**, BDD scenarios, out of scope, quirks.

BDD scenarios are the acceptance criteria. They are written against observed behaviour — real
status codes, real error strings — not against intent. A scenario that is covered by an automated
test says so on a `**Automated:**` line; the absence of that line means the check is manual.

The line names the test, optionally preceded by the repository it lives in:

```markdown
**Automated:** catalog-api LoanRoutesTest
**Automated:** `tests/test_store.py::test_unacked_task_returns_to_the_front`
```

The repository is written only when the documentation covers more than one, and is the first of two
whitespace-separated tokens; a single token is always the test. A reference of the form
`path::name` or `path#name` is a locator rather than a name, so a tool looking for the test greps
for the last segment — the file may be renamed while the function keeps its name. Backticks around
either part are optional.

**Exactly one tool counts this line.** In this repository that is `bdd_report.py`, which has to
parse the line anyway in order to go looking for the test. A second counter is how two checks in
one run came to report 100% and 0% about the same file.

### 3.2 client_screen / client_flow

Filename `screen-<name>.md` or `bot-flow-<name>.md`.

```yaml
---
id: screen-<kebab-name>
title: <name>
type: client_screen | client_flow
platform: [<platform>]
status: draft | active
entry: { <platform>: "<entry point>" }
parent_feature: feature-<...>
calls_api: [<endpoint-id>]
source: <repo>/<path to the feature directory in code>
---
```

`source` is the single most useful field in the file: it is the directory the agent opens first.
Screen states are listed from the actual state class, with field names copied from it.

A conversational flow is a client too. `type: client_flow` keeps it in the same layer instead of
inventing a fifth one; the sections adapt (UI elements → dialog steps, screen states → FSM states).

### 3.3 api_endpoints

```yaml
---
id: endpoint-<kebab-name>
title: <group>
type: api_endpoints
status: active
services: [<service-id>]
contract_source: [<repo>:<module> <ContractClass>]
parent_feature: feature-<...>
---
```

**An endpoint document is the complete route reference, not a supplement to generated API docs.**
It lists *every* route including internal and hidden ones, each with its auth tier and an
"in the generated schema?" column. The reason is practical: generated schemas need a running
service and credentials, which an agent in a review does not have.

Request and response bodies are **linked, not copied** — a table of DTO fields is stale within a
sprint.

### 3.4 service

```yaml
---
id: <service-id>
title: <name>
type: service
repo_url: <url>
module: <module inside the repo, if there are several>
tech_stack: [<...>]
owner: unassigned
depends_on: [<service-id | external system>]
publishes: [<artifact / image>]
---
```

Sections: responsibility (including *what it deliberately does not do*), API contracts, **code
anchors**, how it is built, dependencies, infrastructure and deploy, local setup, configuration,
quirks.

"How it is built" is optional and usually the most useful section in the file: the mechanics that
are not visible from any single file — the order things run in, why a queue and not a lock, where
the thread boundary is — together with why it is not done the obvious way. That reasoning is the
one thing a reader cannot recover from the code, because the code only shows the option that won.

`repo_url` doubles as machine data: `code_anchors.py` uses it to decide which repository a path in
this service's anchors belongs to.

It is **not required**. In the single-repository layout `services/` describes the modules of one
repository, so the field would carry the same URL on every document in the layer — a duplicate that
adds nothing and goes stale together. Its absence is a warning naming what it costs: anchors are
then looked for in every repository at once, which can report a false "found" when two repositories
hold a file with the same path.

### 3.5 research

Research is the layer that records **why** the system is built this way: which facts were verified
and against what, which decisions were taken and what was rejected, which risks are open and how
each is mitigated. Without it the other four layers describe a system whose every choice looks
either obvious or arbitrary, and the next person re-litigates a decision that was settled a year
ago against evidence they cannot see.

It exists in two forms. They share a word and almost nothing else, so the difference is worth
stating before the shapes: one answers **why the system is built this way**, and stays true for as
long as the reasoning does; the other is **the plan for one branch**, and is replaced by the code
the moment that code exists. That is why the first is amended and the second is deleted — and why
a project can have both, one of them, or neither.

Which one a project gets follows from a single question: **does the document have to outlive the
branch it was written in?**

**Permanent — one document per product, `docs/research/research-architecture.md`.** Use it when the
product lives in one repository. It is the entry point of the documentation: the agent instructions
point at it first, and a task that is not read against it looks like "do the obvious thing", which
is frequently wrong. It is amended rather than archived — when the implementation contradicts the
research, the correction is written *at the point of divergence*, keeping the reason the first idea
failed, so the next reader does not repeat the approach.

```yaml
---
id: research-architecture
title: <product> — architecture research
type: research
status: active
date: <YYYY-MM-DD>
---
```

**A branch artefact — `research/feature-<name>.md` in a service repository.** Use it in the
multi-repository, docs-first layout ([WORKFLOW.md](WORKFLOW.md) §2), where the document plans one
feature's work in one repository. It is a file in the branch rather than a pull-request description
because the agent reads the working tree and the paths are only clickable there, and it is
**deleted before that branch merges**: it describes a plan, and a plan merged into `main` starts
lying the moment the code diverges from it. Anything worth keeping has moved into a feature
document (behaviour) or the repository's agent instructions (how the code is arranged) by then.
This form is not stored in the docs tree and carries no `id`; its frontmatter is in
[templates/research-feature.md](templates/research-feature.md).

**The code-anchor rule of §4 is a warning rather than an error here, and only here.** Research
legitimately predates the code — on a greenfield project the verified facts are read out of
dependency artefacts and published metadata, and there is no source tree to point at yet. A gate
that cannot be passed honestly teaches people to invent a path, and an invented path is worse than
an admitted gap.

### 3.6 backlog_item

One item per file, `backlog/B-<NN>-<slug>.md`.

```yaml
---
id: B-NN
title: "<one line>"
status: open | wip | done | question | dropped
priority: P0 | P1 | P2 | P3 | infra
size: XS | S | S/M | M | L | XL
stage: <stage id from backlog.md>
epic: feature-<name>        # optional
blocked_by: [B-NN]          # optional
---
```

**Items are flat and never move.** `stage`, `priority` and `status` are fields, not directories,
because documents in the four layers cite items by id — and re-prioritising a task must not break
a link.

There is deliberately no `epic` entity. An epic here is always a feature, so grouping goes through
`epic: feature-<name>` and one concept is spared.

The tables between the `BEGIN INDEX` / `END INDEX` markers in `backlog.md` are **generated** from
this frontmatter. Edit the item, run the generator, commit both.

---

## 4. Code anchors

Every document must contain at least one path into the code. This is the one structural rule the
checker enforces, and it is what the whole format exists for.

Anchors appear in a table whose first column names the service (or the kind of file) and whose
second column holds paths in backticks:

```markdown
## Code anchors

| Service | Code |
|---|---|
| catalog-api | `catalog-api/src/routes/loans.py` |
| catalog-api | `catalog-api/src/domain/loan.py` — the state machine |
```

Paths may be written in any of three ways, and mixing them is fine:

```
catalog-api/src/routes/loans.py          from the repository root
src/routes/loans.py                      from the module root
.../routes/loans.py                      abbreviated
```

**Anchor matching is by suffix.** A path is alive if some file or directory in the tree ends with
the fragment. This can report a false "found" — two files with the same name in different modules —
but practically never a false "missing", and the job of the check is to catch rot.

Paths in backticks that contain `*`, `{`, `<` or `>` are treated as patterns and skipped.

---

## 5. The coverage map

`docs/README.md` ends with a coverage map: every document, grouped by layer, with a one-line
description of what it covers.

The map is **checked, not generated**. The grouping and the descriptions are editorial — a machine
cannot say that `feature-stock-model` is the core of the domain — so the machine verifies the
*membership* of the list and a human writes the meaning. A document missing from the map, or a map
entry with no file behind it, fails the check.

---

## 6. Statuses and the `main` invariant

| `status` | Meaning |
|---|---|
| `draft` | the document describes intent; it lives in an open pull request |
| `active` | the document describes current behaviour |
| `deprecated` | the behaviour is gone; the document is kept for readers of old code |

On `main`, `status: draft` is a defect: it means intent was documented as fact. The checker has an
`--on-main` mode that turns this into an error, and it is meant to run on push to the default
branch only.

---

## 7. What tools must and must not do

A tool that reads this format:

* **must** treat unknown frontmatter fields as data, not as errors — the format grows;
* **must** treat a missing `docs/` directory as a normal mode, not a failure;
* **must** skip `docs/templates/` — the placeholders there are not documents;
* **must not** enforce section structure. Documents legitimately deviate: a feature that is mostly
  a reality check has no business-rules section, and that is a style, not a defect. What is checked
  instead is the substance of the rule — that at least one path into the code is present;
* **must not** silently rewrite a hand-written document. A generator that finds a discrepancy
  between the code and a document reports it. The invariant above only holds while the person
  responsible for the meaning owns the text.

---

## 8. Versioning

`spec_version` is `1`. Additive changes — a new optional field, a new `type` — keep the version.
Anything that would make a v1 reader wrong (renaming a field, changing what a value means) raises
it, and tools state which version they read.

**`repo_url` stopped being required without raising the version**, and the reasoning is recorded
here rather than left to be inferred. Relaxing a requirement makes previously invalid documents
valid, which can break a reader that counted on the field — the letter of the rule above. It was
treated as a defect in the specification instead: the layout this format recommends first could not
satisfy the requirement other than by repeating one URL on every document in a layer, which was
found by documenting a project rather than by reading the text. No published reader depended on it.
A later relaxation, once there are readers, is a version bump.
