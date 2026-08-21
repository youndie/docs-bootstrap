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


def main():
    ap = argparse.ArgumentParser(description="Packaging manifests against the skill they ship")
    ap.add_argument("--root", metavar="PATH", default=".",
                    help="the repository root (default: the working directory)")
    args = ap.parse_args()

    _utf8_stdout()
    problems = check(os.path.abspath(args.root))
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
