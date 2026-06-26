from datetime import date

from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from timetrack.core.models import Category
from timetrack.schedule.models import PlanBlock, PlanWeek, TemplateWeek
from timetrack.schedule.services import (
    should_show_planning_prompt,
    should_show_review_prompt,
    week_monday,
    week_stats,
)


def healthz(request):
    return JsonResponse({"status": "ok"})


class DashboardView(View):
    def get(self, request):
        today = date.today()
        monday = week_monday(today)

        today_blocks = list(
            PlanBlock.objects.filter(date=today)
            .select_related("category")
            .order_by("start_time")
        )

        this_week = PlanWeek.objects.select_related("reflection").filter(start_date=monday).first()
        this_week_stats = week_stats(this_week) if this_week else {}

        recent_pks = list(
            PlanWeek.objects.order_by("-start_date").values_list("pk", flat=True)[:8]
        )
        recent_weeks_qs = PlanWeek.objects.filter(pk__in=recent_pks).order_by("-start_date")
        recent_weeks = []
        for w in recent_weeks_qs:
            s = week_stats(w)
            recent_weeks.append({
                "week": w,
                "km_planned": s["run"]["total_planned_km"],
                "km_actual": s["run"]["total_actual_km"],
                "practice_mins": sum(
                    v["planned"] for v in s["practice"].values()
                ),
                "total_hours": s["total_hours"],
            })

        templates = TemplateWeek.objects.all()
        default_template = TemplateWeek.objects.filter(is_default=True).first()

        # Training plan context (populated by Feature 3 when active)
        active_plan = None
        current_plan_week = None
        plan_estimated_minutes = None
        try:
            from timetrack.plugins.running.models import TrainingPlan
            from timetrack.plugins.running.services import (
                estimate_week_minutes,
                get_current_plan_week,
            )
            active_plan = TrainingPlan.objects.filter(is_active=True).first()
            if active_plan:
                current_plan_week = get_current_plan_week(active_plan)
                if current_plan_week:
                    plan_estimated_minutes = estimate_week_minutes(
                        current_plan_week, active_plan
                    )
        except Exception:
            pass

        return render(
            request,
            "core/dashboard.html",
            {
                "today": today,
                "today_blocks": today_blocks,
                "this_week": this_week,
                "this_week_stats": this_week_stats,
                "planning_prompt": should_show_planning_prompt(this_week),
                "review_prompt": should_show_review_prompt(this_week),
                "recent_weeks": recent_weeks,
                "templates": templates,
                "default_template": default_template,
                "active_plan": active_plan,
                "current_plan_week": current_plan_week,
                "plan_estimated_minutes": plan_estimated_minutes,
            },
        )


class CategoryListView(View):
    def get(self, request):
        categories = Category.objects.all()
        return render(request, "core/categories.html", {"categories": categories})

    def post(self, request):
        from .forms import CategoryForm

        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
        return render(
            request, "core/categories.html", {"categories": Category.objects.all(), "form": form}
        )


class CategoryUpdateView(View):
    def post(self, request, pk):
        from django.shortcuts import redirect
        from .forms import CategoryForm

        cat = Category.objects.get(pk=pk)
        form = CategoryForm(request.POST, instance=cat)
        if form.is_valid():
            form.save()
        return redirect("/settings/categories/")

    def delete(self, request, pk):
        Category.objects.filter(pk=pk).delete()
        return render(
            request, "core/partials/category_list.html", {"categories": Category.objects.all()}
        )
