from datetime import date
from scenarios import medication_crowded_out
from pawpal_ai import PlanningAgent

owner, _ = medication_crowded_out()
print("INPUT  budget:", owner.available_minutes_per_day, "min")
for t in owner.get_all_tasks():
    print(f"INPUT  {owner.find_pet(t.pet_id).name:<8} {t.title:<20} {t.category:<11} {t.duration_minutes:>2} min  {t.priority.name}")
result = PlanningAgent().run(owner, date(2026, 11, 18))
print("\nOUTPUT schedule:")
for i in result.plan.scheduled_items:
    print(f"  {i.start:%H:%M}-{i.end:%H:%M}  {i.task.title}")
for s in result.plan.skipped_tasks:
    print(f"  skipped: {s.task.title} ({s.reason})")
print("OUTPUT revisions        :", result.revisions)
print("OUTPUT checks passed    :", f"{sum(c.passed for c in result.checks)}/{len(result.checks)}")
print(f"OUTPUT confidence       : {result.confidence:.2f} ({result.confidence_label})")
print("OUTPUT human review     :", result.needs_human_review)
