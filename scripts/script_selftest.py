#!/usr/bin/env python3
"""What the scripts do on the cases `make check` cannot reach.

`make check` runs every script against the example tree, which is complete and correct on purpose.
So two kinds of behaviour are exercised by no gate in this repository and by no gate in any
repository that runs these checks: what a script does when its subject is ABSENT, and what it does
on a defect the example deliberately does not carry. Each check below builds the case in a
temporary directory, runs the real script on it, and asserts the outcome - and every guard is held
from both sides, a fixture that must trip it and one that must not, because a guard that has only
ever been seen passing has not been seen working.

It began with one defect of the first kind. `backlog_index.py --check` printed "no backlog items ...
- nothing checked" and exited 0, so a backlog lost to a bad merge, a `git mv` or a `--docs` path
that stopped matching was reported as a pass - on a green step, in a log nobody opens. A check that
cannot find its subject and reports success is worse than no check.
"""
import json
import os
import subprocess
import sys
import tempfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def run(script, args, cwd):
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, script)] + args,
        cwd=cwd, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr)


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


SERVICE = """---
id: svc
title: A service
type: service
tech_stack: [python]
---

| Service | Code |
|---|---|
| svc | `svc/src/app.py` |
"""

FEATURE = """---
id: feature-x
title: X
type: feature
status: active
involved_services: [svc]
client_entries: []
api: []
---

| Service | Code |
|---|---|
| svc | `svc/src/app.py` |

## 5. Scenarios
{0}
"""

# Two scenarios in one gherkin block under a section heading: what a person reads as two scenarios
# and every counter reads as none. The shape the warning was written for.
GHERKIN_UNDER_SECTION = """
```gherkin
Scenario: the first
  Given a thing
  Then it works

Scenario: the second
  Given another thing
  Then it works too
```
"""

# The same steps, each under its own heading: the block is the body, and the heading is counted.
GHERKIN_UNDER_HEADINGS = """
### Scenario: the first

```gherkin
Given a thing
Then it works
```

### Scenario: the second
* **Given:** another thing
* **Then:** it works too
"""


def uncounted(tree):
    """docs_check's exit code and the `uncounted-scenarios` warnings it raised on a tree."""
    code, out = run("docs_check.py", ["--json", "--docs", os.path.join(tree, "docs")], tree)
    try:
        report = json.loads(out)
    except ValueError:
        return code, None, out
    return code, [w for w in report["warnings"] if w["check"] == "uncounted-scenarios"], out


def main():
    failures = []

    def expect(label, code, wanted, output):
        if code != wanted:
            failures.append("{0}: exit {1}, wanted {2}\n{3}".format(label, code, wanted, output))

    def expect_true(label, ok, output):
        if not ok:
            failures.append("{0}\n{1}".format(label, output))

    # -- the subject is absent ---------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as empty:
        # A project with no backlog yet is not an error when nobody asked a question.
        code, out = run("backlog_index.py", [], empty)
        expect("backlog_index with no backlog", code, 0, out)

        # ... and is an error the moment somebody asks whether the index is in order.
        code, out = run("backlog_index.py", ["--check"], empty)
        expect("backlog_index --check with no backlog", code, 1, out)

        # The escape hatch, for a caller that runs the gate before its first item exists.
        code, out = run("backlog_index.py", ["--check", "--allow-missing"], empty)
        expect("backlog_index --check --allow-missing", code, 0, out)

        # The same question asked of a git ref cannot be answered either.
        code, out = run("backlog_index.py", ["--against", "main"], empty)
        expect("backlog_index --against with no backlog", code, 1, out)

    # -- scenarios nothing counts (SPEC 3.1) -------------------------------------------------------
    # The positive control: the fixture built to trip the warning trips it, and the exit code stays
    # 0 because it is a warning. Without this half the negative case below proves nothing - a
    # detector that never fires passes it too.
    with tempfile.TemporaryDirectory() as tree:
        write(tree, "docs/services/svc.md", SERVICE)
        write(tree, "docs/features/feature-x.md", FEATURE.format(GHERKIN_UNDER_SECTION))
        code, warned, out = uncounted(tree)
        expect("docs_check on scenarios in one gherkin block", code, 0, out)
        expect_true("docs_check did not warn about two scenarios in a gherkin block under a "
                    "section heading", bool(warned), out)

    with tempfile.TemporaryDirectory() as tree:
        write(tree, "docs/services/svc.md", SERVICE)
        write(tree, "docs/features/feature-x.md", FEATURE.format(GHERKIN_UNDER_HEADINGS))
        code, warned, out = uncounted(tree)
        expect("docs_check on scenarios under their own headings", code, 0, out)
        expect_true("docs_check warned about a gherkin block that is the body of a counted "
                    "heading", warned == [], out)

    if failures:
        sys.stderr.write("\n\n".join(failures) + "\n")
        return 1
    print("script_selftest: every case passed - absent subjects refused, uncounted scenarios "
          "reported, and neither guard fires on the shape it allows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
