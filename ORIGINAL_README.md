# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Features

- **Multiple pets, one plan.** An owner has many pets, and each pet has its own tasks. The scheduler reads all of them through `Owner.get_all_tasks()` and plans them together against one shared daily time budget.
- **Priority-first scheduling.** Tasks are ranked by priority (high, medium, low), then by preferred time, then shortest first. The most important tasks get the time budget and the best slots first.
- **Daily time budget.** The plan never schedules more minutes than the owner has available. Minutes are spent only on tasks that actually get a slot, so a task that can't be placed never blocks a smaller one.
- **Smart time placement.** A task with a preferred time gets it when that slot is free. Otherwise it moves to the nearest free slot, and a task with no preferred time takes the earliest free slot, all inside the owner's day window.
- **Sorting by time.** The task list is ordered by preferred time, with untimed tasks last, and the finished plan is always in chronological order.
- **Filtering.** View tasks by pet name, by completion status, or both.
- **Conflict warnings.** If two tasks, for the same pet or different pets, have overlapping preferred times, the app shows a warning that names both and says "same pet" or "different pets". The scheduler then moves one of them so the final plan has no overlaps. Checking never crashes the app.
- **Daily and weekly recurrence.** Completing a recurring task creates the next occurrence on the same pet, due one day or seven days later. Completing it twice does not create a second copy.
- **Plan explanations.** Every scheduled task says why it was placed where it was, and every skipped task says why it didn't fit (over budget, or no free slot).
- **Input validation.** Task durations must be at least 1 minute, and the daily time budget can't be negative.
- **Streamlit interface.** Add pets and tasks, set a preferred time and repeat schedule, mark tasks complete, filter the list, and generate a plan with summary metrics, a schedule table and warnings.
- **Tested.** A pytest suite of 61 tests covers sorting, recurrence, conflicts, budget handling and validation (see [Testing PawPal+](#-testing-pawpal)).

**Known limits:** scheduling is greedy, so one long high-priority task can crowd out several shorter, lower-priority ones. Conflict warnings look only at tasks with a preferred time, and the scheduler assumes the owner does one thing at a time. Data lives in the browser session and isn't saved between sessions.

For the method behind each feature, see [Smarter Scheduling](#-smarter-scheduling).

## Implementation summary

The core logic lives in `pawpal_system.py`. `main.py` is a demo script that builds an owner with two pets and prints today's schedule, and `tests/` holds the pytest suite. The class diagram is in `diagrams/uml.mmd`.

**How the classes work together**

- `Owner` has many `Pet`s, and each `Pet` has many `Task`s. Each task stores its pet's `pet_id`, so a plan can still tell which pet a task belongs to.
- `Owner.get_all_tasks()` returns every pet's tasks in one list. The `Scheduler` reads tasks only through this method, so it plans across all pets at once.
- `Scheduler.generate_plan(date)` builds the day in four steps:
  1. Keep the tasks that are due: not yet completed, and on or after their due date. A recurring task is renewed when you complete it, because `Pet.complete_task` adds the next copy.
  2. Sort them by priority, then preferred time, then shortest first.
  3. Apply the owner's daily minutes budget. All pets share one budget, so a high-priority task for one pet can push out a low-priority task for another.
  4. Place each task at its preferred time if that slot is free, or in the earliest free slot inside the owner's day window.
- The result is a `DailyPlan` holding `ScheduledItem`s and `SkippedTask`s. Each one records a reason, which is how the app explains its choices.
- `Priority` and `Recurrence` are enums, so values like HIGH or DAILY can't be mistyped.

**Known tradeoff:** the scheduler is greedy. It fills the budget in priority order, so one long high-priority task can crowd out several short, lower-priority ones.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Output from running `python main.py`:

```
============================================================
Sorting and filtering check
============================================================

As added (out of order):
  18:00  Brush coat           Biscuit  pending
   any   Refill water bowl    Biscuit  pending
  07:30  Morning walk         Biscuit  pending
  12:30  Training session     Biscuit  pending
  18:00  Flea treatment       Biscuit  pending
  07:00  Breakfast            Biscuit  done
  07:00  Breakfast            Biscuit  pending, due 2026-11-18
  12:30  Feather wand play    Mochi    pending
  08:00  Thyroid medication   Mochi    pending

Sorted by time:
  07:00  Breakfast            Biscuit  done
  07:00  Breakfast            Biscuit  pending, due 2026-11-18
  07:30  Morning walk         Biscuit  pending
  08:00  Thyroid medication   Mochi    pending
  12:30  Feather wand play    Mochi    pending
  12:30  Training session     Biscuit  pending
  18:00  Flea treatment       Biscuit  pending
  18:00  Brush coat           Biscuit  pending
   any   Refill water bowl    Biscuit  pending

Filtered: pet = Mochi
  12:30  Feather wand play    Mochi    pending
  08:00  Thyroid medication   Mochi    pending

Filtered: completed only
  07:00  Breakfast            Biscuit  done

Filtered: pending only, sorted by time
  07:00  Breakfast            Biscuit  pending, due 2026-11-18
  07:30  Morning walk         Biscuit  pending
  08:00  Thyroid medication   Mochi    pending
  12:30  Feather wand play    Mochi    pending
  12:30  Training session     Biscuit  pending
  18:00  Flea treatment       Biscuit  pending
  18:00  Brush coat           Biscuit  pending
   any   Refill water bowl    Biscuit  pending

Filtered: pet = Biscuit and pending, sorted by time
  07:00  Breakfast            Biscuit  pending, due 2026-11-18
  07:30  Morning walk         Biscuit  pending
  12:30  Training session     Biscuit  pending
  18:00  Flea treatment       Biscuit  pending
  18:00  Brush coat           Biscuit  pending
   any   Refill water bowl    Biscuit  pending

============================================================
Today's Schedule - Tuesday, November 17, 2026
Owner: Karen | Pets: Biscuit, Mochi
------------------------------------------------------------
07:00-07:05  Refill water bowl    [Biscuit, low]
             why: low priority, placed in the earliest free slot
07:30-08:00  Morning walk         [Biscuit, high]
             why: high priority, scheduled at its preferred time
08:00-08:05  Thyroid medication   [Mochi, high]
             why: high priority, scheduled at its preferred time
12:30-12:45  Feather wand play    [Mochi, medium]
             why: medium priority, scheduled at its preferred time
12:45-13:05  Training session     [Biscuit, medium]
             why: medium priority, moved to the nearest free slot (preferred time was unavailable)
18:00-18:05  Flea treatment       [Biscuit, medium]
             why: medium priority, scheduled at its preferred time
18:05-18:25  Brush coat           [Biscuit, low]
             why: low priority, moved to the nearest free slot (preferred time was unavailable)

Warning: time conflict - Feather wand play (Mochi) at 12:30 overlaps Training session (Biscuit) at 12:30 (different pets)

Warning: time conflict - Flea treatment (Biscuit) at 18:00 overlaps Brush coat (Biscuit) at 18:00 (same pet)
------------------------------------------------------------
Total: 100 of 120 min
```

## 🧪 Testing PawPal+

Run the full suite from the project root:

```bash
python -m pytest
```

Add `-v` to list every test, or `-k sort` to run only tests whose names match a word.

**What the tests cover** (`tests/`):

- **Sorting:** `Scheduler.sort_by_time` returns tasks in clock order with untimed tasks last. Ties, empty lists, midnight, stability and not changing the input list are covered, and so are the finished plan's chronological order and priority-first ordering in `sort_tasks`.
- **Recurring tasks:** completing a daily or weekly task creates the next occurrence on the same pet, due one day or seven days later. Calendar boundaries (month end, year end, leap day), late completion, completing twice, one-off tasks and removed tasks are covered.
- **Conflict detection:** tasks with identical or overlapping times produce warnings that say "same pet" or "different pets". Back-to-back tasks are not flagged, and odd input doesn't raise an error. The plan still has no overlaps.
- **Scheduling limits:** the shared time budget across pets, an empty owner, a zero budget, exact-fit tasks, the day-window edges, and many tasks wanting the same time.
- **Basic behavior:** adding tasks to a pet, marking tasks complete, and filtering by pet and by status.

**Input validation:** a task with a zero or negative duration raises `ValueError` (at creation and when edited), and so does a negative daily time budget.

**Budget accounting:** minutes are spent only for tasks that are actually placed, so a task that can't be placed never uses up budget that a smaller task could have had.

Test output:

```
============================= test session starts ==============================
platform darwin -- Python 3.13.15, pytest-9.2.0, pluggy-1.7.0
rootdir: .../ai110-module2show-pawpal-starter
plugins: anyio-4.15.1
collected 61 items

tests/test_edge_cases.py ....................................            [ 59%]
tests/test_pawpal.py ......................                              [ 95%]
tests/test_scheduler.py ...                                              [100%]

============================== 61 passed in 0.03s ==============================
```

## 📐 Smarter Scheduling

Each feature below names the method that implements it. `python main.py` prints a demo of sorting, filtering, conflicts and recurrence, and `tests/` covers each one.

### Sorting

| Method | Order | Used for |
|--------|-------|----------|
| `Scheduler.sort_by_time(tasks)` | Preferred time, with untimed tasks last, then shortest first | The task table in the app and the sorting demo in `main.py` |
| `Scheduler.sort_tasks(tasks)` | Priority (high first), then preferred time, then shortest first | Deciding which tasks get the time budget and the best slots when the plan is built |

`sort_by_time` uses a tuple key, `(is untimed, time, duration)`, so `None` never has to be compared with a time. The finished plan's items are always returned in chronological order.

### Filtering

`Owner.filter_tasks(pet_name=None, completed=None)` returns tasks across all pets:

- `pet_name` matches one pet, ignoring case. `None` means every pet.
- `completed=True` keeps tasks completed at least once, `False` keeps the rest, and `None` keeps both.
- The two filters combine, for example `owner.filter_tasks(pet_name="Biscuit", completed=False)`.

`Pet.get_tasks(completed)` does the same for a single pet. Separately, `Scheduler.generate_plan` applies the owner's daily minutes as it places each task. Minutes are spent only when a task is actually placed, and every task left out is recorded with a reason (over budget, or no free slot in the day window).

### Conflict detection

Detection returns warning messages and never raises an error, so a bad schedule can't crash the app.

- `Scheduler.conflict_warnings(tasks)` is the lightweight check. Each task with a preferred time covers its start to start plus duration. Two tasks conflict if their spans overlap, whether they are for the same pet or different pets. Tasks at exactly the same time conflict, and back-to-back tasks do not. Each message names both tasks and says "same pet" or "different pets".
- `Scheduler.detect_conflicts(items)` is the pairing step. It sorts items by start time and scans forward, stopping as soon as a later item starts at or after the current item's end.
- `Scheduler.generate_plan(date)` runs the check and stores the messages in `plan.warnings`. It still builds a full plan: `Scheduler._place` gives the higher-ranked task its preferred time and moves the other to the nearest free slot, so the final plan has no overlaps. Tasks with no preferred time are not checked, because they are placed into free gaps.

```
Warning: time conflict - Flea treatment (Biscuit) at 18:00 overlaps Brush coat (Biscuit) at 18:00 (same pet)
```

### Recurring tasks

- `Task.mark_complete(date)` records the completion. The first time a daily or weekly task is completed, it also adds the next occurrence to the task's pet. Completing it twice does not create a second copy.
- `Task.next_occurrence()` builds that copy: a new task with a new id, due 1 day (daily) or 7 days (weekly) after the completion date. It is not yet completed, so it recurs in turn.
- `Pet.complete_task(task_id, date)` does the same thing for a task looked up by id. The app's "Mark complete" button uses it.
- `Task.is_due(date)` keeps the copy out of today's plan until its due date. A completed task is never due again.

## 📸 Demo Walkthrough

PawPal+ has a Streamlit app (`streamlit run app.py`) and a command-line demo (`python main.py`). Both use the same classes in `pawpal_system.py`.

### What you can do in the app

- **Owner:** set your name and how many minutes you have available today.
- **Add a pet:** enter a name and species. Each pet appears with an icon and a one-line summary.
- **Add a task:** choose the pet, a title, category, duration, priority and how often it repeats (none, daily or weekly). Optionally set a preferred time.
- **Mark a task complete:** pick a task and click the button. A daily or weekly task creates its next occurrence automatically.
- **Review your tasks:** summary tiles show pets, pending tasks, minutes needed today and minutes available. The task table is sorted by preferred time, and you can filter it by pet and by status (all, pending or completed).
- **Build the schedule:** click "Generate schedule" to see today's plan, with a reason for every task, a list of anything that didn't fit, and a "Why this plan?" explanation. The plan stays on screen and updates as you change things.

### Example workflow

1. **Set your time.** Enter 60 minutes in "Time available today".
2. **Add two pets.** Add Biscuit (dog) and Mochi (cat). Both appear under the form with a short summary.
3. **Add tasks with preferred times.** Give Biscuit a 30-minute "Morning walk" (high priority, daily, 08:00). Give Mochi a 5-minute "Thyroid medication" (high priority, daily, 08:00). Give Biscuit a 45-minute "Brush coat" (low priority, weekly, 18:00).
4. **Read the warnings before scheduling.** The summary tiles show 80 minutes needed against 60 available, with a warning that lower-priority tasks will be skipped. A second warning flags the clash: *Thyroid medication (Mochi) at 08:00 overlaps Morning walk (Biscuit) at 08:00 (different pets)*.
5. **Generate the schedule.** The banner reads "Scheduled 2 of 3 task(s)". The medication is at 08:00-08:05, and the walk was moved to 08:05-08:35, the nearest free slot. A note says the conflict was resolved. "Brush coat" is listed as not scheduled because it needs 45 minutes and only 25 were left.
6. **Complete a task.** Mark "Morning walk" complete. The app confirms and creates tomorrow's walk, and the plan updates.

### Scheduler behavior on display

- **Sorting:** the task table is ordered by preferred time (untimed tasks last), and the plan is ranked by priority first.
- **Filtering:** by pet and by status, in the app and in the CLI demo below.
- **Conflict warnings:** overlapping preferred times are flagged before and after generating, labeled "same pet" or "different pets", and then resolved so the final plan has no overlaps.
- **Time budget:** tasks that don't fit are skipped with a stated reason, such as over budget or no free slot.
- **Recurrence:** completing a daily or weekly task queues the next one, due one day or seven days later.
- **Explanations:** every scheduled task says why it was placed where it was.

### Command-line demo

`python main.py` builds an owner with two pets and a set of tasks added out of order. It then prints the sorted and filtered task lists and today's schedule, including two conflicts: one between different pets (12:30) and one for the same pet (18:00). Breakfast is completed on purpose to show the next daily occurrence appear, due the following day. Dates in the output match the day it was run.

```
============================================================
Sorting and filtering check
============================================================

As added (out of order):
  18:00  Brush coat           Biscuit  pending
   any   Refill water bowl    Biscuit  pending
  07:30  Morning walk         Biscuit  pending
  12:30  Training session     Biscuit  pending
  18:00  Flea treatment       Biscuit  pending
  07:00  Breakfast            Biscuit  done
  07:00  Breakfast            Biscuit  pending, due 2026-11-18
  12:30  Feather wand play    Mochi    pending
  08:00  Thyroid medication   Mochi    pending

Sorted by time:
  07:00  Breakfast            Biscuit  done
  07:00  Breakfast            Biscuit  pending, due 2026-11-18
  07:30  Morning walk         Biscuit  pending
  08:00  Thyroid medication   Mochi    pending
  12:30  Feather wand play    Mochi    pending
  12:30  Training session     Biscuit  pending
  18:00  Flea treatment       Biscuit  pending
  18:00  Brush coat           Biscuit  pending
   any   Refill water bowl    Biscuit  pending

Filtered: pet = Mochi
  12:30  Feather wand play    Mochi    pending
  08:00  Thyroid medication   Mochi    pending

Filtered: completed only
  07:00  Breakfast            Biscuit  done

Filtered: pending only, sorted by time
  07:00  Breakfast            Biscuit  pending, due 2026-11-18
  07:30  Morning walk         Biscuit  pending
  08:00  Thyroid medication   Mochi    pending
  12:30  Feather wand play    Mochi    pending
  12:30  Training session     Biscuit  pending
  18:00  Flea treatment       Biscuit  pending
  18:00  Brush coat           Biscuit  pending
   any   Refill water bowl    Biscuit  pending

Filtered: pet = Biscuit and pending, sorted by time
  07:00  Breakfast            Biscuit  pending, due 2026-11-18
  07:30  Morning walk         Biscuit  pending
  12:30  Training session     Biscuit  pending
  18:00  Flea treatment       Biscuit  pending
  18:00  Brush coat           Biscuit  pending
   any   Refill water bowl    Biscuit  pending

============================================================
Today's Schedule - Tuesday, November 17, 2026
Owner: Karen | Pets: Biscuit, Mochi
------------------------------------------------------------
07:00-07:05  Refill water bowl    [Biscuit, low]
             why: low priority, placed in the earliest free slot
07:30-08:00  Morning walk         [Biscuit, high]
             why: high priority, scheduled at its preferred time
08:00-08:05  Thyroid medication   [Mochi, high]
             why: high priority, scheduled at its preferred time
12:30-12:45  Feather wand play    [Mochi, medium]
             why: medium priority, scheduled at its preferred time
12:45-13:05  Training session     [Biscuit, medium]
             why: medium priority, moved to the nearest free slot (preferred time was unavailable)
18:00-18:05  Flea treatment       [Biscuit, medium]
             why: medium priority, scheduled at its preferred time
18:05-18:25  Brush coat           [Biscuit, low]
             why: low priority, moved to the nearest free slot (preferred time was unavailable)

Warning: time conflict - Feather wand play (Mochi) at 12:30 overlaps Training session (Biscuit) at 12:30 (different pets)

Warning: time conflict - Flea treatment (Biscuit) at 18:00 overlaps Brush coat (Biscuit) at 18:00 (same pet)
------------------------------------------------------------
Total: 100 of 120 min
```

**Screenshot or video** *(optional)*: none included. The steps and output above describe the demo.
