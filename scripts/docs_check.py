#!/usr/bin/env python3
"""
Connectivity check for the documentation tree. Complements backlog_index.py: that one watches the
index of tasks, this one watches the layers (research -> feature -> screen -> api -> service).

    python3 scripts/docs_check.py            # report
    python3 scripts/docs_check.py --json     # machine-readable
    python3 scripts/docs_check.py --on-main  # plus the checks that are only true on the default branch

LAYOUT. `--docs PATH` points at the tree (default: `docs` relative to the working directory);
`--backlog PATH` points at the backlog index (default: `<docs>/../backlog.md`), which is read only
as a hub: a document linked from it is not an orphan.

WHY A SCRIPT AND NOT A GREP ONE-LINER. A grep over markdown checks the links in the **body** of a
document, while the links between layers live in the frontmatter (`involved_services`,
`parent_feature`, `calls_api`, `api`) where grep does not look. In the tree this check was written
for, that blind spot was hiding four broken frontmatter references and six documents that had
fallen out of the coverage map in README.

Three levels of severity, and the split is the point:

  * ERROR    - things one cannot be wrong about: a broken link, a missing required field, an `id`
               that is not the file name. Blocking.
  * WARNING  - the rule is right but has legitimate exceptions: an orphan document, a feature with
               no screen. Not blocking.
  * INFO     - counters without a judgement (for instance the number of BDD scenarios).

The rule about exceptions matters more than the checks themselves: a gate that cannot be passed
legitimately gets switched off entirely within a month.

WHAT IS DELIBERATELY NOT CHECKED: the section structure. Documents legitimately deviate from the
template - a feature that is mostly a reality check has no business-rules section, and that is a
style, not a defect. Checking headings would catch style. What is checked instead is the substance
of the rule the format exists for: a reader must reach the code in one hop, so every document must
carry at least one path that looks like a path into a code tree.
"""
import argparse
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required:  pip install pyyaml")

# Layer -> required frontmatter fields. Taken from the templates rather than invented: what is
# checked is the contract the project wrote for itself.
LAYERS = {
    "research": ["id", "title", "type", "status"],
    "features": ["id", "title", "type", "status", "involved_services"],
    "screens":  ["id", "title", "type", "platform", "status", "parent_feature"],
    "api":      ["id", "title", "type", "status", "services", "contract_source"],
    "services": ["id", "title", "type", "tech_stack"],
}

# Research is the one layer that legitimately predates the code, so it is the one layer where a
# missing path into the code is a warning rather than an error. On a greenfield project research is
# written against dependency artefacts and published metadata, and there is no source tree to point
# at yet; demanding an anchor there would either block the check or teach people to invent a path,
# and an invented path is worse than an admitted gap.
ANCHOR_OPTIONAL = {"research"}

# `repo_url` is not in the required list above, and that is a decision rather than an oversight. In
# the single-repository layout `services/` describes the modules of one repository, so the field
# would hold the same URL on every document in the layer - bookkeeping that says nothing and gets
# out of date together. It still earns a warning, because code_anchors.py uses it to decide which
# repository an anchor belongs to, and without it the path is looked for in all of them at once.

# Fields whose values are ids of other documents. The other list-valued fields (`tech_stack`,
# `contract_source`, `depends_on`) hold free text and the names of external systems, so no links
# are resolved through them.
#
# `services` was missing from this list for a while, which made it the one link field the spec
# declares and the resolver ignored: `services: [no-such-service]` on an endpoint document was
# accepted in silence, and so was a link to a service whose document says it is deprecated.
REF_FIELDS = ("involved_services", "client_entries", "api",
              "parent_feature", "calls_api", "services", "epic")

# A path into the code: something in backticks with a slash in it, or a bare file name with a
# familiar source extension. Deliberately loose - the question is "is there a way into the code
# from here at all", not "is this exact path right"; whether the path still exists is the job of
# code_anchors.py, which needs the repositories to answer.
CODE_ANCHOR = re.compile(
    r"`[A-Za-z0-9_.-]+/[A-Za-z0-9_./{}<>-]*`"
    r"|`[A-Za-z0-9_]+\.(?:py|js|ts|tsx|jsx|go|rs|rb|java|kt|kts|cs|php|swift"
    r"|sql|sh|yaml|yml|toml|json|tf)`"
)

ALLOWED_STATUS = {"draft", "active", "deprecated"}

# A link in the body of a document, resolved against the docs root: `../api/endpoint-x.md` from a
# screen and `api/endpoint-x.md` from the root mean the same file.
MD_LINK = re.compile(
    r"\]\((?:\.\./)?((?:research|features|screens|api|services|backlog)/[^)#\s]+\.md)")
# A link in a hub file, wherever the hub happens to live: only the file name is taken from it.
HUB_LINK = re.compile(r"\]\((?!https?:)([^)#\s]+\.md)")

