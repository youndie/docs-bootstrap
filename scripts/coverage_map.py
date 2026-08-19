#!/usr/bin/env python3
"""
The coverage map in docs/README.md against the files on disk.

    python3 scripts/coverage_map.py           # report
    python3 scripts/coverage_map.py --check   # the same, for CI (exit 1 on a discrepancy)
    python3 scripts/coverage_map.py --fix     # append what is missing, correct the counters

LAYOUT. `--docs PATH` points at the tree (default: `docs` relative to the working directory); the
map is the last section of `<docs>/README.md`.

WHY THIS IS NOT A GENERATOR, unlike backlog_index.py. It is tempting to assemble the map out of
the files, but that would lose the only thing the map is read for: the descriptions. A document's
`title` is its full name, while the map holds a short phrase next to other lines grouped by
meaning ("Identity and access", "Stock and trade"). Neither the grouping nor the emphasis can be
derived from the files, and replacing them with generated text makes the document worse.

Hence the split: **the machine owns the membership and the counters, the human owns the meaning.**
Missing a document is impossible (`--check` goes red), but what to call it and which group it
belongs to is the author's decision. `--fix` appends the missing lines at the end of their section
with the `title` filled in and a comment marking them: that is a placeholder, not an answer.

What is checked:
  * every document of a layer is listed in the map;
  * the map holds no links to files that do not exist;
  * the number in the section heading ("### Features (23)") matches reality.

A layer that has neither a directory nor a section is skipped in silence - a project without
screens is not a project with a defect.
"""
import argparse
import os
import re
import sys

# Section heading -> directory. `[ \t]*\r?$` rather than `\s*$`: the file may have CRLF endings,
# and `\s` would eat the line break together with the start of the next line.
SECTIONS = [
    ("Research", re.compile(r"^### Research \((\d+)\)[ \t]*\r?$", re.M | re.I),
     "research"),
    ("Services", re.compile(r"^### Services \((\d+)(?:/(\d+))?\)[ \t]*\r?$", re.M | re.I),
     "services"),
    ("Features", re.compile(r"^### Features \((\d+)\)[ \t]*\r?$", re.M | re.I),
     "features"),
    ("Screens",  re.compile(r"^### Screens / Flows \((\d+)\)[ \t]*\r?$", re.M | re.I),
     "screens"),
    ("API",      re.compile(r"^### API \((\d+)\)[ \t]*\r?$", re.M | re.I),
     "api"),
]


def _utf8_stdout():
    """The output of this script is ASCII, but ids and titles come out of the documents, and a
    project's documentation may be written in any language. A Windows console defaults to a legacy
    code page and dies on the first character outside it; CI on Linux never sees this, so the
    failure looks like a script that is broken on exactly one developer's machine."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def read_title(root, folder, stem):
    """The document's title from its frontmatter - the placeholder for a description."""
    path = os.path.join(root, folder, stem + ".md")
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r'^title:\s*"?(.+?)"?\s*$', line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return stem


def documents(root, folder):
    path = os.path.join(root, folder)
    if not os.path.isdir(path):
        return []
    return sorted(f[:-3] for f in os.listdir(path)
                  if f.endswith(".md") and f != "README.md")


def analyse(root, text):
    """For every section: what the map lists, and what lies on disk."""
    out = []
    for name, pattern, folder in SECTIONS:
        actual = documents(root, folder)
        m = pattern.search(text)
        if not m:
            # No section and no documents: the project does not have this layer.
            if actual:
                out.append({"name": name, "folder": folder, "missing_section": True,
                            "actual": actual})
            continue
        start = m.end()
        nxt = re.search(r"^##+ ", text[start:], re.M)
        end = start + nxt.start() if nxt else len(text)
        listed = re.findall(r"\]\(" + folder + r"/([A-Za-z0-9._-]+)\.md\)", text[start:end])
        out.append({
            "name": name, "folder": folder, "missing_section": False,
            "listed": listed, "actual": actual, "claimed": int(m.group(1)),
            "header": m.group(0), "header_start": m.start(),
            "start": start, "end": end,
        })
    return out


