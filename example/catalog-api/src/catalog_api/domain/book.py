"""Books, physical copies, and the rules for a copy's status.

catalog-api owns the bibliographic record and the shelf state of every copy.
It does not own loans: it never learns *who* has a book, only that the copy is
not on the shelf.
"""
from dataclasses import dataclass, field

ON_SHELF = "on_shelf"
ON_LOAN = "on_loan"
HELD = "held"
IN_REPAIR = "in_repair"
LOST = "lost"

STATUSES = (ON_SHELF, ON_LOAN, HELD, IN_REPAIR, LOST)

# A copy may be declared lost from any state, which is why LOST is not listed
# here — see set_status().
TRANSITIONS = {
    ON_SHELF: {ON_LOAN, HELD, IN_REPAIR},
    ON_LOAN: {ON_SHELF, HELD},
    HELD: {ON_LOAN, ON_SHELF},
    IN_REPAIR: {ON_SHELF},
    LOST: {ON_SHELF},
}


@dataclass
class Book:
    id: str
    title: str
    author: str
    year: int


@dataclass
class Copy:
    barcode: str
    book_id: str
    status: str = ON_SHELF


@dataclass
class Catalog:
    books: dict = field(default_factory=dict)
    copies: dict = field(default_factory=dict)

    def search(self, query, page, page_size):
        needle = query.casefold()
        hits = [
            b
            for b in self.books.values()
            if needle in b.title.casefold() or needle in b.author.casefold()
        ]
        hits.sort(key=lambda b: (b.title, b.id))
        start = (page - 1) * page_size
        return hits[start : start + page_size], len(hits)

    def copies_of(self, book_id):
        return [c for c in self.copies.values() if c.book_id == book_id]

    def set_status(self, copy, new_status):
        if new_status == LOST:
            copy.status = LOST
            return copy
        if new_status not in TRANSITIONS[copy.status]:
            raise StatusConflict(copy.status, new_status)
        copy.status = new_status
        return copy


class StatusConflict(Exception):
    def __init__(self, current, requested):
        super().__init__(f"{current} -> {requested}")
        self.current = current
        self.requested = requested


CATALOG = Catalog(
    books={
        "b-1": Book("b-1", "The Long Ships", "Frans G. Bengtsson", 1941),
        "b-2": Book("b-2", "A Pattern Language", "Christopher Alexander", 1977),
        "b-3": Book("b-3", "The Peregrine", "J. A. Baker", 1967),
    },
    copies={
        "30001": Copy("30001", "b-1"),
        "30002": Copy("30002", "b-1"),
        "30003": Copy("30003", "b-2"),
        "30004": Copy("30004", "b-3", IN_REPAIR),
    },
)
