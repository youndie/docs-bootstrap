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
"everything is in place". A test whose repository or module cannot be found under DIR is not looked
for, and is listed as such: not looked for is not found.

The only non-zero exit comes from that check: a scenario naming a test that the repository does
not contain is a statement of fact that turned out to be false, and unlike a missing automation
line, it is not a matter of policy.

A LINE THAT NAMES A FILE IS CHECKED FOR THE FILE. Not every automated check is a test function: a
conformance script, a `run.sh` that drives the binary, the `Main.kt` of a harness. Such a line names
a path and nothing after `::` or `#`, and through 0.3.6 that path was grepped for as text in the
other files of the repository - so a script nobody else mentions was reported as one the repository
does not contain, while it sat at exactly that path. A path is now resolved the way code_anchors.py
resolves an anchor (SPEC 4): `./x` is `x`, `../` leaves the repository, `.../x` is abbreviated, a
suffix fits, a cited line range has to be inside the file, and the file has to be in its own
repository. A path the anchors check would skip as not looking like one - `samples/oracle`, with no
extension and no source-tree segment - is still searched for as text, as before.

A FILE NAME WITH NO DIRECTORY IS A FILE TOO. `negative-control.sh` and `LoanRoutesTest.kt` name files
as surely as `samples/oracle/negative-control.sh` does, and through 0.3.7 they were searched for as
text: in a git checkout as the whole string, which a script nobody else mentions does not contain;
in a walked directory as what followed the last dot, so `kafka-consumer-groups.sh` became `sh` and
was "found" in the first file holding those two letters. Such a name is now looked for as a file of
that name in its repository (SPEC 3.1, 4). It is told from `TestClass.member` by its extension -
one of FILE_EXTENSIONS - so `LoanTest.renew` stays a class and its member however short the
member's name is.

