from __future__ import annotations

import argparse
import json

from .grader import grade_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade a locked AI Analyst course run")
    parser.add_argument("command", choices=("grade",))
    parser.add_argument("--run", required=True)
    parser.add_argument("--trial-id")
    parser.add_argument("--judge-model", default="claude-opus-4-6")
    args = parser.parse_args()
    result = grade_run(
        run_root=args.run,
        trial_id=args.trial_id,
        judge_model=args.judge_model,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
