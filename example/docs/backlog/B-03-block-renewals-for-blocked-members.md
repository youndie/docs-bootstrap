---
id: B-03
title: "A blocked member can still renew everything they hold"
status: wip
priority: P1
size: S
stage: stage-1-trust
epic: feature-borrow-and-return
---

# B-03 — A blocked member can still renew everything they hold

`blocks_member` is called in `create_loan` and nowhere else. A member with one loan 40 days overdue
cannot take a new book — and can extend the other nine indefinitely, two renewals at a time,
without ever coming to the desk. The block reads as "this member is out of good standing" and
behaves as "this member may not start anything new".

- **The decision and its reason.** Refuse the renewal with `403 {"error": "member is blocked"}` —
  the same status and the same string as checkout, because it is the same fact about the member and
  the desk shows the string verbatim. A member in this state has to speak to a librarian, which is
  the point of the block.
- Returns stay unconditional. Making a return depend on the member's standing would give somebody a
  reason not to bring the book back, which is the opposite of what the block is for.
- The rejected alternative was blocking renewals only on the *overdue* loan itself. It is
  narrower and defensible, but it does not change the member's behaviour: they renew the other nine
  and the overdue one keeps ageing.
- Not covered: what happens to a loan that is renewed *before* the member crosses 30 days. It keeps
  its new due date; this item does not claw anything back.

- AC: a member with a loan more than `LOAN_BLOCK_AFTER_DAYS` overdue gets `403`
  `{"error": "member is blocked"}` from `POST /api/loans/{id}/renew`, and `renewals_used` is
  unchanged.
- AC: the same member's `POST /api/loans/{id}/return` still answers `200`.
- Anchors: `loans-service/src/loans_service/routes/loans.py` (`renew_loan`),
  `loans-service/src/loans_service/domain/loan.py` (`renew`, `blocks_member`),
  `loans-service/tests/test_loan_rules.py`.

Behaviour today: [feature-borrow-and-return](../features/feature-borrow-and-return.md), quirks.
