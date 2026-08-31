"""Browser- and API-facing endpoints for ``contracts/gathering-scheduling-api.yaml``.

Per ``ARCHITECTURE.md``'s module-boundary convention (``dining_radar.web``'s
own division of labor), this module is a thin request/response translation
layer: every phase-transition rule, denominator computation, and access
check lives in ``dining_radar.gathering.services``.

**Interpretation note (developer discretion, not a contract conflict):**
several write operations in ``gathering-scheduling-api.yaml`` (e.g.
``addCandidateDate``, ``issueParticipantLinks``, ``recopyParticipantLink``,
``revokeParticipantLink``, ``confirmCandidateDate``, ``setScheduleResponse``,
``setParticipantDisplayName``) document no ``400`` response for a malformed
request body or a failed CSRF check, even though ``createGathering`` does
(``RequestRejected``) and ``ProblemResponse.code``'s shared enum already
carries ``REQUEST_REJECTED`` for the whole file. Every real control this
contract's browser interface defines only ever sends a well-formed body over
a closed vocabulary (mirrors ``dining_radar.web.views``'s identical, already
accepted precedent for filling candidate-search-api.yaml's own equivalent
gaps), so a malformed request or a forged cross-site submission is
unreachable through the approved UI and exists only as defense-in-depth.
This module answers
every such case the same way, uniformly, with ``400 REQUEST_REJECTED`` --
the same code ``createGathering`` already defines -- rather than inventing a
new code or silently accepting the malformed input.

Similarly, ``setScheduleResponse`` documents only ``LINK_NOT_FOUND`` (404),
not ``CANDIDATE_DATE_NOT_FOUND``, for its path; the browser only ever sends a
``candidateDateId`` the current ``ParticipantView`` itself returned, so an
unknown id is likewise unreachable through the approved UI. This module
reuses the already-defined ``CANDIDATE_DATE_NOT_FOUND`` code (404) for that
case rather than conflating it with ``LINK_NOT_FOUND``.
"""

from __future__ import annotations

import json
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from . import services
from .models import ScheduleResponseStatus
from .serializers import (
    serialize_gathering,
    serialize_issued_participant_link,
    serialize_open_shop_preview,
    serialize_participant_link_summary,
    serialize_participant_view,
)

_SCHEDULE_RESPONSE_STATUSES = frozenset(status.value for status in ScheduleResponseStatus)
_MAX_ISSUE_COUNT = 200
_RATE_LIMIT_RETRY_AFTER_SECONDS = 30


# --- shared helpers ---------------------------------------------------------


class MalformedRequestError(ValueError):
    """The request body did not match this operation's schema."""


def _problem(status: int, code: str, message: str) -> JsonResponse:
    return JsonResponse({"code": code, "message": message}, status=status)


_AUTHENTICATION_REQUIRED = (
    401,
    "AUTHENTICATION_REQUIRED",
    "Sign in is required to manage this gathering.",
)
_REQUEST_REJECTED = (
    400,
    "REQUEST_REJECTED",
    "The request could not be accepted. Refresh the page and try again.",
)
_GATHERING_NOT_FOUND = (404, "GATHERING_NOT_FOUND", "This gathering could not be found.")
_CANDIDATE_DATE_NOT_FOUND = (
    404,
    "CANDIDATE_DATE_NOT_FOUND",
    "This candidate date could not be found.",
)
_GATHERING_NOT_IN_SCHEDULING_PHASE = (
    409,
    "GATHERING_NOT_IN_SCHEDULING_PHASE",
    "This gathering has already moved past scheduling.",
)
_PARTICIPANT_LINK_NOT_FOUND = (
    404,
    "PARTICIPANT_LINK_NOT_FOUND",
    "This participant link could not be found.",
)
_PARTICIPANT_LINK_ALREADY_ANSWERED = (
    409,
    "PARTICIPANT_LINK_ALREADY_ANSWERED",
    "This link has already been answered and cannot be revoked.",
)
_PARTICIPANT_LINK_REVOKED = (
    409,
    "PARTICIPANT_LINK_REVOKED",
    "This link has already been revoked.",
)
_LINK_NOT_FOUND = (404, "LINK_NOT_FOUND", "This link is not valid.")
_LINK_EXPIRED = (
    410,
    "LINK_EXPIRED",
    "This link has expired. Please ask the organizer for a new one.",
)
_LINK_REVOKED = (
    410,
    "LINK_REVOKED",
    "This link is no longer valid. Please ask the organizer for a new one.",
)
_LINK_RATE_LIMITED = (
    429,
    "LINK_RATE_LIMITED",
    "Too many requests were made with this link. Please try again shortly.",
)
_GATHERING_FINALIZED = (409, "GATHERING_FINALIZED", "This gathering is already finalized.")