THE SAME QUESTION WITH OR WITHOUT GIT. A name is looked for as `git grep -w -F` looks for it - the
whole name, as a word, in a file that is not markdown - in a git checkout and in a directory that is
walked alike, and a walk under `--repos .` does not start in `.git` or in a build directory.
"""
import argparse
import json
import os
import re
import subprocess
import sys

import code_anchors        # beside this file; a path on an `**Automated:**` line is an anchor

# Scenarios do not live in features/ only: a screen document legitimately carries a few of its
# own. Looking at features/ alone gives a number that disagrees with docs_check.py, which counts
# across all layers - and two tools reporting different figures about the same thing are worse
# than one imprecise tool.
FOLDERS = ("research", "features", "screens", "api", "services")

# A scenario is its `### Scenario:` heading (SPEC 3.1). Scenarios written any other way - several in
# one gherkin block, a heading in another language - are counted as nothing here, and this report
# cannot tell that 0 from a document that has none. docs_check.py can, and warns
# (`uncounted-scenarios`); it runs in the gate, which is where a warning is read.
SCENARIO = re.compile(r"^###\s+Scenario:\s*(.+?)\s*$", re.M)
# The `**Automated:**` line (SPEC 3.1), taken whole: one line inside a scenario is one automated
# scenario, whatever it names. What it names is read by references() below. The marker quoted in
# backticks is prose ABOUT the line - "a scenario with an `**Automated:**` line names its test" -
# and read as one, it put a note "outside any scenario, not counted" on four documents that had
# nothing outside their scenarios.
AUTOMATED = re.compile(r"(?<!`)\*\*Automated:\*\*(.*)$")
# A heading that opens a section: `#` to `###`. A `####` under a scenario stays inside it.
SECTION = re.compile(r"^(#{1,3})\s")
FENCE = re.compile(r"^\s*(```|~~~)")

# One reference: `<repository> <test>`, or `<test>` when the documentation covers a single
# repository. Two shapes of test are accepted because both are what people write:
#
#     **Automated:** catalog-api LoanRoutesTest
#     **Automated:** `tests/test_store.py::test_unacked_task_returns_to_the_front`
#
# The repository is optional and comes first, so a leading token is one only when a second token
# follows it; a single token is always the test. Requiring the pair was how a whole documentation
# tree could carry a link on every scenario and be reported as having none. Backticks may wrap
# either part, both, or neither. The repository may be a MODULE PATH - `feature/roaming-server-data`
# - because a repository of many modules is the ordinary shape, and verify() looks a module up
# inside each checkout as well as beside them.
#
# A LOCATOR - `path::name`, `path#name`, or `TestClass.name` - names the test after the separator,
# and that name may have spaces in it, because Kotlin and Spock test names are sentences:
# `CommandsTest.kt::TTL is -2 for a missing key`, `KoreKoinTest.routes resolve from the container`.
# Read as one token, the first was the test `CommandsTest.kt::TTL` with the needle `TTL`, and the
# second was grepped for as `KoreKoinTest.routes`, which no source file contains.
_REPO = r"([A-Za-z0-9][A-Za-z0-9._/-]*)"
_TEST = r"((?:\.{1,3}/)*[A-Za-z0-9_][A-Za-z0-9_./:#-]*)"
_LOCATOR = r"([^\s`:#]+(?:::|#)[^`]*[^`\s]|[A-Z][A-Za-z0-9_]*\.[^`]*[^`\s])"
_LEAD = r"^`?(?:" + _REPO + r"`?[ \t]+`?)?"
REFERENCE = re.compile(_LEAD + _TEST)                     # one at the start of a text
WHOLE = re.compile(_LEAD + _TEST + r"`?$")                # a text that is one and nothing else
LOCATOR = re.compile(_LEAD + _LOCATOR + r"`?$")
# `TestClass.member`: the member is the needle. `FooTest.kt` is a file, not a member called `kt`.
MEMBER = re.compile(r"^[A-Z][A-Za-z0-9_]*\.(.+)$")
# A FILE NAME with no directory, and optionally a line or a range: `negative-control.sh`,
# `LoanRoutesTest.kt:40-52`. What makes it a file and not `TestClass.member` is the extension, and
# only one from this list counts: a check written as "any short lowercase tail" took
# `LoanTest.renew` for a file and grepped for the whole string, which no source contains. The list
# is what a test, a script or a check's data is called, and it is narrow on purpose: an extension a
# member is plausibly named (`json`, `patch`, `html`, `env`, `h`) is left out. The two mistakes do not
# cost the same - a member read as a file is reported missing, while a file read as a name is
# searched for as text, which is what happened to every file name through 0.3.7. `.md` is not on
# it either: a document is never a test (see find_test).
FILE_EXTENSIONS = frozenset("""
    kt kts java scala groovy gradle clj cljs cljc
    py pyi rb php pl lua tcl jl ex exs erl hs ml dart nim zig cs vb
    go rs c cc cpp cxx mm swift
    js mjs cjs ts mts cts jsx tsx vue svelte
    sh bash zsh fish ksh ps1 psm1 bat bats
    sql redis cql cypher feature robot jmx
    yaml yml toml jsonl ndjson txt csv tsv
    mk cmake bzl
