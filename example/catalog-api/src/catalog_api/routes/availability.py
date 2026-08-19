"""Shelf state: how many copies of a book can be taken away right now, and the
internal routes loans-service uses to move a single copy between states.
"""
from .books import Route
from ..domain.book import CATALOG, ON_SHELF, STATUSES, StatusConflict


def _copy_json(copy):
    return {"barcode": copy.barcode, "book_id": copy.book_id, "status": copy.status}


def book_availability(request):
    book_id = request.params["book_id"]
    if book_id not in CATALOG.books:
        return 404, {"error": "book not found"}
    copies = CATALOG.copies_of(book_id)
    on_shelf = [c.barcode for c in copies if c.status == ON_SHELF]
    return 200, {
        "book_id": book_id,
        "total_copies": len(copies),
        "available_copies": len(on_shelf),
        "on_shelf": sorted(on_shelf),
    }


def get_copy(request):
    copy = CATALOG.copies.get(request.params["barcode"])
    if copy is None:
        return 404, {"error": "copy not found"}
    return 200, _copy_json(copy)


def set_copy_status(request):
    copy = CATALOG.copies.get(request.params["barcode"])
    if copy is None:
        return 404, {"error": "copy not found"}
    requested = (request.body or {}).get("status")
    if requested not in STATUSES:
        return 400, {"error": "unknown copy status"}
    try:
        CATALOG.set_status(copy, requested)
    except StatusConflict:
        return 409, {"error": "copy status conflict"}
    return 200, _copy_json(copy)


ROUTES = [
    Route(
        "GET",
        "/api/books/{book_id}/availability",
        book_availability,
        "staff-session",
        False,
    ),
    Route("GET", "/internal/copies/{barcode}", get_copy, "service-token", True),
    Route(
        "POST",
        "/internal/copies/{barcode}/status",
        set_copy_status,
        "service-token",
        True,
    ),
]
