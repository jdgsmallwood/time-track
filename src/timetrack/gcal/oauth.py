from django.conf import settings
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from .models import GoogleCredentials


def _build_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_OAUTH_REDIRECT_URI],
        }
    }
    flow = Flow.from_client_config(
        client_config,
        scopes=settings.GOOGLE_OAUTH_SCOPES,
        redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI,
    )
    return flow


def get_auth_url(state: str = "") -> str:
    flow = _build_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",
    )
    return auth_url


def exchange_code(code: str) -> GoogleCredentials:
    flow = _build_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    obj, _ = GoogleCredentials.objects.get_or_create(pk=1)
    obj.token = creds.token
    obj.refresh_token = creds.refresh_token or obj.refresh_token
    obj.token_uri = creds.token_uri
    obj.client_id = creds.client_id
    obj.client_secret = creds.client_secret
    obj.scopes = " ".join(creds.scopes or [])
    obj.expiry = creds.expiry
    obj.save()
    return obj


def get_credentials() -> Credentials | None:
    obj = GoogleCredentials.objects.filter(pk=1).first()
    if not obj:
        return None
    creds = Credentials(
        token=obj.token,
        refresh_token=obj.refresh_token,
        token_uri=obj.token_uri,
        client_id=obj.client_id,
        client_secret=obj.client_secret,
        scopes=obj.scopes.split(),
    )
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        obj.token = creds.token
        obj.expiry = creds.expiry
        obj.save(update_fields=["token", "expiry"])
    return creds


def is_connected() -> bool:
    return GoogleCredentials.objects.filter(pk=1).exists()


def disconnect() -> None:
    GoogleCredentials.objects.filter(pk=1).delete()
