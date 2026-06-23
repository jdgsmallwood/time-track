from django.db import models


class GoogleCredentials(models.Model):
    """Single-row store for the user's Google OAuth tokens."""

    token = models.TextField()
    refresh_token = models.TextField(blank=True)
    token_uri = models.CharField(max_length=200, default="https://oauth2.googleapis.com/token")
    client_id = models.CharField(max_length=300)
    client_secret = models.CharField(max_length=300)
    scopes = models.TextField()  # space-separated
    expiry = models.DateTimeField(null=True, blank=True)
    target_calendar_id = models.CharField(max_length=300, default="primary")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Google Credentials"
        verbose_name_plural = "Google Credentials"

    def __str__(self):
        return f"Google credentials (updated {self.updated_at})"
