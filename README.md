# docs-bootstrap

A documentation format for codebases whose primary reader is a coding agent, and the checks that
keep it honest.

Four layers linked by ids, and a fifth above them that says why. Every document carries paths into
the code, so a reader — human or agent — gets from a claim to the source in one hop. Nothing in a
document duplicates what lives in the code, because a copy is wrong within a sprint and a path is
not.

```
[ Research — why the architecture is this one; verified vs hypothesis ]   optional
                        │
[ Feature — what the system does and why, + BDD scenarios ]
                        │
[ Client screen or flow — states, actions, navigation ]
                        │
[ API endpoint — the complete route reference, auth tiers ]
                        │
[ Service — ownership, dependencies, deploy, quirks ]
```

## What is here

| | |
|---|---|
| [SKILL.md](SKILL.md) | the skill: how an agent bootstraps or extends this documentation for a repository |
| [SPEC.md](SPEC.md) | the format contract — layers, frontmatter, anchors, `spec_version: 1` |
| [templates/](templates/) | one template per document type, two CI workflows and the Makefile a project copies |
| [scripts/](scripts/) | the checks: link graph, coverage map, backlog index, code anchors, BDD count |
| [action.yml](action.yml), [check.mk](check.mk) | the checks as a GitHub Action and a make include, run at the version a project pins |
| [example/](example/) | a complete worked instance — a small library lending system, code and docs |
| [WORKFLOW.md](WORKFLOW.md) | the docs-first process the format grew out of; optional |
| [.out-of-scope/](.out-of-scope/) | what this repository was asked for and declined, with the reasons |

## Install

Two routes, and they differ in who owns the files afterwards.

**As a plugin**, if you would rather subscribe than fork. The repository is its own marketplace:

```bash
claude plugin marketplace add youndie/docs-bootstrap
claude plugin install docs-bootstrap@docs-bootstrap
```

**As a clone**, if you intend to edit it. [SKILL.md](SKILL.md) is a Claude Code skill, so the clone
path *is* the installation — the directory name has to match the `name:` in its frontmatter:

```bash
git clone https://github.com/youndie/docs-bootstrap ~/.claude/skills/docs-bootstrap
```

Either way, then ask your agent to document a repository. It will read `SPEC.md`, survey the code,
and write the tree.

Nothing here depends on that packaging. `SKILL.md` is a markdown file of instructions and any agent
that can be handed one will follow it — [agents/openai.yaml](agents/openai.yaml) is how it
introduces itself to the ones that are not Claude Code — and the half that is not the skill (the
format contract, the templates and the checks) is plain files and six Python scripts that answer to
`make check`. A team writing these documents by hand gets the same gate.

**The checks in a documented repository** come from here too, at a pinned version, rather than as
copies. Two files are copied once — [templates/workflow-check.yaml](templates/workflow-check.yaml)
and [templates/Makefile](templates/Makefile) — and the version lives in one place: the
`uses: youndie/docs-bootstrap@<tag>` line of the workflow. CI runs the checks at that tag; the
Makefile reads the same line and fetches the same tag for a local `make check`; Renovate bumps it.
Copied scripts used to be the route, and that is how 18 copies of one script came to exist in three
versions. [SKILL.md](SKILL.md), steps 8 and 9, has the details and the offline fallback.

## The two rules

> **`main` describes what exists. An open pull request describes what will be.**

Intent is never documented as fact. A designed but unshipped feature is `status: draft` and lives
in an open pull request. `scripts/docs_check.py --on-main` turns a draft that reached the default
branch into an error.

> **What was verified is separated from what was assumed, explicitly.**

Every status code, error string and limit is read out of the source before it is written down, and
a claim that was not verified says so. A document that does not distinguish the two is worse than
no document: it reads as equally authoritative either way. This is why the format is built around
paths, why `code_anchors.py` exists, and why the research layer records where each fact was
checked.

## The example is the specification you can run

`example/` is a small library lending system: one architecture research document, three services,
three features, two screens, two endpoint references, six backlog items — and a real, if tiny, code
tree underneath, so that every anchor in every document resolves to a file that exists.

That is not decoration. It means this repository's own CI runs the checks against its own example,
through the same Makefile template and the same action a documented repository uses:

```bash
pip install pyyaml
make check
```

A format that claims to be machine-checkable and does not check itself is asking to be taken on
faith.

## What the checks do, and what they refuse to do

| Script | Guards | In CI |
|---|---|---|
| `docs_check.py` | link graph across the layers, `id` = filename, required fields, `status` vocabulary, at least one path into the code, a screen's `design.states` naming states the document lists; **warns** about scenarios no tool can count — a gherkin block with no `### Scenario:` heading of its own is reported as 0 everywhere else | blocking |
| `coverage_map.py` | the map in `docs/README.md` matches the files on disk | blocking |
| `backlog_index.py` | the generated index matches the items; no duplicate numbers or slugs; `blocked_by` resolves; **under `--check`, that the items are there at all** — a backlog lost to a merge used to exit 0 (`--allow-missing` for a project without its first item yet) | blocking |
| `plugin_check.py` | the skill's name in `SKILL.md`, `plugin.json` and `marketplace.json` is one name, and every declared skill directory holds a `SKILL.md`; the tag `templates/workflow-check.yaml` pins is that version; **on a pull request, that a change to anything the plugin ships raises `version` above the base branch's** — otherwise `claude plugin update` never sees it | blocking |
| `script_selftest.py` | what the scripts above do on the cases `make check` cannot reach, since it runs them against the example: a tree that is **absent**, and defects the example does not carry — each guard held from both sides, a fixture that must trip it and one that must not | blocking |
| `bdd_report.py` | counts scenarios and how many are automated | report |
| `code_anchors.py` | whether the paths still exist, the design reference PNGs of a screen included | report, scheduled |

Three things they deliberately do **not** do:

- **They do not enforce the template's section structure.** Documents legitimately deviate: a
  feature that is mostly a reality check has no business-rules section. What is checked is the
  substance of the rule — that there is at least one path into the code.
- **They do not confuse an empty list with forgetfulness.** `client_entries: []` is the answer
  "this feature has no client surface"; a missing field is a question, and only a warning.
- **They do not block on code anchors.** An anchor breaks because of a refactor in someone else's
  repository, not because of an edit here, and a path quoted *as obsolete* is
  indistinguishable from a live one by machine. A person reads that report.

## Status

`spec_version: 1`. Additive changes keep the version; anything that would make a v1 reader wrong
raises it. See [SPEC.md §8](SPEC.md).

## License

MIT.
