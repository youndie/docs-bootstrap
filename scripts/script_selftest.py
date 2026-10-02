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
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPTS)
TEMPLATE = os.path.join(REPO, "templates", "Makefile")


def run(script, args, cwd):
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, script)] + args,
        cwd=cwd, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr)


def make(args, cwd, makefile=None, extra_env=None):
    """The consumer's Makefile (templates/Makefile, or a project's Makefile built from it), run in a
    directory standing in for a project.

    The environment is scrubbed of anything a calling make or a calling CI would leak in: MAKEFLAGS
    carries the caller's command-line variables into every make below it, and a DOCS_BOOTSTRAP in
    the environment would answer the very question the pin cases ask.
    """
    leak = {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEFILES", "DOCS_BOOTSTRAP", "DOCS", "BACKLOG",
            "BACKLOG_FORM", "REPOS", "DOCS_BOOTSTRAP_GOALS"}
    env = {k: v for k, v in os.environ.items() if k not in leak}
    env.update(extra_env or {})
    result = subprocess.run(["make", "--no-print-directory", "-f", makefile or TEMPLATE] + args,
                            cwd=cwd, env=env, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr)


# curl as far as the template's fetch uses it. Every call is written down, and the download is a
# copy of a local tarball - or, when none is given, what curl does on a machine with no network.
STUB_CURL = """#!/bin/sh
out= url=
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out=$2; shift;;
    --retry) shift;;
    -*) ;;
    *) url=$1;;
  esac
  shift
done
echo "$url" >> "$SELFTEST_CURL_LOG"
if [ -n "$SELFTEST_TARBALL" ]; then exec cp "$SELFTEST_TARBALL" "$out"; fi
echo "curl: (7) Failed to connect: this test has no network" >&2
exit 7
"""


def no_network(root, tarball=None):
    """An environment in which nothing can be downloaded: curl is the stub above, and every proxy a
    real client would honour points at a closed port. Returns it and the file the stub logs to."""
    write(root, "bin/curl", STUB_CURL)
    os.chmod(os.path.join(root, "bin", "curl"), 0o755)
    log = os.path.join(root, "curl.log")
    write(root, "curl.log", "")
    closed = "http://127.0.0.1:9"
    env = {"PATH": os.path.join(root, "bin") + os.pathsep + os.environ.get("PATH", ""),
           "SELFTEST_CURL_LOG": log, "SELFTEST_TARBALL": tarball or "",
           "http_proxy": closed, "https_proxy": closed, "HTTP_PROXY": closed,
           "HTTPS_PROXY": closed, "ALL_PROXY": closed, "no_proxy": "", "NO_PROXY": ""}
    return env, log


