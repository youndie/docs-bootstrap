---
id: screen-<kebab-name>          # or bot-flow-<name> for a conversational flow
title: <Screen name>
type: client_screen | client_flow
platform: [<platform>]           # e.g. web, ios, android, desktop, chat-bot
status: draft | active
entry:
  <platform>: "<route / screen constructor / bot command>"
parent_feature: feature-<...>
calls_api:
  - <endpoint-id>
source: <repo>/<path to the feature directory in code>
---

# Screen: <name>

> For `client_flow` the sections adapt: "UI elements, top to bottom" → "dialog steps",
> "screen states" → the states of the wizard or state machine.

## 0a. Code anchors

| What | File |
|---|---|
| View model | `<source>/<ViewModel>` |
| UI state | `<source>/<UiState>` |
| Composition / markup | `<source>/<Component>` |
| Wiring / DI | `<source>/<Module>` |

## 0. Entry point and visibility

- **Entry point:** [e.g. the "Cart" tab in the bottom navigation / a main-menu item]
- **Shown when:** [always / behind a feature flag / authenticated users only]

## 1. Screen states

List these from the actual state class, using the field names that are in the code.

- [ ] **Loading:** [skeleton, spinner on the button]
- [ ] **Empty:** [the empty state and its call to action]
- [ ] **Content:** [the main state]
- [ ] **Warning / blocked:** [if applicable] <!-- optional -->
- [ ] **Error:** [banner / toast / retry; which errors are specialised and which are generic]

## 2. API integration

The contract classes (full names) or method + URL, plus links to the endpoint documents — that is
where auth tiers and errors live:

| Call | Contract | Endpoint document |
| :--- | :--- | :--- |
| `POST /api/loans` | `LoansResource` | [endpoint-loans](../api/endpoint-loans.md) |

## 3. Initialisation

What is passed in when the screen opens, and which requests or subscriptions start immediately.

> [!IMPORTANT]
> **Only** what runs automatically on open. A request triggered by the user belongs to that
> element's block in section 4.

**Input parameters:**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `itemId` | `String` | [e.g. from the navigation arguments] |

**Requests and subscriptions on load:**

| Call | Condition | Result |
| :--- | :--- | :--- |
| `GET /api/...` | always | loads … |

**Handling the responses:**

| Call | Case | Handling | Screen state |
| :--- | :--- | :--- | :--- |
| `GET /api/...` | `200`, data present | map to UI | **Content** |
| `GET /api/...` | `200`, empty | — | **Empty** |
| `GET /api/...` | `4xx/5xx`, timeout | [silent fail / retry / cache] | **Error** / hidden |

## 4. UI elements, top to bottom

One block per element: where the data comes from, how it is displayed, its states, its action.

### 4.1. <Element>

- **Field in API / UI state:** `CartUiItem.price`
- **Display:** [formatting, truncation, plural forms]
- **States:** [if any]
- **On tap:** [nothing / navigate / call a use case]

> If the action calls the API, handle the response here:
>
> | Case | Handling | Screen state |
> | :--- | :--- | :--- |
> | success | … | … |
> | error / timeout | [toast / banner] | unchanged |

### 4.2. <Next element>

…

## 5. Navigation (summary)

The transitions from section 4 collected into one list, for the navigation graph:

- <event> ──▶ <screen-id / external destination>
