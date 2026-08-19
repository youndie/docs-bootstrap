"""The holds queue.

A hold's position is **not a stored field**. The queue is rebuilt from the
holds table on every read, ordered by ``placed_at`` and then by ``id``, and the
position is the index in that list. Cancelling a hold therefore moves everyone
behind it up without touching a single row — and without telling them.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from ..config import CONFIG
from .loan import LoanError

WAITING = "waiting"
READY = "ready"
CANCELLED = "cancelled"
FULFILLED = "fulfilled"
EXPIRED = "expired"

OPEN_STATES = (WAITING, READY)


@dataclass
class Hold:
    id: int
    book_id: str
    member_id: str
    placed_at: date
    status: str = WAITING
    ready_on: date = None
    # Set when the hold becomes ready: the copy waiting on the hold shelf.
    barcode: str = None


def queue_for(holds, book_id):
    """Open holds for one book, in the order they will be served."""
    waiting = [h for h in holds if h.book_id == book_id and h.status in OPEN_STATES]
    waiting.sort(key=lambda h: (h.placed_at, h.id))
    return waiting


def position_of(holds, hold):
    queue = queue_for(holds, hold.book_id)
    return queue.index(hold) + 1


def next_in_line(holds, book_id):
    queue = [h for h in queue_for(holds, book_id) if h.status == WAITING]
    return queue[0] if queue else None


def place(hold_id, holds, book_id, member_id, today):
    mine = [h for h in holds if h.member_id == member_id and h.status in OPEN_STATES]
    if any(h.book_id == book_id for h in mine):
        raise LoanError(409, "hold already placed")
    if len(mine) >= CONFIG.max_active_holds:
        raise LoanError(422, "hold limit reached")
    return Hold(id=hold_id, book_id=book_id, member_id=member_id, placed_at=today)


def make_ready(hold, today, barcode):
    hold.status = READY
    hold.ready_on = today
    hold.barcode = barcode
    return hold


def expired(holds, today):
    """Ready holds whose pickup window has closed."""
    deadline = timedelta(days=CONFIG.hold_pickup_days)
    return [
        h
        for h in holds
        if h.status == READY and h.ready_on is not None and today - h.ready_on > deadline
    ]
