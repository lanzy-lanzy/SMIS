import re
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from academics.models import GradingPeriod, Section, Subject
from accounts.models import AuditLog
from grades.mapeh import MAPEH_COMPONENTS, is_mapeh_subject, mapeh_component, merge_mapeh_grades
from grades.models import Grade

from .models import ENROLLED_STATUSES, Student, StudentPromotion


def _school_year_start(name):
    match = re.fullmatch(r'(?:S\.?Y\.?\s*)?(\d{4})\s*[-–—/]\s*(\d{4})', name.strip(), re.IGNORECASE)
    if match and int(match[2]) == int(match[1]) + 1:
        return int(match[1])
    return None


def promotion_sections(student):
    if not student.grade_level_id or not student.school_year_id:
        return Section.objects.none()
    return promotion_destinations(student.school_year, student.grade_level)


def default_promotion_source_year(years):
    current = next((year for year in years if year.is_current), None)
    start = _school_year_start(current.name) if current else None
    if start is not None:
        previous = next((year for year in years if _school_year_start(year.name) == start - 1), None)
        if previous:
            return previous
    return current or next(iter(years), None)


def promotion_destinations(school_year, grade_level):
    start = _school_year_start(school_year.name)
    if start is None:
        return Section.objects.none()
    candidates = Section.objects.filter(
        grade_level__level=grade_level.level + 1,
        school_year__is_current=True,
    ).select_related('grade_level', 'school_year')
    return candidates.filter(pk__in=[
        section.pk for section in candidates
        if _school_year_start(section.school_year.name) == start + 1
    ])


def _check_promotion_grades(period_ids, subjects, grades):
    if set(period_ids) != {order for order, _ in GradingPeriod.PERIOD_CHOICES}:
        raise ValidationError('Configure all three grading terms for the source school year.')
    recorded_subjects = {grade.subject_id for grade in grades}
    subjects = [subject for subject in subjects if subject.is_active or subject.pk in recorded_subjects]
    marks = {
        (grade.subject_id, grade.grading_period_id, grade.component): grade.quarter_grade
        for grade in grades
        if grade.status in ('validated', 'locked') and 0 < grade.quarter_grade <= 100
    }
    missing = []
    failed = []
    legacy_mapeh = {}
    for subject in subjects:
        term_marks = []
        for period_id in period_ids.values():
            value = marks.get((subject.pk, period_id, ''))
            if is_mapeh_subject(subject.name):
                components = [
                    marks.get((subject.pk, period_id, component))
                    for component, _, _ in MAPEH_COMPONENTS
                ]
                if any(mark is not None for mark in components):
                    value = merge_mapeh_grades(components) if None not in components else None
            term_marks.append(value)
        if None in term_marks:
            missing.append(subject.name)
        elif mapeh_component(subject.name):
            legacy_mapeh[mapeh_component(subject.name)] = term_marks
        elif _annual_grade(term_marks) < 75:
            failed.append(subject.name)

    if not subjects:
        raise ValidationError('Configure the required subjects for the source grade level.')
    if missing:
        raise ValidationError('Finalized grades are missing for one or more terms in %(subjects)s.',
                              params={'subjects': ', '.join(missing)})
    if legacy_mapeh:
        if set(legacy_mapeh) != {component for component, _, _ in MAPEH_COMPONENTS}:
            raise ValidationError('Both MAPEH components must have finalized grades.')
        if _annual_grade([merge_mapeh_grades(values) for values in zip(*legacy_mapeh.values())]) < 75:
            failed.append('MAPEH')
    if failed:
        raise ValidationError('A final grade of at least 75 is required in %(subjects)s.',
                              params={'subjects': ', '.join(failed)})