def _organizer_error_response(error: Exception) -> JsonResponse:
    if isinstance(error, services.GatheringNotFoundError):
        return _problem(*_GATHERING_NOT_FOUND)
    if isinstance(error, services.CandidateDateNotFoundError):
        return _problem(*_CANDIDATE_DATE_NOT_FOUND)
    if isinstance(error, services.GatheringNotInSchedulingPhaseError):
        return _problem(*_GATHERING_NOT_IN_SCHEDULING_PHASE)
    if isinstance(error, services.ParticipantLinkNotFoundError):
        return _problem(*_PARTICIPANT_LINK_NOT_FOUND)
    if isinstance(error, services.ParticipantLinkAlreadyAnsweredError):
        return _problem(*_PARTICIPANT_LINK_ALREADY_ANSWERED)
    if isinstance(error, services.ParticipantLinkRevokedError):
        return _problem(*_PARTICIPANT_LINK_REVOKED)
    raise error


def _participant_link_error_response(error: Exception) -> JsonResponse:
    if isinstance(error, services.LinkNotFoundError):
        return _problem(*_LINK_NOT_FOUND)
    if isinstance(error, services.LinkExpiredError):
        return _problem(*_LINK_EXPIRED)
    if isinstance(error, services.LinkRevokedError):
        return _problem(*_LINK_REVOKED)
    if isinstance(error, services.LinkRateLimitedError):
        response = _problem(*_LINK_RATE_LIMITED)
        response["Retry-After"] = str(_RATE_LIMIT_RETRY_AFTER_SECONDS)
        return response
    if isinstance(error, services.GatheringFinalizedError):
        return _problem(*_GATHERING_FINALIZED)
    if isinstance(error, services.CandidateDateNotFoundError):
        return _problem(*_CANDIDATE_DATE_NOT_FOUND)
    raise error


def _csrf_probe(request):
    return None


def _csrf_failed(request) -> bool:
    rejection = CsrfViewMiddleware(lambda _request: None).process_view(request, _csrf_probe, (), {})
    return rejection is not None


def _read_body(request) -> dict:
    try:
        body = json.loads(request.body or b"{}")
    except (TypeError, ValueError) as error:
        raise MalformedRequestError from error
    if not isinstance(body, dict):
        raise MalformedRequestError
    return body


def _parse_start_at(raw: object) -> datetime:
    if not isinstance(raw, str) or not raw:
        raise MalformedRequestError
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as error:
        raise MalformedRequestError from error
    if parsed.tzinfo is None:
        raise MalformedRequestError
    return parsed


def _parse_title(raw: object) -> str:
    if not isinstance(raw, str) or not (1 <= len(raw) <= 200):
        raise MalformedRequestError
    return raw


def _parse_candidate_dates(raw: object) -> list[datetime]:
    if not isinstance(raw, list) or not raw:
        raise MalformedRequestError
    parsed = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"startAt"}:
            raise MalformedRequestError
        parsed.append(_parse_start_at(item["startAt"]))
    return parsed


def _parse_count(raw: object) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or not (1 <= raw <= _MAX_ISSUE_COUNT):
        raise MalformedRequestError
    return raw


def _parse_display_name(raw: object) -> str:
    if not isinstance(raw, str) or not (1 <= len(raw) <= 100):
        raise MalformedRequestError
    return raw


def _parse_status(raw: object) -> str:
    if raw not in _SCHEDULE_RESPONSE_STATUSES:
        raise MalformedRequestError
    return raw


# --- organizer JSON API (organizerSession + CSRF) ---------------------------


@csrf_exempt
@require_http_methods(["POST"])
def gatherings(request):
    """``POST /gatherings``: ``createGathering``."""
    if not request.user.is_authenticated:
        return _problem(*_AUTHENTICATION_REQUIRED)
    if _csrf_failed(request):
        return _problem(*_REQUEST_REJECTED)
    try:
        body = _read_body(request)
        if set(body) != {"title", "candidateDates"}:
            raise MalformedRequestError
        title = _parse_title(body["title"])
        candidate_date_start_ats = _parse_candidate_dates(body["candidateDates"])
    except MalformedRequestError:
        return _problem(*_REQUEST_REJECTED)

    gathering = services.create_gathering(request.user, title, candidate_date_start_ats)
    return JsonResponse(serialize_gathering(gathering), status=201)


