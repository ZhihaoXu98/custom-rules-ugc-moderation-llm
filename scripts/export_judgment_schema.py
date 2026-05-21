"""Export Judgment JSON schema to data/judgment_schema.json.

Consumed in Week 6 by vLLM guided decoding (xgrammar). Idempotent; no API calls.
Run: `uv run python scripts/export_judgment_schema.py`.
"""

import json
from pathlib import Path

from src.schema import Judgment


def main() -> None:
    out = Path("data/judgment_schema.json")
    out.write_text(json.dumps(Judgment.model_json_schema(), indent=2) + "\n")


if __name__ == "__main__":
    main()
