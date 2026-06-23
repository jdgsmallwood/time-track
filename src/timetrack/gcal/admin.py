from django.contrib import admin

from .models import GoogleCredentials


@admin.register(GoogleCredentials)
class GoogleCredentialsAdmin(admin.ModelAdmin):
    list_display = ["target_calendar_id", "updated_at"]
    readonly_fields = ["token", "refresh_token", "scopes", "expiry", "created_at", "updated_at"]
