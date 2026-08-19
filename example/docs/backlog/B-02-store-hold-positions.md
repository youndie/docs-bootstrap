---
id: B-02
title: "Queue positions are recomputed on every read"
status: question
priority: P2
size: M
stage: stage-2-queue
epic: feature-holds-queue
---

# B-02 — Queue positions are recomputed on every read

`holds_queue.position_of` sorts the open holds for a book by `placed_at`, then by id, and returns
an index. Nothing is stored. A cancellation therefore renumbers everyone behind it with no row
touched and no event emitted: the librarian tells a member "you are fourth", two people ahead of
them cancel, and the member is second without anyone knowing — including the member, who has no way
to look.

- **The open question, which is why this is `question` and not `open`.** Is a position a *promise*
  or a *reading*? If it is a promise, it has to be stored, and then a cancellation needs an explicit
  renumber step and the queue acquires a history. If it is a reading, the fix is not storage at all
  but wording: stop saying "you are fourth" and start saying "three people are ahead of you today".
  The second costs a sentence; the first costs a table. The library has not decided.
- The rejected middle way is caching the computed position and invalidating it on write. It buys
  nothing — the computation is a sort over a handful of rows — and it makes a stale position
  possible for the first time.
- Not covered: notifying a member when their position changes. That needs an address, which the
  system does not have; see [B-05](B-05-member-facing-holds.md).

- AC: whichever answer is chosen, `GET /api/books/{book_id}/holds` and the number a librarian reads
  aloud agree on what a position means, and the wording in
  [screen-catalog-search](../screens/screen-catalog-search.md) matches it.
- Anchors: `loans-service/src/loans_service/domain/holds_queue.py` (`position_of`, `queue_for`),
  `loans-service/src/loans_service/routes/holds.py` (`_hold_json`),
  `librarian-web/src/pages/CatalogSearch.jsx`.
