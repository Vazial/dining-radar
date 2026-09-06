from django.db import migrations, models


class Migration(migrations.Migration):
    """Replaces the retired boolean ``approved_shop_ids`` with a three-tier
    ``votes`` mapping (adr/0044). Human decision (ADR-0044 decision 5): the
    prior two-value vote data is not migrated -- production carried
    essentially no real votes under that model, so existing
    ``ShopVoteSubmission`` rows are simply dropped of their old column and
    given a fresh, empty ``votes`` mapping rather than converted.
    """

    dependencies = [
        ("gathering", "0002_gathering_finalized_shop_id_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="shopvotesubmission",
            name="approved_shop_ids",
        ),
        migrations.AddField(
            model_name="shopvotesubmission",
            name="votes",
            field=models.JSONField(default=dict),
        ),
    ]
