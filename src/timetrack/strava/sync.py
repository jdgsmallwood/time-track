"""One-way Strava → RunSession sync for a concrete week."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import requests

from timetrack.plugins.running.models import RunSession
from timetrack.schedule.models import PlanBlock, PlanWeek

from .oauth import get_access_token

_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"


def _pace_str(avg_speed_ms: float) -> str:
    """Convert average speed in m/s to pace string like '5:12/km'."""
    if not avg_speed_ms or avg_speed_ms <= 0:
        return ""
    sec_per_km = int(1000 / avg_speed_ms)
    return f"{sec_per_km // 60}:{sec_per_km % 60:02d}/km"


def sync_week_activities(plan_week: PlanWeek) -> dict:
    """
    Fetch Strava running activities in the plan week's date range and match
    them to RunSession blocks.

    Matching strategy:
    - Filter Strava activities with type == "Run" whose local start date falls
      within the week.
    - For each activity, find PlanBlocks in this week with plugin_slug="running"
      on the same date.
      - If exactly one block on that date: update it.
      - If multiple: choose the one with closest planned_km.
      - If none: count as unmatched.

    Returns {"matched": N, "unmatched": M}
    """
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    start_epoch = int(
        datetime(plan_week.start_date.year, plan_week.start_date.month,
                 plan_week.start_date.day, tzinfo=timezone.utc).timestamp()
    )
    end_epoch = start_epoch + 7 * 86400

    params = {"after": start_epoch, "before": end_epoch, "per_page": 50}
    resp = requests.get(_ACTIVITIES_URL, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    activities = resp.json()

    run_activities = [a for a in activities if a.get("type") == "Run"]

    run_blocks = list(
        plan_week.blocks.filter(plugin_slug="running").select_related("category").order_by("date")
    )
    blocks_by_date: dict = {}
    for b in run_blocks:
        blocks_by_date.setdefault(b.date, []).append(b)

    matched = 0
    unmatched = 0

    for activity in run_activities:
        start_local_str = activity.get("start_date_local", "")
        try:
            activity_date = datetime.fromisoformat(start_local_str[:10]).date()
        except (ValueError, TypeError):
            unmatched += 1
            continue

        candidates = blocks_by_date.get(activity_date, [])
        if not candidates:
            unmatched += 1
            continue

        actual_km = Decimal(str(round(activity.get("distance", 0) / 1000, 2)))
        actual_pace = _pace_str(activity.get("average_speed", 0))
        strava_id = activity["id"]

        if len(candidates) == 1:
            block = candidates[0]
        else:
            # Match by closest planned_km
            def km_distance(b):
                try:
                    session = RunSession.objects.filter(plan_block=b).first()
                    if session and session.planned_km:
                        return abs(float(session.planned_km) - float(actual_km))
                except Exception:
                    pass
                return float("inf")

            block = min(candidates, key=km_distance)

        session, _ = RunSession.objects.get_or_create(plan_block=block)
        session.actual_km = actual_km
        session.actual_pace = actual_pace
        session.strava_activity_id = strava_id
        session.save(update_fields=["actual_km", "actual_pace", "strava_activity_id"])
        matched += 1

    return {"matched": matched, "unmatched": unmatched}
