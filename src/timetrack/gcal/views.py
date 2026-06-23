import secrets

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from . import oauth
from .models import GoogleCredentials


class GCalSettingsView(View):
    def get(self, request):
        connected = oauth.is_connected()
        creds_obj = GoogleCredentials.objects.filter(pk=1).first()
        return render(
            request,
            "gcal/settings.html",
            {"connected": connected, "creds": creds_obj},
        )


class GCalConnectView(View):
    def get(self, request):
        state = secrets.token_urlsafe(16)
        request.session["gcal_oauth_state"] = state
        auth_url = oauth.get_auth_url(state=state)
        return redirect(auth_url)


class GCalCallbackView(View):
    def get(self, request):
        code = request.GET.get("code")
        if not code:
            messages.error(request, "Google OAuth failed: no code received.")
            return redirect("gcal-settings")
        try:
            oauth.exchange_code(code)
            messages.success(request, "Google Calendar connected successfully.")
        except Exception as e:
            messages.error(request, f"Google OAuth error: {e}")
        return redirect("gcal-settings")


class GCalDisconnectView(View):
    def post(self, request):
        oauth.disconnect()
        messages.success(request, "Google Calendar disconnected.")
        return redirect("gcal-settings")


class GCalCalendarPickView(View):
    def post(self, request):
        cal_id = request.POST.get("calendar_id", "primary")
        obj = GoogleCredentials.objects.filter(pk=1).first()
        if obj:
            obj.target_calendar_id = cal_id
            obj.save(update_fields=["target_calendar_id"])
        return redirect("gcal-settings")
