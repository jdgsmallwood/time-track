from datetime import date, time

import pytest
from django.db import IntegrityError

from timetrack.schedule.models import PlanBlock, PlanWeek, PlanWeekReflection, WeeklyGoal
from timetrack.schedule.services import (
    complete_review,
    copy_selected_goals_to_next_week,
    should_show_planning_prompt,
    should_show_review_prompt,
)


@pytest.fixture
def plan_week(db):
    return PlanWeek.objects.create(start_date=date(2024, 6, 17))


@pytest.mark.django_db
def test_weekly_goal_defaults_to_planned(plan_week):
    goal = WeeklyGoal.objects.create(week=plan_week, title="Ship review flow")
    assert goal.status == "planned"
    assert goal.priority == "medium"


@pytest.mark.django_db
def test_plan_week_has_one_reflection(plan_week):
    PlanWeekReflection.objects.create(week=plan_week)
    with pytest.raises(IntegrityError):
        PlanWeekReflection.objects.create(week=plan_week)


@pytest.mark.django_db
def test_carryover_preserves_goal_fields_and_source(plan_week):
    goal = WeeklyGoal.objects.create(
        week=plan_week,
        title="Long run",
        category="Running",
        priority="high",
        notes="Keep it easy",
    )

    copied = copy_selected_goals_to_next_week(plan_week, [goal.pk])

    assert len(copied) == 1
    carried = copied[0]
    assert carried.week.start_date == date(2024, 6, 24)
    assert carried.title == goal.title
    assert carried.category == goal.category
    assert carried.priority == goal.priority
    assert carried.notes == goal.notes
    assert carried.source_goal == goal


@pytest.mark.django_db
def test_unselected_unfinished_goals_do_not_copy(plan_week):
    selected = WeeklyGoal.objects.create(week=plan_week, title="Selected")
    unselected = WeeklyGoal.objects.create(week=plan_week, title="Unselected")

    copy_selected_goals_to_next_week(plan_week, [selected.pk])

    next_week = PlanWeek.objects.get(start_date=date(2024, 6, 24))
    assert next_week.goals.filter(source_goal=selected).exists()
    assert not next_week.goals.filter(source_goal=unselected).exists()


@pytest.mark.django_db
def test_done_goals_do_not_copy_even_when_selected(plan_week):
    done = WeeklyGoal.objects.create(week=plan_week, title="Done", status="done")

    copied = copy_selected_goals_to_next_week(plan_week, [done.pk])

    assert copied == []
    assert not PlanWeek.objects.filter(start_date=date(2024, 6, 24)).exists()


@pytest.mark.django_db
def test_planning_prompt_appears_when_incomplete(plan_week):
    assert should_show_planning_prompt(plan_week, today=date(2024, 6, 17))


@pytest.mark.django_db
def test_planning_prompt_hides_when_complete(plan_week):
    PlanWeekReflection.objects.create(week=plan_week, planning_completed_at="2024-06-17T10:00:00Z")
    assert not should_show_planning_prompt(plan_week, today=date(2024, 6, 17))


@pytest.mark.django_db
def test_review_prompt_does_not_appear_monday_through_thursday(plan_week):
    assert not should_show_review_prompt(plan_week, today=date(2024, 6, 17))
    assert not should_show_review_prompt(plan_week, today=date(2024, 6, 20))


@pytest.mark.django_db
def test_review_prompt_appears_friday_through_sunday(plan_week):
    assert should_show_review_prompt(plan_week, today=date(2024, 6, 21))
    assert should_show_review_prompt(plan_week, today=date(2024, 6, 23))


@pytest.mark.django_db
def test_review_prompt_appears_for_past_incomplete_week(plan_week):
    assert should_show_review_prompt(plan_week, today=date(2024, 6, 24))


@pytest.mark.django_db
def test_planning_modal_get_renders(auth_client, plan_week):
    response = auth_client.get(f"/schedule/plan-weeks/{plan_week.pk}/planning/")
    assert response.status_code == 200
    assert b"Plan week" in response.content


