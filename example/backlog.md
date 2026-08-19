# Backlog: a lending system the staff can trust

> Role of this document: the product backlog. **One file per item in
> [`docs/backlog/`](docs/backlog/)** — `B-NN-<slug>.md`. What lives here is the index (generated)
> and everything that is not an item: the goal, the stages, and the decisions.
>
> New item: copy [`docs/templates/backlog-item.md`](docs/templates/backlog-item.md), take the next
> free `B-NN`, and run `python3 ../scripts/backlog_index.py` after editing.

## Goal

The library has been lending books with this software for a year, and the staff have learned which
parts of it to distrust. The goal of this backlog is to remove the reasons for that distrust in
order of how much they cost at the desk — first the places where the system reports something that
did not happen, then the places where it reports something it cannot promise. Adding a member-facing
surface comes last, because it makes every one of those problems visible to people who cannot ask a
librarian what happened.

## Stages

A stage is a field on the item, not a directory. Items are cited by id from documents in all four
layers, so re-prioritising an item must never move its file.

| Stage id | Stage | What it is |
|---|---|---|
| `stage-1-trust` | The system does not lie | Where a record says something happened and it did not: a notice marked sent that was refused, a block that stops nothing. |
| `stage-2-queue` | A place in the queue means something | Where the answer is correct at the moment it is given and stops being true without anybody noticing. |
| `stage-3-members` | Beyond the desk | Everything that requires a member identity: self-service holds, a real address, an account to sign in to. |

## Marks

`[ ]` open · `[~]` in progress · `[x]` done · `[?]` open question · `[-]` dropped

<!-- BEGIN INDEX -->

## Open (4)

| Task | | Priority | Size | Blocked by |
|---|---|---|---|---|
| [B-01](docs/backlog/B-01-retry-failed-overdue-notices.md) `[ ]` | A failed overdue notice is recorded as sent | P1 | S | - |
| [B-03](docs/backlog/B-03-block-renewals-for-blocked-members.md) `[~]` | A blocked member can still renew everything they hold | P1 | S | - |
| [B-02](docs/backlog/B-02-store-hold-positions.md) `[?]` | Queue positions are recomputed on every read | P2 | M | - |
| [B-05](docs/backlog/B-05-member-facing-holds.md) `[ ]` | Members can place and watch their own holds | P3 | XL | B-02 |

## Closed (2)

**The system does not lie**

- [B-06](docs/backlog/B-06-catalog-first-checkout.md) `[-]` - Tell catalog-api about the copy before saving the loan

**A place in the queue means something**

- [B-04](docs/backlog/B-04-return-response-names-the-copy.md) `[x]` - The return response names the copy to put on the hold shelf

<!-- END INDEX -->

## Decisions worth not re-litigating

**A dropped item is kept, not deleted.**
[B-06](docs/backlog/B-06-catalog-first-checkout.md) proposes swapping two lines in `create_loan`,
and it is wrong for a reason that takes a paragraph to explain. It has been proposed twice. The
file exists so that it is refused in ten seconds the third time.

**An open question is a status, not a stalled item.**
[B-02](docs/backlog/B-02-store-hold-positions.md) is `question` because the work depends on an
answer the library has not given: whether a queue position is a promise or a reading. Writing the
code first would be choosing the expensive answer by accident.

**Blocking is a fact, not a plan.**
[B-05](docs/backlog/B-05-member-facing-holds.md) is blocked by
[B-02](docs/backlog/B-02-store-hold-positions.md) because a member watching their own position
would see it change silently — the same behaviour a librarian can currently explain away on the
telephone. Sequencing preferences do not belong in `blocked_by`.
