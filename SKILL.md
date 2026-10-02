---
name: docs-bootstrap
description: Bootstrap or extend layered, machine-checked documentation for a codebase — research that separates what was verified from what was assumed, features with BDD scenarios, client screens, API endpoint references, service documents and a file-per-item backlog, all carrying paths into the code. Use when a repository has no documentation an agent can navigate, when documentation exists but has drifted from the code, or when a new feature needs documenting before it is built.
---

# docs-bootstrap

Produce documentation whose primary consumer is a coding agent: layers linked by ids, every
document carrying paths into the code, every claim checkable by machine.

```
[ Research — why the architecture is this and not that; verified vs hypothesis ]   optional
                              │
[ Feature — what the system does and why, + BDD scenarios = acceptance criteria ]
                              │
[ Screen / flow — what the user sees ]            only if there is a client
                              │
[ API — the contract: URL, auth tier, error codes ]
                              │
[ Service — who owns the data, config, deploy, quirks ]
```

Each layer answers its own question and points at its neighbour by id. Read [SPEC.md](SPEC.md)
before writing anything — it is the contract. [example/](example/) is a complete worked instance of
it; when unsure what a filled-in document should look like, read the example rather than guessing.

## The two rules everything else follows from

> **`main` describes what exists. An open pull request describes what will be.**

Never document intent as fact. A feature that is designed but not shipped is `status: draft` and
lives in an open pull request. What is not built yet is either that, or labelled *target* or
*hypothesis* in the text itself.

> **What was verified is separated from what was assumed, explicitly.**

Every status code, error string, field name and limit must be read out of the source before it is
written down. A document that does not distinguish "I read this in the code" from "presumably" is
worse than no document at all: it looks equally authoritative in both cases, and the next reader
builds on the sand without knowing which part is sand. If you cannot find something, say the
document does not cover it — an admitted gap costs a reader nothing, an invented detail costs them
their trust in the whole file.

## Procedure

### 0. Decide the scope before creating a single file

1. **Layout.** One product in one repository → `docs/` inside it. A platform of three or more
   service repositories where a feature is smeared across them → a separate docs repository, and
   then the docs-first process of [WORKFLOW.md](WORKFLOW.md) applies. Start with `docs/` inside the
   repository: moving out later is easy, moving back is not.
2. **Greenfield or brownfield.** If there is code, "verified fact" means *read in this code*. If
   there is no code yet, the things you can verify are external artefacts — the contents of a
   dependency's jar or klib, a package registry listing, the official documentation *of the version
   you are actually pinning* — and everything else is honestly called a decision or a hypothesis.
3. **Is there a client anyone will change from the document?** If not, no `screens/` layer at all;
   how the UI is put together lives in `services/<web>.md`.
4. **What already exists.** `README`, the repository's agent instructions, `ARCHITECTURE.md`,
   comments in the code — these are research material, not rubble to clear. A contradiction between
   them and the code is a finding, and its place is the research document.

Ask the user only about what genuinely changes the layout — usually one question, *inside the
repository or a separate one*. Everything else is a default you take yourself and say out loud in
your answer.

Also ask what to cover if the scope is not obvious. Documenting everything at once produces thin
documents; documenting one feature end to end across every layer produces a template for the rest.

### 1. Research, and write it into the file as you go

Research comes **before** the layer documents, and it is written while you read, not reconstructed
afterwards. It is also the first thing anyone picking up a task will read. Scale it to the job: a
platform is hours of reading code, one feature is a single pass.

* **Every fact carries where it was verified.** A `| Fact | Where verified |` table with a path, a
  class name inside an artefact, a URL. Verification addresses are what make the document
  re-checkable by the next person instead of merely believable.
* **Your memory is not a source.** Library versions, whether an API exists, how a framework behaves
  in a given version — this is exactly where memory is wrong most often, and exactly what an
  architecture decision then rests on. Unpack the artefact, list the registry, fetch the docs.