""".split())
BARE_FILE = re.compile(r"^([^\s:#/`]+\.([A-Za-z0-9]+))(?::(\d+)(?:-(\d+))?)?$")
# A path to a file or a directory, with no `::` or `#`: next to a reference, where it lives or what
# it produced - `test_renewal_limit_reached` in `tests/test_loan_rules.py`, a report in
# `bench/reports/b-16/`. Not a test.
PATH = re.compile(r"^[^\s:#]*/(?:[^\s/:#]+\.[A-Za-z0-9]{1,6}|)$")
# A reference that IS a path - a script, a harness's `Main.kt` - rather than a test inside one: a slash,
# no space, nothing after `::` or `#`, and optionally a line or a range. Checked for the file, not
# grepped for as text - see the module docstring. `./`, `../` and `.../` in front are read as SPEC 4
# reads them, which is why the test above may start with them.
PATH_REFERENCE = re.compile(r"^([^\s:#]*/[^\s:#]*?)(?::(\d+)(?:-(\d+))?)?$")
# Commentary after the list: a dash or a semicolon outside backticks ends what is read, and a
# parenthesis outside backticks is an aside - `SagaTimerSinkTest` (in the engine's repository, on a
# branch) names one test, not three.
COMMENTARY = re.compile(r"\s[\u2014\u2013-]\s|;")


def test_needle(reference):
    """The part of a test reference worth grepping for.

    `tests/test_store.py::test_x` is a locator, not a name: the file may be renamed while the test
    keeps its name, and the whole string occurs nowhere in the source. What does occur is the last
    segment after `::` or `#`, which is the name of the function or method - and, for
    `LoanRoutesTest.renewalIsRefused`, what follows the class.
    """
    for separator in ("::", "#"):
        if separator in reference:
            return reference.rsplit(separator, 1)[-1].strip()
    member = MEMBER.match(reference)
    if member and not bare_file(reference):
        return member.group(1).strip()
    return reference.strip()


def bare_file(reference):
    """The BARE_FILE match if the reference is a file name with no directory, else None."""
    m = BARE_FILE.match(reference)
    return m if m and m.group(2).lower() in FILE_EXTENSIONS else None


def file_of(reference):
    """(path, first line, last line, bare) if the reference names a file, else None. One reading for
    both shapes, so that what is a file and what is a name is decided once, before anything is looked
    for - and the same whether the repository is a git checkout or is walked."""
    m = PATH_REFERENCE.match(reference)
    if m:
        return m.group(1), m.group(2), m.group(3), False
    m = bare_file(reference)
    if m:
        return m.group(1), m.group(3), m.group(4), True
    return None


def _outside_backticks(text, pattern):
    """Where `pattern` first matches outside backticks, or None."""
    quoted = False
    for i, ch in enumerate(text):
        if ch == "`":
            quoted = not quoted
        elif not quoted and pattern.match(text, i):
            return i
    return None


def _without_asides(text):
    """The text with its parentheses outside backticks taken out."""
    out, quoted, depth = [], False, 0
    for ch in text:
        if ch == "`" and not depth:
            quoted = not quoted
        if not quoted and ch == "(":
            depth += 1
        if not depth:
            out.append(ch)
        if not quoted and ch == ")" and depth:
            depth -= 1
    return "".join(out)


def _pieces(text):
    """The comma-separated parts of a text, a comma inside backticks not counting: a test name or a
    quotation in a span may hold one."""
    out, cur, quoted = [], [], False
    for ch in text:
        if ch == "`":
            quoted = not quoted
        if ch == "," and not quoted:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return [p.strip() for p in out if p.strip()]


def _one(text):
    """(repository, test) if the text is one reference and nothing else, otherwise None."""
    m = LOCATOR.match(text) or WHOLE.match(text)
    return m.groups() if m else None


def references(rest):
    """The tests one `**Automated:**` line names, as dicts of repository, test and needle.

    SEVERAL TESTS ON ONE LINE ARE A LIST, separated by commas:

        **Automated:** `e2e RoamingScenarioTest`, `feature/roaming-server-data RoamingPackageTest`

    A pattern anchored on the marker matches once, so the second reference used to be dropped - not
    reported, not looked for. What is read:

      * the line up to a dash or a semicolon outside backticks, less its parentheses; the rest is
        commentary;
      * each comma-separated part that is one reference and nothing else - on a line that uses
        backticks, one that ends on a backtick;
      * on a line that uses backticks, a part with none is prose, and of a part that is prose around
        a span, the first span that is one reference - `PurchaseSagaTest`, and against a moved clock
        `SuspendedSagaExpiryTest` is two tests. A quotation is not one (`a purchase that is
        confirmed completes` is longer than a reference), and after the first part neither is a bare
        path or a file name, which says where a test lives or what it reads;
      * on a line with no backticks at all, the reference at the start of each part - which is how
        such a line was always read.
    """
    # A long test name wraps, and the line ends inside its backticks. Closed here, the span is read
    # up to the wrap - a prefix of the name, which is still what the source contains.
    if rest.count("`") % 2:
        rest += "`"
    cut = _outside_backticks(rest, COMMENTARY)
    head = _without_asides(rest if cut is None else rest[:cut])
    backticked = "`" in rest
    out = []
    for index, piece in enumerate(_pieces(head)):
        if backticked and "`" not in piece:
            continue
        # On a line that quotes its tests, a part is one reference only if it ends on a closing
        # backtick. A repository written bare before a quoted test is one; a quoted test followed by
        # the word "and", the sentence going on below, is a test and prose - not a repository called
        # after the test, holding a test called "and".
        pair = _one(piece) if not backticked or piece.endswith("`") else None
        if pair is None and backticked:
            for span in re.findall(r"`([^`]+)`", piece):
                span = span.strip()
                # A file name is a path with its directory left out, and in prose it says the same
                # thing: `ForeignCommitTest`, read against `kafka-consumer-groups.sh` - a tool the
                # test reads, not a second test.
                if index > 0 and (PATH.match(span) or bare_file(span)):
                    continue
                pair = _one(span)
                if pair:
                    break
        elif pair is None:
            m = REFERENCE.match(piece)
            pair = m.groups() if m else None
        if pair:
            repo, test = pair
            ref = {"repo": repo or "", "test": test, "needle": test_needle(test)}
            if file_of(test):
                ref["path"] = True
            out.append(ref)
    return out


def automated_lines(text):
    """The `**Automated:**` lines of a document: (inside a scenario, outside any).

    ONLY A LINE UNDER A `### Scenario:` HEADING IS AN AUTOMATED SCENARIO. A business rule may name
    the test that holds it - a sensible thing to write - and counted, it made the column larger than
    the scenarios it counts: 60 automated of 56, 107%. The scenario runs from its heading to the next
    heading of level three or above; a heading inside a fenced block - a gherkin comment is a `#` -
    is not one. The lines outside are returned so the table can name them instead of dropping them.
    """
    inside, outside = [], []
    in_scenario = fenced = False
    for line in text.split("\n"):
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced and SECTION.match(line):
            in_scenario = bool(SCENARIO.match(line))
        m = AUTOMATED.search(line)
        if m:
            (inside if in_scenario else outside).append(m.group(1).strip())
    return inside, outside


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
            lines, stray = automated_lines(text)
            out.append({
                "document": name[:-3],
                "scenarios": SCENARIO.findall(text),
                # TWO COUNTS, AND THEY ANSWER DIFFERENT QUESTIONS. `automated` is one per line - a
                # scenario is automated or it is not, which is what the percentage means - and
                # `references` is every test those lines name, which is what gets looked for.
                # Folded together, a line naming two tests made the table read over 100%.
                "automated": lines,
                "references": [r for line in lines for r in references(line)],
                "outside_scenarios": stray,
            })
    return out


def _word(name):
    """The name as `git grep -w -F` matches it: the whole string, with no letter, digit or underscore
    on either side. Without the boundary a walk found `Loan` in `LoanTest`, which git does not."""
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])")


def _contains(path, word):
    """Is the name written anywhere in this file, as a word? Text only, and small files only."""
    try:
        if os.path.getsize(path) > MAX_GREP_BYTES:
            return False
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return word.search(fh.read()) is not None
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

    THE SAME QUESTION MEANS THE SAME NEEDLE AND THE SAME MATCH. Through 0.3.7 the walk looked for what
    followed the last dot of the name, as a substring, and took a file named after it as the test:
    `kafka-consumer-groups.sh` was "found" as `sh`, `Loan` inside `LoanTest`, and a test renamed away
    in a file that kept its name - none of which `git grep -w` finds. Both now look for the whole
    name as a word. A name that is a file is not looked for here at all (see _check_file).

    MARKDOWN IS NEVER A TEST, and excluding it is what makes this check able to fail at all. When a
    project keeps its documentation in the same repository as its code - the layout this format
    recommends first - the name of the test occurs in the very document that names it. Searching
    everything found that document, reported the test as present, and went on reporting it as
    present after the test had been renamed away. The check answered a question about itself.
    """
    if os.path.exists(os.path.join(repo, ".git")):     # a file, in a worktree
        try:
            hit = subprocess.run(["git", "grep", "-l", "-w", "-F", "-e", name,
                                  "--", ":(exclude)*.md"],
                                 cwd=repo, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None, None
        out = hit.stdout.strip()
        return (True, out.split("\n")[0]) if out else (False, None)

    # Not a git checkout: walk it, and report the first file whose text has the name as a word.
    word = _word(name)
    for base, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS and not d.startswith("."))
        for f in sorted(files):
            if f.endswith(".md"):
                continue                   # see the docstring: a document is not evidence
            full = os.path.join(base, f)
            if _contains(full, word):
                return True, os.path.relpath(full, repo).replace(os.sep, "/")
    return False, None


