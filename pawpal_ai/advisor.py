"""Grounded advice: retrieve guidance for each task and check the plan against it.

Everything produced here is *extractive*. A note is a sentence copied from a
retrieved chunk and carries that chunk's citation. If nothing relevant enough
is found, the advisor says so instead of inventing guidance (abstention).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from pawpal_system import DailyPlan, Owner, Pet, Task

from .knowledge_base import KnowledgeBase

# Below this relevance the advisor refuses to cite a source.
MIN_RELEVANCE = 0.5


@dataclass
class Advice:
    task: Task
    pet: Pet
    note: str
    citations: list[str] = field(default_factory=list)
    relevance: float = 0.0
    grounded: bool = False


@dataclass
class CareGap:
    pet_name: str
    category: str
    planned_minutes: int
    recommended_minutes: int
    citation: str

    @property
    def message(self) -> str:
        return (f"{self.pet_name} has {self.planned_minutes} min of {self.category} today; "
                f"the guidance suggests at least {self.recommended_minutes} min "
                f"[{self.citation}]")


def _first_sentences(text: str, limit: int = 170) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    out = sentences[0]
    for nxt in sentences[1:]:
        if len(out) + len(nxt) + 1 > limit:
            break
        out += " " + nxt
    return out[:limit + 60]


def build_advice(owner: Owner, tasks: list[Task], kb: KnowledgeBase) -> list[Advice]:
    """Retrieve guidance for each task; abstain when the evidence is weak."""
    advice: list[Advice] = []
    for task in tasks:
        pet = owner.find_pet(task.pet_id)
        if pet is None:
            continue
        # Safety first: a task that names a known hazard gets the hazard guidance, not
        # whatever happens to match its category best.
        words = set(re.findall(r"[a-z]+", (task.title or "").lower()))
        hazard_chunk = next((kb.chunk_by_citation(h.citation)
                             for h in kb.hazard_terms_for(pet.species) if words & set(h.terms)), None)
        if hazard_chunk is not None:
            advice.append(Advice(task, pet, _first_sentences(hazard_chunk.text),
                                 [hazard_chunk.citation], 1.0, True))
            continue
        hits = kb.search(task.category, pet.species,
                         extra_text=f"{task.title} {pet.breed} {pet.special_needs}", k=1,
                         title=task.title)
        if not hits or hits[0].relevance < MIN_RELEVANCE:
            best = hits[0].relevance if hits else 0.0
            advice.append(Advice(
                task, pet,
                f"No reliable guidance found for {pet.species} {task.category} tasks. "
                "Check with a veterinarian.", [], best, False))
            continue
        hit = hits[0]
        advice.append(Advice(task, pet, _first_sentences(hit.chunk.text),
                             [hit.chunk.citation], hit.relevance, True))
    return advice


def find_care_gaps(owner: Owner, plan: DailyPlan, kb: KnowledgeBase, on_date: date) -> list[CareGap]:
    """Compare planned minutes per pet and category against the knowledge base minimums.

    Species-specific minimums (e.g. dogs need a walk) apply even if the pet has no
    such task. General minimums apply only when the pet has a task in that category.
    Time already completed today counts toward the total.
    """
    gaps: list[CareGap] = []
    for pet in owner.pets:
        minutes: dict[str, int] = {}
        for item in plan.scheduled_items:
            if item.task.pet_id == pet.id:
                cat = item.task.category.lower()
                minutes[cat] = minutes.get(cat, 0) + item.task.duration_minutes
        for task in pet.tasks:
            if task.last_completed == on_date:
                cat = task.category.lower()
                minutes[cat] = minutes.get(cat, 0) + task.duration_minutes
        pet_categories = {t.category.lower() for t in pet.tasks}

        seen: set[str] = set()
        # Species-specific rules first so they win over general ones.
        recs = sorted(kb.recommendations_for(pet.species), key=lambda r: r.species == "all")
        for rec in recs:
            if rec.category in seen or rec.category == "meds":
                continue  # never second-guess medication timing or amounts
            specific = rec.species == pet.species.lower()
            if not specific and rec.category not in pet_categories:
                continue
            seen.add(rec.category)
            planned = minutes.get(rec.category, 0)
            if planned < rec.min_minutes:
                gaps.append(CareGap(pet.name, rec.category, planned,
                                    rec.min_minutes, rec.citation))
    return gaps
