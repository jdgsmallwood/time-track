from django.urls import path

from .views import CategoryListView, CategoryUpdateView, DashboardView

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("settings/categories/", CategoryListView.as_view(), name="categories"),
    path("settings/categories/<int:pk>/", CategoryUpdateView.as_view(), name="category-update"),
]
