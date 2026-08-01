from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


@login_required
def home(request):
    """Minimal shell; candidate generation is a subsequent approved slice."""
    return render(request, "web/home.html")


def _csrf_probe(request):
    return None


@csrf_exempt
@require_POST
def candidate_proposals_placeholder(request):
    """Preserve the authentication boundary before candidate search exists."""
    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Sign in is required to view candidate proposals.",
            },
            status=401,
        )

    csrf_rejection = CsrfViewMiddleware(lambda _request: None).process_view(
        request, _csrf_probe, (), {}
    )
    if csrf_rejection is not None:
        return csrf_rejection

    return JsonResponse(
        {
            "code": "PROVIDER_UNAVAILABLE",
            "message": "Candidate proposals cannot be retrieved right now. Please try again later.",
        },
        status=503,
    )
