from datetime import date, time

import pytest

from timetrack.schedule.models import BrainDumpItem, PlanBlock, PlanWeek

pytestmark = pytest.mark.django_db
URL = "/schedule/brain-dump/"
DAY_URL = URL + "?date=2024-06-19"


def schedule_data(item, **overrides):
    return {
        "action": "schedule", "item": item.pk,
        f"{item.pk}-date": "2024-06-19",
        f"{item.pk}-start_time": "10:00",
        f"{item.pk}-end_time": "10:30",
        **overrides,
    }


def test_capture_persists_across_days_and_review_panels(auth_client):
    response = auth_client.post(URL, {"action": "capture", "thoughts": " Call plumber\r\n\nBook flights "})
    assert response.status_code == 200
    assert list(BrainDumpItem.objects.values_list("text", flat=True)) == ["Call plumber", "Book flights"]
    for url in [URL, DAY_URL, URL + "?date=2025-01-01"]:
        assert b"Call plumber" in auth_client.get(url).content
    week = PlanWeek.objects.create(start_date=date(2024, 6, 17))
    for url in ["/schedule/days/2024-06-19/check-in/", "/schedule/days/2024-06-19/recap/",
                f"/schedule/plan-weeks/{week.pk}/review/"]:
        assert URL in auth_client.get(url).content.decode()


def test_schedule_once_keeps_other_items_and_full_text(auth_client):
    item = BrainDumpItem.objects.create(text="A long thought " * 30)
    later = BrainDumpItem.objects.create(text="For another day")
    response = auth_client.post(DAY_URL, schedule_data(item, thoughts="Still typing"))
    assert response.status_code == 200
    assert b"Still typing" in response.content
    assert b"GRID.updateBlock" in response.content
    assert "weekStatsChanged" in response["HX-Trigger"]
    block = PlanBlock.objects.get()
    assert block.date == date(2024, 6, 19)
    assert block.week.start_date == date(2024, 6, 17)
    assert (block.start_time, block.end_time) == (time(10), time(10, 30))
    assert block.title == item.text[:200]
    assert block.notes == item.text
    item.refresh_from_db()
    later.refresh_from_db()
    assert item.is_archived and not later.is_archived
    auth_client.post(DAY_URL, schedule_data(item))
    assert PlanBlock.objects.count() == 1


@pytest.mark.parametrize("overrides", [
    {"start_time": "not a time"}, {"end_time": "09:00"}, {"end_time": "10:00"},
    {"category": "999999"}, {"date": "2024-06-20"},
])
def test_invalid_schedule_keeps_item_pending(auth_client, overrides):
    item = BrainDumpItem.objects.create(text="Keep me safe")
    auth_client.post(DAY_URL, schedule_data(item, **{f"{item.pk}-{k}": v for k, v in overrides.items()}))
    item.refresh_from_db()
    assert not item.is_archived
    assert not PlanBlock.objects.exists()


def test_dismiss_and_escaped_text(auth_client):
    item = BrainDumpItem.objects.create(text="<script>alert('x')</script>")
    assert b"&lt;script&gt;" in auth_client.get(URL).content
    auth_client.post(URL, {"action": "dismiss", "item": item.pk})
    item.refresh_from_db()
    assert item.is_archived
    assert b"Nothing waiting" in auth_client.get(URL).content
    assert not PlanBlock.objects.exists()


def test_invalid_capture_and_unauthenticated_requests(auth_client):
    from django.test import Client

    assert Client().post(URL, {"action": "capture", "thoughts": "Private"}).status_code == 302
    auth_client.post(URL, {"action": "capture", "thoughts": " \n "})
    assert auth_client.post(URL + "?date=invalid", {"action": "capture", "thoughts": "Bad date"}).status_code == 400
    assert not BrainDumpItem.objects.exists()
