# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

My UML models a pet owner who builds a daily care plan for their pets. It has five classes, plus two small enums (`Priority` and `Recurrence`) so values like HIGH or DAILY can't be mistyped. `Owner`, `Pet`, `Task` and `DailyPlan` are dataclasses because they mostly hold data. `Scheduler` is a regular class because it holds the logic.

- **Owner**: holds the owner's name, their daily time budget, their preferences, and their list of pets. It adds and removes pets, updates availability, gathers every task across all pets, and starts plan creation by handing off to the `Scheduler`.
- **Pet**: holds the pet's profile (name, species, breed, age, special needs) and that pet's list of tasks. It adds, removes, edits and filters its tasks, and can describe itself for the UI. I made walking, feeding and grooming `Task` objects rather than pet actions, so the scheduler can sort and filter them.
- **Task**: represents one care activity, with a title, category, duration, priority, optional preferred time, recurrence and completed flag. It can mark itself complete, check whether it is due on a date, create its next occurrence if it recurs, and turn its priority into a number for sorting.
- **Scheduler**: holds the scheduling logic, kept separate from the data classes so it is easy to test. It sorts tasks by priority, fits them into the owner's time budget, detects time conflicts, builds the `DailyPlan`, and explains why it chose that plan.
- **DailyPlan**: the result of scheduling for one date. It holds the scheduled items, the skipped tasks and the total minutes. It can add items, report total duration, give the explanation, and format itself as rows for the Streamlit display.

Relationships: an `Owner` has many `Pet`s, a `Pet` has many `Task`s, and the `Scheduler` reads an owner's tasks to produce a `DailyPlan`.
Y
**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yes. After reviewing my skeleton I found several gaps and changed the design before writing any logic:

- **Tasks know their pet.** `Owner.get_all_tasks()` flattens every pet's tasks into one list, so a plan couldn't say which pet a task was for. I gave `Pet` and `Task` a unique `id` and added `Task.pet_id`, which `Pet.add_task` sets. `Owner.find_pet()` looks a pet up by id.
- **Tasks have identity.** Dataclasses compare by value, so two identical "Walk" tasks were equal, which made `remove_task` and `edit_task` ambiguous and left tasks unhashable. I set `eq=False` on `Task` and `Pet` and changed those methods to take a `task_id`.
- **Removed `Owner.create_plan`.** `Owner` and `Scheduler` depended on each other. The UI now calls `Scheduler(owner).generate_plan(date)`, so the dependency runs one way.
- **Recurring tasks can be completed per day.** A `completed` flag would stay true tomorrow for a daily task, and `is_due` had nothing to compare against. I replaced it with `last_completed` and added `due_date`, and `mark_complete` now takes a date.
- **The owner has a time window.** A minutes budget alone can't produce clock times, so I added `day_start` and `day_end` to `Owner`.
- **Scheduler results keep their reasons.** `fit_to_time_budget` now returns the scheduled and skipped tasks, with a reason for each skip. `detect_conflicts` returns pairs of tasks. I added `ScheduledItem` and `SkippedTask` dataclasses to replace untyped tuples.
- **One source for the explanation.** I removed `Scheduler.explain` and `DailyPlan.total_minutes`. The scheduler records a reason on each item, and `DailyPlan.get_explanation()` and `total_duration()` derive their output from those items, so nothing goes stale or is stored twice.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

The scheduler considers five things:

- **Priority** (high, medium, low). It ranks tasks, so the most important ones get time first.
- **The owner's daily time budget**, in minutes, shared by all pets. This is a hard limit: the plan never schedules more minutes than the owner has.
- **The owner's day window** (`day_start` to `day_end`). Every task must fit inside it, with no overlaps.
- **Preferred time.** A task gets its preferred time if that slot is free. This is a soft preference, not a rule.
- **Due date and recurrence.** Only tasks that are due and not yet completed are planned.

