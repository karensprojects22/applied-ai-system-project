import json
from datetime import date, time

import pytest

from pawpal_ai import PlanningAgent
from pawpal_ai.advisor import build_advice, find_care_gaps
from pawpal_ai.agent import WEIGHTS, CriticalFirstScheduler
from pawpal_ai.knowledge_base import KnowledgeBase
from pawpal_ai.llm import AnthropicClient, default_client
from pawpal_system import Owner, Pet, Priority, Scheduler, Task
import scenarios

TODAY = date(2026, 11, 18)


def test_critical_first_orders_medication_ahead_of_higher_priority_tasks():
    owner, _ = scenarios.medication_crowded_out()
    tasks = owner.get_all_tasks()
    default = [t.title for t in Scheduler(owner).sort_tasks(tasks)]
    critical = [t.title for t in CriticalFirstScheduler(owner).sort_tasks(tasks)]
    assert default[-1] == "Thyroid medication"
    assert critical[0] == "Thyroid medication"


def test_agent_never_edits_the_owners_tasks():
    owner, _ = scenarios.medication_crowded_out()
    before = [(t.id, t.title, t.priority, t.duration_minutes, t.preferred_time, t.last_completed)
              for t in owner.get_all_tasks()]
    PlanningAgent().run(owner, TODAY)
    after = [(t.id, t.title, t.priority, t.duration_minutes, t.preferred_time, t.last_completed)
             for t in owner.get_all_tasks()]
    assert before == after


def test_agent_is_deterministic_without_a_model():
    first = PlanningAgent().run(scenarios.normal_day()[0], TODAY)
    second = PlanningAgent().run(scenarios.normal_day()[0], TODAY)
    assert first.narrative == second.narrative
    assert first.confidence == second.confidence


def test_confidence_weights_sum_to_one_and_score_is_bounded():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)
    for scenario in scenarios.SCENARIOS:
        owner, llm = scenario.build()
        result = PlanningAgent(llm=llm).run(owner, TODAY)
        assert 0.0 <= result.confidence <= 1.0
        assert set(result.breakdown) == set(WEIGHTS)


def test_trace_records_each_stage_in_order():
    result = PlanningAgent().run(scenarios.medication_crowded_out()[0], TODAY)
    steps = [t["step"] for t in result.trace]
    assert steps[0] == "check_inputs" and steps[-1] == "score"
    assert steps.count("plan") == 2 and "critique" in steps
    assert steps.index("critique") < len(steps) - steps[::-1].index("plan") - 1


def test_log_file_gets_one_json_line_per_run(tmp_path):
    log = tmp_path / "nested" / "agent.jsonl"
    agent = PlanningAgent(log_path=log)
    agent.run(scenarios.normal_day()[0], TODAY)
    agent.run(scenarios.critical_task_cannot_fit()[0], TODAY)
    lines = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(lines) == 2
    assert lines[1]["needs_human_review"] is True
    assert lines[0]["trace"][0]["step"] == "check_inputs"
    assert "title" not in json.dumps(lines)  # the log holds codes and counts, not task text


def test_unwritable_log_path_does_not_break_planning(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    result = PlanningAgent(log_path=blocker / "agent.jsonl").run(scenarios.normal_day()[0], TODAY)
    assert result.plan.scheduled_items


def test_iteration_limit_escalates_instead_of_silently_accepting():
    owner, _ = scenarios.medication_crowded_out()
    result = PlanningAgent(max_iterations=1).run(owner, TODAY)
    assert any(f.code == "iteration_limit" for f in result.findings)
    assert result.needs_human_review


def test_original_scheduler_behaviour_is_untouched():
    """The AI layer wraps Scheduler; plain Scheduler output must be unchanged."""
    owner, _ = scenarios.medication_crowded_out()
    plan = Scheduler(owner).generate_plan(TODAY)
    assert "Thyroid medication" in [s.task.title for s in plan.skipped_tasks]


# ------------------------------------------------------------------ advisor
def _dog(*tasks):
    owner = Owner("O", available_minutes_per_day=240, day_start=time(7, 0), day_end=time(21, 0))
    pet = Pet("Rex", "dog")
    owner.add_pet(pet)
    for t in tasks:
        pet.add_task(t)
    return owner, pet


def test_time_already_completed_today_counts_toward_a_care_gap():
    owner, pet = _dog(Task("Morning walk", "walk", 35, Priority.HIGH))
    pet.complete_task(pet.tasks[0].id, TODAY)
    plan = Scheduler(owner).generate_plan(TODAY)
    gaps = find_care_gaps(owner, plan, KnowledgeBase(), TODAY)
    assert not any(g.category == "walk" for g in gaps)


def test_short_walk_is_flagged_with_numbers_and_citation():
    owner, _ = _dog(Task("Quick walk", "walk", 10, Priority.HIGH))
    plan = Scheduler(owner).generate_plan(TODAY)
    gap = next(g for g in find_care_gaps(owner, plan, KnowledgeBase(), TODAY) if g.category == "walk")
    assert (gap.planned_minutes, gap.recommended_minutes) == (10, 30)
    assert "dog_care.md" in gap.message


def test_medication_is_never_second_guessed_as_a_care_gap():
    owner, _ = _dog(Task("Pill", "meds", 1, Priority.HIGH))
    plan = Scheduler(owner).generate_plan(TODAY)
    assert not any(g.category == "meds" for g in find_care_gaps(owner, plan, KnowledgeBase(), TODAY))


def test_advice_abstains_for_species_without_guidance():
    owner = Owner("O", available_minutes_per_day=60)
    pet = Pet("Nibbles", "hamster")
    owner.add_pet(pet)
    task = Task("Fresh food", "feeding", 5)
    pet.add_task(task)
    advice = build_advice(owner, [task], KnowledgeBase())[0]
    assert not advice.grounded and advice.citations == [] and "veterinarian" in advice.note


# ---------------------------------------------------------------------- llm
def test_no_api_key_means_no_client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert default_client() is None


def test_api_key_creates_a_client(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert isinstance(default_client(), AnthropicClient)


def test_network_failure_returns_none_instead_of_raising(monkeypatch):
    import urllib.request

    def boom(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert AnthropicClient("k").complete("sys", "user") is None


def test_task_naming_a_hazard_gets_hazard_guidance_for_its_own_species():
    owner = Owner("O", available_minutes_per_day=60)
    dog, cat = Pet("Rex", "dog"), Pet("Tom", "cat")
    owner.add_pet(dog)
    owner.add_pet(cat)
    for pet in (dog, cat):
        pet.add_task(Task("Chocolate treat", "feeding", 5))
    kb = KnowledgeBase()
    by_pet = {a.pet.name: a.citations[0] for a in build_advice(owner, owner.get_all_tasks(), kb)}
    assert by_pet == {"Rex": "safety_dogs.md#Foods that are toxic to dogs",
                      "Tom": "safety_cats.md#Foods and plants that are toxic to cats"}
