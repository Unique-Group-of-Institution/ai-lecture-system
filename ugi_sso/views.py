from urllib.parse import urlparse

import jwt
from django.conf import settings
from django.contrib.auth import login
from django.db import IntegrityError, transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

from .models import ConsumedLaunchToken, ExternalIdentityLink


PROVIDER = "ugi-crm"
ISSUER = "ugi-crm"
AUDIENCE = "ai-lecture-system"


def _safe_next(value: str | None) -> str:
    if not value:
        return settings.LOGIN_REDIRECT_URL
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/") or value.startswith("//"):
        return settings.LOGIN_REDIRECT_URL
    return value


@csrf_exempt
def consume_ugi_launch(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    token = request.POST.get("token", "").strip()
    if not token:
        return HttpResponseBadRequest("Missing launch token")

    secret = getattr(settings, "UGI_CRM_SSO_SIGNING_SECRET", "")
    if not secret:
        return HttpResponseForbidden("Shared login is not configured")

    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["sub", "jti", "iat", "exp", "iss", "aud"]},
        )
    except jwt.PyJWTError:
        return HttpResponseForbidden("Invalid launch token")

    subject = str(claims.get("sub", "")).strip()
    jti = str(claims.get("jti", "")).strip()
    if not subject or not jti:
        return HttpResponseForbidden("Invalid launch token")

    link = (
        ExternalIdentityLink.objects.select_related("user")
        .filter(provider=PROVIDER, subject=subject, active=True)
        .first()
    )
    if link is None or not link.user.is_active:
        return HttpResponseForbidden("No active LMS identity link")

    try:
        with transaction.atomic():
            ConsumedLaunchToken.objects.create(
                provider=PROVIDER,
                jti=jti,
                subject=subject,
                consumed_by=link.user,
            )
    except IntegrityError:
        return HttpResponseForbidden("Launch token has already been used")

    login(request, link.user)
    return redirect(_safe_next(request.POST.get("next")))
