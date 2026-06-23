from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .models import TrainingPlan
from .services import estimate_week_minutes, import_plan_from_csv


class TrainingPlanListView(View):
    def get(self, request):
        plans = TrainingPlan.objects.prefetch_related("weeks").all()
        return render(request, "running/plan_list.html", {"plans": plans})


def _fmt_pace(secs: int) -> str:
    return f"{secs // 60}:{secs % 60:02d}/km"


class TrainingPlanDetailView(View):
    def get(self, request, pk):
        plan = get_object_or_404(TrainingPlan, pk=pk)
        weeks = plan.weeks.prefetch_related("sessions").all()
        week_data = [
            {
                "week": w,
                "sessions": list(w.sessions.all()),
                "estimated_minutes": estimate_week_minutes(w, plan),
            }
            for w in weeks
        ]
        pace_zones = {
            "Easy": _fmt_pace(plan.pace_easy_sec),
            "Tempo": _fmt_pace(plan.pace_tempo_sec),
            "Intervals": _fmt_pace(plan.pace_interval_sec),
            "Long": _fmt_pace(plan.pace_long_sec),
            "Recovery": _fmt_pace(plan.pace_recovery_sec),
        }
        return render(
            request, "running/plan_detail.html",
            {"plan": plan, "week_data": week_data, "pace_zones": pace_zones},
        )

    def delete(self, request, pk):
        TrainingPlan.objects.filter(pk=pk).delete()
        return redirect("training-plan-list")


class TrainingPlanImportView(View):
    def post(self, request):
        csv_text = ""
        if "csv_file" in request.FILES:
            csv_text = request.FILES["csv_file"].read().decode("utf-8")
        elif "csv_text" in request.POST:
            csv_text = request.POST["csv_text"]

        if not csv_text.strip():
            messages.error(request, "No CSV data provided.")
            return redirect("training-plan-list")

        try:
            plan = import_plan_from_csv(csv_text)
            messages.success(
                request,
                f"Imported '{plan.name}' — {plan.total_weeks} weeks.",
            )
            return redirect("training-plan-detail", pk=plan.pk)
        except ValueError as e:
            messages.error(request, f"Import failed: {e}")
            return redirect("training-plan-list")


class TrainingPlanActivateView(View):
    def post(self, request, pk):
        plan = get_object_or_404(TrainingPlan, pk=pk)
        plan.is_active = True
        plan.save()
        messages.success(request, f"'{plan.name}' is now the active training plan.")
        return redirect("training-plan-detail", pk=pk)
