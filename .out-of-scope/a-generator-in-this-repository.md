# Not putting a generator or a site builder in this repository

The format describes documents precisely enough that a tool could write some of them, and precisely
enough that a tool could render them as a website. Both are reasonable things to build. Neither
belongs here.

**A parser in the same repository becomes the specification.** Once the two ship together, the
answer to "what does the format allow?" quietly changes from *read `SPEC.md`* to *read the parser*,
and the document stops being maintained as a contract because it is no longer the thing that
decides. `spec_version` exists precisely so that a consumer can be built somewhere else and state
which version it reads.

**The format has to be usable with no tool at all.** Documents written by hand and checked by
`make check` are the baseline case. Bundling a generator makes it look like the entry ticket.

This is not a claim that no such tool should exist, and it is not a promise that one is coming. It
is a statement about where the boundary of this repository is: a consumer of the format is a
separate repository that pins `example/` and declares the `spec_version` it understands.

**What would reopen it:** nothing about a generator. A renderer that is strictly read-only, adds no
vocabulary and would otherwise have no home is a smaller question, and it would still start as its
own repository.
