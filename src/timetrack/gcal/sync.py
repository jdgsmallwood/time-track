import hashlib
import json
from datetime import datetime, timezone

from django.conf import settings
from googleapiclient.discovery import build

from timetrack.plugins.registry import get_registry
from timetrack.schedule.models import PlanBlock, PlanWeek

from .oauth import get_credentials


def _block_hash(block: PlanBlock) -> str:
    """Deterministic hash of the fields we sync to GCal."""
    data = json.dumps(
        {
            "title": block.title,
            "date": block.date.isoformat(),
            "start": block.start_time.strftime("%H:%M"),
            "end": block.end_time.strftime("%H:%M"),
            "notes": block.notes,
        },
        sort_keys=True,
    )
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def _to_gcal_event(block: PlanBlock, tz: str) -> dict:
    registry = get_registry()
    plugin = registry.get(block.plugin_slug) if block.plugin_slug else None
    description_parts = []
    if block.notes:
        description_parts.append(block.notes)
    if plugin:
        extra = plugin.gcal_description(block)
        if extra:
            description_parts.append(extra)

    date_str = block.date.isoformat()
    start_dt = f"{date_str}T{block.start_time.strftime('%H:%M:%S')}"
    end_dt = f"{date_str}T{block.end_time.strftime('%H:%M:%S')}"
    return {
        "summary": block.title,
        "description": "\n".join(description_parts),
        "start": {"dateTime": start_dt, "timeZone": tz},
        "end": {"dateTime": end_dt, "timeZone": tz},
    }


def push_week(plan_week: PlanWeek) -> dict:
    """
    One-way push of all PlanBlocks in a PlanWeek to Google Calendar.

    Returns counts: created / updated / skipped / deleted.
    Idempotent: re-pushing an unchanged week is a no-op.
    """
    creds = get_credentials()
    if not creds:
        raise RuntimeError("Google Calendar not connected.")

    service = build("calendar", "v3", credentials=creds)
    cal_id = plan_week.google_calendar_id or _ensure_calendar(service)
    plan_week.google_calendar_id = cal_id

    tz = settings.TIME_ZONE
    counts = {"created": 0, "updated": 0, "skipped": 0, "deleted": 0}

    # Delete GCal events for blocks that were deleted since the last push.
    # Their event IDs were queued in plan_week.gcal_pending_delete_ids by the delete view.
    for orphan_id in list(plan_week.gcal_pending_delete_ids or []):
        try:
            service.events().delete(calendarId=cal_id, eventId=orphan_id).execute()
            counts["deleted"] += 1
        except Exception:
            pass  # may have already been deleted in GCal

    for block in plan_week.blocks.all():
        event_body = _to_gcal_event(block, tz)
        new_hash = _block_hash(block)

        if block.gcal_event_id:
            if block.sync_hash == new_hash:
                counts["skipped"] += 1
                continue
            service.events().update(
                calendarId=cal_id, eventId=block.gcal_event_id, body=event_body
            ).execute()
            counts["updated"] += 1
        else:
            created = service.events().insert(calendarId=cal_id, body=event_body).execute()
            block.gcal_event_id = created["id"]
            counts["created"] += 1

        block.sync_hash = new_hash
        block.save(update_fields=["gcal_event_id", "sync_hash"])

    plan_week.status = "synced"
    plan_week.gcal_pending_delete_ids = []
    plan_week.save(update_fields=["status", "google_calendar_id", "gcal_pending_delete_ids"])
    return counts


def _ensure_calendar(service) -> str:
    """Find or create a dedicated 'Time Tracking' calendar, return its id."""
    calendars = service.calendarList().list().execute().get("items", [])
    for cal in calendars:
        if cal.get("summary") == "Time Tracking":
            return cal["id"]
    new_cal = service.calendars().insert(body={"summary": "Time Tracking"}).execute()
    return new_cal["id"]
