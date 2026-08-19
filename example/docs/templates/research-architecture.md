---
id: research-architecture
title: <product> — architecture research
type: research
status: active
date: <YYYY-MM-DD>
---

# Research: the architecture of <product>

<One paragraph: what the system is and which niche it occupies. Not "a monitoring system", but what
it does differently from the neighbouring options and why anyone would take this one.>

This document records **verified facts** (what was actually read in code and artefacts),
**decisions taken**, and **risks**. Anything unverified is marked as a hypothesis and says where it
will be checked.

This is the entry point of the documentation: the layer documents say what the system does, and
this one says why it is built that way. It lives here permanently and is amended as the
implementation teaches you things — see §1's "correction found while implementing".

---

## 1. Verified facts

### 1.1 <Topic — for example: which API the required version of a dependency actually exposes>

Verified against `<the artefact, and exactly where in it>`.

| Fact | Where verified |
|---|---|
| <the claim> | `<path to the file / class inside the jar / URL of the listing>` |

**Consequence 1.** <What follows from this for the architecture. The consequences are the valuable
part — a fact on its own does nothing.>

**Correction found while implementing <milestone>** *(if one appeared)*: <this used to say X, which
is not possible because Y; the working replacement is Z.>

### 1.2 <Next topic>

…

---

## 2. Decisions

### D1. <The decision in one line> *(deviation from the brief, if that is what it is)*

Brief / first idea: <what was assumed>.
Decision: <what was chosen>.

Why:

- <a reason with numbers rather than adjectives>;
- <what broke in the alternative>;
- the price: <what this costs, honestly; link to the risk>.

### D2. <…>

---

## 3. Risks and open questions

**Risk 1. <What can go wrong, stated as a mechanism>.** Mitigation: <the concrete machinery, not an
intention>. Open: <what gets decided once there is real data>.

**Open question 1.** <A question with no answer yet, and the hypothesis about what the answer will
be — plus where it will be settled.>

---

## 4. What happens next

The order of work and the acceptance criteria live in the backlog. The first substantive steps:
<what has to be nailed down earliest, because everything else depends on it>.
