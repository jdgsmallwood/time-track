from django.db import models

from timetrack.core.models import Category

DAY_CHOICES = [
    (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
    (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
]

STATUS_CHOICES = [("draft", "Draft"), ("synced", "Synced")]


class TemplateWeek(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            TemplateWeek.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class TemplateBlock(models.Model):
    template = models.ForeignKey(TemplateWeek, on_delete=models.CASCADE, related_name="blocks")
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    title = models.CharField(max_length=200)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="template_blocks"
    )
    notes = models.TextField(blank=True)
    plugin_slug = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["day_of_week", "start_time"]

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.start_time}–{self.end_time}: {self.title}"

    @property
    def duration_minutes(self):
        start = self.start_time.hour * 60 + self.start_time.minute
        end = self.end_time.hour * 60 + self.end_time.minute
        return max(end - start, 0)


class PlanWeek(models.Model):
    start_date = models.DateField(unique=True)  # always a Monday
    source_template = models.ForeignKey(
        TemplateWeek, on_delete=models.SET_NULL, null=True, blank=True, related_name="plan_weeks"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    google_calendar_id = models.CharField(max_length=200, blank=True)
    # GCal event IDs queued for deletion on next push (blocks deleted since last sync)
    gcal_pending_delete_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"Week of {self.start_date}"

    @property
    def end_date(self):
        from datetime import timedelta
        return self.start_date + timedelta(days=6)


class PlanBlock(models.Model):
    week = models.ForeignKey(PlanWeek, on_delete=models.CASCADE, related_name="blocks")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    title = models.CharField(max_length=200)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="plan_blocks"
    )
    notes = models.TextField(blank=True)
    plugin_slug = models.CharField(max_length=50, blank=True)
    source_template_block = models.ForeignKey(
        TemplateBlock, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="plan_blocks"
    )
    gcal_event_id = models.CharField(max_length=200, blank=True)
    sync_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.date} {self.start_time}–{self.end_time}: {self.title}"

    @property
    def duration_minutes(self):
        start = self.start_time.hour * 60 + self.start_time.minute
        end = self.end_time.hour * 60 + self.end_time.minute
        return max(end - start, 0)
