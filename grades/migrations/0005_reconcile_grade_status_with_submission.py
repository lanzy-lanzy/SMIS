from django.db import migrations


def reconcile_grade_status_with_submission(apps, schema_editor):
    """Repair legacy data where a GradeSubmission was approved/returned but the
    underlying Grade rows were left in a stale status (e.g. still 'submitted'
    after the Registrar approved). Sync each Grade's status to its submission's
    decision across the whole class scope (subject + section + school_year + period).
    """
    Grade = apps.get_model('grades', 'Grade')
    GradeSubmission = apps.get_model('grades', 'GradeSubmission')

    for sub in GradeSubmission.objects.filter(status='approved').select_related(
        'subject', 'section', 'school_year', 'grading_period'
    ):
        Grade.objects.filter(
            subject=sub.subject,
            section=sub.section,
            school_year=sub.school_year,
            grading_period=sub.grading_period,
            status__in=['draft', 'submitted', 'returned'],
        ).update(status='validated')

    for sub in GradeSubmission.objects.filter(status='returned').select_related(
        'subject', 'section', 'school_year', 'grading_period'
    ):
        Grade.objects.filter(
            subject=sub.subject,
            section=sub.section,
            school_year=sub.school_year,
            grading_period=sub.grading_period,
            status='submitted',
        ).update(status='returned')


def noop(apps, schema_editor):
    # Historical snapshot cannot be reconstructed; forward-only repair.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('grades', '0004_alter_gradesubmission_status_and_more'),
    ]

    operations = [
        migrations.RunPython(reconcile_grade_status_with_submission, noop),
    ]
