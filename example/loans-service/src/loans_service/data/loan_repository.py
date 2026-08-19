"""Storage for loans and holds.

One repository for both, because a return has to close a loan and promote a
hold in the same breath; splitting them would need a transaction across two
stores for no gain.

The in-memory implementation below is what the development server runs. The
method list is the contract the SQL implementation has to satisfy.
"""
from ..domain.holds_queue import OPEN_STATES
from ..domain.loan import LOST, RETURNED


class LoanRepository:
    def __init__(self):
        self._loans = {}
        self._holds = {}
        self._next_loan_id = 1
        self._next_hold_id = 1

    # -- ids ------------------------------------------------------------
    def new_loan_id(self):
        loan_id, self._next_loan_id = self._next_loan_id, self._next_loan_id + 1
        return loan_id

    def new_hold_id(self):
        hold_id, self._next_hold_id = self._next_hold_id, self._next_hold_id + 1
        return hold_id

    # -- loans ----------------------------------------------------------
    def save_loan(self, loan):
        self._loans[loan.id] = loan
        return loan

    def loan(self, loan_id):
        return self._loans.get(loan_id)

    def open_loans_of(self, member_id):
        return [
            l
            for l in self._loans.values()
            if l.member_id == member_id and l.returned_on is None and not l.lost
        ]

    def open_loan_for_copy(self, barcode):
        for loan in self._loans.values():
            if loan.barcode == barcode and loan.returned_on is None:
                return loan
        return None

    def overdue_loans(self, today):
        return sorted(
            (l for l in self._loans.values() if l.state(today) not in (RETURNED, LOST)
             and today > l.due_on),
            key=lambda l: (l.due_on, l.id),
        )

    # -- holds ----------------------------------------------------------
    def save_hold(self, hold):
        self._holds[hold.id] = hold
        return hold

    def hold(self, hold_id):
        return self._holds.get(hold_id)

    def holds(self):
        return list(self._holds.values())

    def open_holds_for_book(self, book_id):
        return [
            h
            for h in self._holds.values()
            if h.book_id == book_id and h.status in OPEN_STATES
        ]


REPOSITORY = LoanRepository()
