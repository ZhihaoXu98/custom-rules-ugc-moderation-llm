---
description: Run scripts/validate_rule_sets.py and report. Does not modify rule sets.
allowed-tools: Bash(uv run python scripts/validate_rule_sets.py)
---

Run `uv run python scripts/validate_rule_sets.py` and report results.

**If the script does not yet exist** (expected before Day 4 of Week 1):
- Report that `scripts/validate_rule_sets.py` is missing and stop.
- Do NOT create it. The script is authored separately as part of the Week 1 plan.

**If it runs:**
- On exit 0: report `Rule sets valid.` plus any non-empty summary lines from stdout.
- On non-zero exit: report the failing rule sets and the validator's stderr/stdout **verbatim**. Do NOT attempt to fix the rule sets or the validator.
