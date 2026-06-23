"""
Playwright E2E tests for the 'To Schedule' suggestions panel.

Covers:
  - WeeklyTask chips visible with correct title and progress counter
  - Tapping a chip opens a pre-filled create popover
  - Dragging a chip to the grid creates a block and persists after reload
  - Running plan session chips appear when a training plan is active
  - Dragging a running chip creates a block with a RunSession in the DB
"""
import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.django_db(transaction=True)

# ── coordinate helpers (same as test_block_interactions.py) ───────────────────

GRID_LEFT_OFFSET_PX = 56


def grid_box(page):
    return page.locator("#week-grid").bounding_box()


def col_center_x(page, col_idx=0):
    box = grid_box(page)
    col_w = (box["width"] - GRID_LEFT_OFFSET_PX) / 7
    return box["x"] + GRID_LEFT_OFFSET_PX + col_w * (col_idx + 0.5)


def drag(page, x1, y1, x2, y2, steps=25):
    page.mouse.move(x1, y1)
    page.mouse.down()
    for i in range(1, steps + 1):
        t = i / steps
        page.mouse.move(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
    page.mouse.up()


def grid_y_for_time(page, hour, minute=0):
    """Viewport Y for a given hour:minute within the grid (START_HOUR=6, SLOT_PX=2)."""
    box = grid_box(page)
    return box["y"] + ((hour - 6) * 60 + minute) * 2


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def weekly_task(transactional_db):
    from timetrack.schedule.models import WeeklyTask
    return WeeklyTask.objects.create(
        title="Physio Exercises",
        duration_minutes=30,
        recurrence_count=3,
        is_active=True,
    )


@pytest.fixture
def active_training_plan(transactional_db):
    from datetime import date
    from timetrack.plugins.running.models import (
        TrainingPlan, TrainingPlanWeek, TrainingPlanSession,
    )
    # Plan starts on the same Monday used by the test fixtures (2026-06-23)
    monday = date(2026, 6, 23)
    plan = TrainingPlan.objects.create(
        name="Test Plan", is_active=True, start_date=monday,
        pace_easy_sec=360, pace_long_sec=390,
    )
    pw = TrainingPlanWeek.objects.create(
        plan=plan, week_number=1, phase="base", target_km=40,
    )
    TrainingPlanSession.objects.create(
        plan_week=pw, run_type="base", target_km=10, day_of_week=0,
    )
    TrainingPlanSession.objects.create(
        plan_week=pw, run_type="long", target_km=18, day_of_week=5,
    )
    return plan


@pytest.fixture
def suggestion_page(authenticated_page, week_url, plan_week, weekly_task):
    """Week view with one WeeklyTask in the DB."""
    authenticated_page.goto(week_url)
    authenticated_page.wait_for_selector("#week-grid", state="visible")
    authenticated_page.wait_for_function("typeof GRID !== 'undefined'")
    return authenticated_page, weekly_task


@pytest.fixture
def suggestion_page_with_plan(authenticated_page, week_url, plan_week, active_training_plan):
    """Week view with an active running training plan."""
    authenticated_page.goto(week_url)
    authenticated_page.wait_for_selector("#week-grid", state="visible")
    authenticated_page.wait_for_function("typeof GRID !== 'undefined'")
    return authenticated_page, active_training_plan


# ── WeeklyTask chip appearance ─────────────────────────────────────────────────


def test_weekly_task_chip_visible(suggestion_page):
    """A WeeklyTask appears as a draggable chip in the suggestions panel."""
    page, task = suggestion_page
    chip = page.locator(f'.suggestion-chip[data-title="{task.title}"]')
    expect(chip).to_be_visible()
    expect(chip).to_contain_text(task.title)


def test_weekly_task_chip_shows_initial_progress(suggestion_page):
    """Chip shows '0/N' progress when no blocks have been scheduled yet."""
    page, task = suggestion_page
    chip = page.locator(f'.suggestion-chip[data-title="{task.title}"]')
    expect(chip).to_contain_text(f"0/{task.recurrence_count}")


def test_weekly_task_chip_has_duration(suggestion_page):
    """Chip displays the task's duration in minutes."""
    page, task = suggestion_page
    chip = page.locator(f'.suggestion-chip[data-title="{task.title}"]')
    expect(chip).to_contain_text(f"{task.duration_minutes}m")


# ── Tap → pre-filled popover ──────────────────────────────────────────────────


def test_tap_chip_opens_prefilled_popover(suggestion_page):
    """Tapping a chip opens the create popover with the task's title pre-filled."""
    page, task = suggestion_page
    page.locator(f'.suggestion-chip[data-title="{task.title}"]').click()
    expect(page.locator("#create-popover")).to_be_visible()
    assert page.locator("#create-popover-input").input_value() == task.title


def test_tap_chip_prefills_correct_duration(suggestion_page):
    """The popover time-range header reflects the task's duration."""
    page, task = suggestion_page
    page.locator(f'.suggestion-chip[data-title="{task.title}"]').click()
    expect(page.locator("#create-popover")).to_be_visible()
    header = page.locator("#create-popover div").first.inner_text()
    # 30-min task anchored at Mon 09:00 → header should show 09:00–09:30
    assert "09:00" in header and "09:30" in header, (
        f"Expected '09:00–09:30' in popover header, got: {header!r}"
    )


def test_tap_chip_with_category_prefills_category(transactional_db, authenticated_page, week_url):
    """When the task has a category, the popover's category select is pre-selected."""
    from timetrack.core.models import Category
    from timetrack.schedule.models import PlanWeek, WeeklyTask
    from datetime import date
    PlanWeek.objects.get_or_create(start_date=date(2026, 6, 23))
    cat = Category.objects.create(name="Health", color="#10b981", icon="")
    WeeklyTask.objects.create(
        title="Stretching", duration_minutes=15, recurrence_count=1,
        is_active=True, category=cat,
    )
    authenticated_page.goto(week_url)
    authenticated_page.wait_for_selector("#week-grid", state="visible")
    authenticated_page.wait_for_function(
        "typeof GRID !== 'undefined' && Array.isArray(CATEGORIES) && CATEGORIES.length > 0"
    )
    authenticated_page.locator('.suggestion-chip[data-title="Stretching"]').click()
    expect(authenticated_page.locator("#create-popover")).to_be_visible()
    # The category dropdown should have the matching category selected
    selected_val = authenticated_page.locator("#create-popover-category").input_value()
    assert str(cat.pk) == selected_val, (
        f"Expected category pk {cat.pk} pre-selected, got: {selected_val!r}"
    )


# ── Drag chip to grid ─────────────────────────────────────────────────────────


def test_drag_chip_to_grid_creates_block(suggestion_page):
    """Dragging a suggestion chip onto the grid creates a block with the correct title."""
    page, task = suggestion_page

    chip = page.locator(f'.suggestion-chip[data-title="{task.title}"]')
    cb = chip.bounding_box()
    from_x = cb["x"] + cb["width"] / 2
    from_y = cb["y"] + cb["height"] / 2

    to_x = col_center_x(page, 0)
    to_y = grid_y_for_time(page, 9, 0)

    drag(page, from_x, from_y, to_x, to_y)
    page.wait_for_timeout(500)

    expect(page.locator(".block-chip", has_text=task.title)).to_be_visible()


def test_drag_chip_block_persists_after_reload(suggestion_page):
    """Block created by dragging a chip onto the grid survives a page reload."""
    page, task = suggestion_page

    chip = page.locator(f'.suggestion-chip[data-title="{task.title}"]')
    cb = chip.bounding_box()
    from_x = cb["x"] + cb["width"] / 2
    from_y = cb["y"] + cb["height"] / 2

    to_x = col_center_x(page, 0)
    to_y = grid_y_for_time(page, 9, 0)

    with page.expect_response(
        lambda r: "/schedule/plan-weeks/" in r.url and r.request.method == "POST"
    ):
        drag(page, from_x, from_y, to_x, to_y)

    page.reload()
    page.wait_for_selector("#week-grid", state="visible")
    page.wait_for_function("typeof GRID !== 'undefined'")
    expect(page.locator(".block-chip", has_text=task.title)).to_be_visible()


def test_drag_chip_links_weekly_task(suggestion_page):
    """Block created from a suggestion chip has weekly_task FK set in the DB."""
    page, task = suggestion_page

    chip = page.locator(f'.suggestion-chip[data-title="{task.title}"]')
    cb = chip.bounding_box()
    from_x = cb["x"] + cb["width"] / 2
    from_y = cb["y"] + cb["height"] / 2

    with page.expect_response(
        lambda r: "/schedule/plan-weeks/" in r.url and r.request.method == "POST"
    ):
        drag(page, from_x, from_y, col_center_x(page, 0), grid_y_for_time(page, 9, 0))

    page.wait_for_timeout(300)

    from timetrack.schedule.models import PlanBlock
    block = PlanBlock.objects.filter(title=task.title).first()
    assert block is not None, "No PlanBlock was created"
    assert block.weekly_task_id == task.pk, (
        f"Expected weekly_task_id={task.pk}, got {block.weekly_task_id}"
    )


# ── Running plan session chips ────────────────────────────────────────────────


def test_running_plan_chips_visible(suggestion_page_with_plan):
    """Running plan sessions appear as chips with plugin-slug='running'."""
    page, plan = suggestion_page_with_plan
    chips = page.locator('.suggestion-chip[data-plugin-slug="running"]')
    expect(chips).to_have_count(2)


def test_running_chip_shows_km(suggestion_page_with_plan):
    """Running session chips display the target km in their text."""
    page, plan = suggestion_page_with_plan
    chip = page.locator('.suggestion-chip[data-plugin-slug="running"]').first
    expect(chip).to_contain_text("km")


def test_drag_running_chip_creates_block(suggestion_page_with_plan):
    """Dragging a running session chip to the grid creates a visible block."""
    page, plan = suggestion_page_with_plan

    chip = page.locator('.suggestion-chip[data-plugin-slug="running"]').first
    cb = chip.bounding_box()
    from_x = cb["x"] + cb["width"] / 2
    from_y = cb["y"] + cb["height"] / 2

    to_x = col_center_x(page, 0)
    to_y = grid_y_for_time(page, 9, 0)

    drag(page, from_x, from_y, to_x, to_y)
    page.wait_for_timeout(500)

    expect(page.locator(".block-chip")).to_have_count(1)


def test_drag_running_chip_creates_run_session(suggestion_page_with_plan):
    """A block created from a running plan chip has a RunSession record in the DB."""
    page, plan = suggestion_page_with_plan

    chip = page.locator('.suggestion-chip[data-plugin-slug="running"]').first
    cb = chip.bounding_box()
    from_x = cb["x"] + cb["width"] / 2
    from_y = cb["y"] + cb["height"] / 2

    with page.expect_response(
        lambda r: "/schedule/plan-weeks/" in r.url and r.request.method == "POST"
    ):
        drag(page, from_x, from_y, col_center_x(page, 0), grid_y_for_time(page, 9, 0))

    page.wait_for_timeout(300)

    from timetrack.plugins.running.models import RunSession
    from timetrack.schedule.models import PlanBlock
    block = PlanBlock.objects.filter(plugin_slug="running").first()
    assert block is not None, "No running PlanBlock was created"
    run_session = RunSession.objects.filter(plan_block=block).first()
    assert run_session is not None, "No RunSession was created"
    assert run_session.run_type == "base", (
        f"Expected run_type='base' (first session in plan), got '{run_session.run_type}'"
    )


def test_drag_running_chip_persists_after_reload(suggestion_page_with_plan):
    """Running block created from a plan chip survives a page reload."""
    page, plan = suggestion_page_with_plan

    chip = page.locator('.suggestion-chip[data-plugin-slug="running"]').first
    cb = chip.bounding_box()
    from_x = cb["x"] + cb["width"] / 2
    from_y = cb["y"] + cb["height"] / 2

    with page.expect_response(
        lambda r: "/schedule/plan-weeks/" in r.url and r.request.method == "POST"
    ):
        drag(page, from_x, from_y, col_center_x(page, 0), grid_y_for_time(page, 9, 0))

    page.reload()
    page.wait_for_selector("#week-grid", state="visible")
    page.wait_for_function("typeof GRID !== 'undefined'")

    # Block should still be visible and contain "km"
    chip_text = page.locator(".block-chip").first.inner_text()
    assert "km" in chip_text.lower(), f"Expected 'km' in persisted block text: {chip_text!r}"