SCENARIO = re.compile(r"^###\s+Scenario:", re.M)

# There is deliberately no pattern for `**Automated:**` here. How many scenarios carry a link to a
# test has exactly one owner, bdd_report.py, which needs the shape of that line anyway in order to
# go looking for the test. Counting it in both places is how the two came to disagree: a bare
# marker matched here, a repository-and-test pair matched there, and one run reported 100% and 0%
# about the same file. A number with two owners has none.


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


def read_hub_links(root, backlog_path):
    """Documents linked from README.md or from the backlog index - they count as "someone links
    here" too, which is what keeps an entry point from being reported as an orphan."""
    out = set()
    for path in (os.path.join(root, "README.md"), backlog_path):
        if path and os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                for link in HUB_LINK.findall(fh.read()):
                    out.add(os.path.basename(link)[:-3])
    return out


def load_docs(root):
    """Every document of the layers, with its frontmatter.

    Only the layer directories are walked, which is also how `templates/` inside the tree is
    skipped: the placeholders there are not documents and would fail every check in the file.
    """
    docs = {}
    for layer in LAYERS:
        folder = os.path.join(root, layer)
        if not os.path.isdir(folder):
            continue          # a missing layer is a valid answer, not a defect
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".md") or name == "README.md":
                continue
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                text = fh.read()
            m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
            fm, err = {}, None
            if not m:
                err = "no frontmatter"
            else:
                try:
                    fm = yaml.safe_load(m.group(1)) or {}
                except yaml.YAMLError as e:
                    err = "frontmatter does not parse: {0}".format(e)
                if err is None and not isinstance(fm, dict):
                    fm, err = {}, "frontmatter is not a mapping"
            docs["{0}/{1}".format(layer, name)] = {
                "layer": layer, "stem": name[:-3], "fm": fm,
                "text": text, "error": err,
            }
    return docs


def refs(fm, field):
    """The values of a link field as a list, with template placeholders dropped."""
    v = fm.get(field)
    if v is None:
        return []
    items = v if isinstance(v, list) else [v]
    return [str(x).strip() for x in items
            if isinstance(x, str) and x.strip() and not x.strip().startswith("<")]


