#!/usr/bin/env python3
"""What the scripts do when they cannot find their subject.

Every check here runs one of the scripts in a directory that has no documentation tree at all, and
asserts the exit code. That is the case nothing else covers: `make check` runs them against the
example tree, where everything is present, so the behaviour on an ABSENT subject is exercised by no
gate in this repository and by no gate in the seven that copy these scripts.

It exists because of one defect of exactly that shape. `backlog_index.py --check` printed
"no backlog items ... - nothing checked" and exited 0, so a backlog lost to a bad merge, a `git mv`
or a `--docs` path that stopped matching was reported as a pass — on a green step, in a log nobody
opens. A check that cannot find its subject and reports success is worse than no check.
"""
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


def main():
    failures = []

    def expect(label, code, wanted, output):
        if code != wanted:
            failures.append("{0}: exit {1}, wanted {2}\n{3}".format(label, code, wanted, output))

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

    if failures:
        sys.stderr.write("\n\n".join(failures) + "\n")
        return 1
    print("script_selftest: 4 checks, every script refuses to pass on a subject it cannot find")
    return 0


if __name__ == "__main__":
    sys.exit(main())
