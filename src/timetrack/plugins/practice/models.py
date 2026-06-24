from django.db import models

FOCUS_CHOICES = [
    ("technique", "Technique"),
    ("repertoire", "Repertoire"),
    ("sight_reading", "Sight Reading"),
    ("theory", "Theory"),
    ("improvisation", "Improvisation"),
    ("band", "Band Pieces"),
    ("free", "Free Practice"),
]


class PracticeGoal(models.Model):
    """A recurring practice target shown in the week view 'To Schedule' panel."""
    instrument = models.CharField(max_length=100, blank=True)
    focus = models.CharField(max_length=30, choices=FOCUS_CHOICES, default="free")
    duration_minutes = models.PositiveIntegerField(default=60)
    recurrence_count = models.PositiveSmallIntegerField(
        default=1, help_text="How many times per week."
    )
    category = models.ForeignKey(
        "core.Category",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="practice_goals",
    )
    notes = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["instrument", "focus"]

    def __str__(self):
        return f"{self.instrument or 'Practice'} — {self.get_focus_display()}"

    @property
    def title(self):
        label = self.instrument or "Practice"
        return f"{label} · {self.get_focus_display()}"

    @property
    def color(self):
        return self.category.color if self.category else "#a855f7"


class PracticeSession(models.Model):
    template_block = models.OneToOneField(
        "schedule.TemplateBlock",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="practice_session",
    )
    plan_block = models.OneToOneField(
        "schedule.PlanBlock",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="practice_session",
    )
    goal = models.ForeignKey(
        PracticeGoal,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="sessions",
    )
    instrument = models.CharField(max_length=100, blank=True)
    focus = models.CharField(max_length=30, choices=FOCUS_CHOICES, default="free")
    pieces = models.TextField(blank=True, help_text="Pieces / exercises to work on")
    planned_minutes = models.PositiveIntegerField(null=True, blank=True)
    actual_minutes = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.instrument or 'Practice'} — {self.get_focus_display()}"
