# Not renaming the repository to `docs-bootstrap-skill`

Considered because the suffix would say plainly what the repository plugs into, and because
repositories that are agent skills often carry it.

Declined for three reasons, in descending weight.

**The skill is one of six things here.** `SKILL.md` sits in the same table as `SPEC.md`,
`templates/`, `scripts/`, `example/` and `WORKFLOW.md`. Naming the repository after its entry point
rather than its subject is how a project ends up called `thing-cli`.

**The repository name is the installation directory name.** The skill is discovered under
`~/.claude/skills/<name>/`, and that directory has to match the `name:` in the frontmatter of
`SKILL.md`. With the current name the install line reads as one thing:

```bash
git clone https://github.com/youndie/docs-bootstrap ~/.claude/skills/docs-bootstrap
```

With a suffix it becomes a clone into a differently named directory, which reads as a typo and has
to be explained in the README.

**The format is meant to outlive the packaging.** `spec_version` exists so that other tools can
read a `docs/` tree and say which version of the format they understand. A name that fixes the
repository to one agent's plugin format narrows it to the packaging that happens to be current.

**What would reopen it:** the repository starting to ship more than one skill. At that point the
subject really would be "skills", and the honest name would be the plural, not the suffix.
