from django.db import models

RUN_TYPE_CHOICES = [
    ("base", "Base / Easy"),
    ("tempo", "Tempo"),
    ("intervals", "Intervals"),
    ("long", "Long Run"),
    ("recovery", "Recovery"),
    ("race", "Race"),
]

PHASE_CHOICES = [
    ("base", "Base"),
    ("build", "Build"),
    ("peak", "Peak"),
    ("taper", "Taper"),
    ("recovery", "Recovery"),
]

DAY_CHOICES = [
    (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
    (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
]


class RunSession(models.Model):
    template_block = models.OneToOneField(
        "schedule.TemplateBlock",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="run_session",
    )
    plan_block = models.OneToOneField(
        "schedule.PlanBlock",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="run_session",
    )
    run_type = models.CharField(max_length=20, choices=RUN_TYPE_CHOICES, default="base")
    planned_km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    actual_km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    planned_pace = models.CharField(max_length=10, blank=True, help_text="e.g. 5:30/km")
    actual_pace = models.CharField(max_length=10, blank=True, help_text="e.g. 5:12/km — filled by Strava sync")
    strava_activity_id = models.BigIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        km = self.planned_km or "?"
        return f"{self.get_run_type_display()} — {km} km"


class TrainingPlan(models.Model):
    """A multi-week running training plan with phase structure and pace zones."""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=False)
    start_date = models.DateField(help_text="Monday of Week 1")
    # Pace zones in seconds/km for arithmetic
    pace_easy_sec = models.IntegerField(default=360, help_text="6:00/km")
    pace_tempo_sec = models.IntegerField(default=300, help_text="5:00/km")
    pace_interval_sec = models.IntegerField(default=270, help_text="4:30/km")
    pace_long_sec = models.IntegerField(default=390, help_text="6:30/km")
    pace_recovery_sec = models.IntegerField(default=420, help_text="7:00/km")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_active:
            TrainingPlan.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @property
    def total_weeks(self):
        return self.weeks.count()


class TrainingPlanWeek(models.Model):
    plan = models.ForeignKey(TrainingPlan, on_delete=models.CASCADE, related_name="weeks")
    week_number = models.IntegerField()
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default="base")
    target_km = models.DecimalField(max_digits=6, decimal_places=1)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("plan", "week_number")
        ordering = ["week_number"]

    def __str__(self):
        return f"Week {self.week_number} ({self.get_phase_display()}) — {self.target_km} km"


class TrainingPlanSession(models.Model):
    plan_week = models.ForeignKey(TrainingPlanWeek, on_delete=models.CASCADE, related_name="sessions")
    run_type = models.CharField(max_length=20, choices=RUN_TYPE_CHOICES, default="base")
    target_km = models.DecimalField(max_digits=5, decimal_places=1)
    day_of_week = models.IntegerField(choices=DAY_CHOICES, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["day_of_week"]

    def __str__(self):
        return f"{self.get_run_type_display()} {self.target_km} km ({self.get_day_of_week_display()})"