def fetches(log):
    with open(log, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def release_tarball(root, ref):
    """What GitHub serves for REF, built from this checkout: one top directory holding the files a
    consumer's Makefile reads."""
    path = os.path.join(root, "src.tar.gz")
    skip = lambda info: None if "__pycache__" in info.name else info
    with tarfile.open(path, "w:gz") as tar:
        for name in ("check.mk", "scripts", ".claude-plugin", "templates"):
            tar.add(os.path.join(REPO, name), arcname="docs-bootstrap-{0}/{1}".format(ref, name),
                    filter=skip)
    return path


def checkmk_targets():
    """The targets check.mk declares - its .PHONY lines."""
    targets = []
    with open(os.path.join(REPO, "check.mk"), encoding="utf-8") as fh:
        for line in fh:
            if line.startswith(".PHONY:"):
                targets += line.split(":", 1)[1].split()
    return targets


def assigned(path, name):
    """The value a makefile assigns to NAME with `:=`, or None."""
    with open(path, encoding="utf-8") as fh:
        m = re.search(r"^" + re.escape(name) + r"\s*:=\s*(.*)$", fh.read(), re.M)
    return m.group(1).strip() if m else None


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
    global TEMPLATE
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--template", default=TEMPLATE,
                        help="run the Makefile cases against another consumer's Makefile - how a "
                             "case added for a fix is shown to fail on the template before it")
    TEMPLATE = os.path.abspath(parser.parse_args().template)
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

    # -- the consumer's Makefile: only a goal that runs the checks loads them -----------------------
    # A project adds goals of its own below the template's head, and make reads every included file -
    # fetching one that is missing - before it runs any goal. Through 0.3.4 check.mk was included
    # whatever the goal, so on a fresh clone `make chart`, `make` alone and `make -n` downloaded the
    # checks, and offline they failed. Here curl is a stub that writes every call down and has no
    # network, and every proxy points at a closed port.
    with open(TEMPLATE, encoding="utf-8") as fh:
        template = fh.read()
    own = "\nhello:\n\t@echo hello from the project\n\nci: check\n"
    url = "https://codeload.github.com/youndie/docs-bootstrap/tar.gz/v9.9.9"
    with tempfile.TemporaryDirectory() as project:
        write(project, ".github/workflows/check.yaml", uses.format("v9.9.9"))
        write(project, "Makefile", template + own)
        env, log = no_network(project)
        cache = os.path.join(project, ".docs-bootstrap")

        def offline(args):
            """Exit code, output, and the downloads this run attempted."""
            before = len(fetches(log))
            code, out = make(args, project, os.path.join(project, "Makefile"), env)
            tried = fetches(log)[before:]
            return code, out + "\ncurl was called for: {0}".format(tried or "nothing"), tried

        for args, what in ((["hello"], "a goal of the project's own"),
                           (["-n", "hello"], "make -n of a goal of the project's own"),
                           ([], "make with no goal (the default, help)")):
            code, out, tried = offline(args)
            expect_true("{0}, offline: wanted it to run without fetching the checks".format(what),
                        code == 0 and tried == [] and not os.path.exists(cache), out)

        # A goal of the project's own that leads to the checks without being listed stops, and says
        # which variable to add it to, rather than make's "No rule to make target docs-gate".
        code, out, tried = offline(["ci"])
        expect_true("an unlisted goal leading to docs-gate did not stop on DOCS_BOOTSTRAP_GOALS",
                    code != 0 and "DOCS_BOOTSTRAP_GOALS" in out and tried == [], out)

        # The positive control: the same goal, listed, loads the checks - exactly what every goal did
        # through 0.3.4 - and the stub sees the fetch, and fails it. Without this the cases above
        # prove nothing: a stub that is never consulted passes them too.
        code, out, tried = offline(["hello", "DOCS_BOOTSTRAP_GOALS=hello"])
        expect_true("a listed goal did not try to fetch the pinned ref through curl",
                    code != 0 and tried == [url], out)

        # The pin is read for the checks only: without one, a goal of the project's own still runs.
        os.remove(os.path.join(project, ".github", "workflows", "check.yaml"))
        code, out, tried = offline(["hello"])
        expect("a goal of the project's own with no pin", code, 0, out)
        code, out, tried = offline(["check"])
        expect_true("make check ran with no pin to read", code != 0 and "uses:" in out, out)

    # ... and every goal that runs the checks still loads them, the way it did: on a fresh clone it
    # fetches the pinned ref - under -n too, since make remakes an included file even when asked
    # only to print - and `make check` then checks with what it fetched. The download is a tarball
    # of this checkout, served by the stub.
    goals = ["check", "gate", "report", "fix"] + checkmk_targets()
    expect_true("check.mk declares a target outside the `docs-` prefix the template loads it for: "
                "{0}".format(goals[4:]), goals[4:] and all(t.startswith("docs-") for t in goals[4:]),
                "")
    listed = "DOCS_BOOTSTRAP_GOALS := check gate report fix\n"
    expect_true("the template does not list check gate report fix in DOCS_BOOTSTRAP_GOALS",
                listed in template, "")
    with tempfile.TemporaryDirectory() as root:
        project = os.path.join(root, "project")
        shutil.copytree(os.path.join(REPO, "example"), project)
        write(project, ".github/workflows/check.yaml", uses.format("v9.9.9"))
        write(project, "Makefile",
              template.replace(listed, listed + "DOCS_BOOTSTRAP_GOALS += ci\n") + own)
        env, log = no_network(root, release_tarball(root, "v9.9.9"))
        cache = os.path.join(project, ".docs-bootstrap")

        def online(args, makefile="Makefile", fresh=True):
            """Exit code, output, and the downloads this run attempted - on a fresh clone unless
            told otherwise."""
            if fresh:
                shutil.rmtree(cache, ignore_errors=True)
            before = len(fetches(log))
            code, out = make(args, project, os.path.join(project, makefile), env)
            tried = fetches(log)[before:]
            return code, out + "\ncurl was called for: {0}".format(tried or "nothing"), tried

        for goal in goals + ["ci"]:
            code, out, tried = online(["-n", goal, "BASE=origin/main", "REPOS=."])
            expect_true("make -n {0} on a fresh clone did not fetch the pinned ref".format(goal),
                        tried == [url], out)

        # A project whose default goal is the gate: `make` alone is a goal that runs the checks.
        write(project, "Makefile.default",
              template.replace(".DEFAULT_GOAL := help", ".DEFAULT_GOAL := check") + own)
        code, out, tried = online(["-n"], "Makefile.default")
        expect_true("make with no goal, the default goal being check, did not fetch the pinned ref",
                    tried == [url], out)

        code, out, tried = online(["check", "REPOS=."])
        expect_true("make check on a fresh clone did not fetch the pinned ref and pass on it, "
                    "without a warning about the template's revision",
                    code == 0 and tried == [url]
                    and os.path.isfile(os.path.join(cache, "v9.9.9", "check.mk"))
                    and "from .docs-bootstrap/v9.9.9" in out and "expects revision" not in out, out)

        # Fetched once: the next run reads the copy.
        code, out, tried = online(["gate"], fresh=False)
        expect_true("make gate fetched again over a fetched copy", code == 0 and tried == [], out)

    # The revision the template states is the one check.mk expects; otherwise every project copying
    # the current template would be told on every run that its Makefile is out of date.
    shim = assigned(TEMPLATE, "DOCS_BOOTSTRAP_SHIM")
    current = assigned(os.path.join(REPO, "check.mk"), "DOCS_BOOTSTRAP_SHIM_CURRENT")
    expect_true("the template is revision {0} and check.mk expects {1}".format(shim, current),
                shim is not None and shim == current, "")

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

    # An address (SPEC 4.1) is a path into the code. Through 0.3.9 it was not one to docs_check: a
    # service document whose code lives entirely in another repository, with every path written as
    # `owner/repo@<sha>!/...` as SPEC 4 asks, failed with no-code-anchor. An address at a ref that
    # moves counts as well - code_anchors lists it apart, without failing --check, and docs_check must
    # not make that list blocking by another road. An address nobody can fetch does not count, and
    # neither does a repository named with no path inside it. Each document carries one candidate
    # and nothing else, and code_anchors reads the same tree, so the two scripts are held to one
    # answer on what an address is.
    with tempfile.TemporaryDirectory() as tree:
        cases = {
            "youndie/petich@bfff0b6!/petich-chronik/src/commonMain/kotlin/": True,
            "kubernetes/website@v1.31!/content/en/docs/pod-lifecycle.md": True,
            "io.github.smyrgeorge:sqlx4k:1.13.0!/commonMain/.../ConnectionPool.kt": True,
            "ktor-server-core-3.5.2.klib!/commonMain/io/ktor/server/engine/ShutdownHook.kt:40-52": True,
            "youndie/petich!/petich-core/src/commonMain/kotlin/Petich.kt": True,
            "youndie/petich@main!/petich-core/src/commonMain/kotlin/Petich.kt": True,
            "com.example:lib:1.0-SNAPSHOT!/src/X.kt": True,
            "Ktor!/commonMain/io/ktor/server/engine/ShutdownHook.kt": False,
            "<artefact>!/<path>": False,
            "youndie/petich@bfff0b6": False,
        }
        write(tree, "app/src/x.py", "x = 1\n")    # a tree for code_anchors to stand on
        names = {}
        for i, address in enumerate(cases):
            names["feature-{0}".format(i)] = address
            write(tree, "docs/features/feature-{0}.md".format(i), doc("active", address).replace(
                "id: feature-x", "id: feature-{0}".format(i)))
        errors, out = no_anchor_errors(tree)
        refused = {os.path.basename(e["file"])[:-3] for e in errors or []}
        counted = dict((names[n], n not in refused) for n in names)
        expect_true("docs_check did not take an address with a fetchable left side, pinned or not, "
                    "for a path into the code, and only that: {0}".format(sorted(
                        (a, counted[a], want) for a, want in cases.items() if counted[a] != want)),
                    errors is not None and counted == cases, out)
        expect_true("docs_check did not say which address it could not count",
                    any("'Ktor'" in e["message"] for e in errors or []), out)
        code, report, out = anchors(tree, ".")
        resolved = dict((a["path"], a["status"]) for a in (report or {}).get("anchors", []))
        disagree = sorted(a for a, want in cases.items()
                          if "!/" in a and (resolved.get(a) in ("external", "unpinned")) != want)
        expect_true("docs_check and code_anchors disagree on what an address is: {0}".format(disagree),
                    report is not None and not disagree, out)

    # The two copies of the pattern for a fetchable left side: each script runs on its own, so the
    # pattern is not imported, and two copies drift unless something compares them.
    def pattern(script, name):
        text = open(os.path.join(SCRIPTS, script), encoding="utf-8").read()
        m = re.search(r"^{0} = re\.compile\(\n?(.*?)\n?\)\n".format(name), text, re.M | re.S)
        return re.sub(r"\s*#[^\n]*", "", m.group(1)).split() if m else None

    expect_true("FETCHABLE in docs_check.py is not the one in code_anchors.py",
                pattern("docs_check.py", "FETCHABLE") is not None
                and pattern("docs_check.py", "FETCHABLE") == pattern("code_anchors.py", "FETCHABLE"),
                "docs_check:    {0}\ncode_anchors: {1}".format(
                    pattern("docs_check.py", "FETCHABLE"), pattern("code_anchors.py", "FETCHABLE")))

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

    # `./x` is `x`, written from the root of the anchor's own repository. Through 0.3.5 the `.` was
    # taken for the name of a repository: none is called that, so a file that is plainly there was
    # reported missing - beside the neighbours and under `--repos .` alike. A path that climbs out
    # with `../` names no tree at all and is missing, saying why; bare dots in prose are no path.
    with tempfile.TemporaryDirectory() as root:
        repos = os.path.join(root, "repos")
        write(repos, "own/src/live.py", "x = 1\n")
        write(repos, "other/src/live.py", "x = 1\n")
        write(repos, "own/docs/features/feature-x.md", doc(
            "active", "./src/live.py",
            "\n`./src/gone.py`, `../src/live.py`, `../other/src/live.py`, and the depth of `../`.\n"))
        code, report, out = anchors(os.path.join(repos, "own"), repos)
        status = dict((a["path"], a["status"]) for a in (report or {}).get("anchors", []))
        why = dict((a["path"], a.get("why", "")) for a in (report or {}).get("anchors", []))
        expect_true("code_anchors did not read `./x` as `x` in the anchor's own repository, or "
                    "resolved a path that climbs out with `../` (wanted ./src/live.py found, "
                    "./src/gone.py missing, both `../` paths missing saying so, bare `../` skipped)",
                    status == {"./src/live.py": "found", "./src/gone.py": "missing",
                               "../src/live.py": "missing", "../other/src/live.py": "missing",
                               "../": "skipped"}
                    and "`../`" in why.get("../src/live.py", "")
                    and "`../`" in why.get("../other/src/live.py", ""), out)

    with tempfile.TemporaryDirectory() as tree:
        write(tree, "app/src/live.py", "x = 1\n")
        write(tree, "docs/features/feature-x.md", doc("active", "./app/src/live.py"))
        code, report, out = anchors(tree, ".")
        expect_true("code_anchors --repos . reported `./app/src/live.py` as missing",
                    report is not None and missing_paths(report) == [] and report["found"] == 1, out)

    # -- addresses: the ref is what was read (SPEC 4.1) -----------------------------------------------
    # `owner/repo@ref` passed on its shape alone, so `@<a branch that only lives in somebody's clone>`
    # was as good as a commit. A ref has to look like a commit or a version tag; anything else, and no
    # ref at all, is listed as moving - in a section of its own, not as rot, and not failing --check,
    # because consumers carry such addresses today. The controls: the pinned forms stay where they
    # were, and a left side nobody can fetch is still missing.
    addresses = {
        "o/r@0123abc!/src/a.kt": "external", "o/r@v1.31!/src/a.kt": "external",
        "o/r@4.3.1!/src/a.kt": "external", "o/r@7.6.0.RELEASE!/src/a.kt": "external",
        "o/r@worktree-local-only!/src/a.kt": "unpinned", "o/r@main!/src/a.kt": "unpinned",
        "o/r@feat/memory-limit!/src/a.kt": "unpinned", "o/r!/src/a.kt": "unpinned",
        "Ktor!/src/a.kt": "missing",
    }
    with tempfile.TemporaryDirectory() as tree:
        write(tree, "app/src/live.py", "x = 1\n")
        body = "\n" + "\n".join("* `{0}`".format(a) for a in addresses if a != "Ktor!/src/a.kt") + "\n"
        write(tree, "docs/research/research-x.md", doc("active", "app/src/live.py", body))
        code, report, out = anchors(tree, ".", "--check")
        status = dict((a["path"], a["status"]) for a in (report or {}).get("anchors", [])
                      if "!/" in a["path"])
        wanted = dict((a, s) for a, s in addresses.items() if a != "Ktor!/src/a.kt")
        expect_true("code_anchors did not tell an address at a commit or a version tag from one at a "
                    "branch or at no ref", status == wanted, out)
        expect("code_anchors --check with addresses at a moving ref and nothing missing", code, 0, out)
        moving = [a for a in (report or {}).get("anchors", []) if a["status"] == "unpinned"]
        expect_true("code_anchors did not say which ref moves and what to write instead",
                    report is not None and report.get("unpinned") == 4
                    and all("<sha>" in a.get("why", "") for a in moving)
                    and any("worktree-local-only" in a.get("why", "") for a in moving), out)
        code, out = run("code_anchors.py", ["--docs", os.path.join(tree, "docs"), "--repos", "."], tree)
        expect_true("code_anchors did not list the addresses at a moving ref in a section of their own",
                    code == 0 and "AT A REF THAT MOVES" in out
                    and "o/r@main!/src/a.kt" in out.split("AT A REF THAT MOVES", 1)[-1], out)

        write(tree, "docs/research/research-x.md",
              doc("active", "app/src/live.py", body + "* `Ktor!/src/a.kt`\n"))
        code, report, out = anchors(tree, ".", "--check")
        expect_true("code_anchors --check passed an address whose left side nobody can fetch",
                    code == 1 and missing_paths(report) == ["Ktor!/src/a.kt"], out)

    # The version is what was read, too. Through 0.3.6 any coordinate and any packaged file passed as
    # pinned, a snapshot and a jar with no version in its name among them. They are listed with the
    # moving refs - and a version in a file name is read loosely, so that the forms people actually
    # ship (`-r09`, `-v2`, `Name.13.0.3`, a build number `0.8.0.14`) stay pinned. The controls on the
    # other side: a number glued to a word (`linuxx64`, `jdk18on`) and `x86_64` are not versions, and
    # a tool called "snapshot" is not a snapshot.
    artefacts = {
        "x:y:1.2!/a.kt": "external", "io.github.youndie:kontainer:0.1.0.14!/a.kt": "external",
        "org.springframework:spring-core:5.3.9.RELEASE!/a.kt": "external",
        "x:y:1.2-SNAPSHOT!/a.kt": "unpinned", "x:y:1.+!/a.kt": "unpinned",
        "x:y:latest.release!/a.kt": "unpinned", "x:y:+!/a.kt": "unpinned",
        "x.jar!/a.kt": "unpinned", "x-1.2-SNAPSHOT.jar!/a.kt": "unpinned",
        "x-1.2-SNAPSHOT-sources.jar!/a.kt": "unpinned", "kotlin-native-2.4.20-SNAPSHOT!/a.kt": "unpinned",
        "kotlinx-coroutines-core-linuxx64.klib!/a.kt": "unpinned", "bcprov-jdk18on.jar!/a.kt": "unpinned",
        "lib-linux-x86_64.zip!/a.kt": "unpinned",
        "ktor-server-core-linuxx64-3.6.0-sources.jar!/a.kt": "external",
        "guava-r09.jar!/a.kt": "external", "foo-v2.jar!/a.kt": "external",
        "Newtonsoft.Json.13.0.3.nupkg!/a.kt": "external", "kompot-spec-0.8.0.14.jar!/a.kt": "external",
        "foo-1.0rc1.jar!/a.kt": "external", "lib-linux-x86_64-1.0.zip!/a.kt": "external",
        "snapshot-tool-1.0.jar!/a.kt": "external", "kotlin-native-2.4.20!/a.kt": "external",
        "librdkafka-2.13.0.tar.gz!/a.kt": "external", "x:y:0.1.0.<run>!/a.kt": "skipped",
    }
    with tempfile.TemporaryDirectory() as tree:
        write(tree, "app/src/live.py", "x = 1\n")
        body = "\n" + "\n".join("* `{0}`".format(a) for a in artefacts) + "\n"
        write(tree, "docs/research/research-x.md", doc("active", "app/src/live.py", body))
        code, report, out = anchors(tree, ".", "--check")
        status = dict((a["path"], a["status"]) for a in (report or {}).get("anchors", [])
                      if "!/" in a["path"])
        expect_true("code_anchors did not tell a released coordinate or a versioned file from a "
                    "snapshot, a dynamic version or a file with no version in its name: {0}".format(
                        sorted((a, status.get(a), s) for a, s in artefacts.items()
                               if status.get(a) != s)), status == artefacts, out)
        expect("code_anchors --check with snapshots and unversioned files and nothing missing",
               code, 0, out)
        why = dict((a["path"], a.get("why", "")) for a in (report or {}).get("anchors", []))
        expect_true("code_anchors did not say why a snapshot, a dynamic version or an unversioned "
                    "file moves, and what to cite instead",
                    "snapshot" in why.get("x:y:1.2-SNAPSHOT!/a.kt", "")
                    and "x:y:<version>" in why.get("x:y:1.2-SNAPSHOT!/a.kt", "")
                    and "dynamic" in why.get("x:y:1.+!/a.kt", "")
                    and "no version" in why.get("x.jar!/a.kt", "")
                    and "snapshot" in why.get("x-1.2-SNAPSHOT.jar!/a.kt", ""), out)

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

    # A line that names a FILE - a conformance script, a harness's Main.kt - is checked for the file
    # (SPEC 3.1, 4). Through 0.3.6 the path was grepped for as text in the other files, so a script
    # nobody else mentions was "not contained" while it sat at that very path, and a deleted one
    # still mentioned in a Makefile was found. Looked for as an anchor is: in its own repository,
    # `./` and `.../` as SPEC 4 reads them, `../` leaving it, a cited range inside the file. A path
    # the anchors check would not take for one (`samples/oracle`) is still searched for as text, and a
    # named test is still looked for by its name.
    with tempfile.TemporaryDirectory() as root:
        repos = os.path.join(root, "repos")
        own, other = os.path.join(repos, "own"), os.path.join(repos, "other")
        write(own, "conformance/scripts/hashes.redis", "HSET k f v\n")
        write(own, "harness/src/Main.kt", "fun main() {\n    smoke()\n}\n")
        write(own, "samples/oracle/run.sh", "# runs samples/oracle\n")
        write(own, "src/LoanTest.kt", "class LoanTest {\n  fun `a loan is refused`() {}\n}\n")
        write(own, "Makefile", "conformance:\n\tredis-cli < conformance/scripts/gone.redis\n")
        write(other, "scripts/only-other.sh", "exit 0\n")
        files = {
            "conformance/scripts/hashes.redis": True, "./conformance/scripts/hashes.redis": True,
            "harness/src/Main.kt": True, ".../src/Main.kt": True, "harness/src/Main.kt:2-3": True,
            "other scripts/only-other.sh": True,
            "conformance/scripts/gone.redis": False, "harness/src/Main.kt:40-52": False,
            "scripts/only-other.sh": False, "../other/scripts/only-other.sh": False,
        }
        body = "\n## 5. Scenarios\n" + "".join(
            "\n### Scenario: {0}\n* **Automated:** `{1}`\n".format(i, ref)
            for i, ref in enumerate(list(files) + ["samples/oracle",
                                                   "src/LoanTest.kt::a loan is refused"]))
        write(own, "docs/features/feature-x.md", doc("active", "src/LoanTest.kt", body))
        for repo in (own, other):
            git(repo, "init", "-q")
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", "base")
        report, out = bdd(own, repos)
        refs = dict((" ".join(x for x in (r["repo"], r["test"]) if x), r)
                    for d in (report or {}).get("documents", []) for r in d.get("references", []))
        found = dict((ref, refs.get(ref, {}).get("found")) for ref in files)
        expect_true("bdd_report did not check a path on an `**Automated:**` line for the file, in its "
                    "own repository, as SPEC 4 resolves an anchor: {0}".format(
                        sorted((ref, found[ref], want) for ref, want in files.items()
                               if found[ref] != want)), found == files, out)
        expect_true("bdd_report did not take every path on an `**Automated:**` line for one",
                    all(refs.get(ref, {}).get("path") for ref in files), out)
        expect_true("bdd_report did not say why a path that climbs out with `../` is not found",
                    "`../`" in refs.get("../other/scripts/only-other.sh", {}).get("why", ""), out)
        expect_true("bdd_report checked a path with no extension as a file instead of searching for "
                    "it, or a named test for a file, or found neither",
                    refs.get("samples/oracle", {}).get("found") is True
                    and not refs.get("samples/oracle", {}).get("path")
                    and refs.get("src/LoanTest.kt::a loan is refused", {}).get("found") is True
                    and not refs.get("src/LoanTest.kt::a loan is refused", {}).get("path"), out)
        code, out = run("bdd_report.py", ["--docs", os.path.join(own, "docs"), "--repos", repos,
                                          "--check"], own)
        missing_section = out.split("A file is named that is not in its repository", 1)[-1]
        expect_true("bdd_report --check passed a file that is not there, or did not list it apart "
                    "from the tests", code == 1 and "conformance/scripts/gone.redis" in missing_section
                    and "conformance/scripts/hashes.redis" not in missing_section, out)

    # The same under `--repos .`, where the trees are the documented repository's own directories.
    with tempfile.TemporaryDirectory() as tree:
        write(tree, "ci/b-09/run.sh", "exit 0\n")
        write(tree, "docs/features/feature-x.md", doc(
            "active", "ci/b-09/run.sh", "\n### Scenario: a\n* **Automated:** `ci/b-09/run.sh`\n"
                                        "\n### Scenario: b\n* **Automated:** `ci/b-99/run.sh`\n"))
        report, out = bdd(tree, ".")
        found = [(r["test"], r.get("found")) for d in (report or {}).get("documents", [])
                 for r in d.get("references", [])]
        expect_true("bdd_report --repos . did not check a path for the file",
                    found == [("ci/b-09/run.sh", True), ("ci/b-99/run.sh", False)], out)

    # A FILE NAME WITH NO DIRECTORY IS A FILE, AND A NAME IS ONE NAME, WITH GIT OR WITHOUT IT. Through
    # 0.3.7 a git checkout grepped `negative-control.sh` as text (a script nobody mentions: missing;
    # a deleted one a Makefile still mentions: found) while a walked tree looked for what followed the
    # last dot - `kafka-consumer-groups.sh` was found as `sh` - as a substring (`Loan` in `LoanTest`),
    # took a file named after a test for the test, and under `--repos .` walked `.git`, whose logs
    # hold a commit subject naming a test long gone. One tree, read both ways, has to give one answer.
    with tempfile.TemporaryDirectory() as root:
        own = os.path.join(root, "own")
        write(own, "samples/oracle/negative-control.sh", "#!/bin/sh\nexit 1\n")
        write(own, "src/LoanTest.kt", "class LoanTest {\n    fun renew() {}\n}\n")
        write(own, "src/RenamedTest.kt", "class Other\n")
        write(own, "samples/Makefile", "# GoneTest.kt was folded into LoanTest\n")
        wanted = {
            "negative-control.sh": True, "LoanTest.kt": True, "LoanTest.kt:2-3": True,
            "LoanTest": True, "LoanTest.renew": True,
            "kafka-consumer-groups.sh": False, "GoneTest.kt": False, "LoanTest.kt:40-52": False,
            "Loan": False, "RenamedTest": False, "StaleTest": False, "billing.renew": False,
        }
        body = "\n## 5. Scenarios\n" + "".join(
            "\n### Scenario: {0}\n* **Automated:** `{1}`\n".format(i, ref)
            for i, ref in enumerate(wanted))
        body += ("\n### Scenario: prose\n* **Automated:** `LoanTest`, read against "
                 "`kafka-consumer-groups.sh` by `samples/oracle/negative-control.sh`\n")
        write(own, "docs/features/feature-x.md", doc("active", "src/LoanTest.kt", body))
        git(own, "init", "-q")
        git(own, "add", "-A")
        git(own, "commit", "-q", "-m", "drop StaleTest")
        for mode, repos in (("a git checkout", root), ("a walked tree (--repos .)", ".")):
            report, out = bdd(own, repos)
            refs = [r for d in (report or {}).get("documents", []) for r in d.get("references", [])]
            found = dict((r["test"], r.get("found")) for r in refs[:len(wanted)])
            expect_true("bdd_report in {0} did not answer for each name as `git grep -w` and for each "
                        "file name as a file: {1}".format(mode, sorted(
                            (ref, found.get(ref), want) for ref, want in wanted.items()
                            if found.get(ref) != want)), found == wanted, out)
            files = sorted(r["test"] for r in refs[:len(wanted)] if r.get("path"))
            expect_true("bdd_report in {0} did not take exactly the file names for files, or took "
                        "`LoanTest.renew` for one".format(mode),
                        files == ["GoneTest.kt", "LoanTest.kt", "LoanTest.kt:2-3", "LoanTest.kt:40-52",
                                  "kafka-consumer-groups.sh", "negative-control.sh"], out)
            needle = dict((r["test"], r["needle"]) for r in refs)
            expect_true("bdd_report in {0} looked for `LoanTest.renew` by another needle than "
                        "`renew`".format(mode), needle.get("LoanTest.renew") == "renew", out)
            expect_true("bdd_report in {0} read a file name in prose after the first test as a "
                        "second test".format(mode),
                        [r["test"] for r in refs[len(wanted):]] == ["LoanTest"], out)

    # A file name after a repository or a module is a file of that name inside it - not at its root,
    # and not in a sibling. Without one, it is in the documentation's own repository (SPEC 4).
    with tempfile.TemporaryDirectory() as root:
        repos = os.path.join(root, "repos")
        own, other = os.path.join(repos, "own"), os.path.join(repos, "other")
        write(own, "samples/oracle/negative-control.sh", "exit 1\n")
        write(own, "src/LoanTest.kt", "class LoanTest\n")
        write(other, "scripts/only-other.sh", "exit 0\n")
        wanted = {
            "own negative-control.sh": True, "samples negative-control.sh": True,
            "other only-other.sh": True,
            "samples LoanTest.kt": False, "other negative-control.sh": False,
            "only-other.sh": False, "own LoanTest.kt:40-52": False,
        }
        body = "\n## 5. Scenarios\n" + "".join(
            "\n### Scenario: {0}\n* **Automated:** `{1}`\n".format(i, ref)
            for i, ref in enumerate(wanted))
        write(own, "docs/features/feature-x.md", doc("active", "src/LoanTest.kt", body))
        for repo in (own, other):
            git(repo, "init", "-q")
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", "base")
        report, out = bdd(own, repos)
        refs = dict((" ".join(x for x in (r["repo"], r["test"]) if x), r)
                    for d in (report or {}).get("documents", []) for r in d.get("references", []))
        found = dict((ref, refs.get(ref, {}).get("found")) for ref in wanted)
        expect_true("bdd_report did not look for a file name inside the repository or module named "
                    "before it, or in its own repository when none is: {0}".format(sorted(
                        (ref, found[ref], want) for ref, want in wanted.items() if found[ref] != want)),
                    found == wanted, out)
        expect_true("bdd_report did not say where a file name it could not find in its module is",
                    "own/src/LoanTest.kt" in refs.get("samples LoanTest.kt", {}).get("why", ""), out)

    if failures:
        sys.stderr.write("\n\n".join(failures) + "\n")
        return 1
    print("script_selftest: every case passed - absent subjects refused by the scripts and by the "
          "Makefile, the pin read once and never guessed, the checks loaded and fetched for the goals that run "
          "them and for no other, uncounted scenarios reported, a shipped "
          "change without a version bump and a template pinning another release refused, reports "
          "that cannot block the gate, anchors not looked for where they should not be, anchors "
          "citing lines looked for and anchors found only in their own repository, `./` read as "
          "the root and `../` as leaving it, addresses at a branch or at no ref, snapshots, dynamic "
          "versions and unversioned files told from pinned ones without failing --check, an "
          "address with a fetchable left side taken for a path into the code, a "
          "renamed item told from a stolen number, `**Automated:**` lines read as lists and "
          "counted only in scenarios, a line naming a file - by its path or by its name alone - checked "
          "for the file, a test name looked for the same way with git and without, and no guard "
          "fires on the shape it allows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
