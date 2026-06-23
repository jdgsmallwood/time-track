from django.db import models


class StravaCredentials(models.Model):
    """Singleton (pk=1) storing the Strava OAuth tokens."""
    athlete_id = models.BigIntegerField()
    athlete_name = models.CharField(max_length=200, blank=True)
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.IntegerField(help_text="Unix timestamp when access_token expires")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Strava Credentials"
        verbose_name_plural = "Strava Credentials"

    def __str__(self):
        return f"Strava: {self.athlete_name or self.athlete_id}"