@pytest.mark.django_db
def test_planning_post_saves_intention_priorities_and_goals(auth_client, plan_week):
    response = auth_client.post(
        f"/schedule/plan-weeks/{plan_week.pk}/planning/",
        {
            "weekly_intention": "Make progress",
            "goal_title": ["Build modal", "Run intervals"],
            "goal_category": ["Work", "Running"],
            "goal_priority": ["high", "medium"],
            "goal_notes": ["Keep scope tight", "Track effort"],
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 204
    reflection = plan_week.reflection
    assert reflection.weekly_intention == "Make progress"
    assert reflection.planning_completed_at is not None
    assert list(plan_week.goals.values_list("title", flat=True)) == ["Build modal", "Run intervals"]


@pytest.mark.django_db
def test_review_modal_get_includes_goals_and_stats(auth_client, plan_week):
    WeeklyGoal.objects.create(week=plan_week, title="Finish feature")
    PlanBlock.objects.create(
        week=plan_week,
        date=date(2024, 6, 17),
        start_time=time(9, 0),
        end_time=time(10, 30),
        title="Deep work",
    )

    response = auth_client.get(f"/schedule/plan-weeks/{plan_week.pk}/review/")

    assert response.status_code == 200
    assert b"Finish feature" in response.content
    assert b"1.5h" in response.content


@pytest.mark.django_db
def test_review_post_updates_status_reflection_and_carryover(auth_client, plan_week):
    carry = WeeklyGoal.objects.create(week=plan_week, title="Carry", category="Work", priority="high")
    skip = WeeklyGoal.objects.create(week=plan_week, title="Skip")
    done = WeeklyGoal.objects.create(week=plan_week, title="Done")

    response = auth_client.post(
        f"/schedule/plan-weeks/{plan_week.pk}/review/",
        {
            f"goal_status_{carry.pk}": "planned",
            f"goal_status_{skip.pk}": "skipped",
            f"goal_status_{done.pk}": "done",
            "carryover_goals": [str(carry.pk), str(skip.pk)],
            "wins": "Good focus",
            "misses": "Too many meetings",
            "lessons": "Protect mornings",
            "next_week_notes": "Start earlier",
            "energy_score": "4",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 204
    carry.refresh_from_db()
    skip.refresh_from_db()
    done.refresh_from_db()
    assert carry.status == "planned"
    assert skip.status == "skipped"
    assert done.status == "done"
    assert plan_week.reflection.wins == "Good focus"
    assert plan_week.reflection.energy_score == 4
    assert plan_week.reflection.review_completed_at is not None

    next_week = PlanWeek.objects.get(start_date=date(2024, 6, 24))
    assert next_week.goals.filter(source_goal=carry).exists()
    assert next_week.goals.filter(source_goal=skip).exists()
    assert not next_week.goals.filter(source_goal=done).exists()


@pytest.mark.django_db
def test_complete_review_does_not_copy_unselected_goals(plan_week):
    selected = WeeklyGoal.objects.create(week=plan_week, title="Selected")
    unselected = WeeklyGoal.objects.create(week=plan_week, title="Unselected")

    complete_review(
        plan_week,
        {
            "wins": "",
            "misses": "",
            "lessons": "",
            "next_week_notes": "",
            "energy_score": None,
        },
        {selected.pk: "planned", unselected.pk: "planned"},
        [selected.pk],
    )

    next_week = PlanWeek.objects.get(start_date=date(2024, 6, 24))
    assert next_week.goals.filter(source_goal=selected).exists()
    assert not next_week.goals.filter(source_goal=unselected).exists()


@pytest.mark.django_db
def test_week_view_planning_done_badge_has_htmx_link(auth_client, plan_week):
    from django.utils import timezone

    PlanWeekReflection.objects.create(week=plan_week, planning_completed_at=timezone.now())
    response = auth_client.get(f"/schedule/weeks/{plan_week.start_date.isoformat()}/")
    content = response.content.decode()
    assert response.status_code == 200
    assert f"/schedule/plan-weeks/{plan_week.pk}/planning/" in content
    assert "Planning done" in content


@pytest.mark.django_db
def test_week_view_review_done_badge_has_htmx_link(auth_client, plan_week):
    from django.utils import timezone

    PlanWeekReflection.objects.create(week=plan_week, review_completed_at=timezone.now())
    response = auth_client.get(f"/schedule/weeks/{plan_week.start_date.isoformat()}/")
    content = response.content.decode()
    assert response.status_code == 200
    assert f"/schedule/plan-weeks/{plan_week.pk}/review/" in content
    assert "Review done" in content