I ranked them by what goes wrong if they're ignored. Skipping a medication or a walk matters far more than skipping grooming, so priority comes first. The time budget is a hard limit because the owner really can't do more than they have time for. Preferred time is last because pet-care times are flexible: moving a walk by ten minutes costs little. The `Owner.preferences` dictionary and `Scheduler.constraints` exist in the classes but nothing reads them yet.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

**Tradeoff: the scheduler warns about time conflicts and fixes them itself, based only on preferred times.**

- **What it does.** `Scheduler.conflict_warnings` compares the time span of each task that has a `preferred_time` (start to start plus duration), so a 30-minute walk at 08:00 conflicts with a task at 08:15, not just one at exactly 08:00. It returns a warning message and never raises an error. `generate_plan` then keeps both tasks and moves the lower-ranked one to the nearest free slot, so the final plan never has overlapping tasks.
- **What it gives up.**
  - Only tasks with a preferred time can conflict. A task with no time is simply placed in a gap, so it is never reported.
  - The owner isn't asked which task should win. Priority decides, then the shorter task, and the loser can end up away from the time they wanted. It can even be skipped if the day is full.
  - The scheduler is fixed to one owner's single timeline. It doesn't model two things happening at once, such as walking two pets together, and flags them as a conflict.
- **Why it is reasonable.** Pet-care times are mostly preferences, not appointments. A walk at 08:10 instead of 08:00 rarely matters, so a plan that always works and tells the owner what it moved is more useful than one that stops with an error or demands a decision for every clash. The warning keeps the owner informed, and the reason shown beside each moved task explains why it moved. I also kept the check small, a sort plus one pass, so it is easy to read and test.
- **What I'd change with more time.** Add a way to mark a task as fixed (a vet visit or medication at a set time) so it never moves, and let the owner choose which task yields.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

I used AI at every stage, in roughly this order:

- **Design brainstorming.** I asked for the main objects with their attributes and methods, and it proposed `Owner`, `Pet`, `Task`, `Scheduler` and `DailyPlan`. It also suggested making walking and feeding `Task` objects rather than pet actions.
- **Drafting.** I asked it to turn that into a Mermaid class diagram, then into dataclass stubs, then to fill in the logic, the demo script and the tests.
- **Design review.** I asked it to review my own skeleton for missing relationships and logic bottlenecks. This was the most useful prompt, because it found real flaws before any logic existed.
- **Documentation.** It drafted the docstrings, the README sections and the reflection text. I edit them so they match what I built.

The most helpful prompts were specific and gave it something concrete to check, such as "review my skeleton" or "how should the Scheduler retrieve all tasks from the Owner's pets?". Open requests like "brainstorm the objects" gave a starting point that I still had to question.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

**What the AI suggested, and what I accepted or rejected.** The review of my skeleton produced a list of problems in three groups: missing relationships, logic gaps, and smaller cleanups plus a bottleneck note. I accepted the first two groups and left the rest out:

- Accepted: tasks linked to their pet, task ids with identity-based equality, removing the circular `Owner.create_plan`, replacing `completed` with `last_completed` and `due_date`, a day window on `Owner`, scheduler results that keep reasons, and one source for the explanation.
- Not taken: the smaller cleanups (renaming `DailyPlan.date`, dropping `priority_score`, changing `get_tasks` to a status enum) and the idea of a `required` flag so medication is never skipped. They didn't block the requirements, so I kept the scope smaller. The `required` flag is the one I'd add first, because right now a medication can be skipped when time runs out.
- Handled differently: its suggestion to redesign the terminal output as a table. I kept the command-line output simple and pasted the real `main.py` output into the README, and used the table styling in the Streamlit app instead.

I did not take the AI's first design as correct either. Its own initial design had flaws, such as `Owner.create_plan` making `Owner` and `Scheduler` depend on each other, and a `completed` flag that would stay true for a daily task the next day. Asking it to review its own work found them.

