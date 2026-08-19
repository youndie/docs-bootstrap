"""Renewal rules. Run with `python3 -m pytest loans-service/tests` or directly."""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from loans_service.config import CONFIG  # noqa: E402
from loans_service.domain.loan import LoanError, checkout, renew  # noqa: E402

COPY = {"barcode": "30001", "book_id": "b-1"}
TODAY = date(2026, 3, 2)


def a_loan():
    return checkout(1, COPY, "m-100", TODAY)


def test_renewal_blocked_by_holds():
    loan = a_loan()
    try:
        renew(loan, TODAY, holds_waiting=True)
    except LoanError as exc:
        assert (exc.status, exc.message) == (409, "renewal blocked by holds")
        assert loan.renewals_used == 0
    else:
        raise AssertionError("a hold must block the renewal")


def test_renewal_limit_reached():
    loan = a_loan()
    period = timedelta(days=CONFIG.loan_period_days)
    for used in range(CONFIG.max_renewals):
        due_before = loan.due_on
        renew(loan, TODAY, holds_waiting=False)
        # The period is added to the due date, not to the day of the renewal.
        assert loan.due_on == due_before + period
        assert loan.renewals_used == used + 1
    try:
        renew(loan, TODAY, holds_waiting=False)
    except LoanError as exc:
        assert (exc.status, exc.message) == (409, "renewal limit reached")
    else:
        raise AssertionError("the third renewal must be rejected")


if __name__ == "__main__":
    test_renewal_blocked_by_holds()
    test_renewal_limit_reached()
    print("ok")
