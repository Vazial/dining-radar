"""Acceptance-only Given seams; never registered by the public application."""

import json
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from dining_radar.authentication.throttle import LoginThrottle

SYNTHETIC_ACCOUNT_GROUP = "tdr-acceptance-synthetic-accounts"
ACCOUNT_REF_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


def _acceptance_only() -> None:
    if not getattr(settings, "ACCEPTANCE_TEST_SUPPORT", False):
        raise Http404


def _body(request) -> dict:
    try:
        body = json.loads(request.body)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError from error
    if not isinstance(body, dict):
        raise ValueError
    return body


def _synthetic_group() -> Group:
    return Group.objects.get_or_create(name=SYNTHETIC_ACCOUNT_GROUP)[0]


def _remove_sessions_for_user_ids(user_ids: set[str]) -> None:
    for session in Session.objects.all():
        if session.get_decoded().get("_auth_user_id") in user_ids:
            session.delete()


@csrf_exempt
@require_http_methods(["DELETE"])
def authentication_state(request):
    _acceptance_only()
    group = _synthetic_group()
    synthetic_users = list(group.user_set.all())
    _remove_sessions_for_user_ids({str(user.pk) for user in synthetic_users})
    group.user_set.clear()
    get_user_model().objects.filter(pk__in=[user.pk for user in synthetic_users]).delete()
    cache.clear()
    return HttpResponse(status=204)


@csrf_exempt
@require_http_methods(["PUT"])
def authentication_account(request, account_ref: str):
    _acceptance_only()
    if not ACCOUNT_REF_PATTERN.fullmatch(account_ref):
        return HttpResponse(status=400)

    try:
        body = _body(request)
        login_identifier = body["loginIdentifier"]
        password = body["password"]
        is_active = body["isActive"]
    except (KeyError, ValueError):
        return HttpResponse(status=400)

    if (
        set(body) != {"loginIdentifier", "password", "isActive"}
        or not isinstance(login_identifier, str)
        or not login_identifier
        or not isinstance(password, str)
        or not password
        or not isinstance(is_active, bool)
    ):
        return HttpResponse(status=400)

    group = _synthetic_group()
    user_model = get_user_model()
    account = group.user_set.filter(last_name=account_ref).first()
    duplicate_login = user_model.objects.exclude(pk=getattr(account, "pk", None)).filter(
        username=login_identifier
    )
    if duplicate_login.exists():
        return HttpResponse(status=400)

    if account is None:
        account = user_model(username=login_identifier, last_name=account_ref)
        account.save()
        group.user_set.add(account)
    else:
        account.username = login_identifier

    account.is_active = is_active
    account.set_password(password)
    account.save()
    if not is_active:
        _remove_sessions_for_user_ids({str(account.pk)})
    return HttpResponse(status=204)


@csrf_exempt
@require_http_methods(["POST"])
def login_throttle(request):
    _acceptance_only()
    try:
        body = _body(request)
        login_identifier = body["loginIdentifier"]
    except (KeyError, ValueError):
        return HttpResponse(status=400)

    if (
        set(body) != {"loginIdentifier"}
        or not isinstance(login_identifier, str)
        or not login_identifier
    ):
        return HttpResponse(status=400)

    LoginThrottle(request, login_identifier).seed_acceptance_limit()
    return HttpResponse(status=204)


@require_http_methods(["GET"])
def authentication_security_boundary(request):
    _acceptance_only()
    return JsonResponse(
        {
            "profile": "acceptance",
            "transport": "HTTP_LOCAL_ONLY",
            "sessionCookie": {
                "secure": settings.SESSION_COOKIE_SECURE,
                "httpOnly": settings.SESSION_COOKIE_HTTPONLY,
                "sameSite": settings.SESSION_COOKIE_SAMESITE,
            },
            "csrfProtectedOperations": [
                "SIGN_IN",
                "SIGN_OUT",
                "CHANGE_PASSWORD",
                "CANDIDATE_PROPOSAL",
            ],
            "credentialedArbitraryOriginCorsAllowed": False,
            "browserLocalStorageBearerTokenUsed": False,
        }
    )
