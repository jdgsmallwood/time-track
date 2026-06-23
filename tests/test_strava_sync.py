"""Tests for Strava OAuth and sync logic."""
import time
from datetime import date, datetime, time as dtime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from timetrack.schedule.models import PlanBlock, PlanWeek


# ─── OAuth helpers ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_strava_is_connected_false_by_default():
    from timetrack.strava.oauth import is_connected
    assert not is_connected()


@pytest.mark.django_db
def test_strava_disconnect_clears():
    from timetrack.strava.models import StravaCredentials
    from timetrack.strava.oauth import disconnect, is_connected

    StravaCredentials.objects.create(
        pk=1, athlete_id=123, access_token="tok", refresh_token="ref",
        expires_at=int(time.time()) + 3600,
    )
    assert is_connected()
    disconnect()
    assert not is_connected()


@pytest.mark.django_db
def test_exchange_code_creates_credentials():
    from timetrack.strava.oauth import exchange_code

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_at": int(time.time()) + 3600,
        "athlete": {"id": 42, "firstname": "Jay", "lastname": "Test"},
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("timetrack.strava.oauth.requests.post", return_value=mock_resp):
        creds = exchange_code("some-code")

    assert creds.athlete_id == 42
    assert creds.access_token == "new_access"
    assert creds.athlete_name == "Jay Test"


@pytest.mark.django_db
def test_get_access_token_refreshes_if_expired():
    from timetrack.strava.models import StravaCredentials
    from timetrack.strava.oauth import get_access_token

    StravaCredentials.objects.create(
        pk=1, athlete_id=1, access_token="old_tok", refresh_token="ref",
        expires_at=int(time.time()) - 100,  # already expired
    )
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "access_token": "refreshed_tok",
        "refresh_token": "new_ref",
        "expires_at": int(time.time()) + 3600,
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("timetrack.strava.oauth.requests.post", return_value=mock_resp):
        token = get_access_token()

    assert token == "refreshed_tok"


# ─── Sync logic ───────────────────────────────────────────────────────────────

def _make_activity(strava_id, date_str, distance_m, avg_speed_ms, run_type="Run"):
    return {
        "id": strava_id,
        "type": run_type,
        "start_date_local": f"{date_str}T07:30:00",
        "distance": distance_m,
        "average_speed": avg_speed_ms,
    }


@pytest.fixture
def sync_week(db):
    week = PlanWeek.objects.create(start_date=date(2024, 6, 17))
    b1 = PlanBlock.objects.create(
        week=week, date=date(2024, 6, 17), start_time=dtime(7, 0), end_time=dtime(8, 0),
        title="Easy Run", plugin_slug="running",
    )
    b2 = PlanBlock.objects.create(
        week=week, date=date(2024, 6, 19), start_time=dtime(7, 0), end_time=dtime(8, 0),
        title="Tempo Run", plugin_slug="running",
    )
    return week, b1, b2


@pytest.mark.django_db
def test_strava_sync_matches_by_date(sync_week):
    from timetrack.plugins.running.models import RunSession
    from timetrack.strava.sync import sync_week_activities

    week, b1, b2 = sync_week
    activities = [
        _make_activity(1001, "2024-06-17", 10200, 2.78),  # ~10.2km, ~6:00/km
        _make_activity(1002, "2024-06-19", 6100, 3.33),   # ~6.1km, ~5:00/km
    ]

    mock_resp = MagicMock()
    mock_resp.json.return_value = activities
    mock_resp.raise_for_status = MagicMock()

    with patch("timetrack.strava.sync.get_access_token", return_value="tok"), \
         patch("timetrack.strava.sync.requests.get", return_value=mock_resp):
        result = sync_week_activities(week)

    assert result["matched"] == 2
    assert result["unmatched"] == 0

    s1 = RunSession.objects.filter(plan_block=b1).first()
    assert s1 is not None
    assert s1.strava_activity_id == 1001
    assert s1.actual_km == Decimal("10.2")

    s2 = RunSession.objects.filter(plan_block=b2).first()
    assert s2 is not None
    assert s2.strava_activity_id == 1002


