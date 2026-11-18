import re
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

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
    start = _school_year_start(student.school_year.name)
    if start is None:
        return Section.objects.none()
    candidates = Section.objects.filter(
        grade_level__level=student.grade_level.level + 1,
        school_year__is_current=True,
    ).select_related('grade_level', 'school_year')
    return candidates.filter(pk__in=[
        section.pk for section in candidates
        if _school_year_start(section.school_year.name) == start + 1
    ])


def check_promotion_grades(student):
    period_ids = dict(GradingPeriod.objects.filter(school_year=student.school_year).values_list('order', 'pk'))
    if set(period_ids) != {order for order, _ in GradingPeriod.PERIOD_CHOICES}:
        raise ValidationError('Configure all three grading terms for the source school year.')

    grades = Grade.objects.filter(
        student=student, school_year=student.school_year,
        subject__grade_level=student.grade_level, grading_period_id__in=period_ids.values(),
    )
    subjects = Subject.objects.filter(grade_level=student.grade_level).filter(
        Q(is_active=True) | Q(pk__in=grades.values('subject_id'))
    )
    marks = {
        (subject_id, period_id, component): value
        for subject_id, period_id, component, value in grades.filter(
            status__in=('validated', 'locked'),
        ).values_list(
            'subject_id', 'grading_period_id', 'component', 'quarter_grade'
        )
        if 0 < value <= 100
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


@transaction.atomic
def promote_student(student_id, source_year_id, source_grade_id, section_id, actor):
    student = Student.objects.select_for_update().get(pk=student_id)
    if (student.school_year_id, student.grade_level_id) != (source_year_id, source_grade_id):
        raise ValidationError('The student’s placement changed. Review the current profile and try again.')
    if student.status not in ENROLLED_STATUSES:
        raise ValidationError('Only enrolled students can be promoted.')

    section = promotion_sections(student).filter(pk=section_id).first()
    if section is None:
        raise ValidationError('Select a section in the next grade and next school year.')
    if student.promotions.filter(from_school_year_id=source_year_id).exists():
        raise ValidationError('A promotion has already been recorded for this school year.')
    if Grade.objects.filter(student=student, school_year=section.school_year).exclude(
        section=section, subject__grade_level=section.grade_level
    ).exists():
        raise ValidationError('Existing destination-year grades conflict with the selected placement.')

    check_promotion_grades(student)
    StudentPromotion.objects.create(
        student=student, from_grade_level=student.grade_level,
        from_school_year=student.school_year, from_section=student.section,
        to_grade_level=section.grade_level, to_school_year=section.school_year,
        to_section=section, promoted_by=actor,
    )
    AuditLog.objects.create(
        user=actor, action='update', model_name='Student', object_id=str(student.pk),
        description=f'Promoted {student.full_name} from {student.grade_level} ({student.school_year}) '
                    f'to {section} ({section.school_year})',
    )
    student.grade_level = section.grade_level
    student.school_year = section.school_year
    student.section = section
    student.save(update_fields=['grade_level', 'school_year', 'section', 'updated_at'])
