from django.db import migrations, models


class Migration(migrations.Migration):
    """Adds ``ParticipantLink.server_error_once`` (adr/0047, test-support-api.yaml
    1.5.4's ``seedParticipantLinkServerError``) -- a one-shot flag, consumed by the
    very next ``getParticipantView`` call only, mirroring ``rate_limited_once``'s
    existing shape but narrower in scope (see this field's own model docstring).
    """

    dependencies = [
        ("gathering", "0003_shopvotesubmission_votes"),
    ]

    operations = [
        migrations.AddField(
            model_name="participantlink",
            name="server_error_once",
            field=models.BooleanField(default=False),
        ),
    ]
