#!/usr/bin/env python3
"""
The packaging manifests against each other and against the skill they ship.

    python3 scripts/plugin_check.py            # check
    python3 scripts/plugin_check.py --root ..  # a repository somewhere else

WHY. The name of this skill is written down in four places: the `name:` in the frontmatter of
SKILL.md, `name` in `.claude-plugin/plugin.json`, the entry in `.claude-plugin/marketplace.json`,
and the directory the skill is installed into. Nothing in the runtime compares them. A rename that
updates three of the four leaves a plugin that installs and a skill that never fires, and the
failure is silent in both directions: the manifest is valid, and the skill is simply absent.

WHAT THIS ADDS TO `claude plugin validate`. That command checks the manifests against their schema
and checks that each `skills[]` path exists. It does not check that the path holds a `SKILL.md` —
pointing the array at a directory of Python scripts passes validation and produces a plugin with no
skills in it. So the schema is its job and the correspondence is this script's, and both are worth
running: `validate --strict` for the shape, this one for the agreement.

A repository with no `.claude-plugin/` directory is a normal case, not a failure: the format and
the checks do not need packaging. That is said out loud rather than passed over in silence, because
"not checked" and "nothing wrong" are different statements.

    python3 scripts/plugin_check.py --against origin/main   # CI on a pull request

UNDER `--against`, A CHANGE THAT SHIPS HAS TO RAISE THE VERSION. `claude plugin update` compares the
`version` in plugin.json and nothing else, so a fix merged without a bump is a fix that reaches no
installed copy - and nothing says so. That was the state of this repository for six weeks: tag
v0.2.0 on 19.08, ten commits on main after it, `plugin.json` still at 0.2.0, and installed copies
pinned to a commit that lacked the guard the tenth commit added. Every one of those ten pull
requests was green.

What ships is decided by exclusion, not by a list. The plugin installs the whole repository, and the
set of shipped paths grows - action.yml did not exist when this check was written - while the set of
paths only this repository reads (its CI, its own Makefile, its out-of-scope notes) is small and
stable. A list of shipped paths would go silently out of date the day a new one appeared, which is
the failure this check exists to catch; a list of repository-only paths that is out of date asks for
one bump too many, loudly. `example/` ships: the skill tells the agent to read it.

The comparison is between two trees - the ref and the working tree - so a shallow checkout is
enough, and locally an uncommitted change counts. Two pull requests that both raise 0.3.0 to 0.3.1
are each green against the base they were opened on; the second merges as 0.3.1 with both changes
in it, which still reaches installs. The check is about the version moving, not about one bump per
change.
"""
import argparse
import json
import os
import re
import subprocess
import sys

# Paths the plugin carries but nothing installed reads: this repository's own CI and housekeeping,
# and the pages a person reads on GitHub. Everything else is shipped - see the docstring for why the
# list is of the exceptions. A directory ends with a slash.
REPO_ONLY = (
    ".github/",
    ".out-of-scope/",
    ".gitignore",
    "renovate.json",
    "Makefile",            # this repository's gate; the consumer's is templates/Makefile, which ships
    "README.md",
    "LICENSE",
)

VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required:  pip install pyyaml")


def _utf8_stdout():
    """See the same helper in docs_check.py: ids and titles come out of files that may be written
    in any language, and a legacy console code page dies on the first character outside it."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def read_json(path, problems):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as e:
        problems.append("cannot read {0}: {1}".format(path, e))
    except ValueError as e:
        problems.append("{0} does not parse: {1}".format(path, e))
    return None


def skill_name(path, problems):
    """The `name:` from a SKILL.md frontmatter block."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        problems.append("cannot read {0}: {1}".format(path, e))
        return None
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        problems.append("{0} has no frontmatter".format(path))
        return None
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        problems.append("{0}: frontmatter does not parse: {1}".format(path, e))
        return None
    if not isinstance(fm, dict) or not fm.get("name"):
        problems.append("{0}: frontmatter carries no name".format(path))
        return None
    return str(fm["name"])


