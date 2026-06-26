from django.contrib import admin

from .models import PlanBlock, PlanWeek, PlanWeekReflection, TemplateBlock, TemplateWeek, WeeklyGoal


class TemplateBlockInline(admin.TabularInline):
    model = TemplateBlock
    extra = 1


@admin.register(TemplateWeek)
class TemplateWeekAdmin(admin.ModelAdmin):
    list_display = ["name", "is_default", "created_at"]
    inlines = [TemplateBlockInline]


class PlanBlockInline(admin.TabularInline):
    model = PlanBlock
    extra = 0


class WeeklyGoalInline(admin.TabularInline):
    model = WeeklyGoal
    extra = 0


@admin.register(PlanWeek)
class PlanWeekAdmin(admin.ModelAdmin):
    list_display = ["start_date", "source_template", "status"]
    inlines = [PlanBlockInline, WeeklyGoalInline]


@admin.register(PlanWeekReflection)
class PlanWeekReflectionAdmin(admin.ModelAdmin):
    list_display = ["week", "planning_completed_at", "review_completed_at", "energy_score"]


@admin.register(WeeklyGoal)
class WeeklyGoalAdmin(admin.ModelAdmin):
    list_display = ["title", "week", "priority", "status", "source_goal"]
    list_filter = ["priority", "status"]
