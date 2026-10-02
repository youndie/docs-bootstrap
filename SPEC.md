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
whitespace-separated tokens; a single token is always the test. The repository may be a module path
inside one (`feature/roaming-data`), because a repository of many modules is the ordinary shape. A
reference of the form `path::name`, `path#name` or `TestClass.name` is a locator rather than a name,
so a tool looking for the test greps for what follows the separator — the file may be renamed while
the function keeps its name — and that name may contain spaces, as Kotlin and Spock test names do.
Backticks around either part are optional. A name is looked for as a whole word in the files of the
repository that are not Markdown, and the answer does not depend on whether the repository is a git
checkout or a directory that is walked: the same name, matched the same way.

A check that is not a test function — a conformance script, a `run.sh` that drives the binary, the
`Main.kt` of a harness — is named by its path, with nothing after `::` or `#`:

```markdown
**Automated:** `conformance/scripts/hashes/encoding.redis`
```

Such a reference is checked for the file, not looked for as text: it resolves the way a code anchor
does (§4) — in its own repository, `./` from the root, `.../` abbreviated, `../` out of it, a cited
range inside the file — and a repository written before it means the path is inside that one. A
path with no extension, which the anchor check would not take for one (`samples/oracle`), is looked
for as text, like a test name.

A file name with no directory — `negative-control.sh`, `LoanRoutesTest.kt`, optionally with a line or
a range — is a path too, and is looked for as a file of that name: in the reference's own repository
as §4 finds a path by its suffix, or anywhere inside the repository or module written before it. It
is told from `TestClass.name` by its extension, which has to be one that a test, a script or a
check's data is given (`.kt`, `.py`, `.sh`, `.redis`, `.yaml`, …). An extension that is also a
plausible member name (`json`, `patch`, `html`) is not on that list, so `LoanTest.renew` and
`Serializer.json` are a class and its member, looked for by the member's name.

A scenario covered by several tests names them as a list, separated by commas, each reference in
its own backticks. A dash or a semicolon ends the list, and what follows it is commentary for the
reader; so is anything in parentheses. After the first reference, a path or a file name inside a
sentence says where a test lives or what it reads, and is not a reference of its own.

```markdown
**Automated:** `e2e RoamingScenarioTest`, `feature/roaming-data RoamingPackageTest`
**Automated:** `PurchaseSagaTest`, and against a moved clock `SuspendedSagaExpiryTest`
**Automated:** `LoanRoutesTest` (on both targets) — the case `a renewal behind a hold is refused`
```

**The line belongs to a scenario.** Only an `**Automated:**` line between a `### Scenario:` heading
and the next heading of level one, two or three says that scenario is automated. The same words in a
business rule are a pointer for the reader, not a scenario, and are not counted — counted, they
made one document report more automated scenarios than it has.

**Exactly one tool counts this line.** In this repository that is `bdd_report.py`, which has to
parse the line anyway in order to go looking for the test. A second counter is how two checks in
one run came to report 100% and 0% about the same file.

**A scenario is counted by its heading, `### Scenario: <name>`, and by nothing else.** What sits
under the heading is free: the bullets of the template, or the steps in a fenced `gherkin` block.

````markdown
### Scenario: A renewal is refused while somebody is waiting

```gherkin
Given an open loan on a copy of b-1 and one waiting hold on b-1
When the librarian renews the loan
Then the answer is 409 "renewal blocked by holds"
```
````

The word `Scenario` is a marker for tools, like a frontmatter field name or `**Automated:**`, and
stays as it is in a document written in another language. Several scenarios inside one gherkin
block, a heading in another language, or a heading at another level are read by a person and
counted by nothing: the report says the document has no scenarios, which is a wrong number rather
than a low one. `docs_check.py` warns about each of these shapes (`uncounted-scenarios`). A warning
and not an error, because documents written the other way were valid before this paragraph existed
and remain valid v1 documents (§8); what they were missing was being told.

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

#### 3.2.1 `design` (optional)

A screen that was built to a design carries where that design is and how its states map onto it:

