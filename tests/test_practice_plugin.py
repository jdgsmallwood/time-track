"""Tests for the practice plugin model, form, and plugin class."""
from datetime import date, time

import pytest

from timetrack.plugins.practice.models import PracticeSession, FOCUS_CHOICES
from timetrack.plugins.practice.forms import PracticeSessionForm
from timetrack.plugins.practice.plugin import PracticePlugin
from timetrack.schedule.models import PlanBlock, PlanWeek, TemplateBlock, TemplateWeek


@pytest.fixture
def template_block(db):
    template = TemplateWeek.objects.create(name="T")
    return TemplateBlock.objects.create(
        template=template, day_of_week=1, start_time=time(18, 0), end_time=time(19, 0),
        title="Piano", plugin_slug="practice",
    )


@pytest.fixture
def plan_block(db):
    week = PlanWeek.objects.create(start_date=date(2024, 6, 17))
    return PlanBlock.objects.create(
        week=week, date=date(2024, 6, 18), start_time=time(18, 0), end_time=time(19, 0),
        title="Piano", plugin_slug="practice",
    )


@pytest.mark.django_db
def test_focus_choices_valid():
    valid = [c[0] for c in FOCUS_CHOICES]
    assert "technique" in valid
    assert "repertoire" in valid
    assert "sight_reading" in valid
    assert "theory" in valid
    assert "improvisation" in valid
    assert "free" in valid


@pytest.mark.django_db
def test_practice_form_valid():
    form = PracticeSessionForm(data={
        "instrument": "Piano",
        "focus": "repertoire",
        "pieces": "Bach Prelude in C",
        "planned_minutes": "60",
        "actual_minutes": "",
        "notes": "",
    })
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_practice_form_invalid_focus():
    form = PracticeSessionForm(data={"instrument": "Guitar", "focus": "jamming"})
    assert not form.is_valid()
    assert "focus" in form.errors


@pytest.mark.django_db
def test_practice_plugin_clone(template_block, plan_block):
    PracticeSession.objects.create(
        template_block=template_block,
        instrument="Piano",
        focus="technique",
        pieces="Hanon exercises",
        planned_minutes=45,
    )
    plugin = PracticePlugin()
    plugin.clone_block_data(template_block, plan_block)

    session = PracticeSession.objects.get(plan_block=plan_block)
    assert session.instrument == "Piano"
    assert session.focus == "technique"
    assert session.pieces == "Hanon exercises"
    assert session.planned_minutes == 45
    assert session.actual_minutes is None  # not cloned


@pytest.mark.django_db
def test_practice_plugin_gcal_description(plan_block):
    PracticeSession.objects.create(
        plan_block=plan_block, instrument="Guitar", focus="improvisation",
        planned_minutes=30, pieces="Blues in A",
    )
    plugin = PracticePlugin()
    desc = plugin.gcal_description(plan_block)
    assert "Guitar" in desc
    assert "Improvisation" in desc
    assert "30 min" in desc
    assert "Blues in A" in desc


@pytest.mark.django_db
def test_practice_plugin_clone_no_session(template_block, plan_block):
    plugin = PracticePlugin()
    plugin.clone_block_data(template_block, plan_block)
    assert not PracticeSession.objects.filter(plan_block=plan_block).exists()
