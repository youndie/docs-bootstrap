#!/usr/bin/env python3
"""
A summary of the BDD scenarios: how many there are, how many are automated, where the tests live.

    python3 scripts/bdd_report.py                  # a table by document
    python3 scripts/bdd_report.py --json           # machine-readable
    python3 scripts/bdd_report.py --repos ..       # plus a check that the named tests exist

WHY. The feature template describes a mechanism: an automated scenario is marked with a line
`**Automated:** <repo> <TestName>`, and what is left manual is visible by the absence of that
line. A mechanism that exists and is never used is worth seeing as a number rather than as a
feeling - either there really are no automated tests, or there are and the link was never written
down, and both are worth knowing.

THIS IS A REPORT, NOT A GATE. Automation cannot be demanded by a documentation checker: a project
may legitimately accept its scenarios by running them by hand. The script blocks nothing - it
shows a figure and how it moves. A gate makes sense once the figure is non-zero and the team
decides not to let it fall.

The existence check is switched on by `--repos DIR`, a directory whose subdirectories are the
service repositories. Without the flag the script prints "not checked" - which is not the same as
"everything is in place".

The only non-zero exit comes from that check: a scenario naming a test that the repository does
not contain is a statement of fact that turned out to be false, and unlike a missing automation
line, it is not a matter of policy.
"""
import argparse
import json
import os
import re
import subprocess
import sys

# Scenarios do not live in features/ only: a screen document legitimately carries a few of its
# own. Looking at features/ alone gives a number that disagrees with docs_check.py, which counts
# across all layers - and two tools reporting different figures about the same thing are worse
# than one imprecise tool.
FOLDERS = ("research", "features", "screens", "api", "services")

SCENARIO = re.compile(r"^###\s+Scenario:\s*(.+?)\s*$", re.M)
# `**Automated:** <repository> <test>`, or `**Automated:** <test>` when the documentation covers a
# single repository. Backticks may wrap either part or neither. Two shapes of test reference are
# accepted because both are what people write:
#
#     **Automated:** catalog-api LoanRoutesTest
#     **Automated:** `tests/test_store.py::test_unacked_task_returns_to_the_front`
#
# The repository is optional and comes first, so the pattern only treats a leading token as one
# when a second token follows it. A path::test reference is a single token - the character class
# for a repository name has no slash in it - and therefore reads as the test, which is right.
# Requiring the pair was how a whole documentation tree could carry a link on every scenario and
# be reported as having none.
AUTOMATED = re.compile(
    r"\*\*Automated:\*\*\s*"
    r"(?:`?([A-Za-z0-9][A-Za-z0-9._-]*)`?[ \t]+)?"
    r"`?([A-Za-z0-9_][A-Za-z0-9_./:#-]*)`?"
)


def test_needle(reference):
    """The part of a test reference worth grepping for.

    `tests/test_store.py::test_x` is a locator, not a name: the file may be renamed while the test
    keeps its name, and the whole string occurs nowhere in the source. What does occur is the last
    segment after `::` or `#`, which is the name of the function or method.
    """
    for separator in ("::", "#"):
        if separator in reference:
            reference = reference.rsplit(separator, 1)[-1]
    return reference

IGNORED_DIRS = {".git", ".hg", ".svn", "node_modules", "build", "dist", "out", "target",
                "__pycache__", ".venv", "venv", ".tox", ".idea", ".gradle", ".next",
                "vendor", "coverage", ".mypy_cache", ".pytest_cache"}

# A file larger than this is not source and is not read: the point is to find a test name, and
# reading a bundle or a fixture dump to fail to find one is a waste.
MAX_GREP_BYTES = 2_000_000


