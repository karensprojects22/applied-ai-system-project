from datetime import date, time

from pawpal_system import Owner, Pet, Priority, Recurrence, Scheduler, Task


def build_demo_owner(today: date) -> Owner:
    owner = Owner(
        "Karen",
        available_minutes_per_day=120,
        day_start=time(7, 0),
        day_end=time(21, 0),
    )

    biscuit = Pet("Biscuit", "dog", breed="Golden Retriever", age=3)
    mochi = Pet("Mochi", "cat", breed="Siamese", age=5, special_needs="thyroid meds")
    owner.add_pet(biscuit)
    owner.add_pet(mochi)

    # Tasks are added deliberately out of time order, and one has no time at all.
    biscuit.add_task(Task("Brush coat", "grooming", 20, Priority.LOW,
                          preferred_time=time(18, 0), recurrence=Recurrence.WEEKLY))
    mochi.add_task(Task("Feather wand play", "enrichment", 15, Priority.MEDIUM,
                        preferred_time=time(12, 30)))
    biscuit.add_task(Task("Refill water bowl", "feeding", 5, Priority.LOW))
    mochi.add_task(Task("Thyroid medication", "meds", 5, Priority.HIGH,
                        preferred_time=time(8, 0), recurrence=Recurrence.DAILY))
    biscuit.add_task(Task("Morning walk", "walk", 30, Priority.HIGH,
                          preferred_time=time(7, 30), recurrence=Recurrence.DAILY))

    # Two pairs of tasks share a start time: one across pets, one for the same pet.
    biscuit.add_task(Task("Training session", "enrichment", 20, Priority.MEDIUM,
                          preferred_time=time(12, 30)))  # clashes with Mochi's play
    biscuit.add_task(Task("Flea treatment", "meds", 5, Priority.MEDIUM,
                          preferred_time=time(18, 0)))  # clashes with Biscuit's brushing

    # Breakfast is already done today, so completing it also queues tomorrow's.
    breakfast = Task("Breakfast", "feeding", 10, Priority.HIGH,
                     preferred_time=time(7, 0), recurrence=Recurrence.DAILY)
    biscuit.add_task(breakfast)
    biscuit.complete_task(breakfast.id, today)
    return owner


def print_tasks(heading: str, tasks: list[Task], owner: Owner) -> None:
    print(f"\n{heading}")
    if not tasks:
        print("  (none)")
    for task in tasks:
        when = f"{task.preferred_time:%H:%M}" if task.preferred_time else " any "
        pet = owner.find_pet(task.pet_id).name
        status = "done" if task.last_completed else "pending"
        due = f", due {task.due_date}" if task.due_date else ""
        print(f"  {when}  {task.title:<20} {pet:<8} {status}{due}")


def print_sorting_and_filtering(owner: Owner) -> None:
    scheduler = Scheduler(owner)

    print("=" * 60)
    print("Sorting and filtering check")
    print("=" * 60)
    print_tasks("As added (out of order):", owner.get_all_tasks(), owner)
    print_tasks("Sorted by time:", scheduler.sort_by_time(owner.get_all_tasks()), owner)
    print_tasks("Filtered: pet = Mochi", owner.filter_tasks(pet_name="Mochi"), owner)
    print_tasks("Filtered: completed only", owner.filter_tasks(completed=True), owner)
    print_tasks("Filtered: pending only, sorted by time",
                scheduler.sort_by_time(owner.filter_tasks(completed=False)), owner)
    print_tasks("Filtered: pet = Biscuit and pending, sorted by time",
                scheduler.sort_by_time(
                    owner.filter_tasks(pet_name="Biscuit", completed=False)), owner)


def print_schedule(owner: Owner, today: date) -> None:
    plan = Scheduler(owner).generate_plan(today)

    print("\n" + "=" * 60)
    print(f"Today's Schedule - {today:%A, %B %d, %Y}")
    print(f"Owner: {owner.name} | Pets: {', '.join(p.name for p in owner.pets)}")
    print("-" * 60)
    for item in plan.scheduled_items:
        pet = owner.find_pet(item.task.pet_id)
        print(f"{item.start:%H:%M}-{item.end:%H:%M}  {item.task.title:<20} "
              f"[{pet.name}, {item.task.priority.name.lower()}]")
        print(f"             why: {item.reason}")
    for warning in plan.warnings:
        print(f"\nWarning: time conflict - {warning}")
    if plan.skipped_tasks:
        print("\nSkipped:")
        for skipped in plan.skipped_tasks:
            print(f"  {skipped.task.title}: {skipped.reason}")
    print("-" * 60)
    print(f"Total: {plan.total_duration()} of {owner.available_minutes_per_day} min")


if __name__ == "__main__":
    today = date.today()
    demo_owner = build_demo_owner(today)
    print_sorting_and_filtering(demo_owner)
    print_schedule(demo_owner, today)
