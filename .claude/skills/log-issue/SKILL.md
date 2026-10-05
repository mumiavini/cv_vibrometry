---
name: log-issue
description: Append a new issue or update an existing one in this project's issues.md (bug/performance log at the repo root). Use whenever a bug, crash, or performance problem is identified in this project, or whenever a previously logged issue gets fixed. Triggers on "log this issue", "add to issues.md", "mark issue as solved/fixed", "update the issues log".
---

# log-issue

Maintains `issues.md` at the repo root as a running, append-only history of
bugs and performance problems in this project and how they were fixed.
Never delete or rewrite a past entry's `Symptom`/`Root cause` — only append
a `Fix` and flip its status when it's resolved. The log is the project's
memory of what broke and why; treat past entries as historical record.

## Format

`issues.md` is a flat list of entries, **newest issue first**, each a level-2
heading:

```markdown
## [OPEN|SOLVED] <short title of the problem>

**Date opened:** YYYY-MM-DD
**Date solved:** YYYY-MM-DD   <- only present once solved
**Area:** <file(s) or module(s) involved>

**Symptom:** what the user observed (error message, slow behavior, wrong
output) — concrete enough to recognize if it happens again.

**Root cause:** why it happens, in terms of the actual code/design, not just
a restatement of the symptom.

**Fix:** <only once SOLVED> what changed, referencing the file/function and,
if available, the commit hash. If the fix is only proposed and not yet
implemented, use a "Proposed fix (not yet implemented):" line instead of
"Fix:" and keep the status `[OPEN]`.
```

## Logging a new issue

1. Read the current `issues.md` (create it with the header below if it does
   not exist yet).
2. Write a new `## [OPEN] ...` entry using the format above, inserted at the
   top of the entry list (immediately after the header/intro, before the
   first existing `##`).
3. Be concrete in `Symptom` and `Root cause` — enough that future-you (or a
   fresh Claude session with no memory of this conversation) could recognize
   the same issue if it recurs, and understand why it happens without
   re-deriving it from the code.
4. Do not include a `Fix` section yet; if a solution direction is already
   known but not applied, add it as `**Proposed fix (not yet implemented):**`
   instead, and keep the status `[OPEN]`.

## Marking an issue solved

1. Find the matching `## [OPEN] ...` entry (match by title/keywords/area,
   not by exact date — the user may describe it in different words than
   when it was logged).
2. Change `[OPEN]` to `[SOLVED]` in the heading.
3. Add a `**Date solved:**` line right after `**Date opened:**`.
4. Add a `**Fix:**` line (replacing any `Proposed fix` line) describing what
   actually changed — file/function touched, and the commit hash if the fix
   has been committed.
5. Leave `Symptom` and `Root cause` untouched unless they turn out to have
   been wrong — in that case correct them but note the correction rather
   than silently rewriting history.

## New file header

If `issues.md` doesn't exist yet, create it with:

```markdown
# Issues Log

Running log of bugs and performance issues found in this project. Every
issue is logged when found (`OPEN`) and updated in place when fixed
(`SOLVED`) — never delete an entry, append the fix to it instead, so this
stays a history of what broke and why.

Newest issue first.

---
```
