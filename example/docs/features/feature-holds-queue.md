---
id: feature-holds-queue
title: Holds queue
type: feature
status: active
owner: unassigned
involved_services:
  - loans-service
  - catalog-api
  - librarian-web
client_entries:
  - screen-catalog-search
api:
  - endpoint-loans
  - endpoint-catalog
tags: [lending, queue]
---

# Holds queue

## 1. Overview

Every copy of a popular book is out, so the member asks to be told when one comes back. The library
keeps one queue per **book**, not per copy: whichever copy is returned first goes to whoever has
waited longest. When that happens the copy does not go back to the shelf — it spends three days on
the hold shelf with the member's name on it, and then, if nobody comes, moves on to the next person
in line.

The queue is the reason renewals can be refused: an extension for one member is a delay for
everybody behind them — see
[feature-borrow-and-return](feature-borrow-and-return.md).

Holds are placed from [screen-catalog-search](../screens/screen-catalog-search.md) in
[librarian-web](../services/librarian-web.md); the queue lives in
[loans-service](../services/loans-service.md) ([endpoint-loans](../api/endpoint-loans.md)) and the
copy it is waiting for in [catalog-api](../services/catalog-api.md)
([endpoint-catalog](../api/endpoint-catalog.md)).

## 2. Business rules

* One queue per book, ordered by `placed_at` and then by hold id. Same-day holds are served in the
  order they were entered.
* A member may have 5 open holds (`max_active_holds`); the sixth is refused.
* A member cannot hold a book they already have on loan, and cannot hold the same book twice.
* A returned copy is offered to the first **waiting** hold. That hold becomes `ready`, remembers
  the barcode it was matched with, and the copy status becomes `held`.
* A ready hold has 3 days (`hold_pickup_days`) to be collected. After that it expires and the copy
  passes to the next in line, or back to the shelf if the queue is empty.
* While a hold on a book is ready, no other member can take **any** copy of that book.
* A hold is closed as `fulfilled` when the member it is ready for checks the book out.

## 3. Flow

```
librarian-web ── POST /loans/api/holds {book_id, member_id} ──▶ loans-service  (staff session)
                 ◀── 201 {id, position, status: "waiting"}

return of any copy of the book ──▶ first waiting hold becomes "ready"
                     loans-service ── POST /internal/copies/{barcode}/status {"status":"held"} ──▶ catalog-api

daily ── POST /loans/internal/holds/expire ──▶ loans-service      (service token)
                 ready holds older than 3 days ──▶ "expired", copy re-offered or shelved
```

## 4. Code anchors

| Service | Code |
|---|---|
| loans-service | `loans-service/src/loans_service/domain/holds_queue.py` — order, positions, expiry |
| loans-service | `src/loans_service/routes/holds.py` — place, cancel, list, expire |
| loans-service | `.../routes/loans.py` — `create_loan` (ready holds block checkout) and `return_loan` (promotion) |
| catalog-api | `catalog-api/src/catalog_api/domain/book.py` — the `held` copy status |
| librarian-web | `librarian-web/src/pages/CatalogSearch.jsx` — the "Place hold" action |

## 5. Scenarios (BDD / test cases)

### Scenario: The first hold on a book
* **Given:** book `b-1` has no open holds.
* **When:** `POST /api/holds {"book_id": "b-1", "member_id": "m-200"}`.
* **Then:** `201` with `"status": "waiting"` and `"position": 1`.

### Scenario: The second member queues behind the first
* **Given:** `m-200` already holds a place in the queue for `b-1`.
* **When:** `m-300` places a hold on `b-1`.
* **Then:** `201` with `"position": 2`, and `GET /api/books/b-1/holds` lists the two in that order.

### Scenario: The same member cannot queue twice
* **When:** `m-200` places a second hold on `b-1`.
* **Then:** `409` with `{"error": "hold already placed"}`.

### Scenario: The sixth hold is refused
* **Given:** `m-200` has 5 open holds.
* **When:** they place a sixth on any book.
* **Then:** `422` with `{"error": "hold limit reached"}`.

### Scenario: Holding a book you already have
* **Given:** `m-200` has an open loan on a copy of `b-1`.
* **When:** they place a hold on `b-1`.
* **Then:** `409` with `{"error": "member already has this book on loan"}` — renew it instead.

### Scenario: A return promotes the head of the queue
* **Given:** copy `30001` of `b-1` is on loan and `m-200` is first in the queue.
* **When:** the copy is returned.
* **Then:** `200`, `next_hold` = `{id, member_id: "m-200", barcode: "30001"}`, the hold reads
  `ready`, and the copy status is `held`.
* **And:** the barcode is in the response so the librarian knows which book in the stack to label —
  [B-04](../backlog/B-04-return-response-names-the-copy.md).

### Scenario: A ready hold blocks everybody else
* **Given:** a hold on `b-1` is ready for `m-200`.
* **When:** `m-300` tries to check out a copy of `b-1`.
* **Then:** `409` with `{"error": "copy is held for another member"}`.

### Scenario: The member the copy is waiting for collects it
* **Given:** the hold on `b-1` is ready for `m-200`.
* **When:** `m-200` checks the copy out.
* **Then:** `201`, and the hold is closed as `fulfilled` rather than left open.

### Scenario: An uncollected hold expires
* **Given:** a hold went ready 4 days ago and nobody came.
* **When:** `POST /internal/holds/expire`.
* **Then:** `200` with `{"expired": 1}`; the next waiting hold becomes ready for the same barcode,
  or the copy goes back to `on_shelf` if the queue is empty.

### Scenario: Cancelling a hold
* **When:** `DELETE /api/holds/{id}` on an open hold.
* **Then:** `204` and everybody behind it moves up one place — see the quirks.

## 6. Out of scope

* Notifying the member that a hold is ready. Nothing sends that message today; the librarian
  telephones. The only automated mail in the system is
  [feature-overdue-notices](feature-overdue-notices.md).
* Holds on a specific copy, and holds with a "not before" date.
* Suspending a hold while the member is away.

## 7. Quirks

* **Positions are not stored.** `position_of` recomputes the queue on every read from `placed_at`.
  A cancellation therefore renumbers everybody behind it with no event and no record: the position
  a member was told on the phone is a snapshot, not a promise. Tracked as
  [B-02](../backlog/B-02-store-hold-positions.md).
* **A ready hold blocks every copy of the book, not the copy it is waiting on.** `create_loan`
  looks for any ready hold on the book, so a second copy sitting on the shelf cannot be lent to
  anyone else while one copy waits on the hold shelf. For a library with three copies of a
  best-seller this is visible daily.
* **Nothing checks that the book exists.** loans-service never asks catalog-api about `book_id`, so
  a typo produces a `201` and a hold that can never be filled. There is no route that lists such
  holds; they are found only by reading the queue of a book nobody borrows.
* **Expiry only happens when somebody calls it.** `POST /internal/holds/expire` has no scheduler in
  this repository. If the caller stops, ready holds sit on the hold shelf forever and the copies
  stay invisible to the rest of the queue.
