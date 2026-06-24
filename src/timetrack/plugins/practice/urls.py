from django.urls import path

from .views import (
    PracticeGoalDeleteView,
    PracticeGoalEditView,
    PracticeGoalListView,
    PracticeGoalRowView,
    PracticeGoalToggleView,
)

urlpatterns = [
    path("goals/", PracticeGoalListView.as_view(), name="practice-goals"),
    path("goals/<int:pk>/edit/", PracticeGoalEditView.as_view(), name="practice-goal-edit"),
    path("goals/<int:pk>/row/", PracticeGoalRowView.as_view(), name="practice-goal-row"),
    path("goals/<int:pk>/delete/", PracticeGoalDeleteView.as_view(), name="practice-goal-delete"),
    path("goals/<int:pk>/toggle/", PracticeGoalToggleView.as_view(), name="practice-goal-toggle"),
]
