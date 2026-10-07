from datetime import date

import pytest
from playwright.sync_api import expect

from timetrack.schedule.models import BrainDumpItem, PlanBlock, PlanWeek

pytestmark = pytest.mark.django_db(transaction=True)


def test_capture_review_and_schedule_without_losing_checkin(authenticated_page, live_server):
    week = PlanWeek.objects.create(start_date=date(2024, 6, 17))
    page = authenticated_page
    page.goto(f"{live_server.url}/schedule/weeks/{week.start_date}/")
    page.locator('[hx-get="/schedule/days/2024-06-19/recap/"]:visible').click()
    page.get_by_label("Things to remember (one per line)").fill("Call plumber\nBook flights")
    page.get_by_role("button", name="Save for later").click()
    expect(page.get_by_role("status")).to_contain_text("Saved 2")
    page.get_by_role("button", name="Cancel", exact=True).click()

    page.locator('[hx-get="/schedule/days/2024-06-20/check-in/"]:visible').click()
    page.get_by_label("Daily intention").fill("Keep my unfinished check-in")
    page.locator("#brain-dump summary").click()
    expect(page.locator("#brain-dump")).to_contain_text("Book flights")
    page.get_by_label("Things to remember (one per line)").fill("An unsaved thought")
    item = BrainDumpItem.objects.get(text="Call plumber")
    page.get_by_label("Start time", exact=True).first.fill("11:00")
    page.get_by_label("End time", exact=True).first.fill("10:00")
    page.get_by_role("button", name="Add to day's board").first.click()
    expect(page.get_by_role("alert")).to_contain_text("End time must be after start time")
    page.get_by_label("End time", exact=True).first.fill("11:30")
    page.get_by_role("button", name="Add to day's board").first.click()
    expect(page.get_by_role("status")).to_contain_text("Added to the day's board")
    expect(page.get_by_label("Daily intention")).to_have_value("Keep my unfinished check-in")
    expect(page.get_by_label("Things to remember (one per line)")).to_have_value("An unsaved thought")
    block = PlanBlock.objects.get(title="Call plumber")
    assert block.date == date(2024, 6, 20)
    expect(page.locator(f"#block-{block.pk}")).to_have_count(1)
    item.refresh_from_db()
    assert item.is_archived
    page.get_by_role("button", name="Save for later").click()
    expect(page.get_by_role("status")).to_contain_text("Saved 1")
    page.get_by_role("button", name="Save check-in").click()
    expect(page.get_by_role("heading", name="Daily check-in")).to_have_count(0)

    page.get_by_role("button", name="Review week", exact=True).click()
    page.locator("#brain-dump summary").click()
    expect(page.locator("#brain-dump")).to_contain_text("An unsaved thought")
    expect(page.get_by_role("button", name="Add to day's board")).to_have_count(0)
