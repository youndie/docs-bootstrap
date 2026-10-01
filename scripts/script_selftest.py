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
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPTS)
TEMPLATE = os.path.join(REPO, "templates", "Makefile")


def run(script, args, cwd):
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, script)] + args,
        cwd=cwd, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr)


def make(args, cwd):
    """The consumer's Makefile (templates/Makefile), run in a directory standing in for a project.

    The environment is scrubbed of anything a calling make or a calling CI would leak in: MAKEFLAGS
    carries the caller's command-line variables into every make below it, and a DOCS_BOOTSTRAP in
    the environment would answer the very question the pin cases ask.
    """
    leak = {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEFILES", "DOCS_BOOTSTRAP", "DOCS", "BACKLOG",
            "BACKLOG_FORM", "REPOS"}
    env = {k: v for k, v in os.environ.items() if k not in leak}
    result = subprocess.run(["make", "--no-print-directory", "-f", TEMPLATE] + args,
                            cwd=cwd, env=env, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr)


def pinned_copy(project, ref):
    """What a fetch of REF would leave behind, built from this checkout: the pin cases test how the
    Makefile finds its checks, not GitHub, and must not need the network."""
    cache = os.path.join(project, ".docs-bootstrap", ref)
    os.makedirs(cache)
    shutil.copy(os.path.join(REPO, "check.mk"), cache)
    shutil.copytree(SCRIPTS, os.path.join(cache, "scripts"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(os.path.join(REPO, ".claude-plugin"), os.path.join(cache, ".claude-plugin"))
    return os.path.realpath(cache)


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


PLUGIN = """{{
  "name": "x",
  "version": "{0}",
  "skills": ["."]
}}
"""


def git(cwd, *args):
    """git with an identity of its own: the fixture must not depend on the machine's config, and a
    commit signed by a hook or a missing user.email would fail for reasons that are not the check."""
    return subprocess.run(
        ["git", "-c", "user.name=selftest", "-c", "user.email=selftest@invalid",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"] + list(args),
        cwd=cwd, capture_output=True, text=True, check=True)


def plugin_repo(root):
    """A packaged skill with one commit, tagged `base` - what a pull request is compared with."""
    write(root, "SKILL.md", "---\nname: x\ndescription: y\n---\n")
    write(root, ".claude-plugin/plugin.json", PLUGIN.format("0.1.0"))
    write(root, "scripts/a.py", "print('a')\n")
    write(root, "README.md", "x\n")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    git(root, "tag", "base")


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

    # -- the consumer's Makefile: no subject, no verdict --------------------------------------------
    # Every script treats a missing tree as a mode and exits 0, as SPEC 7 requires of a tool; the
    # gate is what knows the repository HAS documentation. These are the cases a copied root
    # Makefile once passed in silence.
    here = ["DOCS_BOOTSTRAP=" + REPO]
    with tempfile.TemporaryDirectory() as project:
        code, out = make(["docs-gate"] + here, project)
        expect_true("the gate passed with no docs/ tree", code != 0 and "no docs tree" in out, out)

        write(project, "docs/README.md", "# docs\n")
        code, out = make(["docs-gate"] + here, project)
        expect_true("the gate passed with BACKLOG_FORM=files and no item files",
                    code != 0 and "BACKLOG_FORM=files" in out, out)

        code, out = make(["docs-gate", "BACKLOG_FORM=bogus"] + here, project)
        expect_true("the gate accepted BACKLOG_FORM=bogus", code != 0, out)

        # The negative control: a tree that is there and a backlog declared absent pass the guard.
        code, out = make(["docs-gate", "BACKLOG_FORM=none"] + here, project)
        expect("the gate on docs/ with BACKLOG_FORM=none", code, 0, out)

    # -- the consumer's Makefile: one pin, read from the workflow ------------------------------------
    uses = "      - uses: youndie/docs-bootstrap@{0}\n"
    with tempfile.TemporaryDirectory() as project:
        code, out = make(["docs-bootstrap-path"], project)
        expect_true("the Makefile ran with no pin to read", code != 0 and "uses:" in out, out)

        # Both jobs name the same tag: one version. The answer is the fetched copy of that tag.
        want = pinned_copy(project, "v9.9.9")
        write(project, ".github/workflows/check.yaml", uses.format("v9.9.9") * 2)
        code, out = make(["docs-bootstrap-path"], project)
        expect_true("the Makefile did not take its checks from the pinned ref",
                    code == 0 and out.strip() == want, out)

        # The shape Renovate writes when it pins digests.
        want = pinned_copy(project, "0123abc")
        write(project, ".github/workflows/check.yaml", uses.format("0123abc # v9.9.9"))
        code, out = make(["docs-bootstrap-path"], project)
        expect_true("the Makefile did not read a digest pin",
                    code == 0 and out.strip() == want, out)

        # Two refs is two versions, and the Makefile does not pick one.
        write(project, ".github/workflows/check.yaml", uses.format("v9.9.9") + uses.format("v9.9.8"))
        code, out = make(["docs-bootstrap-path"], project)
        expect_true("the Makefile chose between two pins", code != 0 and "more than one" in out, out)

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

    # -- a change that ships without a higher version (plugin_check --against) ---------------------
    # The positive control first: a script changed and the version left alone is exactly the state
    # this repository sat in for six weeks, and the check has to refuse it.
    with tempfile.TemporaryDirectory() as repo:
        plugin_repo(repo)
        against = ["--root", repo, "--against", "base"]

        write(repo, "scripts/a.py", "print('b')\n")
        code, out = run("plugin_check.py", against, repo)
        expect("plugin_check --against: a script changed, version not raised", code, 1, out)

        write(repo, ".claude-plugin/plugin.json", PLUGIN.format("0.1.1"))
        code, out = run("plugin_check.py", against, repo)
        expect("plugin_check --against: a script changed, version raised", code, 0, out)

        # Lowered is not raised.
        write(repo, ".claude-plugin/plugin.json", PLUGIN.format("0.0.9"))
        code, out = run("plugin_check.py", against, repo)
        expect("plugin_check --against: version lowered", code, 1, out)

        # A file nobody has added yet still ships once it is: a new template counts.
        git(repo, "checkout", "-q", "--", ".")
        write(repo, "templates/new.yaml", "x: 1\n")
        code, out = run("plugin_check.py", against, repo)
        expect("plugin_check --against: an untracked file in a shipped directory", code, 1, out)

        # What only this repository reads does not ask for a release.
        os.remove(os.path.join(repo, "templates", "new.yaml"))
        write(repo, "README.md", "y\n")
        write(repo, ".github/workflows/check.yaml", "on: push\n")
        code, out = run("plugin_check.py", against, repo)
        expect("plugin_check --against: README and CI only", code, 0, out)

        # A ref that cannot be read is a failure, not a pass: the question was not answered.
        code, out = run("plugin_check.py", ["--root", repo, "--against", "no-such-ref"], repo)
        expect("plugin_check --against an unreadable ref", code, 1, out)

    if failures:
        sys.stderr.write("\n\n".join(failures) + "\n")
        return 1
    print("script_selftest: every case passed - absent subjects refused by the scripts and by the "
          "Makefile, the pin read once and never guessed, uncounted scenarios reported, a shipped "
          "change without a version bump refused, and no guard fires on the shape it allows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