```yaml
design:
  canvas: <url>                        # where the design lives; free text for a person
  references: <repo>/<directory>       # in the code: one PNG per state, named like the screenshot fixture
  states:                              # section-1 state -> reference stem in that directory
    empty: CatalogSearch_empty
    content: CatalogSearch_content
```

`references` is a code anchor like any other and rots the same way, so `code_anchors.py` checks
`<references>/<stem>.png` for every entry of `states`. `docs_check.py` checks the other direction:
every key of `states` names a state listed in section 1 of the document (the bold name of a
`- [ ] **state:**` line, backticks ignored, case-insensitive), because a design of a state the
document does not know is either a state the document forgot or an artboard nobody implements. A
listed state without a design entry is a warning, not an error - a loading spinner rarely gets an
artboard.

The stems are what the screenshot tool names its files (`[A-Za-z0-9_.-]` only), so that the same
name identifies the artboard, the reference PNG and the fixture; `viddikDesignParity` in the
Compose toolchain reads exactly this directory. The numbers a parity run produces stay in the pull
request that produced them, not in the document: a percentage written here is wrong after the
next commit, and the check that would notice does not exist.

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
checker enforces, and it is what the whole format exists for. Missing, it is the `no-code-anchor`
error (a warning on research, which may predate the code, §3.5).

An address (§4.1) satisfies the rule the same as a path does: a document whose code lives entirely in
another repository writes every path as `owner/repo@<sha>!/…`, as this section asks, and must not
have to add a path of its own repository that it does not need. The left side has to name something
fetchable — `Ktor!/…` or a placeholder is not a way into the code and does not count. The ref is not
asked about: an address at a branch, at no ref, or at a snapshot still reaches the code in one hop,
and whether it reaches the code that was read is the anchors report's question, answered in its own
section that does not fail `--check` (§4.1). Refusing it here would make that section blocking by
another road.

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

A leading `./` changes nothing: `./scripts/verify.sh` is `scripts/verify.sh`, from the root of the
anchor's own repository. A path that climbs out with `../` is none of the three forms — relative to
the document or to the root, nothing says which, and either way it has left the anchor's
repository — and is reported missing, saying so. A path into another repository starts with that
repository's name, or is an address (§4.1).

A path may end in a line or a range, `catalog-api/src/routes/loans.py:40-52`, where the place in the
file is the point. The checker resolves the file the same way and reports the anchor missing when
the file is now shorter than the range; it does not check what the lines say, which moves with every
edit above them — so a file or a directory remains the better anchor wherever it will do. An address
inside an artefact (§4.1) may end the same way.

**Anchor matching is by suffix.** A path is alive if some file or directory in the tree ends with
the fragment. This can report a false "found" — two files with the same name in different modules —
but practically never a false "missing", and the job of the check is to catch rot.

**The tree is the anchor's own repository.** When the checker looks across several repositories, an
anchor belongs to the one its first segment names, else to the one its service names (the
`repo_url` of the service document), else to the one the documentation lives in. A file found only
in some other repository is not the anchor's file and is reported missing; across repositories a
suffix fits too much — `.github/workflows/deploy.yml` and `gradle/libs.versions.toml` are in most of
them — and a false "found" hides exactly the rot the check is for. When none of the three is known,
a path that two repositories have is ambiguous. A path into a repository the checker does not hold
is written as an address (§4.1).

Paths in backticks that contain `*`, `{`, `<` or `>` are treated as patterns and skipped.

**Not everything written like a path is one.** Besides patterns, the checker skips four kinds of
word with a slash, each only where the tree cannot hold it — so a file that is there is still found,
and a file that went is still missing:

* a layer of this documentation, one segment with its slash — `features/`, `services/`, `api/`
  (§1) — unless the code has a directory of that name; found only in the documentation tree, it was
  the document pointing at its own layer;
* a git ref — `origin/main`, `refs/tags/v1.0`;
* a path the anchor's repository ignores — `build/libs`, `server/build/bin/` — asked of git, which
  never reports a tracked file; build output and local state are in no checkout, so such an anchor
  was missing for ever;
