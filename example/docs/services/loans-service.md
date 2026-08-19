---
id: loans-service
title: loans-service
type: service
repo_url: https://github.com/example-library/loans-service
module: src/loans_service
tech_stack: [Python, PostgreSQL, SMTP]
owner: unassigned
depends_on:
  - catalog-api
  - PostgreSQL
  - SMTP relay
publishes:
  - "loans-service (container image)"
---

# loans-service

## 1. Responsibility

Owns everything that connects a member to a copy: loans, renewals, returns, the holds queue, and
the overdue notice job. It is the only service that knows a member id exists.

It deliberately does **not** own the copy's location. When a loan opens or closes it *asks*
[catalog-api](catalog-api.md) to move the copy, and it accepts the answer; there is no local mirror
of the shelf state to fall out of sync.

It also does not own members. `member_id` is a string it stores and compares — there is no member
record, no name and no email address anywhere in the service. See the quirks; this is felt.

## 2. API contracts

* **Published schema:** none. The `hidden` flag on `Route` is set on the internal routes and is
  read by nothing, so [endpoint-loans](../api/endpoint-loans.md) is the only route reference that
  exists.
* **Contracts:** `_loan_json` (`routes/loans.py`) and `_hold_json` (`routes/holds.py`) are the
  response contract; `Loan` and `Hold` are the dataclasses behind them.
* **Errors:** every policy failure is a `LoanError(status, message)` raised in the domain, so the
  status code and the user-facing string live next to the rule that produces them.
* **Auth tiers:** `/api/**` trusts the staff session from the reverse proxy; `/internal/**` needs
  `X-Service-Token` equal to `LOANS_SERVICE_TOKEN`.

## 2a. Code anchors

| File | What is there |
|---|---|
| `loans-service/src/loans_service/domain/loan.py` | the state machine, the policy checks, and every error string |
| `loans-service/src/loans_service/domain/holds_queue.py` | queue order, positions, readiness, expiry |
| `loans-service/src/loans_service/routes/loans.py` | checkout / renew / return, plus `CatalogClient` — the only outbound call in the service |
| `.../routes/holds.py` | place, cancel, list, expire |
| `.../data/loan_repository.py` | the storage contract; the in-memory implementation the dev server runs |
| `src/loans_service/jobs/overdue_notices.py` | the daily job and `SmtpMailer` |
| `src/loans_service/config.py` | the whole lending policy as environment variables |
| `loans-service/tests/test_loan_rules.py` | the two automated renewal scenarios |

## 3. How it is built

Three orderings in this service are decisions rather than accidents, and each is the thing a
reader gets wrong first:

* **Checkout validates its own state before the catalogue's.** `create_loan` looks for an open loan
  on the barcode and only then at `copy["status"]` — when the two services disagree, "copy already
  on loan" names what happened and "copy is not lendable" does not. The loan is saved *before*
  `CATALOG.set_copy_status()`, so a failure after the save leaves a stale catalogue rather than a
  book with no borrower. See [research-architecture](../research/research-architecture.md), D3.
* **Return closes the loan and promotes the next hold against one store**, which is why loans and
  holds share `LoanRepository` instead of getting a repository each.
* **The notice job marks a loan notified before the mail leaves.** That ordering is the bug behind
  [B-01](../backlog/B-01-retry-failed-overdue-notices.md), not a retry policy; it is listed under
  quirks as well because it is what surprises people at three in the morning.

Everything above `data/` is ignorant of storage: the domain modules take collections and return
values, which is why `test_loan_rules.py` needs no fixtures.

## 4. Dependencies

| Kind | Name | What for |
|---|---|---|
| Database | PostgreSQL | loans and holds — see the quirks about what actually stores them today |
| Service | [catalog-api](catalog-api.md) | resolve a barcode, move a copy between statuses |
| External | SMTP relay | overdue notices, one connection per message |
| External | reverse proxy | the staff session; the service authenticates nobody itself |
| External | a scheduler | calls the notice job and `POST /internal/holds/expire`. Neither has a caller inside this repository |

## 5. Infrastructure and deploy

* **Image:** `loans-service`
* **Health:** none — `ROUTES` in the two route modules is the complete list.
* Build and chart files are not part of this example repository.

## 6. Local setup

```bash
python3 loans-service/tests/test_loan_rules.py     # the renewal rules, no server needed
python3 -m pytest loans-service/tests              # same, if pytest is installed
```

The domain runs with no dependencies at all. Exercising a route needs catalog-api reachable at
`CATALOG_API_URL`, because `create_loan` resolves the barcode before it does anything else.

## 7. Configuration

| Key | Description | Required |
|---|---|---|
| `LOANS_DATABASE_URL` | PostgreSQL DSN | yes |
| `CATALOG_API_URL` | base URL of catalog-api | yes |
| `LOANS_SERVICE_TOKEN` | sent as `X-Service-Token` to catalog-api and expected on `/internal/**` | yes |
| `LOANS_SMTP_URL` | `smtp://host:port` for the notice job | yes |
| `LOANS_NOTICE_FROM` | sender address of the notices | no |
| `LOAN_PERIOD_DAYS` | loan period, default 21 | no |
| `LOAN_MAX_RENEWALS` | renewals per loan, default 2 | no |
| `LOAN_MAX_ACTIVE` | open loans per member, default 10 | no |
| `HOLD_MAX_ACTIVE` | open holds per member, default 5 | no |
| `HOLD_PICKUP_DAYS` | days a ready hold waits, default 3 | no |
| `LOAN_BLOCK_AFTER_DAYS` | overdue days that block a member, default 30 | no |
| `LOAN_NOTICE_DAYS` | comma-separated notice days, default `1,7,14` | no |
| `LOAN_GRACE_DAYS` | see the quirks — nothing reads it | no |

`config.py` is the only module that touches the environment; the lending policy lives there rather
than in the code that applies it, because the policy is what a library changes and the state
machine is not.

## 8. Quirks

* **The overdue notice is fire-and-forget, and in the wrong order.** `run` in
  `jobs/overdue_notices.py` writes `last_notice_day` and saves the loan *before* handing the
  message to SMTP. A refused connection is logged at WARNING and the loan is marked as notified,
  so one outage removes a whole day of notices with no trace but a log line.
  [B-01](../backlog/B-01-retry-failed-overdue-notices.md).
* **`LOANS_DATABASE_URL` is read and no code opens a connection.** `LoanRepository` is four
  dictionaries in a module-level singleton. Everything — loans, holds, queue positions — is lost on
  restart, and the DSN in the environment makes it look otherwise. The class exists to be the shape
  a SQL implementation has to satisfy, not to be it.
* **`LOAN_GRACE_DAYS` does nothing.** Read into `CONFIG.grace_days`, referenced by no other module.
  A loan is overdue the day after its due date and no setting changes that.
* **`hidden` is set and never read.** The flag on the two internal routes is copied from
  catalog-api's convention, but this service builds no schema, so nothing keeps `/internal/**` out
  of anything. What actually keeps those routes internal is the proxy and the service token.
* **A blocked member can still renew.** The block is checked in `create_loan` only —
  [B-03](../backlog/B-03-block-renewals-for-blocked-members.md).
* **The `lost` state has no way in.** `Loan.lost` is honoured everywhere — `state`,
  `open_loans_of`, `overdue_loans`, `renew` — and set by nothing: `declare_lost` has no route. A
  lost book is currently an overdue book forever.
