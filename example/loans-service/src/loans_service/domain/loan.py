"""The loan state machine and every error text a loan route can produce.

    checkout ──▶ active ──renew──▶ active
                   │  │
                   │  └──(due date passed)──▶ overdue ──return──▶ returned
                   └──return──▶ returned
                   └──declare lost──▶ lost

``overdue`` is computed from the due date, never stored. A row that says
``active`` may well be overdue; ask state(), not the field.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from ..config import CONFIG

ACTIVE = "active"
OVERDUE = "overdue"
RETURNED = "returned"
LOST = "lost"


class LoanError(Exception):
    """Carries the HTTP status and the exact message the route will return."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class Loan:
    id: int
    barcode: str
    book_id: str
    member_id: str
    checked_out_on: date
    due_on: date
    renewals_used: int = 0
    returned_on: date = None
    lost: bool = False
    last_notice_day: int = 0

    def state(self, today):
        if self.returned_on is not None:
            return RETURNED
        if self.lost:
            return LOST
        return OVERDUE if today > self.due_on else ACTIVE

    def days_overdue(self, today):
        return max(0, (today - self.due_on).days) if self.returned_on is None else 0


def checkout(loan_id, copy, member_id, today):
    return Loan(
        id=loan_id,
        barcode=copy["barcode"],
        book_id=copy["book_id"],
        member_id=member_id,
        checked_out_on=today,
        due_on=today + timedelta(days=CONFIG.loan_period_days),
    )


def renew(loan, today, holds_waiting):
    """A renewal adds a full loan period to the *current due date*, not to
    today, so renewing early costs the member nothing."""
    if loan.returned_on is not None:
        raise LoanError(409, "loan already returned")
    if loan.lost:
        raise LoanError(409, "loan is closed as lost")
    if loan.renewals_used >= CONFIG.max_renewals:
        raise LoanError(409, "renewal limit reached")
    if holds_waiting:
        raise LoanError(409, "renewal blocked by holds")
    loan.due_on = loan.due_on + timedelta(days=CONFIG.loan_period_days)
    loan.renewals_used += 1
    return loan


def close(loan, today):
    if loan.returned_on is not None:
        raise LoanError(409, "loan already returned")
    loan.returned_on = today
    return loan


def declare_lost(loan):
    if loan.returned_on is not None:
        raise LoanError(409, "loan already returned")
    loan.lost = True
    return loan


def blocks_member(loan, today):
    """A member is blocked by any single loan this far past its due date."""
    return loan.days_overdue(today) > CONFIG.block_after_overdue_days