def _by_name(anchor, name, dirs, trees):
    """A file name with a repository or module before it: a file of that name anywhere inside it.

    `dirs` are the directories the repository token names (see verify), each mapped onto the tree
    that holds it, so a git checkout is read through `git ls-files` here as it is for an anchor.
    None when no tree holds any of them - then nothing was looked in."""
    held = False
    for d in dirs:
        real = os.path.realpath(d)
        for repo, tree in sorted(trees.items()):
            root = os.path.realpath(tree["root"])
            if real == root:
                prefix = ""
            elif real.startswith(root + os.sep):
                prefix = os.path.relpath(real, root).replace(os.sep, "/") + "/"
            else:
                continue
            held = True
            at = sorted(f for f in tree["files"]
                        if f.startswith(prefix) and f.rsplit("/", 1)[-1] == name)
            if at:
                return code_anchors._within(
                    anchor, {"status": "found", "repo": repo, "at": at[0], "exact": False}, trees)
    return code_anchors._missing(name, trees) if held else None


def _check_file(a, trees, dirs):
    """A reference that is a path, resolved as an anchor is (SPEC 4) - see the module docstring.

    `trees` is code_anchors.context(). With a repository or module named, the path is inside it,
    which is how an anchor writes the same file; a bare file name is then anywhere inside it, which
    `dirs` - the directories that token names - say. Returns False, and leaves the reference alone,
    when the anchors check would skip the path as not looking like one: then it is searched for as
    text, as every reference was through 0.3.6."""
    path, first, last, bare = file_of(a["test"])
    if a["repo"] and not bare:
        while path.startswith("./"):
            path = path[2:]
        path = a["repo"].rstrip("/") + "/" + path
    anchor = {"path": path, "shortened": False, "service_hint": ""}
    if first:
        anchor["lines"] = [int(first), int(last or first)]
    if not trees[0]:
        a["found"] = None              # nothing under --repos to look in
        return True
    if bare and a["repo"]:
        res = _by_name(anchor, path, dirs, trees[0])
        if res is None:
            a["found"] = None
            return True
    else:
        # With no repository named, a bare name is the shortest suffix there is: a file of that name
        # in the reference's own repository, by the rule an anchor is found by.
        res = code_anchors.resolve(anchor, *trees)
    if res["status"] == "skipped":
        a.pop("path", None)
        return False
    if res["status"] == "found":
        a["found"], a["at"] = True, "{0}/{1}".format(res["repo"], res["at"])
        return True
    a["found"], a["at"] = False, ""
    why = res.get("why", "")
    if res.get("moved_to"):
        why = "possibly now: " + ", ".join(res["moved_repo"] + "/" + f for f in res["moved_to"])
    if why:
        a["why"] = why
    return True


