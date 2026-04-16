---
description: Critique pending changes (or a target file) against the Eclatech design principles in .impeccable.md
argument-hint: "[file or area to critique — optional; defaults to current diff]"
---

# /critique

Review work against the Eclatech Hub brand, aesthetic, and design principles defined in `.impeccable.md`. Call out concrete violations. Be blunt. Rank issues by severity.

## Step 1 — Load the rubric

Read `/home/user/eclatech-hub/.impeccable.md` in full. This is the source of truth for:
- Brand personality (precise · cinematic · backstage)
- Aesthetic direction (dark-first, Linear/Raycast/Vercel feel, approved typefaces)
- Color system (lime `#bed62f` for actions only; studio identity colors own their context)
- Anti-references (no gradients, no glowing borders, no AI-startup feel, no blue primary buttons, no sidebar-with-accordion nav)
- Design principles (density, studio-color-owns-context, lime-is-sacred, weight-carries-hierarchy, nothing-decorates)

## Step 2 — Determine target

If `$ARGUMENTS` is provided, critique that file/directory/feature.

Otherwise, critique the pending changes:
- `git diff --stat` to see scope
- `git diff` for the actual changes
- `git status` for untracked files

## Step 3 — Evaluate

For each changed surface, judge against every principle in `.impeccable.md`. Produce findings with:
- **Severity**: Blocker · Major · Minor · Nit
- **Principle violated** (quote the rule)
- **Location**: `file:line`
- **Why it fails**
- **Fix**: one concrete sentence

Pay special attention to:
- Lime green used anywhere other than primary action or active/selected state
- Studio context screens where the studio color isn't the dominant accent
- Decorative elements (dividers, gradients, glows, ambient backgrounds) that don't orient the user
- Color used to carry hierarchy where weight/size should
- Light backgrounds, blue primary buttons, gradient text, purple/cyan combos
- Loose spacing, low information density, enterprise-style table chrome
- Unapproved typefaces on new work

## Step 4 — Report

Output format:

```
CRITIQUE — <target>

Blockers
  1. <file:line> — <rule> — <why> — Fix: <one line>
  ...

Major
  ...

Minor
  ...

Nits
  ...

Verdict: ship / revise / rework
```

If nothing violates the rubric, say so in one line and stop. Do not invent issues.

Do not modify files. This command is read-only critique — the user will decide what to fix.
