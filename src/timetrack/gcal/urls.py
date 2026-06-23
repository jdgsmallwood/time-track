from django.urls import path

from .views import GCalCallbackView, GCalCalendarPickView, GCalConnectView, GCalDisconnectView, GCalSettingsView

urlpatterns = [
    path("settings/", GCalSettingsView.as_view(), name="gcal-settings"),
    path("connect/", GCalConnectView.as_view(), name="gcal-connect"),
    path("oauth/callback/", GCalCallbackView.as_view(), name="gcal-callback"),
    path("disconnect/", GCalDisconnectView.as_view(), name="gcal-disconnect"),
    path("calendar-pick/", GCalCalendarPickView.as_view(), name="gcal-calendar-pick"),
]
