from django.urls import path

from .views import (
    TrainingPlanActivateView,
    TrainingPlanDetailView,
    TrainingPlanImportView,
    TrainingPlanListView,
)

urlpatterns = [
    path("training-plans/", TrainingPlanListView.as_view(), name="training-plan-list"),
    path("training-plans/<int:pk>/", TrainingPlanDetailView.as_view(), name="training-plan-detail"),
    path("training-plans/import/", TrainingPlanImportView.as_view(), name="training-plan-import"),
    path("training-plans/<int:pk>/activate/", TrainingPlanActivateView.as_view(), name="training-plan-activate"),
]
