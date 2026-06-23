"""Tests for the running plugin model, form, and plugin class."""
from datetime import date, time
from decimal import Decimal

import pytest

from timetrack.plugins.running.models import RunSession, RUN_TYPE_CHOICES
from timetrack.plugins.running.forms import RunSessionForm
from timetrack.plugins.running.plugin import RunningPlugin
from timetrack.schedule.models import PlanBlock, PlanWeek, TemplateBlock, TemplateWeek


@pytest.fixture
def template_block(db):
    template = TemplateWeek.objects.create(name="T")
    return TemplateBlock.objects.create(
        template=template, day_of_week=0, start_time=time(7, 0), end_time=time(8, 0),
        title="Run", plugin_slug="running",
    )


@pytest.fixture
def plan_block(db):
    week = PlanWeek.objects.create(start_date=date(2024, 6, 17))
    return PlanBlock.objects.create(
        week=week, date=date(2024, 6, 17), start_time=time(7, 0), end_time=time(8, 0),
        title="Run", plugin_slug="running",
    )


@pytest.mark.django_db
def test_run_type_choices_valid():
    valid_types = [c[0] for c in RUN_TYPE_CHOICES]
    assert "base" in valid_types
    assert "tempo" in valid_types
    assert "intervals" in valid_types
    assert "long" in valid_types
    assert "recovery" in valid_types
    assert "race" in valid_types


@pytest.mark.django_db
def test_run_session_form_valid():
    form = RunSessionForm(data={
        "run_type": "tempo",
        "planned_km": "8.0",
        "actual_km": "",
        "planned_pace": "4:30/km",
        "notes": "",
    })
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_run_session_form_invalid_run_type():
    form = RunSessionForm(data={"run_type": "sprinting"})
    assert not form.is_valid()
    assert "run_type" in form.errors


@pytest.mark.django_db
def test_running_plugin_clone(template_block, plan_block):
    RunSession.objects.create(
        template_block=template_block,
        run_type="tempo",
        planned_km=Decimal("8.0"),
        planned_pace="4:30/km",
    )
    plugin = RunningPlugin()
    plugin.clone_block_data(template_block, plan_block)

    session = RunSession.objects.get(plan_block=plan_block)
    assert session.run_type == "tempo"
    assert session.planned_km == Decimal("8.0")
    assert session.planned_pace == "4:30/km"
    assert session.actual_km is None  # not cloned


@pytest.mark.django_db
def test_running_plugin_gcal_description(plan_block):
    RunSession.objects.create(
        plan_block=plan_block, run_type="long", planned_km=Decimal("21.1"),
        planned_pace="5:00/km",
    )
    plugin = RunningPlugin()
    desc = plugin.gcal_description(plan_block)
    assert "Long Run" in desc
    assert "21.1" in desc
    assert "5:00/km" in desc


@pytest.mark.django_db
def test_running_plugin_gcal_description_no_session(plan_block):
    plugin = RunningPlugin()
    assert plugin.gcal_description(plan_block) == ""


@pytest.mark.django_db
def test_running_plugin_clone_no_session(template_block, plan_block):
    """clone_block_data is a no-op if the template block has no RunSession."""
    plugin = RunningPlugin()
    plugin.clone_block_data(template_block, plan_block)
    assert not RunSession.objects.filter(plan_block=plan_block).exists()
