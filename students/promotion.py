import re

from django.core.exceptions import ValidationError
from django.db import transaction

from academics.models import Section
from accounts.models import AuditLog
from grades.annual import annual_results
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

    results = annual_results(school_year, dict.fromkeys(student_ids, grade_level.pk))

    issues = {}
    for student in students:
        if student.status not in ENROLLED_STATUSES:
            issues[student.pk] = 'Only enrolled students can be promoted.'
        elif student.pk in previously_promoted:
            issues[student.pk] = 'A promotion has already been recorded for this school year.'
        elif student.pk in conflicts:
            issues[student.pk] = 'Existing destination-year grades conflict with the selected placement.'
        else:
            finals, reason = results[student.pk]
            if reason:
                issues[student.pk] = reason
            else:
                failed = [name for (_, name), mark in finals.items() if mark < 75]
                if failed:
                    issues[student.pk] = f'A final grade of at least 75 is required in {", ".join(failed)}.'
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
