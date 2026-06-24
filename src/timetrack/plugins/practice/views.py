from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .forms import PracticeGoalForm
from .models import PracticeGoal


class PracticeGoalListView(View):
    def get(self, request):
        goals = PracticeGoal.objects.all()
        form = PracticeGoalForm()
        return render(request, "practice/goals.html", {"goals": goals, "form": form})

    def post(self, request):
        form = PracticeGoalForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("practice-goals")
        goals = PracticeGoal.objects.all()
        return render(request, "practice/goals.html", {"goals": goals, "form": form})


class PracticeGoalDeleteView(View):
    def post(self, request, pk):
        get_object_or_404(PracticeGoal, pk=pk).delete()
        return redirect("practice-goals")


class PracticeGoalToggleView(View):
    def post(self, request, pk):
        goal = get_object_or_404(PracticeGoal, pk=pk)
        goal.is_active = not goal.is_active
        goal.save(update_fields=["is_active"])
        return redirect("practice-goals")
