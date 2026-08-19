---
id: <service-id>
title: <Service name>
type: service
repo_url: <https://github.com/<org>/<repo>>
module: <module inside the repo, if there are several>
tech_stack: [<language>, <framework>, <datastore>, <runtime>]
owner: unassigned
depends_on:
  - <service-id | external system>
publishes:
  - <artifact / image>
---

# <Service name>

## 1. Responsibility

Which data it owns, which operations it is responsible for, and — just as important — what it
deliberately does **not** do.

## 2. API contracts

* **Generated schema:** `<path>` (produced from the routes; internal routes hidden)
* **Contracts:** `<shared module>`
* **Auth tiers:** the "mount → gate" table, or a link to the repository's agent instructions

## 2a. Code anchors

Every piece of work in this service starts from these files:

| File | What is there |
|---|---|
| `<path>/Routes.<ext>` | composition of all routes + auth tiers |
| `<path>/Modules.<ext>` | dependency wiring + config bindings |
| `<path>/config.<ext>` | configuration |
| `<path>/migrate.<ext>` | migrations (check whether it is empty) |

## 3. How it is built <!-- optional, but usually the most useful section -->

The mechanics that are not visible from any single file: the order things run in, why it goes
through a queue instead of a lock, where the thread boundary is. With the reasoning — *why this way
and not the obvious one* — because the obvious way is what the next reader will otherwise try.

## 4. Dependencies

| Kind | Name | What for |
|---|---|---|
| Database | … | … |
| Service | <service-id> | … |
| External | … | … |

## 5. Infrastructure and deploy

* **Image:** `<name>`
* **Chart / manifest:** `<repo>/<path>`
* **Health:** `GET /health`
* **Metrics:** `GET /metrics` <!-- optional -->
* **Version:** `GET /version` <!-- optional -->

## 6. Local setup

```bash
<the command that actually starts it>
```

What else has to be running or mocked.

## 7. Configuration

| Key | Description | Required |
|---|---|---|
| `<KEY>` | … | yes |

Do not copy the full config file here — link to it. A copied key list rots; a path does not.

## 8. Quirks <!-- optional -->

Empty handlers, hard-coded test values, fire-and-forget jobs, in-memory state that survives no
restart. Write these down; they are the reason someone reads this file at two in the morning.
