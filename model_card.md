# Model card: PawPal+ AI Care Agent

## 1. Overview and intended use

**What it is.** An applied AI layer on top of PawPal+ (my Module 2 pet care scheduler). It plans a day of pet care tasks, verifies the plan, retrieves cited guidance from a small knowledge base (RAG), scores its own confidence, and asks a person to decide when it should not guess.

**Intended use:** helping a pet owner order daily care tasks and sanity-check the plan.

**Not intended for:** diagnosing illness, choosing or changing medication doses, emergencies (call a veterinarian or a pet poison hotline), or species other than dogs and cats.

**Components**

| Component | Type | Notes |
|---|---|---|
| Scheduler | Deterministic rules | The original Module 2 code, unchanged |
| Retriever | BM25 keyword ranking | 8 hand-written markdown documents, no embeddings, no training |
| Advisor | Extractive | Copies a sentence from a retrieved passage and cites it; abstains below 0.5 relevance |
| Explanation | Template by default | Optionally a hosted language model, whose output is validated before use |
| Guardrails | Pattern and rule based | Input checks, plan verification, output checks |

**Knowledge base.** Written for this project as general guidance (exercise, feeding, medication handling, grooming, enrichment, toxic foods). **It has not been reviewed by a veterinarian.**

**Evaluation.** 13 scripted scenarios (46 expectations) and 90 pytest cases, all passing. These test cases I thought of, so they say little about cases I did not. Full table: see [README.md](README.md#testing-summary).

## 2. Limitations and biases

- **Species bias.** The knowledge base covers only dogs and cats. For any other species the system abstains and says "ask a veterinarian". That is deliberate, but it means owners of rabbits, birds, reptiles or hamsters get no help.
- **Narrow, unreviewed content.** Eight short documents, no breed-specific, age-specific or condition-specific guidance, English only, and not checked by a professional. The minimum-minutes rules (for example 30 minutes of walking for a dog) are general and will be wrong for some animals.
- **Greedy scheduling inherited from Module 2.** Fits tasks by priority, so one long high-priority task can crowd out several short ones. It assumes one owner doing one thing at a time, and nothing is saved between sessions.
- **"Critical" is defined narrowly.** Only medication, or a task that matches a word in the pet's special-needs field. A vet visit or an insulin-related feeding task that is not labeled that way is not protected.
- **Keyword retrieval.** BM25 with light stemming misses paraphrases. The relevance score is a coverage heuristic, not a calibrated probability.
- **Rule-based guardrails.** The prompt-injection and hazard checks are pattern and word lists. A new attack wording or an unlisted toxic food gets through. They reduce risk and do not remove it.
- **Confidence is not safety.** It measures plan quality and evidence strength. The chocolate-treat scenario scores 1.00 confidence, because the plan is valid, and is caught only by the hazard flag and the review rule. Do not read a high score as "approved".
- **Untested paths.** The live model call was only tested with fake models. The Streamlit AI panel was not run in a browser in the build environment.

## 3. Misuse and prevention

| Way it could be misused or misread | What prevents or limits it | What remains |
|---|---|---|
| Treating a cited note as veterinary advice | Notes are general guidance and point to a veterinarian; the system never gives doses; low-evidence cases abstain | A user can still ignore the warnings |
| Relying on "no hazard flagged" as proof a food or plant is safe | Hazard findings are phrased as warnings to confirm with a veterinarian | The hazard list is short, so absence of a flag means nothing |
| Prompt injection through task titles (user text that tries to instruct the AI) | Instruction-like titles are flagged, replaced with `[task title withheld]` before any prompt, and force human review | Novel wordings are not detected |
| A model inventing sources or dosing advice | Citations are checked against what was actually retrieved; dosage patterns are blocked; failures fall back to the template | A model could state a wrong fact without a citation |
| Leaking secrets or personal data | API key read from the environment only; logs hold counts and codes, never task text | Local log files are plain text |
| Over-trusting an automatic fix | The only automatic change is re-ordering so medication goes first, it is shown in the explanation, and the owner's data is never edited | The owner may not read the explanation |

## 4. What surprised me while testing reliability

1. **A bug hid behind a passing test.** My first test that dog advice never came from cat text passed, but only because the species tag was set per file and both toxin sections shared one file. Reading real output showed cat toxin text being shown for a dog's chocolate task. I fixed the data (per-species files), made hazard guidance take priority when a task names a hazard, and rewrote the test to inspect section headings.
2. **The explanation claimed a fix that had failed.** In the impossible-day scenario, the re-plan did not help, yet the text said the draft had been revised. A user would read that as the problem being solved. I changed the message and added a scenario for it.
3. **A safety list silently lost an entry.** `terms=grapes, raisins` parsed as only `grapes` because of how the parser split on spaces. A unit test caught it.
4. **Retrieval got the wrong passage for an obvious task.** "Refill water bowl" returned meal-timing advice, because relevance only looked at category words. Scoring against the task title fixed it.
5. **Confidence did not track risk the way I expected.** Mean confidence was 0.97 on clean scenarios and only 0.86 on risky ones, and the injection and hazard scenarios scored High. The score and the safety flags measure different things, so I kept them as separate signals.
6. **Breaking my own system was the best test.** Disabling the critical-first revision, and separately the output guardrail, made exactly the expected scenarios fail. That was how I knew the checks were not decorative.

## 5. Collaboration with AI during this project

I built this final project with an AI assistant (Claude) working in my repository: it proposed the architecture, wrote the code, and ran the tests, and I directed the goals and reviewed the results.

<!-- REVIEW BEFORE SUBMITTING: this section was drafted from what actually happened in the build session. Edit it so it also reflects your own decisions and what you checked yourself. -->

**One suggestion I accepted as written.** The assistant proposed keeping `pawpal_system.py` untouched and adding the AI as a wrapper, with the only behavior change being a `CriticalFirstScheduler` subclass that overrides the sort order. I accepted it because it kept my Module 2 code and its tests valid, and it makes "the agent never edits the owner's data" easy to claim and to test. I checked it by diffing `pawpal_system.py` against my original (identical) and with a test that the owner's tasks and priorities are unchanged after a run. It also implements the `required` flag idea I had listed as an improvement in my Module 2 reflection.

**Suggestions I changed or scoped down.**

- **Scoped down: embeddings and an LLM-first design.** The more "AI-looking" option was a vector database and having a model write every explanation. I scoped it down to BM25 over eight documents with an extractive template, and made the model optional and validated. Reasons: package installs were blocked in the build environment, a simple method is far easier to explain and test, and a model that can invent sources is a poor fit for pet-health content.
- **Revised after testing: the first retrieval and knowledge-base design.** The assistant's first version scored relevance on category keywords only, penalized general documents heavily, and kept all safety content in one file. Testing and a review of real output showed wrong advice for the water-bowl task, medication guidance being abstained on, and cat toxin text shown for a dog. I did not keep that design: relevance now also uses the task title, the general-document penalty was reduced, safety content is split per species, and a task that names a hazard gets the hazard guidance.
- **Revised: how to report a failed fix.** The first explanation text said the planner had revised its draft even when the revision failed. I changed the wording and added a test for it.

**How I verified AI-written work.** I did not rely on the assistant's explanation of its own code. I ran the demo and read the real output, ran the full test suite, broke the system on purpose to confirm the evaluation fails when it should, and diffed the files that were supposed to be unchanged.

**What I would do differently.** Ask for a review of the first knowledge-base design before building on it, as I did for the scheduler skeleton in Module 2. Two of the bugs above came from design choices that a review would likely have caught.
