"""Browser-facing candidate-proposal endpoint and authenticated shell.

Per ``ARCHITECTURE.md``'s module table, ``web`` handles condition input,
candidate display, and credit display; it must not reach ``integrations`` or
``records`` directly (see ``tests/test_structure.py``). The Hot Pepper
adapter is invoked only from ``dining_radar.suggestions.hotpepper_source``;
this module reaches it solely through ``suggestions``.

Per adr/0023, the request body is a single optional ``filters`` object
(``CandidateFilters``) rather than a ``reproposalKind``/
``previouslyShownProviderPageUrls`` pair; the initial request, "try again",
and "change filters" are all the same ``POST /candidate-proposals`` shape.
Per adr/0024 decision 4, the request body may additionally carry an optional
``shownProviderPageUrls`` array (the browser's current
``shownCandidateMemory`` snapshot); it is priority information forwarded to
the pipeline for this one request only and is never persisted, logged, or
echoed back.

**Interpretation note (developer discretion, not a contract conflict):**
``candidate-search-api.yaml`` v1.0.0's ``/candidate-proposals`` operation
defines only ``200``/``401``/``403``/``429``/``503`` responses -- no ``400``
(the prior draft's only 400 response, ``PROPOSAL_REPROPOSAL_KIND_INVALID``,
is retired by adr/0023 decision 8, and no replacement validation-error code
was added). The browser's own filter panel (``candidate-search-browser-
interface.yaml``) only ever sends a well-formed body, since every filter
control is a closed selection over a server-supplied or fixed enum
vocabulary -- so a malformed request body is unreachable through the real UI
and exists only as defense-in-depth against a malicious or buggy client. This
module treats a malformed body the same as a failed CSRF check: ``403
REQUEST_REJECTED``, the same generic, safe, already-defined "request could
not be accepted" message. This is a defensible filling of an unspecified
edge case, not a resolution of a conflict between approved artifacts, so it
does not require the escalation ``meta/permissions.md`` §3 reserves for
contract contradictions.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from dining_radar.recommendation.pipeline import CandidateFilters
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
_PROVIDER_UNAVAILABLE = (
    "PROVIDER_UNAVAILABLE",
    "Candidate proposals cannot be retrieved right now. Please try again later.",
)
_RATE_LIMITED = (
    "PROPOSAL_RATE_LIMITED",
    "Too many proposal requests were made. Please try again shortly.",
)

_ALLOWED_FILTER_KEYS = frozenset(
    {
        "genres",
        "includeIzakayaBar",
        "nonSmokingOnly",
        "cardPaymentOnly",
        "budgetTiers",
        "walkingTimeMaxMinutes",
    }
)
_ALLOWED_BUDGET_TIERS = frozenset({"LOW", "MID", "HIGH"})
_ALLOWED_REQUEST_KEYS = frozenset({"filters", "shownProviderPageUrls"})
# candidate-search-api.yaml CandidateProposalRequest.shownProviderPageUrls:
# maxItems 200 (adr/0024 decision 4) -- a defensive schema bound, not an
# expected operating size.
_MAX_SHOWN_PROVIDER_PAGE_URLS = 200


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


def _parse_string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise MalformedProposalRequestError
    return tuple(value)


def _parse_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise MalformedProposalRequestError
    return value


def _parse_walking_time_max_minutes(value: object) -> int | None:
    """``CandidateFilters.walkingTimeMaxMinutes`` (adr/0025 decision 3).

    ``None`` (the field's own omitted/``null`` "no restriction" value) is
    accepted unchanged; any other value must be a positive (``minimum: 1``,
    matching the contract) integer, excluding ``bool`` -- Python's ``bool``
    is an ``int`` subclass, so this must be checked explicitly, mirroring
    the equivalent guard other request-parsing code in this project already
    applies where a wire integer must not silently accept ``true``/``false``.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise MalformedProposalRequestError
    return value


def _parse_filters(raw: object) -> CandidateFilters:
    if raw is None:
        return CandidateFilters()
    if not isinstance(raw, dict) or (set(raw) - _ALLOWED_FILTER_KEYS):
        raise MalformedProposalRequestError

    genres = _parse_string_list(raw.get("genres", []))
    include_izakaya_bar = _parse_bool(raw.get("includeIzakayaBar", False))
    non_smoking_only = _parse_bool(raw.get("nonSmokingOnly", False))
    card_payment_only = _parse_bool(raw.get("cardPaymentOnly", False))
    budget_tiers = _parse_string_list(raw.get("budgetTiers", []))
    if any(tier not in _ALLOWED_BUDGET_TIERS for tier in budget_tiers):
        raise MalformedProposalRequestError
    walking_time_max_minutes = _parse_walking_time_max_minutes(raw.get("walkingTimeMaxMinutes"))

    return CandidateFilters(
        genres=genres,
        include_izakaya_bar=include_izakaya_bar,
        non_smoking_only=non_smoking_only,
        card_payment_only=card_payment_only,
        budget_tiers=budget_tiers,
        walking_time_max_minutes=walking_time_max_minutes,
    )


def _parse_shown_provider_page_urls(value: object) -> tuple[str, ...]:
    """Parse ``CandidateProposalRequest.shownProviderPageUrls`` (adr/0024 decision 4).

    Omitted or ``None`` means "no shown-set exists yet" (an empty tuple);
    every element must be a string, and the array may not exceed the
    contract's defensive ``maxItems: 200``. This value is priority
    information only -- it is forwarded to the pipeline and discarded once
    this request finishes; it is never validated against, or stored in, any
    durable state.
    """
    if value is None:
        return ()
    urls = _parse_string_list(value)
    if len(urls) > _MAX_SHOWN_PROVIDER_PAGE_URLS:
        raise MalformedProposalRequestError
    return urls


def _parse_request_body(raw_body: bytes) -> tuple[CandidateFilters, tuple[str, ...]]:
    """Parse ``CandidateProposalRequest`` into ``(CandidateFilters, shownProviderPageUrls)``."""
    try:
        body = json.loads(raw_body or b"{}")
    except (TypeError, ValueError) as error:
        raise MalformedProposalRequestError from error

    if not isinstance(body, dict) or (set(body) - _ALLOWED_REQUEST_KEYS):
        raise MalformedProposalRequestError

    filters = _parse_filters(body.get("filters"))
    shown_provider_page_urls = _parse_shown_provider_page_urls(body.get("shownProviderPageUrls"))
    return filters, shown_provider_page_urls


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
        filters, shown_provider_page_urls = _parse_request_body(request.body)
    except MalformedProposalRequestError:
        return _problem(403, _REQUEST_REJECTED)

    override = active_mode()
    if override is not None:
        try:
            result = propose_with_override(override, filters, shown_provider_page_urls)
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
            filters,
            fetch_candidates=fetch_real_candidates,
            shown_provider_page_urls=shown_provider_page_urls,
        )
    except CandidateSourceUnavailableError:
        return _problem(503, _PROVIDER_UNAVAILABLE)

    return JsonResponse(serialize_result(result), status=200)
