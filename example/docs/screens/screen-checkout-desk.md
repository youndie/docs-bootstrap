---
id: screen-checkout-desk
title: Checkout desk
type: client_screen
platform: [web]
status: active
entry:
  web: "/desk"
parent_feature: feature-borrow-and-return
calls_api:
  - endpoint-loans
source: librarian-web/src/pages
---

# Screen: Checkout desk

The screen a librarian keeps open all day. One member at a time, one barcode at a time; every
action is a single request whose error message is shown verbatim.

Part of [feature-borrow-and-return](../features/feature-borrow-and-return.md); it talks only to
[loans-service](../services/loans-service.md) through
[endpoint-loans](../api/endpoint-loans.md).

## 0a. Code anchors

| What | File |
|---|---|
| Component | `librarian-web/src/pages/CheckoutDesk.jsx` |
| State and actions | `librarian-web/src/state/checkoutState.js` — `initialState`, `reduce`, the four action functions |
| HTTP | `src/api/client.js` — `api.checkout`, `api.renew`, `api.returnLoan`, `api.memberLoans` |

## 0. Entry point and visibility

- **Entry point:** `/desk`, mounted by the application shell. The shell and its router are not in
  this repository; this screen is a default-exported component and nothing else.
- **Shown when:** always, for staff. The reverse proxy in front of `/loans` and `/catalog` adds the
  session cookie; the client sends no token of its own (`credentials: "same-origin"`).

## 1. Screen states

From `initialState` in `checkoutState.js`; `status` is the field, the values are its literals.

- [x] **`idle`:** the member field alone. Nothing has been requested yet.
- [x] **`loading`:** the body is not rendered — section 4 is gated on `status === "content"`, so
  between scanning a card and the answer the desk shows only the member field. There is no
  skeleton and no spinner.
- [x] **`content`:** barcode field, due-date hint, and the member's open loans.
- [x] **Blocked (`blocked: true`, orthogonal to `status`):** a warning banner above the loan list.
  The screen does not disable anything — the block is enforced by loans-service, and the banner
  only explains the `403` before it happens.
- [x] **`error`:** the banner replaces the body, but **only when the member has no loans loaded**.
  `reduce` keeps `status: "content"` on a failure whenever `loans.length > 0`, so a failed scan
  leaves the desk usable and puts the message in the banner above it. This is the whole point of
  the screen: a rejected book must not cost the librarian the member they are serving.

## 2. API integration

| Call | Client method | Endpoint document |
| :--- | :--- | :--- |
| `GET /api/members/{member_id}/loans` | `api.memberLoans` | [endpoint-loans](../api/endpoint-loans.md) |
| `POST /api/loans` | `api.checkout` | [endpoint-loans](../api/endpoint-loans.md) |
| `POST /api/loans/{loan_id}/renew` | `api.renew` | [endpoint-loans](../api/endpoint-loans.md) |
| `POST /api/loans/{loan_id}/return` | `api.returnLoan` | [endpoint-loans](../api/endpoint-loans.md) |

Every path is prefixed with `/loans` by `client.js`; that prefix is the proxy's, not the service's.

## 3. Initialisation

> [!IMPORTANT]
> Nothing is requested when the screen opens. The first request is caused by the librarian
> submitting a member card.

**Input parameters:** none. The screen takes no props and reads no navigation arguments.

**Requests on load:** none.

**Handling the responses** (after a member card is submitted):

| Call | Case | Handling | Screen state |
| :--- | :--- | :--- | :--- |
| `GET /api/members/{id}/loans` | `200`, `items` non-empty | fill the table, read `blocked` | **content** |
| `GET /api/members/{id}/loans` | `200`, `items` empty | "Nothing on loan." | **content** |
| `GET /api/members/{id}/loans` | any error | `describe(error)` into the banner | **error** |

A transport failure (no HTTP status) is shown as `the service is unreachable`; everything else
shows the service's own `error` string.

## 4. UI elements, top to bottom

### 4.1. Member card field

- **Field in UI state:** `memberId` (committed), local `memberInput` (typed).
- **Display:** a single text input, placeholder "Scan or type a member card".
- **On submit:** `loadMember` → `GET /api/members/{id}/loans`. The value is trimmed.

### 4.2. Banners

- **Field in UI state:** `error` (`role="alert"`) and `blocked` (`role="status"`).
- **Display:** the service's message verbatim. No mapping table, no rewording — the desk shows
  `copy already on loan` because that is what the service said.

### 4.3. Barcode field

- **Field in UI state:** local `barcode`; rendered only in **content**.
- **Display:** `autoFocus`, so the field takes focus the moment the content state appears, and it
  is cleared after every scan. Nothing re-focuses it after **Renew** or **Return** — the barcode
  scanner types into whatever holds focus, so a scan made straight after clicking a button goes
  into the button and is lost. See the quirks.
- **On submit:** `checkoutCopy` → `POST /api/loans`, then a fresh `GET .../loans` regardless of the
  outcome.

| Case | Handling | Screen state |
| :--- | :--- | :--- |
| `201` | the loan appears in the table on the refresh | **content** |
| `409` / `422` / `403` / `404` | message into the banner, field cleared | **content** |

### 4.4. Due-date hint

- **Field in UI state:** none — `duePreview()` computes today + `LOAN_PERIOD_DAYS`.
- **Display:** "Due 2026-03-23" next to the barcode field, before any request is made.

### 4.5. Loan table

- **Fields in API response:** `barcode`, `due_on`, `renewals_left`, `state`.
- **Display:** one row per open loan; `state` (`active` / `overdue`) becomes the row's CSS class.
- **Actions:** **Renew** → `POST .../renew`, **Return** → `POST .../return`. Both refresh the
  member afterwards.

### 4.6. Hold-shelf banner

- **Field in UI state:** `lastAction.nextHold`.
- **Display:** shown after a return that promoted a hold: which copy to put on the hold shelf and
  for whom. It is the only instruction in the product that the librarian must act on physically.

## 5. Navigation (summary)

- none — the desk is a leaf. Switching to [screen-catalog-search](screen-catalog-search.md) happens
  through the application shell, which lives outside this repository.

## 6. Quirks

- **`LOAN_PERIOD_DAYS = 21` is duplicated in the client.** `checkoutState.js` needs it to show a
  due date before the server answers. If a library changes `LOAN_PERIOD_DAYS` in loans-service, the
  hint lies until someone changes the constant here too — and the hint is what the librarian reads
  aloud to the member.
- **`lastAction` survives the next member.** `reduce` clears it only on `reset`, which nothing
  calls, so the hold-shelf banner from the previous member stays on screen while the next one is
  being served.
- **Focus is only restored by the librarian.** `autoFocus` fires once. Every **Renew** and
  **Return** button moves focus to itself and nothing gives it back, so the next scan lands
  nowhere. Librarians learn to click the barcode field after every button; nothing in the code
  says they must.
