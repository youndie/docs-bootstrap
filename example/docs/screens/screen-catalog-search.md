---
id: screen-catalog-search
title: Catalogue search
type: client_screen
platform: [web]
status: active
entry:
  web: "/catalogue"
parent_feature: feature-holds-queue
calls_api:
  - endpoint-catalog
  - endpoint-loans
source: librarian-web/src/pages
design:
  canvas: https://example.invalid/design/librarian-catalogue   # the canvas is not public; the PNGs are
  references: librarian-web/design
  states:
    idle: CatalogSearch_idle
    loading: CatalogSearch_loading
    content: CatalogSearch_content
    empty: CatalogSearch_empty
    error: CatalogSearch_error
---

# Screen: Catalogue search

Find a book by title or author, see how many copies are on the shelf and how long the queue is, and
place a hold for the member on the telephone. It is the only screen that writes to the holds queue.

Part of [feature-holds-queue](../features/feature-holds-queue.md); it reads
[endpoint-catalog](../api/endpoint-catalog.md) and writes through
[endpoint-loans](../api/endpoint-loans.md).

## 0a. Code anchors

| What | File |
|---|---|
| Component | `librarian-web/src/pages/CatalogSearch.jsx` |
| HTTP | `librarian-web/src/api/client.js` — `searchBooks`, `availability`, `bookHolds`, `placeHold` |
| Error type | `src/api/client.js` — `ApiError` carries `status` and the service's `error` string |

## 0. Entry point and visibility

- **Entry point:** `/catalogue`, mounted by the application shell (not in this repository).
- **Shown when:** always, for staff. Same session cookie as
  [screen-checkout-desk](screen-checkout-desk.md).

## 1. Screen states

Local component state; `status` holds the literals below.

- [x] **`idle`:** the search field alone.
- [x] **`loading`:** the previous results stay on screen. `results` is replaced only on success, so
  a slow search looks like a screen that has not reacted yet.
- [x] **`content`:** the result list, one row per book, each expandable.
- [x] **`empty`:** "Nothing found." The result list is not cleared — `results` still holds the
  previous page — but nothing renders it, because the empty branch is checked first.
- [x] **`error`:** a banner with the service's message. `query must be at least 2 characters`
  arrives here as-is from catalog-api.

## 2. API integration

| Call | Client method | Endpoint document |
| :--- | :--- | :--- |
| `GET /api/books?q=&page=` | `api.searchBooks` | [endpoint-catalog](../api/endpoint-catalog.md) |
| `GET /api/books/{book_id}/availability` | `api.availability` | [endpoint-catalog](../api/endpoint-catalog.md) |
| `GET /api/books/{book_id}/holds` | `api.bookHolds` | [endpoint-loans](../api/endpoint-loans.md) |
| `POST /api/holds` | `api.placeHold` | [endpoint-loans](../api/endpoint-loans.md) |

The two prefixes in `client.js` (`/catalog`, `/loans`) are the proxy's routes to the two services.

## 3. Initialisation

> [!IMPORTANT]
> Nothing is requested on open. The screen starts in `idle` with an empty field.

**Input parameters:** none.

**Requests on load:** none.

**Handling the responses:**

| Call | Case | Handling | Screen state |
| :--- | :--- | :--- | :--- |
| `GET /api/books` | `200`, `items` non-empty | render the list | **content** |
| `GET /api/books` | `200`, `items` empty | "Nothing found." | **empty** |
| `GET /api/books` | `400` (query too short) | the service's message in the banner | **error** |
| `GET /api/books` | transport failure | `the catalogue is unreachable` | **error** |

## 4. UI elements, top to bottom

### 4.1. Search field

- **Field in UI state:** `query`.
- **Display:** one input, placeholder "Title or author". Submitted with Enter; there is no button
  and no debounce — a request is made per submit, not per keystroke.
- **On submit:** `GET /api/books?q=<trimmed>&page=1`. Page 2 cannot be requested: the client always
  sends `page=1`, so a search with more than `CATALOG_PAGE_SIZE` (25) hits shows the first page and
  no way to leave it.

### 4.2. Result row

- **Fields in API response:** `id`, `title`, `author`, `year`.
- **Display:** "Title — Author, Year" as a button.
- **On click:** `expand(book)` fires availability and holds in parallel and fills `detail`.

| Case | Handling | Screen state |
| :--- | :--- | :--- |
| both `200` | the detail block opens under the row | **content** |
| either fails | nothing happens at all — see the quirks | **content** |

### 4.3. Detail block

- **Fields in API response:** `availability.available_copies`, `availability.total_copies`, and the
  length of `holds.items`.
- **Display:** "2 of 3 on the shelf, 1 in the holds queue". A copy on the hold shelf is not
  available — `available_copies` counts `on_shelf` only.

### 4.4. Member card field and "Place hold"

- **Field in UI state:** `memberId` — one field for the whole screen, not per row.
- **On click:** `POST /api/holds {book_id, member_id}`.

| Case | Handling | Screen state |
| :--- | :--- | :--- |
| `201` | the new hold is appended to `detail.holds`, banner cleared | **content** |
| `409` `hold already placed` / `member already has this book on loan` | message in the banner | **content** |
| `422` `hold limit reached` | message in the banner | **content** |

## 5. Navigation (summary)

- none — like the desk, this screen is a leaf; the shell moves between the two.

## 6. Quirks

- **A failed detail request is invisible.** `expand` has no `catch`. If availability or the holds
  list fails, the promise rejects, `detail` is never set, and the row simply does not open. The
  librarian clicks again, and again, with no message anywhere.
- **The member card is shared between rows.** Expanding a second book keeps the card typed for the
  first. Placing two holds for two different members in a row means remembering to retype it, and
  nothing prompts for that.
- **The appended hold does not refresh the others.** After a `201` the client pushes the server's
  object into `detail.holds` instead of re-reading the queue, so the positions shown for the other
  members are as stale as the moment the row was opened — which is exactly the recomputation
  problem described in [B-02](../backlog/B-02-store-hold-positions.md).
