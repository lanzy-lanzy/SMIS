"""Data assembly for School Form 6 (SF6).

SF6 summarises, per grade level, how many learners were promoted, retained or
needed conditional promotion, and groups every learner by the DepEd
achievement band of their general average. The table uses finalized annual
grades and recorded promotions for the selected school year.
"""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from grades.annual import _annual_grade
from grades.mapeh import MAPEH_COMPONENTS, is_mapeh_subject, mapeh_component, merge_mapeh_grades
from grades.models import Grade, GradeSubmission
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


def _sf6_subject_finals(school_year, grade_by_student):
    """Compute per-subject finals for each learner from their finalized grades in *school_year*.

    Unlike bulk-promotion eligibility (which requires all three terms and every
    configured subject), SF6 and dashboard monitoring classify every learner
    who has finalized grades in one or more terms so real in-year progress
    reflects immediately in PROMOTED / CONDITIONAL / RETAINED and achievement
    bands.
    """
    if not grade_by_student:
        return {}

    approved_scopes = set(
        GradeSubmission.objects.filter(
            school_year=school_year,
            status='approved',
        ).values_list('subject_id', 'section_id', 'grading_period_id')
    )

    grades = Grade.objects.filter(
        school_year=school_year,
        student_id__in=grade_by_student,
        quarter_grade__gt=0,
        quarter_grade__lte=100,
    ).values_list(
        'student_id', 'subject_id', 'subject__name', 'section_id',
        'grading_period_id', 'component', 'quarter_grade', 'status',
    ).order_by()

    by_student = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    for student_id, subject_id, subject_name, section_id, period_id, component, mark, status in grades:
        is_finalized = (
            status in ('validated', 'locked')
            or (subject_id, section_id, period_id) in approved_scopes
        )
        if not is_finalized:
            continue
        by_student[student_id][(subject_id, subject_name)][period_id][component] = mark

    component_keys = {key for key, _, _ in MAPEH_COMPONENTS}
    results = {}
    for student_id in grade_by_student:
        subjects_data = by_student.get(student_id, {})
        has_combined_mapeh = any(is_mapeh_subject(name) for _sid, name in subjects_data)
        finals = {}
        legacy_by_period = defaultdict(dict)

        for (subject_id, name), period_map in subjects_data.items():
            lower_name = (name or '').strip().lower()
            legacy_comp = mapeh_component(lower_name)
            is_combined = is_mapeh_subject(lower_name)

            if has_combined_mapeh and (
                legacy_comp or lower_name in {'music', 'arts', 'physical education', 'health'}
            ):
                continue

            if legacy_comp:
                for period_id, comp_map in period_map.items():
                    if '' in comp_map:
                        legacy_by_period[period_id][legacy_comp] = comp_map['']
                continue

            term_marks = []
            for _period_id, comp_map in period_map.items():
                if is_combined:
                    if '' in comp_map:
                        term_marks.append(comp_map[''])
                    else:
                        parts = [comp_map.get(key) for key, _, _ in MAPEH_COMPONENTS]
                        if all(v is not None for v in parts):
                            term_marks.append(merge_mapeh_grades(parts))
                elif '' in comp_map:
                    term_marks.append(comp_map[''])

            if term_marks:
                finals[(subject_id, name)] = _annual_grade(term_marks)

        if legacy_by_period and not has_combined_mapeh:
            merged_terms = [
                merge_mapeh_grades([comps[key] for key, _, _ in MAPEH_COMPONENTS])
                for comps in legacy_by_period.values()
                if component_keys <= comps.keys()
            ]
            if merged_terms:
                finals[(None, 'MAPEH')] = _annual_grade(merged_terms)

        results[student_id] = finals
    return results


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
        results = _sf6_subject_finals(school_year, {
            student_id: level.pk for student_id, (level, _) in placements.items()
        })
        for student_id, (level, sex) in placements.items():
            entry = by_level[level.level]
            _add(entry['total'], sex)
            _add(grand_total, sex)

            finals = results.get(student_id, {})
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
