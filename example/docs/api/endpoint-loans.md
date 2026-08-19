---
id: endpoint-loans
title: Loans and holds
type: api_endpoints
status: active
services:
  - loans-service
contract_source:
  - loans-service:src/loans_service/routes ROUTES
  - loans-service:src/loans_service/domain/loan.py Loan, LoanError
  - loans-service:src/loans_service/domain/holds_queue.py Hold
parent_feature: feature-borrow-and-return
---

# API: Loans and holds

> The **complete** route reference for [loans-service](../services/loans-service.md). Two features
> share it —
> [feature-borrow-and-return](../features/feature-borrow-and-return.md) and
> [feature-holds-queue](../features/feature-holds-queue.md) — because they share a service and a
> transaction: a return closes a loan and promotes a hold in one call.

## Routes — all of them, no exceptions

| Method and path | Service | Auth tier | In the published schema? | Purpose |
|---|---|---|---|---|
| `POST /api/loans` | loans-service | staff session | n/a | check a copy out to a member |
| `POST /api/loans/{loan_id}/renew` | loans-service | staff session | n/a | extend the due date |
| `POST /api/loans/{loan_id}/return` | loans-service | staff session | n/a | close the loan, promote the queue |
| `GET /api/members/{member_id}/loans` | loans-service | staff session | n/a | open loans + the `blocked` flag |
| `GET /internal/loans/overdue` | loans-service | service token | n/a (hidden) | every loan past due, oldest first |
| `POST /api/holds` | loans-service | staff session | n/a | place a hold on a book |
| `DELETE /api/holds/{hold_id}` | loans-service | staff session | n/a | cancel a hold |
| `GET /api/books/{book_id}/holds` | loans-service | staff session | n/a | the queue, with positions |
| `POST /internal/holds/expire` | loans-service | service token | n/a (hidden) | close uncollected ready holds |

**The column says `n/a` because loans-service publishes no schema.** The `hidden` flag is set on
the two internal routes for symmetry with [endpoint-catalog](endpoint-catalog.md), and nothing in
this service reads it — there is no counterpart to catalog-api's `openapi.py`. The flag is
documentation that happens to be executable syntax. This table is therefore the only route
reference that exists for the service.

**Auth tiers.** `staff session` is the proxy's cookie; `service token` is `X-Service-Token`
compared against `LOANS_SERVICE_TOKEN`. `member_id` in a path is a string the service accepts as
given — it is never checked against the session, so any librarian can read any member.

## Handlers (code anchors)

| Route | Handler |
|---|---|
| `POST /api/loans` | `loans-service/src/loans_service/routes/loans.py` → `create_loan` |
| `POST /api/loans/{loan_id}/renew` | `.../routes/loans.py` → `renew_loan` |
| `POST /api/loans/{loan_id}/return` | `.../routes/loans.py` → `return_loan` |
| `GET /api/members/{member_id}/loans` | `.../routes/loans.py` → `member_loans` |
| `GET /internal/loans/overdue` | `src/loans_service/routes/loans.py` → `overdue_loans` |
| `POST /api/holds`, `DELETE /api/holds/{hold_id}` | `loans-service/src/loans_service/routes/holds.py` → `place_hold`, `cancel_hold` |
| `GET /api/books/{book_id}/holds` | `.../routes/holds.py` → `book_holds` |
| `POST /internal/holds/expire` | `.../routes/holds.py` → `expire_holds` |
| the outbound half | `.../routes/loans.py` → `CatalogClient` — the only place this service calls catalog-api |

## Request and response bodies

Bodies are built by two serialisers, and those are the contract: `_loan_json` in `routes/loans.py`
and `_hold_json` in `routes/holds.py`. The dataclasses behind them are `Loan` in
`domain/loan.py` and `Hold` in `domain/holds_queue.py`.

Three things about the shapes are worth stating because they are not visible in a field list:

