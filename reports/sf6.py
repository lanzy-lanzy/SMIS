"""Data assembly for School Form 6 (SF6).

SF6 summarises, per grade level, how many learners were promoted, retained or
needed conditional promotion, and groups every learner by the DepEd
achievement band of their general average. The table uses finalized annual
grades and recorded promotions for the selected school year.
"""

from decimal import Decimal, ROUND_HALF_UP

from grades.annual import annual_results
from students.models import ENROLLED_STATUSES, Student, StudentPromotion


SF6_GRADE_LEVELS = (7, 8, 9, 10, 11, 12)

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


def build_sf6_summary(school_year):
    """Build the SF6 table for *school_year*.

    Returns the fixed grade-level groups plus one entry per table row. The
    TOTAL row counts enrolled learners. Outcome rows use completed annual marks
    or a recorded promotion, while achievement rows require completed grades.
    """
    level_entries = [
        {
            'level': level,
            'label': f'GRADE {level}',
            'counts': {key: _empty_counts() for key in SF6_ROW_KEYS},
            'total': _empty_counts(),
        }
        for level in SF6_GRADE_LEVELS
    ]
    by_level = {entry['level']: entry for entry in level_entries}
    row_totals = {key: _empty_counts() for key in SF6_ROW_KEYS}
    grand_total = _empty_counts()

    graded_total = 0
    unclassified_total = 0
    recorded_promoted_total = 0
    if school_year is not None:
        placements = {}
        students = Student.objects.filter(
            school_year=school_year, status__in=ENROLLED_STATUSES,
        ).select_related('grade_level', 'section__grade_level')
        for student in students:
            level = student.grade_level or (student.section.grade_level if student.section_id else None)
            if level:
                placements[student.pk] = (level, student.sex)

        promotions = StudentPromotion.objects.filter(from_school_year=school_year).select_related(
            'student', 'from_grade_level',
        )
        promoted_ids = set()
        for promotion in promotions:
            placements[promotion.student_id] = (promotion.from_grade_level, promotion.student.sex)
            promoted_ids.add(promotion.student_id)

        placements = {
            student_id: (level, sex) for student_id, (level, sex) in placements.items()
            if level.level in by_level
        }
        results = annual_results(school_year, {
            student_id: level.pk for student_id, (level, _) in placements.items()
        })
        for student_id, (level, sex) in placements.items():
            entry = by_level[level.level]
            _add(entry['total'], sex)
            _add(grand_total, sex)

            finals, _reason = results[student_id]
            status, band, _average = classify_finals(finals)
            if student_id in promoted_ids:
                status = 'promoted'
                recorded_promoted_total += 1

            if status:
                _add(entry['counts'][status], sex)
                _add(row_totals[status], sex)
            else:
                unclassified_total += 1
            if band:
                graded_total += 1
                _add(entry['counts'][band], sex)
                _add(row_totals[band], sex)

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

    return {
        'levels': [
            {'level': entry['level'], 'label': entry['label']}
            for entry in level_entries
        ],
        'rows': rows,
        'enrolled_total': grand_total['total'],
        'graded_total': graded_total,
        'ungraded_total': grand_total['total'] - graded_total,
        'unclassified_total': unclassified_total,
        'recorded_promoted_total': recorded_promoted_total,
    }
