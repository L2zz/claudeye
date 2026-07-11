---
description: Run claudeye on this machine's Claude Code history and summarize where context is being wasted.
---

Analyze my local Claude Code usage with claudeye and give a short, actionable summary of where my context is being wasted. claudeye runs fully locally and sends no data anywhere.

Steps:
1. Pick a scratch output dir (a temp folder).
2. Run claudeye with no-install uvx, writing agent-readable facet files:

   ```bash
   uvx --from git+https://github.com/L2zz/claudeye claudeye \
     --out <scratch>/report.html \
     --data-dir <scratch>/facets \
     $ARGUMENTS
   ```

   Pass through any period/project flags in $ARGUMENTS (e.g. --today, --one-week, --one-month, --all, --project X). If the user gave none, default to --one-week.
3. Read <scratch>/facets/INDEX.md, then advice.txt and the top facet JSONs it points to.
4. Summarize tightly: the biggest context-waste patterns + 2–3 concrete changes. This is a diagnostic, not a data dump.
