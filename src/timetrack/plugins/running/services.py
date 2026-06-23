"""Business logic for running training plans."""
import csv
import io
from datetime import date, timedelta
from decimal import Decimal

from .models import RUN_TYPE_CHOICES, TrainingPlan, TrainingPlanSession, TrainingPlanWeek

_RUN_TYPE_MAP = {label.lower(): slug for slug, label in RUN_TYPE_CHOICES}
# Also allow the raw slugs directly
_RUN_TYPE_MAP.update({slug: slug for slug, _ in RUN_TYPE_CHOICES})
# Common abbreviations
_RUN_TYPE_MAP.update({
    "easy": "base",
    "base/easy": "base",
    "base / easy": "base",
    "lr": "long",
    "long run": "long",
    "interval": "intervals",
    "rec": "recovery",
})

_PACE_FIELD_MAP = {
    "easy": "pace_easy_sec",
    "base": "pace_easy_sec",
    "tempo": "pace_tempo_sec",
    "intervals": "pace_interval_sec",
    "interval": "pace_interval_sec",
    "long": "pace_long_sec",
    "recovery": "pace_recovery_sec",
    "race": "pace_tempo_sec",  # approximate race as tempo pace
}


def _parse_pace(pace_str: str) -> int:
    """Convert 'M:SS' or 'M:SS/km' to seconds/km."""
    pace_str = pace_str.strip().replace("/km", "").strip()
    parts = pace_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid pace format '{pace_str}' — expected M:SS")
    return int(parts[0]) * 60 + int(parts[1])


def pace_sec_for_type(plan: TrainingPlan, run_type: str) -> int:
    """Return the pace in seconds/km for the given run type from the plan's pace zones."""
    field = _PACE_FIELD_MAP.get(run_type, "pace_easy_sec")
    return getattr(plan, field)


def estimate_session_minutes(session: TrainingPlanSession, plan: TrainingPlan) -> int:
    """Estimated duration in minutes: target_km × pace_sec/km ÷ 60."""
    pace_sec = pace_sec_for_type(plan, session.run_type)
    return int(float(session.target_km) * pace_sec / 60)


def estimate_week_minutes(plan_week: TrainingPlanWeek, plan: TrainingPlan) -> int:
    """Total estimated minutes across all sessions in the plan week."""
    return sum(estimate_session_minutes(s, plan) for s in plan_week.sessions.all())


def get_current_plan_week(plan: TrainingPlan) -> TrainingPlanWeek | None:
    """
    Return the TrainingPlanWeek whose date range includes today.
    Week N covers [start_date + (N-1)*7 days, start_date + N*7 - 1 days].
    Returns None if today is before the plan starts or after all weeks end.
    """
    today = date.today()
    if today < plan.start_date:
        return None
    delta = (today - plan.start_date).days
    week_number = delta // 7 + 1
    return plan.weeks.filter(week_number=week_number).first()


