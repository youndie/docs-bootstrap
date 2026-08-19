---
id: B-04
title: "The return response names the copy to put on the hold shelf"
status: done
priority: P2
size: XS
stage: stage-2-queue
epic: feature-holds-queue
---

# B-04 — The return response names the copy to put on the hold shelf

A return that promoted a hold used to answer with the hold id and the member id. The librarian was
holding a stack of books and had no way to tell which of them the message referred to, so the
banner said "put a copy on the hold shelf for m-200" and the librarian guessed. For a book with one
copy the guess was right; for a best-seller with four it was a coin toss, and a mislabelled copy
sits on the hold shelf until somebody audits it.

- **The decision and its reason.** `Hold` gained a `barcode` field, set by `make_ready` at the
  moment the hold is matched with a copy, and `next_hold` in the return response carries it. The
  field is not redundant with the loan's barcode: the hold outlives the loan, and hold expiry needs
  to know which copy to re-offer or shelve long after the loan is closed.
- The rejected alternative was for the client to reuse the barcode it had just sent. It works for
  the desk and breaks for every other caller, and it makes the response depend on the request in a
  way nothing else in the API does.

- AC: `POST /api/loans/{id}/return` on a book with a waiting hold answers
  `{"loan": ..., "next_hold": {"id", "member_id", "barcode"}}`, and the desk banner names the copy.
- AC: `POST /internal/holds/expire` re-offers that same barcode to the next member in line.
- Anchors: `loans-service/src/loans_service/domain/holds_queue.py` (`Hold.barcode`, `make_ready`),
  `loans-service/src/loans_service/routes/loans.py` (`return_loan`),
  `librarian-web/src/pages/CheckoutDesk.jsx` (the hold-shelf banner).
