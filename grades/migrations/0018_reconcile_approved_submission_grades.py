from django.db import migrations


def reconcile_approved_submission_grades(apps, schema_editor):
    Grade = apps.get_model('grades', 'Grade')
    GradeSubmission = apps.get_model('grades', 'GradeSubmission')
    for sub in GradeSubmission.objects.filter(status='approved'):
        Grade.objects.filter(
            subject_id=sub.subject_id,
            section_id=sub.section_id,
            school_year_id=sub.school_year_id,
            grading_period_id=sub.grading_period_id,
            status__in=['draft', 'submitted', 'returned'],
        ).update(status='validated')


class Migration(migrations.Migration):

    dependencies = [
        ('grades', '0017_alter_grade_unique_together_grade_component_and_more'),
    ]

    operations = [
        migrations.RunPython(reconcile_approved_submission_grades, migrations.RunPython.noop),
    ]
