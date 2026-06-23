import secrets

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from timetrack.schedule.models import PlanWeek

from . import oauth
from .sync import sync_week_activities


class StravaSettingsView(View):
    def get(self, request):
        connected = oauth.is_connected()
        athlete_name = oauth.get_athlete_name() if connected else ""
        return render(
            request,
            "strava/settings.html",
            {"connected": connected, "athlete_name": athlete_name},
        )


class StravaConnectView(View):
    def get(self, request):
        state = secrets.token_urlsafe(16)
        request.session["strava_oauth_state"] = state
        return redirect(oauth.get_auth_url(state=state))


class StravaCallbackView(View):
    def get(self, request):
        code = request.GET.get("code")
        error = request.GET.get("error")
        if error or not code:
            messages.error(request, f"Strava connection failed: {error or 'no code'}")
            return redirect("strava-settings")
        try:
            oauth.exchange_code(code)
            messages.success(request, "Strava connected successfully.")
        except Exception as e:
            messages.error(request, f"Strava connection error: {e}")
        return redirect("strava-settings")


class StravaDisconnectView(View):
    def post(self, request):
        oauth.disconnect()
        messages.success(request, "Strava disconnected.")
        return redirect("strava-settings")


class StravaWeekSyncView(View):
    def post(self, request, week_pk):
        week = get_object_or_404(PlanWeek, pk=week_pk)
        try:
            result = sync_week_activities(week)
            msg = f"Synced from Strava: {result['matched']} matched, {result['unmatched']} unmatched."
            return HttpResponse(f'<p class="text-sm text-green-700">{msg}</p>')
        except Exception as e:
            return HttpResponse(f'<p class="text-sm text-red-600">Strava sync error: {e}</p>')
