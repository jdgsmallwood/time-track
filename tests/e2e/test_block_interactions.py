"""
Playwright tests for block drag, resize, keyboard shortcuts, category
selection, and persistence (reload checks).

These complement test_grid_interactions.py, which covers the basic
popover open/close/create flow.

Run both browsers:  pytest tests/e2e/ --browser chromium --browser firefox
"""
import re
import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.django_db(transaction=True)

# ── coordinate helpers ────────────────────────────────────────────────────────

GRID_LEFT_OFFSET_PX = 56  # width of the time-label column (w-14 at 16px base)


def grid_box(page):
    return page.locator('#week-grid').bounding_box()


def col_center_x(page, col_idx: int) -> float:
    """Absolute viewport X for the centre of a day column (0=Mon … 6=Sun)."""
    box = grid_box(page)
    col_width = (box['width'] - GRID_LEFT_OFFSET_PX) / 7
    return box['x'] + GRID_LEFT_OFFSET_PX + col_width * (col_idx + 0.5)


def col_width(page) -> float:
    box = grid_box(page)
    return (box['width'] - GRID_LEFT_OFFSET_PX) / 7


def drag(page, x1, y1, x2, y2, steps: int = 20):
    """Smooth pointer drag from (x1,y1) to (x2,y2) in `steps` increments."""
    page.mouse.move(x1, y1)
    page.mouse.down()
    for i in range(1, steps + 1):
        t = i / steps
        page.mouse.move(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
    page.mouse.up()


# ── popover keyboard shortcuts ────────────────────────────────────────────────

def test_popover_enter_key_submits(week_page):
    """Pressing Enter in the title field saves the block without clicking Add."""
    page = week_page
    # Click an empty cell to open the popover
    box = grid_box(page)
    x = box['x'] + GRID_LEFT_OFFSET_PX + col_width(page) * 0.5
    y = box['y'] + 120
    page.mouse.click(x, y)
    expect(page.locator('#create-popover')).to_be_visible()

    # Inject a marker that disappears on page reload
    page.evaluate("window._alive = true")
    page.fill('#create-popover-input', 'Enter Key Block')
    page.locator('#create-popover-input').press('Enter')

    expect(page.locator('.block-chip', has_text='Enter Key Block')).to_be_visible()
    # Marker must still be set — no full-page reload occurred
    assert page.evaluate("window._alive === true"), "Page was reloaded unexpectedly"


def test_popover_escape_key_closes(week_page):
    """Pressing Escape in the title field closes the popover without saving."""
    page = week_page
    box = grid_box(page)
    x = box['x'] + GRID_LEFT_OFFSET_PX + col_width(page) * 0.5
    y = box['y'] + 120
    page.mouse.click(x, y)
    expect(page.locator('#create-popover')).to_be_visible()

    page.locator('#create-popover-input').press('Escape')
    expect(page.locator('#create-popover')).to_have_count(0)
    # No block was created
    expect(page.locator('.block-chip')).to_have_count(0)


def test_popover_empty_title_shows_validation(week_page):
    """Clicking Add block with an empty title keeps the popover open and marks the input."""
    page = week_page
    box = grid_box(page)
    x = box['x'] + GRID_LEFT_OFFSET_PX + col_width(page) * 0.5
    y = box['y'] + 120
    page.mouse.click(x, y)
    expect(page.locator('#create-popover')).to_be_visible()

    # Click save without typing a title
    page.locator('#create-popover-save').click()

    # Popover must remain open
    expect(page.locator('#create-popover')).to_be_visible()
    # Input border-color should be set to the error colour #f87171
    border = page.locator('#create-popover-input').evaluate("el => el.style.borderColor")
    assert border, "Expected an inline border-color on the input"
    assert '248' in border or 'f87171' in border.lower(), (
        f"Expected red (#f87171 / rgb(248,113,113)) border, got: {border}"
    )


# ── block create without page reload ─────────────────────────────────────────

def test_block_created_without_page_reload(week_page):
    """Creating a block via the popover adds it to the grid without a full reload."""
    page = week_page
    page.evaluate("window._noReloadMarker = true")

    box = grid_box(page)
    x = box['x'] + GRID_LEFT_OFFSET_PX + col_width(page) * 0.5
    y = box['y'] + 120
    page.mouse.click(x, y)
    expect(page.locator('#create-popover')).to_be_visible()
    page.fill('#create-popover-input', 'No Reload Block')
    page.locator('#create-popover-save').click()

    expect(page.locator('.block-chip', has_text='No Reload Block')).to_be_visible()
    assert page.evaluate("window._noReloadMarker === true"), (
        "window._noReloadMarker was cleared — a page reload happened"
    )


# ── drag-to-create keyboard cancel ───────────────────────────────────────────

def test_escape_during_drag_create_removes_ghost(week_page):
    """Pressing Escape mid drag-to-create removes the ghost block."""
    page = week_page
    box = grid_box(page)
    x = box['x'] + GRID_LEFT_OFFSET_PX + col_width(page) * 0.5
    y_start = box['y'] + 120
    y_end   = box['y'] + 240

    page.mouse.move(x, y_start)
    page.mouse.down()
    for step in range(int(y_start), int(y_end), 20):
        page.mouse.move(x, step)

    expect(page.locator('#create-ghost')).to_be_visible()

    page.keyboard.press('Escape')
    expect(page.locator('#create-ghost')).to_have_count(0)

    # Clean up
    page.mouse.up()
    page.wait_for_timeout(100)
    expect(page.locator('#create-popover')).to_have_count(0)


# ── block drag ────────────────────────────────────────────────────────────────

def test_block_drag_changes_day_column(week_page_with_block):
    """Dragging a block to a different day visually moves it to that column."""
    page, block = week_page_with_block

    bb = page.locator(f'#block-{block.pk}').bounding_box()
    from_x = bb['x'] + bb['width'] / 2
    # Use upper third of block to stay clear of the resize handle zones
    from_y = bb['y'] + bb['height'] / 4

    # Drag Monday → Wednesday (2 columns right)
    to_x = col_center_x(page, 2)

    drag(page, from_x, from_y, to_x, from_y)
    page.wait_for_timeout(300)

    new_bb = page.locator(f'#block-{block.pk}').bounding_box()
    # Block must have moved at least one full column width to the right
    assert new_bb['x'] > bb['x'] + col_width(page) * 0.9, (
        f"Block did not move far enough: was x={bb['x']:.0f}, now x={new_bb['x']:.0f}"
    )


def test_block_drag_persists_after_reload(week_page_with_block):
    """After dragging a block to a new day, a page reload shows it in the new column."""
    page, block = week_page_with_block

    bb = page.locator(f'#block-{block.pk}').bounding_box()
    from_x = bb['x'] + bb['width'] / 2
    from_y = bb['y'] + bb['height'] / 4
    to_x   = col_center_x(page, 2)

    with page.expect_response(
        lambda r: f'/schedule/plan-blocks/{block.pk}/' in r.url and r.request.method == 'PATCH'
    ):
        drag(page, from_x, from_y, to_x, from_y)

    page.reload()
    page.wait_for_selector(f'#block-{block.pk}', state='visible')
    page.wait_for_function("typeof GRID !== 'undefined'")

    new_bb = page.locator(f'#block-{block.pk}').bounding_box()
    assert new_bb['x'] > bb['x'] + col_width(page) * 0.9, (
        "Block did not persist in new column after reload"
    )


# ── block resize — bottom edge ────────────────────────────────────────────────

def test_resize_bottom_extends_end_time_label(week_page_with_block):
    """Dragging the bottom edge down extends the end time shown on the chip."""
    page, block = week_page_with_block

    bb = page.locator(f'#block-{block.pk}').bounding_box()
    edge_x = bb['x'] + bb['width'] / 2
    edge_y = bb['y'] + bb['height'] - 4  # just inside the bottom resize zone

    # Drag down 60 px = 30 minutes (SLOT_PX=2, so 60px / 2 = 30 min)
    drag(page, edge_x, edge_y, edge_x, edge_y + 60)
    page.wait_for_timeout(300)

    # Chip must show a later end time than the original 09:00
    chip = page.locator(f'#block-{block.pk}')
    text = chip.inner_text()
    assert re.search(r'09:[1-9]\d|10:|11:|12:|13:|14:|15:|16:|17:|18:|19:|20:|21:|22:', text), (
        f"Expected end time later than 09:00 in chip text: {text!r}"
    )


def test_resize_bottom_persists_after_reload(week_page_with_block):
    """After bottom-edge resize the new end time survives a page reload."""
    page, block = week_page_with_block

    bb = page.locator(f'#block-{block.pk}').bounding_box()
    edge_x = bb['x'] + bb['width'] / 2
    edge_y = bb['y'] + bb['height'] - 4

    with page.expect_response(
        lambda r: f'/schedule/plan-blocks/{block.pk}/' in r.url and r.request.method == 'PATCH'
    ):
        drag(page, edge_x, edge_y, edge_x, edge_y + 60)

    page.reload()
    page.wait_for_selector(f'#block-{block.pk}', state='visible')

    text = page.locator(f'#block-{block.pk}').inner_text()
    assert re.search(r'09:[1-9]\d|10:|11:|12:|13:|14:|15:|16:|17:|18:|19:|20:|21:|22:', text), (
        f"Expected later end time after reload: {text!r}"
    )


# ── block resize — top edge ───────────────────────────────────────────────────

def test_resize_top_moves_start_time_label(week_page_with_block):
    """Dragging the top edge up shifts the start time shown on the chip."""
    page, block = week_page_with_block

    bb = page.locator(f'#block-{block.pk}').bounding_box()
    edge_x = bb['x'] + bb['width'] / 2
    edge_y = bb['y'] + 4  # just inside the top resize zone

    # Drag up 30 px = 15 minutes earlier (30px / 2 px/min = 15 min)
    drag(page, edge_x, edge_y, edge_x, edge_y - 30)
    page.wait_for_timeout(300)

    # Chip must show a start time earlier than the original 08:00
    chip = page.locator(f'#block-{block.pk}')
    text = chip.inner_text()
    assert re.search(r'0[67]:', text), (
        f"Expected start time earlier than 08:00 in chip text: {text!r}"
    )


def test_resize_top_persists_after_reload(week_page_with_block):
    """After top-edge resize the new start time survives a page reload."""
    page, block = week_page_with_block

    bb = page.locator(f'#block-{block.pk}').bounding_box()
    edge_x = bb['x'] + bb['width'] / 2
    edge_y = bb['y'] + 4

    with page.expect_response(
        lambda r: f'/schedule/plan-blocks/{block.pk}/' in r.url and r.request.method == 'PATCH'
    ):
        drag(page, edge_x, edge_y, edge_x, edge_y - 30)

    page.reload()
    page.wait_for_selector(f'#block-{block.pk}', state='visible')

    text = page.locator(f'#block-{block.pk}').inner_text()
    assert re.search(r'0[67]:', text), (
        f"Expected earlier start time after reload: {text!r}"
    )


# ── category in create popover ────────────────────────────────────────────────

def test_category_dropdown_present_when_categories_exist(week_page_with_category):
    """The create popover shows a category <select> when categories exist in the DB."""
    page, category = week_page_with_category
    box = grid_box(page)
    x = box['x'] + GRID_LEFT_OFFSET_PX + col_width(page) * 0.5
    y = box['y'] + 120
    page.mouse.click(x, y)

    expect(page.locator('#create-popover')).to_be_visible()
    expect(page.locator('#create-popover-category')).to_be_visible()
    expect(page.locator('#create-popover-category')).to_contain_text(category.name)


def test_create_block_with_category_sets_chip_colour(week_page_with_category):
    """Selecting a category in the popover creates a block with that category's colour."""
    page, category = week_page_with_category
    box = grid_box(page)
    x = box['x'] + GRID_LEFT_OFFSET_PX + col_width(page) * 0.5
    y = box['y'] + 120
    page.mouse.click(x, y)

    expect(page.locator('#create-popover')).to_be_visible()
    page.fill('#create-popover-input', 'Categorised Block')
    page.select_option('#create-popover-category', str(category.pk))
    page.locator('#create-popover-save').click()

    chip = page.locator('.block-chip', has_text='Categorised Block')
    expect(chip).to_be_visible()

    # The chip border-left colour should match the category colour (#e5534b)
    border = chip.evaluate("el => el.style.borderLeftColor")
    assert border, "Expected a border-left-color set on the chip"
    # rgb(229, 83, 75) is #e5534b — check enough digits to be unambiguous
    assert '229' in border or 'e5534b' in border.lower(), (
        f"Expected category colour in border-left-color, got: {border!r}"
    )
