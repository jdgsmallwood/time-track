"""Tests for the running training plan feature."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from timetrack.plugins.running.models import (
    TrainingPlan,
    TrainingPlanSession,
    TrainingPlanWeek,
)
from timetrack.plugins.running.services import (
    estimate_session_minutes,
    estimate_week_minutes,
    get_current_plan_week,
    import_plan_from_csv,
    pace_sec_for_type,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def plan(db):
    p = TrainingPlan.objects.create(
        name="Test Plan",
        start_date=date(2024, 9, 2),
        pace_easy_sec=360,
        pace_tempo_sec=300,
        pace_interval_sec=270,
        pace_long_sec=390,
        pace_recovery_sec=420,
    )
    pw = TrainingPlanWeek.objects.create(plan=p, week_number=1, phase="base", target_km=Decimal("40.0"))
    TrainingPlanSession.objects.create(plan_week=pw, run_type="base", target_km=Decimal("10"), day_of_week=1)
    TrainingPlanSession.objects.create(plan_week=pw, run_type="tempo", target_km=Decimal("6"), day_of_week=3)
    TrainingPlanSession.objects.create(plan_week=pw, run_type="long", target_km=Decimal("14"), day_of_week=6)
    return p


# ─── Model: single-active enforcement ────────────────────────────────────────

@pytest.mark.django_db
def test_training_plan_single_active():
    p1 = TrainingPlan.objects.create(name="P1", start_date=date(2024, 1, 1), is_active=True)
    p2 = TrainingPlan.objects.create(name="P2", start_date=date(2024, 6, 1), is_active=True)
    p1.refresh_from_db()
    assert not p1.is_active
    assert p2.is_active


@pytest.mark.django_db
def test_training_plan_total_weeks(plan):
    assert plan.total_weeks == 1


# ─── Services: pace calc ─────────────────────────────────────────────────────

@pytest.mark.django_db
def test_pace_sec_for_type_easy(plan):
    assert pace_sec_for_type(plan, "base") == 360


@pytest.mark.django_db
def test_pace_sec_for_type_tempo(plan):
    assert pace_sec_for_type(plan, "tempo") == 300


@pytest.mark.django_db
def test_pace_sec_for_type_long(plan):
    assert pace_sec_for_type(plan, "long") == 390


@pytest.mark.django_db
def test_estimate_session_minutes_easy(plan):
    session = TrainingPlanSession(plan_week=None, run_type="base", target_km=Decimal("10"))
    assert estimate_session_minutes(session, plan) == int(10 * 360 / 60)  # 60min


@pytest.mark.django_db
def test_estimate_session_minutes_tempo(plan):
    session = TrainingPlanSession(plan_week=None, run_type="tempo", target_km=Decimal("6"))
    assert estimate_session_minutes(session, plan) == int(6 * 300 / 60)  # 30min


@pytest.mark.django_db
def test_estimate_week_minutes(plan):
    pw = plan.weeks.first()
    # base 10km = 60min, tempo 6km = 30min, long 14km = 14*390/60 = 91min
    expected = 60 + 30 + int(14 * 390 / 60)
    assert estimate_week_minutes(pw, plan) == expected


# ─── Services: get_current_plan_week ─────────────────────────────────────────

@pytest.mark.django_db
def test_get_current_plan_week_day_0(plan, freezer=None):
    """On the plan start date (week 1 day 0), returns week 1."""
    import datetime
    from unittest.mock import patch
    with patch("timetrack.plugins.running.services.date") as mock_date:
        mock_date.today.return_value = date(2024, 9, 2)
        result = get_current_plan_week(plan)
    assert result is not None
    assert result.week_number == 1


@pytest.mark.django_db
def test_get_current_plan_week_day_7_returns_none_if_no_week_2(plan):
    """Day 7 (week 2) but only week 1 exists → returns None."""
    from unittest.mock import patch
    with patch("timetrack.plugins.running.services.date") as mock_date:
        mock_date.today.return_value = date(2024, 9, 9)  # start + 7 days = week 2
        result = get_current_plan_week(plan)
    assert result is None


@pytest.mark.django_db
def test_get_current_plan_week_before_start(plan):
    from unittest.mock import patch
    with patch("timetrack.plugins.running.services.date") as mock_date:
        mock_date.today.return_value = date(2024, 9, 1)  # one day before start
        result = get_current_plan_week(plan)
    assert result is None


@pytest.mark.django_db
def test_get_current_plan_week_mid_week(plan):
    from unittest.mock import patch
    with patch("timetrack.plugins.running.services.date") as mock_date:
        mock_date.today.return_value = date(2024, 9, 5)  # day 3 of week 1
        result = get_current_plan_week(plan)
    assert result is not None
    assert result.week_number == 1


# ─── Services: CSV import ─────────────────────────────────────────────────────

SAMPLE_CSV = """name,My 12-week plan
start_date,2024-09-02
description,Test plan
pace_easy,6:00
pace_tempo,5:00
pace_interval,4:30
pace_long,6:30
pace_recovery,7:00