**How I verified the result.**
- I ran code instead of trusting the explanations. I created two identical "Walk" tasks to confirm they compare unequal and stay distinct in a set, and I ran a small scenario to see the plan the scheduler produced.
- I wrote pytest tests, including one with two pets to check that the scheduler reads tasks from every pet and that the pets share one time budget. The full suite (61 tests) passes.
- I ran `python main.py` and read the schedule against my expectations, for example that tasks landed at their preferred times and that the totals added up.
- I compared the UML diagram with the code after each design change, so the two stayed in sync.

**c. AI strategy**

*Which assistant features were most effective for building the scheduler?*

What I loved most was using the assistant to verify and check my code as I went, and to understand the codebase and the problem I was solving.

- **Review and verification.** I asked it to review my skeleton before I wrote any logic, and it found real design flaws early. Later it ran small scenarios and my test suite against its own changes, which caught bugs I wouldn't have spotted by reading: a time budget that was spent on tasks that couldn't be placed, a Streamlit dropdown that returns a copy of an object so tasks were silently lost, and a task that accepted a negative duration. It also checked my UML against the code in both directions, so I could see exactly which methods were missing from the diagram.
- **Explaining the code.** Questions like "how should the Scheduler retrieve all tasks from the Owner's pets?" got me pointed to the exact line that already did it, and I learned why the sort key is a tuple (so `None` is never compared with a time) and how `st.session_state` keeps the owner between reruns.
- **Fast drafting of routine work.** Class stubs, docstrings, test scaffolding and README sections took minutes, which left my time for decisions.

*One suggestion I rejected or modified to keep the design clean.*

The design review gave me a long list. I took only the fixes that mattered for the system and left out the rest. I accepted the missing relationships and logic gaps, such as linking tasks to pets, giving tasks ids and replacing the `completed` flag with `last_completed`. I did not take the smaller cleanups or the idea of a `required` flag for medication. The biggest modification was where plan creation lives. The first brainstorm put `create_plan` on `Owner`, which made `Owner` and `Scheduler` depend on each other. I removed it so the `Scheduler` is the one place that plans, and it reads every pet's tasks only through `Owner.get_all_tasks()`. That kept `Owner` and `Pet` as simple data and made the scheduler easy to test.

*How separate chat sessions for different phases helped me stay organized.*

I kept design, implementation and testing in separate conversations. Each one stayed focused on a single question, so I wasn't scrolling through old discussion of the UML while debugging a test. Starting a fresh session also forced me to write a short hand-over note: what was done, which bugs were known, and what was covered. That meant the project files, the UML, the tests and the git history became the source of truth, and not the chat. The cost is that a new session doesn't remember earlier decisions, so the reasons for them have to be written down in the reflection, the commit messages and the README.

*What I learned about being the "lead architect" with powerful AI tools.*

- **I decide, the AI proposes.** The assistant can produce a working class, a diagram or a feature in seconds, but choosing which classes exist, who owns what and what to leave out stayed my job.
- **Confident output is not correct output.** Some of the AI's own first design was wrong. The way to find out was to run it, test it and ask for a review, not to read it and nod.
- **Verify before trusting, and test the edges.** The bugs it found were in boundaries and unusual cases: budgets, midnight, month ends and empty input.
- **Keep the scope small and the design documented.** Saying "only these fixes" kept the project finishable, and updating the UML and README after each change kept them honest.
- **Keep control of what leaves your machine.** I decided what got committed and pushed, and when I didn't want a push to `main` to stand I had it undone.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

I wrote 61 pytest tests in three files (`tests/test_pawpal.py`, `tests/test_scheduler.py` and `tests/test_edge_cases.py`). They cover:

- **Sorting.** Tasks come back in clock order with untimed ones last, ties go to the shorter task, equal tasks keep their order, midnight counts as a real time, and the input list isn't changed. The finished plan is always in chronological order, and priority beats time of day.
- **Recurring tasks.** Completing a daily or weekly task creates the next one, due one or seven days later, including across month ends, year ends and a leap day. They also cover late completion, completing twice, one-off tasks, removed tasks, and a successor that is a separate copy and stays out of the plan until its due date.
- **Conflict detection.** Overlapping and identical times produce warnings labeled same pet or different pets, back-to-back tasks don't, odd input doesn't crash, and the final plan has no overlaps.
- **Scheduling limits.** Pets share one budget, a zero budget skips everything, a task that exactly fills the budget fits, tasks ending exactly at the end of the day fit but one minute more doesn't, and a task that can't be placed no longer uses up budget.
- **Validation.** Zero or negative durations and negative budgets are rejected.

