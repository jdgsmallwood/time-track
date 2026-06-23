from django.contrib import admin

from .models import PlanBlock, PlanWeek, TemplateBlock, TemplateWeek


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


@admin.register(PlanWeek)
class PlanWeekAdmin(admin.ModelAdmin):
    list_display = ["start_date", "source_template", "status"]
    inlines = [PlanBlockInline]
