# Presentation notes (about 5 minutes)

**1. The problem (30s).** A scheduler can produce a plan that looks fine but quietly drops a medication, because it ranks by priority. PawPal+ is my Module 2 scheduler. I extended it so the plan gets *verified*, not just produced.

**2. Live demo: `python demo_ai.py` (2 min).**
- Run 1, normal day: show the trace, cited advice, confidence 0.94.
- Run 2, crowded day: first draft drops the thyroid medication, verify fails, the agent revises, and verify passes. *"This is the agentic loop: plan, verify, critique, revise."*
- Run 3, impossible day: medication needs 5 min, 3 available. The agent **escalates** instead of guessing. *"This is human-in-the-loop."*

**3. How it works (1 min).** Show the diagram in `docs/architecture.md`. Key terms to say out loud: RAG (retrieval-augmented generation) with citations and abstention, a guardrail on inputs and outputs, orchestration in `PlanningAgent`, verification after every plan, reliability testing in `evaluate.py`.

**4. Reliability (1 min).** `python evaluate.py`: 13 scenarios, 46/46 expectations, 88 tests. Point out the risky scenarios: prompt-injection title, toxic food, model invents a citation, model gives a dose. *"I also broke the system on purpose and the evaluation caught it."*

**5. Honest limits (30s).** (Full detail is in `model_card.md`.) Confidence is not safety. Small unreviewed knowledge base, dogs and cats only. Pattern-based guardrails.

## Likely questions
- **Why not just let an LLM do it?** The plan must be correct and checkable. The scheduler and checks are deterministic; the LLM is optional and validated.
- **What stops hallucination?** Advice is copied from retrieved text, citations are checked against what was retrieved, and the system abstains below 0.5 relevance.
- **What did testing find?** Cat toxin advice showed up for a dog (my first test passed for the wrong reason), retrieval picked meal advice for a water task, a parser dropped a hazard term, and a message claimed a failed fix worked. All fixed.
- **Is the confidence score calibrated?** No. It is a weighted heuristic of four signals, and it does not capture every risk, which is why there is a separate human-review flag.
- **What would you do next?** A `required` flag set by the owner, a vet-reviewed knowledge base, embedding retrieval, and persistence.
