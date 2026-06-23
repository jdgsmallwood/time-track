from datetime import time

from django.core.management.base import BaseCommand

from timetrack.core.models import Category
from timetrack.plugins.running.models import RunSession
from timetrack.schedule.models import TemplateBlock, TemplateWeek


CATEGORIES = [
    ("Work", "#6366f1", "💼", 0),
    ("Deep Focus", "#8b5cf6", "🧠", 1),
    ("Exercise", "#22c55e", "🏃", 2),
    ("Music", "#a855f7", "🎵", 3),
    ("Family", "#f59e0b", "👨‍👩‍👧", 4),
    ("Admin", "#64748b", "📋", 5),
    ("Rest", "#94a3b8", "😴", 6),
]

BLOCKS = [
    # (day, start, end, title, category_name, plugin_slug, run_type, planned_km)
    # Monday
    (0, time(7, 0),  time(8, 0),  "Morning Run",        "Exercise", "running", "base", 8),
    (0, time(9, 0),  time(10, 0), "Team Standup",       "Work",     "",        None,   None),
    (0, time(10, 0), time(12, 30),"Deep Focus Block",   "Deep Focus","",       None,   None),
    (0, time(13, 0), time(14, 0), "Admin & Email",      "Admin",    "",        None,   None),
    (0, time(19, 0), time(20, 0), "Piano Practice",     "Music",    "practice",None,   None),
    # Tuesday
    (1, time(9, 0),  time(10, 0), "Team Standup",       "Work",     "",        None,   None),
    (1, time(10, 0), time(12, 30),"Deep Focus Block",   "Deep Focus","",       None,   None),
    (1, time(18, 0), time(19, 0), "Tempo Run",          "Exercise", "running", "tempo",10),
    (1, time(19, 30),time(20, 30),"Guitar Practice",    "Music",    "practice",None,   None),
    # Wednesday
    (2, time(9, 0),  time(10, 0), "Team Standup",       "Work",     "",        None,   None),
    (2, time(10, 0), time(12, 30),"Deep Focus Block",   "Deep Focus","",       None,   None),
    (2, time(13, 0), time(14, 0), "1:1 Meetings",       "Work",     "",        None,   None),
    (2, time(19, 0), time(20, 0), "Piano Practice",     "Music",    "practice",None,   None),
    # Thursday
    (3, time(7, 0),  time(8, 0),  "Recovery Run",       "Exercise", "running", "recovery", 5),
    (3, time(9, 0),  time(10, 0), "Team Standup",       "Work",     "",        None,   None),
    (3, time(10, 0), time(12, 30),"Deep Focus Block",   "Deep Focus","",       None,   None),
    (3, time(14, 0), time(16, 0), "Meetings",           "Work",     "",        None,   None),
    # Friday
    (4, time(9, 0),  time(10, 0), "Team Standup",       "Work",     "",        None,   None),
    (4, time(10, 0), time(12, 0), "Deep Focus Block",   "Deep Focus","",       None,   None),
    (4, time(13, 0), time(14, 0), "Week Review",        "Admin",    "",        None,   None),
    (4, time(19, 0), time(20, 30),"Guitar Practice",    "Music",    "practice",None,   None),
    # Saturday
    (5, time(8, 0),  time(10, 30),"Long Run",           "Exercise", "running", "long", 18),
    (5, time(14, 0), time(17, 0), "Family Time",        "Family",   "",        None,   None),
    # Sunday
    (6, time(10, 0), time(11, 0), "Piano Practice",     "Music",    "practice",None,   None),
    (6, time(14, 0), time(18, 0), "Family Time",        "Family",   "",        None,   None),
    (6, time(20, 0), time(21, 0), "Rest / Prep",        "Rest",     "",        None,   None),
]


class Command(BaseCommand):
    help = "Seed demo categories and a default template week."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Re-seed even if data exists")

    def handle(self, *args, **options):
        if not options["force"] and Category.objects.exists():
            self.stdout.write("Data already exists. Use --force to re-seed.")
            return

        self.stdout.write("Creating categories...")
        cat_map = {}
        for name, color, icon, order in CATEGORIES:
            cat, _ = Category.objects.get_or_create(
                name=name, defaults={"color": color, "icon": icon, "order": order}
            )
            cat_map[name] = cat

        self.stdout.write("Creating default template week...")
        template, _ = TemplateWeek.objects.get_or_create(
            name="Default Week",
            defaults={"description": "A balanced week — work, running, music, family.", "is_default": True},
        )
        if options["force"]:
            template.blocks.all().delete()

        for day, start, end, title, cat_name, plugin_slug, run_type, planned_km in BLOCKS:
            block = TemplateBlock.objects.create(
                template=template,
                day_of_week=day,
                start_time=start,
                end_time=end,
                title=title,
                category=cat_map.get(cat_name),
                plugin_slug=plugin_slug,
            )
            if plugin_slug == "running" and run_type:
                from decimal import Decimal
                RunSession.objects.create(
                    template_block=block,
                    run_type=run_type,
                    planned_km=Decimal(str(planned_km)),
                )
            if plugin_slug == "practice":
                from timetrack.plugins.practice.models import PracticeSession
                instrument = "Piano" if "Piano" in title else "Guitar"
                PracticeSession.objects.create(
                    template_block=block,
                    instrument=instrument,
                    focus="repertoire",
                    planned_minutes=int((end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)),
                )

        self.stdout.write(self.style.SUCCESS(
            f"Done. {len(BLOCKS)} template blocks created across 7 days."
        ))
