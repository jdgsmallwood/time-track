from datetime import date

import pytest
from django.utils import timezone

from timetrack.schedule.models import DailyCheckIn, DailyGoalProgress, PlanWeek, WeeklyGoal


@pytest.fixture
def plan_week(db):
    return PlanWeek.objects.create(start_date=date(2024, 6, 17))


@pytest.fixture
def goal(plan_week):
    return WeeklyGoal.objects.create(week=plan_week, title="Finish the feature", priority="high")


# ─── Model ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_daily_checkin_date_is_unique():
    DailyCheckIn.objects.create(date=date(2024, 6, 17))
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        DailyCheckIn.objects.create(date=date(2024, 6, 17))


@pytest.mark.django_db
def test_daily_goal_progress_unique_per_day_and_goal(plan_week, goal):
    ci = DailyCheckIn.objects.create(date=date(2024, 6, 17))
    DailyGoalProgress.objects.create(check_in=ci, goal=goal, plan="Do X")
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        DailyGoalProgress.objects.create(check_in=ci, goal=goal, plan="Do Y")


@pytest.mark.django_db
def test_daily_checkin_defaults_blank():
    ci = DailyCheckIn.objects.create(date=date(2024, 6, 18))
    assert ci.intention == ""
    assert ci.general_aims == ""
    assert ci.energy_score is None
    assert ci.completed_at is None
    assert ci.recap_wins == ""
    assert ci.recap_misses == ""
    assert ci.recap_energy_score is None
    assert ci.recap_completed_at is None


# ─── Check-in GET ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_checkin_get_renders(auth_client, plan_week):
    response = auth_client.get("/schedule/days/2024-06-17/check-in/")
    assert response.status_code == 200
    assert b"Daily check-in" in response.content
    assert b"Monday 17 June 2024" in response.content


@pytest.mark.django_db
def test_checkin_get_shows_weekly_goals(auth_client, plan_week, goal):
    response = auth_client.get("/schedule/days/2024-06-17/check-in/")
    assert b"Finish the feature" in response.content


@pytest.mark.django_db
def test_checkin_get_excludes_skipped_goals(auth_client, plan_week):
    WeeklyGoal.objects.create(week=plan_week, title="Skipped goal", status="skipped")
    response = auth_client.get("/schedule/days/2024-06-17/check-in/")
    assert b"Skipped goal" not in response.content


@pytest.mark.django_db
def test_checkin_get_prefills_existing_data(auth_client, plan_week):
    ci = DailyCheckIn.objects.create(
        date=date(2024, 6, 17),
        intention="Stay focused",
        general_aims="Finish PR",
        energy_score=4,
        completed_at=timezone.now(),
    )
    response = auth_client.get("/schedule/days/2024-06-17/check-in/")
    content = response.content.decode()
    assert "Stay focused" in content
    assert "Finish PR" in content


@pytest.mark.django_db
def test_checkin_get_prefills_goal_progress(auth_client, plan_week, goal):
    ci = DailyCheckIn.objects.create(date=date(2024, 6, 17), completed_at=timezone.now())
    DailyGoalProgress.objects.create(check_in=ci, goal=goal, plan="Work on the modal")
    response = auth_client.get("/schedule/days/2024-06-17/check-in/")
    assert b"Work on the modal" in response.content


