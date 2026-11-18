# PawPal+ AI architecture

Source of truth: [`system_diagram.mmd`](system_diagram.mmd). Rendered below by GitHub.

```mermaid
flowchart TD
    OWNER["Owner input<br/>pets, tasks, time budget"] --> IG["Input guardrails<br/>injection, bad values, toxic foods"]
    IG --> PLAN["PLAN<br/>original Scheduler"]
    PLAN --> VERIFY["VERIFY<br/>6 deterministic checks"]
    VERIFY -->|all pass| ADVISE
    VERIFY -->|critical task dropped| CRITIQUE["CRITIQUE"]
    CRITIQUE -->|first time| REVISE["REVISE<br/>critical-first ordering"]
    REVISE --> PLAN
    CRITIQUE -->|cannot be fixed| HUMAN
    KB[("Knowledge base<br/>8 markdown files")] --> RET["Retriever<br/>BM25 plus relevance score"]
    RET --> ADVISE["ADVISE<br/>cited guidance and care gaps<br/>abstains when relevance is below 0.5"]
    ADVISE --> EXPLAIN["EXPLAIN<br/>template, or optional LLM"]
    EXPLAIN --> OG["Output guardrails<br/>real citations, no dosages"]
    OG -->|rejected| TEMPLATE["Template fallback"]
    OG -->|accepted| SCORE
    TEMPLATE --> SCORE["SCORE<br/>confidence plus review decision"]
    SCORE -->|review needed| HUMAN["HUMAN IN THE LOOP<br/>a person decides"]
    SCORE -->|no review needed| OUT["Output<br/>plan, explanation, confidence"]
    HUMAN --> OUT
    SCORE --> LOG[("logs/agent_log.jsonl")]
    subgraph TESTING["Reliability testing"]
        SCEN["scenarios.py<br/>13 scenarios"] --> EVAL["evaluate.py and pytest<br/>90 tests"]
    end
    EVAL -. runs the whole pipeline .-> OWNER
    EVAL --> REPORT["Pass or fail report<br/>reviewed by the developer"]
```

## Reading the diagram

- **Data flow:** owner input goes through input guardrails, the planner, and verification. Retrieval feeds the advisor, then an explanation is written and checked before it reaches the user.
- **Where a person is involved:** the HUMAN IN THE LOOP node. The agent sends a plan there when a critical task cannot be scheduled, or when a hazard or injection is flagged, or when confidence is below 0.6.
- **Where testing is involved:** the Reliability testing box runs the whole pipeline on 13 scenarios and 90 tests, and produces a report that the developer reviews.

## Where each key term lives

| Term | Where |
|------|-------|
| RAG | `pawpal_ai/knowledge_base.py`, `advisor.py`, `knowledge/*.md` |
| agent / orchestration | `pawpal_ai/agent.py` (`PlanningAgent.run`) |
| guardrail | `pawpal_ai/guardrails.py` |
| human-in-the-loop | `needs_human_review` and `review_reasons` on `AgentResult` |
| verification | `guardrails.verify_plan`, six checks after every plan |
| reliability testing | `scenarios.py`, `evaluate.py`, `tests/test_ai_*.py` |
