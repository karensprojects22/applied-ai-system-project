from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Optional
from uuid import uuid4


def _new_id() -> str:
    return uuid4().hex


def _check_duration(minutes: int) -> None:
    if minutes <= 0:
        raise ValueError(f"Task duration must be at least 1 minute, got {minutes}")


def _to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _to_time(minutes: int) -> time:
    return time(minutes // 60, minutes % 60)


class Priority(Enum):
    HIGH = 3
    MEDIUM = 2
    LOW = 1


class Recurrence(Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"


_RECURRENCE_DAYS = {Recurrence.DAILY: 1, Recurrence.WEEKLY: 7}


# eq=False keeps identity-based equality, so two identical "Walk" tasks stay
# distinct and the objects remain hashable.
@dataclass(eq=False)
class Task:
    title: str
    category: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    preferred_time: Optional[time] = None
    recurrence: Recurrence = Recurrence.NONE
    due_date: Optional[date] = None
    last_completed: Optional[date] = None
    pet_id: Optional[str] = None  # set by Pet.add_task
    id: str = field(default_factory=_new_id)
    # Back-reference set by Pet.add_task so a recurring task can queue its own successor.
    _pet: Optional["Pet"] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """Reject a duration that is not a positive number of minutes."""
        _check_duration(self.duration_minutes)

    def mark_complete(self, on_date: date) -> Optional["Task"]:
        """Record completion; a daily or weekly task also queues its next occurrence.

        Only the first completion queues a successor, so calling this twice never
        duplicates it. The successor is added to the task's pet when it has one and
        is always returned, so a task not attached to a pet can still be re-queued
        by the caller. Returns None for a one-off task or a repeat completion.
        """
        first_time = self.last_completed is None
        self.last_completed = on_date
        if not first_time:
            return None
        following = self.next_occurrence()
        if following is not None and self._pet is not None:
            self._pet.add_task(following)
        return following

    def is_due(self, on_date: date) -> bool:
        """Return whether the task is not yet done and has reached its due date.

        A task with no due_date is due immediately. A completed task is never due
        again; a recurring task comes back as a new copy from next_occurrence.
        """
        if self.due_date and on_date < self.due_date:
            return False
        return self.last_completed is None

    def next_occurrence(self) -> Optional["Task"]:
        """Return a fresh copy due one interval later, or None if not recurring.

        The interval is 1 day for daily and 7 days for weekly, counted from the last
        completion date (falling back to the due date, then today). The copy gets a
        new id and is not yet completed, so it recurs in turn when it is finished.
        """
        if self.recurrence is Recurrence.NONE:
            return None
        base = self.last_completed or self.due_date or date.today()
        next_due = base + timedelta(days=_RECURRENCE_DAYS[self.recurrence])
        return replace(self, id=_new_id(), due_date=next_due, last_completed=None)

    def priority_score(self) -> int:
        """Return the priority as a number, where higher means more urgent."""
        return self.priority.value


@dataclass(eq=False)
class Pet:
    name: str
    species: str
    breed: str = ""
    age: int = 0
    special_needs: str = ""
    tasks: list[Task] = field(default_factory=list)
    id: str = field(default_factory=_new_id)

    def add_task(self, task: Task) -> None:
        """Attach a task to this pet and link it back through pet_id."""
        task.pet_id = self.id
        task._pet = self
        if task not in self.tasks:
            self.tasks.append(task)

    def remove_task(self, task_id: str) -> None:
        """Delete the task with this id, raising KeyError if it isn't found."""
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                del self.tasks[i]
                task._pet = None
                return
        raise KeyError(f"No task with id {task_id!r} for {self.name}")

    def _get_task(self, task_id: str) -> Task:
        """Return the task with this id, raising KeyError if it isn't found."""
        task = next((t for t in self.tasks if t.id == task_id), None)
        if task is None:
            raise KeyError(f"No task with id {task_id!r} for {self.name}")
        return task

    def complete_task(self, task_id: str, on_date: date) -> Optional[Task]:
        """Mark a task done and add its next occurrence if it recurs, returning it.

        Looks the task up by id (KeyError if missing) and delegates to
        Task.mark_complete. Completing an already-completed task changes nothing
        and returns None.
        """
        task = self._get_task(task_id)
        if task.last_completed is not None:
            return None
        return task.mark_complete(on_date)

    def edit_task(self, task_id: str, **changes) -> None:
        """Update fields on the task with this id, rejecting id and unknown fields."""
        task = self._get_task(task_id)
        for key, value in changes.items():
            if key in ("id", "pet_id") or not hasattr(task, key):
                raise AttributeError(f"Cannot edit task field {key!r}")
            if key == "duration_minutes":
                _check_duration(value)
            setattr(task, key, value)

    def get_tasks(self, completed: Optional[bool] = None) -> list[Task]:
        """Return this pet's tasks, optionally filtered by completed status."""
        # "completed" means the task has been completed at least once.
        if completed is None:
            return list(self.tasks)
        return [t for t in self.tasks if (t.last_completed is not None) == completed]

    def describe(self) -> str:
        """Return a one-line summary of the pet for display."""
        text = f"{self.name} ({self.breed or self.species}, age {self.age})"
        if self.special_needs:
            text += f" - needs: {self.special_needs}"
        return text


@dataclass
class Owner:
    name: str
    available_minutes_per_day: int = 0
    day_start: time = time(8, 0)
    day_end: time = time(20, 0)
    preferences: dict = field(default_factory=dict)
    pets: list[Pet] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Reject a negative daily time budget."""
        if self.available_minutes_per_day < 0:
            raise ValueError("Availability cannot be negative")

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner, ignoring one that is already added."""
        if pet not in self.pets:
            self.pets.append(pet)

    def remove_pet(self, pet_id: str) -> None:
        """Remove the pet with this id, raising KeyError if it isn't found."""
        pet = self.find_pet(pet_id)
        if pet is None:
            raise KeyError(f"No pet with id {pet_id!r}")
        self.pets.remove(pet)

    def find_pet(self, pet_id: str) -> Optional[Pet]:
        """Return the pet with this id, or None if the owner has no such pet."""
        return next((p for p in self.pets if p.id == pet_id), None)

    def set_availability(self, minutes: int) -> None:
        """Set the owner's daily time budget in minutes, rejecting negatives."""
        if minutes < 0:
            raise ValueError("Availability cannot be negative")
        self.available_minutes_per_day = minutes

    def get_all_tasks(self) -> list[Task]:
        """Return every task from every pet in one flat list."""
        return [task for pet in self.pets for task in pet.tasks]

    def filter_tasks(
        self, pet_name: Optional[str] = None, completed: Optional[bool] = None
    ) -> list[Task]:
        """Return all tasks, optionally limited to one pet name and/or done status.

        pet_name matches case-insensitively; None means every pet. completed=True
        keeps tasks completed at least once, False keeps the rest, None keeps both.
        The two filters combine, and the result keeps each pet's task order.
        """
        tasks = []
        for pet in self.pets:
            if pet_name is not None and pet.name.lower() != pet_name.lower():
                continue
            tasks.extend(pet.get_tasks(completed))
        return tasks


@dataclass
class ScheduledItem:
    task: Task
    start: time
    end: time
    reason: str = ""


@dataclass
class SkippedTask:
    task: Task
    reason: str


@dataclass
class DailyPlan:
    date: date
    scheduled_items: list[ScheduledItem] = field(default_factory=list)
    skipped_tasks: list[SkippedTask] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_item(self, task: Task, start: time, reason: str = "") -> None:
        """Schedule a task at the given start time, computing its end time."""
        start_dt = datetime.combine(self.date, start)
        end_dt = start_dt + timedelta(minutes=task.duration_minutes)
        if end_dt.date() != self.date:
            raise ValueError(f"{task.title!r} would run past midnight")
        self.scheduled_items.append(ScheduledItem(task, start, end_dt.time(), reason))

    def total_duration(self) -> int:
        """Return the total scheduled minutes across all items."""
        return sum(item.task.duration_minutes for item in self.scheduled_items)

    def get_explanation(self) -> str:
        """Return a text summary of each scheduled and skipped task with reasons."""
        lines = [f"Plan for {self.date.isoformat()} ({self.total_duration()} min total)"]
        for item in self.scheduled_items:
            lines.append(
                f"{item.start:%H:%M}-{item.end:%H:%M} {item.task.title}: {item.reason}"
            )
        for skipped in self.skipped_tasks:
            lines.append(f"Skipped {skipped.task.title}: {skipped.reason}")
        for warning in self.warnings:
            lines.append(f"Warning: {warning}")
        return "\n".join(lines)

    def to_rows(self) -> list[dict]:
        """Return the scheduled items as dicts ready for a table display."""
        return [
            {
                "Start": f"{item.start:%H:%M}",
                "End": f"{item.end:%H:%M}",
                "Task": item.task.title,
                "Category": item.task.category,
                "Duration (min)": item.task.duration_minutes,
                "Priority": item.task.priority.name.title(),
                "Why": item.reason,
            }
            for item in self.scheduled_items
        ]


class Scheduler:
    def __init__(self, owner: Owner, constraints: Optional[dict] = None):
        """Create a scheduler for an owner's pets with optional constraints."""
        self.owner = owner
        self.constraints = constraints or {}

    def generate_plan(self, on_date: date) -> DailyPlan:
        """Build the day's plan from every pet's due tasks within time limits.

        Tasks are taken in priority order. Each one must fit both the remaining
        daily minutes and a free slot in the day window. Minutes are spent only
        when a task is actually placed, so a task that cannot be placed never uses
        up budget that a smaller, lower-priority task could have had. Every task
        that is left out is recorded with the reason.
        """
        plan = DailyPlan(on_date)
        due = [t for t in self.owner.get_all_tasks() if t.is_due(on_date)]
        remaining = self.owner.available_minutes_per_day
        window_start = _to_minutes(self.owner.day_start)
        window_end = _to_minutes(self.owner.day_end)
        busy: list[tuple[int, int]] = []  # (start, end) in minutes, kept sorted
        placed: list[Task] = []

        for task in self.sort_tasks(due):
            if task.duration_minutes > remaining:
                plan.skipped_tasks.append(SkippedTask(
                    task,
                    f"Needs {task.duration_minutes} min but only {remaining} min "
                    "of the daily budget was left",
                ))
                continue
            start, reason = self._place(task, busy, window_start, window_end)
            if start is None:
                plan.skipped_tasks.append(SkippedTask(
                    task,
                    f"No free slot left between {self.owner.day_start:%H:%M} "
                    f"and {self.owner.day_end:%H:%M}",
                ))
                continue
            remaining -= task.duration_minutes
            busy.append((start, start + task.duration_minutes))
            busy.sort()
            placed.append(task)
            plan.add_item(task, _to_time(start), reason)

        plan.warnings.extend(self.conflict_warnings(placed))
        plan.scheduled_items.sort(key=lambda item: item.start)
        return plan

    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Return tasks ordered by priority, then preferred time, then duration.

        Highest priority comes first, so the budget and the best slots go to the
        most important tasks. Ties go to the earlier preferred time (untimed last),
        then the shorter task. This is the order the plan is built in.
        """
        # Highest priority first, then earliest preferred time, then shortest.
        return sorted(
            tasks,
            key=lambda t: (-t.priority_score(), t.preferred_time or time.max,
                           t.duration_minutes),
        )

    def sort_by_time(self, tasks: list[Task]) -> list[Task]:
        """Return tasks ordered by preferred time, with untimed tasks last.

        Priority is ignored here; this is the display order. The sort key is a
        tuple so None never has to be compared with a time: (is untimed, time,
        duration). Equal times fall back to the shorter task first.
        """
        return sorted(
            tasks,
            key=lambda t: (t.preferred_time is None, t.preferred_time or time.min,
                           t.duration_minutes),
        )

    def conflict_warnings(self, tasks: list[Task]) -> list[str]:
        """Return a warning for each pair of tasks whose preferred times overlap.

        Each task with a preferred time covers start to start + duration (capped at
        23:59). Tasks at the same time, across pets or within one pet, overlap;
        back-to-back tasks do not. Tasks without a preferred time are ignored. Each
        message names both tasks and says "same pet" or "different pets". It returns
        strings and never raises, so the caller can show them and carry on.
        """
        items = []
        for task in tasks:
            if task.preferred_time is None:
                continue
            start = _to_minutes(task.preferred_time)
            end = _to_time(min(start + task.duration_minutes, 24 * 60 - 1))
            items.append(ScheduledItem(task, task.preferred_time, end))
        return [
            f"{self._describe(a)} overlaps {self._describe(b)} "
            f"({'same pet' if a.pet_id == b.pet_id else 'different pets'})"
            for a, b in self.detect_conflicts(items)
        ]

    def _describe(self, task: Task) -> str:
        """Return 'title (pet) at HH:MM' for a task with a preferred time."""
        pet = self.owner.find_pet(task.pet_id)
        owner_part = f" ({pet.name})" if pet else ""
        return f"{task.title}{owner_part} at {task.preferred_time:%H:%M}"

    def detect_conflicts(self, items: list[ScheduledItem]) -> list[tuple[Task, Task]]:
        """Return pairs of tasks whose scheduled times overlap.

        Sorts the items by start time, then compares each with the ones after it and
        stops as soon as a later item starts at or after the current item's end, so
        it is a sort plus a short scan instead of checking every pair.
        """
        ordered = sorted(items, key=lambda item: item.start)
        conflicts = []
        for i, first in enumerate(ordered):
            for second in ordered[i + 1:]:
                if second.start >= first.end:
                    break
                conflicts.append((first.task, second.task))
        return conflicts

    @staticmethod
    def _place(
        task: Task, busy: list[tuple[int, int]], window_start: int, window_end: int
    ) -> tuple[Optional[int], str]:
        """Pick a start time (in minutes) for the task, or None if nothing fits.

        Uses the preferred time when that slot is free and inside the day window.
        Otherwise it tries the window start plus the moments just before and after
        every busy block: a task with a preferred time takes the free start nearest
        to it, and an untimed task takes the earliest one. Returns the start and a
        reason string that explains the choice.
        """
        length = task.duration_minutes

        def is_free(start: int) -> bool:
            end = start + length
            return (window_start <= start and end <= window_end
                    and all(end <= b_start or start >= b_end for b_start, b_end in busy))

        label = task.priority.name.lower()
        if task.preferred_time is not None:
            wanted = _to_minutes(task.preferred_time)
            if is_free(wanted):
                return wanted, f"{label} priority, scheduled at its preferred time"

        # Candidate starts: the window start, just after each busy block, and just before.
        candidates = {window_start}
        for b_start, b_end in busy:
            candidates.update((b_end, b_start - length))
        free = sorted(s for s in candidates if is_free(s))
        if not free:
            return None, ""
        if task.preferred_time is not None:
            wanted = _to_minutes(task.preferred_time)
            start = min(free, key=lambda s: (abs(s - wanted), s))
            return start, (f"{label} priority, moved to the nearest free slot "
                           "(preferred time was unavailable)")
        return free[0], f"{label} priority, placed in the earliest free slot"