* `state` in a loan object is **computed** (`Loan.state(today)`), never stored. A stored row has
  no overdue flag; the API is where "overdue" comes into existence.
* `position` in a hold object is likewise computed at read time by `holds_queue.position_of`.
* `POST /api/loans/{id}/return` answers `{"loan": ..., "next_hold": ...}`, where `next_hold` is
  `null` when the copy goes back to the shelf and `{id, member_id, barcode}` when it goes to the
  hold shelf. The barcode is echoed so the librarian knows which book in their hands to label.

Request bodies: `{"barcode", "member_id"}` for a checkout, `{"book_id", "member_id"}` for a hold.
Renew, return, cancel and both internal routes take no body.

## Errors

Every error is `{"error": "<message>"}`. The messages for policy failures are raised as
`LoanError(status, message)` in `domain/loan.py` and `domain/holds_queue.py`, so the route and the
rule cannot drift apart.

| Condition | Status | Body |
|---|---|---|
| `barcode` or `member_id` missing | `400` | `{"error": "barcode and member_id are required"}` |
| `book_id` or `member_id` missing | `400` | `{"error": "book_id and member_id are required"}` |
| catalog-api does not know the barcode | `404` | `{"error": "copy not found"}` |
| copy is `in_repair` or `lost` | `409` | `{"error": "copy is not lendable"}` |
| copy is already on an open loan | `409` | `{"error": "copy already on loan"}` |
| a hold on the book is ready for somebody else | `409` | `{"error": "copy is held for another member"}` |
| the member has a loan >30 days overdue | `403` | `{"error": "member is blocked"}` |
| the member has 10 open loans | `422` | `{"error": "loan limit reached"}` |
| unknown `loan_id` | `404` | `{"error": "loan not found"}` |
| the loan is closed | `409` | `{"error": "loan already returned"}` |
| the loan was written off | `409` | `{"error": "loan is closed as lost"}` |
| two renewals already used | `409` | `{"error": "renewal limit reached"}` |
| somebody is waiting for the book | `409` | `{"error": "renewal blocked by holds"}` |
| the member already holds this book | `409` | `{"error": "hold already placed"}` |
| the member already has it on loan | `409` | `{"error": "member already has this book on loan"}` |
| the member has 5 open holds | `422` | `{"error": "hold limit reached"}` |
| unknown `hold_id` | `404` | `{"error": "hold not found"}` |
| the hold is cancelled, expired or fulfilled | `409` | `{"error": "hold already closed"}` |

One row in that table is **unreachable today**: `loan is closed as lost`. `declare_lost` exists in
`domain/loan.py`, nothing calls it, and no route sets `Loan.lost`. It is listed rather than omitted
because the state machine has the state and a reader who finds `lost` in the code should learn here
that nothing produces it.

`422` versus `409` is a real distinction here and not a preference: `409` means the object in the
librarian's hands is in the wrong state, `422` means the member has hit a policy limit. The desk
shows both verbatim, so the wording is user-facing text.

## Quirks

* **The order of the two `409`s is deliberate.** `create_loan` looks for an open loan on the
  barcode *before* it looks at the copy status, so a copy the two services disagree about answers
  `copy already on loan` rather than `copy is not lendable`. The first message tells the librarian
  what happened; the second tells them to look at the copy.
* **A checkout that half-succeeds returns `500`.** `create_loan` saves the loan and only then tells
  catalog-api the copy is on loan. If that call raises, the client sees a failure while the loan
  exists and the copy still reads `on_shelf`.
* **`404` from catalog-api is swallowed by design.** `CatalogClient._call` turns `404` into `None`
  and re-raises everything else, which is how "copy not found" reaches the caller as a clean `404`
  instead of a `500`. Any other catalog failure is an unhandled `500` here.
* **`DELETE /api/holds/{id}` answers `204` with no body**, unlike every other route in the service.
  A client that parses the response unconditionally has to special-case it; `client.js` does, by
  checking for empty text before `JSON.parse`.
