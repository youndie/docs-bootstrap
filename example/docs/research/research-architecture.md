---
id: research-architecture
title: Riverside lending system — architecture research
type: research
status: active
date: 2026-08-19
---

# Research: the architecture of the Riverside lending system

Three services lend books at one branch library: a catalogue that knows what is on the shelf, a
lending service that knows who has what, and a web application the staff use at the desk. The
interesting part is not the domain — it is the seam: **the catalogue never learns who has a book**,
and almost every design decision below follows from holding that line.

This document records **verified facts** (read in the code next to this directory), **decisions**
and **risks**. Anything not verified is marked as a hypothesis and says where it will be settled.
The layer documents say what the system does; this one says why it is built this way.

---

## 1. Verified facts

### 1.1 catalog-api owns the shelf, loans-service owns the borrower

Verified in `catalog-api/src/catalog_api/domain/book.py`: `Copy` carries `barcode`, `book_id` and
`status`, and nothing else. There is no member field anywhere in the catalogue.

| Fact | Where verified |
|---|---|
| A copy has a status and no borrower | `catalog-api/src/catalog_api/domain/book.py` — `Copy` |
| Statuses are `on_shelf`, `on_loan`, `held`, `in_repair`, `lost` | same file — `STATUSES`, `TRANSITIONS` |
| Only loans-service writes a copy's status, over `/internal/` | `loans-service/src/loans_service/routes/loans.py` — `CatalogClient` |

**Consequence 1.** "Is this book available?" and "who has it?" are two questions to two services,
so the checkout desk asks both and the screen is responsible for reconciling them —
[screen-checkout-desk](../screens/screen-checkout-desk.md).

**Consequence 2.** The two can disagree, and the code takes a side: `create_loan` checks its own
open loans *before* the catalogue's status, because "copy already on loan" tells the librarian what
actually happened while "copy is not lendable" does not.

### 1.2 A hold's position is not stored — it is recomputed on every read

Verified in `loans-service/src/loans_service/domain/holds_queue.py`: `queue_for()` filters the
holds table by book and open status, sorts by `(placed_at, id)`, and `position_of()` returns the
index in that list.

| Fact | Where verified |
|---|---|
| No `position` column exists; position is a list index | `.../domain/holds_queue.py` — `queue_for`, `position_of` |
| Cancelling a hold only flips `status` to `cancelled` | `loans-service/src/loans_service/routes/holds.py` — `cancel_hold` |

**Consequence.** Cancelling a hold silently moves everyone behind it up. Nothing observes the move,
so nothing can announce it — a position is only ever true at the moment it is read. That is
acceptable while the only reader is a librarian on the phone, and it is the whole question in
[B-02](../backlog/B-02-store-hold-positions.md).

### 1.3 "Overdue" is derived from the due date, never stored

Verified in `loans-service/src/loans_service/domain/loan.py`: `Loan.state()` returns `overdue` when
`today > due_on`, and there is no status column to disagree with it.

**Consequence.** No nightly job has to flip a field, and a loan cannot be stale-overdue. The price
is that a query cannot filter on a status column: `overdue_loans()` compares dates
(`loans-service/src/loans_service/data/loan_repository.py`), which is fine at branch scale and is
the first thing to revisit at consortium scale.

### 1.4 Loans and holds share one repository

Verified in `loans-service/src/loans_service/data/loan_repository.py`: one class holds both tables,
and the docstring gives the reason — a return has to close a loan and promote a hold in the same
breath.

**Consequence.** `return_loan` is one call against one store. Splitting the two would buy a cleaner
diagram and a distributed transaction.

### 1.5 The notice job records a send before attempting it

Verified in `loans-service/src/loans_service/jobs/overdue_notices.py`: `last_notice_day` is written
and saved, and only then does `mailer.send()` run; an `OSError` is logged and the loop continues.

**Consequence.** A failed notice is indistinguishable from a delivered one, for good — the member
who never received day 7 gets day 14 next. This is a bug and not a policy, and it is
[B-01](../backlog/B-01-retry-failed-overdue-notices.md).

