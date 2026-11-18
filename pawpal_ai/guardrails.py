"""Guardrails for PawPal+: checks that run before and after the AI steps.

Three groups:
  * input guardrails   - reject or flag suspicious task text before it goes near a prompt
  * plan verification  - deterministic checks that the schedule is actually valid
  * output guardrails  - make sure generated text is grounded and gives no dosing advice

Nothing here calls a model, so every check is cheap, deterministic and testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from pawpal_system import DailyPlan, Owner, Pet, Task, _to_minutes

from .knowledge_base import KnowledgeBase

MAX_TITLE_LENGTH = 80
MAX_TASK_MINUTES = 480

SEVERITIES = ("info", "warning", "critical")


@dataclass
class Finding:
    """Something the system noticed that a person may want to know about."""
    severity: str          # info | warning | critical
    code: str              # short machine-readable id, e.g. "critical_task_skipped"
    message: str
    task_id: Optional[str] = None


@dataclass
class Check:
    """One verification check and whether the plan passed it."""
    name: str
    passed: bool
    detail: str = ""


# --------------------------------------------------------------------------- critical tasks
_CRITICAL_CATEGORIES = {"meds"}


def is_critical(task: Task, pet: Optional[Pet]) -> bool:
    """A task that must not be dropped: medication, or one tied to a pet's special needs."""
    if task.category.lower() in _CRITICAL_CATEGORIES:
        return True
    if pet and pet.special_needs:
        need_words = {w for w in re.findall(r"[a-z]+", pet.special_needs.lower()) if len(w) > 3}
        title_words = set(re.findall(r"[a-z]+", task.title.lower()))
        return bool(need_words & title_words)
    return False


# --------------------------------------------------------------------------- input guardrails
_INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier)",
    r"disregard (all |any |the )?(previous|prior|above|earlier|instructions)",
    r"system prompt",
    r"you are now",
    r"act as (a|an)\b",
    r"reveal (your|the) (instructions|prompt|key)",
    r"<\s*/?\s*(script|system|assistant)",
    r"api[_ ]?key",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION_RE.search(text or ""))


def check_task_inputs(owner: Owner) -> list[Finding]:
    """Flag task text and values that are empty, oversized, odd or look like prompt injection."""
    findings: list[Finding] = []
    for task in owner.get_all_tasks():
        title = task.title or ""
        if not title.strip():
            findings.append(Finding("warning", "empty_title", "A task has no title.", task.id))
        if len(title) > MAX_TITLE_LENGTH:
            findings.append(Finding(
                "warning", "long_title",
                f"Task title is {len(title)} characters (limit {MAX_TITLE_LENGTH}); "
                "it is shortened before use in any prompt.", task.id))
        if any(not ch.isprintable() for ch in title):
            findings.append(Finding(
                "warning", "unprintable_title",
                f"Task {title[:20]!r} contains control characters.", task.id))
        if looks_like_injection(title):
            findings.append(Finding(
                "warning", "possible_injection",
                f"Task title {title[:30]!r} looks like an instruction to an AI system. "
                "It is withheld from AI prompts and treated as plain data.", task.id))
        if task.duration_minutes > MAX_TASK_MINUTES:
            findings.append(Finding(
                "warning", "implausible_duration",
                f"{title!r} is {task.duration_minutes} min, which is over "
                f"{MAX_TASK_MINUTES // 60} hours. Please double-check it.", task.id))
    return findings


def safe_title(task: Task) -> str:
    """Return a title that is safe to place into a prompt (or a placeholder)."""
    title = "".join(ch for ch in (task.title or "") if ch.isprintable()).strip()
    if not title or looks_like_injection(title):
        return "[task title withheld]"
    return title[:MAX_TITLE_LENGTH]


def check_hazards(owner: Owner, kb: KnowledgeBase) -> list[Finding]:
    """Warn when a task title mentions something the knowledge base lists as toxic for that pet."""
    findings: list[Finding] = []
    for pet in owner.pets:
        hazards = kb.hazard_terms_for(pet.species)
        for task in pet.tasks:
            words = set(re.findall(r"[a-z]+", (task.title or "").lower()))
            for hazard in hazards:
                hit = sorted(words & set(hazard.terms))
                if hit:
                    findings.append(Finding(
                        "warning", "hazard_mention",
                        f"{task.title!r} for {pet.name} mentions {', '.join(hit)}, which can be "
                        f"harmful to a {pet.species}. See {hazard.citation}. "
                        "Please confirm with a veterinarian.", task.id))
                    break
    return findings


# --------------------------------------------------------------------------- plan verification
def verify_plan(plan: DailyPlan, owner: Owner, on_date: date) -> list[Check]:
    """Run deterministic checks on a schedule. Never raises."""
    items = sorted(plan.scheduled_items, key=lambda i: i.start)
    checks: list[Check] = []

    overlaps = [(a, b) for a, b in zip(items, items[1:]) if b.start < a.end]
    checks.append(Check("no_overlaps", not overlaps,
                        "" if not overlaps else
                        "; ".join(f"{a.task.title} / {b.task.title}" for a, b in overlaps)))

    total = plan.total_duration()
    budget = owner.available_minutes_per_day
    checks.append(Check("within_time_budget", total <= budget,
                        f"{total} of {budget} min"))

    start, end = _to_minutes(owner.day_start), _to_minutes(owner.day_end)
    outside = [i for i in items if _to_minutes(i.start) < start or _to_minutes(i.end) > end]
    checks.append(Check("within_day_window", not outside,
                        "" if not outside else ", ".join(i.task.title for i in outside)))

    due_ids = {t.id for t in owner.get_all_tasks() if t.is_due(on_date)}
    seen = [i.task.id for i in plan.scheduled_items] + [s.task.id for s in plan.skipped_tasks]
    missing = due_ids - set(seen)
    checks.append(Check("every_due_task_accounted_for",
                        not missing and len(seen) == len(set(seen)),
                        f"{len(missing)} unaccounted" if missing else ""))

    no_reason = [s.task.title for s in plan.skipped_tasks if not s.reason.strip()]
    checks.append(Check("skips_explained", not no_reason, ", ".join(no_reason)))

    skipped_critical = [s.task.title for s in plan.skipped_tasks
                        if is_critical(s.task, owner.find_pet(s.task.pet_id))]
    checks.append(Check("critical_tasks_scheduled", not skipped_critical,
                        ", ".join(skipped_critical)))
    return checks


# --------------------------------------------------------------------------- output guardrails
_CITATION_RE = re.compile(r"\[([^\[\]]+\.md#[^\[\]]+)\]")
_DOSAGE_RE = re.compile(r"\b\d+(\.\d+)?\s?(mg|mcg|ml|cc|iu|units?|tablets?|pills?)\b", re.IGNORECASE)
_MAX_NARRATIVE_CHARS = 1800


def check_narrative(text: str, allowed_citations: set[str]) -> list[str]:
    """Return the problems with a generated explanation (empty list means it is acceptable)."""
    problems: list[str] = []
    if not text or not text.strip():
        return ["empty response"]
    if len(text) > _MAX_NARRATIVE_CHARS:
        problems.append("response is too long")
    for cited in _CITATION_RE.findall(text):
        if cited not in allowed_citations:
            problems.append(f"cites a source that was not retrieved: {cited}")
    if _DOSAGE_RE.search(text):
        problems.append("contains a dosage, which this assistant must not give")
    if looks_like_injection(text):
        problems.append("contains instruction-like text")
    return problems
