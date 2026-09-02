"""Routes for ``contracts/gathering-scheduling-api.yaml`` and its two screens.

Every JSON API path below matches the contract's own path exactly (no
trailing slash). Each page route the browser-interface contract's
``browserEntry`` defines instead carries a trailing slash, so it can coexist
with the JSON path of the same prefix as a distinct URL pattern rather than
relying on Django's ``APPEND_SLASH`` redirect behavior to disambiguate them.
"""

from django.urls import path

from . import views

app_name = "gathering"

urlpatterns = [
    # Organizer JSON API (organizerSession + CSRF).
    path("gatherings", views.gatherings, name="gatherings"),
    path("gatherings/in-progress-count", views.in_progress_count, name="in-progress-count"),
    path("gatherings/<uuid:gathering_id>", views.gathering_detail, name="gathering-detail"),
    path(
        "gatherings/<uuid:gathering_id>/candidate-dates",
        views.candidate_dates,
        name="candidate-dates",
    ),
    path(
        "gatherings/<uuid:gathering_id>/candidate-dates/<uuid:candidate_date_id>/open-shop-preview",
        views.open_shop_preview,
        name="open-shop-preview",
    ),
    path(
        "gatherings/<uuid:gathering_id>/participant-links",
        views.participant_links,
        name="participant-links",
    ),
    path(
        "gatherings/<uuid:gathering_id>/participant-links/<uuid:link_id>/recopy",
        views.recopy_participant_link,
        name="participant-link-recopy",
    ),
    path(
        "gatherings/<uuid:gathering_id>/participant-links/<uuid:link_id>/revoke",
        views.revoke_participant_link,
        name="participant-link-revoke",
    ),
    path("gatherings/<uuid:gathering_id>/confirm-date", views.confirm_date, name="confirm-date"),
    # Participant JSON API (signed token, no session, no CSRF).
    path("participant-links/<str:token>", views.participant_view, name="participant-view"),
    path(
        "participant-links/<str:token>/responses/<uuid:candidate_date_id>",
        views.schedule_response,
        name="schedule-response",
    ),
    path(
        "participant-links/<str:token>/display-name",
        views.participant_display_name,
        name="participant-display-name",
    ),
    # Browser page shells (gathering-scheduling-browser-interface.yaml).
    path(
        "gatherings/",
        views.organizer_gathering_list,
        name="organizer-gathering-list",
    ),
    path(
        "gatherings/new/",
        views.organizer_gathering_create,
        name="organizer-gathering-create",
    ),
    path(
        "gatherings/<uuid:gathering_id>/",
        views.organizer_dashboard,
        name="organizer-dashboard",
    ),
    path("participant-links/<str:token>/", views.participant_answer, name="participant-answer"),
]
