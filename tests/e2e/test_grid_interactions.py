"""
Playwright tests for grid.js interactive behaviours:
  - click-to-create (opens popover, popover has correct time)
  - cancel button closes without reopening a new popover
  - drag-to-create shows ghost then opens popover with end time set
  - block-edit save updates chip in place and closes the panel

These tests run against a real Django server with real JS, so they catch
regressions that unit tests (mock DOM) cannot.

Run both browsers:  pytest tests/e2e/ --browser chromium --browser firefox
"""
import re
import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.django_db(transaction=True)

# ── helpers ───────────────────────────────────────────────────────────────────

GRID_LEFT_OFFSET_PX = 56  # time-label width (w-14 = 3.5rem = 56px at 16px base)


def grid_point(page, x_frac: float, y_px: int) -> tuple[float, float]:
    """
    Return absolute page coordinates inside the grid.
    x_frac: 0.0–1.0 within the 7-column area (after the time label)
    y_px:   pixels from the top of the grid (0 = 06:00)
    """
    box = page.locator('#week-grid').bounding_box()
    col_area_width = box['width'] - GRID_LEFT_OFFSET_PX
    x = box['x'] + GRID_LEFT_OFFSET_PX + col_area_width * x_frac
    y = box['y'] + y_px
    return x, y


# ── tests ─────────────────────────────────────────────────────────────────────


def test_click_opens_create_popover(week_page):
    """Clicking an empty cell opens the create popover at that time slot."""
    page = week_page
    x, y = grid_point(page, 0.15, 120)  # ~08:00 in Monday column
    page.mouse.click(x, y)

    popover = page.locator('#create-popover')
    expect(popover).to_be_visible()
    # Input should be focused immediately
    expect(page.locator('#create-popover-input')).to_be_focused()
    # Time display should mention a time (e.g. "08:00")
    expect(popover).to_contain_text(re.compile(r'\d{2}:\d{2}'))


def test_cancel_button_closes_without_reopening(week_page):
    """Clicking the × cancel button closes the popover and doesn't reopen it."""
    page = week_page
    x, y = grid_point(page, 0.15, 120)
    page.mouse.click(x, y)

    expect(page.locator('#create-popover')).to_be_visible()

    # Click the cancel button
    page.locator('#create-popover-cancel').click()

    # Popover must be gone
    expect(page.locator('#create-popover')).to_have_count(0)

    # Wait long enough for any inadvertent re-open to manifest
    page.wait_for_timeout(400)
    expect(page.locator('#create-popover')).to_have_count(0)


def test_outside_click_closes_popover(week_page):
    """Clicking outside the popover (but not on the grid) closes it."""
    page = week_page
    x, y = grid_point(page, 0.15, 120)
    page.mouse.click(x, y)
    expect(page.locator('#create-popover')).to_be_visible()

    # Click somewhere outside the grid entirely
    page.mouse.click(5, 5)
    expect(page.locator('#create-popover')).to_have_count(0)


def test_drag_creates_ghost_and_popover(week_page):
    """Dragging on the grid shows a ghost block then opens the create popover."""
    page = week_page
    x, y_start = grid_point(page, 0.15, 120)   # ~08:00
    _, y_end   = grid_point(page, 0.15, 240)   # ~10:00

    page.mouse.move(x, y_start)
    page.mouse.down()

    # Move in steps so pointermove fires incrementally
    for step_y in range(int(y_start), int(y_end), 20):
        page.mouse.move(x, step_y)

    expect(page.locator('#create-ghost')).to_be_visible()

    page.mouse.up()

    # Ghost should disappear and popover should appear
    expect(page.locator('#create-ghost')).to_have_count(0)
    popover = page.locator('#create-popover')
    expect(popover).to_be_visible()

    # The popover should show a time range (e.g. "08:00–10:00")
    expect(popover).to_contain_text(re.compile(r'\d{2}:\d{2}–\d{2}:\d{2}'))


def test_create_block_via_popover(week_page, plan_week):
    """Filling and saving the create popover creates a visible block on the grid."""
    page = week_page
    x, y = grid_point(page, 0.15, 120)
    page.mouse.click(x, y)

    expect(page.locator('#create-popover')).to_be_visible()
    page.fill('#create-popover-input', 'Test E2E Block')
    page.locator('#create-popover-save').click()

    # Popover should close after save
    expect(page.locator('#create-popover')).to_have_count(0)

    # A block chip with the title should appear on the grid
    expect(page.locator('.block-chip', has_text='Test E2E Block')).to_be_visible()


def test_edit_panel_opens_on_block_click(week_page_with_block):
    """Clicking an existing block opens the edit panel with the block's data."""
    page, block = week_page_with_block

    page.locator(f'#block-{block.pk}').click()

    expect(page.locator('#edit-panel')).to_be_visible()
    expect(page.locator('#edit-panel [name=title]')).to_have_value('Morning run')


def test_edit_panel_save_updates_chip(week_page_with_block):
    """Saving the edit panel updates the block chip title without a full page reload."""
    page, block = week_page_with_block

    page.locator(f'#block-{block.pk}').click()
    expect(page.locator('#edit-panel')).to_be_visible()

    page.locator('#edit-panel [name=title]').fill('Updated by E2E')
    page.locator('#edit-panel [type=submit]').click()

    # Panel closes and chip shows new title — no page reload
    expect(page.locator('#edit-panel')).to_be_hidden()
    expect(page.locator(f'#block-{block.pk}')).to_contain_text('Updated by E2E')


def test_edit_panel_delete_removes_chip(week_page_with_block):
    """Deleting a block from the edit panel removes it from the grid."""
    page, block = week_page_with_block

    page.locator(f'#block-{block.pk}').click()
    expect(page.locator('#edit-panel')).to_be_visible()

    page.on('dialog', lambda d: d.accept())
    page.locator('#edit-panel button', has_text='Delete').click()

    expect(page.locator(f'#block-{block.pk}')).to_have_count(0)
    expect(page.locator('#edit-panel')).to_be_hidden()
