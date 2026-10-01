# THIS REPOSITORY'S GATE, AND ONLY THIS REPOSITORY'S. Do not copy it into a project being documented:
# it checks docs-bootstrap itself - the example tree, the packaging, the scripts' own behaviour - and
# a copy of an earlier version, dropped into a real project, printed "no docs tree - nothing checked"
# three times and went green having checked nothing. The Makefile for a project is
# templates/Makefile, which takes the checks from check.mk at the version the project pins.
#
# One gate, and CI runs exactly these targets. A local check set that differs from the CI one turns
# "green here, red there" into the normal state of affairs, and people stop reading either. So:
# whatever is not in `make check` is not a gate, and whatever is in it runs the same way in both
# places. The two exceptions are the pull-request checks, which need the branch the change merges
# into; they are `make against`, and CI calls that target too.
#
# THE EXAMPLE IS CHECKED THROUGH THE CONSUMER'S MAKEFILE. `example/` is run through
# templates/Makefile and check.mk exactly as a project would run them, with this checkout standing in
# for the pinned version - so the gate that ships is the gate this repository passes, and a change to
# check.mk or the template is exercised by the first `make check` after it. CI also runs the action
# itself against `example/`; see .github/workflows/check.yaml.

PY ?= python3
BASE ?= origin/main

# The example, as a consumer: its Makefile is the template, its checks are this checkout.
EXAMPLE = $(MAKE) --no-print-directory -C example -f $(CURDIR)/templates/Makefile \
	DOCS_BOOTSTRAP=$(CURDIR) REPOS=. PY=$(PY)

.PHONY: check gate report fix against on-main help

help:
	@echo "make check    - the gate: blocking checks, exactly what CI runs"
	@echo "make report   - non-blocking reports: BDD coverage, code anchors"
	@echo "make fix      - regenerate the backlog index, fill in missing coverage-map lines"
	@echo "make against  - the pull-request checks against BASE (default origin/main)"

check: gate report

# Blocking. The first line is the documentation gate a project gets. The other two are not about
# documents at all and are here for the same reason: the skill's name lives in four places and
# nothing in the runtime compares them, and the scripts' behaviour on an ABSENT subject or on a
# defect the example does not carry is exercised by nothing else - every target above runs them
# against the example, where everything is present and correct.
gate:
	$(EXAMPLE) docs-gate
	$(PY) scripts/plugin_check.py
	$(PY) scripts/script_selftest.py

report:
	$(EXAMPLE) docs-report

fix:
	$(EXAMPLE) docs-fix

# Pull requests: a backlog number taken on the base branch since this one was cut, and a change to
# anything the plugin ships that did not raise the version. BASE has to be fetched; CI does that.
against:
	$(EXAMPLE) docs-against BASE=$(BASE)
	$(PY) scripts/plugin_check.py --against $(BASE)

# Push to the default branch only: `status: draft` there means intent was documented as fact.
on-main:
	$(EXAMPLE) docs-on-main