week,phase,target_km,day,type,km,notes
1,base,40,1,easy,10,Morning run
1,base,40,3,tempo,6,Track session
1,base,40,6,long,14,Long easy run
2,build,44,1,easy,11,
2,build,44,3,tempo,7,
2,build,44,6,long,16,"""


@pytest.mark.django_db
def test_import_creates_plan():
    plan = import_plan_from_csv(SAMPLE_CSV)
    assert plan.name == "My 12-week plan"
    assert plan.description == "Test plan"
    assert plan.start_date == date(2024, 9, 2)
    assert plan.pace_easy_sec == 360
    assert plan.pace_tempo_sec == 300
    assert plan.pace_interval_sec == 270
    assert plan.pace_long_sec == 390
    assert plan.pace_recovery_sec == 420


@pytest.mark.django_db
def test_import_creates_weeks():
    plan = import_plan_from_csv(SAMPLE_CSV)
    assert plan.weeks.count() == 2
    w1 = plan.weeks.get(week_number=1)
    assert w1.phase == "base"
    assert w1.target_km == Decimal("40.0")
    w2 = plan.weeks.get(week_number=2)
    assert w2.phase == "build"
    assert w2.target_km == Decimal("44.0")


@pytest.mark.django_db
def test_import_creates_sessions():
    plan = import_plan_from_csv(SAMPLE_CSV)
    w1 = plan.weeks.get(week_number=1)
    assert w1.sessions.count() == 3
    session_types = list(w1.sessions.values_list("run_type", flat=True))
    assert "base" in session_types
    assert "tempo" in session_types
    assert "long" in session_types


@pytest.mark.django_db
def test_import_duplicate_week_target_km_uses_first():
    """Second row for the same week should not create a duplicate week."""
    plan = import_plan_from_csv(SAMPLE_CSV)
    assert plan.weeks.filter(week_number=1).count() == 1


@pytest.mark.django_db
def test_import_pace_string_parses():
    plan = import_plan_from_csv(SAMPLE_CSV)
    assert plan.pace_easy_sec == 6 * 60  # "6:00" → 360s


@pytest.mark.django_db
def test_import_bad_date_raises():
    bad_csv = SAMPLE_CSV.replace("start_date,2024-09-02", "start_date,not-a-date")
    with pytest.raises(ValueError, match="start_date"):
        import_plan_from_csv(bad_csv)


@pytest.mark.django_db
def test_import_missing_name_raises():
    bad_csv = SAMPLE_CSV.replace("name,My 12-week plan\n", "")
    with pytest.raises(ValueError, match="name"):
        import_plan_from_csv(bad_csv)


@pytest.mark.django_db
def test_import_unknown_run_type_raises():
    bad_csv = SAMPLE_CSV.replace("easy,10,Morning run", "flying,10,Wrong type")
    with pytest.raises(ValueError, match="run type"):
        import_plan_from_csv(bad_csv)


@pytest.mark.django_db
def test_import_easy_alias_maps_to_base():
    """'easy' should be accepted as an alias for 'base'."""
    plan = import_plan_from_csv(SAMPLE_CSV)
    w1 = plan.weeks.get(week_number=1)
    base_sessions = list(w1.sessions.filter(run_type="base"))
    assert len(base_sessions) >= 1


# ─── Views ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_training_plan_list_view(auth_client, db):
    resp = auth_client.get("/running/training-plans/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_training_plan_import_view(auth_client):
    resp = auth_client.post(
        "/running/training-plans/import/",
        {"csv_text": SAMPLE_CSV},
        follow=True,
    )
    assert resp.status_code == 200
    assert TrainingPlan.objects.filter(name="My 12-week plan").exists()


@pytest.mark.django_db
def test_training_plan_activate_view(auth_client, db):
    plan = TrainingPlan.objects.create(name="P", start_date=date(2024, 1, 1))
    resp = auth_client.post(f"/running/training-plans/{plan.pk}/activate/", follow=True)
    assert resp.status_code == 200
    plan.refresh_from_db()
    assert plan.is_active


@pytest.mark.django_db
def test_training_plan_detail_view(auth_client, plan):
    resp = auth_client.get(f"/running/training-plans/{plan.pk}/")
    assert resp.status_code == 200
    assert b"Test Plan" in resp.content


@pytest.mark.django_db
def test_week_view_shows_training_plan_banner(auth_client):
    from timetrack.schedule.models import PlanWeek
    from timetrack.schedule.services import week_monday

    today = date.today()
    plan = TrainingPlan.objects.create(
        name="Active Plan", start_date=week_monday(today), is_active=True
    )
    TrainingPlanWeek.objects.create(plan=plan, week_number=1, phase="base", target_km=Decimal("40"))
    PlanWeek.objects.create(start_date=week_monday(today))

    resp = auth_client.get(f"/schedule/weeks/{week_monday(today).isoformat()}/")
    assert resp.status_code == 200
    assert resp.context["current_plan_week"] is not None
