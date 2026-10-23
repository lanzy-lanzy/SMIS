# Re-scale the grades saved before transmutation. Until now quarter_grade held
# the weighted total of the three categories; that value is moved to
# initial_grade and quarter_grade/final_grade take the term grade the
# transmutation table maps it to, with remarks following the new term grade.
# Rows with nothing encoded (0) are left alone: 0 is "no grade", not the
# bottom of the table.
from decimal import ROUND_HALF_UP, Decimal

from django.db import migrations

# Frozen copy of grades.TRANSMUTATION_BANDS (descending inclusive minimums).
BANDS = [
    (Decimal('99.50'), 100), (Decimal('98.32'), 99), (Decimal('97.14'), 98),
    (Decimal('95.96'), 97), (Decimal('94.78'), 96), (Decimal('93.60'), 95),
    (Decimal('92.42'), 94), (Decimal('91.24'), 93), (Decimal('90.06'), 92),
    (Decimal('88.88'), 91), (Decimal('87.70'), 90), (Decimal('86.52'), 89),
    (Decimal('85.34'), 88), (Decimal('84.16'), 87), (Decimal('82.98'), 86),
    (Decimal('81.80'), 85), (Decimal('80.62'), 84), (Decimal('79.44'), 83),
    (Decimal('78.26'), 82), (Decimal('77.08'), 81), (Decimal('75.90'), 80),
    (Decimal('74.72'), 79), (Decimal('73.54'), 78), (Decimal('72.36'), 77),
    (Decimal('71.18'), 76), (Decimal('70.00'), 75), (Decimal('65.34'), 74),
    (Decimal('60.67'), 73), (Decimal('56.01'), 72), (Decimal('51.34'), 71),
    (Decimal('46.67'), 70), (Decimal('42.01'), 69), (Decimal('37.34'), 68),
    (Decimal('32.68'), 67), (Decimal('28.01'), 66), (Decimal('23.35'), 65),
    (Decimal('18.68'), 64), (Decimal('14.01'), 63), (Decimal('9.35'), 62),
    (Decimal('4.68'), 61), (Decimal('0.00'), 60),
]


def transmute(value):
    initial = max(Decimal('0.00'), min(
        Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        Decimal('100.00')))
    for low, term in BANDS:
        if initial >= low:
            return Decimal(term)
    return Decimal('60')


def remarks_for(term):
    if term >= 75:
        return 'Passed'
    if term >= 60:
        return 'Incomplete'
    return 'Failed'


def forward(apps, schema_editor):
    Grade = apps.get_model('grades', 'Grade')
    for grade in Grade.objects.exclude(quarter_grade=0).iterator():
        initial = Decimal(grade.quarter_grade)
        grade.initial_grade = initial
        grade.quarter_grade = transmute(initial)
        grade.final_grade = grade.quarter_grade
        grade.remarks = remarks_for(grade.quarter_grade)
        grade.save(update_fields=['initial_grade', 'quarter_grade', 'final_grade', 'remarks'])


def backward(apps, schema_editor):
    Grade = apps.get_model('grades', 'Grade')
    for grade in Grade.objects.exclude(initial_grade=0).iterator():
        grade.quarter_grade = grade.initial_grade
        grade.final_grade = grade.initial_grade
        grade.remarks = remarks_for(grade.initial_grade)
        grade.save(update_fields=['initial_grade', 'quarter_grade', 'final_grade', 'remarks'])


class Migration(migrations.Migration):

    dependencies = [
        ("grades", "0012_grade_initial_grade"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
