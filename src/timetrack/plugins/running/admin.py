from django.contrib import admin

from .models import RunSession


@admin.register(RunSession)
class RunSessionAdmin(admin.ModelAdmin):
    list_display = ["run_type", "planned_km", "actual_km", "template_block", "plan_block"]
