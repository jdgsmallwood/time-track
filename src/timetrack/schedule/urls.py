from django.urls import path

from .views import (
    CopyWeekForwardView,
    PlanBlockCreateView,
    PlanBlockUpdateView,
    PlanWeekCurrentView,
    PlanWeekHistoryView,
    PlanWeekListView,
    PlanWeekPlanningView,
    PlanWeekReviewView,
    PlanWeekStatsView,
    PlanWeekView,
    PushToGCalView,
    TemplateBlockCreateView,
    TemplateBlockUpdateView,
    TemplateWeekDetailView,
    TemplateWeekListView,
    WeeklyTaskDeleteView,
    WeeklyTaskListView,
    WeeklyTaskToggleView,
)

urlpatterns = [
    # Templates
    path("templates/", TemplateWeekListView.as_view(), name="templates"),
    path("templates/<int:pk>/", TemplateWeekDetailView.as_view(), name="template-detail"),
    path("templates/<int:template_pk>/blocks/", TemplateBlockCreateView.as_view(), name="template-block-create"),
    path("template-blocks/<int:pk>/", TemplateBlockUpdateView.as_view(), name="template-block-update"),
    # Concrete weeks
    path("weeks/", PlanWeekListView.as_view(), name="weeks"),
    path("weeks/current/", PlanWeekCurrentView.as_view(), name="week-current"),
    path("weeks/<str:start_date>/", PlanWeekView.as_view(), name="week-view"),
    path("plan-weeks/<int:week_pk>/blocks/", PlanBlockCreateView.as_view(), name="plan-block-create"),
    path("plan-blocks/<int:pk>/", PlanBlockUpdateView.as_view(), name="plan-block-update"),
    path("plan-weeks/<int:week_pk>/stats/", PlanWeekStatsView.as_view(), name="plan-week-stats"),
    path("plan-weeks/<int:week_pk>/planning/", PlanWeekPlanningView.as_view(), name="plan-week-planning"),
    path("plan-weeks/<int:week_pk>/review/", PlanWeekReviewView.as_view(), name="plan-week-review"),
    path("plan-weeks/<int:week_pk>/push/", PushToGCalView.as_view(), name="push-gcal"),
    path("plan-weeks/<int:week_pk>/copy-forward/", CopyWeekForwardView.as_view(), name="copy-week-forward"),
    path("history/", PlanWeekHistoryView.as_view(), name="week-history"),
    # Weekly tasks
    path("weekly-tasks/", WeeklyTaskListView.as_view(), name="weekly-tasks"),
    path("weekly-tasks/<int:pk>/delete/", WeeklyTaskDeleteView.as_view(), name="weekly-task-delete"),
    path("weekly-tasks/<int:pk>/toggle/", WeeklyTaskToggleView.as_view(), name="weekly-task-toggle"),
]
