"""Reliability evaluation for PawPal+ AI.

Runs every scenario in scenarios.py through the agent and prints a report:
which expectations held, the confidence the system reported, and whether it asked
for human review. Exit code is 1 if any expectation fails, so it can run in CI.

    python evaluate.py            # table + summary
    python evaluate.py -v         # also list every expectation
    python evaluate.py --table    # print the results as a markdown table
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pawpal_ai import PlanningAgent
from scenarios import SCENARIOS, TODAY


def markdown_table(rows) -> str:
    """Results as a parseable markdown table (used in README.md)."""
    lines = ["| Test input (scenario) | Evaluation criteria | Result | Confidence | Human review |",
             "|---|---|---|---|---|"]
    for scenario, result, outcomes in rows:
        passed = sum(ok for _, ok in outcomes)
        criteria = "; ".join(label for label, _ in outcomes)
        status = "Pass" if passed == len(outcomes) else "FAIL"
        lines.append(f"| `{scenario.name}`: {scenario.description} | {criteria} | "
                     f"{status} ({passed}/{len(outcomes)}) | {result.confidence:.2f} "
                     f"{result.confidence_label} | {'yes' if result.needs_human_review else 'no'} |")
    return "\n".join(lines)


def main(verbose: bool = False, table: bool = False) -> int:
    agent_log = Path("logs") / "agent_log.jsonl"
    rows = []
    for scenario in SCENARIOS:
        owner, llm = scenario.build()
        result = PlanningAgent(llm=llm, log_path=agent_log).run(owner, TODAY)
        outcomes = [(label, bool(fn(result, llm))) for label, fn in scenario.expectations]
        rows.append((scenario, result, outcomes))

    if table:
        print(markdown_table(rows))
        return 0 if all(ok for _, _, o in rows for _, ok in o) else 1

    width = max(len(s.name) for s in SCENARIOS)
    print(f"\n{'Scenario':<{width}}  Result  Checks  Confidence  Human review")
    print("-" * (width + 46))
    for scenario, result, outcomes in rows:
        passed = sum(ok for _, ok in outcomes)
        status = "PASS" if passed == len(outcomes) else "FAIL"
        review = "yes" if result.needs_human_review else "no"
        print(f"{scenario.name:<{width}}  {status:<6}  {passed}/{len(outcomes):<5}  "
              f"{result.confidence:.2f} {result.confidence_label:<6}  {review}")
        if verbose or status == "FAIL":
            for label, ok in outcomes:
                print(f"    [{'x' if ok else ' '}] {label}")

    total = sum(len(o) for _, _, o in rows)
    passed = sum(ok for _, _, o in rows for _, ok in o)
    clean = [r.confidence for s, r, _ in rows if s.kind == "clean"]
    risky = [r.confidence for s, r, _ in rows if s.kind == "risky"]
    flagged = sum(r.needs_human_review for _, r, _ in rows)
    print("\nSummary")
    print(f"  expectations met        : {passed}/{total}")
    print(f"  scenarios fully passing : {sum(all(ok for _, ok in o) for _, _, o in rows)}/{len(rows)}")
    print(f"  mean confidence, clean  : {sum(clean) / len(clean):.2f}  ({len(clean)} scenarios)")
    print(f"  mean confidence, risky  : {sum(risky) / len(risky):.2f}  ({len(risky)} scenarios)")
    print(f"  escalated to a person   : {flagged}/{len(rows)}")

    out = Path("logs") / "evaluation_results.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps([{
        "scenario": s.name, "kind": s.kind, "confidence": r.confidence,
        "needs_human_review": r.needs_human_review,
        "expectations": [{"label": label, "passed": ok} for label, ok in o],
    } for s, r, o in rows], indent=2))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main("-v" in sys.argv, "--table" in sys.argv))
