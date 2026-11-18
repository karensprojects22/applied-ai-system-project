"""PlanningAgent: the orchestration layer of PawPal+ AI.

One run is a short, bounded loop:

    CHECK INPUTS -> PLAN -> VERIFY -> (CRITIQUE -> REVISE -> PLAN -> VERIFY)* -> ADVISE -> EXPLAIN -> SCORE

* PLAN uses the original ``Scheduler`` from pawpal_system.py.
* VERIFY runs deterministic guardrail checks on the result.
* CRITIQUE decides what failed and which fix, if any, is allowed. The only automatic
  fix is to switch to a "critical-first" ordering so medication is placed before
  anything else (the ``required`` idea from the Module 2 reflection).
* If a critical task still cannot fit, the agent does NOT guess. It stops and asks
  for a human decision (human-in-the-loop).
* ADVISE retrieves guidance from the knowledge base (RAG) and finds care gaps.
* EXPLAIN writes a cited explanation, via an LLM if one is configured and its output
  passes the output guardrails, otherwise via a template.
* SCORE combines the evidence into a confidence value and a review decision.

Every step is appended to a trace and, optionally, to a JSONL log file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from pawpal_system import DailyPlan, Owner, Scheduler, Task

from .advisor import Advice, CareGap, build_advice, find_care_gaps
from .guardrails import (
    Check, Finding, check_hazards, check_task_inputs, is_critical, verify_plan,
)
from .knowledge_base import KnowledgeBase
from .llm import LLMClient
from .narrator import generate_narrative

# Confidence weights (sum to 1.0). Documented in the README.
WEIGHTS = {"verification": 0.4, "retrieval": 0.3, "completeness": 0.2, "grounding": 0.1}
REVIEW_THRESHOLD = 0.6      # below this, a person should look at the plan
CRITICAL_CAP = 0.4          # confidence can never exceed this if a critical task is dropped


class CriticalFirstScheduler(Scheduler):
    """Scheduler that places critical tasks (medication etc.) before everything else.

    Only the ordering changes. Placement, budget handling and conflict resolution are
    inherited unchanged from the original Scheduler.
    """

    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        ordered = super().sort_tasks(tasks)
        # sorted() is stable, so the original priority/time order holds inside each group.
        return sorted(ordered, key=lambda t: not is_critical(t, self.owner.find_pet(t.pet_id)))


@dataclass
class AgentResult:
    plan: DailyPlan
    checks: list[Check]
    findings: list[Finding]
    advice: list[Advice]
    gaps: list[CareGap]
    revisions: list[str]
    narrative: str
    narrative_source: str
    confidence: float
    confidence_label: str
    breakdown: dict
    needs_human_review: bool
    review_reasons: list[str]
    trace: list[dict] = field(default_factory=list)

    @property
    def all_checks_passed(self) -> bool:
        return all(c.passed for c in self.checks)


def confidence_label(score: float) -> str:
    return "High" if score >= 0.8 else "Medium" if score >= REVIEW_THRESHOLD else "Low"


class PlanningAgent:
    def __init__(
        self,
        kb: Optional[KnowledgeBase] = None,
        llm: Optional[LLMClient] = None,
        log_path: Optional[Path | str] = None,
        max_iterations: int = 3,
    ):
        self.kb = kb or KnowledgeBase()
        self.llm = llm
        self.log_path = Path(log_path) if log_path else None
        self.max_iterations = max(1, max_iterations)

    # ------------------------------------------------------------------ main loop
    def run(self, owner: Owner, on_date: Optional[date] = None) -> AgentResult:
        on_date = on_date or date.today()
        trace: list[dict] = []

        def log(step: str, detail: str) -> None:
            trace.append({"step": step, "detail": detail})

        findings: list[Finding] = []
        review_reasons: list[str] = []
        revisions: list[str] = []

        # 1. Input guardrails
        findings += check_task_inputs(owner)
        findings += check_hazards(owner, self.kb)
        log("check_inputs", f"{len(findings)} finding(s)")

        # 2. Plan, verify, critique, revise
        strategy = "priority"
        plan: DailyPlan
        checks: list[Check] = []
        resolved = False
        for attempt in range(1, self.max_iterations + 1):
            scheduler = (CriticalFirstScheduler(owner) if strategy == "critical_first"
                         else Scheduler(owner))
            plan = scheduler.generate_plan(on_date)
            checks = verify_plan(plan, owner, on_date)
            failed = [c for c in checks if not c.passed]
            log("plan", f"attempt {attempt}, strategy={strategy}, "
                        f"{len(plan.scheduled_items)} scheduled, {len(plan.skipped_tasks)} skipped")
            log("verify", f"{len(checks) - len(failed)}/{len(checks)} checks passed"
                          + (f"; failed: {', '.join(c.name for c in failed)}" if failed else ""))
            if not failed:
                resolved = True
                break

            names = {c.name for c in failed}
            if "critical_tasks_scheduled" in names and strategy == "priority":
                detail = next(c.detail for c in failed if c.name == "critical_tasks_scheduled")
                revisions.append(f"{detail} was dropped in the first draft, so critical tasks "
                                 "were placed before everything else")
                log("critique", f"critical task skipped ({detail}); switching to critical_first")
                strategy = "critical_first"
                continue

            # No automatic fix is allowed for anything else: stop and ask a person.
            if "critical_tasks_scheduled" in names:
                detail = next(c.detail for c in failed if c.name == "critical_tasks_scheduled")
                if revisions:  # the earlier "fix" did not work, so do not claim it did
                    revisions[-1] = ("placing critical tasks first did not help: "
                                     f"{detail} still cannot fit")
                findings.append(Finding(
                    "critical", "critical_task_unresolvable",
                    f"{detail} cannot fit even when placed first. Increase the time budget "
                    "or decide what to drop."))
                review_reasons.append(f"critical task not scheduled: {detail}")
            others = [c for c in failed if c.name != "critical_tasks_scheduled"]
            for check in others:
                findings.append(Finding("critical", f"check_failed_{check.name}",
                                        f"Plan failed {check.name}: {check.detail}"))
                review_reasons.append(f"plan failed {check.name}")
            log("critique", "no automatic fix available; escalating to a person")
            resolved = True  # handled: escalated rather than silently accepted
            break
        if not resolved:
            findings.append(Finding("critical", "iteration_limit",
                                    "The planner hit its iteration limit with failing checks."))
            review_reasons.append("iteration limit reached with failing checks")

        # 3. Retrieval-grounded advice and care-gap review
        scheduled_tasks = [item.task for item in plan.scheduled_items]
        advice = build_advice(owner, scheduled_tasks, self.kb)
        gaps = find_care_gaps(owner, plan, self.kb, on_date)
        weak = sum(1 for a in advice if not a.grounded)
        log("retrieve", f"{len(advice) - weak} grounded, {weak} abstained, {len(gaps)} care gap(s)")
        for gap in gaps:
            findings.append(Finding("info", "care_gap", gap.message))

        # 4. Explanation (LLM if available and safe, otherwise template)
        narrative, source, problems = generate_narrative(
            self.llm, plan, owner, advice, gaps, findings, revisions)
        log("explain", f"source={source}" + (f"; rejected model output: {'; '.join(problems)}"
                                             if problems else ""))
        if problems:
            findings.append(Finding("info", "llm_output_rejected",
                                    "Model output failed guardrails; used the template instead: "
                                    + "; ".join(problems)))

        # 5. Confidence and human-in-the-loop decision
        breakdown = self._score(plan, owner, on_date, checks, advice, source)
        confidence = self._combine(breakdown, findings)
        label = confidence_label(confidence)

        for f in findings:
            if f.code in ("hazard_mention", "possible_injection"):
                review_reasons.append(f.message)
        if confidence < REVIEW_THRESHOLD:
            review_reasons.append(f"confidence {confidence:.2f} is below {REVIEW_THRESHOLD}")
        review_reasons = list(dict.fromkeys(review_reasons))  # de-duplicate, keep order
        needs_review = bool(review_reasons)
        log("score", f"confidence={confidence:.2f} ({label}); human review "
                     f"{'REQUIRED' if needs_review else 'not needed'}")

        result = AgentResult(
            plan=plan, checks=checks, findings=findings, advice=advice, gaps=gaps,
            revisions=revisions, narrative=narrative, narrative_source=source,
            confidence=confidence, confidence_label=label, breakdown=breakdown,
            needs_human_review=needs_review, review_reasons=review_reasons, trace=trace,
        )
        self._write_log(owner, on_date, result)
        return result

    # ------------------------------------------------------------------- scoring
    @staticmethod
    def _score(plan: DailyPlan, owner: Owner, on_date: date, checks: list[Check],
               advice: list[Advice], narrative_source: str) -> dict:
        due = [t for t in owner.get_all_tasks() if t.is_due(on_date)]
        return {
            "verification": sum(c.passed for c in checks) / len(checks) if checks else 0.0,
            "retrieval": (sum(a.relevance for a in advice) / len(advice)) if advice else 1.0,
            "completeness": (len(plan.scheduled_items) / len(due)) if due else 1.0,
            "grounding": 0.5 if narrative_source == "template-fallback" else 1.0,
        }

    @staticmethod
    def _combine(breakdown: dict, findings: list[Finding]) -> float:
        score = sum(WEIGHTS[k] * min(1.0, breakdown[k]) for k in WEIGHTS)
        if any(f.severity == "critical" for f in findings):
            score = min(score, CRITICAL_CAP)
        return round(score, 3)

    # ------------------------------------------------------------------- logging
    def _write_log(self, owner: Owner, on_date: date, result: AgentResult) -> None:
        if self.log_path is None:
            return
        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "owner": owner.name,
            "date": on_date.isoformat(),
            "pets": [p.name for p in owner.pets],
            "confidence": result.confidence,
            "needs_human_review": result.needs_human_review,
            "review_reasons": result.review_reasons,
            "narrative_source": result.narrative_source,
            "findings": [{"severity": f.severity, "code": f.code} for f in result.findings],
            "trace": result.trace,
        }
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
        except OSError:
            pass  # logging must never break planning
