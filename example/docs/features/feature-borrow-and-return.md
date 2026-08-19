---
id: feature-borrow-and-return
title: Borrowing and returning a book
type: feature
status: active
owner: unassigned
involved_services:
  - catalog-api
  - loans-service
  - librarian-web
client_entries:
  - screen-checkout-desk
api:
  - endpoint-loans
  - endpoint-catalog
tags: [lending, desk]
---

# Borrowing and returning a book

## 1. Overview

A member brings a book to the desk. The librarian scans the member card and the barcode, and the
copy leaves the building for three weeks. The same desk takes it back, renews it, and tells the
librarian when the returned copy belongs to somebody else's hold rather than to the shelf.

Two services split the work along the line of ownership: [catalog-api](../services/catalog-api.md)
knows where a physical copy is, [loans-service](../services/loans-service.md) knows who has it.
Neither knows the other's half, which is why every checkout is two calls rather than one.

The surface is one screen — [screen-checkout-desk](../screens/screen-checkout-desk.md) in
[librarian-web](../services/librarian-web.md) — over the routes in
[endpoint-loans](../api/endpoint-loans.md) and [endpoint-catalog](../api/endpoint-catalog.md).

## 2. Business rules

* The loan period is 21 days (`loan_period_days`). The due date is the day the copy was taken plus
  the period; there is no rounding to opening hours.
* A member may hold up to 10 open loans at once (`max_active_loans`). The eleventh checkout is
  refused.
* A loan may be renewed twice (`max_renewals`). A renewal adds a **full loan period to the current
  due date**, not to the day of the renewal — renewing early costs the member nothing.
* A renewal is refused while anybody is waiting for the book. See
  [feature-holds-queue](feature-holds-queue.md).
* A member with any single loan more than 30 days overdue (`block_after_overdue_days`) is blocked
  and cannot take a new book.
* A copy can be lent only from `on_shelf` or `held`. `in_repair` and `lost` copies are refused.
* Returning is unconditional: a blocked member, an overdue loan and a lost-and-found copy are all
  returned the same way.

## 3. Flow

```
librarian-web ── POST /loans/api/loans {barcode, member_id} ──▶ loans-service   (staff session)
                     loans-service ── GET /internal/copies/{barcode} ──▶ catalog-api  (service token)
                     loans-service ── POST /internal/copies/{barcode}/status {"status":"on_loan"} ──▶ catalog-api
                 ◀── 201 {id, due_on, renewals_left, state}

librarian-web ── POST /loans/api/loans/{id}/return ──▶ loans-service
                     first waiting hold, if any, becomes ready
                     copy status ──▶ "held" (hold shelf) or "on_shelf"
                 ◀── 200 {loan, next_hold}
```

The browser never talks to catalog-api about copies: `/internal/**` is reachable only with the
service token, which lives in loans-service.

## 4. Code anchors

| Service | Code |
|---|---|
| loans-service | `loans-service/src/loans_service/domain/loan.py` — the state machine and every policy error string |
| loans-service | `src/loans_service/routes/loans.py` — checkout, renew, return, member loans |
| loans-service | `loans-service/src/loans_service/config.py` — period, limits, block threshold |
| catalog-api | `.../catalog_api/routes/availability.py` — the internal copy routes |
| catalog-api | `catalog-api/src/catalog_api/domain/book.py` — the copy status graph (`TRANSITIONS`) |
| librarian-web | `librarian-web/src/pages/CheckoutDesk.jsx`, `src/state/checkoutState.js` |

## 5. Scenarios (BDD / test cases)

### Scenario: A copy on the shelf is lent
* **Given:** copy `30001` is `on_shelf` and member `m-100` has no open loans.
* **When:** `POST /api/loans {"barcode": "30001", "member_id": "m-100"}`.
* **Then:** `201` with `due_on` = today + 21 days, `renewals_used: 0`, `renewals_left: 2`,
  `state: "active"`.
* **And:** the copy reads `on_loan` in `GET /api/books/b-1/availability`.

