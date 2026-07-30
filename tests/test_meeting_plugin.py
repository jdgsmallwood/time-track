"""Tests for the meeting plugin model, form, plugin class, and minutes modal view."""
from datetime import date, time

import pytest
from django.urls import reverse

from timetrack.plugins.meeting.forms import MeetingNotesForm
from timetrack.plugins.meeting.models import MeetingNotes
from timetrack.plugins.meeting.plugin import MeetingPlugin
from timetrack.plugins.registry import get_registry
from timetrack.schedule.models import PlanBlock, PlanWeek, TemplateBlock, TemplateWeek
from timetrack.schedule.services import clone_template_to_week


@pytest.fixture
def plan_block(db):
    week = PlanWeek.objects.create(start_date=date(2026, 6, 15))
    return PlanBlock.objects.create(
        week=week, date=date(2026, 6, 16), start_time=time(10, 0), end_time=time(11, 0),
        title="Standup", plugin_slug="meeting",
    )


@pytest.mark.django_db
def test_plugin_registered():
    plugin = get_registry().get("meeting")
    assert isinstance(plugin, MeetingPlugin)
    assert plugin.name == "Meeting"


@pytest.mark.django_db
def test_form_accepts_text_and_blank():
    assert MeetingNotesForm(data={"minutes": "Agreed to ship on Friday"}).is_valid()
    assert MeetingNotesForm(data={"minutes": ""}).is_valid()


@pytest.mark.django_db
def test_init_block_data_is_idempotent(plan_block):
    plugin = MeetingPlugin()
    plugin.init_block_data(plan_block)
    plugin.init_block_data(plan_block)
    assert MeetingNotes.objects.filter(plan_block=plan_block).count() == 1


@pytest.mark.django_db
def test_render_summary_only_when_minutes_present(plan_block):
    plugin = MeetingPlugin()
    notes = MeetingNotes.objects.create(plan_block=plan_block, minutes="   ")
    plan_block.refresh_from_db()
    assert plugin.render_summary(plan_block) == ""

    notes.minutes = "Decided X"
    notes.save()
    plan_block.refresh_from_db()
    assert "Minutes" in plugin.render_summary(plan_block)


@pytest.mark.django_db
def test_render_summary_no_notes_row(plan_block):
    assert MeetingPlugin().render_summary(plan_block) == ""


@pytest.mark.django_db
def test_gcal_description_is_empty(plan_block):
    MeetingNotes.objects.create(plan_block=plan_block, minutes="Private minutes")
    plan_block.refresh_from_db()
    assert MeetingPlugin().gcal_description(plan_block) == ""


@pytest.mark.django_db
def test_get_plan_form_bound_to_existing_notes(plan_block):
    MeetingNotes.objects.create(plan_block=plan_block, minutes="Existing")
    form = MeetingPlugin().get_plan_form(plan_block)
    assert form.instance.minutes == "Existing"
    assert form.prefix == "meeting"


@pytest.mark.django_db
def test_modal_get_renders_existing_minutes(auth_client, plan_block):
    MeetingNotes.objects.create(plan_block=plan_block, minutes="Last week's decisions")
    url = reverse("meeting-notes", kwargs={"block_pk": plan_block.pk})
    response = auth_client.get(url)
    assert response.status_code == 200
    assert "Last week&#x27;s decisions" in response.content.decode()
    assert "Standup" in response.content.decode()


@pytest.mark.django_db
def test_modal_get_creates_notes_row(auth_client, plan_block):
    url = reverse("meeting-notes", kwargs={"block_pk": plan_block.pk})
    auth_client.get(url)
    assert MeetingNotes.objects.filter(plan_block=plan_block).exists()


@pytest.mark.django_db
def test_modal_post_saves_and_refreshes(auth_client, plan_block):
    url = reverse("meeting-notes", kwargs={"block_pk": plan_block.pk})
    response = auth_client.post(url, {"meeting-minutes": "Ship on Friday"})
    assert response.status_code == 204
    assert response["HX-Refresh"] == "true"
    assert MeetingNotes.objects.get(plan_block=plan_block).minutes == "Ship on Friday"


@pytest.mark.django_db
def test_modal_404_for_unknown_block(auth_client):
    response = auth_client.get(reverse("meeting-notes", kwargs={"block_pk": 999999}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_clone_from_template_carries_no_minutes():
    template = TemplateWeek.objects.create(name="T")
    TemplateBlock.objects.create(
        template=template, day_of_week=0, start_time=time(9, 0), end_time=time(9, 30),
        title="Standup", plugin_slug="meeting",
    )
    plan_week = clone_template_to_week(template, date(2026, 7, 6))

    block = plan_week.blocks.get()
    assert block.plugin_slug == "meeting"
    assert not MeetingNotes.objects.filter(plan_block=block).exists()


@pytest.mark.django_db
def test_copy_plan_block_forward_carries_no_minutes(plan_block):
    MeetingNotes.objects.create(plan_block=plan_block, minutes="Do not copy me")
    next_week = PlanWeek.objects.create(start_date=date(2026, 6, 22))
    dest = PlanBlock.objects.create(
        week=next_week, date=date(2026, 6, 23), start_time=time(10, 0), end_time=time(11, 0),
        title="Standup", plugin_slug="meeting",
    )
    MeetingPlugin().clone_plan_block_data(plan_block, dest)
    assert not MeetingNotes.objects.filter(plan_block=dest).exists()


@pytest.mark.django_db
def test_grid_create_with_meeting_plugin_inits_notes(auth_client):
    """Popover/drag create posts plugin_slug; server must init the notes row."""
    week = PlanWeek.objects.create(start_date=date(2026, 7, 6))
    response = auth_client.post(
        reverse("plan-block-create", kwargs={"week_pk": week.pk}),
        data='{"title": "Standup", "date": "2026-07-06", "start_time": "09:00",'
             ' "end_time": "09:30", "plugin_slug": "meeting"}',
        content_type="application/json",
    )
    assert response.status_code == 200
    block = week.blocks.get()
    assert block.plugin_slug == "meeting"
    assert MeetingNotes.objects.filter(plan_block=block).exists()
