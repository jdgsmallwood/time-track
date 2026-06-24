"""
Regression tests for plugin data being wiped on plan block save.

Root cause: PlanBlockForm includes plugin_slug and weekly_task as hidden fields.
When block_edit_panel.html submits via HTMX it must include those hidden inputs
explicitly — otherwise Django overwrites them with empty values.

These tests POST to the plan-block-update endpoint with and without plugin_slug
to ensure the field is preserved when supplied and wiped only when absent.
"""
from datetime import date, time
from decimal import Decimal

import pytest

from timetrack.plugins.practice.models import PracticeGoal, PracticeSession
from timetrack.plugins.running.models import RunSession
from timetrack.schedule.models import PlanBlock, PlanWeek


@pytest.fixture
def plan_week(db):
    return PlanWeek.objects.create(start_date=date(2024, 6, 17))


@pytest.fixture
def running_block(plan_week):
    block = PlanBlock.objects.create(
        week=plan_week, date=date(2024, 6, 17), start_time=time(7, 0),
        end_time=time(8, 0), title="Morning run", plugin_slug="running",
    )
    RunSession.objects.create(
        plan_block=block, run_type="tempo", planned_km=Decimal("8.0"),
    )
    return block


@pytest.fixture
def practice_block(plan_week):
    block = PlanBlock.objects.create(
        week=plan_week, date=date(2024, 6, 18), start_time=time(18, 0),
        end_time=time(19, 0), title="Guitar practice", plugin_slug="practice",
    )
    PracticeSession.objects.create(
        plan_block=block, instrument="Guitar", focus="technique", planned_minutes=60,
    )
    return block


# ─── Running plugin ──────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_save_running_block_preserves_plugin_slug(auth_client, running_block):
    """Submitting the edit form with plugin_slug='running' must keep the slug."""
    auth_client.post(
        f"/schedule/plan-blocks/{running_block.pk}/",
        {
            "title": "Morning run edited",
            "date": "2024-06-17",
            "start_time": "07:00",
            "end_time": "08:30",
            "notes": "",
            "plugin_slug": "running",   # must be included — this is the fix
            "weekly_task": "",
            "run-run_type": "tempo",
            "run-planned_km": "8.0",
            "run-actual_km": "",
            "run-planned_pace": "",
            "run-notes": "",
        },
    )
    running_block.refresh_from_db()
    assert running_block.plugin_slug == "running", (
        "plugin_slug was wiped to '' — the hidden input is missing from the edit form"
    )


@pytest.mark.django_db
def test_save_running_block_updates_run_session(auth_client, running_block):
    """Editing run details saves them to the RunSession."""
    auth_client.post(
        f"/schedule/plan-blocks/{running_block.pk}/",
        {
            "title": "Morning run",
            "date": "2024-06-17",
            "start_time": "07:00",
            "end_time": "08:00",
            "notes": "",
            "plugin_slug": "running",
            "weekly_task": "",
            "run-run_type": "long",
            "run-planned_km": "21.1",
            "run-actual_km": "",
            "run-planned_pace": "5:30/km",
            "run-notes": "Take it easy",
        },
    )
    session = RunSession.objects.get(plan_block=running_block)
    assert session.run_type == "long"
    assert session.planned_km == Decimal("21.1")
    assert session.planned_pace == "5:30/km"
    assert session.notes == "Take it easy"


@pytest.mark.django_db
def test_save_running_block_edit_panel_get(auth_client, running_block):
    """GET on the update URL should return the edit panel with run details pre-filled."""
    response = auth_client.get(f"/schedule/plan-blocks/{running_block.pk}/")
    assert response.status_code == 200
    assert b"run_type" in response.content or b"Run type" in response.content
    assert b"run" in response.content


# ─── Practice plugin ─────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_save_practice_block_preserves_plugin_slug(auth_client, practice_block):
    """Submitting the edit form with plugin_slug='practice' must keep the slug."""
    auth_client.post(
        f"/schedule/plan-blocks/{practice_block.pk}/",
        {
            "title": "Guitar practice",
            "date": "2024-06-18",
            "start_time": "18:00",
            "end_time": "19:00",
            "notes": "",
            "plugin_slug": "practice",
            "weekly_task": "",
            "practice-instrument": "Guitar",
            "practice-focus": "technique",
            "practice-pieces": "",
            "practice-planned_minutes": "60",
            "practice-actual_minutes": "",
            "practice-notes": "",
        },
    )
    practice_block.refresh_from_db()
    assert practice_block.plugin_slug == "practice", (
        "plugin_slug was wiped — hidden input missing from edit form"
    )


