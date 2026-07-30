from django.db import models


class MeetingNotes(models.Model):
    """Minutes taken during a meeting block. Plan blocks only — templates have no minutes."""
    plan_block = models.OneToOneField(
        "schedule.PlanBlock",
        on_delete=models.CASCADE,
        related_name="meeting_notes",
        null=True,
        blank=True,
    )
    minutes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "meeting notes"

    def __str__(self):
        return f"Minutes for {self.plan_block}"
