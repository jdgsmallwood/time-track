from datetime import date

from django.core.management.base import BaseCommand, CommandError

from timetrack.gcal.sync import push_week
from timetrack.schedule.models import PlanWeek
from timetrack.schedule.services import week_monday


class Command(BaseCommand):
    help = "Push a plan week to Google Calendar. Provide the week's start date (YYYY-MM-DD)."

    def add_arguments(self, parser):
        parser.add_argument("date", help="Any date in the target week (YYYY-MM-DD)")

    def handle(self, *args, **options):
        try:
            d = date.fromisoformat(options["date"])
        except ValueError:
            raise CommandError("Date must be in YYYY-MM-DD format.")

        monday = week_monday(d)
        try:
            week = PlanWeek.objects.get(start_date=monday)
        except PlanWeek.DoesNotExist:
            raise CommandError(f"No plan week found for {monday}.")

        result = push_week(week)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {result['created']} created, {result['updated']} updated, "
                f"{result['skipped']} skipped, {result['deleted']} deleted."
            )
        )
