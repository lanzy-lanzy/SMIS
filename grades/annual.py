"""Finalized annual subject marks shared by promotion and SF6."""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from academics.models import GradingPeriod, Subject

from .mapeh import MAPEH_COMPONENTS, is_mapeh_subject, mapeh_component, merge_mapeh_grades
from .models import Grade, GradeSubmission


def annual_results(school_year, grade_by_student):
    """Return (subject finals, incomplete reason) for each learner in the cohort."""
    if not grade_by_student:
        return {}
    period_ids = dict(GradingPeriod.objects.filter(school_year=school_year).values_list('order', 'pk'))
    if set(period_ids) != {order for order, _ in GradingPeriod.PERIOD_CHOICES}:
        return {
            student_id: ({}, 'Configure all three grading terms for the source school year.')
            for student_id in grade_by_student
        }

    subjects_by_level = defaultdict(list)
    grade_levels = set(grade_by_student.values())
    for subject in Subject.objects.filter(grade_level_id__in=grade_levels):
        subjects_by_level[subject.grade_level_id].append(subject)

    approved_scopes = set(
        GradeSubmission.objects.filter(
            school_year=school_year,
            status='approved',
            grading_period_id__in=period_ids.values(),
        ).values_list('subject_id', 'section_id', 'grading_period_id')
    )

    grades_by_student = defaultdict(list)
    grades = Grade.objects.filter(
        school_year=school_year, student_id__in=grade_by_student,
        grading_period_id__in=period_ids.values(), subject__grade_level_id__in=grade_levels,
    ).values_list(
        'student_id', 'subject_id', 'section_id', 'subject__grade_level_id', 'grading_period_id',
        'component', 'quarter_grade', 'status',
    ).order_by()
    for student_id, subject_id, section_id, level_id, period_id, component, mark, status in grades:
        if level_id == grade_by_student[student_id]:
            effective_status = (
                'validated'
                if status in ('validated', 'locked') or (subject_id, section_id, period_id) in approved_scopes
                else status
            )
            grades_by_student[student_id].append((subject_id, period_id, component, mark, effective_status))

    return {
        student_id: _subject_finals(period_ids.values(), subjects_by_level[level_id], grades_by_student[student_id])
        for student_id, level_id in grade_by_student.items()
    }


def _subject_finals(period_ids, subjects, grades):
    recorded_subjects = {subject_id for subject_id, *_ in grades}
    subjects = [subject for subject in subjects if subject.is_active or subject.pk in recorded_subjects]
    if not subjects:
        return {}, 'Configure the required subjects for the source grade level.'

    combined_mapeh = [subject for subject in subjects if is_mapeh_subject(subject.name)]
    legacy_mapeh = {
        mapeh_component(subject.name): subject for subject in subjects if mapeh_component(subject.name)
    }
    component_keys = {key for key, _, _ in MAPEH_COMPONENTS}
    # An older cohort can have paired component subjects even after a combined
    # MAPEH subject has been enabled for newer cohorts.
    uses_legacy_pair = component_keys <= legacy_mapeh.keys() and any(
        subject.pk in recorded_subjects for subject in legacy_mapeh.values()
    ) and not any(subject.pk in recorded_subjects for subject in combined_mapeh)
    marks = {
        (subject_id, period_id, component): mark
        for subject_id, period_id, component, mark, status in grades
        if status in ('validated', 'locked') and 0 < mark <= 100
    }

    finals = {}
    missing = []
    legacy_marks = {}
    for subject in subjects:
        name = subject.name.strip().lower()
        legacy_component = mapeh_component(name)
        is_combined = is_mapeh_subject(name)
        if uses_legacy_pair and is_combined:
            continue
        if combined_mapeh and not uses_legacy_pair and (
            legacy_component or name in {'music', 'arts', 'physical education', 'health'}
        ):
            continue

        term_marks = []
        for period_id in period_ids:
            mark = marks.get((subject.pk, period_id, ''))
            if is_combined:
                components = [marks.get((subject.pk, period_id, key)) for key, _, _ in MAPEH_COMPONENTS]
                if any(value is not None for value in components):
                    mark = merge_mapeh_grades(components) if None not in components else None
            term_marks.append(mark)
        if None in term_marks:
            missing.append(subject.name)
        elif legacy_component:
            legacy_marks[legacy_component] = term_marks
        else:
            finals[(subject.pk, subject.name)] = _annual_grade(term_marks)

    if missing:
        return {}, f'Finalized grades are missing for one or more terms in {", ".join(missing)}.'
    if legacy_marks:
        if set(legacy_marks) != component_keys:
            return {}, 'Both MAPEH components must have finalized grades.'
        finals[(None, 'MAPEH')] = _annual_grade(
            [merge_mapeh_grades(values) for values in zip(*legacy_marks.values())]
        )
    return finals, None


def _annual_grade(term_marks):
    return (sum(map(Decimal, term_marks)) / len(term_marks)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
