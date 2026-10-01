# Not shipping the checks as a Python package or a git submodule

The checks reach a documented repository at a version that repository pins: a GitHub Action named
by tag in its workflow, and a Makefile that reads that same tag and fetches the same files for a
local run (see `templates/Makefile` and `action.yml`). Before settling on that, the two other ways
to give a project one pinned version were considered, and so was keeping the copies.

**Keeping copies as the default — declined.** It is the route this repository started with, and it
is the reason for the change: across one portfolio, 18 copies of `backlog_index.py` were in three
versions and 11 of them lacked a guard that had been fixed upstream for weeks. A copy is a pin
nobody bumps. It stays documented as the offline fallback (`DOCS_BOOTSTRAP=<dir>`), because a
project that cannot reach GitHub at build time still deserves a gate.

**A package on PyPI — declined.** A `requirements` line is one pin, readable by CI and by a laptop
alike, and Renovate bumps it; on that point it is as good as the action. It loses on everything
around it: a publishing pipeline and an account for a handful of scripts, a virtual environment in
every project that has no other Python in it, and - the deciding part - the gate itself would not
travel. Which scripts run, with which flags, and the guard that refuses an absent subject are a
Makefile's worth of decisions, and a package of scripts leaves each project to write those again,
which is exactly how the copied Makefiles came to differ.

**A git submodule — declined.** Also one pin, a commit in the project's tree, and it works offline
once cloned. But every clone needs `--recursive` and every checkout `submodules: true`, a forgotten
`submodule update` runs the old checks without a word, and Renovate's submodule support is off by
default and follows a branch rather than tags. It trades a fetch the Makefile does on its own for a
step every person and every workflow has to remember.

**What would reopen it:** a consumer that cannot run GitHub Actions at all and needs more than the
fallback - a second CI system becoming common among the projects that use this format. The Makefile
half already works anywhere `make`, `curl` and Python do; what would be missing is a second place to
write the pin, and that is the question a reopening has to answer without making it two pins.