### 1.6 One policy knob is read and never applied

Verified by reading every use of the config object: `grace_days` is assigned in
`loans-service/src/loans_service/config.py` and referenced by no other module. A loan is overdue
the day after its due date, with no grace at all.

**Consequence.** The configuration file overstates the policy the service implements. It is
recorded here and in the service document rather than deleted, because the knob's existence is
evidence that somebody expected a grace period and will expect it again.

---

## 2. Decisions

### D1. The queue is derived, not stored

First idea: a `position` column, updated when holds are placed and cancelled.
Decision: rebuild the queue from `(placed_at, id)` on every read.

Why:

- a stored position is wrong the instant any hold ahead of it is cancelled, and the update touches
  every row behind the cancellation — at one branch that is cheap, but so is recomputing;
- there is exactly one reader today, a librarian answering the phone, and they want the position
  *now*, not the position as of the last write;
- the price: no history, and nothing to hang a notification off, which is precisely what blocks
  member-facing holds ([B-05](../backlog/B-05-member-facing-holds.md) is blocked by
  [B-02](../backlog/B-02-store-hold-positions.md)).

### D2. Lending policy lives in configuration, the state machine does not

Decision: loan period, renewal limit, hold limits, pickup window and notice days are config keys;
the transitions in `domain/loan.py` are code.

Why: a library changes its lending policy and never changes what "returned" means. The split is
stated in the docstring of `loans-service/src/loans_service/config.py`, which is also the complete
list of knobs the service has — the reason no document copies that list.

### D3. Checkout saves the loan first and tells the catalogue second *(deviation from the brief)*

First idea: mark the copy `on_loan` in catalog-api, then save the loan, so the catalogue is never
behind.
Decision: save the loan, then call `CATALOG.set_copy_status()` — verified in
`loans-service/src/loans_service/routes/loans.py`, `create_loan`.

Why:

- the failure that matters is the one where the book has left the building: a loan that was never
  saved loses the borrower, while a catalogue that says `on_shelf` for a copy that is out is
  corrected by the next return or by an inventory pass;
- reversing the order needs a compensating call on every path that can fail after the catalogue
  write, which is more machinery than the disagreement costs;
- the price: a window in which the two services disagree, handled by the check order in §1.1, and
  the reason [B-06](../backlog/B-06-catalog-first-checkout.md) was dropped rather than done.

---

## 3. Risks and open questions

**Risk 1. The repository is in memory, so every restart is a data loss.** Mitigation: the method
list on `LoanRepository` is the contract a SQL implementation has to satisfy, and it is
deliberately small — ids, save, read-by-key, and three queries. Nothing above `data/` knows how it
is stored. Open until the store is real.

**Risk 2. Notices are fire-and-forget, so trust in the system decays silently.** Mitigation: none
in the code today; [B-01](../backlog/B-01-retry-failed-overdue-notices.md) is the mitigation, and it
is the first item of the first stage for that reason.

**Risk 3. A blocked member can still renew.** `blocks_member()` is applied in `create_loan` and not
in `renew_loan` — verified in `loans-service/src/loans_service/routes/loans.py`. Mitigation:
[B-03](../backlog/B-03-block-renewals-for-blocked-members.md), in progress. Until it lands, the
block is a checkout block only, and the feature document says so rather than implying otherwise.

**Open question 1. Does a position have to be storable before members can see it?** The hypothesis
is yes — a member watching a queue expects a number that moves for a reason, and a derived number
cannot explain itself. To be settled in [B-02](../backlog/B-02-store-hold-positions.md), which is
deliberately `status: question` rather than `open`.

---

## 4. What happens next

The order of work and the acceptance criteria live in [backlog.md](../../backlog.md), in three
stages: make the system honest about what it did (stage 1), then decide the queue (stage 2), then
open it to members (stage 3). The one thing to settle before anything in stage 3 is Open question 1
— everything member-facing depends on the answer.
