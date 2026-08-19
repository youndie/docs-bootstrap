---
id: librarian-web
title: librarian-web
type: service
repo_url: https://github.com/example-library/librarian-web
module: src
tech_stack: [JavaScript, React]
owner: unassigned
depends_on:
  - catalog-api
  - loans-service
publishes:
  - "librarian-web (static bundle)"
---

# librarian-web

## 1. Responsibility

The two screens the staff use: the [checkout desk](../screens/screen-checkout-desk.md) and
[catalogue search](../screens/screen-catalog-search.md). It renders what the services say and
sends what the librarian does.

It deliberately holds **no policy**. It does not check the loan limit, the renewal count or the
block before sending a request — those answers belong to loans-service, and duplicating them would
mean two places to change when a library changes its rules. The one exception is the due-date
hint, and it is listed in the quirks for exactly that reason.

It also does no authentication. There is no login screen and no token in the code: the reverse
proxy in front of `/catalog` and `/loans` adds the staff session, and every request goes out with
`credentials: "same-origin"` and nothing else.

## 2. API contracts

* **Client:** `src/api/client.js` — every URL the application knows, in one object. A screen that
  needs a new call adds it there rather than calling `fetch` itself.
* **Errors:** `ApiError` carries the HTTP status and the `error` string from the service. Both
  screens show that string **verbatim**; there is no mapping table and no rewording, which is why
  the wording in [endpoint-loans](../api/endpoint-loans.md) is user-facing text.
* **Route references:** [endpoint-catalog](../api/endpoint-catalog.md),
  [endpoint-loans](../api/endpoint-loans.md).

## 2a. Code anchors

| File | What is there |
|---|---|
| `librarian-web/src/api/client.js` | every request, the two proxy prefixes, `ApiError` |
| `librarian-web/src/state/checkoutState.js` | the desk's reducer, its four action functions, `LOAN_PERIOD_DAYS` |
| `librarian-web/src/pages/CheckoutDesk.jsx` | the desk |
| `src/pages/CatalogSearch.jsx` | search, availability, and the "Place hold" action |

## 3. Dependencies

| Kind | Name | What for |
|---|---|---|
| Service | [catalog-api](catalog-api.md) | search, availability — behind the `/catalog` prefix |
| Service | [loans-service](loans-service.md) | loans and holds — behind the `/loans` prefix |
| External | reverse proxy | serves the bundle, adds the staff session, maps the two prefixes |

## 4. Infrastructure and deploy

* **Bundle:** `librarian-web`, served as static files by the same proxy that fronts the two APIs —
  which is what makes `credentials: "same-origin"` sufficient.
* Build configuration, the application shell and its router are not part of this example
  repository: both pages are default-exported components and nothing mounts them here.

## 5. Local setup

The two pages need a bundler and a shell to run. Reading them does not:

```bash
sed -n '1,40p' librarian-web/src/state/checkoutState.js
```

Against a real backend, the proxy must map `/catalog` to catalog-api and `/loans` to
loans-service; without it every request is a 404 from the static file server.

## 6. Configuration

None. There is no configuration file and no environment variable: the two prefixes are constants at
the top of `src/api/client.js`, and everything else about the deployment lives in the proxy.

## 7. Quirks

* **The loan period is duplicated here.** `LOAN_PERIOD_DAYS = 21` in `checkoutState.js` exists so
  the desk can show a due date before the server answers. It is the one piece of lending policy in
  the client, it is the piece the librarian reads out loud to the member, and nothing detects it
  drifting from `LOAN_PERIOD_DAYS` in loans-service.
* **A failed detail request on catalogue search is silent.** `expand()` has no `catch`: if
  availability or the holds list fails, the row simply does not open, with no banner and no
  retry. The librarian's only feedback is that clicking does nothing.
* **Without the proxy the application still works.** Nothing in the client sends or checks
  credentials, so pointing the two prefixes straight at the services produces a fully functional,
  fully unauthenticated library system. The security of the product is entirely a deployment
  property.
