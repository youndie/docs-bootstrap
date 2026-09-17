# One gate, and CI runs exactly this target.
#
# A local check set that differs from the CI one turns "green here, red there" into the normal
# state of affairs, and people stop reading either. So: whatever is not in `make check` is not a
# gate, and whatever is in it runs the same way in both places.
#
# DOCS points at the documentation tree. In this repository it is the reference example; in a real
# project it is `docs`, which is the default of every script.

DOCS ?= example/docs
BACKLOG ?= example/backlog.md
REPOS ?= example
PY ?= python3

.PHONY: check gate report fix help

help:
	@echo "make check   - the gate: blocking checks, exactly what CI runs"
	@echo "make report  - non-blocking reports: BDD coverage, code anchors"
	@echo "make fix     - regenerate the backlog index, fill in missing coverage-map lines"
	@echo ""
	@echo "Point them at another tree with:  make check DOCS=docs BACKLOG=backlog.md"

check: gate report

# Blocking. Any of these failing means the documentation is internally inconsistent, which is a
# defect in the documentation and not a matter of opinion. The last two are not about the documents
# at all and are here for the same reason: the skill's name lives in four places and nothing in the
# runtime compares them, and the scripts' behaviour on an ABSENT tree is exercised by nothing else —
# every target above runs them against the example, where everything is present.
gate:
	$(PY) scripts/backlog_index.py --check --docs $(DOCS) --backlog $(BACKLOG)
	$(PY) scripts/docs_check.py --docs $(DOCS) --backlog $(BACKLOG)
	$(PY) scripts/coverage_map.py --check --docs $(DOCS)
	$(PY) scripts/plugin_check.py
	$(PY) scripts/script_selftest.py

# Non-blocking, on purpose.
#
# bdd_report counts scenarios; demanding a percentage is meaningless while acceptance is done by
# hand. code_anchors goes stale because of a refactor in somebody else's repository rather than
# because of an edit here, and it cannot tell a live path from one quoted as obsolete ("the item
# said infra/k8s/, the chart is actually elsewhere"). Both are read by a person.
report:
	$(PY) scripts/bdd_report.py --docs $(DOCS) --repos $(REPOS)
	$(PY) scripts/code_anchors.py --docs $(DOCS) --repos $(REPOS)

fix:
	$(PY) scripts/backlog_index.py --docs $(DOCS) --backlog $(BACKLOG)
	$(PY) scripts/coverage_map.py --fix --docs $(DOCS)