### Scenario: The same copy cannot be lent twice
* **Given:** copy `30001` is already on an open loan.
* **When:** `POST /api/loans` with the same barcode.
* **Then:** `409` with `{"error": "copy already on loan"}`.

### Scenario: A copy in repair is refused
* **Given:** copy `30004` is `in_repair`.
* **When:** `POST /api/loans` with barcode `30004`.
* **Then:** `409` with `{"error": "copy is not lendable"}` — the copy status, not the member, is
  the reason.

### Scenario: A renewal is refused while somebody is waiting
* **Given:** an open loan on a copy of `b-1` and one waiting hold on `b-1`.
* **When:** `POST /api/loans/{id}/renew`.
* **Then:** `409` with `{"error": "renewal blocked by holds"}` and `renewals_used` is unchanged.
* **Automated:** `loans-service test_renewal_blocked_by_holds` in `tests/test_loan_rules.py`

### Scenario: The third renewal is refused
* **Given:** a loan that has been renewed twice and no holds on the book.
* **When:** `POST /api/loans/{id}/renew`.
* **Then:** `409` with `{"error": "renewal limit reached"}`.
* **And:** each of the first two renewals moved `due_on` by 21 days from the previous due date.
* **Automated:** `loans-service test_renewal_limit_reached` in `tests/test_loan_rules.py`

### Scenario: The eleventh loan is refused
* **Given:** member `m-100` has 10 open loans.
* **When:** `POST /api/loans` with any lendable barcode.
* **Then:** `422` with `{"error": "loan limit reached"}`.

### Scenario: A long-overdue member is blocked
* **Given:** member `m-100` has one loan 31 days past its due date.
* **When:** `POST /api/loans`.
* **Then:** `403` with `{"error": "member is blocked"}`.
* **And:** `GET /api/members/m-100/loans` answers `200` with `"blocked": true`.

### Scenario: A returned copy goes to the hold shelf
* **Given:** an open loan on copy `30001` and a waiting hold on `b-1` from member `m-200`.
* **When:** `POST /api/loans/{id}/return`.
* **Then:** `200`, `next_hold` names `m-200` and barcode `30001`, and the copy status becomes
  `held` rather than `on_shelf`.

### Scenario: Returning the same loan twice
* **When:** `POST /api/loans/{id}/return` on a loan that is already closed.
* **Then:** `409` with `{"error": "loan already returned"}`. A book scanned twice at the desk is
  therefore an error rather than a silent success — the librarian is told, because the second scan
  usually means the first one went to the wrong pile.

## 6. Out of scope

* Fines and payments. An overdue loan blocks the member; it never costs money.
* Member registration and the member directory — loans-service stores a `member_id` string and
  never resolves it.
* Inter-library loans, reading-room-only copies, and anything the member does without a librarian.

## 7. Quirks

* **Renewing early is worth more than renewing late.** The period is added to the current due date,
  so a member who renews on day 1 ends up with 41 days remaining and one who renews on day 21 ends
  up with 21. This is deliberate — the alternative punishes the member who came in early — but it
  regularly reads as an arithmetic bug in support tickets.
* **A blocked member can still renew.** The block is checked in `create_loan` and nowhere else, so
  the member who is 40 days late on one book can extend the other nine indefinitely. Tracked as
  [B-03](../backlog/B-03-block-renewals-for-blocked-members.md).
* **The loan is saved before catalog-api is told.** If the internal status call fails, the request
  fails, but the loan row is already there: the copy reads `on_shelf` while a member has it. There
  is no compensation and no retry — the desk has to notice. Swapping the two steps was proposed and
  rejected, with the reasoning kept in
  [B-06](../backlog/B-06-catalog-first-checkout.md).
* **`lost` is not a dead end.** A copy declared lost can be moved back to `on_shelf` by
  `POST /internal/copies/{barcode}/status`, which is how a book found behind a radiator returns to
  circulation. Until somebody does that, checkout answers `copy is not lendable`.