@require_GET
def gathering_detail(request, gathering_id):
    """``GET /gatherings/{gatheringId}``: ``getGathering``."""
    if not request.user.is_authenticated:
        return _problem(*_AUTHENTICATION_REQUIRED)
    try:
        gathering = services.get_gathering(request.user, gathering_id)
    except services.GatheringNotFoundError as error:
        return _organizer_error_response(error)
    return JsonResponse(serialize_gathering(gathering), status=200)


@csrf_exempt
@require_http_methods(["POST"])
def candidate_dates(request, gathering_id):
    """``POST /gatherings/{gatheringId}/candidate-dates``: ``addCandidateDate``."""
    if not request.user.is_authenticated:
        return _problem(*_AUTHENTICATION_REQUIRED)
    if _csrf_failed(request):
        return _problem(*_REQUEST_REJECTED)
    try:
        body = _read_body(request)
        if set(body) != {"startAt"}:
            raise MalformedRequestError
        start_at = _parse_start_at(body["startAt"])
    except MalformedRequestError:
        return _problem(*_REQUEST_REJECTED)

    try:
        gathering, _candidate_date = services.add_candidate_date(
            request.user, gathering_id, start_at
        )
    except (services.GatheringNotFoundError, services.GatheringNotInSchedulingPhaseError) as error:
        return _organizer_error_response(error)
    return JsonResponse(serialize_gathering(gathering), status=201)


@require_GET
def open_shop_preview(request, gathering_id, candidate_date_id):
    """``GET .../candidate-dates/{candidateDateId}/open-shop-preview``."""
    if not request.user.is_authenticated:
        return _problem(*_AUTHENTICATION_REQUIRED)
    try:
        candidate_date, population = services.preview_open_shops_for_candidate_date(
            request.user, gathering_id, candidate_date_id
        )
    except (services.GatheringNotFoundError, services.CandidateDateNotFoundError) as error:
        return _organizer_error_response(error)
    return JsonResponse(serialize_open_shop_preview(candidate_date, population), status=200)


