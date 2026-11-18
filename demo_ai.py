"""Presentation demo for PawPal+ AI.  Run:  python demo_ai.py

Shows three runs of the same agent:
  1. a normal day
  2. a crowded day where the first draft drops the medication and the agent fixes it
  3. an impossible day where the agent refuses to guess and asks a person

Set ANTHROPIC_API_KEY to let a real model write the explanation (its output is still
checked by the guardrails). Without a key everything runs offline.
"""

from datetime import date

from main import build_demo_owner
from pawpal_ai import PlanningAgent
from pawpal_ai.llm import default_client
from scenarios import critical_task_cannot_fit, medication_crowded_out


def show(title: str, owner, agent: PlanningAgent) -> None:
    today = date.today()
    result = agent.run(owner, today)
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)

    print("\nAgent trace:")
    for step in result.trace:
        print(f"  {step['step']:<13} {step['detail']}")

    print("\nFinal schedule:")
    for item in result.plan.scheduled_items:
        pet = owner.find_pet(item.task.pet_id)
        print(f"  {item.start:%H:%M}-{item.end:%H:%M}  {item.task.title:<22} [{pet.name}]")
    for skipped in result.plan.skipped_tasks:
        print(f"  SKIPPED  {skipped.task.title}: {skipped.reason}")

    print("\nExplanation (" + result.narrative_source + "):")
    for line in result.narrative.splitlines():
        print("  " + line)

    flags = [f for f in result.findings if f.severity != "info"]
    if flags:
        print("\nFlags:")
        for f in flags:
            print(f"  [{f.severity}] {f.message}")

    parts = ", ".join(f"{k} {v:.2f}" for k, v in result.breakdown.items())
    print(f"\nConfidence: {result.confidence:.2f} ({result.confidence_label})  <- {parts}")
    if result.needs_human_review:
        print("HUMAN REVIEW REQUIRED:")
        for reason in result.review_reasons:
            print(f"  - {reason}")
    else:
        print("Human review: not needed")


if __name__ == "__main__":
    llm = default_client()
    agent = PlanningAgent(llm=llm, log_path="logs/agent_log.jsonl")
    print(f"Explanation model: {llm.name if llm else 'none (offline template)'}")
    show("1. Normal day (Karen's demo data)", build_demo_owner(date.today()), agent)
    show("2. Crowded day: medication would be dropped", medication_crowded_out()[0], agent)
    show("3. Impossible day: medication cannot fit", critical_task_cannot_fit()[0], agent)
