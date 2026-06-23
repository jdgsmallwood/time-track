from django.conf import settings
from django.shortcuts import redirect


PUBLIC_PATHS = {settings.LOGIN_URL, "/healthz", "/admin/"}


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        is_public = any(path.startswith(p) for p in PUBLIC_PATHS)
        if not is_public and not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={path}")
        return self.get_response(request)
