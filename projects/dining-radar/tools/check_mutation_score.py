#!/usr/bin/env python
"""Fail the local L1 gate when mutation quality is below its reviewed floor."""

import argparse
import json
from pathlib import Path

DEFAULT_REPORT = Path("coverage/gremlins/gremlins.json")
MINIMUM_SCORE = 80.0


def mutation_score(report_path: Path) -> float:
    """Load the machine report and return its numeric mutation score."""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    score = report["summary"]["percentage"]
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError("Mutation report summary.percentage must be numeric.")
    return float(score)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--minimum", type=float, default=MINIMUM_SCORE)
    arguments = parser.parse_args()

    score = mutation_score(arguments.report)
    print(f"Mutation score: {score:.2f}% (required: {arguments.minimum:.2f}%)")
    return 0 if score >= arguments.minimum else 1


if __name__ == "__main__":
    raise SystemExit(main())
