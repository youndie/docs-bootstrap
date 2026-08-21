# WORKFLOW — the docs-first process

The format in [SPEC.md](SPEC.md) does not require a process. This is the one it grew out of, in
case it is useful; skip it if your team already has one that works.

## The invariant

> **`main` in docs describes what exists. An open pull request describes what will be.**

While a feature does not work, its docs pull request stays open. A merged docs pull request means:
the behaviour is implemented, it was checked, and the description matches reality. That is why BDD
scenarios are written against the intended behaviour and then **verified against the actual one**
— status codes, error strings — before the merge.

Everything below is machinery for keeping that one sentence true.

## Phases

```
┌─ 1. Design ──────────┐   ┌─ 2. Research ────────┐   ┌─ 3. Implement ───────┐
│ architect            │   │ analyst / developer  │   │ developers           │
│ PR in docs:          │──▶│ draft PR in every    │──▶│ code in the same     │
│ feature + screens +  │   │ affected repo, tied  │   │ branches, merged in  │
│ endpoints (+ service │   │ to the docs PR       │   │ contract order       │
│ deltas), BDD         │   │                      │   │                      │
└──────────────────────┘   └──────────────────────┘   └──────────┬───────────┘
                                                                 ▼
┌─ 5. Close ──────────────────────────┐   ┌─ 4. Test ─────────────────────────┐
│ merge the docs PR, update the       │◀──│ deploy, run the BDD scenarios as  │
│ coverage map                        │   │ the acceptance checklist          │
└─────────────────────────────────────┘   └───────────────────────────────────┘
```

### 1. Design — a pull request in docs

The architect opens `feature/<kebab-name>` and adds or changes the feature document (including the
BDD scenarios, which are the future acceptance criteria, and the flow section with the auth tier of
every cross-service call), the screen and endpoint documents, and any deltas in service documents.

The body of the pull request is the **hub of the feature**: a checklist of all the service pull
requests, still empty, and the status of each phase. Reviewing this pull request *is* the
architecture review. Arguments about the contract happen here, before the code.

### 2. Research — a draft pull request in each service repository

In every affected repository, open a **draft** pull request from a branch with the same name. Its
first commit is `research/feature-<kebab-name>.md`, from
[templates/research-feature.md](templates/research-feature.md): which modules are touched with
paths, migrations and compatibility, the step-by-step plan.

Research is a **file in the branch**, not a pull-request description, on purpose: the coding agent
reads the working tree, and paths are only clickable there. The description carries a link to the
docs pull request and a short summary; the full version is in the file.

**The research file is deleted before its pull request merges.** Anything worth keeping has moved
into the docs pull request (behaviour) or the repository's agent instructions (how the code is
arranged) by then. Research merged into `main` starts lying immediately and misleads the next
reader.

This is the per-feature plan, not the architecture research a single-repository project keeps at
`docs/research/research-architecture.md` for good. The two share a word and have opposite
lifetimes; [SPEC.md §3.5](SPEC.md) is where the difference is set out.

Nothing in the documentation repository can check this half of the invariant — the file is in a
service repository, which has no documentation tree and which none of the checks ever look at. Copy
[templates/workflow-research-guard.yaml](templates/workflow-research-guard.yaml) into each service
repository: it fails the default branch when `research/*.md` is present, and leaves a reminder on a
pull request, where the file belongs.

### 3. Implement — code in the same branches

The agent session in a branch starts by reading the research file plus the feature document from
the open docs pull request. Together they are the assignment.

**Merge order follows the contracts, and is not a matter of taste.** Where a shared module is
published and propagated between repositories:

1. The repository that **produces** the new contract merges first, and CI publishes it.
2. Consumers wait for the new version to reach them (or raise it by hand in their branch to avoid
   waiting), and only then does their code compile against it.
3. If contracts change in a **cycle**, budget two rounds of publish-and-propagate: additive changes
   on both sides first, then use. A breaking contract change cannot be done in one round trip —
   only expand → migrate → contract.

### 4. Test — deploy and accept against the BDD

Acceptance is **running the feature document's BDD scenarios as a checklist**, in the body of the
docs pull request: copy the scenarios in and tick them off. This is not a ritual. Where there are
no automated tests on the pull request, those scenarios are the only systematic list of checks that
exists.

Where behaviour diverges from the document, either fix the code or commit the difference to the
docs pull request. Which one is the architect's call at review.

A scenario that has been automated gets an `**Automated:**` line naming the test, so that what is
still manual stays visible.

### 5. Close — merge the docs pull request

Whoever confirmed acceptance merges it. Before merging:

- [ ] all service pull requests merged, the checklist in the body closed;
- [ ] the BDD checklist passed on the test environment;
- [ ] `status:` in new documents moved from `draft` to `active`;
- [ ] the coverage map in `docs/README.md` updated.

## Linking rules

| What | How |
|---|---|
| Branch name | `feature/<kebab-name>` — **identical** in docs and in every service repository |
| Research | `research/feature-<kebab-name>.md` in the service branch; deleted before merge |
| Service PR → docs PR | the full URL in the description |
| docs PR → service PRs | a checklist in the body: `- [ ] catalog-api: <url>` |
| Document → code | the `source:` field (screen), `contract_source:` (endpoint), the anchors table (everywhere) |

## Small changes

Not everything needs the full cycle. A change inside one service that alters neither a contract nor
any behaviour described in the docs is an ordinary pull request. The rule is short:

> **If merging it would make some document a lie, it needs a docs pull request. Otherwise it does
> not.**

## Deliberately out of scope

- Automating the pull-request ↔ docs links with bots or status checks. Done by hand, by the rules
  above.
- Screenshots and mockups in screen documents.
- Running the BDD scenarios automatically as end-to-end tests.
