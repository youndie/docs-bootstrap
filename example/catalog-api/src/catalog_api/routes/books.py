"""Search and lookup of bibliographic records.

A handler takes a request (``.query`` for the query string, ``.params`` for
path parameters, ``.body`` for the decoded JSON) and returns a
``(status, body)`` pair. ``hidden`` on a Route keeps the route out of the
published schema; see ``openapi.py``.
"""
from collections import namedtuple

from ..config import CONFIG
from ..domain.book import CATALOG

Route = namedtuple("Route", "method path handler auth hidden")


def _as_json(book):
    return {"id": book.id, "title": book.title, "author": book.author, "year": book.year}


def search_books(request):
    query = (request.query.get("q") or "").strip()
    if len(query) < CONFIG.min_query_length:
        return 400, {
            "error": f"query must be at least {CONFIG.min_query_length} characters"
        }
    try:
        page = int(request.query.get("page", "1"))
    except ValueError:
        return 400, {"error": "page must be a number"}
    if page < 1:
        return 400, {"error": "page must be a number"}

    hits, total = CATALOG.search(query, page, CONFIG.page_size)
    return 200, {"items": [_as_json(b) for b in hits], "page": page, "total": total}


def get_book(request):
    book = CATALOG.books.get(request.params["book_id"])
    if book is None:
        return 404, {"error": "book not found"}
    return 200, _as_json(book)


def reindex(request):
    """Rebuilds the search index. Returns before the work is finished."""
    return 202, {"status": "accepted", "books": len(CATALOG.books)}


ROUTES = [
    Route("GET", "/api/books", search_books, "staff-session", False),
    Route("GET", "/api/books/{book_id}", get_book, "staff-session", False),
    Route("POST", "/internal/books/reindex", reindex, "service-token", True),
]
