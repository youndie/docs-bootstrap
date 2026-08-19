---
id: B-01
title: "A failed overdue notice is recorded as sent"
status: open
priority: P1
size: S
stage: stage-1-trust
epic: feature-overdue-notices
---

# B-01 — A failed overdue notice is recorded as sent

`run` in `jobs/overdue_notices.py` sets `loan.last_notice_day = step` and saves the loan **before**
calling `mailer.send`. If SMTP refuses the connection the exception is caught, logged at WARNING,
and the loop moves on. The loan now says it has had its day-1 notice, `last_notice_day` never goes
backwards, and the member is next contacted on day 7 — or never, if that send fails too. One
outage during the daily run silently deletes a day of notices, and nothing but a log line records
which members were affected.

- **The decision and its reason.** Send first, record second, and let a duplicate notice be the
  failure mode. A member who receives the same reminder twice is mildly annoyed; a member who is
  blocked on day 30 having been told nothing has a complaint the library cannot answer.
- The rejected alternative is a `sent_notices` table with retry and back-off. It is the right shape
  for a system with several channels, and this system has one address per member computed with an
  f-string — the table would be infrastructure around a placeholder.
- Not covered: retrying anything *older* than the current run. If a notice was lost before this
  change, it stays lost; `last_notice_day` cannot tell a sent notice from a swallowed one.

- AC: with SMTP refusing connections, a run over a loan due for its day-1 notice leaves
  `last_notice_day` at `0`, logs the failure, and the next run sends the notice.
- AC: a run where the send succeeds still writes `last_notice_day` exactly once per loan.
- Anchors: `loans-service/src/loans_service/jobs/overdue_notices.py`,
  `loans-service/src/loans_service/domain/loan.py` (`last_notice_day`).

Behaviour today: [feature-overdue-notices](../features/feature-overdue-notices.md), scenario
"SMTP is down".
