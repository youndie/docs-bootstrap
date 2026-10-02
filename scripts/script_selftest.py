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


def anchors(tree, repos, *extra):
    """code_anchors' exit code and its JSON report, run from `tree` against `repos`."""
    code, out = run("code_anchors.py", ["--json", "--docs", os.path.join(tree, "docs"),
                                        "--repos", repos] + list(extra), tree)
    try:
        return code, json.loads(out), out
    except ValueError:
        return code, None, out


def missing_paths(report):
    return sorted(a["path"] for a in report["anchors"] if a["status"] == "missing") if report else None


def bdd(tree, repos=None):
    """bdd_report's JSON report on a tree, with the existence check when `repos` is given."""
    args = ["--json", "--docs", os.path.join(tree, "docs")] + (["--repos", repos] if repos else [])
    code, out = run("bdd_report.py", args, tree)
    try:
        return json.loads(out), out
    except ValueError:
        return None, out


def doc(status, anchor, body=""):
    """A feature document with one anchor and the given status."""
    return ("---\nid: feature-x\ntitle: X\ntype: feature\nstatus: {0}\ninvolved_services: []\n"
            "client_entries: []\napi: []\n---\n\n| Service | Code |\n|---|---|\n| app | `{1}` |\n{2}"
            .format(status, anchor, body))


