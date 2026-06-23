from django.db import models

FOCUS_CHOICES = [
    ("technique", "Technique"),
    ("repertoire", "Repertoire"),
    ("sight_reading", "Sight Reading"),
    ("theory", "Theory"),
    ("improvisation", "Improvisation"),
    ("free", "Free Practice"),
]


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
    instrument = models.CharField(max_length=100, blank=True)
    focus = models.CharField(max_length=30, choices=FOCUS_CHOICES, default="free")
    pieces = models.TextField(blank=True, help_text="Pieces / exercises to work on")
    planned_minutes = models.PositiveIntegerField(null=True, blank=True)
    actual_minutes = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.instrument or 'Practice'} — {self.get_focus_display()}"
