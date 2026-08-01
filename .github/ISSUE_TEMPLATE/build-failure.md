---
title: "Build failure - run {{ RUN_ID }}"
labels: ["build-failure", "auto-repair"]
assignees: ["salom600"]
---

## ❌ NovaOS ISO build failed

- **Run ID:** [{{ RUN_ID }}]({{ LOG_URL }})
- **Git SHA:** `{{ GIT_SHA }}`
- **Time:** {{ date }}

## What happens next

1. The `auto-repair` workflow is automatically triggered.
2. It downloads the logs of this failed run and applies deterministic
   fixes for known patterns (missing package, signature errors, disk full, etc.).
3. If it can fix the build, it opens a Pull Request with the patch and
   re-triggers the build workflow.
4. If it cannot fix the build, the auto-repair bot will comment below with
   the offending log excerpt.

## Manual review checklist (only if auto-repair could not fix)

- [ ] Check the failed job's log: {{ LOG_URL }}
- [ ] Identify the failing step
- [ ] Patch locally
- [ ] Push to `main` - the build workflow will run again automatically

> This issue is managed by the NovaOS auto-repair pipeline.
> Do not delete - it will be auto-closed when a successful build lands.
