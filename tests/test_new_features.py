"""Tests for QoL features: copy-forward, flash messages, gcal orphan deletion, week stats, seed."""
from datetime import date, time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from timetrack.core.models import Category
from timetrack.plugins.practice.models import PracticeSession
from timetrack.plugins.running.models import RunSession
from timetrack.schedule.models import PlanBlock, PlanWeek, TemplateWeek
from timetrack.schedule.services import week_stats as _week_stats


# ─── Copy-week-forward ───────────────────────────────────────────────────────

@pytest.fixture
def src_week(db):
    week = PlanWeek.objects.create(start_date=date(2024, 6, 17))
    PlanBlock.objects.create(
        week=week, date=date(2024, 6, 17), start_time=time(9, 0), end_time=time(10, 0),
        title="Standup",
    )
    PlanBlock.objects.create(
        week=week, date=date(2024, 6, 19), start_time=time(7, 0), end_time=time(8, 0),
        title="Run", plugin_slug="running",
    )
    return week


@pytest.mark.django_db
def test_copy_forward_creates_next_week(auth_client, src_week):
    resp = auth_client.post(f"/schedule/plan-weeks/{src_week.pk}/copy-forward/", {"replace": ""})
    assert resp.status_code == 302
    next_week = PlanWeek.objects.filter(start_date=date(2024, 6, 24)).first()
    assert next_week is not None
    assert next_week.blocks.count() == 2


@pytest.mark.django_db
def test_copy_forward_shifts_dates(auth_client, src_week):
    auth_client.post(f"/schedule/plan-weeks/{src_week.pk}/copy-forward/", {"replace": ""})
    next_week = PlanWeek.objects.get(start_date=date(2024, 6, 24))
    dates = list(next_week.blocks.values_list("date", flat=True).order_by("date"))
    assert date(2024, 6, 24) in dates
    assert date(2024, 6, 26) in dates


@pytest.mark.django_db
def test_copy_forward_copies_plugin_data(auth_client, src_week):
    run_block = src_week.blocks.get(title="Run")
    RunSession.objects.create(
        plan_block=run_block, run_type="tempo", planned_km=Decimal("8.0"), planned_pace="4:30/km"
    )
    auth_client.post(f"/schedule/plan-weeks/{src_week.pk}/copy-forward/", {"replace": ""})
    next_week = PlanWeek.objects.get(start_date=date(2024, 6, 24))
    next_run = next_week.blocks.get(title="Run")
    session = RunSession.objects.filter(plan_block=next_run).first()
    assert session is not None
    assert session.run_type == "tempo"
    assert session.planned_km == Decimal("8.0")


@pytest.mark.django_db
def test_copy_forward_errors_if_exists(auth_client, src_week):
    PlanWeek.objects.create(start_date=date(2024, 6, 24))
    resp = auth_client.post(f"/schedule/plan-weeks/{src_week.pk}/copy-forward/", {"replace": ""})
    assert resp.status_code == 302
    assert not PlanWeek.objects.get(start_date=date(2024, 6, 24)).blocks.exists()


@pytest.mark.django_db
def test_copy_forward_replace_overwrites(auth_client, src_week):
    existing = PlanWeek.objects.create(start_date=date(2024, 6, 24))
    PlanBlock.objects.create(
        week=existing, date=date(2024, 6, 24), start_time=time(10, 0), end_time=time(11, 0),
        title="Old block",
    )
    auth_client.post(f"/schedule/plan-weeks/{src_week.pk}/copy-forward/", {"replace": "1"})
    existing.refresh_from_db()
    assert existing.blocks.count() == 2
    assert not existing.blocks.filter(title="Old block").exists()


# ─── Flash messages on clone ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_clone_success_flash_message(auth_client):
    template = TemplateWeek.objects.create(name="T")
    resp = auth_client.post(
        "/schedule/weeks/2024-07-01/",
        {"template": template.pk, "replace": ""},
        follow=True,
    )
    msgs = [str(m) for m in resp.context["messages"]]
    assert any("Cloned" in m for m in msgs)


@pytest.mark.django_db
def test_clone_conflict_flash_message(auth_client):
    template = TemplateWeek.objects.create(name="T")
    PlanWeek.objects.create(start_date=date(2024, 7, 1))
    resp = auth_client.post(
        "/schedule/weeks/2024-07-01/",
        {"template": template.pk, "replace": ""},
        follow=True,
    )
    msgs = [str(m) for m in resp.context["messages"]]
    assert any("already exists" in m or "Replace" in m for m in msgs)


# ─── Weekly stats ─────────────────────────────────────────────────────────────

@pytest.fixture
def stats_week(db):
    cat = Category.objects.create(name="Exercise", color="#22c55e")
    week = PlanWeek.objects.create(start_date=date(2024, 6, 17))
    run_block = PlanBlock.objects.create(
        week=week, date=date(2024, 6, 17), start_time=time(7, 0), end_time=time(8, 0),
        title="Run", plugin_slug="running", category=cat,
    )
    RunSession.objects.create(
        plan_block=run_block, run_type="tempo", planned_km=Decimal("8.0"),
    )
    practice_block = PlanBlock.objects.create(
        week=week, date=date(2024, 6, 18), start_time=time(19, 0), end_time=time(20, 0),
        title="Piano", plugin_slug="practice",
    )
    PracticeSession.objects.create(
        plan_block=practice_block, instrument="Piano", focus="repertoire", planned_minutes=60,
        actual_minutes=55,
    )
    return week


