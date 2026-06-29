"""
Playwright E2E tests for weekly planning and review modals.

Covers:
  - opening the planning modal from the week view and saving goals
  - opening the review modal, updating goal statuses, and carrying goals forward
"""
from datetime import date

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.django_db(transaction=True)


def test_planning_modal_saves_reflection_and_goals(authenticated_page, live_server):
    from timetrack.schedule.models import PlanWeek

    week = PlanWeek.objects.create(start_date=date(2026, 6, 30))
    page = authenticated_page
    page.goto(f"{live_server.url}/schedule/weeks/{week.start_date.isoformat()}/")
    page.wait_for_selector("#week-grid", state="visible")

    page.get_by_role("button", name="Plan week").click()
    expect(page.get_by_role("heading", name="Plan week")).to_be_visible()

    page.locator('[name="weekly_intention"]').fill("Keep the week focused")

    goal_titles = page.locator('[name="goal_title"]')
    goal_categories = page.locator('[name="goal_category"]')
    goal_priorities = page.locator('[name="goal_priority"]')
    goal_notes = page.locator('[name="goal_notes"]')

    goal_titles.nth(0).fill("Finish modal flow")
    goal_categories.nth(0).fill("Work")
    goal_priorities.nth(0).select_option("high")
    goal_notes.nth(0).fill("Keep the scope tight")

    goal_titles.nth(1).fill("Run intervals")
    goal_categories.nth(1).fill("Running")
    goal_priorities.nth(1).select_option("medium")

    page.get_by_role("button", name="Save planning").click()
    page.wait_for_load_state("networkidle")

    week.refresh_from_db()
    assert week.reflection.weekly_intention == "Keep the week focused"
    assert week.reflection.planning_completed_at is not None
    assert list(week.goals.values_list("title", "category", "priority")) == [
        ("Finish modal flow", "Work", "high"),
        ("Run intervals", "Running", "medium"),
    ]

    expect(page.get_by_role("button", name="Plan week")).to_have_count(0)
    expect(page.locator("body")).to_contain_text("Planning done")


def test_review_modal_updates_goals_and_carries_selected_forward(authenticated_page, live_server):
    from timetrack.schedule.models import PlanWeek, PlanWeekReflection, WeeklyGoal

    week = PlanWeek.objects.create(start_date=date(2026, 6, 15))
    PlanWeekReflection.objects.create(
        week=week,
        weekly_intention="Finish important work",
        top_priorities="Build\nRun",
    )
    carry_goal = WeeklyGoal.objects.create(
        week=week,
        title="Carry this goal",
        category="Work",
        priority="high",
        notes="Still useful",
    )
    skipped_goal = WeeklyGoal.objects.create(week=week, title="Do not carry", priority="medium")
    done_goal = WeeklyGoal.objects.create(week=week, title="Completed goal", priority="low")

    page = authenticated_page
    page.goto(f"{live_server.url}/schedule/weeks/{week.start_date.isoformat()}/")
    page.wait_for_selector("#week-grid", state="visible")

    page.get_by_role("button", name="Review week").click()
    expect(page.get_by_role("heading", name="Review week")).to_be_visible()
    expect(page.locator("body")).to_contain_text("Carry this goal")

    page.locator(f'[name="goal_status_{carry_goal.pk}"]').select_option("planned")
    page.locator(f'[name="goal_status_{skipped_goal.pk}"]').select_option("skipped")
    page.locator(f'[name="goal_status_{done_goal.pk}"]').select_option("done")
    page.locator(f'input[name="carryover_goals"][value="{carry_goal.pk}"]').check()

    page.locator('[name="wins"]').fill("Protected focus")
    page.locator('[name="misses"]').fill("Too many meetings")
    page.locator('[name="lessons"]').fill("Start earlier")
    page.locator('[name="next_week_notes"]').fill("Carry the right work")
    page.locator('[name="energy_score"]').fill("4")

    page.get_by_role("button", name="Save review").click()
    page.wait_for_load_state("networkidle")

    week.refresh_from_db()
    carry_goal.refresh_from_db()
    skipped_goal.refresh_from_db()
    done_goal.refresh_from_db()

    assert week.reflection.wins == "Protected focus"
    assert week.reflection.energy_score == 4
    assert week.reflection.review_completed_at is not None
    assert carry_goal.status == "planned"
    assert skipped_goal.status == "skipped"
    assert done_goal.status == "done"

    next_week = PlanWeek.objects.get(start_date=date(2026, 6, 22))
    carried = next_week.goals.get(source_goal=carry_goal)
    assert carried.title == "Carry this goal"
    assert carried.category == "Work"
    assert carried.priority == "high"
    assert carried.notes == "Still useful"
    assert not next_week.goals.filter(source_goal=skipped_goal).exists()
    assert not next_week.goals.filter(source_goal=done_goal).exists()

    expect(page.get_by_role("button", name="Review week")).to_have_count(0)
    expect(page.locator("body")).to_contain_text("Review done")


def test_planning_done_badge_reopens_prefilled_modal(authenticated_page, live_server):
    from django.utils import timezone
    from timetrack.schedule.models import PlanWeek, PlanWeekReflection, WeeklyGoal

    week = PlanWeek.objects.create(start_date=date(2026, 6, 30))
    PlanWeekReflection.objects.create(
        week=week,
        weekly_intention="Focus on shipping",
        planning_completed_at=timezone.now(),
    )
    WeeklyGoal.objects.create(week=week, title="Ship the feature", priority="high")

    page = authenticated_page
    page.goto(f"{live_server.url}/schedule/weeks/{week.start_date.isoformat()}/")
    page.wait_for_selector("#week-grid", state="visible")

    expect(page.get_by_role("button", name="Plan week")).to_have_count(0)
    page.get_by_role("button", name="Planning done").click()
    expect(page.get_by_role("heading", name="Plan week")).to_be_visible()
    expect(page.locator('[name="weekly_intention"]')).to_have_value("Focus on shipping")
    expect(page.locator('[name="goal_title"]').first).to_have_value("Ship the feature")