def check_template_pins(root, plugin, problems):
    """The version a template pins is the version that ships it.

    templates/workflow-check.yaml names this repository as an action at a tag, and a project copies
    that line as its pin. A template shipped at 0.4.0 that still says @v0.3.0 sets up every new
    project one release behind, with the skill that set it up describing checks it is not running;
    one that says @v0.5.0 pins a tag that may not exist yet. So the number lives in plugin.json and in the template, and this holds them equal: a
    release that raises one and not the other fails here, in the pull request that makes it.
    """
    m = re.match(r"^https?://github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?/?$",
                 str(plugin.get("repository") or ""))
    version = plugin.get("version")
    templates = os.path.join(root, "templates")
    if not m or not version or not os.path.isdir(templates):
        return
    # A `uses:` line, commented out or not - an example in a comment is copied as readily as a step.
    # A placeholder (`@<tag>`) in prose is not a pin.
    pin = re.compile(r"uses:\s*[\"']?" + re.escape(m.group(1)) + r"@([^\s\"'`<][^\s\"'`]*)")
    for name in sorted(os.listdir(templates)):
        path = os.path.join(templates, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for ref in sorted(set(pin.findall(fh.read()))):
                if ref != "v" + str(version):
                    problems.append("templates/{0} pins {1}@{2}, and the version shipping it is {3} "
                                    "- a project copying it would pin checks other than the ones its skill describes"
                                    .format(name, m.group(1), ref, version))


def check(root):
    problems = []
    plugin_dir = os.path.join(root, ".claude-plugin")
    plugin_path = os.path.join(plugin_dir, "plugin.json")

    if not os.path.isfile(plugin_path):
        # "Not checked" and "nothing wrong" are different statements, and saying both in one run is
        # how a report stops being read. Returning None rather than an empty list is what lets the
        # caller tell them apart.
        print("no {0} - packaging not checked".format(os.path.relpath(plugin_path, root)))
        return None

    plugin = read_json(plugin_path, problems)
    if plugin is None:
        return problems

    name = plugin.get("name")
    if not name:
        problems.append("plugin.json carries no name")

    # Every declared skill directory must actually hold a skill. This is the check the schema
    # validator does not make, and the one whose absence produces an empty plugin.
    entries = plugin.get("skills") or []
    if not entries:
        problems.append("plugin.json declares no skills - the plugin would ship nothing")
    skill_names = []
    for entry in entries:
        folder = os.path.normpath(os.path.join(root, str(entry)))
        skill_md = os.path.join(folder, "SKILL.md")
        if not os.path.isdir(folder):
            problems.append("skills[]: {0} is not a directory".format(entry))
            continue
        if not os.path.isfile(skill_md):
            problems.append("skills[]: {0} holds no SKILL.md - the plugin would install with this "
                            "entry contributing nothing".format(entry))
            continue
        got = skill_name(skill_md, problems)
        if got:
            skill_names.append((entry, got))

    # The installation directory is named by the skill, so a plugin shipping exactly one skill and
    # naming itself something else is the rename that half happened.
    if name and len(skill_names) == 1 and skill_names[0][1] != name:
        problems.append("plugin.json name is {0!r}, but the skill it ships is {1!r} ({2}/SKILL.md)"
                        .format(name, skill_names[0][1], skill_names[0][0]))

    check_template_pins(root, plugin, problems)

    market_path = os.path.join(plugin_dir, "marketplace.json")
    if os.path.isfile(market_path):
        market = read_json(market_path, problems)
        if market is not None:
            listed = market.get("plugins") or []
            if not listed:
                problems.append("marketplace.json lists no plugins")
            for item in listed:
                source = os.path.normpath(os.path.join(root, str(item.get("source") or ".")))
                if not os.path.isfile(os.path.join(source, ".claude-plugin", "plugin.json")):
                    problems.append("marketplace.json: source {0!r} has no plugin.json"
                                    .format(item.get("source")))
            if name and not any(i.get("name") == name for i in listed):
                problems.append("marketplace.json lists {0}, but the plugin here is named {1!r}"
                                .format(sorted(repr(i.get("name")) for i in listed), name))
    return problems


def git(root, *args):
    return subprocess.run(["git", "-C", root] + list(args),
                          capture_output=True, text=True, check=True).stdout


def parse_version(text):
    """`0.3.0` -> (0, 3, 0). A pre-release or build suffix is ignored, so `0.3.0-rc1` -> `0.3.0`
    does not count as raising the version; nothing here publishes pre-releases."""
    m = VERSION.match(str(text or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def shipped(path):
    return not any(path == p or (p.endswith("/") and path.startswith(p)) for p in REPO_ONLY)


def check_version_against(root, ref):
    """A change to what ships, compared with REF, has to come with a higher version than REF's."""
    problems = []
    try:
        # `--no-renames`, so that a file moved out of a shipped directory is seen leaving it.
        changed = git(root, "diff", "--name-only", "--no-renames", "--relative", ref, "--").splitlines()
        changed += git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    except (subprocess.CalledProcessError, OSError) as e:
        detail = getattr(e, "stderr", "") or str(e)
        return ["could not compare with {0}: {1}".format(ref, detail.strip())]

    ships = sorted(p for p in set(changed) if shipped(p))
    if not ships:
        print("nothing that ships differs from {0} - the version does not have to move".format(ref))
        return problems

    try:
        theirs = json.loads(git(root, "show", "{0}:./.claude-plugin/plugin.json".format(ref)))
    except subprocess.CalledProcessError:
        print("no .claude-plugin/plugin.json on {0} - no version to raise".format(ref))
        return problems
    except ValueError as e:
        return ["plugin.json on {0} does not parse: {1}".format(ref, e)]

    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            ours = json.load(fh)
    except (OSError, ValueError) as e:
        return ["cannot read plugin.json here: {0}".format(e)]

    old, new = theirs.get("version"), ours.get("version")
    if parse_version(new) is None:
        return ["plugin.json version {0!r} is not MAJOR.MINOR.PATCH".format(new)]
    if parse_version(old) is not None and parse_version(new) <= parse_version(old):
        shown = ships[:8] + (["... {0} more".format(len(ships) - 8)] if len(ships) > 8 else [])
        problems.append(
            "{0} shipped file{1} changed against {2}, and plugin.json still says {3} ({2}: {4}). "
            "`claude plugin update` compares that number and nothing else, so without a higher one "
            "this change reaches no installed copy. Changed: {5}"
            .format(len(ships), "" if len(ships) == 1 else "s", ref, new, old, ", ".join(shown)))
    else:
        print("version {0} -> {1}: {2} shipped file{3} changed against {4}"
              .format(old, new, len(ships), "" if len(ships) == 1 else "s", ref))
    return problems


def main():
    ap = argparse.ArgumentParser(description="Packaging manifests against the skill they ship")
    ap.add_argument("--root", metavar="PATH", default=".",
                    help="the repository root (default: the working directory)")
    ap.add_argument("--against", metavar="REF",
                    help="also require a higher version than REF's when anything that ships "
                         "differs from REF (CI on a pull request: the base branch)")
    args = ap.parse_args()

    _utf8_stdout()
    root = os.path.abspath(args.root)
    problems = check(root)
    if args.against:
        if problems is None:
            # No packaging here: there is no version to raise, and that is said rather than passed.
            print("no plugin.json - nothing to compare with {0}".format(args.against))
        else:
            problems += check_version_against(root, args.against)
    if problems is None:
        return 0
    if problems:
        print("Packaging is inconsistent:")
        for p in problems:
            print("  - {0}".format(p))
        return 1
    print("packaging manifests agree with the skill they ship")
    return 0


if __name__ == "__main__":
    sys.exit(main())
