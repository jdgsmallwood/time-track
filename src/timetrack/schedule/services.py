from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from .models import PlanBlock, PlanWeek, PlanWeekReflection, TemplateWeek, WeeklyGoal


def iso_week_monday(year: int, week: int) -> date:
    """Return the Monday of a given ISO year/week."""
    return date.fromisocalendar(year, week, 1)


def week_monday(d: date) -> date:
    """Return the Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


def clone_template_to_week(
    template: TemplateWeek,
    start_date: date,
    replace: bool = False,
) -> PlanWeek:
    """
    Create a PlanWeek from a TemplateWeek.

    If a PlanWeek already exists for start_date and replace=False, raises ValueError.
    If replace=True, deletes existing blocks before re-cloning.
    Plugin data is cloned via the plugin registry if a plugin_slug is set.
    """
    from timetrack.plugins.registry import get_registry

    start_date = week_monday(start_date)

    existing = PlanWeek.objects.filter(start_date=start_date).first()
    if existing:
        if not replace:
            raise ValueError(f"A plan week already exists for {start_date}.")
        existing.blocks.all().delete()
        plan_week = existing
        plan_week.source_template = template
        plan_week.status = "draft"
        plan_week.save()
    else:
        plan_week = PlanWeek.objects.create(
            start_date=start_date,
            source_template=template,
        )

    registry = get_registry()
    for tb in template.blocks.select_related("category").all():
        block_date = start_date + timedelta(days=tb.day_of_week)
        plan_block = PlanBlock.objects.create(
            week=plan_week,
            date=block_date,
            start_time=tb.start_time,
            end_time=tb.end_time,
            title=tb.title,
            category=tb.category,
            notes=tb.notes,
            plugin_slug=tb.plugin_slug,
            source_template_block=tb,
        )
        if tb.plugin_slug:
            plugin = registry.get(tb.plugin_slug)
            if plugin:
                plugin.clone_block_data(tb, plan_block)

    return plan_week


def get_or_create_reflection(plan_week: PlanWeek) -> PlanWeekReflection:
    reflection, _created = PlanWeekReflection.objects.get_or_create(week=plan_week)
    return reflection


def should_show_planning_prompt(plan_week: PlanWeek | None, today: date | None = None) -> bool:
    if not plan_week:
        return False
    reflection = getattr(plan_week, "reflection", None)
    if reflection and reflection.planning_completed_at:
        return False

    today = today or timezone.localdate()
    current_monday = week_monday(today)
    if plan_week.start_date == current_monday:
        return today.weekday() <= 3
    return True


def should_show_review_prompt(plan_week: PlanWeek | None, today: date | None = None) -> bool:
    if not plan_week:
        return False
    reflection = getattr(plan_week, "reflection", None)
    if reflection and reflection.review_completed_at:
        return False

    today = today or timezone.localdate()
    current_monday = week_monday(today)
    if plan_week.start_date < current_monday:
        return True
    if plan_week.start_date == current_monday:
        return today.weekday() >= 4
    return False


def complete_planning(plan_week: PlanWeek, reflection_data: dict, goals_data: list[dict]) -> PlanWeekReflection:
    reflection = get_or_create_reflection(plan_week)
    reflection.weekly_intention = reflection_data.get("weekly_intention", "")
    reflection.top_priorities = reflection_data.get("top_priorities", "")
    reflection.planning_completed_at = timezone.now()
    reflection.save()

    plan_week.goals.all().delete()
    goals = []
    for data in goals_data:
        title = data.get("title", "").strip()
        if not title:
            continue
        goals.append(
            WeeklyGoal(
                week=plan_week,
                title=title,
                category=data.get("category", "").strip(),
                priority=data.get("priority") or "medium",
                notes=data.get("notes", "").strip(),
            )
        )
    if goals:
        WeeklyGoal.objects.bulk_create(goals)
    return reflection


def copy_selected_goals_to_next_week(plan_week: PlanWeek, selected_goal_ids: list[int]) -> list[WeeklyGoal]:
    if not selected_goal_ids:
        return []

    copied = []
    goals = list(
        plan_week.goals
        .filter(pk__in=selected_goal_ids)
        .exclude(status="done")
        .order_by("created_at")
    )
    if not goals:
        return []

    next_week, _created = PlanWeek.objects.get_or_create(
        start_date=plan_week.start_date + timedelta(days=7),
        defaults={"source_template": plan_week.source_template},
    )
    for goal in goals:
        copied.append(
            WeeklyGoal.objects.create(
                week=next_week,
                title=goal.title,
                category=goal.category,
                priority=goal.priority,
                notes=goal.notes,
                source_goal=goal,
            )
        )
    return copied


def complete_review(
    plan_week: PlanWeek,
    reflection_data: dict,
    goal_statuses: dict[int, str],
    carryover_goal_ids: list[int],
) -> PlanWeekReflection:
    for goal in plan_week.goals.all():
        status = goal_statuses.get(goal.pk)
        if status in {"planned", "done", "skipped"}:
            goal.status = status
            goal.save(update_fields=["status", "updated_at"])

    reflection = get_or_create_reflection(plan_week)
    for field in ("wins", "misses", "lessons", "next_week_notes", "energy_score"):
        setattr(reflection, field, reflection_data.get(field))
    reflection.review_completed_at = timezone.now()
    reflection.save()
    copy_selected_goals_to_next_week(plan_week, carryover_goal_ids)
    return reflection


def week_stats(plan_week) -> dict:
    """Aggregate stats for a concrete week — used by the week view and dashboard."""
    from timetrack.plugins.practice.models import PracticeSession
    from timetrack.plugins.running.models import RunSession

    blocks = list(plan_week.blocks.select_related("category").all())

    hours_by_cat: dict = defaultdict(Decimal)
    for b in blocks:
        dur = Decimal(str(b.duration_minutes)) / 60
        label = b.category.name if b.category else "Uncategorised"
        hours_by_cat[label] += dur

    run_blocks = [b for b in blocks if b.plugin_slug == "running"]
    run_ids = [b.pk for b in run_blocks]
    sessions = RunSession.objects.filter(plan_block_id__in=run_ids)
    total_planned_km = sum(s.planned_km or 0 for s in sessions)
    total_actual_km = sum(s.actual_km or 0 for s in sessions)
    km_by_type: dict = defaultdict(Decimal)
    for s in sessions:
        km_by_type[s.get_run_type_display()] += s.planned_km or Decimal(0)

    practice_blocks = [b for b in blocks if b.plugin_slug == "practice"]
    pr_ids = [b.pk for b in practice_blocks]
    pr_sessions = PracticeSession.objects.filter(plan_block_id__in=pr_ids)
    practice_by_instrument: dict = defaultdict(lambda: {"planned": 0, "actual": 0})
    for s in pr_sessions:
        key = s.instrument or "Unspecified"
        practice_by_instrument[key]["planned"] += s.planned_minutes or 0
        practice_by_instrument[key]["actual"] += s.actual_minutes or 0

    return {
        "hours_by_cat": dict(sorted(hours_by_cat.items(), key=lambda x: x[1], reverse=True)),
        "total_hours": sum(hours_by_cat.values()),
        "run": {
            "total_planned_km": total_planned_km,
            "total_actual_km": total_actual_km,
            "km_by_type": dict(km_by_type),
            "session_count": len(run_blocks),
        },
        "practice": dict(practice_by_instrument),
    }
