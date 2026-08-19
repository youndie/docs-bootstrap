---
id: B-06
title: "Tell catalog-api about the copy before saving the loan"
status: dropped
priority: infra
size: M
stage: stage-1-trust
epic: feature-borrow-and-return
---

# B-06 — Tell catalog-api about the copy before saving the loan

`create_loan` saves the loan and then calls `CATALOG.set_copy_status(barcode, "on_loan")`. If that
call fails the librarian sees a `500`, the loan exists, and the copy still reads `on_shelf`. The
proposal was to swap the two lines: confirm with catalog-api first, save afterwards.

- **Dropped, and this is the reason.** The swap does not remove the failure, it changes which half
  survives — and the surviving half gets worse. Today the inconsistency is *loud*: a copy that a
  member is carrying home says `on_shelf`, so the next person to scan it gets
  `copy already on loan` and asks a librarian. Reversed, the surviving half is a copy marked
  `on_loan` with no loan behind it: nobody is holding it, no return can close it, and it disappears
  from availability until an audit finds it. A visible inconsistency is worth more than an
  invisible one.
- The real fix is a transaction across two services, and neither the traffic (a few hundred
  checkouts a day) nor the damage (one confused scan) justifies it. This item exists so that the
  swap is not re-proposed as an obvious one-line improvement — it has been proposed twice.
- What would change the decision: a second writer of copy status. As long as loans-service is the
  only caller of `POST /internal/copies/{barcode}/status`, the loud failure is recoverable by
  scanning the book again.

- Anchors: `loans-service/src/loans_service/routes/loans.py` (`create_loan`, `CatalogClient`),
  `catalog-api/src/catalog_api/routes/availability.py` (`set_copy_status`).

Behaviour today: [feature-borrow-and-return](../features/feature-borrow-and-return.md), quirks;
[endpoint-loans](../api/endpoint-loans.md), quirks.