* **Derive the consequence, separately.** A fact on its own is inert: "JMX is resolved lazily" does
  nothing, while "therefore the base metric set must work without JMX" decides the architecture.
  The consequences are the valuable half.
* **A hypothesis is called a hypothesis and gets an address** — "check in M2". When that milestone
  closes, the hypothesis becomes a fact or a refutation *in writing*, not a silent deletion.
* **A decision is recorded with its reason and the alternative you rejected.** In six months the
  value is in why, not what; what is visible in the diff.
* **A deviation from what you were asked for is the most valuable entry in the document.** The user
  described X, research showed X impossible or harmful — that is a labelled *deviation from the
  brief* with its reasoning, never a quiet substitution.
* **Risks come with mitigation machinery**, not with a statement of concern. "Might not be fast
  enough" is not a risk; "UDP loss distorts the picture silently — mitigation: a sequence number
  per packet so the server shows gaps instead of drawing a clean graph over incomplete data" is.

Research is a living document. When the implementation diverges from it, amend **the research**, at
the point of divergence: "this used to say take X — you cannot, because Y; the working replacement
is Z". That keeps the document true *and* preserves why the first idea was wrong, which is what
saves the next person from trying it again.

Which of the two forms you write — the permanent `docs/research/research-architecture.md` or the
per-feature file that is deleted before its branch merges — follows from the layout you chose in
step 0. They share a word and have opposite lifetimes: one says why the system is built this way
and is amended as you learn, the other is the plan for one branch and is replaced by the code it
asked for. [SPEC.md §3.5](SPEC.md) has both, with templates. If the project uses the second, give
each service repository
[templates/workflow-research-guard.yaml](templates/workflow-research-guard.yaml) — nothing in the
documentation repository can see a file that lives in a service one.

### 2. Create the tree

```
docs/README.md      from templates/docs-readme.md
docs/research/  docs/features/  docs/screens/  docs/api/  docs/services/  docs/backlog/
docs/templates/     copy the templates in, so the format travels with the repository
backlog.md          the index page, with the BEGIN INDEX / END INDEX markers
Makefile            from templates/Makefile — the gate (step 9)
.github/workflows/check.yaml    from templates/workflow-check.yaml — CI, and the version of the checks (step 8)
```

**Do not copy `scripts/` in.** This step used to say so, on the grounds that a check living elsewhere
does not run. A check living elsewhere at a pinned version does; a copied one runs at the version of
the day it was copied and never hears of a fix — 18 copies of one script were found across one
portfolio in three versions, eleven of them without a guard that had been fixed upstream for weeks.
The checks arrive at the ref the workflow pins, in CI and in a local `make check` alike.

Omit the layers the project does not have. A single-service tool has no `screens/`; a library has
no `api/`. Do not rename them — the tooling looks for these names.

### 3. Write the layers bottom-up by how reliable the knowledge is

Not top-down by the diagram:

1. `services/` — what the services or modules even are and who owns what. The most verifiable.
2. `api/` — the contracts between them, written from the route code, because a mistake here is the
   most expensive one in the tree.
3. `features/` — what it gives the user, plus BDD. Rests on the two layers below it.
4. `screens/` — if there is a client.

Common to every layer:

* **One document, one entity.** A feature touching three services is **one** file with three
  entries in `involved_services`, not three files.
* **`id` in the frontmatter equals the filename.** Cross-layer links are ids in the frontmatter
  *and* ordinary markdown links in the body.
* **Paths instead of copies, always.** DTO fields, config keys, endpoint lists are not duplicated —
  a path is given. A pasted list is wrong within a sprint; a path stays right until the file is
  renamed, and there is a check for that.
* **Language: the project's.** Identifiers, URLs and HTTP header names verbatim as in the code.

