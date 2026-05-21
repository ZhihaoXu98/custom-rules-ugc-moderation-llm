"""Validate every data/rule_sets/*.yaml against src.schema.RuleSet.

Also enforces filename-stem == slug so the on-disk layout cannot drift
from the in-file identifier. Used by CI and by the /rule-set-audit slash
command. Run: `uv run python scripts/validate_rule_sets.py`.

Exits 0 if every YAML parses and validates; exits 1 if any fails, after
reporting every failure (not just the first) so one run surfaces the
whole picture.
"""

import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from src.schema import RuleSet

RULE_SETS_DIR = Path("data/rule_sets")


def main() -> int:
    paths = sorted(RULE_SETS_DIR.glob("*.yaml"))
    if not paths:
        print(f"no rule sets found in {RULE_SETS_DIR}/", file=sys.stderr)
        return 1

    failures = 0
    for path in paths:
        try:
            data = yaml.safe_load(path.read_text())
            rs = RuleSet.model_validate(data)
            if rs.slug != path.stem:
                raise ValueError(f"slug {rs.slug!r} != filename stem {path.stem!r}")
        except (ValidationError, ValueError, yaml.YAMLError) as err:
            print(f"FAIL {path.name}: {err}", file=sys.stderr)
            failures += 1
            continue
        print(f"OK   {path.name}  ({rs.regime.value}, {len(rs.rules)} rules)")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