These matter because a scheduler can quietly produce a wrong plan without any error, and the failures hide at boundaries, like the end of a month or the last minute of the day. The tests also caught real bugs: the budget leak and the missing duration check.

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

I'm fairly confident, about 4 out of 5, in the scheduling logic itself: the 61 tests pass, and I wrote tests for the bugs the AI review found. I'm less sure about the Streamlit app, which I checked only by running it through Streamlit's headless test runner, not by clicking through it in a browser. Nothing is saved between sessions, so I haven't tested persistence at all.

With more time I would test:

- tasks that must not move (a fixed vet visit or medication), once that feature exists
- a task that runs past the end of the day, and a day window that changes between runs
- tasks that were due yesterday and weren't done (overdue handling)
- many pets and many tasks at once
- weekly tasks tied to particular weekdays
- the UI in a real browser, including editing and removing tasks

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

I'm most satisfied with reviewing the design before writing the logic. Finding the problems in my skeleton (tasks that didn't know their pet, a completed flag that broke recurring tasks, and a circular dependency) cost minutes then, and would have cost much more once the scheduler was built on top of them. I'm also happy that the scheduler explains itself: every scheduled task says why it landed where it did, and every skipped task says why it didn't fit. The test suite gives me real confidence in changing the code.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

- Add a `required` or fixed flag so medication and appointments are never skipped or moved, and let the owner choose which task yields in a conflict.
- Save the owner, pets and tasks to a file so they survive a restart.
- Handle overdue tasks, so a daily task missed yesterday shows up as overdue instead of disappearing.
- Replace the greedy fit with something that can swap a long task for several shorter ones when that fits more of the day.
- Either use the `Owner.preferences` and `Scheduler.constraints` fields (for example for buffer time between tasks) or remove them.
- Let the app edit and delete tasks, not just add and complete them.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

Working with AI made me the lead architect, and that meant owning the decisions. The assistant is very fast at producing code, and it is also confident when it is wrong, so the real work was deciding what to build, keeping the scope small, and checking everything with tests and review. Designing the system first, then fixing the design before the logic, kept the project simple. Good tools made me think more about the design, not less.

---

## 6. Final Project: Applied AI System (DRAFT - rewrite in your own words before submitting)

**What I extended and why.** I extended PawPal+ because its scheduler already explained its choices, which made it a good base for AI that has to justify itself. The weakness I wanted to fix is the one I named in section 5: a medication can be skipped when time runs out. The AI layer treats that as something to verify and, if it cannot be fixed, hand to a person.

**What the system does.** It runs the original scheduler, verifies the plan with six checks, re-plans with medication first if a critical task was dropped, retrieves cited guidance from a small knowledge base (RAG), and reports a confidence score and a human-review flag. A language model is optional, and its text is rejected if it invents a source or gives a dose.

**What testing taught me.** Four things changed because of tests and reading real output, not because of reading code: cat toxin advice appeared for a dog (and my first test for that passed for the wrong reason), retrieval gave meal advice for a water-bowl task, a hazard list silently lost a term because of how it was parsed, and the explanation claimed a failed fix had worked. I also broke the system on purpose to confirm the evaluation fails when it should.

**Limits I would tell a user about.** Confidence is not safety: the injection and toxic-food cases score High and are caught by flags, not by the score. The knowledge base is small, unreviewed by a vet, and covers only dogs and cats. The guardrails are pattern lists.

**AI collaboration.** See the responsible-AI reflection in `model_card.md` (section 5) for the accepted and revised suggestions, and add your own notes here.
