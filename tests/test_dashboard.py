"""Tests for the expanded dashboard view."""
from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from timetrack.schedule.models import PlanBlock, PlanWeek
from timetrack.schedule.services import week_monday


@pytest.mark.django_db
def test_dashboard_shows_today_blocks(auth_client):
    today = date.today()
    monday = week_monday(today)
    week = PlanWeek.objects.create(start_date=monday)
    block = PlanBlock.objects.create(
        week=week, date=today, start_time=time(9, 0), end_time=time(10, 0), title="Standup"
    )
    resp = auth_client.get("/")
    assert resp.status_code == 200
    assert block in resp.context["today_blocks"]


@pytest.mark.django_db
def test_dashboard_empty_today(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 200
    assert resp.context["today_blocks"] == []


@pytest.mark.django_db
def test_dashboard_this_week_context(auth_client):
    monday = week_monday(date.today())
    week = PlanWeek.objects.create(start_date=monday)
    resp = auth_client.get("/")
    assert resp.context["this_week"] == week


@pytest.mark.django_db
def test_dashboard_no_this_week(auth_client):
    resp = auth_client.get("/")
    assert resp.context["this_week"] is None


@pytest.mark.django_db
def test_dashboard_recent_weeks_up_to_8(auth_client):
    for i in range(10):
        PlanWeek.objects.create(start_date=date(2024, 1, 1) + timedelta(weeks=i))
    resp = auth_client.get("/")
    assert len(resp.context["recent_weeks"]) == 8


@pytest.mark.django_db
def test_dashboard_recent_weeks_have_stats_keys(auth_client):
    week = PlanWeek.objects.create(start_date=date(2024, 6, 17))
    resp = auth_client.get("/")
    assert len(resp.context["recent_weeks"]) == 1
    row = resp.context["recent_weeks"][0]
    assert "km_planned" in row
    assert "practice_mins" in row
    assert "total_hours" in row


@pytest.mark.django_db
def test_dashboard_training_plan_context(auth_client):
    from timetrack.plugins.running.models import TrainingPlan, TrainingPlanWeek

    plan = TrainingPlan.objects.create(
        name="Test Plan", is_active=True, start_date=week_monday(date.today())
    )
    plan_week = TrainingPlanWeek.objects.create(
        plan=plan, week_number=1, phase="base", target_km=Decimal("40.0")
    )
    resp = auth_client.get("/")
    assert resp.context["active_plan"] == plan
    assert resp.context["current_plan_week"] == plan_week


@pytest.mark.django_db
def test_dashboard_no_active_plan(auth_client):
    resp = auth_client.get("/")
    assert resp.context["active_plan"] is None
    assert resp.context["current_plan_week"] is None