@pytest.mark.django_db
def test_week_stats_hours_by_category(stats_week):
    stats = _week_stats(stats_week)
    assert "Exercise" in stats["hours_by_cat"]
    assert stats["hours_by_cat"]["Exercise"] == Decimal("1")


@pytest.mark.django_db
def test_week_stats_running(stats_week):
    stats = _week_stats(stats_week)
    assert stats["run"]["total_planned_km"] == Decimal("8.0")
    assert stats["run"]["session_count"] == 1
    assert "Tempo" in stats["run"]["km_by_type"]


@pytest.mark.django_db
def test_week_stats_practice_by_instrument(stats_week):
    stats = _week_stats(stats_week)
    assert "Piano" in stats["practice"]
    assert stats["practice"]["Piano"]["planned"] == 60
    assert stats["practice"]["Piano"]["actual"] == 55


@pytest.mark.django_db
def test_week_stats_empty_week(db):
    week = PlanWeek.objects.create(start_date=date(2024, 7, 1))
    stats = _week_stats(week)
    assert stats["total_hours"] == 0
    assert stats["run"]["session_count"] == 0
    assert stats["practice"] == {}


# ─── GCal orphan deletion ─────────────────────────────────────────────────────

@pytest.mark.django_db
def test_gcal_push_deletes_orphaned_event(auth_client):
    """
    If a block was previously pushed then deleted via the UI, its GCal event ID is
    queued in plan_week.gcal_pending_delete_ids and removed on next push.
    """
    from timetrack.gcal.sync import push_week

    week = PlanWeek.objects.create(start_date=date(2024, 6, 17))
    surviving = PlanBlock.objects.create(
        week=week, date=date(2024, 6, 17), start_time=time(9, 0), end_time=time(10, 0),
        title="Surviving", gcal_event_id="surviving-event-id", sync_hash="stale",
    )
    orphan = PlanBlock.objects.create(
        week=week, date=date(2024, 6, 18), start_time=time(9, 0), end_time=time(10, 0),
        title="Orphan", gcal_event_id="orphan-event-id",
    )

    # Simulate UI delete: the view queues the event ID before deleting the block
    auth_client.delete(f"/schedule/plan-blocks/{orphan.pk}/")
    week.refresh_from_db()
    assert "orphan-event-id" in week.gcal_pending_delete_ids

    deleted_calls = []

    def fake_delete(calendarId, eventId):
        deleted_calls.append(eventId)
        m = MagicMock()
        m.execute.return_value = {}
        return m

    service = MagicMock()
    service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "tt-cal", "summary": "Time Tracking"}]
    }
    service.events.return_value.update.return_value.execute.return_value = {"id": "surviving-event-id"}
    service.events.return_value.delete.side_effect = fake_delete

    with patch("timetrack.gcal.sync.get_credentials") as mc, \
         patch("timetrack.gcal.sync.build") as mb:
        mc.return_value = MagicMock()
        mb.return_value = service
        result = push_week(week)

    assert "orphan-event-id" in deleted_calls
    assert result["deleted"] == 1
    # pending list should be cleared after successful push
    week.refresh_from_db()
    assert week.gcal_pending_delete_ids == []


# ─── Seed command ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_seed_demo_creates_categories_and_template():
    from django.core.management import call_command
    call_command("seed_demo")
    assert Category.objects.filter(name="Exercise").exists()
    assert Category.objects.filter(name="Music").exists()
    assert TemplateWeek.objects.filter(name="Default Week").exists()


@pytest.mark.django_db
def test_seed_demo_creates_run_sessions():
    from django.core.management import call_command
    call_command("seed_demo")
    assert RunSession.objects.filter(run_type="tempo").exists()
    assert RunSession.objects.filter(run_type="long").exists()


@pytest.mark.django_db
def test_seed_demo_creates_practice_sessions():
    from django.core.management import call_command
    call_command("seed_demo")
    assert PracticeSession.objects.filter(instrument="Piano").exists()
    assert PracticeSession.objects.filter(instrument="Guitar").exists()


@pytest.mark.django_db
def test_seed_demo_idempotent(db):
    from django.core.management import call_command
    call_command("seed_demo")
    call_command("seed_demo")  # second call should be a no-op (data exists)
    assert Category.objects.filter(name="Exercise").count() == 1


# ─── Category delete partial ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_category_delete_returns_partial(auth_client):
    cat = Category.objects.create(name="ToDelete", color="#ff0000")
    resp = auth_client.delete(f"/settings/categories/{cat.pk}/")
    assert resp.status_code == 200
    assert not Category.objects.filter(pk=cat.pk).exists()
