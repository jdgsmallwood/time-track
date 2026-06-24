from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .forms import PracticeGoalForm
from .models import PracticeGoal


class PracticeGoalListView(View):
    def get(self, request):
        goals = PracticeGoal.objects.select_related("category").all()
        form = PracticeGoalForm()
        return render(request, "practice/goals.html", {"goals": goals, "form": form})

    def post(self, request):
        form = PracticeGoalForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("practice-goals")
        goals = PracticeGoal.objects.select_related("category").all()
        return render(request, "practice/goals.html", {"goals": goals, "form": form})


class PracticeGoalEditView(View):
    def get(self, request, pk):
        goal = get_object_or_404(PracticeGoal, pk=pk)
        form = PracticeGoalForm(instance=goal)
        return render(request, "practice/partials/goal_edit_row.html", {"goal": goal, "form": form})

    def post(self, request, pk):
        goal = get_object_or_404(PracticeGoal, pk=pk)
        form = PracticeGoalForm(request.POST, instance=goal)
        if form.is_valid():
            goal = form.save()
            return render(request, "practice/partials/goal_row.html", {"goal": goal})
        return render(request, "practice/partials/goal_edit_row.html", {"goal": goal, "form": form})


class PracticeGoalRowView(View):
    """Returns just the display row — used by Cancel in the edit form."""
    def get(self, request, pk):
        goal = get_object_or_404(PracticeGoal.objects.select_related("category"), pk=pk)
        return render(request, "practice/partials/goal_row.html", {"goal": goal})


class PracticeGoalDeleteView(View):
    def post(self, request, pk):
        get_object_or_404(PracticeGoal, pk=pk).delete()
        return redirect("practice-goals")


class PracticeGoalToggleView(View):
    def post(self, request, pk):
        goal = get_object_or_404(PracticeGoal, pk=pk)
        goal.is_active = not goal.is_active
        goal.save(update_fields=["is_active"])
        if request.headers.get("HX-Request"):
            goal.refresh_from_db()
            return render(request, "practice/partials/goal_row.html", {"goal": goal})
        return redirect("practice-goals")
