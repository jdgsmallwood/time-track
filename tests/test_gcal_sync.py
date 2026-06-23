"""Tests for the Google Calendar sync engine — Google client is mocked."""
from datetime import date, time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from timetrack.gcal.sync import _block_hash, push_week
from timetrack.schedule.models import PlanBlock, PlanWeek


@pytest.fixture
def plan_week(db):
    week = PlanWeek.objects.create(start_date=date(2024, 6, 17))
    PlanBlock.objects.create(
        week=week, date=date(2024, 6, 17), start_time=time(9, 0), end_time=time(10, 0),
        title="Standup", notes="",
    )
    PlanBlock.objects.create(
        week=week, date=date(2024, 6, 18), start_time=time(7, 0), end_time=time(8, 0),
        title="Run", notes="",
    )
    return week


def _make_service_mock(existing_event_id=None):
    service = MagicMock()
    service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "tt-cal-id", "summary": "Time Tracking"}]
    }
    insert_result = {"id": "new-event-id"}
    service.events.return_value.insert.return_value.execute.return_value = insert_result
    service.events.return_value.update.return_value.execute.return_value = {"id": existing_event_id or "upd-id"}
    return service


@pytest.mark.django_db
def test_push_creates_events_when_none_exist(plan_week):
    with patch("timetrack.gcal.sync.get_credentials") as mock_creds, \
         patch("timetrack.gcal.sync.build") as mock_build:
        mock_creds.return_value = MagicMock()
        mock_build.return_value = _make_service_mock()

        result = push_week(plan_week)

    assert result["created"] == 2
    assert result["updated"] == 0
    assert result["skipped"] == 0

    plan_week.refresh_from_db()
    assert plan_week.status == "synced"
    for block in plan_week.blocks.all():
        assert block.gcal_event_id == "new-event-id"
        assert block.sync_hash != ""


@pytest.mark.django_db
def test_push_skips_unchanged_blocks(plan_week):
    # Pre-populate with existing event ids and hashes
    for block in plan_week.blocks.all():
        block.gcal_event_id = "existing-id"
        block.sync_hash = _block_hash(block)
        block.save()

    with patch("timetrack.gcal.sync.get_credentials") as mock_creds, \
         patch("timetrack.gcal.sync.build") as mock_build:
        mock_creds.return_value = MagicMock()
        mock_build.return_value = _make_service_mock()

        result = push_week(plan_week)

    assert result["skipped"] == 2
    assert result["created"] == 0
    assert result["updated"] == 0


@pytest.mark.django_db
def test_push_updates_changed_blocks(plan_week):
    # Pre-populate with existing event ids but stale hashes
    for block in plan_week.blocks.all():
        block.gcal_event_id = "existing-id"
        block.sync_hash = "stale-hash"
        block.save()

    with patch("timetrack.gcal.sync.get_credentials") as mock_creds, \
         patch("timetrack.gcal.sync.build") as mock_build:
        mock_creds.return_value = MagicMock()
        mock_build.return_value = _make_service_mock()

        result = push_week(plan_week)

    assert result["updated"] == 2
    assert result["created"] == 0
    assert result["skipped"] == 0


@pytest.mark.django_db
def test_push_raises_when_not_connected(plan_week):
    with patch("timetrack.gcal.sync.get_credentials", return_value=None):
        with pytest.raises(RuntimeError, match="not connected"):
            push_week(plan_week)


@pytest.mark.django_db
def test_push_includes_plugin_description(plan_week):
    """When a running plugin session exists, its description appears in the event."""
    from timetrack.plugins.running.models import RunSession
    run_block = plan_week.blocks.get(title="Run")
    run_block.plugin_slug = "running"
    run_block.save()
    RunSession.objects.create(
        plan_block=run_block, run_type="tempo", planned_km=Decimal("8.0"), planned_pace="4:30/km"
    )

    captured_bodies = []

    def fake_insert(calendarId, body):
        captured_bodies.append(body)
        m = MagicMock()
        m.execute.return_value = {"id": "new-id"}
        return m

    service = _make_service_mock()
    service.events.return_value.insert.side_effect = fake_insert

    with patch("timetrack.gcal.sync.get_credentials") as mock_creds, \
         patch("timetrack.gcal.sync.build") as mock_build:
        mock_creds.return_value = MagicMock()
        mock_build.return_value = service
        push_week(plan_week)

    run_body = next(b for b in captured_bodies if b["summary"] == "Run")
    assert "Tempo" in run_body["description"]
    assert "8.0" in run_body["description"]


def test_block_hash_is_deterministic(db):
    week = PlanWeek.objects.create(start_date=date(2024, 6, 17))
    block = PlanBlock.objects.create(
        week=week, date=date(2024, 6, 17), start_time=time(9, 0), end_time=time(10, 0),
        title="Test", notes="",
    )
    assert _block_hash(block) == _block_hash(block)


def test_block_hash_changes_with_title(db):
    week = PlanWeek.objects.create(start_date=date(2024, 6, 17))
    b1 = PlanBlock.objects.create(
        week=week, date=date(2024, 6, 17), start_time=time(9, 0), end_time=time(10, 0),
        title="A", notes="",
    )
    b2 = PlanBlock.objects.create(
        week=week, date=date(2024, 6, 18), start_time=time(9, 0), end_time=time(10, 0),
        title="B", notes="",
    )
    assert _block_hash(b1) != _block_hash(b2)
