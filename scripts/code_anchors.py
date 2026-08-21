#!/usr/bin/env python3
"""
Code anchors: do the paths the documentation points at still exist?

    python3 scripts/code_anchors.py --repos ..          # report
    python3 scripts/code_anchors.py --repos .. --check  # the same, exit 1 if anything has rotted
    python3 scripts/code_anchors.py --repos .. --json

WHY. "Every document carries code anchors, the reader reaches the code in one hop" is the rule the
whole format exists for. A path into another repository rots silently: nobody renames it together
with the code, because the refactor happens elsewhere and knows nothing about these documents.
This is the one class of defect that cannot be caught inside the documentation tree - it needs
access to the code.

HOW PATHS ARE MATCHED. They are written down in different ways, and that is fine:

    catalog-api/src/routes/loans.py            from the repository root
    src/routes/loans.py                        from the module root
    .../routes/loans.py                        abbreviated
    routes/loans.py                            just the tail

Normalising them to one form would be pointless - an abbreviated `...` reads better in prose than
a full path. So the check is a **suffix** check: an anchor is alive if the repository tree holds a
file or directory whose path ends with the fragment. Such a check can report a false "found" (two
files with the same name in different modules); a false "missing" it practically cannot produce.
For the job at hand - catching rot - the bias is chosen deliberately.

Which repository to look in is decided by the "Service" column of the anchor table: a service id
leads to `<docs>/services/<id>.md`, whose `repo_url` gives the name of the clone (its last path
segment). If that fails, the path is looked for in every repository at once - and then the report
shows where it was found.

WITHOUT --repos THE SCRIPT ASSERTS NOTHING. "Not checked" and "no violations" are different
statements; the first one is printed explicitly.

`--repos DIR` is a directory whose subdirectories are the repositories (`--repos ..` when the
clones sit side by side). A subdirectory that is a git checkout is read with `git ls-files`, which
respects .gitignore for free; anything else is walked with the usual build directories skipped.
"""
import argparse
import json
import os
import re
import subprocess
import sys

FOLDERS = ("research", "features", "screens", "api", "services")

# A path in backticks: at least one slash.
PATH_RE = re.compile(r"`(\.{3}/)?([A-Za-z0-9_.-][A-Za-z0-9_./{}<>*-]*/[A-Za-z0-9_./{}<>*-]*)`")
# A row of the code-anchor table: | service | paths |
TABLE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$", re.M)
# Fragments there is nothing to check against: patterns and substitutions.
WILDCARD = re.compile(r"[*{}<>]")

# Not everything with a slash in backticks is a path. What is obviously not one is filtered out,
# otherwise the report drowns in noise: MIME types, slash-separated enumerations, host names.
NOT_A_PATH = re.compile(
    r"^application/|^text/|^image/|^multipart/"          # MIME
    r"|^[A-Za-z]+(/[A-Z][A-Za-z]*)+$"                    # createAccess/Refresh/Token
    r"|^[A-Za-z]+\.[a-z][A-Za-z]*(/[a-z]+)+$"            # rateLimit.average/burst/period
    r"|^[a-z0-9-]+(\.[a-z0-9-]+)+/"                      # a host: shop.example.com/api
)

# A segment that says "this is a source tree", used to tell a path from a class reference.
STRUCTURAL = re.compile(
    r"(^|/)(src|main|lib|libs|app|apps|packages|modules|internal|pkg|cmd|test|tests|spec"
    r"|resources|assets|static|templates|charts|deploy|k8s|infra|config|scripts|migrations"
    r"|server|client|shared|common|core|docs)(/|$)"
)

# Directories that are build output or tooling state: never worth indexing, and big enough to make
# the walk slow if they are.
IGNORED_DIRS = {".git", ".hg", ".svn", "node_modules", "build", "dist", "out", "target",
                "__pycache__", ".venv", "venv", ".tox", ".idea", ".gradle", ".next",
                "vendor", "coverage", ".mypy_cache", ".pytest_cache"}


