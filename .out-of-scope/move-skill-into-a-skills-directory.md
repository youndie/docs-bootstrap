# Not moving `SKILL.md` into `skills/docs-bootstrap/`

A plugin manifest lists skill directories, and collections of skills put each one under
`skills/<bucket>/<name>/SKILL.md`. The obvious reading is that a plugin requires that layout, which
would mean moving `SKILL.md` out of the repository root — and losing the property that the clone
path is the installation.

Declined, because the premise turned out to be false. `plugin.json` names the repository root as
its one skill directory:

```json
"skills": ["."]
```

and the runtime resolves it. `claude plugin details docs-bootstrap` on the installed plugin reports
`Skills (1) docs-bootstrap`, which is the whole inventory this repository intends to ship. The move
would have bought nothing and cost the install line.

Two things learned while checking, both worth keeping:

- `claude plugin validate --strict` checks that each `skills[]` path **exists**, not that it holds
  a `SKILL.md`. Pointing the array at `./scripts` passes. That gap is why
  [`scripts/plugin_check.py`](../scripts/plugin_check.py) exists.
- Validation passing is not the same as the skill loading. The two were confirmed separately, by
  installing the plugin from a local marketplace and reading the component inventory.

**What would reopen it:** a second skill in this repository. One skill at the root is unambiguous;
two would need somewhere to live, and then the layout the collections use is the right one.
