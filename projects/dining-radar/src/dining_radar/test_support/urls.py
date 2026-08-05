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
]
