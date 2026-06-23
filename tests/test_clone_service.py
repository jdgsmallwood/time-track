"""Tests for the template→week clone service."""
from datetime import date, time

import pytest

from timetrack.core.models import Category
from timetrack.schedule.models import PlanBlock, PlanWeek, TemplateBlock, TemplateWeek
from timetrack.schedule.services import clone_template_to_week, week_monday


@pytest.fixture
def category(db):
    return Category.objects.create(name="Work", color="#6366f1")


@pytest.fixture
def template(db):
    return TemplateWeek.objects.create(name="Default Week", is_default=True)


@pytest.fixture
def template_with_blocks(template, category):
    TemplateBlock.objects.create(
        template=template, day_of_week=0, start_time=time(9, 0), end_time=time(10, 0),
        title="Morning standup", category=category,
    )
    TemplateBlock.objects.create(
        template=template, day_of_week=2, start_time=time(14, 0), end_time=time(15, 30),
        title="Deep work", category=category,
    )
    TemplateBlock.objects.create(
        template=template, day_of_week=4, start_time=time(17, 0), end_time=time(18, 0),
        title="Run", plugin_slug="running",
    )
    return template


@pytest.mark.django_db
def test_week_monday():
    assert week_monday(date(2024, 6, 19)) == date(2024, 6, 17)  # Wed → Mon
    assert week_monday(date(2024, 6, 17)) == date(2024, 6, 17)  # Mon stays Mon
    assert week_monday(date(2024, 6, 23)) == date(2024, 6, 17)  # Sun → Mon


@pytest.mark.django_db
def test_clone_creates_plan_week(template_with_blocks):
    start = date(2024, 6, 17)  # Monday
    plan_week = clone_template_to_week(template_with_blocks, start)

    assert plan_week.start_date == start
    assert plan_week.source_template == template_with_blocks
    assert plan_week.status == "draft"


@pytest.mark.django_db
def test_clone_creates_correct_blocks(template_with_blocks):
    start = date(2024, 6, 17)
    plan_week = clone_template_to_week(template_with_blocks, start)

    blocks = list(plan_week.blocks.order_by("date", "start_time"))
    assert len(blocks) == 3

    # Monday block
    assert blocks[0].date == date(2024, 6, 17)  # Monday
    assert blocks[0].title == "Morning standup"
    assert blocks[0].start_time == time(9, 0)
    assert blocks[0].end_time == time(10, 0)

    # Wednesday block
    assert blocks[1].date == date(2024, 6, 19)
    assert blocks[1].title == "Deep work"

    # Friday block
    assert blocks[2].date == date(2024, 6, 21)
    assert blocks[2].title == "Run"
    assert blocks[2].plugin_slug == "running"


@pytest.mark.django_db
def test_clone_links_source_template_block(template_with_blocks):
    plan_week = clone_template_to_week(template_with_blocks, date(2024, 6, 17))
    for pb in plan_week.blocks.all():
        assert pb.source_template_block is not None


@pytest.mark.django_db
def test_clone_copies_category(template_with_blocks, category):
    plan_week = clone_template_to_week(template_with_blocks, date(2024, 6, 17))
    monday_block = plan_week.blocks.get(date=date(2024, 6, 17))
    assert monday_block.category == category


@pytest.mark.django_db
def test_clone_normalizes_to_monday(template_with_blocks):
    # Pass a Wednesday — service should snap to the Monday of that week
    plan_week = clone_template_to_week(template_with_blocks, date(2024, 6, 19))
    assert plan_week.start_date == date(2024, 6, 17)


@pytest.mark.django_db
def test_clone_raises_if_week_exists(template_with_blocks):
    start = date(2024, 6, 17)
    clone_template_to_week(template_with_blocks, start)
    with pytest.raises(ValueError, match="already exists"):
        clone_template_to_week(template_with_blocks, start)


@pytest.mark.django_db
def test_clone_replace_clears_old_blocks(template_with_blocks):
    start = date(2024, 6, 17)
    clone_template_to_week(template_with_blocks, start)
    # Add an extra manual block to the week
    week = PlanWeek.objects.get(start_date=start)
    PlanBlock.objects.create(
        week=week, date=date(2024, 6, 18), start_time=time(8, 0), end_time=time(9, 0),
        title="Manual block",
    )
    assert week.blocks.count() == 4

    # Re-clone with replace=True
    clone_template_to_week(template_with_blocks, start, replace=True)
    week.refresh_from_db()
    assert week.blocks.count() == 3  # manual block gone


@pytest.mark.django_db
def test_template_week_only_one_default():
    t1 = TemplateWeek.objects.create(name="T1", is_default=True)
    t2 = TemplateWeek.objects.create(name="T2", is_default=True)
    t1.refresh_from_db()
    assert not t1.is_default
    assert t2.is_default