def verify(items, repos_root, docs_root):
    # The trees are what code_anchors takes for trees. Under `--repos .` every subdirectory was one,
    # `.git` included, and walked raw: its index lists every tracked path and its logs every commit
    # subject, so a name was "found" there long after the code had dropped it.
    everything = [os.path.join(repos_root, n) for n in sorted(os.listdir(repos_root))
                  if os.path.isdir(os.path.join(repos_root, n)) and code_anchors.is_tree(n)]
    trees = None                       # loaded for the first reference that is a path
    for item in items:
        for a in item["references"]:
            # No repository named means "somewhere in what was given", which is the normal case for
            # a project documented in its own repository.
            #
            # A repository named is looked for BESIDE THE OTHERS, AND AS A MODULE INSIDE EACH OF
            # THEM. `server`, `e2e` and `feature/roaming-server-data` are modules of one checkout,
            # and looked for only as siblings they resolved to nothing - eleven references of
            # fourteen in one tree, every one of them silently not checked.
            candidates = ([os.path.join(repos_root, a["repo"])]
                          + [os.path.join(root, a["repo"]) for root in everything]
                          if a["repo"] else everything)
            candidates = [c for c in candidates if os.path.isdir(c)]
            if not candidates:
                a["found"] = None          # the repository is not here - nothing was checked
                continue
            if a.get("path"):
                if trees is None:
                    trees = code_anchors.context(docs_root, repos_root)
                if _check_file(a, trees, candidates):
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
        items = verify(items, os.path.abspath(args.repos), root)

    total = sum(len(i["scenarios"]) for i in items)
    auto = sum(len(i["automated"]) for i in items)
    missing = [(i["document"], a) for i in items for a in i["references"]
               if a.get("found") is False]
    # NOT LOOKED FOR IS NOT A PASS. `found is None` means the repository or module named could not
    # be located, so nothing was searched - and for as long as that was invisible, the reference read
    # as covered. A named test nobody looks for is exactly the rot this report exists to catch.
    unchecked = [(i["document"], a) for i in items for a in i["references"]
                 if args.repos and a.get("found") is None]
    # The same, one step earlier: a line in a scenario from which no reference could be read. It
    # counts as automated - the author said so - but no test was looked for, and that is said too.
    unread = [(i["document"], line) for i in items for line in i["automated"]
              if args.repos and not references(line)]

    if args.json:
        print(json.dumps({
            "total": total, "automated": auto,
            "documents": items,
            "tests_not_found": [dict(document=d, **a) for d, a in missing],
            "tests_not_looked_for": [dict(document=d, **a) for d, a in unchecked],
            "lines_naming_no_readable_test": [dict(document=d, line=l) for d, l in unread],
        }, ensure_ascii=False, indent=2))
        return 1 if (missing and args.check) else 0

    print("{0:34}{1:>10}{2:>10}".format("document", "scenarios", "automated"))
    print("-" * 54)
    # A document is shown if it has scenarios OR `**Automated:**` lines outside them. Skipping on
    # scenarios alone hid the case that matters: headings that do not read `### Scenario:` parse as
    # no scenarios, the row drops out, and its automated lines vanish with it. The row with a zero
    # and the lines it could not count is what names the malformed file.
    for i in sorted(items, key=lambda x: -len(x["scenarios"])):
        if not i["scenarios"] and not i["outside_scenarios"]:
            continue
        stray = len(i["outside_scenarios"])
        print("{0:34}{1:>10}{2:>10}{3}".format(
            i["document"], len(i["scenarios"]), len(i["automated"]),
            "   <- {0} `**Automated:**` line(s) outside any `### Scenario:`, not counted"
            .format(stray) if stray else ""))
    print("-" * 54)
    pct = auto * 100 // total if total else 0
    print("{0:34}{1:>10}{2:>10}   ({3}%)".format("TOTAL", total, auto, pct))

    tests = [(d, a) for d, a in missing if not a.get("path")]
    files = [(d, a) for d, a in missing if a.get("path")]
    if tests:
        print("\nA test is named that the repository does not contain:")
        for d, a in tests:
            print("  {0}: {1} {2}".format(d, a["repo"], a["test"]))
    if files:
        print("\nA file is named that is not in its repository (looked for as a path, SPEC 4):")
        for d, a in files:
            print("  {0}: {1}".format(d, " ".join(x for x in (a["repo"], a["test"]) if x)))
            if a.get("why"):
                print("      {0}".format(a["why"]))
    if unchecked:
        print("\n{0} named test(s) were NOT looked for - the repository or module could not be "
              "found under {1}, so nothing was searched:".format(len(unchecked), args.repos))
        for d, a in unchecked:
            print("  {0}: {1} {2}".format(d, a["repo"] or "(no repository named)", a["test"]))
    if unread:
        print("\n{0} `**Automated:**` line(s) in a scenario name no test this report can read "
              "(SPEC 3.1), so nothing was looked for:".format(len(unread)))
        for d, line in unread:
            print("  {0}: {1}".format(d, line if len(line) <= 90 else line[:87] + "..."))
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
