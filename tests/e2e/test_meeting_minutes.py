"""
Playwright E2E tests for the meeting plugin minutes modal.

Covers:
  - the 📝 button on a meeting chip opening the modal and saving minutes
  - reopening the modal with previously saved minutes prefilled
  - non-meeting chips having no 📝 button and still opening the edit panel
"""
from datetime import time

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def meeting_page(authenticated_page, week_url, plan_week):
    """Week page with a single meeting block already on the grid."""
    from timetrack.schedule.models import PlanBlock

    block = PlanBlock.objects.create(
        week=plan_week,
        title="Team standup",
        date=plan_week.start_date,
        start_time=time(10, 0),
        end_time=time(11, 0),
        plugin_slug="meeting",
    )
    authenticated_page.goto(week_url)
    authenticated_page.wait_for_selector(f"#block-{block.pk}", state="visible")
    authenticated_page.wait_for_function(
        "typeof GRID !== 'undefined' && typeof GRID.updateBlock === 'function'"
    )
    return authenticated_page, block


def test_chip_minutes_button_opens_modal_and_saves(meeting_page):
    from timetrack.plugins.meeting.models import MeetingNotes

    page, block = meeting_page

    page.click(f"#block-{block.pk} .minutes-btn")
    expect(page.get_by_role("heading", name="Minutes — Team standup")).to_be_visible()

    page.locator('[name="meeting-minutes"]').fill("Agreed to ship on Friday")
    page.get_by_role("button", name="Save minutes").click()
    page.wait_for_load_state("networkidle")

    assert MeetingNotes.objects.get(plan_block=block).minutes == "Agreed to ship on Friday"
    # HX-Refresh reloaded the page, so the modal is gone
    expect(page.locator('[name="meeting-minutes"]')).to_have_count(0)


def test_minutes_modal_reopens_prefilled(meeting_page):
    from timetrack.plugins.meeting.models import MeetingNotes

    page, block = meeting_page
    MeetingNotes.objects.create(plan_block=block, minutes="Notes from last time")

    page.click(f"#block-{block.pk} .minutes-btn")
    expect(page.locator('[name="meeting-minutes"]')).to_have_value("Notes from last time")

    page.get_by_role("button", name="Cancel").click()
    expect(page.locator('[name="meeting-minutes"]')).to_have_count(0)


def test_non_meeting_chip_has_no_minutes_button(week_page_with_block):
    page, block = week_page_with_block

    expect(page.locator(f"#block-{block.pk} .minutes-btn")).to_have_count(0)

    page.click(f"#block-{block.pk}")
    expect(page.locator("#edit-panel")).to_be_visible()
    expect(page.locator('[name="meeting-minutes"]')).to_have_count(0)