def _utf8_stdout():
    """The output of this script is ASCII, but scenario names come out of the documents, and a
    project's documentation may be written in any language. A Windows console defaults to a legacy
    code page and dies on the first character outside it; CI on Linux never sees this, so the
    failure looks like a script that is broken on exactly one developer's machine."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def collect(root):
    out = []
    for folder in FOLDERS:
        path = os.path.join(root, folder)
        if not os.path.isdir(path):
            continue
        for name in sorted(os.listdir(path)):
            if not name.endswith(".md") or name == "README.md":
                continue
            with open(os.path.join(path, name), encoding="utf-8") as fh:
                text = fh.read()
            out.append({
                "document": name[:-3],
                "scenarios": SCENARIO.findall(text),
                "automated": [{"repo": r, "test": tn, "needle": test_needle(tn)}
                              for r, tn in AUTOMATED.findall(text)],
            })
    return out


def _contains(path, needle):
    """Is the name written anywhere in this file? Text only, and small files only."""
    try:
        if os.path.getsize(path) > MAX_GREP_BYTES:
            return False
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return needle in fh.read()
    except OSError:
        return False


def find_test(repo, name):
    """Looks for the named test in the repository. Returns (found, where).

    Deliberately crude - a search for the name, nothing more. An exact search would mean parsing
    the language; here it is enough to answer "that name does not occur in the repository at all",
    which is the common way this line rots.

    A git checkout is read with `git grep`, which is free and respects .gitignore. Anything else -
    a vendored copy, a subdirectory of a monorepo, the example tree shipped with this repository -
    is walked and read. The two paths must answer the same question: a directory that happens not
    to be a repository of its own is not a reason to declare a test missing, and a check on the
    file name alone would do exactly that for every test function that does not have a file to
    itself.

    MARKDOWN IS NEVER A TEST, and excluding it is what makes this check able to fail at all. When a
    project keeps its documentation in the same repository as its code - the layout this format
    recommends first - the name of the test occurs in the very document that names it. Searching
    everything found that document, reported the test as present, and went on reporting it as
    present after the test had been renamed away. The check answered a question about itself.
    """
    if os.path.isdir(os.path.join(repo, ".git")):
        try:
            hit = subprocess.run(["git", "grep", "-l", "-w", "-F", "-e", name,
                                  "--", ":(exclude)*.md"],
                                 cwd=repo, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None, None
        out = hit.stdout.strip()
        return (True, out.split("\n")[0]) if out else (False, None)

    # Not a git checkout: walk it. A file named after the test wins - a test class usually lives in
    # one - and otherwise the first file whose text mentions the name is reported.
    stem = name.split(".")[-1]
    inside = None
    for base, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
        for f in sorted(files):
            if f.endswith(".md"):
                continue                   # see the docstring: a document is not evidence
            full = os.path.join(base, f)
            rel = os.path.relpath(full, repo).replace(os.sep, "/")
            if os.path.splitext(f)[0] == stem:
                return True, rel
            if inside is None and _contains(full, stem):
                inside = rel
    return (True, inside) if inside else (False, None)


def verify(items, repos_root):
    for item in items:
        for a in item["automated"]:
            # No repository named means "somewhere in what was given", which is the normal case for
            # a project documented in its own repository.
            candidates = ([os.path.join(repos_root, a["repo"])] if a["repo"]
                          else [os.path.join(repos_root, n) for n in sorted(os.listdir(repos_root))
                                if os.path.isdir(os.path.join(repos_root, n))])
            candidates = [c for c in candidates if os.path.isdir(c)]
            if not candidates:
                a["found"] = None          # the repository is not here - nothing was checked
                continue
            a["found"], a["at"] = False, ""
            for candidate in candidates:
                found, at = find_test(candidate, a["needle"])
                if found:
                    a["found"], a["at"] = True, at
                    break
    return items


def main():
    ap = argparse.ArgumentParser(description="A summary of the BDD scenarios")
    ap.add_argument("--docs", metavar="PATH", default="docs",
                    help="the docs/ tree (default: docs, relative to the working directory)")
    ap.add_argument("--repos", metavar="DIR",
                    help="a directory whose subdirectories are the service repositories; "
                         "switches on the check that the named tests exist")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    # This script is a report, not a gate: demanding a share of automated scenarios is meaningless
    # while acceptance is run by hand, and a named test that cannot be found is usually a renamed
    # test in someone else's repository. So a miss is printed and exits 0 unless asked otherwise.
    ap.add_argument("--check", action="store_true",
                    help="exit 1 when a named test cannot be found (off by default)")
    args = ap.parse_args()

    _utf8_stdout()

    root = os.path.abspath(args.docs)

    # A missing tree is a mode, not a failure. Saying "nothing was checked" is not the same as
    # saying "nothing is wrong", so it is said out loud.
    if not os.path.isdir(root):
        print("no docs tree at {0} - nothing checked".format(root))
        return 0

    items = collect(root)
    if args.repos:
        items = verify(items, os.path.abspath(args.repos))

    total = sum(len(i["scenarios"]) for i in items)
    auto = sum(len(i["automated"]) for i in items)
    missing = [(i["document"], a) for i in items for a in i["automated"]
               if a.get("found") is False]

    if args.json:
        print(json.dumps({
            "total": total, "automated": auto,
            "documents": items,
            "tests_not_found": [dict(document=d, **a) for d, a in missing],
        }, ensure_ascii=False, indent=2))
        return 1 if (missing and args.check) else 0

    print("{0:34}{1:>10}{2:>10}".format("document", "scenarios", "automated"))
    print("-" * 54)
    for i in sorted(items, key=lambda x: -len(x["scenarios"])):
        if not i["scenarios"]:
            continue
        print("{0:34}{1:>10}{2:>10}".format(i["document"], len(i["scenarios"]),
                                            len(i["automated"])))
    print("-" * 54)
    pct = auto * 100 // total if total else 0
    print("{0:34}{1:>10}{2:>10}   ({3}%)".format("TOTAL", total, auto, pct))

    if missing:
        print("\nA test is named that the repository does not contain:")
        for d, a in missing:
            print("  {0}: {1} {2}".format(d, a["repo"], a["test"]))
    if not args.repos:
        print("\nThe existence of the tests was NOT checked: --repos was not given. "
              "That is not the same as \"they are all there\".")
    if auto == 0 and total:
        print("\nNone of the {0} scenarios carries an `**Automated:**` line. The field is "
              "described in the feature template - the mechanism exists, nothing uses it."
              .format(total))
    return 1 if (missing and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
