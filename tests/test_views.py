"""Smoke tests and view tests for schedule, core, and gcal."""
from datetime import date, time

import pytest

from timetrack.schedule.models import PlanBlock, PlanWeek, TemplateBlock, TemplateWeek
from timetrack.core.models import Category


@pytest.fixture
def template(db):
    return TemplateWeek.objects.create(name="My Template", is_default=True)


@pytest.fixture
def plan_week(db):
    return PlanWeek.objects.create(start_date=date(2024, 6, 17))


@pytest.fixture
def plan_block(plan_week):
    return PlanBlock.objects.create(
        week=plan_week, date=date(2024, 6, 17), start_time=time(9, 0), end_time=time(10, 0),
        title="Test block",
    )


# ─── Auth ──────────────────────────────────────────────────────────────────

def test_login_required_redirects(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def test_login_page_renders(client):
    response = client.get("/accounts/login/")
    assert response.status_code == 200


# ─── Healthcheck ────────────────────────────────────────────────────────────

def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ─── Dashboard ──────────────────────────────────────────────────────────────

def test_dashboard_renders(auth_client):
    response = auth_client.get("/")
    assert response.status_code == 200
    assert b"TimeTrack" in response.content


# ─── Templates ─────────────────────────────────────────────────────────────

def test_template_list(auth_client, template):
    response = auth_client.get("/schedule/templates/")
    assert response.status_code == 200
    assert b"My Template" in response.content


def test_template_create(auth_client):
    response = auth_client.post(
        "/schedule/templates/",
        {"name": "Holiday", "description": "Relaxed", "is_default": False},
    )
    assert response.status_code in (200, 302)
    assert TemplateWeek.objects.filter(name="Holiday").exists()


def test_template_detail(auth_client, template):
    response = auth_client.get(f"/schedule/templates/{template.pk}/")
    assert response.status_code == 200
    assert b"My Template" in response.content


# ─── Template blocks ───────────────────────────────────────────────────────

def test_create_template_block(auth_client, template):
    response = auth_client.post(
        f"/schedule/templates/{template.pk}/blocks/",
        {
            "title": "Morning run", "day_of_week": "0",
            "start_time": "07:00", "end_time": "08:00",
            "notes": "", "plugin_slug": "",
        },
    )
    assert response.status_code == 200
    assert TemplateBlock.objects.filter(title="Morning run").exists()


def test_update_template_block(auth_client, template):
    block = TemplateBlock.objects.create(
        template=template, day_of_week=0, start_time=time(9, 0),
        end_time=time(10, 0), title="Old Title",
    )
    response = auth_client.post(
        f"/schedule/template-blocks/{block.pk}/",
        {
            "title": "New Title", "day_of_week": "1",
            "start_time": "10:00", "end_time": "11:00",
            "notes": "", "plugin_slug": "",
        },
    )
    assert response.status_code == 200
    block.refresh_from_db()
    assert block.title == "New Title"


def test_patch_template_block_position(auth_client, template):
    import json
    block = TemplateBlock.objects.create(
        template=template, day_of_week=0, start_time=time(9, 0),
        end_time=time(10, 0), title="Block",
    )
    response = auth_client.patch(
        f"/schedule/template-blocks/{block.pk}/",
        json.dumps({"day_of_week": 2, "start_time": "14:00", "end_time": "15:00"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    block.refresh_from_db()
    assert block.day_of_week == 2
    assert str(block.start_time) == "14:00:00"


def test_delete_template_block(auth_client, template):
    block = TemplateBlock.objects.create(
        template=template, day_of_week=0, start_time=time(9, 0),
        end_time=time(10, 0), title="To delete",
    )
    response = auth_client.delete(f"/schedule/template-blocks/{block.pk}/")
    assert response.status_code == 204
    assert not TemplateBlock.objects.filter(pk=block.pk).exists()


# ─── Plan weeks ─────────────────────────────────────────────────────────────

def test_week_view_empty(auth_client):
    response = auth_client.get("/schedule/weeks/2024-06-17/")
    assert response.status_code == 200


def test_week_view_with_plan(auth_client, plan_week, plan_block):
    response = auth_client.get(f"/schedule/weeks/{plan_week.start_date}/")
    assert response.status_code == 200
    assert b"Test block" in response.content


def test_week_clone_via_post(auth_client, template):
    response = auth_client.post(
        "/schedule/weeks/2024-06-17/",
        {"template": template.pk, "replace": False},
    )
    assert response.status_code == 302
    assert PlanWeek.objects.filter(start_date=date(2024, 6, 17)).exists()


def test_plan_block_create(auth_client, plan_week):
    response = auth_client.post(
        f"/schedule/plan-weeks/{plan_week.pk}/blocks/",
        {
            "title": "Gym", "date": "2024-06-17",
            "start_time": "06:00", "end_time": "07:00",
            "notes": "", "plugin_slug": "",
        },
    )
    assert response.status_code == 200
    assert PlanBlock.objects.filter(title="Gym", week=plan_week).exists()


def test_plan_block_patch_position(auth_client, plan_block):
    import json
    response = auth_client.patch(
        f"/schedule/plan-blocks/{plan_block.pk}/",
        json.dumps({"date": "2024-06-18", "start_time": "10:00", "end_time": "11:00"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    plan_block.refresh_from_db()
    assert str(plan_block.date) == "2024-06-18"


def test_plan_block_delete(auth_client, plan_block):
    response = auth_client.delete(f"/schedule/plan-blocks/{plan_block.pk}/")
    assert response.status_code == 204
    assert not PlanBlock.objects.filter(pk=plan_block.pk).exists()


def test_delete_sets_week_to_draft(auth_client, plan_week, plan_block):
    plan_week.status = "synced"
    plan_week.save()
    auth_client.delete(f"/schedule/plan-blocks/{plan_block.pk}/")
    plan_week.refresh_from_db()
    assert plan_week.status == "draft"


# ─── GCal settings ──────────────────────────────────────────────────────────

def test_gcal_settings_not_connected(auth_client):
    response = auth_client.get("/gcal/settings/")
    assert response.status_code == 200
    assert b"Not connected" in response.content