def import_plan_from_csv(csv_text: str) -> TrainingPlan:
    """
    Parse a CSV training plan and create TrainingPlan + weeks + sessions.

    Format:
      # Header block (key,value pairs)
      name,My plan
      start_date,2024-09-02
      pace_easy,6:00
      ...

      # Blank line separates header from session rows
      week,phase,target_km,day,type,km,notes
      1,base,40,1,easy,10,Notes here
      ...

    Raises ValueError with row context on bad data.
    """
    reader = csv.reader(io.StringIO(csv_text.strip()))
    rows = list(reader)

    # Split header from data at the first blank row
    header_rows = []
    data_rows = []
    in_data = False
    col_header_row = None

    for i, row in enumerate(rows):
        if not any(cell.strip() for cell in row):
            in_data = True
            continue
        if in_data:
            if col_header_row is None:
                col_header_row = [c.strip().lower() for c in row]
            else:
                data_rows.append((i + 1, row))
        else:
            header_rows.append(row)

    # Parse header key/value pairs
    header = {}
    for row in header_rows:
        if len(row) >= 2:
            header[row[0].strip().lower()] = row[1].strip()

    if "name" not in header:
        raise ValueError("CSV must include a 'name' key in the header section.")
    if "start_date" not in header:
        raise ValueError("CSV must include a 'start_date' key (YYYY-MM-DD).")

    try:
        start_date = date.fromisoformat(header["start_date"])
    except ValueError:
        raise ValueError(f"Invalid start_date '{header['start_date']}' — use YYYY-MM-DD.")

    plan_kwargs = {
        "name": header["name"],
        "description": header.get("description", ""),
        "start_date": start_date,
    }
    for pace_key, field in [
        ("pace_easy", "pace_easy_sec"),
        ("pace_tempo", "pace_tempo_sec"),
        ("pace_interval", "pace_interval_sec"),
        ("pace_long", "pace_long_sec"),
        ("pace_recovery", "pace_recovery_sec"),
    ]:
        if pace_key in header:
            try:
                plan_kwargs[field] = _parse_pace(header[pace_key])
            except ValueError as e:
                raise ValueError(f"Bad value for '{pace_key}': {e}")

    plan = TrainingPlan.objects.create(**plan_kwargs)

    if not col_header_row or not data_rows:
        return plan

    required = {"week", "phase", "type", "km"}
    missing = required - set(col_header_row)
    if missing:
        raise ValueError(f"Session rows missing columns: {', '.join(missing)}")

    def col(row, name, lineno):
        idx = col_header_row.index(name) if name in col_header_row else -1
        if idx < 0:
            return ""
        if idx >= len(row):
            raise ValueError(f"Row {lineno}: too few columns (expected column '{name}').")
        return row[idx].strip()

    plan_weeks: dict = {}

    for lineno, row in data_rows:
        if not any(cell.strip() for cell in row):
            continue
        try:
            week_num = int(col(row, "week", lineno))
            phase_raw = col(row, "phase", lineno).lower()
            target_km_raw = col(row, "target_km", lineno) if "target_km" in col_header_row else ""
            day_raw = col(row, "day", lineno) if "day" in col_header_row else "0"
            type_raw = col(row, "type", lineno).lower()
            km_raw = col(row, "km", lineno)
            notes = col(row, "notes", lineno) if "notes" in col_header_row else ""
        except ValueError as e:
            raise ValueError(f"Row {lineno}: {e}")

        # Resolve run type
        run_type = _RUN_TYPE_MAP.get(type_raw)
        if not run_type:
            raise ValueError(f"Row {lineno}: unknown run type '{type_raw}'.")

        # Resolve phase
        valid_phases = {slug for slug, _ in [
            ("base", "Base"), ("build", "Build"), ("peak", "Peak"),
            ("taper", "Taper"), ("recovery", "Recovery"),
        ]}
        if phase_raw not in valid_phases:
            raise ValueError(f"Row {lineno}: unknown phase '{phase_raw}'.")

        try:
            km = Decimal(km_raw)
        except Exception:
            raise ValueError(f"Row {lineno}: invalid km value '{km_raw}'.")

        try:
            day_of_week = int(day_raw) if day_raw else 0
        except ValueError:
            raise ValueError(f"Row {lineno}: invalid day '{day_raw}' — use 0 (Mon) to 6 (Sun).")

        # Get or create the plan week
        if week_num not in plan_weeks:
            target_km = Decimal(target_km_raw) if target_km_raw else Decimal("0")
            pw = TrainingPlanWeek.objects.create(
                plan=plan,
                week_number=week_num,
                phase=phase_raw,
                target_km=target_km,
            )
            plan_weeks[week_num] = pw
        else:
            pw = plan_weeks[week_num]

        TrainingPlanSession.objects.create(
            plan_week=pw,
            run_type=run_type,
            target_km=km,
            day_of_week=day_of_week,
            notes=notes,
        )

    return plan