Useful optional documents: `infrastructure.md` for everything that lives *between* services and
therefore fits in none of them (environments, domains, credentials, deploy triggers), `workflow.md`
if the process is not the obvious one. A screen built to a design does not get a `design/` folder
of mockups; it gets a `design:` block in its frontmatter (SPEC §3.2.1) pointing at the canvas and
at the directory in the code where one reference PNG per state lives, with a state → stem map that
the checker holds against section 1. The PNGs are code, kept next to the screenshot goldens, and
the parity numbers stay in the pull request that measured them.

For each document: copy the template, fill the frontmatter, then fill the body from what you read
in the code.

### 4. The code anchors table is not optional

Every document needs at least one table of paths into the code. This is the single thing that makes
the documentation worth having for an agent, and it is the one structural rule the checker
enforces. Point at the feature directory or the key file — not at a line number, which moves. Where
the place in a file is the point (research citing what it read), `loans.py:40-52` is checked as the
file, and as missing once the file is shorter than the range ([SPEC §4](SPEC.md)).

The one exception is research, which legitimately predates the code; there the checker warns
instead of failing, and what you cite is the artefact you verified against — **as an address inside
it**, with the separator a jar URL uses:

```
ktor-server-core-3.5.2.klib!/commonMain/io/ktor/server/engine/ShutdownHook.kt
```

Written as a bare path, that line is reported rotten for ever, because no tree here holds it; written
this way it is reported as what it is. The left side has to name something a reader can fetch — a
versioned file, a coordinate, or `owner/repo` — so the notation cannot be used to quiet an anchor
that really has rotted. [SPEC §4.1](SPEC.md).

A document marked `status: deprecated` keeps its anchors as a record of where the behaviour was;
the checker skips them and says so ([SPEC §4](SPEC.md)).

An anchor resolves in its own repository only — the one its first segment names, else its service's,
else the one the documentation lives in — so a path into another repository starts with that
repository's name, or is an address when the checker will not have a clone of it.

### 5. BDD scenarios are acceptance criteria

Write them against behaviour you have confirmed in the code: real status codes, real error strings.
While the code does not exist, mark them *target*. A scenario covered by a test carries an
`**Automated:**` line naming it — `**Automated:** catalog-api LoanRoutesTest` when several
repositories are in play, or just the test when one is, in whatever form that project writes
(`tests/test_store.py::test_name` and `LoanRoutesTest.a renewal is refused` are fine). Several
tests are a comma-separated list, each in its own backticks; after a dash or a semicolon the line is
commentary. The line goes under the scenario it automates — the same line in a business rule is not
counted. The absence of that line means the check is manual, and that asymmetry is worth seeing.

Give every scenario its own `### Scenario: <name>` heading, in English even in a document written
in another language: the heading is what the tools count. The steps under it may be the template's
bullets or a fenced `gherkin` block. Several scenarios in one block are counted as none, and the
report then says 0 about a document full of them ([SPEC.md §3.1](SPEC.md)).

### 6. Quirks sections are the highest-value content

An empty logout handler, a hard-coded test domain, a fire-and-forget sync, state kept in memory
that no restart survives, a config key nothing reads — write these down. They are why someone opens
the file at two in the morning. Do not quietly delete one when it is supposedly fixed; delete it
after verifying the fix.

### 7. Backlog

Research without "what to do next" is an essay, not a working document. Size the backlog to the
project:

* **Up to about thirty items in one repository** → `BACKLOG.md` at the root, items `M-NN` grouped
  under milestones M0…MN as checkboxes. A milestone closes as a whole and gets a summary line: what
  came out beyond the plan, and which research hypothesis was confirmed or refuted.
* **Dozens of items, or several repositories** → one file per item in `docs/backlog/`, flat, plus
  the generated index in `backlog.md`.

Either way: **`stage`, `priority` and `status` are frontmatter fields, not directories**, because
documents cite items by id and re-prioritising must not break a link. There is no separate epic
entity; `epic: feature-<name>` is the grouping.

The tables in `backlog.md` between the markers are generated. Edit the item, run the generator,
commit both.

### 8. Wire the documentation into the repository

Without this step the documents exist and nobody opens them.

