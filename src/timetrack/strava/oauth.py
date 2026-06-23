"""
Strava OAuth2 helpers — mirrors the pattern in gcal/oauth.py.

Required Django settings:
  STRAVA_CLIENT_ID
  STRAVA_CLIENT_SECRET
  STRAVA_REDIRECT_URI  (e.g. http://localhost:8000/strava/callback/)
"""
import time

import requests
from django.conf import settings

from .models import StravaCredentials

_AUTH_URL = "https://www.strava.com/oauth/authorize"
_TOKEN_URL = "https://www.strava.com/oauth/token"


def get_auth_url(state: str = "") -> str:
    params = {
        "client_id": settings.STRAVA_CLIENT_ID,
        "redirect_uri": settings.STRAVA_REDIRECT_URI,
        "response_type": "code",
        "approval_prompt": "auto",
        "scope": "activity:read_all",
        "state": state,
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items() if v)
    return f"{_AUTH_URL}?{qs}"


def exchange_code(code: str) -> StravaCredentials:
    """Exchange an authorization code for tokens and persist them."""
    resp = requests.post(
        _TOKEN_URL,
        data={
            "client_id": settings.STRAVA_CLIENT_ID,
            "client_secret": settings.STRAVA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    athlete = data.get("athlete", {})
    creds, _ = StravaCredentials.objects.update_or_create(
        pk=1,
        defaults={
            "athlete_id": data["athlete"]["id"],
            "athlete_name": f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_at": data["expires_at"],
        },
    )
    return creds


def _refresh_token(creds: StravaCredentials) -> StravaCredentials:
    resp = requests.post(
        _TOKEN_URL,
        data={
            "client_id": settings.STRAVA_CLIENT_ID,
            "client_secret": settings.STRAVA_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": creds.refresh_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    creds.access_token = data["access_token"]
    creds.refresh_token = data["refresh_token"]
    creds.expires_at = data["expires_at"]
    creds.save(update_fields=["access_token", "refresh_token", "expires_at", "updated_at"])
    return creds


def get_access_token() -> str:
    """Return a valid access token, refreshing if needed."""
    try:
        creds = StravaCredentials.objects.get(pk=1)
    except StravaCredentials.DoesNotExist:
        raise RuntimeError("Strava not connected.")
    if creds.expires_at < int(time.time()) + 60:
        creds = _refresh_token(creds)
    return creds.access_token


def is_connected() -> bool:
    return StravaCredentials.objects.filter(pk=1).exists()


def get_athlete_name() -> str:
    try:
        return StravaCredentials.objects.get(pk=1).athlete_name or "Connected"
    except StravaCredentials.DoesNotExist:
        return ""


def disconnect() -> None:
    StravaCredentials.objects.filter(pk=1).delete()
