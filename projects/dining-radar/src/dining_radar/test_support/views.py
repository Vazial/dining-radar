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
from dining_radar.gathering import services as gathering_services
from dining_radar.recommendation.pipeline import Origin
from dining_radar.suggestions import acceptance_state

SYNTHETIC_ACCOUNT_GROUP = "tdr-acceptance-synthetic-accounts"
ACCOUNT_REF_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
CANDIDATE_PROPOSAL_MODES = {mode.value for mode in acceptance_state.AcceptanceCandidateProposalMode}
_SEARCH_ORIGIN_KEYS = {"latitude", "longitude"}


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


def _parse_search_origin(raw: object) -> Origin | None:
    """Parse ``CandidateProposalAcceptanceState.searchOrigin`` (1.4.0).

    Returns ``None`` for an omitted or explicitly ``null`` value (the
    default, unpinned behavior). Raises ``ValueError`` for anything that
    does not match the contract's schema exactly: an object with exactly
    ``latitude``/``longitude`` numeric properties, each within its declared
    range.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != _SEARCH_ORIGIN_KEYS:
        raise ValueError
    latitude = raw["latitude"]
    longitude = raw["longitude"]
    if (
        not isinstance(latitude, int | float)
        or isinstance(latitude, bool)
        or not isinstance(longitude, int | float)
        or isinstance(longitude, bool)
        or not (-90 <= latitude <= 90)
        or not (-180 <= longitude <= 180)
    ):
        raise ValueError
    return Origin(latitude=float(latitude), longitude=float(longitude))


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


@csrf_exempt
@require_http_methods(["PUT", "DELETE"])
def candidate_proposal_state(request):
    """Selects or resets the synthetic state the next public API call observes.

    Implements ``CandidateProposalAcceptanceState`` from
    ``contracts/test-support-api.yaml``, including the ``randomSeed`` property
    adr/0023 decision 4 adds to pin the server's random pool-sampling source.
    """
    _acceptance_only()

    if request.method == "DELETE":
        acceptance_state.reset_mode()
        return HttpResponse(status=204)

    try:
        body = _body(request)
        mode = body["mode"]
    except (KeyError, ValueError):
        return HttpResponse(status=400)

    if set(body) - {"mode", "randomSeed", "searchOrigin"} or mode not in CANDIDATE_PROPOSAL_MODES:
        return HttpResponse(status=400)

    random_seed = body.get("randomSeed")
    if random_seed is not None and (
        not isinstance(random_seed, int) or isinstance(random_seed, bool)
    ):
        return HttpResponse(status=400)

    try:
        search_origin = _parse_search_origin(body.get("searchOrigin"))
    except ValueError:
        return HttpResponse(status=400)

    acceptance_state.set_mode(
        acceptance_state.AcceptanceCandidateProposalMode(mode), random_seed, search_origin
    )
    return HttpResponse(status=204)


@csrf_exempt
@require_http_methods(["DELETE"])
def gathering_scheduling_state(request):
    """``resetGatheringSchedulingAcceptanceState`` (test-support-api.yaml 1.5.0)."""
    _acceptance_only()
    gathering_services.reset_gathering_scheduling_state()
    return HttpResponse(status=204)


def _gathering_participant_link_token(request) -> str | None:
    try:
        body = _body(request)
        token = body["token"]
    except (KeyError, ValueError):
        return None
    if set(body) != {"token"} or not isinstance(token, str) or not token:
        return None
    return token


@csrf_exempt
@require_http_methods(["POST"])
def gathering_seed_expired_participant_link(request):
    """``seedExpiredParticipantLink`` (test-support-api.yaml 1.5.0)."""
    _acceptance_only()
    token = _gathering_participant_link_token(request)
    if token is None:
        return HttpResponse(status=400)
    try:
        gathering_services.seed_expired_participant_link(token)
    except gathering_services.LinkNotFoundError:
        return HttpResponse(status=404)
    return HttpResponse(status=204)


@csrf_exempt
@require_http_methods(["POST"])
def gathering_seed_rate_limited_participant_link(request):
    """``seedRateLimitedParticipantLink`` (test-support-api.yaml 1.5.0)."""
    _acceptance_only()
    token = _gathering_participant_link_token(request)
    if token is None:
        return HttpResponse(status=400)
    try:
        gathering_services.seed_rate_limited_participant_link(token)
    except gathering_services.LinkNotFoundError:
        return HttpResponse(status=404)
    return HttpResponse(status=204)


@csrf_exempt
@require_http_methods(["POST"])
def gathering_seed_participant_link_server_error(request):
    """``seedParticipantLinkServerError`` (test-support-api.yaml 1.5.4, adr/0047)."""
    _acceptance_only()
    token = _gathering_participant_link_token(request)
    if token is None:
        return HttpResponse(status=400)
    try:
        gathering_services.seed_participant_link_server_error(token)
    except gathering_services.LinkNotFoundError:
        return HttpResponse(status=404)
    return HttpResponse(status=204)
