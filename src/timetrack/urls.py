from django.contrib import admin
from django.urls import include, path

from timetrack.core.views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("timetrack.accounts.urls")),
    path("gcal/", include("timetrack.gcal.urls")),
    path("schedule/", include("timetrack.schedule.urls")),
    path("running/", include("timetrack.plugins.running.urls")),
    path("strava/", include("timetrack.strava.urls")),
    path("healthz", healthz, name="healthz"),
    path("", include("timetrack.core.urls")),
]