1. **The repository's agent instructions** (`CLAUDE.md` or equivalent) get a "how to start a
   session" section: research → backlog → the layer document the task belongs to. This is the
   single highest-leverage line in the whole exercise.
2. **The product README** links to `docs/` in one line.
3. **CI** — copy [templates/workflow-check.yaml](templates/workflow-check.yaml) to
   `.github/workflows/check.yaml`, unchanged, together with the Makefile of step 9. Do not write one
   from memory: several of the decisions in it are not the obvious ones, and each was paid for.

   * **The version of the checks is written once**, in its `uses: youndie/docs-bootstrap@<tag>`
     lines. CI runs the checks at that ref; the Makefile reads the same line and fetches the same
     ref for a local run. A version pinned in the workflow and again anywhere else is two pins, and
     two pins drift. Renovate's github-actions manager bumps the line, so a fix to the checks
     arrives as a pull request instead of never.
   * The action runs `make check` — the same target a contributor runs. A local set that differs
     from the CI set turns "green here, red there" into the normal state of affairs, and then
     neither is read. Checks of the project's own therefore go into the Makefile, not into the
     workflow. Before anything runs, the action asks the Makefile where its checks come from, so a
     pinned `uses:` over a Makefile that still runs copies fails instead of passing under a version
     it does not run.
   * **No path filters.** They save seconds and buy red default branches: a generated file diverges
     from its sources when something outside the listed paths moves, and a new directory is a list
     nobody remembers to update.
   * **Two checks are branch-specific**, and the action runs them around `make check`.
     `status: draft` is an error only on the default branch, because in a pull request it is the
     normal state. The other compares backlog item numbers with the base branch, and how much it
     buys depends on a decision made elsewhere: if every branch commits the regenerated index, two
     branches adding items always conflict in that one file, and the conflict — not this check — is
     what stops them. It earns its keep when the index is rebuilt on the default branch instead.
     Either way it runs **before** `make check`, because both catch the collision and only one of
     them says which branch took the number.
   * **A pull request that cannot be merged runs no `pull_request` workflows at all.** Nothing is
     reported and nothing is red; the checks are simply absent, exactly when the branches have
     diverged most. Anything gated on that event is a backstop rather than a guarantee.
   * **Anchors run on a schedule, not on a pull request, and do not block.** They rot because
     somebody refactored a different repository, so a pull request here is the least likely moment
     for one to break — and a red build nobody caused is a build people learn to ignore.

### 9. Run the checks and fix what they find

Copy [templates/Makefile](templates/Makefile) to the root of the repository — **not** this
repository's own `Makefile`, which checks docs-bootstrap itself: copied into a project it prints
"no docs tree — nothing checked" and goes green having checked nothing. Set the three lines that
are the project's: `DOCS` and `BACKLOG` if the tree is not at `docs/` and `backlog.md`, and
`BACKLOG_FORM` — `files`, `milestones` or `none`, the answer of step 7.

```bash
pip install pyyaml
make check      # the gate and the reports: exactly what CI runs
make fix        # regenerate the backlog index, append missing coverage-map lines
```

The first run fetches the checks at the ref the workflow pins into `.docs-bootstrap/`, which ignores
itself; `make check` then runs the same scripts CI runs. The gate opens with a guard that fails when
its subject is not there — no `docs/`, or `BACKLOG_FORM=files` and no `docs/backlog/B-*.md` —
because every script treats a missing tree as nothing to check, and a gate that cannot find its
subject must not report success. The line it prints names the version of the checks that ran.

Only the goals that run the checks load them: `check`, `gate`, `report` and `fix` — the list in
`DOCS_BOOTSTRAP_GOALS` — and check.mk's own `docs-` targets. The project's other targets below the
template's head — a chart, a stand, a release — and `make` with no goal run without reading the pin
and without the network: make fetches an included file before it runs any goal, so a Makefile that
always included check.mk made every one of them download it on a fresh clone and fail offline. A
goal of the project's own that leads to the checks (`ci: check build`) is added to
`DOCS_BOOTSTRAP_GOALS` above the line that says nothing below is to be edited; left out, it stops
with a message naming that variable. A Makefile copied from an earlier revision of the template
keeps working, and check.mk warns that it is one; it is moved like a Makefile of copies in the
section below — the new template, with the project's own lines carried over.