@pytest.mark.django_db
def test_strava_sync_ignores_non_run_activities(sync_week):
    """Cycling activities are silently skipped (not counted as unmatched)."""
    from timetrack.strava.sync import sync_week_activities

    week, _, _ = sync_week
    activities = [
        _make_activity(9001, "2024-06-17", 30000, 8.0, run_type="Ride"),  # cycling, skip
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = activities
    mock_resp.raise_for_status = MagicMock()

    with patch("timetrack.strava.sync.get_access_token", return_value="tok"), \
         patch("timetrack.strava.sync.requests.get", return_value=mock_resp):
        result = sync_week_activities(week)

    assert result["matched"] == 0
    assert result["unmatched"] == 0


@pytest.mark.django_db
def test_strava_sync_unmatched_if_no_block_on_date(sync_week):
    from timetrack.strava.sync import sync_week_activities

    week, _, _ = sync_week
    activities = [
        _make_activity(2001, "2024-06-20", 5000, 3.0),  # Thursday — no block
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = activities
    mock_resp.raise_for_status = MagicMock()

    with patch("timetrack.strava.sync.get_access_token", return_value="tok"), \
         patch("timetrack.strava.sync.requests.get", return_value=mock_resp):
        result = sync_week_activities(week)

    assert result["matched"] == 0
    assert result["unmatched"] == 1


@pytest.mark.django_db
def test_strava_sync_sets_actual_pace(sync_week):
    from timetrack.plugins.running.models import RunSession
    from timetrack.strava.sync import sync_week_activities

    week, b1, _ = sync_week
    # avg_speed 2.78 m/s → 1000/2.78 ≈ 359s/km → 5:59/km
    activities = [_make_activity(1001, "2024-06-17", 10000, 2.78)]
    mock_resp = MagicMock()
    mock_resp.json.return_value = activities
    mock_resp.raise_for_status = MagicMock()

    with patch("timetrack.strava.sync.get_access_token", return_value="tok"), \
         patch("timetrack.strava.sync.requests.get", return_value=mock_resp):
        sync_week_activities(week)

    s = RunSession.objects.filter(plan_block=b1).first()
    assert s.actual_pace != ""
    assert "/km" in s.actual_pace


@pytest.mark.django_db
def test_strava_sync_multiple_blocks_same_day_matches_closest_km(db):
    """When two blocks on same date, choose one closest to activity km."""
    from timetrack.plugins.running.models import RunSession
    from timetrack.strava.sync import sync_week_activities

    week = PlanWeek.objects.create(start_date=date(2024, 6, 17))
    b_short = PlanBlock.objects.create(
        week=week, date=date(2024, 6, 17), start_time=dtime(6, 0), end_time=dtime(6, 45),
        title="Short", plugin_slug="running",
    )
    b_long = PlanBlock.objects.create(
        week=week, date=date(2024, 6, 17), start_time=dtime(16, 0), end_time=dtime(18, 0),
        title="Long", plugin_slug="running",
    )
    RunSession.objects.create(plan_block=b_short, run_type="base", planned_km=Decimal("5"))
    RunSession.objects.create(plan_block=b_long, run_type="long", planned_km=Decimal("20"))

    # Activity is 19.5km — should match b_long
    activities = [_make_activity(999, "2024-06-17", 19500, 2.5)]
    mock_resp = MagicMock()
    mock_resp.json.return_value = activities
    mock_resp.raise_for_status = MagicMock()

    with patch("timetrack.strava.sync.get_access_token", return_value="tok"), \
         patch("timetrack.strava.sync.requests.get", return_value=mock_resp):
        sync_week_activities(week)

    long_session = RunSession.objects.get(plan_block=b_long)
    short_session = RunSession.objects.get(plan_block=b_short)
    assert long_session.strava_activity_id == 999
    assert short_session.strava_activity_id is None


# ─── Strava views ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_strava_settings_view(auth_client):
    resp = auth_client.get("/strava/settings/")
    assert resp.status_code == 200
    assert b"Strava" in resp.content


@pytest.mark.django_db
def test_strava_settings_connected(auth_client):
    from timetrack.strava.models import StravaCredentials
    StravaCredentials.objects.create(
        pk=1, athlete_id=1, athlete_name="Jay Test",
        access_token="tok", refresh_token="ref",
        expires_at=int(time.time()) + 3600,
    )
    resp = auth_client.get("/strava/settings/")
    assert b"Jay Test" in resp.content
