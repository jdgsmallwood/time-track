from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from .models import PlanBlock, PlanWeek, TemplateWeek


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
