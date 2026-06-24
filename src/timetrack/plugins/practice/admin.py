from django.contrib import admin

from .models import PracticeGoal, PracticeSession


@admin.register(PracticeGoal)
class PracticeGoalAdmin(admin.ModelAdmin):
    list_display = ["instrument", "focus", "duration_minutes", "recurrence_count", "is_active"]
    list_filter = ["is_active", "focus"]


@admin.register(PracticeSession)
class PracticeSessionAdmin(admin.ModelAdmin):
    list_display = ["instrument", "focus", "planned_minutes", "actual_minutes", "goal", "template_block", "plan_block"]