def _annual_grade(term_marks):
    return (sum(map(Decimal, term_marks)) / len(term_marks)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def promotion_issues(students, school_year, grade_level, destination=None):
    """Evaluate a cohort with the same rules used at confirmation."""
    if not students:
        return {}
    student_ids = [student.pk for student in students]
    previously_promoted = set(StudentPromotion.objects.filter(
        student_id__in=student_ids, from_school_year=school_year,
    ).values_list('student_id', flat=True))
    conflicts = set()
    if destination:
        conflicts = set(
            Grade.objects.filter(student_id__in=student_ids, school_year=destination.school_year)
            .exclude(section=destination, subject__grade_level=destination.grade_level)
            .order_by().values_list('student_id', flat=True).distinct()
        )

    period_ids = dict(GradingPeriod.objects.filter(school_year=school_year).values_list('order', 'pk'))
    subjects = list(Subject.objects.filter(grade_level=grade_level))
    grades_by_student = defaultdict(list)
    grades = Grade.objects.filter(
        student_id__in=student_ids, school_year=school_year,
        subject__grade_level=grade_level, grading_period_id__in=period_ids.values(),
    ).only('student_id', 'subject_id', 'grading_period_id', 'component', 'quarter_grade', 'status').order_by()
    for grade in grades:
        grades_by_student[grade.student_id].append(grade)

    issues = {}
    for student in students:
        if student.status not in ENROLLED_STATUSES:
            issues[student.pk] = 'Only enrolled students can be promoted.'
        elif student.pk in previously_promoted:
            issues[student.pk] = 'A promotion has already been recorded for this school year.'
        elif student.pk in conflicts:
            issues[student.pk] = 'Existing destination-year grades conflict with the selected placement.'
        else:
            try:
                _check_promotion_grades(period_ids, subjects, grades_by_student[student.pk])
            except ValidationError as error:
                issues[student.pk] = error.messages[0]
    return issues


@transaction.atomic
def promote_student(student_id, source_year_id, source_grade_id, section_id, actor):
    student = Student.objects.select_for_update().get(pk=student_id)
    if (student.school_year_id, student.grade_level_id) != (source_year_id, source_grade_id):
        raise ValidationError('The student’s placement changed. Review the current profile and try again.')
    section = promotion_sections(student).filter(pk=section_id).first()
    if section is None:
        raise ValidationError('Select a section in the next grade and next school year.')
    issues = promotion_issues([student], student.school_year, student.grade_level, section)
    if issues:
        raise ValidationError(issues[student.pk])
    _record_promotion(student, student.school_year, student.grade_level, section, actor)


@transaction.atomic
def promote_cohort(cohort, student_ids, school_year, grade_level, destination_id, actor):
    students = list(cohort.filter(pk__in=student_ids).select_for_update().order_by('pk'))
    if len(students) != len(student_ids):
        raise ValidationError('One or more selected students are no longer in this cohort. Review the roster and try again.')
    destination = promotion_destinations(school_year, grade_level).filter(pk=destination_id).first()
    if destination is None:
        raise ValidationError('The selected destination is no longer available. Choose a destination and try again.')
    issues = promotion_issues(students, school_year, grade_level, destination)
    if issues:
        raise ValidationError([
            f'{student.full_name} ({student.lrn}): {issues[student.pk]}'
            for student in students if student.pk in issues
        ])
    for student in students:
        _record_promotion(student, school_year, grade_level, destination, actor)


def _record_promotion(student, school_year, grade_level, section, actor):
    StudentPromotion.objects.create(
        student=student, from_grade_level=grade_level,
        from_school_year=school_year, from_section_id=student.section_id,
        to_grade_level=section.grade_level, to_school_year=section.school_year,
        to_section=section, promoted_by=actor,
    )
    AuditLog.objects.create(
        user=actor, action='update', model_name='Student', object_id=str(student.pk),
        description=f'Promoted {student.full_name} from {grade_level} ({school_year}) '
                    f'to {section} ({section.school_year})',
    )
    student.grade_level = section.grade_level
    student.school_year = section.school_year
    student.section = section
    student.save(update_fields=['grade_level', 'school_year', 'section', 'updated_at'])