# ─── Check-in POST ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_checkin_post_creates_record(auth_client, plan_week):
    response = auth_client.post(
        "/schedule/days/2024-06-17/check-in/",
        {"intention": "Deep work day", "general_aims": "Ship it", "energy_score": "4"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 204
    ci = DailyCheckIn.objects.get(date=date(2024, 6, 17))
    assert ci.intention == "Deep work day"
    assert ci.general_aims == "Ship it"
    assert ci.energy_score == 4
    assert ci.completed_at is not None


@pytest.mark.django_db
def test_checkin_post_saves_goal_progress(auth_client, plan_week, goal):
    auth_client.post(
        "/schedule/days/2024-06-17/check-in/",
        {
            "intention": "Focus",
            "general_aims": "",
            f"goal_progress_{goal.pk}": "Spend 2h on it",
        },
        HTTP_HX_REQUEST="true",
    )
    ci = DailyCheckIn.objects.get(date=date(2024, 6, 17))
    progress = DailyGoalProgress.objects.get(check_in=ci, goal=goal)
    assert progress.plan == "Spend 2h on it"


@pytest.mark.django_db
def test_checkin_post_updates_existing_record(auth_client, plan_week):
    DailyCheckIn.objects.create(date=date(2024, 6, 17), intention="Old intention")
    auth_client.post(
        "/schedule/days/2024-06-17/check-in/",
        {"intention": "New intention", "general_aims": ""},
        HTTP_HX_REQUEST="true",
    )
    ci = DailyCheckIn.objects.get(date=date(2024, 6, 17))
    assert ci.intention == "New intention"
    assert DailyCheckIn.objects.filter(date=date(2024, 6, 17)).count() == 1


@pytest.mark.django_db
def test_checkin_post_upserts_goal_progress(auth_client, plan_week, goal):
    ci = DailyCheckIn.objects.create(date=date(2024, 6, 17))
    DailyGoalProgress.objects.create(check_in=ci, goal=goal, plan="Old plan")
    auth_client.post(
        "/schedule/days/2024-06-17/check-in/",
        {"intention": "", "general_aims": "", f"goal_progress_{goal.pk}": "Updated plan"},
        HTTP_HX_REQUEST="true",
    )
    progress = DailyGoalProgress.objects.get(check_in=ci, goal=goal)
    assert progress.plan == "Updated plan"


# ─── Recap GET ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_recap_get_renders(auth_client, plan_week):
    response = auth_client.get("/schedule/days/2024-06-17/recap/")
    assert response.status_code == 200
    assert b"Daily recap" in response.content
    assert b"Monday 17 June 2024" in response.content


@pytest.mark.django_db
def test_recap_get_shows_weekly_goals(auth_client, plan_week, goal):
    response = auth_client.get("/schedule/days/2024-06-17/recap/")
    assert b"Finish the feature" in response.content


@pytest.mark.django_db
def test_recap_get_shows_morning_plan_as_context(auth_client, plan_week, goal):
    ci = DailyCheckIn.objects.create(date=date(2024, 6, 17), completed_at=timezone.now())
    DailyGoalProgress.objects.create(check_in=ci, goal=goal, plan="Do 2 hours of work")
    response = auth_client.get("/schedule/days/2024-06-17/recap/")
    assert b"Do 2 hours of work" in response.content


@pytest.mark.django_db
def test_recap_get_shows_morning_energy_hint(auth_client, plan_week):
    DailyCheckIn.objects.create(date=date(2024, 6, 17), energy_score=3)
    response = auth_client.get("/schedule/days/2024-06-17/recap/")
    assert b"morning estimate was 3" in response.content


@pytest.mark.django_db
def test_recap_get_prefills_existing_recap(auth_client, plan_week):
    DailyCheckIn.objects.create(
        date=date(2024, 6, 17),
        recap_wins="Got the PR merged",
        recap_misses="Skipped lunch",
        recap_energy_score=3,
        recap_completed_at=timezone.now(),
    )
    response = auth_client.get("/schedule/days/2024-06-17/recap/")
    content = response.content.decode()
    assert "Got the PR merged" in content
    assert "Skipped lunch" in content


# ─── Recap POST ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_recap_post_saves_fields(auth_client, plan_week):
    response = auth_client.post(
        "/schedule/days/2024-06-17/recap/",
        {"recap_wins": "PR merged", "recap_misses": "No gym", "recap_energy_score": "3"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 204
    ci = DailyCheckIn.objects.get(date=date(2024, 6, 17))
    assert ci.recap_wins == "PR merged"
    assert ci.recap_misses == "No gym"
    assert ci.recap_energy_score == 3
    assert ci.recap_completed_at is not None


@pytest.mark.django_db
def test_recap_post_saves_goal_actual(auth_client, plan_week, goal):
    auth_client.post(
        "/schedule/days/2024-06-17/recap/",
        {
            "recap_wins": "",
            "recap_misses": "",
            f"goal_actual_{goal.pk}": "Did 90 mins, good progress",
        },
        HTTP_HX_REQUEST="true",
    )
    ci = DailyCheckIn.objects.get(date=date(2024, 6, 17))
    progress = DailyGoalProgress.objects.get(check_in=ci, goal=goal)
    assert progress.actual == "Did 90 mins, good progress"


@pytest.mark.django_db
def test_recap_post_creates_checkin_if_no_morning_checkin(auth_client, plan_week):
    assert not DailyCheckIn.objects.filter(date=date(2024, 6, 17)).exists()
    auth_client.post(
        "/schedule/days/2024-06-17/recap/",
        {"recap_wins": "Surprise win", "recap_misses": ""},
        HTTP_HX_REQUEST="true",
    )
    assert DailyCheckIn.objects.filter(date=date(2024, 6, 17)).exists()


@pytest.mark.django_db
def test_recap_post_upserts_goal_actual(auth_client, plan_week, goal):
    ci = DailyCheckIn.objects.create(date=date(2024, 6, 17))
    DailyGoalProgress.objects.create(check_in=ci, goal=goal, plan="Morning plan", actual="Old actual")
    auth_client.post(
        "/schedule/days/2024-06-17/recap/",
        {"recap_wins": "", "recap_misses": "", f"goal_actual_{goal.pk}": "New actual"},
        HTTP_HX_REQUEST="true",
    )
    progress = DailyGoalProgress.objects.get(check_in=ci, goal=goal)
    assert progress.actual == "New actual"
    assert progress.plan == "Morning plan"


# ─── Week view integration ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_week_view_shows_checkin_buttons(auth_client, plan_week):
    response = auth_client.get(f"/schedule/weeks/{plan_week.start_date.isoformat()}/")
    content = response.content.decode()
    assert "/schedule/days/2024-06-17/check-in/" in content
    assert "/schedule/days/2024-06-17/recap/" in content


@pytest.mark.django_db
def test_week_view_shows_completed_checkin_indicator(auth_client, plan_week):
    DailyCheckIn.objects.create(date=date(2024, 6, 17), completed_at=timezone.now())
    response = auth_client.get(f"/schedule/weeks/{plan_week.start_date.isoformat()}/")
    content = response.content.decode()
    assert "completed_checkin_dates" not in content  # context not leaked to template
    assert "☀" in content


@pytest.mark.django_db
def test_week_view_shows_completed_recap_indicator(auth_client, plan_week):
    DailyCheckIn.objects.create(date=date(2024, 6, 17), recap_completed_at=timezone.now())
    response = auth_client.get(f"/schedule/weeks/{plan_week.start_date.isoformat()}/")
    assert "★" in response.content.decode()
