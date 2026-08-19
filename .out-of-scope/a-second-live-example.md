# Not shipping a second example taken from a real project

`example/` is synthetic: a three-service library lending system written for this repository. The
alternative on the table was to add a second example lifted from a project that actually uses the
format, on the grounds that a real tree is more convincing than an invented one.

Declined for now.

**A real example cannot be edited to demonstrate a rule.** The synthetic one carries, on purpose, a
feature with `client_entries: []`, a backlog item in every status the vocabulary has, and all three
anchor notations mixed in one tree — because each of those is a rule someone will otherwise get
wrong. A real tree has whatever it happens to have, and the gaps land where the format most needs a
demonstration.

**A real example drags in decisions that are not this repository's to explain.** Every quirk in a
live service document is a claim about somebody's running system, and it goes stale on their
schedule rather than on this repository's.

**One example that is checked end to end beats two that are not.** `make check` runs against
`example/`, and every anchor in every document resolves to a file underneath it. A second tree
doubles that obligation.

**What would reopen it:** the synthetic example turning out to hide a class of problem that only a
real tree produces — a document that no small system could motivate, a check that passes here and
fails everywhere real. That is a finding, and it would arrive as a bug report rather than as a
preference.
