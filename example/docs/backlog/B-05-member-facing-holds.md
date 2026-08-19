---
id: B-05
title: "Members can place and watch their own holds"
status: open
priority: P3
size: XL
stage: stage-3-members
epic: feature-holds-queue
blocked_by: [B-02]
---

# B-05 — Members can place and watch their own holds

Every hold in the system was typed by a librarian with a member on the telephone. There is no
member-facing surface anywhere: `member_id` is a string loans-service stores and never resolves,
the overdue notice invents an address with `f"{loan.member_id}@example.org"`, and nothing
authenticates a member. Making holds self-service means building the member identity the product
has done without so far — which is why this is XL and P3 rather than XL and P1.

- **The decision and its reason.** Do the member record first and the screen second. The screen is
  a week; the record is a directory, an authentication story, an address of record, and a privacy
  answer for "which librarian may see which member". Starting from the screen produces a login form
  in front of a `member_id` text field, which is worse than the telephone.
- Blocked by [B-02](B-02-store-hold-positions.md), and not for scheduling reasons: a member
  refreshing their own page sees the position change. Whether that is allowed to happen silently is
  exactly the question B-02 asks, and it must be answered before a member can watch the number.
- The rejected alternative is a read-only page behind a link mailed to the member. It skips
  authentication, and it also skips the address of record, which is the part that has to exist
  anyway.
- Not covered: borrowing, renewing or returning without a librarian. The desk stays.

- AC: a member signs in, places a hold on a book with copies out, and sees the same queue the
  librarian sees in [screen-catalog-search](../screens/screen-catalog-search.md).
- AC: the notice job sends to an address from the member record, not to one built from the id.
- Anchors: `loans-service/src/loans_service/routes/holds.py`,
  `loans-service/src/loans_service/jobs/overdue_notices.py` (the address placeholder),
  `librarian-web/src/api/client.js` (the only place URLs are built today).
