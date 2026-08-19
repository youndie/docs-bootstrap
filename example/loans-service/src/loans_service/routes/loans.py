"""Checkout, renewal and return.

A handler takes a request (``.query``, ``.params``, ``.body``) and returns a
``(status, body)`` pair. Every error body is ``{"error": "<message>"}``; the
messages for policy failures come from the domain (``domain/loan.py``) so that
they cannot drift between the route and the rule.

The ``hidden`` flag is set on internal routes for symmetry with catalog-api,
but nothing in this service reads it — loans-service publishes no schema.
"""
import json
import urllib.error
import urllib.request
from collections import namedtuple
from datetime import date

from ..config import CONFIG
from ..data.loan_repository import REPOSITORY
from ..domain import holds_queue
from ..domain.loan import LoanError, blocks_member, checkout, close, renew

Route = namedtuple("Route", "method path handler auth hidden")

LENDABLE = ("on_shelf", "held")


class CatalogClient:
    """The only place loans-service talks to catalog-api."""

    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _call(self, method, path, body=None):
        request = urllib.request.Request(
            self.base_url + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"X-Service-Token": self.token, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise

    def copy(self, barcode):
        return self._call("GET", f"/internal/copies/{barcode}")

    def set_copy_status(self, barcode, status):
        return self._call("POST", f"/internal/copies/{barcode}/status", {"status": status})


CATALOG = CatalogClient(CONFIG.catalog_api_url, CONFIG.service_token)


def _loan_json(loan, today):
    return {
        "id": loan.id,
        "barcode": loan.barcode,
        "book_id": loan.book_id,
        "member_id": loan.member_id,
        "due_on": loan.due_on.isoformat(),
        "renewals_used": loan.renewals_used,
        "renewals_left": max(0, CONFIG.max_renewals - loan.renewals_used),
        "state": loan.state(today),
    }


def create_loan(request):
    body = request.body or {}
    barcode, member_id = body.get("barcode"), body.get("member_id")
    if not barcode or not member_id:
        return 400, {"error": "barcode and member_id are required"}

    today = date.today()
    copy = CATALOG.copy(barcode)
    if copy is None:
        return 404, {"error": "copy not found"}
    # The open loan is checked before the copy status on purpose: when the two
    # services disagree, "copy already on loan" is the message that tells the
    # librarian what actually happened.
    if REPOSITORY.open_loan_for_copy(barcode) is not None:
        return 409, {"error": "copy already on loan"}
    if copy["status"] not in LENDABLE:
        return 409, {"error": "copy is not lendable"}

    ready = [
        h
        for h in REPOSITORY.open_holds_for_book(copy["book_id"])
        if h.status == holds_queue.READY
    ]
    mine = [h for h in ready if h.member_id == member_id]
    if ready and not mine:
        return 409, {"error": "copy is held for another member"}

    open_loans = REPOSITORY.open_loans_of(member_id)
    if any(blocks_member(l, today) for l in open_loans):
        return 403, {"error": "member is blocked"}
    if len(open_loans) >= CONFIG.max_active_loans:
        return 422, {"error": "loan limit reached"}

    loan = checkout(REPOSITORY.new_loan_id(), copy, member_id, today)
    REPOSITORY.save_loan(loan)
    for hold in mine:
        hold.status = holds_queue.FULFILLED
        REPOSITORY.save_hold(hold)
    CATALOG.set_copy_status(barcode, "on_loan")
    return 201, _loan_json(loan, today)


def renew_loan(request):
    today = date.today()
    loan = REPOSITORY.loan(int(request.params["loan_id"]))
    if loan is None:
        return 404, {"error": "loan not found"}
    waiting = holds_queue.next_in_line(REPOSITORY.holds(), loan.book_id)
    try:
        renew(loan, today, holds_waiting=waiting is not None)
    except LoanError as exc:
        return exc.status, {"error": exc.message}
    REPOSITORY.save_loan(loan)
    return 200, _loan_json(loan, today)


def return_loan(request):
    today = date.today()
    loan = REPOSITORY.loan(int(request.params["loan_id"]))
    if loan is None:
        return 404, {"error": "loan not found"}
    try:
        close(loan, today)
    except LoanError as exc:
        return exc.status, {"error": exc.message}
    REPOSITORY.save_loan(loan)

    hold = holds_queue.next_in_line(REPOSITORY.holds(), loan.book_id)
    if hold is None:
        CATALOG.set_copy_status(loan.barcode, "on_shelf")
        return 200, {"loan": _loan_json(loan, today), "next_hold": None}

    holds_queue.make_ready(hold, today, loan.barcode)
    REPOSITORY.save_hold(hold)
    CATALOG.set_copy_status(loan.barcode, "held")
    return 200, {
        "loan": _loan_json(loan, today),
        "next_hold": {"id": hold.id, "member_id": hold.member_id, "barcode": hold.barcode},
    }


def member_loans(request):
    today = date.today()
    loans = REPOSITORY.open_loans_of(request.params["member_id"])
    return 200, {
        "items": [_loan_json(l, today) for l in loans],
        "blocked": any(blocks_member(l, today) for l in loans),
    }


def overdue_loans(request):
    today = date.today()
    return 200, {"items": [_loan_json(l, today) for l in REPOSITORY.overdue_loans(today)]}


ROUTES = [
    Route("POST", "/api/loans", create_loan, "staff-session", False),
    Route("POST", "/api/loans/{loan_id}/renew", renew_loan, "staff-session", False),
    Route("POST", "/api/loans/{loan_id}/return", return_loan, "staff-session", False),
    Route("GET", "/api/members/{member_id}/loans", member_loans, "staff-session", False),
    Route("GET", "/internal/loans/overdue", overdue_loans, "service-token", True),
]
