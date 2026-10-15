# Data migration: reconcile the legacy four-quarter structure with the new
# three-term model. Renames "Quarter N" grading periods to "Term N" and removes
# the 4th-term periods (their Grade / GradeSubmission rows cascade away).
#
# The backwards operation is intentionally a no-op: deleted 4th-term grade data
# cannot be reconstructed. Re-running `seed_data` repopulates a clean 3-term set.

from django.db import migrations


def rename_and_prune(apps, schema_editor):
    GradingPeriod = apps.get_model("academics", "GradingPeriod")

    # Remove the 4th term (order=4) and everything that cascades from it.
    GradingPeriod.objects.filter(order__gte=4).delete()

    # Rename the surviving periods' display names Quarter -> Term.
    for period in GradingPeriod.objects.filter(order__lte=3):
        if "Quarter" in period.name:
            period.name = period.name.replace("Quarter", "Term")
            period.save(update_fields=["name"])


def noop(apps, schema_editor):
    # Irreversible: 4th-term grade data was intentionally pruned.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0005_alter_gradingperiod_end_month_and_more"),
    ]

    operations = [
        migrations.RunPython(rename_and_prune, noop),
    ]
