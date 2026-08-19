---
feature: feature-<kebab-name>          # the feature id in docs
docs_pr: <full URL of the docs pull request>
repo_scope: <this repository: which modules are affected>
status: research | ready-for-dev | in-dev
---

# Research: <feature name> — <this service>

> A working artefact of the branch `feature/<kebab-name>`. It is read by the coding agent as the
> assignment, so write file paths and specifics, not generalities.
> **Delete it before the pull request merges**; anything worth keeping moves to the docs pull
> request (behaviour) or to the repository's agent instructions (how the code is arranged).

This template is the exception in the set: it is **not** copied into the docs repository. It goes
into a branch of the service repository as `research/feature-<name>.md`.

## 1. What we are building (in your own words)

One paragraph: this service's contribution to the feature. Link the BDD scenarios that this
repository closes.

## 2. Affected code, with paths

| What | Where | Action |
|---|---|---|
| contract | `<shared>/<Contract>` | add … |
| route | `<server>/<feature>/<Routes>` | new endpoint, tier: … |
| use case | `<server>/<feature>/domain/` | new … |
| repository | `<server>/<feature>/data/` | new field in the stored model |

## 3. Contracts and merge order

- Does the shared contract change? If so, is this pull request the **producer** or the
  **consumer** of the new contract? That decides the merge order.
- Is it a breaking change? If so, plan expand → migrate → contract.

## 4. Data and compatibility

- Migrations — and whether the migration hook is actually wired up, rather than assumed.
- Behaviour with old data and old clients.
- Is a feature flag needed?

## 5. Implementation plan

1. …
2. …
3. Tests: which scenarios get automated and in which suite.

## 6. Open questions

- [ ] … Questions for the architect are resolved by a commit to the docs pull request, not here.

## 7. Findings

What the code turned out to be, where it contradicted the expectation. Move these out as they
appear — to the agent instructions (how the code is arranged) or to the docs pull request
(behaviour). Do not let them pile up here; this file is about to be deleted.