def check(docs, root, hub, on_main=False):
    errors, warns, info = [], [], []
    ids = {d["fm"].get("id") or d["stem"] for d in docs.values()}
    # id -> status, so that a link can be judged by what it points at rather than only by whether
    # it resolves. See the deprecated check below.
    status_of = {(d["fm"].get("id") or d["stem"]): str(d["fm"].get("status", ""))
                 for d in docs.values()}

    # Who links to me. Both the frontmatter AND the markdown links in the body count: screens are
    # tied to each other by navigation (a main screen leads to a profile screen leads to an orders
    # screen), not only by "feature -> screen". Counting the frontmatter alone declares perfectly
    # live screens to be orphans.
    incoming = {i: set() for i in ids}
    for path, d in docs.items():
        me = d["fm"].get("id") or d["stem"]
        targets = set()
        for field in REF_FIELDS:
            targets.update(refs(d["fm"], field))
        for link in MD_LINK.findall(d["text"]):
            targets.add(os.path.basename(link)[:-3])
        for r in targets:
            if r in incoming and r != me:
                incoming[r].add(me)

    for path, d in sorted(docs.items()):
        fm, stem = d["fm"], d["stem"]
        did = fm.get("id") or stem

        if d["error"]:
            errors.append((path, "frontmatter", d["error"]))
            continue

        if fm.get("id") != stem:
            errors.append((path, "id-mismatch",
                           "id={0!r}, but the file is called {1!r}".format(fm.get("id"), stem)))

        for field in LAYERS[d["layer"]]:
            if field not in fm or fm[field] in (None, "", []):
                errors.append((path, "missing-field", "no {0} field".format(field)))

        status = str(fm.get("status", ""))
        if status and status not in ALLOWED_STATUS:
            errors.append((path, "bad-status",
                           "status={0!r}, allowed: {1}".format(status, sorted(ALLOWED_STATUS))))
        if on_main and status == "draft":
            # The invariant: the default branch describes what exists.
            errors.append((path, "draft-on-main",
                           "status: draft cannot live on the default branch - the document "
                           "describes intent, not fact"))

        for field in REF_FIELDS:
            for r in refs(fm, field):
                if r not in ids:
                    errors.append((path, "broken-ref",
                                   "{0}: {1} - no such document".format(field, r)))
                # A link that resolves to a document announcing that its subject is gone. The
                # third status value used to do nothing at all: `draft` has --on-main, `active` is
                # the default, and `deprecated` was accepted and acted on by nobody - so a live
                # feature could keep routing readers to a service whose document says the
                # behaviour no longer exists, and every check stayed green.
                #
                # A warning rather than an error, because deprecating something and updating its
                # dependants are days apart and both states are legitimate in between. What is not
                # legitimate is nobody knowing.
                elif status_of.get(r) == "deprecated" and status != "deprecated":
                    warns.append((path, "points-at-deprecated",
                                  "{0}: {1} is deprecated, and this document is {2}"
                                  .format(field, r, status or "not marked")))

        for link in set(MD_LINK.findall(d["text"])):
            if not os.path.isfile(os.path.join(root, link)):
                errors.append((path, "broken-link", "link to {0}".format(link)))

        if not CODE_ANCHOR.search(d["text"]):
            msg = ("not a single path into the code - the implementation cannot be "
                   "reached from this document in one hop")
            if d["layer"] in ANCHOR_OPTIONAL:
                warns.append((path, "no-code-anchor",
                              msg + " (research may predate the code; cite the artefact you "
                                    "verified against)"))
            else:
                errors.append((path, "no-code-anchor", msg))

        # Features are the roots of the graph - nothing above them links down to them - so they
        # are exempt: the place a feature is listed in is the coverage map, and that is
        # coverage_map.py's business, not this one's.
        if (did in incoming and not incoming[did] and did not in hub
                and d["layer"] != "features"):
            warns.append((path, "orphan",
                          "no document and no hub (README, backlog) links here"))

        # See the note next to ANCHOR_OPTIONAL: absent is legitimate for the modules of a single
        # repository, so this is a warning that names what it costs rather than an error.
        if d["layer"] == "services" and not fm.get("repo_url"):
            warns.append((path, "no-repo-url",
                          "no repo_url - code_anchors.py will look this service's paths up in "
                          "every repository at once instead of in one. Legitimate when the "
                          "documentation covers a single repository"))

    # Coverage in both directions: a feature should say where the client enters and which
    # contracts it touches.
    for path, d in sorted(docs.items()):
        if d["layer"] != "features" or d["error"]:
            continue
        # An empty list is an ANSWER ("this feature has no client"); a missing field is silence.
        # Telling them apart is mandatory: otherwise every honest server-side feature carrying
        # `client_entries: []` shows up in the report as unfinished work, and a month later the
        # report stops being read.
        for field, msg in (
            ("client_entries",
             "no client_entries field - does the feature have no client surface, or was it "
             "forgotten? An empty list [] settles the question"),
            ("api",
             "no api field - does the feature touch no contracts, or are the links missing? "
             "An empty list [] settles the question"),
        ):
            if field not in d["fm"]:
                warns.append((path, "no-{0}".format(field.replace("_", "-")), msg))

    total = sum(len(SCENARIO.findall(d["text"])) for d in docs.values())
    info.append(("BDD", "{0} scenarios (how many are automated: bdd_report.py)".format(total)))
    return errors, warns, info, {
        "documents": len(docs), "scenarios": total,
        "errors": len(errors), "warnings": len(warns),
    }


def main():
    ap = argparse.ArgumentParser(description="Connectivity check for the documentation tree")
    ap.add_argument("--docs", metavar="PATH", default="docs",
                    help="the docs/ tree (default: docs, relative to the working directory)")
    ap.add_argument("--backlog", metavar="PATH",
                    help="the backlog index, read as a hub (default: <docs>/../backlog.md)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--on-main", action="store_true",
                    help="add the checks that only hold on the default branch")
    args = ap.parse_args()

    _utf8_stdout()

    root = os.path.abspath(args.docs)
    backlog_path = (os.path.abspath(args.backlog) if args.backlog
                    else os.path.join(os.path.dirname(root), "backlog.md"))

    # A missing tree is a mode, not a failure. Saying "nothing was checked" is not the same as
    # saying "nothing is wrong", so it is said out loud.
    if not os.path.isdir(root):
        print("no docs tree at {0} - nothing checked".format(root))
        return 0

    docs = load_docs(root)
    hub = read_hub_links(root, backlog_path)
    errors, warns, info, stats = check(docs, root, hub, args.on_main)

    if args.json:
        print(json.dumps({"stats": stats,
                          "errors": [dict(zip(("file", "check", "message"), e)) for e in errors],
                          "warnings": [dict(zip(("file", "check", "message"), w)) for w in warns]},
                         ensure_ascii=False, indent=2))
        return 1 if errors else 0

    if errors:
        print("ERROR ({0})".format(len(errors)))
        print("-" * 72)
        for f, c, m in errors:
            print("  [{0}] {1}\n      {2}".format(c, f, m))
        print()
    if warns:
        print("WARNING ({0})".format(len(warns)))
        print("-" * 72)
        for f, c, m in warns:
            print("  [{0}] {1}\n      {2}".format(c, f, m))
        print()
    for k, v in info:
        print("{0}: {1}".format(k, v))
    print("-" * 72)
    print("Documents: {documents}".format(**stats))
    print("FAILED: {0} errors".format(len(errors)) if errors else "No errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
