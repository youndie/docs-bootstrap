# check.mk - the docs-bootstrap gate, included by the Makefile of a repository that uses the checks.
#
# NOT COPIED INTO THAT REPOSITORY. Its Makefile (templates/Makefile) includes this file from wherever
# the checks sit at the version the repository pins: `.docs-bootstrap/<ref>/` after a local fetch, or
# the action's own checkout in CI. Everything that decides HOW the documentation is checked lives
# here - which scripts, with which flags, in which order, and the guard that refuses an absent
# subject - so that a fix to any of it reaches every repository with the next version bump instead
# of with the next person who remembers to re-copy a file. The consumer's Makefile keeps only what is
# the consumer's: where the tree is, which backlog form it keeps, and checks of its own.
#
# The targets are prefixed `docs-` so that they cannot collide with a target of the project's own,
# and the consumer's Makefile maps its `gate`, `report` and `fix` onto them.
#
# DOCS_BOOTSTRAP is the directory this file is in; the including Makefile sets it.

DOCS ?= docs
BACKLOG ?= backlog.md
BACKLOG_FORM ?= files
REPOS ?= ..
PY ?= python3
ANCHORS_ARGS ?=

DOCS_BOOTSTRAP_SCRIPTS := $(DOCS_BOOTSTRAP)/scripts
DOCS_BOOTSTRAP_VERSION := $(shell sed -n -E 's/^[[:space:]]*"version"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p' "$(DOCS_BOOTSTRAP)/.claude-plugin/plugin.json" 2>/dev/null)

# The revision of templates/Makefile this file was written against. The consumer's Makefile is the
# one file that is still copied, so it is the one file that can fall behind without anybody being
# told; it states its revision and this says when that is not the current one. A warning, not an
# error: a version bump must not turn every consumer red over a file that still works.
DOCS_BOOTSTRAP_SHIM_CURRENT := 1
ifneq ($(strip $(DOCS_BOOTSTRAP_SHIM)),$(DOCS_BOOTSTRAP_SHIM_CURRENT))
$(warning the Makefile here is revision '$(strip $(DOCS_BOOTSTRAP_SHIM))' of docs-bootstrap's templates/Makefile and $(DOCS_BOOTSTRAP_VERSION) expects revision $(DOCS_BOOTSTRAP_SHIM_CURRENT) - compare it with $(DOCS_BOOTSTRAP)/templates/Makefile)
endif

.PHONY: docs-guard docs-gate docs-report docs-fix docs-against docs-on-main docs-bootstrap-path

# THE SUBJECT HAS TO EXIST BEFORE ANY VERDICT ABOUT IT MEANS ANYTHING. Every script treats a missing
# tree as a mode and says "nothing checked" (SPEC 7: a tool reading the format must), which is right
# for a tool and wrong for a gate: a gate exists because this repository HAS documentation, and a
# deleted docs/, a `git mv` that took it elsewhere or a DOCS that stopped matching is exactly what it
# is for. This repository's own Makefile, copied into a consumer, once printed "no docs tree -
# nothing checked" three times and went green having checked nothing at all.
#
# The backlog is declared rather than detected, for the same reason: detection would read "no items"
# as "no backlog" and pass. `files` is one file per item plus a generated index, `milestones` is a
# single hand-kept file, `none` is the answer "this project keeps no backlog".
docs-guard:
	@test -d "$(DOCS)" || { echo "no docs tree at $(DOCS) - the gate has no subject. Point DOCS at the tree; if it was deleted or moved, that is what this guard is for." >&2; exit 1; }
	@case "$(strip $(BACKLOG_FORM))" in \
	  files) n=$$(ls "$(DOCS)"/backlog/B-*.md 2>/dev/null | wc -l | tr -d ' '); \
	    test "$$n" -gt 0 || { echo "BACKLOG_FORM=files, and there is no $(DOCS)/backlog/B-*.md - the index check would pass on nothing. Lost to a merge or a move? A project without its first item yet says BACKLOG_FORM=none until it has one." >&2; exit 1; }; \
	    subject="$$n backlog items";; \
	  milestones) test -f "$(BACKLOG)" || { echo "BACKLOG_FORM=milestones, and there is no $(BACKLOG)" >&2; exit 1; }; \
	    subject="the backlog in $(BACKLOG)";; \
	  none) subject="no backlog, as declared";; \
	  *) echo "BACKLOG_FORM='$(BACKLOG_FORM)': expected files, milestones or none" >&2; exit 1;; \
	esac; \
	echo "docs-bootstrap $(DOCS_BOOTSTRAP_VERSION) from $(DOCS_BOOTSTRAP): $(DOCS)/ present, $$subject"