def report(sections):
    problems = []
    for s in sections:
        if s.get("missing_section"):
            problems.append((s["name"],
                             "no section in README, but {0} documents on disk"
                             .format(len(s["actual"]))))
            continue
        listed, actual = set(s["listed"]), set(s["actual"])
        for stem in sorted(actual - listed):
            problems.append((s["name"], "not in the map: {0}".format(stem)))
        for stem in sorted(listed - actual):
            problems.append((s["name"], "in the map, but there is no file: {0}".format(stem)))
        if s["claimed"] != len(actual):
            problems.append((s["name"], "the heading says {0}, there are {1} files"
                             .format(s["claimed"], len(actual))))
    return problems


def fix(root, text, sections):
    """Corrects the counters and appends the missing lines.

    Walking from the end of the file: an edit shifts the offsets, and the sections above it in the
    text have already had theirs computed.
    """
    eol = "\r\n" if "\r\n" in text else "\n"
    for s in reversed(sections):
        if s.get("missing_section"):
            continue          # a whole section is an editorial decision, not a placeholder
        add = sorted(set(s["actual"]) - set(s["listed"]))
        if add:
            lines = [
                "- [x] [{0}]({1}/{0}.md) - {2}  "
                "<!-- added by coverage_map.py: write the description and pick the group -->"
                .format(stem, s["folder"], read_title(root, s["folder"], stem))
                for stem in add
            ]
            body = text[s["start"]:s["end"]].rstrip("\r\n")
            body += eol + eol.join(lines) + eol + eol
            text = text[:s["start"]] + body + text[s["end"]:]
        if s["claimed"] != len(s["actual"]):
            head = re.sub(r"\((\d+)(/\d+)?\)",
                          lambda mm: "({0}{1})".format(len(s["actual"]), mm.group(2) or ""),
                          s["header"])
            text = text[:s["header_start"]] + head + text[s["header_start"] + len(s["header"]):]
    return text


def main():
    ap = argparse.ArgumentParser(description="The README coverage map against the files on disk")
    ap.add_argument("--docs", metavar="PATH", default="docs",
                    help="the docs/ tree (default: docs, relative to the working directory)")
    ap.add_argument("--check", action="store_true",
                    help="for CI; the behaviour is the same, exit 1 on a discrepancy")
    ap.add_argument("--fix", action="store_true",
                    help="append the missing lines as placeholders and correct the counters")
    args = ap.parse_args()

    _utf8_stdout()

    root = os.path.abspath(args.docs)
    readme = os.path.join(root, "README.md")

    # A missing tree is a mode, not a failure. Saying "nothing was checked" is not the same as
    # saying "nothing is wrong", so it is said out loud.
    if not os.path.isdir(root):
        print("no docs tree at {0} - nothing checked".format(root))
        return 0
    if not os.path.isfile(readme):
        print("no README.md at {0} - the coverage map lives there".format(readme))
        return 1

    # newline="" on both read and write: without it Python normalises CRLF to LF and --fix
    # rewrites the whole file instead of three lines. A diff in review should show the edit, not
    # "167 lines changed".
    with open(readme, encoding="utf-8", newline="") as fh:
        text = fh.read()

    sections = analyse(root, text)
    problems = report(sections)

    if args.fix:
        if not problems:
            print("The map matches the files, nothing to fix")
            return 0
        updated = fix(root, text, sections)
        if updated == text:
            # Everything that was wrong needs a person: a whole missing section is a grouping
            # decision, and inventing one here would be the "silently rewrite a hand-written
            # document" that the format forbids.
            for name, msg in problems:
                print("  [{0}] {1}".format(name, msg))
            print("\nNothing could be appended automatically: {0} discrepancies, all of them "
                  "editorial.".format(len(problems)))
            return 1
        with open(readme, "w", encoding="utf-8", newline="") as fh:
            fh.write(updated)
        print("README.md updated: there were {0} discrepancies".format(len(problems)))
        print("The appended lines carry a comment - describe them in your own words and put them "
              "in the right groups.")
        return 0

    for name, msg in problems:
        print("  [{0}] {1}".format(name, msg))
    if problems:
        print("\nDiscrepancies: {0}. To append placeholders: "
              "python3 scripts/coverage_map.py --fix".format(len(problems)))
        return 1
    print("The coverage map matches the files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
