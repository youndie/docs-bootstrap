"""Builds the published schema from the route tables.

The only thing that decides whether a route is public is the ``hidden`` flag on
the Route tuple. There is no allow-list and no annotation: a new route is public
unless whoever added it said otherwise.
"""
from .routes import availability, books

ALL_ROUTES = books.ROUTES + availability.ROUTES


def public_schema(version="1.0.0"):
    paths = {}
    for route in ALL_ROUTES:
        if route.hidden:
            continue
        entry = paths.setdefault(route.path, {})
        entry[route.method.lower()] = {
            "operationId": route.handler.__name__,
            "summary": (route.handler.__doc__ or "").strip().splitlines()[0]
            if route.handler.__doc__
            else route.handler.__name__,
            "security": [{route.auth: []}],
        }
    return {"openapi": "3.0.3", "info": {"title": "catalog-api", "version": version}, "paths": paths}