@csrf_exempt
@require_http_methods(["POST", "GET"])
def participant_links(request, gathering_id):
    """``POST``/``GET /gatherings/{gatheringId}/participant-links``."""
    if not request.user.is_authenticated:
        return _problem(*_AUTHENTICATION_REQUIRED)

    if request.method == "GET":
        try:
            _gathering, links = services.list_participant_links(request.user, gathering_id)
        except services.GatheringNotFoundError as error:
            return _organizer_error_response(error)
        return JsonResponse(
            {"participantLinks": [serialize_participant_link_summary(link) for link in links]},
            status=200,
        )

    if _csrf_failed(request):
        return _problem(*_REQUEST_REJECTED)
    try:
        body = _read_body(request)
        if set(body) != {"count"}:
            raise MalformedRequestError
        count = _parse_count(body["count"])
    except MalformedRequestError:
        return _problem(*_REQUEST_REJECTED)

    try:
        gathering, links = services.issue_participant_links(request.user, gathering_id, count)
    except services.GatheringNotFoundError as error:
        return _organizer_error_response(error)
    return JsonResponse(
        {
            "issuedLinks": [serialize_issued_participant_link(request, link) for link in links],
            "totalIssuedParticipantLinks": gathering.total_issued_participant_links,
            "activeParticipantLinkCount": gathering.active_participant_link_count,
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["POST"])
def recopy_participant_link(request, gathering_id, link_id):
    """``POST .../participant-links/{linkId}/recopy``."""
    if not request.user.is_authenticated:
        return _problem(*_AUTHENTICATION_REQUIRED)
    if _csrf_failed(request):
        return _problem(*_REQUEST_REJECTED)
    try:
        link = services.recopy_participant_link(request.user, gathering_id, link_id)
    except (
        services.GatheringNotFoundError,
        services.ParticipantLinkNotFoundError,
        services.ParticipantLinkRevokedError,
    ) as error:
        return _organizer_error_response(error)
    return JsonResponse(serialize_issued_participant_link(request, link), status=200)


@csrf_exempt
@require_http_methods(["POST"])
def revoke_participant_link(request, gathering_id, link_id):
    """``POST .../participant-links/{linkId}/revoke``."""
    if not request.user.is_authenticated:
        return _problem(*_AUTHENTICATION_REQUIRED)
    if _csrf_failed(request):
        return _problem(*_REQUEST_REJECTED)
    try:
        gathering, link = services.revoke_participant_link(request.user, gathering_id, link_id)
    except (
        services.GatheringNotFoundError,
        services.ParticipantLinkNotFoundError,
        services.ParticipantLinkAlreadyAnsweredError,
    ) as error:
        return _organizer_error_response(error)
    return JsonResponse(
        {
            "participantLink": serialize_participant_link_summary(link),
            "gathering": serialize_gathering(gathering),
        },
        status=200,
    )


@csrf_exempt
@require_http_methods(["POST"])
def confirm_date(request, gathering_id):
    """``POST /gatherings/{gatheringId}/confirm-date``: ``confirmCandidateDate``."""
    if not request.user.is_authenticated:
        return _problem(*_AUTHENTICATION_REQUIRED)
    if _csrf_failed(request):
        return _problem(*_REQUEST_REJECTED)
    try:
        body = _read_body(request)
        if set(body) != {"candidateDateId"}:
            raise MalformedRequestError
        candidate_date_id = body["candidateDateId"]
        if not isinstance(candidate_date_id, str) or not candidate_date_id:
            raise MalformedRequestError
    except MalformedRequestError:
        return _problem(*_REQUEST_REJECTED)

    try:
        gathering = services.confirm_candidate_date(request.user, gathering_id, candidate_date_id)
    except (
        services.GatheringNotFoundError,
        services.GatheringNotInSchedulingPhaseError,
        services.CandidateDateNotFoundError,
    ) as error:
        return _organizer_error_response(error)
    return JsonResponse(serialize_gathering(gathering), status=200)


# --- participant JSON API (signed token, no session, no CSRF) ---------------


@require_GET
def participant_view(request, token):
    """``GET /participant-links/{token}``: ``getParticipantView``."""
    try:
        link = services.get_participant_view(token)
    except (
        services.LinkNotFoundError,
        services.LinkExpiredError,
        services.LinkRevokedError,
        services.LinkRateLimitedError,
    ) as error:
        return _participant_link_error_response(error)
    return JsonResponse(serialize_participant_view(link), status=200)


@csrf_exempt
@require_http_methods(["PUT"])
def schedule_response(request, token, candidate_date_id):
    """``PUT /participant-links/{token}/responses/{candidateDateId}``."""
    try:
        body = _read_body(request)
        if set(body) != {"status"}:
            raise MalformedRequestError
        status = _parse_status(body["status"])
    except MalformedRequestError:
        return _problem(*_REQUEST_REJECTED)

    try:
        link = services.set_schedule_response(token, candidate_date_id, status)
    except (
        services.LinkNotFoundError,
        services.LinkExpiredError,
        services.LinkRevokedError,
        services.LinkRateLimitedError,
        services.GatheringFinalizedError,
        services.CandidateDateNotFoundError,
    ) as error:
        return _participant_link_error_response(error)
    return JsonResponse(serialize_participant_view(link), status=200)


@csrf_exempt
@require_http_methods(["PUT"])
def participant_display_name(request, token):
    """``PUT /participant-links/{token}/display-name``."""
    try:
        body = _read_body(request)
        if set(body) != {"displayName"}:
            raise MalformedRequestError
        display_name = _parse_display_name(body["displayName"])
    except MalformedRequestError:
        return _problem(*_REQUEST_REJECTED)

    try:
        link = services.set_participant_display_name(token, display_name)
    except (
        services.LinkNotFoundError,
        services.LinkExpiredError,
        services.LinkRevokedError,
        services.LinkRateLimitedError,
    ) as error:
        return _participant_link_error_response(error)
    return JsonResponse(serialize_participant_view(link), status=200)


# --- browser page shells (contracts/gathering-scheduling-browser-interface.yaml) --


@login_required
def organizer_dashboard(request, gathering_id):
    """The authenticated organizer-dashboard screen shell (``organizerDashboard``)."""
    return render(request, "gathering/organizer_dashboard.html", {"gathering_id": gathering_id})


def participant_answer(request, token):
    """The signed-link participant-answer screen shell (``participantAnswer``).

    No sign-in is required or accepted specially -- the token itself governs
    access (gathering-scheduling-api.yaml's ParticipantToken parameter); this
    view only ever renders the empty client-side mount point, exactly like
    ``dining_radar.web.views.home`` does for candidate-search.
    """
    return render(request, "gathering/participant_answer.html", {"token": token})
