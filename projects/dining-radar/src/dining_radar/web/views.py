"""Browser-facing candidate-proposal endpoint and authenticated shell.

Per ``ARCHITECTURE.md``'s module table, ``web`` handles condition input,
candidate display, and credit display; it must not reach ``integrations`` or
``records`` directly (see ``tests/test_structure.py``). The Hot Pepper
adapter is invoked only from ``dining_radar.suggestions.hotpepper_source``;
this module reaches it solely through ``suggestions``.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from dining_radar.recommendation.pipeline import ReproposalKindUnavailableError
from dining_radar.suggestions.acceptance_state import (
    AcceptanceProviderUnavailable,
    AcceptanceRateLimited,
    active_mode,
    propose_with_override,
)
from dining_radar.suggestions.errors import CandidateSourceUnavailableError
from dining_radar.suggestions.hotpepper_source import fetch_real_candidates
from dining_radar.suggestions.rate_limit import ProposalThrottle
from dining_radar.suggestions.service import propose_candidates

from .serializers import serialize_result

_AUTHENTICATION_REQUIRED = (
    "AUTHENTICATION_REQUIRED",
    "Sign in is required to view candidate proposals.",
)
_REQUEST_REJECTED = (
    "REQUEST_REJECTED",
    "The request could not be accepted. Refresh the page and try again.",
)
_REPROPOSAL_KIND_INVALID = (
    "PROPOSAL_REPROPOSAL_KIND_INVALID",
    "This proposal lens is not available. Choose another one.",
)
_PROVIDER_UNAVAILABLE = (
    "PROVIDER_UNAVAILABLE",
    "Candidate proposals cannot be retrieved right now. Please try again later.",
)
_RATE_LIMITED = (
    "PROPOSAL_RATE_LIMITED",
    "Too many proposal requests were made. Please try again shortly.",
)


@login_required
def home(request):
    """The authenticated candidate-proposal screen shell."""
    return render(request, "web/home.html")


class MalformedProposalRequestError(ValueError):
    """The request body did not match ``CandidateProposalRequest``."""


def _csrf_probe(request):
    return None


def _csrf_failed(request) -> bool:
    rejection = CsrfViewMiddleware(lambda _request: None).process_view(request, _csrf_probe, (), {})
    return rejection is not None


_ALLOWED_REQUEST_KEYS = frozenset({"reproposalKind", "previouslyShownProviderPageUrls"})


def _parse_request_body(raw_body: bytes) -> tuple[str | None, tuple[str, ...]]:
    """Parse ``CandidateProposalRequest``: ``(reproposalKind, previouslyShownProviderPageUrls)``.

    Per ADR-0017 decision 3 (Must), the parsed
    ``previouslyShownProviderPageUrls`` value is returned only as a plain
    local tuple for the caller to pass straight into the recommendation
    pipeline for this one request's candidate selection -- this function and
    every caller in this module must never log, trace, or echo it back in an
    error response.
    """
    try:
        body = json.loads(raw_body or b"{}")
    except (TypeError, ValueError) as error:
        raise MalformedProposalRequestError from error

    if not isinstance(body, dict) or (set(body) - _ALLOWED_REQUEST_KEYS):
        raise MalformedProposalRequestError

    reproposal_kind = body.get("reproposalKind")
    if reproposal_kind is not None and not isinstance(reproposal_kind, str):
        raise MalformedProposalRequestError

    previously_shown = body.get("previouslyShownProviderPageUrls", [])
    if not isinstance(previously_shown, list) or not all(
        isinstance(item, str) for item in previously_shown
    ):
        raise MalformedProposalRequestError

    return reproposal_kind, tuple(previously_shown)


def _problem(status: int, code_and_message: tuple[str, str]) -> JsonResponse:
    code, message = code_and_message
    return JsonResponse({"code": code, "message": message}, status=status)


@csrf_exempt
@require_POST
def candidate_proposals(request):
    """``POST /candidate-proposals``: one fresh displayed proposal."""
    if not request.user.is_authenticated:
        return _problem(401, _AUTHENTICATION_REQUIRED)

    if _csrf_failed(request):
        return _problem(403, _REQUEST_REJECTED)

    try:
        reproposal_kind, previously_shown_provider_page_urls = _parse_request_body(request.body)
    except MalformedProposalRequestError:
        return _problem(400, _REPROPOSAL_KIND_INVALID)

    override = active_mode()
    if override is not None:
        try:
            result = propose_with_override(
                override, reproposal_kind, previously_shown_provider_page_urls
            )
        except ReproposalKindUnavailableError:
            return _problem(400, _REPROPOSAL_KIND_INVALID)
        except AcceptanceProviderUnavailable:
            return _problem(503, _PROVIDER_UNAVAILABLE)
        except AcceptanceRateLimited as limited:
            response = _problem(429, _RATE_LIMITED)
            response["Retry-After"] = str(limited.retry_after_seconds)
            return response
        return JsonResponse(serialize_result(result), status=200)

    throttle = ProposalThrottle(request)
    if throttle.is_limited():
        response = _problem(429, _RATE_LIMITED)
        response["Retry-After"] = str(throttle.window_seconds)
        return response
    throttle.record_request()

    try:
        result = propose_candidates(
            reproposal_kind,
            fetch_candidates=fetch_real_candidates,
            previously_shown_provider_page_urls=previously_shown_provider_page_urls,
        )
    except (ValueError, ReproposalKindUnavailableError):
        return _problem(400, _REPROPOSAL_KIND_INVALID)
    except CandidateSourceUnavailableError:
        return _problem(503, _PROVIDER_UNAVAILABLE)

    return JsonResponse(serialize_result(result), status=200)