def _utf8_stdout():
    """The output of this script is ASCII, but paths and ids come out of the documents, and a
    project's documentation may be written in any language. A Windows console defaults to a legacy
    code page and dies on the first character outside it; CI on Linux never sees this, so the
    failure looks like a script that is broken on exactly one developer's machine."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def repo_by_service(root):
    """Service id -> repository directory name, taken from the frontmatter of services/*.md.

    The directory name is the last segment of `repo_url`, which is how a clone is called by
    default. A `.git` suffix is dropped; a template placeholder in angle brackets is ignored.
    """
    out = {}
    folder = os.path.join(root, "services")
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md") or name == "README.md":
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"^repo_url:\s*[\"'<]?(\S+?)[\"'>]?\s*$", line)
                if not m:
                    continue
                url = m.group(1)
                if "<" in url or ">" in url:
                    break
                leaf = url.rstrip("/").rsplit("/", 1)[-1]
                if leaf.endswith(".git"):
                    leaf = leaf[:-4]
                if leaf:
                    out[name[:-3]] = leaf
                break
    return out


def _dirs_of(files):
    dirs = set()
    for f in files:
        parts = f.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    return dirs


def _git_tree(path):
    """The tracked files of a git checkout, or None if this is not one / git is unavailable."""
    if not os.path.isdir(os.path.join(path, ".git")):
        return None
    try:
        res = subprocess.run(["git", "ls-files"], cwd=path,
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    files = {ln.strip() for ln in res.stdout.split("\n") if ln.strip()}
    if not files:
        return None
    return {"files": files, "dirs": _dirs_of(files)}


def _walked_tree(path):
    """The files of a plain directory. The fallback for a repository that is not a git checkout -
    a vendored copy, a subdirectory of a monorepo, the example tree shipped with this repository."""
    files = set()
    for base, names, filenames in os.walk(path):
        # Only the known build and tooling directories are pruned. Dot-directories in general are
        # kept: `.github/workflows/` is a perfectly ordinary anchor target.
        names[:] = [n for n in names if n not in IGNORED_DIRS]
        rel = os.path.relpath(base, path)
        prefix = "" if rel == "." else rel.replace(os.sep, "/") + "/"
        for n in filenames:
            files.add(prefix + n)
    return {"files": files, "dirs": _dirs_of(files)}


def load_trees(repos_root, skip=()):
    """Repository name -> the set of file and directory paths inside it.

    `skip` holds directories that are not code to look in. The documentation tree is one of them:
    it frequently sits next to the clones (`--repos ..`), or inside them, as it does in this
    repository's own example - and it is the thing being checked, not a thing to check against.
    Indexing it makes an anchor resolvable by the document that mentions it.
    """
    trees = {}
    if not os.path.isdir(repos_root):
        return trees
    skip = {os.path.realpath(p) for p in skip}
    for name in sorted(os.listdir(repos_root)):
        path = os.path.join(repos_root, name)
        if not os.path.isdir(path) or name.startswith(".") or name in IGNORED_DIRS:
            continue
        if os.path.realpath(path) in skip:
            continue
        tree = _git_tree(path) or _walked_tree(path)
        if tree["files"]:
            trees[name] = tree
    return trees


def collect_anchors(root):
    """The anchors of every document, with a guess at the service from the table row."""
    anchors = []
    for folder in FOLDERS:
        path = os.path.join(root, folder)
        if not os.path.isdir(path):
            continue
        for name in sorted(os.listdir(path)):
            if not name.endswith(".md") or name == "README.md":
                continue
            doc = "{0}/{1}".format(folder, name)
            with open(os.path.join(path, name), encoding="utf-8") as fh:
                text = fh.read()
            # The tables first: they are the only place with a service column.
            in_table = {}
            for cells in TABLE_ROW.findall(text):
                service = cells[0].strip().strip("*` ")
                for _, p in PATH_RE.findall(cells[1]):
                    in_table[p] = service
            for dots, p in PATH_RE.findall(text):
                anchors.append({
                    "doc": doc, "path": p, "shortened": bool(dots),
                    "service_hint": in_table.get(p, ""),
                })
    return anchors


def resolve(anchor, trees, svc2repo):
    """Looks the anchor up: first in the repository the hint names, then in all of them."""
    raw = anchor["path"]
    is_dir = raw.endswith("/")     # remember BEFORE trimming: below there is no slash any more
    p = raw.rstrip("/")
    if WILDCARD.search(p):
        return {"status": "skipped", "why": "a pattern, not a path"}
    if NOT_A_PATH.match(p):
        return {"status": "skipped", "why": "not a path into the code"}
    # What marks a real path: a file extension, a trailing slash, or a structural segment. Without
    # one of those this is a reference to a class (`feature/shop/GetShopsUseCase`) or a plain turn
    # of phrase (`try/catch`) - both have made it into the report before and forced someone to
    # explain why they need no fixing.
    if not (re.search(r"\.[A-Za-z0-9]{1,6}(/|$)", p) or is_dir or STRUCTURAL.search(p)):
        return {"status": "skipped", "why": "looks like a class name, not a path"}

    # `...` in the middle is the ordinary abbreviation: server/.../routes/loans.py. The search uses
    # the last meaningful fragment, which is the most specific one.
    if "/.../" in p or p.startswith(".../"):
        p = p.rsplit("...", 1)[-1].lstrip("/")
        if not p or "/" not in p:
            return {"status": "skipped", "why": "an abbreviation with no path left"}

    hint = svc2repo.get(anchor["service_hint"], "")
    order = ([hint] if hint in trees else []) + [r for r in trees if r != hint]

    for repo in order:
        tree = trees[repo]
        # An exact match from the repository root, or the same path with the repository name cut
        # off the front.
        for candidate in (p, p.split("/", 1)[1] if "/" in p else p):
            if candidate in tree["files"] or candidate in tree["dirs"]:
                return {"status": "found", "repo": repo, "at": candidate, "exact": True}
        # A suffix match: the anchor was written from the module root, or abbreviated.
        suffix = "/" + p
        hit = next((f for f in tree["files"] if f.endswith(suffix)), None) \
            or next((d for d in tree["dirs"] if d.endswith(suffix)), None)
        if hit:
            return {"status": "found", "repo": repo, "at": hit, "exact": False}

    # Not found. A file of that name may simply have moved - a refactor that shuffles modules
    # around is the usual cause. Saying where a file with the same name lives now turns the report
    # into repair instructions.
    leaf = p.rstrip("/").split("/")[-1]
    if leaf and "." in leaf:
        for repo, tree in trees.items():
            same = [f for f in tree["files"] if f.endswith("/" + leaf)]
            if same:
                return {"status": "missing", "moved_to": sorted(same)[:2], "moved_repo": repo}
    return {"status": "missing"}


def main():
    ap = argparse.ArgumentParser(description="Do the code anchors still exist?")
    ap.add_argument("--docs", metavar="PATH", default="docs",
                    help="the docs/ tree (default: docs, relative to the working directory)")
    ap.add_argument("--repos", metavar="DIR",
                    help="a directory whose subdirectories are the service repositories; "
                         "without it nothing is checked")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any anchor did not resolve")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    _utf8_stdout()

    root = os.path.abspath(args.docs)

    # A missing tree is a mode, not a failure. Saying "nothing was checked" is not the same as
    # saying "nothing is wrong", so it is said out loud.
    if not os.path.isdir(root):
        print("no docs tree at {0} - nothing checked".format(root))
        return 0

    anchors = collect_anchors(root)
    if not args.repos:
        print("Anchors in the documentation: {0}".format(len(anchors)))
        print("Their existence was NOT checked: --repos was not given. "
              "That is not the same as \"they are all there\".")
        return 0

    trees = load_trees(os.path.abspath(args.repos), skip=[root])
    if not trees:
        # The same answer as "--repos was not given", because it is the same situation: nothing was
        # checked, and that is said out loud rather than dressed up as a pass. It used to exit 2,
        # which made `make check` red in a separate documentation repository — there the clones
        # exist only inside CI, so every contributor saw a failure caused by a directory that is
        # not supposed to be there. A report that fails the gate stops being read, and takes the
        # gate with it. Only --check, which is a request to assert, turns this into an error.
        print("no repository directories under {0} - their existence was NOT checked. "
              "That is not the same as \"they are all there\".".format(args.repos))
        return 2 if args.check else 0

    svc2repo = repo_by_service(root)
    for a in anchors:
        a.update(resolve(a, trees, svc2repo))

    missing = [a for a in anchors if a["status"] == "missing"]
    skipped = [a for a in anchors if a["status"] == "skipped"]
    found = [a for a in anchors if a["status"] == "found"]

    if args.json:
        print(json.dumps({"total": len(anchors), "found": len(found),
                          "missing": len(missing), "skipped": len(skipped),
                          "repos": sorted(trees), "anchors": anchors},
                         ensure_ascii=False, indent=2))
        return 1 if (missing and args.check) else 0

    print("Repositories: {0}".format(", ".join(sorted(trees))))
    print("Anchors: {0} - found {1}, not found {2}, skipped {3}\n"
          .format(len(anchors), len(found), len(missing), len(skipped)))

    if missing:
        by_doc = {}
        for a in missing:
            by_doc.setdefault(a["doc"], []).append(a)
        print("NOT FOUND")
        print("-" * 72)
        for doc in sorted(by_doc):
            print("  {0}".format(doc))
            for a in by_doc[doc]:
                mark = " (abbreviated)" if a["shortened"] else ""
                print("      {0}{1}".format(a["path"], mark))
                for at in a.get("moved_to", []):
                    print("          possibly now: {0}/{1}".format(a["moved_repo"], at))
        print()
    if skipped:
        print("Skipped as patterns: {0}\n"
              .format(", ".join(sorted({a["path"] for a in skipped}))))

    if missing:
        print("Rotten anchors: {0}. A path in another repository gets renamed without anyone "
              "looking into the documentation.".format(len(missing)))
        return 1 if args.check else 0
    print("Every anchor resolves")
    return 0


if __name__ == "__main__":
    sys.exit(main())
