from django.urls import path

from . import views

urlpatterns = [
    path("authentication-state", views.authentication_state, name="authentication-state"),
    path("authentication/accounts/<str:account_ref>", views.authentication_account, name="account"),
    path("authentication/login-throttle", views.login_throttle, name="login-throttle"),
    path(
        "authentication/security-boundary",
        views.authentication_security_boundary,
        name="security-boundary",
    ),
    path(
        "candidate-proposals/state",
        views.candidate_proposal_state,
        name="candidate-proposal-state",
    ),
    path(
        "gathering-scheduling-state",
        views.gathering_scheduling_state,
        name="gathering-scheduling-state",
    ),
    path(
        "gathering-scheduling/participant-links/expire",
        views.gathering_seed_expired_participant_link,
        name="gathering-participant-link-expire",
    ),
    path(
        "gathering-scheduling/participant-links/rate-limit",
        views.gathering_seed_rate_limited_participant_link,
        name="gathering-participant-link-rate-limit",
    ),
    path(
        "gathering-scheduling/participant-links/server-error",
        views.gathering_seed_participant_link_server_error,
        name="gathering-participant-link-server-error",
    ),
]
