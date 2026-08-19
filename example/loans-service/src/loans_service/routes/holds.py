"""Placing, cancelling and inspecting holds.

Positions in the responses below are computed at read time by
``domain/holds_queue.position_of``; nothing stores them.
"""
from datetime import date

from ..data.loan_repository import REPOSITORY
from ..domain import holds_queue
from ..domain.loan import LoanError
from .loans import CATALOG, Route


def _hold_json(hold, holds):
    return {
        "id": hold.id,
        "book_id": hold.book_id,
        "member_id": hold.member_id,
        "status": hold.status,
        "placed_at": hold.placed_at.isoformat(),
        "position": holds_queue.position_of(holds, hold),
    }


def place_hold(request):
    body = request.body or {}
    book_id, member_id = body.get("book_id"), body.get("member_id")
    if not book_id or not member_id:
        return 400, {"error": "book_id and member_id are required"}

    today = date.today()
    on_loan = [l for l in REPOSITORY.open_loans_of(member_id) if l.book_id == book_id]
    if on_loan:
        return 409, {"error": "member already has this book on loan"}

    try:
        hold = holds_queue.place(
            REPOSITORY.new_hold_id(), REPOSITORY.holds(), book_id, member_id, today
        )
    except LoanError as exc:
        return exc.status, {"error": exc.message}

    REPOSITORY.save_hold(hold)
    return 201, _hold_json(hold, REPOSITORY.holds())


def cancel_hold(request):
    hold = REPOSITORY.hold(int(request.params["hold_id"]))
    if hold is None:
        return 404, {"error": "hold not found"}
    if hold.status not in holds_queue.OPEN_STATES:
        return 409, {"error": "hold already closed"}
    hold.status = holds_queue.CANCELLED
    REPOSITORY.save_hold(hold)
    return 204, None


def book_holds(request):
    book_id = request.params["book_id"]
    holds = REPOSITORY.holds()
    queue = holds_queue.queue_for(holds, book_id)
    return 200, {"book_id": book_id, "items": [_hold_json(h, holds) for h in queue]}


def expire_holds(request):
    """Closes ready holds nobody came for and passes the copy to the next
    member in line."""
    today = date.today()
    holds = REPOSITORY.holds()
    closed = 0
    for hold in holds_queue.expired(holds, today):
        hold.status = holds_queue.EXPIRED
        REPOSITORY.save_hold(hold)
        closed += 1
        heir = holds_queue.next_in_line(REPOSITORY.holds(), hold.book_id)
        if heir is None:
            CATALOG.set_copy_status(hold.barcode, "on_shelf")
        else:
            holds_queue.make_ready(heir, today, hold.barcode)
            REPOSITORY.save_hold(heir)
    return 200, {"expired": closed}


ROUTES = [
    Route("POST", "/api/holds", place_hold, "staff-session", False),
    Route("DELETE", "/api/holds/{hold_id}", cancel_hold, "staff-session", False),
    Route("GET", "/api/books/{book_id}/holds", book_holds, "staff-session", False),
    Route("POST", "/internal/holds/expire", expire_holds, "service-token", True),
]