* a class in its binary form — `jdk/internal/javac/PreviewFeature`: lower-case package segments and
  a type name with two capitals or more, because `deploy/Dockerfile` has the same shape with one.

What the shape cannot tell from a path is left to the writer, in a form that says what it is. A JVM
frame or member is written dotted, `bench.Pricing.quote` — `Pricing.quote` and `Pricing.kt` differ
by nothing a pattern can hold. A section of somebody's specification is an address into it (§4.1)
or prose. A directory of an installed runtime, image or toolchain carries its root —
`$JAVA_HOME/jmods`, `<image>/bin/` — and a URL segment its host or slash, `/tree/<ref>`. One
segment is the weakest anchor there is, found in any directory of that name: `runtime/` meaning a
runtime image resolves to whatever package is called `runtime`, so a directory of the code is
written with enough of its path to be its own.

**A `deprecated` document's anchors are not looked for.** Such a document describes behaviour that
is gone and is kept for readers of old code (§6), so its paths say where something *was* and are
expected to resolve to nothing. The checker names the documents it skipped instead of reporting
their anchors as rot for as long as the document is kept.

### 4.1 Addresses inside something the tree does not hold

Research verifies facts by unpacking a dependency's artefact and reading the source inside it. That
address is not a path: no search over sibling repositories can ever resolve it, so it is reported
missing for ever — and a list that is permanently non-zero teaches the reader to skip it, taking the
one entry in it that is a real defect along with it.

Such an address uses the separator every jar URL already uses:

```
ktor-server-core-3.5.2.klib!/commonMain/io/ktor/server/engine/ShutdownHook.kt
io.github.smyrgeorge:sqlx4k:1.13.0!/commonMain/.../ConnectionPool.kt
kubernetes/website@v1.31!/content/en/docs/concepts/workloads/pods/pod-lifecycle.md
```

The checker reports these in their own section and never counts them as rot.

**The left side must name something fetchable**, and that is what stops the notation from becoming a
way to silence any inconvenient anchor. A versioned file, a Maven-style coordinate, or `owner/repo`
(optionally `@ref`) can be obtained by a reader who wants to check the claim; `Ktor!/…` cannot, and
is reported as **missing**, saying why. The escape hatch is deliberately too narrow to hide in.

**The ref names what was read: a commit or a version tag, not a branch.** A branch moves, so the file
a reader fetches at it is not the one the claim was checked against, and a branch that lives only in
somebody's local clone cannot be fetched at all. No ref is the default branch, and moves the same
way. The checker reads the shape of the ref — 7 to 40 hex digits is a commit, `v1.31`, `4.3.1` or
`7.6.0.RELEASE` is a version tag — and lists any other ref, and a missing one, in a section of its
own: *at a ref that moves*, with the pinned form to write instead. That section is not rot and does
not fail `--check`. Whether the ref exists is not asked: that would take the network, and a token for
every private repository, on every run, and a branch would still pass it, because a branch exists.
The shape is all the check can hold, and it has blind spots a reader should know: a branch named
like a version (`7.2`) passes, and so does a sha that was never pushed.

**So does the version.** A coordinate and a packaged file carry their version in their own name, and
a version published again under the same name moves like a branch: a `-SNAPSHOT` coordinate or
file, and a dynamic version (`1.+`, `latest.release`). A packaged file with no version in its name —
`x.jar` — says nothing about which build was read. Both are listed with the refs that move, and
neither fails `--check`. A version in a file name is read loosely, as a number after a `-`, `_` or
`.` (`guava-r09.jar`, `foo-v2.jar`, `Newtonsoft.Json.13.0.3.nupkg`): the forms are many, and a
pinned file reported as moving costs the list its reader. The blind spot is therefore the other way
round — a number that is not a version passes (`x86_64` is known and does not count). A build
numbered once and never published again, such as `0.1.0.<run>`, is a version.

The rule this serves is the same one §4 opens with: an anchor exists so the reader reaches the thing
in one hop. `ktor-server-core-3.5.2.klib!/…` is one hop. A bare path that no tree contains is none.

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
  instead is the substance of the rule — that at least one path into the code, or an address
  (§4.1), is present;
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