# Blocking. A failure here means the documentation contradicts itself, which is a defect and not a
# matter of opinion.
docs-gate: docs-guard
ifeq ($(strip $(BACKLOG_FORM)),files)
	$(PY) "$(DOCS_BOOTSTRAP_SCRIPTS)/backlog_index.py" --check --docs "$(DOCS)" --backlog "$(BACKLOG)"
endif
	$(PY) "$(DOCS_BOOTSTRAP_SCRIPTS)/docs_check.py" --docs "$(DOCS)" --backlog "$(BACKLOG)"
	$(PY) "$(DOCS_BOOTSTRAP_SCRIPTS)/coverage_map.py" --check --docs "$(DOCS)"

# Non-blocking, on purpose, and read by a person. bdd_report counts scenarios; demanding a percentage
# is meaningless while acceptance is done by hand. code_anchors goes stale because of a refactor in
# somebody else's repository rather than because of an edit here, and it cannot tell a live path
# from one quoted as obsolete. ANCHORS_ARGS=--check makes the second one blocking once its list of
# stale anchors has reached zero and the team decides to keep it there.
docs-report: docs-guard
	$(PY) "$(DOCS_BOOTSTRAP_SCRIPTS)/bdd_report.py" --docs "$(DOCS)" --repos "$(REPOS)"
	$(PY) "$(DOCS_BOOTSTRAP_SCRIPTS)/code_anchors.py" --docs "$(DOCS)" --repos "$(REPOS)" $(ANCHORS_ARGS)

# Regenerates the backlog index and appends the coverage-map lines that are missing. The
# descriptions it writes are placeholders; finishing them is the author's.
docs-fix:
ifeq ($(strip $(BACKLOG_FORM)),files)
	$(PY) "$(DOCS_BOOTSTRAP_SCRIPTS)/backlog_index.py" --docs "$(DOCS)" --backlog "$(BACKLOG)"
endif
	$(PY) "$(DOCS_BOOTSTRAP_SCRIPTS)/coverage_map.py" --fix --docs "$(DOCS)"

# Pull requests: an item number that was free when the branch was cut and has since been taken by a
# branch that merged first. BASE is the ref of the branch this one merges into, already fetched.
# The action runs this before the gate; why, and when it is only a backstop, is written there.
docs-against: docs-guard
	@test -n "$(strip $(BASE))" || { echo "BASE is not set - the branch this one merges into, e.g. make docs-against BASE=origin/main" >&2; exit 1; }
ifeq ($(strip $(BACKLOG_FORM)),files)
	$(PY) "$(DOCS_BOOTSTRAP_SCRIPTS)/backlog_index.py" --against "$(BASE)" --docs "$(DOCS)"
else
	@echo "BACKLOG_FORM=$(strip $(BACKLOG_FORM)): no item files, so no numbers to compare with $(BASE)"
endif

# The default branch only: `status: draft` is legal in a pull request, where it means "this branch
# will make it true", and a defect the moment it merges.
docs-on-main: docs-guard
	$(PY) "$(DOCS_BOOTSTRAP_SCRIPTS)/docs_check.py" --on-main --docs "$(DOCS)" --backlog "$(BACKLOG)"

# Where the checks this Makefile runs come from. The action compares it with its own directory, so
# that a workflow pinning a version over a Makefile that still runs copied scripts fails instead of
# reporting a version it is not running.
docs-bootstrap-path:
	@cd "$(DOCS_BOOTSTRAP)" && pwd -P
