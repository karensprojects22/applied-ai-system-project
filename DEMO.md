# Demo and portfolio: PawPal+ AI Care Agent

**GitHub:** https://github.com/karensprojects22/applied-ai-system-project
**Original project:** PawPal+ (Module 2), an object-oriented pet care scheduler. This final project wraps it in an AI layer and leaves `pawpal_system.py` unchanged.
**One-line pitch:** an AI system that plans a pet owner's day, checks its own work, cites its sources, and asks a person to decide when it should not guess.

---

## Presentation plan (about 6 minutes)

| Time | Section | What to show |
|---|---|---|
| 0:00 - 0:45 | The problem and the original project | Just talk, with the README top open (no slides) |
| 0:45 - 1:30 | Architecture | `docs/system_diagram.png` |
| 1:30 - 4:30 | Live demo | Terminal: `python3 demo_ai.py` |
| 4:30 - 5:30 | Reliability and guardrails | Terminal: `python3 evaluate.py` |
| 5:30 - 6:30 | What I learned, limits, questions | README "Testing summary" |

### 0:00 - 0:45: The problem

> "My Module 2 project, PawPal+, builds a daily schedule for a pet owner. It ranks tasks by priority and fits them into the time available. The problem is that a greedy scheduler can quietly make a bad choice: if I mark a medication as medium priority, a high-priority play session can take its slot. Nothing crashes. The plan just looks fine. So I extended it into an AI system that treats the plan as something to *verify*, and treats unsafe cases as something a *person* should decide."

### 0:45 - 1:30: Architecture

Open `docs/system_diagram.png` and trace one path with your finger: input, guardrails, plan, verify, then either advise (retrieval) or critique, revise and re-plan, or human review, then explain, output guardrails, score.

> "The original scheduler still makes the plan. Around it I added retrieval with citations, an agent loop that checks and revises its own plan, guardrails on inputs and outputs, a confidence score, and a rule for when a human has to decide."

### 1:30 - 4:30: Live demo

Run once and scroll as you narrate:
```bash
python3 demo_ai.py
```

1. **Run 1, normal day (30 s).** Point at a cited line such as `[dog_care.md#Daily walks and exercise]` and the confidence of 0.94.
   > "This is RAG. The advice is retrieved from a knowledge base and cited, not invented."
2. **Run 2, crowded day (90 s).** Point at three trace lines in order: `verify ... failed: critical_tasks_scheduled`, then `critique ... switching to critical_first`, then `verify ... 6/6 checks passed`.
   > "The first plan dropped the thyroid medication. The agent noticed, revised, and re-checked. That is the agentic loop: plan, verify, critique, revise."
3. **Run 3, impossible day (60 s).** Point at `HUMAN REVIEW REQUIRED`.
   > "The medication needs 5 minutes and only 3 exist. The agent tries its one allowed fix, it fails, and it stops. It does not pretend the problem is solved. That is human-in-the-loop."

Optional if you have tested it (30 s): `streamlit run app.py`, then add a `meds` task, set time to 40, click **Generate schedule**, then **Run AI agent**.

### 4:30 - 5:30: Reliability and guardrails

```bash
python3 evaluate.py
```

Point at `expectations met: 46/46` and `escalated to a person: 3/13`. If you have 20 spare seconds, also run `python3 guardrail_report.py` and point at `Guardrail cases passed: 11/11`.

> "13 scenarios, including attacks: a task title that tries to hijack the AI, a toxic food, a model that invents a citation, a model that gives a dose. Each is caught. I also broke my own system on purpose, disabling the revision step and then the output guardrail, and the evaluation failed in exactly the expected places, so the tests are not decorative."

### 5:30 - 6:30: What I learned

> "Three things. One: the useful part of AI in a system is often the checking, not the generating. Two: confidence is not safety. The chocolate-treat scenario scores 1.00 confidence because the plan is valid, and is caught by a separate hazard flag, so I kept those as two signals. Three: tests can pass for the wrong reason. An audit of real output found cat toxin advice shown for a dog's task, and my first test for that had passed anyway. I fixed the data and rewrote the test."

Close with limits: dogs and cats only, a small knowledge base that no veterinarian has reviewed, and pattern-based guardrails. Then take questions.

### Key terms to say out loud

*agent, guardrail, human-in-the-loop, orchestration, RAG (retrieval-augmented generation), reliability testing, verification.* For example: "`PlanningAgent` is the orchestration layer. After every plan it runs verification. It is a RAG system because retrieved text drives the advice. If a critical task cannot fit, it hands off to a human."

### If something breaks

| Problem | What to do |
|---|---|
| Streamlit will not start | Say "same logic, different front end" and go back to `python3 demo_ai.py` |
| `command not found` or `No module named` | `source .venv/bin/activate`, and check you are in the project folder (`ls` should show `demo_ai.py`) |
| Terminal output too long to scroll | Show `logs/demo_output.txt` or the README "Sample interactions" section. They are real saved output |
| Nothing works | Open the README "Reproducible execution evidence" section |

### Likely questions

- **Why not let an LLM do all of it?** The plan has to be correct and checkable. The scheduler and the checks are deterministic. A model is optional, sees only retrieved facts, and its output is validated before anyone reads it.
- **What stops hallucination?** Advice is copied from retrieved text, citations are checked against what was actually retrieved, and the system abstains below 0.5 relevance.
- **Is the confidence score calibrated?** No. It is a weighted heuristic of four signals, and it does not capture every risk. That is why there is a separate human-review flag.
- **What would you do next?** An owner-set "required" flag, a veterinarian-reviewed knowledge base, embedding-based retrieval, and saving data between sessions.

---

## Portfolio artifact

**Code:** https://github.com/karensprojects22/applied-ai-system-project

**Reflection: what this project says about me as an AI engineer**

<!-- DRAFT: rewrite in your own words before submitting. Keep only claims that are true for you. -->

This project shows that I treat AI as one component in a system that has to be verified, not as the product itself. I took a working scheduler from an earlier module, left it untouched, and built the layer around it that makes an AI system trustworthy: retrieval with citations, an agent that checks and revises its own plan, guardrails on inputs and outputs, a confidence score, and a clear rule for when a person must decide. I test adversarially and I read real output instead of trusting passing tests, which caught a bug my first test had missed. I care more about what a system does when it is wrong than about how impressive it looks when it is right.

---

## Where to find the grading evidence

| Requirement | Location |
|---|---|
| GitHub link to the code | This file, above |
| Short reflection paragraph | This file, above |
| Sample command executions | `README.md`, "Reproducible execution evidence" |
| Example inputs and outputs | `README.md`, "Sample interactions" and "Command 1" |
| Reliability and guardrail results | `README.md`, "Command 5", "Guardrail and reliability results" and "Testing summary"; raw output in `logs/guardrail_report.txt` |
| Saved raw output | `logs/*.txt`, `logs/agent_log.jsonl`, `logs/evaluation_results.json` |
| Responsible-AI reflection | `model_card.md` |
| Architecture diagram | `docs/system_diagram.mmd` and `docs/system_diagram.png` |
