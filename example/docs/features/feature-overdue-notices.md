---
id: feature-overdue-notices
title: Overdue notices
type: feature
status: active
owner: unassigned
involved_services:
  - loans-service
client_entries: []
api:
  - endpoint-loans
tags: [lending, notifications]
---

# Overdue notices

## 1. Overview

A loan that passes its due date generates up to three emails — after 1, 7 and 14 days — and, once
it is 30 days late, blocks its member from borrowing anything else. The notices are the polite part
of that escalation; the block is the part that works.

`client_entries` is `[]` on purpose: this feature has no screen anywhere. It is a job that runs
once a day and an SMTP conversation, both inside
[loans-service](../services/loans-service.md). The only way a librarian sees it is
`GET /internal/loans/overdue` ([endpoint-loans](../api/endpoint-loans.md)), and that route has no
UI in front of it. An empty list is the answer "there is no client"; a missing field would have
meant "nobody checked".

## 2. Business rules

* Notices go out on the days listed in `notice_days` — 1, 7 and 14 days after the due date.
* At most one notice per loan per run. If a run is missed, the loan gets the notice for the highest
  day it has passed, not one for each day it skipped.
* `last_notice_day` on the loan is monotonic: a loan that has had the day-7 notice will never get
  the day-1 notice, however the days are reconfigured.
* Returned and lost loans are never in the overdue set.
* A loan more than `block_after_overdue_days` (30) past due blocks the member — enforced at
  checkout, see [feature-borrow-and-return](feature-borrow-and-return.md).
* There are no fines, so a notice asks for the book back and nothing else.

## 3. Flow

```
daily (external scheduler) ──▶ jobs/overdue_notices.run(today)
        repository.overdue_loans(today)      loans past due, oldest first
        step = highest notice day passed     1 | 7 | 14 | none
        last_notice_day := step  ─── written and committed BEFORE the send
        mailer.send(...)                     failures are logged, not retried
```

## 4. Code anchors

| Service | Code |
|---|---|
| loans-service | `loans-service/src/loans_service/jobs/overdue_notices.py` — the whole job, including `SmtpMailer` |
| loans-service | `.../loans_service/data/loan_repository.py` — `overdue_loans` |
| loans-service | `src/loans_service/domain/loan.py` — `days_overdue`, `state`, `blocks_member` |
| loans-service | `loans-service/src/loans_service/config.py` — `notice_days`, `block_after_overdue_days` |

## 5. Scenarios (BDD / test cases)

### Scenario: The first notice
* **Given:** a loan due yesterday with `last_notice_day: 0`.
* **When:** the job runs.
* **Then:** one message is sent, the subject is `Overdue: copy 30001`, and `last_notice_day`
  becomes `1`.

### Scenario: A second run on the same day sends nothing
* **Given:** the loan above, after the first run.
* **When:** the job runs again the same day.
* **Then:** the loan is skipped (`last_notice_day >= step`) and the run reports 0 notices for it.

### Scenario: A missed week does not produce a backlog of mail
* **Given:** a loan 9 days overdue that never received the day-1 notice.
* **When:** the job runs.
* **Then:** exactly one message goes out — the day-7 one — and `last_notice_day` becomes `7`.

### Scenario: SMTP is down
* **Given:** the mail server refuses the connection.
* **When:** the job runs over a loan due for its day-1 notice.
* **Then:** `last_notice_day` is already `1`, the failure is logged at WARNING, the run continues
  to the next loan, and the member never receives that notice. See
  [B-01](../backlog/B-01-retry-failed-overdue-notices.md).

### Scenario: A returned loan is silent
* **Given:** a loan returned two months after its due date.
* **When:** the job runs.
* **Then:** it is not in `overdue_loans` and no notice is sent.

## 6. Out of scope

* Reminders *before* the due date.
* Notifying a member that a hold is ready — nothing sends that message, see
  [feature-holds-queue](feature-holds-queue.md).
* Fines, collection agencies, and any escalation past the block.
* Choosing a channel. It is email or nothing.

## 7. Quirks

* **The send is fire-and-forget in the worst order.** `last_notice_day` is written *before* the
  message leaves, so a failed send is not merely un-retried — it is recorded as done. One SMTP
  outage silently removes a whole day's notices, and the loans look notified.
  [B-01](../backlog/B-01-retry-failed-overdue-notices.md).
* **There is no member directory.** The recipient is `f"{loan.member_id}@example.org"`, built in
  the job. loans-service stores a member id and has never had an address for it; this line is the
  placeholder that has to disappear before the feature can face a real member.
* **`LOAN_GRACE_DAYS` does nothing.** The key is read into `CONFIG.grace_days` and referenced by no
  other module. A loan is overdue the day after its due date, and setting the variable changes
  nothing at all.
* **The job has no scheduler here.** `run()` is a function; whatever calls it daily lives outside
  this repository. If that caller stops, nothing in the service notices or complains.
