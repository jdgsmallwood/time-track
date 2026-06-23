from django.urls import path

from .views import (
    StravaCallbackView,
    StravaConnectView,
    StravaDisconnectView,
    StravaSettingsView,
    StravaWeekSyncView,
)

urlpatterns = [
    path("settings/", StravaSettingsView.as_view(), name="strava-settings"),
    path("connect/", StravaConnectView.as_view(), name="strava-connect"),
    path("callback/", StravaCallbackView.as_view(), name="strava-callback"),
    path("disconnect/", StravaDisconnectView.as_view(), name="strava-disconnect"),
    path("sync-week/<int:week_pk>/", StravaWeekSyncView.as_view(), name="strava-week-sync"),
]
