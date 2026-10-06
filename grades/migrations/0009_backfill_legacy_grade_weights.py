# Backfill category weights for Grade rows that existed before weights were
# configurable. Those grades were computed with the previous fixed DepEd split
# (WW 20% / PT 50% / QA 30%), so we stamp that onto every pre-existing row to
# keep its stored quarter_grade consistent with the per-category weighted scores
# now shown in the UI. Rows created after this point use the new 20/20/50 default.
from django.db import migrations


def backfill_legacy_weights(apps, schema_editor):
    Grade = apps.get_model('grades', 'Grade')
    Grade.objects.update(
        written_work_weight=20,
        performance_task_weight=50,
        assessment_weight=30,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("grades", "0008_grade_assessment_weight_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_legacy_weights, migrations.RunPython.noop),
    ]
