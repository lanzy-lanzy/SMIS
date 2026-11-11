"""Data assembly for School Form 6 (SF6).

SF6 summarises, per grade level, how many learners were promoted, retained or
needed conditional promotion, and groups every learner by the DepEd
achievement band of their general average. The numbers are derived from
validated/locked grades only, so the form always reflects finalized records.
"""

from decimal import Decimal, ROUND_HALF_UP

from grades.models import Grade
from grades.mapeh import mapeh_component, merge_mapeh_grades
from students.models import ENROLLED_STATUSES, Student


SF6_GRADE_LEVELS = (7, 8, 9, 10, 11, 12)

# MAPEH sub-components are folded into the MAPEH parent grade when the parent
# has a final grade, matching how the general average is computed elsewhere.
SF6_MAPEH_SUBJECTS = ('Music', 'Arts', 'Physical Education', 'Health')

SF6_STATUS_ROWS = (
    ('promoted', 'PROMOTED'),
    ('conditional', 'CONDITIONAL'),
    ('retained', 'RETAINED'),
)

SF6_ACHIEVEMENT_ROWS = (
    ('did_not_meet', 'Did Not Meet Expectations (74% and below)'),
    ('fairly_satisfactory', 'Fairly Satisfactory (75%-79%)'),
    ('satisfactory', 'Satisfactory (80%-84%)'),
    ('very_satisfactory', 'Very Satisfactory (85%-89%)'),
    ('outstanding', 'Outstanding (90%-100%)'),
)

SF6_ROW_KEYS = tuple(
    key for key, _label in SF6_STATUS_ROWS + SF6_ACHIEVEMENT_ROWS
)


def _empty_counts():
    return {'male': 0, 'female': 0, 'total': 0}


def _add(counts, sex):
    if sex == 'M':
        counts['male'] += 1
    elif sex == 'F':
        counts['female'] += 1
    counts['total'] += 1


def _band_for(grade):
    if grade >= 90:
        return 'outstanding'
    if grade >= 85:
        return 'very_satisfactory'
    if grade >= 80:
        return 'satisfactory'
    if grade >= 75:
        return 'fairly_satisfactory'
    return 'did_not_meet'


def classify_finals(subject_finals):
    """Classify one learner from their per-subject final grades.

    Returns ``(status, band, average)``. ``status`` is a key from
    ``SF6_STATUS_ROWS``, ``band`` a key from ``SF6_ACHIEVEMENT_ROWS`` and
    ``average`` the general average rounded to a whole number. Learners with no
    final grades return ``(None, None, None)``.
    """
    finals = [value for value in subject_finals.values() if value is not None]
    if not finals:
        return None, None, None

    average = sum(finals) / len(finals)
    average_whole = int(average.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    failed = sum(1 for value in finals if value < Decimal('75'))

    if average_whole < 75 or failed >= 3:
        status = 'retained'
    elif failed:
        status = 'conditional'
    else:
        status = 'promoted'

    return status, _band_for(average_whole), average_whole


def _level_of(student):
    if student.grade_level_id:
        return student.grade_level.level
    if student.section_id and student.section.grade_level_id:
        return student.section.grade_level.level
    return None


def _student_finals(students, school_year):
    """Return ``{student_id: {subject_name: final_grade}}`` for one school year.

    Only validated/locked grades count, the latest grading period wins for each
    subject, and MAPEH sub-components are dropped when a MAPEH parent grade
    exists so they are not counted twice in the general average. Music and
    Arts / PE and Health component finals are merged into one MAPEH final
    when no parent grade exists.
    """
    student_levels = {student.id: student.grade_level_id for student in students}
    grades = (
        Grade.objects
        .filter(
            school_year=school_year,
            status__in=('validated', 'locked'),
            student__in=students,
        )
        .select_related('subject', 'grading_period')
        .order_by('grading_period__order')
    )

    latest = {}
    for grade in grades:
        level_id = student_levels.get(grade.student_id)
        if level_id and grade.subject.grade_level_id != level_id:
            continue
        latest[(grade.student_id, grade.subject.name)] = grade

    finals = {}
    for (student_id, subject_name), grade in latest.items():
        finals.setdefault(student_id, {})[subject_name] = grade.final_grade

    for subject_finals in finals.values():
        if subject_finals.get('MAPEH') is not None:
            for subject_name in SF6_MAPEH_SUBJECTS:
                subject_finals.pop(subject_name, None)
            continue
        component_names = [name for name in subject_finals if mapeh_component(name)]
        if component_names:
            merged = merge_mapeh_grades(subject_finals[name] for name in component_names)
            for name in component_names:
                subject_finals.pop(name)
            if merged is not None:
                subject_finals['MAPEH'] = Decimal(merged)

    return finals


def build_sf6_summary(school_year):
    """Build the SF6 table for *school_year*.

    Returns the fixed grade-level groups plus one entry per table row. The
    TOTAL row counts enrolled learners; when some of them have no finalized
    grades, ``ungraded_total`` reports how many are missing from the promotion
    and achievement breakdowns.
    """
    level_entries = [
        {
            'level': level,
            'label': f'GRADE {level}',
            'counts': {key: _empty_counts() for key in SF6_ROW_KEYS},
            'total': _empty_counts(),
            'ungraded': 0,
        }
        for level in SF6_GRADE_LEVELS
    ]
    by_level = {entry['level']: entry for entry in level_entries}
    row_totals = {key: _empty_counts() for key in SF6_ROW_KEYS}
    grand_total = _empty_counts()

    if school_year is not None:
        students = list(
            Student.objects
            .filter(school_year=school_year, status__in=ENROLLED_STATUSES)
            .select_related('grade_level', 'section__grade_level')
        )
        finals = _student_finals(students, school_year)

        for student in students:
            entry = by_level.get(_level_of(student))
            if entry is None:
                continue

            _add(entry['total'], student.sex)
            _add(grand_total, student.sex)

            status, band, _average = classify_finals(finals.get(student.id, {}))
            if status is None:
                entry['ungraded'] += 1
                continue

            _add(entry['counts'][status], student.sex)
            _add(entry['counts'][band], student.sex)
            _add(row_totals[status], student.sex)
            _add(row_totals[band], student.sex)

    rows = []
    for key, label in SF6_STATUS_ROWS:
        rows.append({
            'kind': 'data',
            'label': label,
            'cells': [entry['counts'][key] for entry in level_entries],
            'total': row_totals[key],
        })

    rows.append({'kind': 'section', 'label': 'LEARNING PROGRESS AND ACHIEVEMENT'})

    for key, label in SF6_ACHIEVEMENT_ROWS:
        rows.append({
            'kind': 'data',
            'label': label,
            'cells': [entry['counts'][key] for entry in level_entries],
            'total': row_totals[key],
        })

    rows.append({
        'kind': 'total',
        'label': 'TOTAL',
        'cells': [entry['total'] for entry in level_entries],
        'total': grand_total,
    })

    graded_total = sum(
        entry['counts']['promoted']['total']
        + entry['counts']['conditional']['total']
        + entry['counts']['retained']['total']
        for entry in level_entries
    )

    return {
        'levels': [
            {'level': entry['level'], 'label': entry['label']}
            for entry in level_entries
        ],
        'rows': rows,
        'enrolled_total': grand_total['total'],
        'graded_total': graded_total,
        'ungraded_total': sum(entry['ungraded'] for entry in level_entries),
    }