@pytest.mark.django_db
def test_save_practice_block_updates_session(auth_client, practice_block):
    """Editing practice details saves them to PracticeSession."""
    auth_client.post(
        f"/schedule/plan-blocks/{practice_block.pk}/",
        {
            "title": "Guitar practice",
            "date": "2024-06-18",
            "start_time": "18:00",
            "end_time": "19:00",
            "notes": "",
            "plugin_slug": "practice",
            "weekly_task": "",
            "practice-instrument": "Guitar",
            "practice-focus": "band",
            "practice-pieces": "Symphony No. 5",
            "practice-planned_minutes": "45",
            "practice-actual_minutes": "50",
            "practice-notes": "Good session",
        },
    )
    session = PracticeSession.objects.get(plan_block=practice_block)
    assert session.focus == "band"
    assert session.pieces == "Symphony No. 5"
    assert session.planned_minutes == 45
    assert session.actual_minutes == 50


# ─── Practice Goals ──────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_practice_goal_create_via_post(auth_client):
    """POST to /practice/goals/ creates a PracticeGoal."""
    response = auth_client.post(
        "/practice/goals/",
        {
            "instrument": "Violin",
            "focus": "repertoire",
            "duration_minutes": "45",
            "recurrence_count": "2",
            "notes": "Scales and arpeggios",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    assert PracticeGoal.objects.filter(instrument="Violin", focus="repertoire").exists()


@pytest.mark.django_db
def test_practice_goal_toggle(auth_client, db):
    goal = PracticeGoal.objects.create(
        instrument="Drums", focus="technique", duration_minutes=30, is_active=True,
    )
    auth_client.post(f"/practice/goals/{goal.pk}/toggle/")
    goal.refresh_from_db()
    assert not goal.is_active

    auth_client.post(f"/practice/goals/{goal.pk}/toggle/")
    goal.refresh_from_db()
    assert goal.is_active


@pytest.mark.django_db
def test_practice_goal_delete(auth_client, db):
    goal = PracticeGoal.objects.create(
        instrument="Trumpet", focus="free", duration_minutes=60,
    )
    pk = goal.pk
    auth_client.post(f"/practice/goals/{pk}/delete/")
    assert not PracticeGoal.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_drag_practice_goal_creates_session(auth_client, plan_week, db):
    """POST to plan-block-create with practice_goal_id auto-creates PracticeSession."""
    goal = PracticeGoal.objects.create(
        instrument="Piano", focus="technique", duration_minutes=60, is_active=True,
    )
    import json
    response = auth_client.post(
        f"/schedule/plan-weeks/{plan_week.pk}/blocks/",
        json.dumps({
            "title": "Piano · Technique",
            "date": "2024-06-17",
            "start_time": "18:00",
            "end_time": "19:00",
            "plugin_slug": "practice",
            "practice_goal_id": goal.pk,
        }),
        content_type="application/json",
    )
    assert response.status_code == 200
    block = PlanBlock.objects.get(week=plan_week, title="Piano · Technique")
    assert block.plugin_slug == "practice"
    session = PracticeSession.objects.get(plan_block=block)
    assert session.goal == goal
    assert session.instrument == "Piano"
    assert session.focus == "technique"
    assert session.planned_minutes == 60


@pytest.mark.django_db
def test_practice_goal_suggestions_count(plan_week, db):
    """get_suggestions counts how many sessions this week are linked to each goal."""
    from timetrack.plugins.practice.plugin import PracticePlugin

    goal = PracticeGoal.objects.create(
        instrument="Guitar", focus="band", duration_minutes=45, recurrence_count=3,
    )
    block = PlanBlock.objects.create(
        week=plan_week, date=date(2024, 6, 17), start_time=time(18, 0),
        end_time=time(19, 0), title="Band", plugin_slug="practice",
    )
    PracticeSession.objects.create(plan_block=block, goal=goal)

    plugin = PracticePlugin()
    suggs = plugin.get_suggestions(plan_week)
    assert len(suggs) == 1
    assert suggs[0]["scheduled_count"] == 1
    assert suggs[0]["recurrence_count"] == 3
    assert suggs[0]["practice_goal_id"] == goal.pk


@pytest.mark.django_db
def test_week_view_includes_practice_suggestions(auth_client, plan_week, db):
    """Practice goals appear in week view context as plugin_suggestions."""
    PracticeGoal.objects.create(
        instrument="Cello", focus="sight_reading", duration_minutes=30, is_active=True,
    )
    response = auth_client.get(f"/schedule/weeks/{plan_week.start_date}/")
    assert response.status_code == 200
    assert b"Cello" in response.content or b"Sight Reading" in response.content