Checks of the project's own go under `gate:` in the Makefile, where CI runs them too.
`DOCS_BOOTSTRAP=<dir> make check` runs the checks from a directory instead — a clone of
docs-bootstrap being changed, or, offline or without GitHub Actions, a committed copy of its
`check.mk`, `scripts/` and `.claude-plugin/`. That is the copy route again, with its drift: the
fallback, not the default.

The two reports are non-blocking on purpose. Demanding a percentage of automated scenarios is
meaningless while acceptance is manual, and an anchor goes stale because of a refactor in somebody
else's repository, not because of an edit here — a machine cannot tell a live path from one quoted
as obsolete. `make fix` regenerates the index and appends the coverage-map lines you forgot; the
descriptions it writes are placeholders, and finishing them is yours.

## When the repository already carries copies of the checks

Repositories documented before 0.3.0 copied `scripts/` and a Makefile in. Moving one to the pinned
checks, in one pull request:

* **`scripts/backlog_index.py`, `docs_check.py`, `coverage_map.py`, `bdd_report.py`,
  `code_anchors.py`** → delete them. A script of the project's own stays, and its line moves under
  `gate:` in the new Makefile.
* **The Makefile** → [templates/Makefile](templates/Makefile). Carry over `DOCS`, `BACKLOG`,
  `REPOS` and the project's own gate lines; set `BACKLOG_FORM`; a target of the project's own that
  runs `check`, `gate`, `report` or `fix` goes into `DOCS_BOOTSTRAP_GOALS`. A hand-written guard
  (`test -d docs`, a count of `docs/backlog/B-*.md`) goes — `docs-guard` in check.mk does that now.
* **`.github/workflows/check.yaml`** → the steps `setup-python`, `pip install pyyaml`, the
  `backlog_index.py --against` step, `make check` and the `docs_check.py --on-main` step become one
  `uses: youndie/docs-bootstrap@<tag>`, the tag in
  [templates/workflow-check.yaml](templates/workflow-check.yaml); the anchors job's steps become the
  same line with `target: report`. Steps that are not the documentation gate — a formatter, a build —
  stay as they are.
* **`docs/templates/`** → leave it, or refresh it from [templates/](templates/): the copies of
  0.3.0 and earlier tell an author to run `python3 scripts/backlog_index.py`, which is gone once the
  copies are; from 0.3.1 they say `make fix` and `make check`.
* **Renovate** needs nothing when the repository extends a preset with the github-actions manager
  on, which is the default.

Then `make check` locally and the check job in CI print the same `docs-bootstrap <version>` line.

## When the documentation already exists

Do not rewrite it. Report the discrepancy between what a document claims and what the code does,
and let the person who owns the meaning decide. The `main` invariant only holds while that is true;
an agent that silently overwrites hand-written documents breaks it in one commit.

Extend instead: add the missing layer, add the anchors table to a document that has none, add the
quirk you just discovered.

## What not to do

- **Do not put research off until after the structure is in place.** Structure without research is
  empty files with the right names, and they begin lying by existing.
- **Do not retell the code.** If a paragraph can be replaced by a path, replace it.
- **Do not enforce the section structure of the templates.** Documents legitimately deviate — a
  feature that is mostly a reality check has no business-rules section. Check the substance
  instead: is there a path into the code?
- **Do not treat an empty list as a mistake.** `client_entries: []` is the answer "this feature has
  no client surface".
- **Do not invent a layer that is not there.** No client, no `screens/`; one service, and
  `services/` may be a single file or a section of the README.
- **Do not write a number you have not seen.** Measured figures name what was measured and how;
  everything else is a hypothesis and says so.
