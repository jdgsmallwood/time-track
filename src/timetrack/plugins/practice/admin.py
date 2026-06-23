from django.contrib import admin

from .models import PracticeSession


@admin.register(PracticeSession)
class PracticeSessionAdmin(admin.ModelAdmin):
    list_display = ["instrument", "focus", "planned_minutes", "actual_minutes", "template_block", "plan_block"]
