---
id: feature-<kebab-name>
title: <Feature name>
type: feature
status: draft | active | deprecated
owner: unassigned
involved_services:
  - <service-id from services/>
client_entries:
  - <screen-id or flow-id from screens/>   # [] means "no client surface"
api:
  - <endpoint-id from api/>                # [] means "no HTTP surface"
tags: []
---

# <Feature name>

## 1. Overview

One or two paragraphs: what the user gets and why. No implementation detail.

## 2. Business rules

* A rule phrased so that it can be checked.
* …

## 3. Flow <!-- optional -->

The sequence of calls between services — an arrow diagram or a numbered list. State the auth tier
of every cross-service call (end-user credential / service credential).

## 4. Code anchors

Entry points into the implementation, per service — so that a reader reaches the code in one hop.
Point at the feature directory or the key file:

| Service | Code |
|---|---|
| <service-id> | `<repo>/<module>/<path>/<feature>/` |
| <service-id> | `<repo>/<shared module>/<Contract>` — the contract |

## 5. Scenarios (BDD / test cases)

Write these against the behaviour the code actually has: real status codes, real error strings.
Mark an automated scenario with a link to its test — that is how it stays visible which checks are
still manual.

### Scenario: <happy path>
* **Given:** …
* **When:** …
* **Then:** …
* **And:** …
* **Automated:** `<repo> <TestName>` <!-- omit the line entirely if the check is manual -->

### Scenario: <the interesting failure>
* **Given:** …
* **When:** …
* **Then:** the system returns `<status>` with `<error text or code>`.

## 6. Out of scope

* …

## 7. Quirks <!-- optional -->

Behaviour that is easy to mistake for a bug, or the reverse: undocumented 404s, compensating
actions, races. This section is load-bearing — a documented surprise is the highest-value content
in the file. Delete an entry only after verifying the fix, not when someone claims it is fixed.
