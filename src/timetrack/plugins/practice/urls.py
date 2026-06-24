from django.urls import path

from .views import PracticeGoalDeleteView, PracticeGoalListView, PracticeGoalToggleView

urlpatterns = [
    path("goals/", PracticeGoalListView.as_view(), name="practice-goals"),
    path("goals/<int:pk>/delete/", PracticeGoalDeleteView.as_view(), name="practice-goal-delete"),
    path("goals/<int:pk>/toggle/", PracticeGoalToggleView.as_view(), name="practice-goal-toggle"),
]
