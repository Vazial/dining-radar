from django.db import migrations


class Migration(migrations.Migration):
    """Fixes the two model-level ``Meta.ordering`` values adr/0048 found to be
    non-deterministic in practice: every ``CandidateDate``/``ParticipantLink``
    row created in the same request (``createGathering``'s ``candidateDates``,
    ``issueParticipantLinks``'s ``count`` > 1) can share one identical
    ``auto_now_add`` timestamp at this database's timestamp resolution.

    ``CandidateDate``: ``ordering`` moves from ``["created_at"]`` to
    ``["start_at"]``. This is cosmetic/query-default only -- the actual
    API-facing order (``Gathering.candidateDates``/``ParticipantView.
    scheduleQuestions``, goingCount descending, ties broken by startAt
    ascending) has always come from ``services.candidate_dates_with_tallies``'s
    own explicit sort, now made independent of this Meta option entirely.

    ``ParticipantLink``: ``ordering`` gains an ``id`` ascending secondary key
    (``["issued_at", "id"]``). Unlike ``CandidateDate`` above,
    ``services.list_participant_links`` performs a plain ``.all()`` with no
    explicit ``order_by`` of its own, so this Meta option *is* the mechanism
    that makes ``listParticipantLinks`` deterministic (発行順, ties broken by
    ``id`` ascending).

    ``ShortlistedShop``/``Gathering`` are unchanged here -- their tie-breaks
    (distance-then-shop_id; id) are applied by explicit ``order_by``/sort
    calls in ``services.py`` instead, so no ``Meta.ordering`` migration is
    needed for either.
    """

    dependencies = [
        ("gathering", "0004_participantlink_server_error_once"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="candidatedate",
            options={"ordering": ["start_at"]},
        ),
        migrations.AlterModelOptions(
            name="participantlink",
            options={"ordering": ["issued_at", "id"]},
        ),
    ]