def failing_python(root, scripts):
    """A PY that fails for the named scripts - the way a killed report fails - and runs the rest."""
    path = os.path.join(root, "py-failing")
    cases = "|".join("*/" + name for name in scripts)
    write(root, "py-failing", '#!/bin/sh\ncase "$1" in {0}) echo "killed: $1" >&2; exit 137;; esac\n'
                              'exec "{1}" "$@"\n'.format(cases, sys.executable))
    os.chmod(path, 0o755)
    return path


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

    # -- the template's pin is the version that ships it ---------------------------------------------
    with tempfile.TemporaryDirectory() as repo:
        write(repo, "SKILL.md", "---\nname: x\ndescription: y\n---\n")
        write(repo, ".claude-plugin/plugin.json",
              '{"name": "x", "version": "0.2.0", "skills": ["."], '
              '"repository": "https://github.com/someone/x"}\n')
        write(repo, "templates/workflow-check.yaml", "      - uses: someone/x@v0.1.0\n")
        code, out = run("plugin_check.py", ["--root", repo], repo)
        expect("plugin_check: a template pinning the previous release", code, 1, out)

        write(repo, "templates/workflow-check.yaml", "      - uses: someone/x@v0.2.0\n")
        code, out = run("plugin_check.py", ["--root", repo], repo)
        expect("plugin_check: a template pinning the shipping release", code, 0, out)

    # -- reports do not block, the gate does (check.mk docs-report) -----------------------------------
    # `make check` is `gate report`. A report that dies - killed for memory, a walk that started at
    # `/` - must leave it green, and a gate line that fails must still turn it red: the second half
    # is what proves the first is not a check that never fails.
    with tempfile.TemporaryDirectory() as project:
        shutil.copytree(os.path.join(REPO, "example"), project, dirs_exist_ok=True)
        base = ["check", "REPOS=."] + here
        reports_die = failing_python(project, ["bdd_report.py", "code_anchors.py"])
        code, out = make(base + ["PY=" + reports_die], project)
        expect("make check with both reports failing", code, 0, out)

        gate_dies = failing_python(project, ["docs_check.py"])
        code, out = make(base + ["PY=" + gate_dies], project)
        expect_true("make check passed with a gate line failing", code != 0, out)

        # ANCHORS_ARGS=--check is the documented request to block on the anchors, and keeps working.
        code, out = make(base + ["PY=" + reports_die, "ANCHORS_ARGS=--check"], project)
        expect_true("make check ANCHORS_ARGS=--check passed with the anchors report failing",
                    code != 0, out)

    # -- code anchors: what is not looked in, and what is not looked at -------------------------------
    # A deprecated document's anchors say where the behaviour was (SPEC 6); they are not rot. Held
    # from both sides: the same document, active, reports the same anchor missing.
    with tempfile.TemporaryDirectory() as tree:
        write(tree, "app/src/live.py", "x = 1\n")
        write(tree, "docs/features/feature-x.md", doc("deprecated", "app/src/gone.py"))
        code, report, out = anchors(tree, ".", "--check")
        expect("code_anchors --check on a deprecated document's anchor", code, 0, out)
        expect_true("code_anchors did not name the deprecated document it skipped",
                    report is not None and report.get("deprecated_documents") == ["features/feature-x.md"],
                    out)
        write(tree, "docs/features/feature-x.md", doc("active", "app/src/gone.py"))
        code, report, out = anchors(tree, ".", "--check")
        expect("code_anchors --check on an active document's missing anchor", code, 1, out)

    # `--repos .` makes this repository's subdirectories the trees, `.github` among them.
    with tempfile.TemporaryDirectory() as tree:
        write(tree, ".github/workflows/check.yaml", "on: push\n")
        write(tree, "app/src/live.py", "x = 1\n")
        write(tree, "docs/features/feature-x.md", doc("active", ".github/workflows/check.yaml"))
        code, report, out = anchors(tree, ".")
        expect_true("code_anchors --repos . reported an anchor into .github/ as missing",
                    missing_paths(report) == [], out)

    # A tree that is walked, not listed by git, must not index the checks a Makefile fetched into
    # .docs-bootstrap/ - they carry docs-bootstrap's own example, `routes/loans.py` included.
    fetched = ".docs-bootstrap/v9.9.9/example/loans-service/src/loans_service/routes/loans.py"
    with tempfile.TemporaryDirectory() as tree:
        write(tree, "app/src/live.py", "x = 1\n")
        write(tree, "app/" + fetched, "x = 1\n")
        write(tree, "docs/features/feature-x.md", doc("active", "routes/loans.py"))
        code, report, out = anchors(tree, ".")
        expect_true("code_anchors found an anchor inside a fetched .docs-bootstrap/",
                    missing_paths(report) == ["routes/loans.py"], out)

    # A worktree is a git checkout whose `.git` is a file. Read as a plain directory it was walked,
    # and what git ignores - here a fetched copy of the checks - resolved anchors and named tests.
    with tempfile.TemporaryDirectory() as root:
        origin, repos = os.path.join(root, "origin"), os.path.join(root, "repos")
        write(origin, "src/live.py", "x = 1\n")
        write(origin, ".gitignore", "generated/\n")
        git(origin, "init", "-q")
        git(origin, "add", "-A")
        git(origin, "commit", "-q", "-m", "base")
        worktree = os.path.join(repos, "app")
        os.makedirs(repos)
        git(origin, "worktree", "add", "-q", worktree)
        write(worktree, "generated/routes/loans.py", "def test_ghost(): pass\n")
        tree = os.path.join(root, "doctree")
        write(tree, "docs/features/feature-x.md", doc(
            "active", "routes/loans.py",
            "\n### Scenario: a ghost\n* **Automated:** `test_ghost`\n"))
        code, report, out = anchors(tree, repos)
        expect_true("code_anchors walked a worktree and found an anchor in an ignored directory",
                    missing_paths(report) == ["routes/loans.py"], out)
        report, out = bdd(tree, repos)
        found = [r.get("found") for d in (report or {}).get("documents", []) for r in d.get("references", [])]
        expect_true("bdd_report walked a worktree and found a test in an ignored directory",
                    found == [False], out)

    # A path may cite a line or a range (SPEC 4). It used to be collected as nothing - neither found
    # nor missing - so the file under it could move or go and the report never said.
    with tempfile.TemporaryDirectory() as tree:
        write(tree, "app/src/live.py", "a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n")
        write(tree, "docs/features/feature-x.md", doc(
            "active", "app/src/live.py:2-4",
            "\nAlso `app/src/gone.py:3` and `app/src/live.py:40-52`.\n"))
        code, report, out = anchors(tree, ".")
        statuses = sorted((a["path"], a.get("lines"), a["status"])
                          for a in (report or {}).get("anchors", []))
        expect_true("code_anchors did not check anchors that cite lines: a range inside the file "
                    "found, a missing file and a range past the file's end missing",
                    statuses == [("app/src/gone.py", [3, 3], "missing"),
                                 ("app/src/live.py", [2, 4], "found"),
                                 ("app/src/live.py", [40, 52], "missing")], out)

    # ... and docs_check counts it as the path into the code a document must carry. The control: the
    # same document with no path at all is refused, so the case can fail.
    def no_anchor_errors(tree):
        code, out = run("docs_check.py", ["--json", "--docs", os.path.join(tree, "docs")], tree)
        try:
            return [e for e in json.loads(out)["errors"] if e["check"] == "no-code-anchor"], out
        except (ValueError, KeyError):
            return None, out

    with tempfile.TemporaryDirectory() as tree:
        write(tree, "docs/features/feature-x.md", doc("active", "app/src/live.py:2"))
        errors, out = no_anchor_errors(tree)
        expect_true("docs_check refused a document whose only anchor cites a line", errors == [], out)
        write(tree, "docs/features/feature-x.md", doc("active", "no path here"))
        errors, out = no_anchor_errors(tree)
        expect_true("docs_check accepted a document with no anchor at all", bool(errors), out)

    # An anchor is looked for in ITS repository. Matched against every sibling, `a/x.md` - repository
    # `a`, not checked out here - resolved to `b`'s x.md once its first segment was cut off, and a
    # path missing from the documented repository was "found" in whichever sibling had it.
    with tempfile.TemporaryDirectory() as root:
        repos = os.path.join(root, "repos")
        write(repos, "b/x.md", "x\n")
        write(repos, "b/src/thing.py", "x = 1\n")
        write(repos, "b/src/only_b.py", "x = 1\n")
        write(repos, "c/src/thing.py", "x = 1\n")
        write(repos, "own/src/live.py", "x = 1\n")
        body = "\n`b/x.md`, `src/thing.py`, `src/live.py`.\n"
        write(repos, "own/docs/features/feature-x.md",
              doc("active", "a/x.md", body + "And `src/only_b.py`.\n"))
        code, report, out = anchors(os.path.join(repos, "own"), repos)
        status = dict((a["path"], a["status"]) for a in (report or {}).get("anchors", []))
        expect_true("code_anchors found an anchor outside its repository: `a/x.md` with only "
                    "`b/x.md` checked out, or a path the documented repository lacks in a sibling",
                    status == {"a/x.md": "missing", "b/x.md": "found", "src/thing.py": "missing",
                               "src/live.py": "found", "src/only_b.py": "missing"}, out)

        # A documentation tree that is none of the repositories, and no service to say which: a path
        # one repository has is found there, a path two have is ambiguous, and `a/x.md` is still not
        # `b`'s x.md.
        tree = os.path.join(root, "doctree")
        write(tree, "docs/features/feature-x.md",
              doc("active", "src/only_b.py", body + "And `a/x.md`.\n"))
        code, report, out = anchors(tree, repos)
        status = dict((a["path"], a["status"]) for a in (report or {}).get("anchors", []))
        expect_true("code_anchors chose between two repositories that both have a path, or found "
                    "`a/x.md` in b", status.get("src/only_b.py") == "found"
                    and status.get("src/thing.py") == "missing" and status.get("a/x.md") == "missing",
                    out)

    # -- backlog numbers against the base: a rename is not a theft ------------------------------------
    item = "---\nid: B-01\ntitle: \"{0}\"\nstatus: open\n---\n\n{1}\n"
    with tempfile.TemporaryDirectory() as repo:
        write(repo, "docs/backlog/B-01-old-title.md", item.format("Old", "A long enough body for "
              "git to see the same file under a new name, line one.\nline two\nline three\n"))
        git(repo, "init", "-q")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "base")
        git(repo, "tag", "base")
        git(repo, "mv", "docs/backlog/B-01-old-title.md", "docs/backlog/B-01-new-title.md")
        git(repo, "commit", "-q", "-m", "retitle")
        code, out = run("backlog_index.py", ["--against", "base"], repo)
        expect("backlog_index --against: the branch renamed its own item", code, 0, out)

        # The control: the same number under another slug, NOT a rename - a different task.
        git(repo, "rm", "-q", "docs/backlog/B-01-new-title.md")
        write(repo, "docs/backlog/B-01-another-task.md", item.format("Another", "Unrelated."))
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "steal")
        code, out = run("backlog_index.py", ["--against", "base"], repo)
        expect("backlog_index --against: a different task under a taken number", code, 1, out)

    # -- what an `**Automated:**` line names, and which lines count (SPEC 3.1) ------------------------
    lines = """
## 2. Business rules

A scenario with an `**Automated:**` line names its test; this sentence is about the line.

* A rule a test holds. **Automated:** `RuleTest`

## 5. Scenarios

### Scenario: two tests and a module
* **Automated:** `e2e ScenarioTest`, `feature/x-data XDataTest`

### Scenario: a test, where it lives, and a quotation
* **Automated:** `app LoanTest` in `src/LoanTest.kt` - the case `a loan that is returned, late`

### Scenario: a sentence for a name
* **Automated:** `src/LoanTest.kt::a loan is refused while somebody waits`
"""
    with tempfile.TemporaryDirectory() as tree:
        repos = os.path.join(tree, "repos")
        write(repos, "app/e2e/src/ScenarioTest.kt", "class ScenarioTest\n")
        write(repos, "app/feature/x-data/src/XDataTest.kt", "class XDataTest\n")
        write(repos, "app/src/LoanTest.kt",
              "class LoanTest {\n  fun `a loan is refused while somebody waits`() {}\n}\n")
        write(repos, "app/src/RuleTest.kt", "class RuleTest\n")
        write(tree, "docs/features/feature-x.md", doc("active", "src/LoanTest.kt", lines))
        report, out = bdd(tree, repos)
        if report is None:
            failures.append("bdd_report printed no JSON\n" + out)
        else:
            refs = [(r["repo"], r["test"], r["needle"], r.get("found"))
                    for d in report["documents"] for r in d.get("references", [])]
            expect_true("bdd_report counted an `**Automated:**` line outside any scenario "
                        "(wanted 3 of 3)", report["automated"] == 3 and report["total"] == 3, out)
            stray = [l for d in report["documents"] for l in d.get("outside_scenarios", [])]
            expect_true("bdd_report took the marker quoted in prose for an `**Automated:**` line "
                        "(wanted the business rule's line alone outside the scenarios)",
                        stray == ["`RuleTest`"], out)
            expect_true("bdd_report did not read both tests of a comma-separated line, a module "
                        "path as their repository, or found neither",
                        refs[:2] == [("e2e", "ScenarioTest", "ScenarioTest", True),
                                     ("feature/x-data", "XDataTest", "XDataTest", True)], out)
            expect_true("bdd_report read a file path or a quotation as a test",
                        refs[2:3] == [("app", "LoanTest", "LoanTest", True)], out)
            expect_true("bdd_report did not take the whole sentence after `::` as the name",
                        refs[3:] == [("", "src/LoanTest.kt::a loan is refused while somebody waits",
                                      "a loan is refused while somebody waits", True)], out)

    if failures:
        sys.stderr.write("\n\n".join(failures) + "\n")
        return 1
    print("script_selftest: every case passed - absent subjects refused by the scripts and by the "
          "Makefile, the pin read once and never guessed, uncounted scenarios reported, a shipped "
          "change without a version bump and a template pinning another release refused, reports "
          "that cannot block the gate, anchors not looked for where they should not be, anchors "
          "citing lines looked for and anchors found only in their own repository, a renamed "
          "item told from a stolen number, `**Automated:**` lines read as lists and counted only in "
          "scenarios, and no guard fires on the shape it allows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
