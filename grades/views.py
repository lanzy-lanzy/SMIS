from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.cache import never_cache
from django.db.models import Q, Avg, Count, Subquery, OuterRef, Case, When, Value, IntegerField, DecimalField
from django.utils import timezone
from .models import (
    Grade, GradeSubmission, GradeValidation, weighted_quarter_grade,
    WW_WEIGHT, PT_WEIGHT, AS_WEIGHT,
)
from academics.models import TeacherAssignment, GradingPeriod, SchoolYear, Section, Subject
from students.models import Student
from accounts.models import AuditLog
from accounts.decorators import (
    role_required,
    admin_required,
    registrar_or_admin_required,
    teacher_or_admin_required,
)


@role_required('admin', 'registrar', 'teacher')
def grade_list(request):
    from django.db.models import Count, Q
    
    teacher = request.user
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    current_period = GradingPeriod.objects.filter(is_current=True).first()
    all_periods = GradingPeriod.objects.filter(school_year=current_sy).order_by('order') if current_sy else GradingPeriod.objects.none()
    
    period_filter = request.GET.get('period', '')
    if period_filter:
        selected_period = GradingPeriod.objects.filter(pk=period_filter).first()
    else:
        selected_period = current_period
    
    query = request.GET.get('q', '')
    subject_filter = request.GET.get('subject', '')
    section_filter = request.GET.get('section', '')
    view_type = request.GET.get('view', 'grid')
    
    if request.user.is_teacher:
        assignments = TeacherAssignment.objects.filter(
            teacher=teacher, school_year=current_sy
        ).select_related('subject', 'section', 'section__grade_level').annotate(
            student_count=Count('section__student')
        ).order_by('section__grade_level__level', 'section__name', 'subject__name')
    else:
        assignments = TeacherAssignment.objects.filter(
            school_year=current_sy
        ).select_related('teacher', 'subject', 'section', 'section__grade_level').annotate(
            student_count=Count('section__student')
        ).order_by('section__grade_level__level', 'section__name', 'subject__name')

    if query:
        assignments = assignments.filter(
            Q(teacher__first_name__icontains=query)
            | Q(teacher__last_name__icontains=query)
            | Q(subject__name__icontains=query)
            | Q(subject__code__icontains=query)
        )
    
    if subject_filter:
        assignments = assignments.filter(subject_id=subject_filter)
    if section_filter:
        assignments = assignments.filter(section_id=section_filter)
    
    submissions_status = {}
    if current_sy and selected_period:
        all_submissions = GradeSubmission.objects.filter(
            school_year=current_sy, grading_period=selected_period
        ).order_by('-submitted_at')
        
        for sub in all_submissions:
            key = (sub.teacher_id, sub.subject_id, sub.section_id)
            if key not in submissions_status:
                submissions_status[key] = sub.status
    
    submission_status_by_pk = {}
    for assignment in assignments:
        key = (assignment.teacher_id, assignment.subject_id, assignment.section_id)
        submission_status_by_pk[assignment.pk] = submissions_status.get(key)
    
    total_assignments = assignments.count()
    pending_submissions = GradeSubmission.objects.filter(
        status='pending', school_year=current_sy, grading_period=selected_period
    ).count() if current_sy and selected_period else 0
    validated_grades = Grade.objects.filter(
        status__in=['validated', 'locked'], school_year=current_sy, grading_period=selected_period
    ).count() if current_sy and selected_period else 0
    at_risk_count = Grade.objects.filter(
        status__in=['validated', 'locked'], quarter_grade__lt=75, school_year=current_sy, grading_period=selected_period
    ).values('student').distinct().count() if current_sy and selected_period else 0
    
    paginator = Paginator(assignments, 15)
    page = request.GET.get('page', 1)
    assignments_page = paginator.get_page(page)

    if request.headers.get('HX-Request'):
        template = 'grades/partials/assignment_table.html' if view_type == 'table' else 'grades/partials/assignment_list.html'
        return render(request, template, {
            'assignments': assignments_page,
            'current_period': selected_period,
            'submissions_status': submission_status_by_pk,
            'query': query,
            'subject_filter': subject_filter,
            'section_filter': section_filter,
            'period_filter': period_filter,
        })

    subjects = Subject.objects.all()
    sections = Section.objects.filter(school_year=current_sy) if current_sy else Section.objects.all()

    return render(request, 'grades/grade_list.html', {
        'assignments': assignments_page,
        'current_sy': current_sy,
        'current_period': selected_period,
        'all_periods': all_periods,
        'subjects': subjects,
        'sections': sections,
        'subject_filter': subject_filter,
        'section_filter': section_filter,
        'period_filter': period_filter,
        'query': query,
        'total_assignments': total_assignments,
        'pending_submissions': pending_submissions,
        'validated_grades': validated_grades,
        'at_risk_count': at_risk_count,
        'submissions_status': submission_status_by_pk,
    })


IMMUTABLE_GRADE_STATUSES = ('validated', 'locked')


def _parse_weights(post_data, prefix=''):
    """Read the three category weight inputs (percent) from POST data.

    Returns ``(weights, error)``. Missing inputs fall back to the defaults
    (WW 20 / PT 50 / QA 30). Weights must be non-negative and total 100 so the
    weighted scores aggregate into a proper 0-100 quarter grade.
    """
    try:
        ww = float(post_data.get(f'{prefix}written_weight', '') or WW_WEIGHT)
        pt = float(post_data.get(f'{prefix}performance_weight', '') or PT_WEIGHT)
        as_ = float(post_data.get(f'{prefix}assessment_weight', '') or AS_WEIGHT)
    except (ValueError, TypeError):
        return None, 'Category weights must be valid numbers.'
    if ww < 0 or pt < 0 or as_ < 0:
        return None, 'Category weights cannot be negative.'
    if round(ww + pt + as_, 2) != 100:
        return None, (
            f'Category weights must total 100% (got {ww:g}% + {pt:g}% + {as_:g}% = '
            f'{ww + pt + as_:g}%).'
        )
    return {'ww': ww, 'pt': pt, 'as': as_}, None


def _parse_maxes(post_data, prefix='', fallback=None):
    """Read the class-wide per-item 'highest possible score' from POST data.

    Each item column has its own maximum (the same test for every learner); the
    category maximum that drives the percentage score is the SUM of its items'
    maxima. Returns ``(maxes, error)`` where ``maxes`` carries the per-item lists
    (``ww_items`` etc., ``None`` where nothing was entered) and the summed totals
    (``ww`` etc.). A category with no item values posted falls back to ``fallback``
    (the currently stored maximum) or 100, so a save that omits a category never
    silently resets it.
    """
    fallback = fallback or {}

    def items(cat, n):
        out, any_entered = [], False
        for i in range(1, n + 1):
            raw = post_data.get(f'{prefix}{cat}_highest_{i}', '')
            if str(raw).strip():
                any_entered = True
            try:
                out.append(float(raw) if str(raw).strip() else 0)
            except (ValueError, TypeError):
                return None, False
        if any(v < 0 for v in out):
            return 'negative', any_entered
        return out, any_entered

    ww_items, ww_any = items('written', 5)
    pt_items, pt_any = items('performance', 3)
    as_items, as_any = items('assessment', 3)
    for vals in (ww_items, pt_items, as_items):
        if vals == 'negative':
            return None, 'Highest possible scores must be greater than 0.'
        if vals is None:
            return None, 'Highest possible scores must be valid numbers.'

    def total(vals, any_entered, key):
        s = sum(vals)
        if not any_entered or s <= 0:
            return float(fallback.get(key) or 100)
        return s

    return {
        'ww': total(ww_items, ww_any, 'ww'),
        'pt': total(pt_items, pt_any, 'pt'),
        'qa': total(as_items, as_any, 'qa'),
        'ww_items': ww_items if ww_any else [None] * 5,
        'pt_items': pt_items if pt_any else [None] * 3,
        'as_items': as_items if as_any else [None] * 3,
    }, None


def _weights_from_grades(grades):
    """Derive the class weight config for display from the first encoded grade.

    Weights are stored per Grade row but configured per class, so any row's
    values represent the class setup. Falls back to the model defaults.
    """
    first = next((g for g in grades if g is not None), None)
    if first is None:
        return {
            'ww': float(WW_WEIGHT), 'pt': float(PT_WEIGHT), 'as': float(AS_WEIGHT),
            'total': 100.0,
        }
    ww = float(first.written_work_weight)
    pt = float(first.performance_task_weight)
    as_ = float(first.assessment_weight)
    return {'ww': ww, 'pt': pt, 'as': as_, 'total': round(ww + pt + as_, 2)}


def _maxes_from_grades(grades):
    """Derive the class-wide per-item 'highest possible score' for display.

    Like the weights, the maxima are a single class setting (the same test for
    every learner), so they are read from the first encoded grade. Returns the
    per-item lists (``ww_items`` etc.) plus the summed category totals (``ww``
    etc.). Falls back to 100 (with empty item lists) when nothing is encoded yet.
    """
    empty = {'ww': 100.0, 'pt': 100.0, 'qa': 100.0,
             'ww_items': [None] * 5, 'pt_items': [None] * 3, 'as_items': [None] * 3}
    first = next((g for g in grades if g is not None), None)
    if first is None:
        return empty

    def pick(names):
        return [float(getattr(first, n)) if getattr(first, n) is not None else None
                for n in names]

    return {
        'ww': float(first.written_work_highest or 100),
        'pt': float(first.performance_task_highest or 100),
        'qa': float(first.assessment_highest or 100),
        'ww_items': pick(['written_work_1_highest', 'written_work_2_highest',
                          'written_work_3_highest', 'written_work_4_highest',
                          'written_work_5_highest']),
        'pt_items': pick(['performance_task_1_highest', 'performance_task_2_highest',
                          'performance_task_3_highest']),
        'as_items': pick(['assessment_1_highest', 'assessment_2_highest',
                          'assessment_3_highest']),
    }


def _can_submit(submission):
    """Whether a grade-entry form may (re)submit for validation.

    A submission can only be created or resubmitted when there is no existing
    GradeSubmission yet, or when the Registrar returned it for correction.
    A pending (under review) or approved (validated) submission is frozen, so
    the submit button must be disabled on page load to reflect the true status.
    """
    return submission is None or submission.status == 'returned'


def _locked_period_pks(assignment):
    """Return the pks of grading periods that are fully finalized for the given
    teacher assignment.

    A period counts as locked only when it has at least one grade AND *every*
    grade for that (subject, section, school_year, period) is in an immutable
    state ('validated'/'locked'). Partially-validated quarters are NOT treated as
    finalized, so the Q1 -> Q2 -> ... sequence advances correctly and a quarter is
    only read-only history once the Registrar has validated it end to end.
    """
    rows = (
        Grade.objects.filter(
            subject=assignment.subject,
            section=assignment.section,
            school_year=assignment.school_year,
        )
        .values('grading_period_id')
        .annotate(
            total=Count('id'),
            finalized=Count('id', filter=Q(status__in=IMMUTABLE_GRADE_STATUSES)),
        )
    )
    return {
        row['grading_period_id']
        for row in rows
        if row['total'] and row['total'] == row['finalized']
    }


def _period_access(assignment, all_periods):
    """Strict Q1 -> Q2 -> Q3 -> Q4 sequential gate for a single assignment.

    Returns ``(access, locked_pks)`` where ``access`` maps every grading period
    pk to one of:
      * ``'locked'``  – contains finalized (validated/locked) grades -> read-only history
      * ``'current'`` – the active quarter the teacher may enter (all prior
        quarters finalized, this one not yet finalized)
      * ``'blocked'`` – a later quarter whose prior quarters are not finalized yet
    """
    locked = _locked_period_pks(assignment)
    access = {}
    awaiting_current = True
    for period in all_periods:  # expected to be ordered by `order`
        if period.pk in locked:
            access[period.pk] = 'locked'
        elif awaiting_current:
            access[period.pk] = 'current'
            awaiting_current = False
        else:
            access[period.pk] = 'blocked'
    return access, locked


def _sequence_context(assignment, all_periods, current_period):
    """Build the sequential-lock context shared by the grade entry views.

    Annotates each period object with ``access_state`` so templates can render
    tabs/rows without dict lookups, and derives flags for the current period.
    """
    access, locked = _period_access(assignment, all_periods)
    for period in all_periods:
        period.access_state = access.get(period.pk, 'blocked')

    current_state = access.get(current_period.pk, 'blocked')
    next_actionable = next(
        (p for p in all_periods if access.get(p.pk) == 'current'), None
    )

    return {
        'all_periods': all_periods,
        'period_access': access,
        'locked_periods': locked,
        'current_state': current_state,
        'current_period_locked': current_state == 'locked',
        'current_period_editable': current_state == 'current',
        'current_period_blocked': current_state == 'blocked',
        'prior_periods_locked': [
            p for p in all_periods
            if p.access_state == 'locked' and p.order < current_period.order
        ],
        'next_actionable_period': next_actionable,
    }


def _sequential_save_block(assignment, grading_period):
    """Return a user-facing error string when `grading_period` may not be edited
    for this assignment under the strict Q1 -> Q2 -> Q3 -> Q4 sequence, else None.

    Uses ``_locked_period_pks`` (via ``_period_access``) to detect finalized
    quarters and enforce that a quarter is only editable once every prior
    quarter has been validated by the Registrar.
    """
    all_periods = list(GradingPeriod.objects.filter(
        school_year=assignment.school_year
    ).order_by('order'))
    access, _ = _period_access(assignment, all_periods)
    state = access.get(grading_period.pk, 'blocked')

    if state == 'locked':
        return (
            f'{grading_period.name} has been validated and locked. Finalized grades are '
            'read-only and cannot be modified — contact the Registrar to return it for correction.'
        )
    if state == 'blocked':
        actionable = next((p for p in all_periods if access.get(p.pk) == 'current'), None)
        if actionable:
            return (
                f'You cannot edit {grading_period.name} yet. Complete and submit '
                f'{actionable.name} for validation first — quarters follow the '
                'Q1 → Q2 → Q3 → Q4 sequence.'
            )
        return (
            f'{grading_period.name} is not the active quarter. Quarters must be '
            'completed in order (Q1 → Q2 → Q3 → Q4).'
        )
    return None


@never_cache
@teacher_or_admin_required
def grade_encode(request, assignment_pk):
    assignment = get_object_or_404(TeacherAssignment, pk=assignment_pk)
    
    period_pk = request.GET.get('period') or request.POST.get('period')
    if period_pk:
        grading_period = get_object_or_404(GradingPeriod, pk=period_pk)
    else:
        grading_period = GradingPeriod.objects.filter(is_current=True).first()
    
    if not grading_period:
        messages.error(request, 'No grading period selected.')
        return redirect('grades:grade_list')
    
    if not grading_period.is_submissions_open:
        messages.error(request, 'Grade submissions are not open for this grading period.')
        return redirect('grades:grade_list')
    
    students = Student.objects.filter(
        grade_level=assignment.section.grade_level,
        section=assignment.section,
        status='active'
    )
    
    existing_grades = {}
    for grade in Grade.objects.filter(
        subject=assignment.subject,
        section=assignment.section,
        school_year=assignment.school_year,
        grading_period=grading_period
    ).select_related('student'):
        existing_grades[grade.student_id] = grade
    
    grade_data = []
    for student in students:
        grade = existing_grades.get(student.id)
        grade_data.append({
            'student': student,
            'grade': grade
        })
    
    all_periods = list(GradingPeriod.objects.filter(
        school_year=assignment.school_year
    ).order_by('order'))

    context = {
        'assignment': assignment,
        'current_period': grading_period,
        'grade_data': grade_data,
        'students': students,
        'weights': _weights_from_grades(item['grade'] for item in grade_data),
        'maxes': _maxes_from_grades(item['grade'] for item in grade_data),
    }
    context.update(_sequence_context(assignment, all_periods, grading_period))

    context['submission'] = GradeSubmission.objects.filter(
        teacher=request.user,
        subject=assignment.subject,
        section=assignment.section,
        school_year=assignment.school_year,
        grading_period=grading_period
    ).first()
    context['can_submit'] = _can_submit(context['submission'])

    return render(request, 'grades/grade_encode.html', context)


@teacher_or_admin_required
def grade_save(request, assignment_pk):
    if request.method != 'POST':
        return HttpResponse(status=405)
    
    assignment = get_object_or_404(TeacherAssignment, pk=assignment_pk)
    
    period_pk = request.POST.get('period')
    if period_pk:
        grading_period = get_object_or_404(GradingPeriod, pk=period_pk)
    else:
        grading_period = GradingPeriod.objects.filter(is_current=True).first()

    if not grading_period:
        messages.error(request, 'No grading period selected.')
        return redirect('grades:grade_list')
    
    if not grading_period.is_submissions_open:
        messages.error(request, 'Grade submissions are not open for this grading period.')
        return redirect('grades:grade_list')

    # Backend enforcement of the strict Q1 -> Q2 -> Q3 -> Q4 sequence: reject edits
    # to finalized quarters or to quarters whose prior quarters are not yet validated,
    # even when the current period's submissions are open.
    block_msg = _sequential_save_block(assignment, grading_period)
    if block_msg:
        messages.error(request, block_msg)
        return redirect(f'{reverse("grades:grade_encode", args=[assignment.pk])}?period={grading_period.pk}')

    # Prevent duplicate submissions: once the teacher has submitted for validation
    # (pending) or the Registrar has approved it (approved), the submission is frozen
    # and cannot be re-submitted. Only a missing submission or one that was returned
    # for correction may be (re)submitted.
    existing_submission = GradeSubmission.objects.filter(
        teacher=request.user,
        subject=assignment.subject,
        section=assignment.section,
        school_year=assignment.school_year,
        grading_period=grading_period,
    ).first()
    if existing_submission and existing_submission.status == 'pending':
        messages.warning(
            request,
            f'Grades for {grading_period.name} are already submitted and under review by the Registrar. '
            'Editing and duplicate submissions are locked until a decision is made.'
        )
        return redirect(f'{reverse("grades:grade_encode_select")}?assignment={assignment_pk}&period={grading_period.pk}')
    if existing_submission and existing_submission.status == 'approved':
        messages.warning(
            request,
            f'Grades for {grading_period.name} have already been validated by the Registrar. '
            'Contact the Registrar to return them before editing or resubmitting.'
        )
        return redirect(f'{reverse("grades:grade_encode_select")}?assignment={assignment_pk}&period={grading_period.pk}')

    action = request.POST.get('action', 'draft')

    weights, weight_error = _parse_weights(request.POST)
    if weight_error:
        messages.error(request, weight_error)
        return redirect(f'{reverse("grades:grade_encode", args=[assignment.pk])}?period={grading_period.pk}')

    existing_maxes = _maxes_from_grades(Grade.objects.filter(
        subject=assignment.subject, section=assignment.section,
        school_year=assignment.school_year, grading_period=grading_period,
    ))
    maxes, max_error = _parse_maxes(request.POST, fallback=existing_maxes)
    if max_error:
        messages.error(request, max_error)
        return redirect(f'{reverse("grades:grade_encode", args=[assignment.pk])}?period={grading_period.pk}')

    students = Student.objects.filter(
        grade_level=assignment.section.grade_level,
        section=assignment.section,
        status='active'
    )

    student_ids_with_data = []
    locked_skipped = 0

    for student in students:
        prefix = f'student_{student.id}'
        ww_items = [request.POST.get(f'{prefix}_written_{i}', '') for i in (1, 2, 3, 4, 5)]
        pt_items = [request.POST.get(f'{prefix}_performance_{i}', '') for i in (1, 2, 3)]
        as_items = [request.POST.get(f'{prefix}_assessment_{i}', '') for i in (1, 2, 3)]

        if not any(v.strip() for v in ww_items + pt_items + as_items):
            continue

        existing_grade = Grade.objects.filter(
            student=student,
            subject=assignment.subject,
            grading_period=grading_period,
            school_year=assignment.school_year,
        ).first()

        # Backend enforcement of sequential locking: validated/locked grades are
        # immutable to teachers even while the current period's submissions remain
        # open. They can only be changed after the Registrar returns them.
        if existing_grade and existing_grade.status in IMMUTABLE_GRADE_STATUSES:
            locked_skipped += 1
            continue

        try:
            ww_vals = [float(v) if v.strip() else 0 for v in ww_items]
            pt_vals = [float(v) if v.strip() else 0 for v in pt_items]
            as_vals = [float(v) if v.strip() else 0 for v in as_items]
        except (ValueError, TypeError):
            messages.error(request, f'Invalid grade values for {student.full_name}.')
            continue

        # Class-wide maxima (configured once) apply to every learner.
        written_highest = maxes['ww']
        performance_highest = maxes['pt']
        assessment_highest = maxes['qa']

        written = sum(ww_vals)
        performance = sum(pt_vals)
        assessment = sum(as_vals)

        if any(v < 0 for v in ww_vals + pt_vals + as_vals):
            messages.error(request, f'Item scores for {student.full_name} cannot be negative.')
            continue

        if not (written <= written_highest and performance <= performance_highest and assessment <= assessment_highest):
            messages.error(request, f'Total scores for {student.full_name} cannot exceed their highest possible score.')
            continue

        student_ids_with_data.append(student.id)

        quarter_grade = weighted_quarter_grade(
            written, written_highest,
            performance, performance_highest,
            assessment, assessment_highest,
            weights['ww'], weights['pt'], weights['as'],
        )
        remarks = 'Passed' if quarter_grade >= 75 else ('Incomplete' if quarter_grade >= 60 else 'Failed')
        
        status = 'submitted' if action == 'submit' else 'draft'

        grade, created = Grade.objects.update_or_create(
            student=student,
            subject=assignment.subject,
            grading_period=grading_period,
            school_year=assignment.school_year,
            defaults={
                'section': assignment.section,
                'written_work_1': ww_vals[0], 'written_work_2': ww_vals[1], 'written_work_3': ww_vals[2],
                'written_work_4': ww_vals[3], 'written_work_5': ww_vals[4],
                'written_work_1_highest': maxes['ww_items'][0], 'written_work_2_highest': maxes['ww_items'][1],
                'written_work_3_highest': maxes['ww_items'][2], 'written_work_4_highest': maxes['ww_items'][3],
                'written_work_5_highest': maxes['ww_items'][4],
                'written_work': written,
                'written_work_highest': written_highest,
                'performance_task_1': pt_vals[0], 'performance_task_2': pt_vals[1], 'performance_task_3': pt_vals[2],
                'performance_task_1_highest': maxes['pt_items'][0], 'performance_task_2_highest': maxes['pt_items'][1],
                'performance_task_3_highest': maxes['pt_items'][2],
                'performance_task': performance,
                'performance_task_highest': performance_highest,
                'assessment_1': as_vals[0], 'assessment_2': as_vals[1], 'assessment_3': as_vals[2],
                'assessment_1_highest': maxes['as_items'][0], 'assessment_2_highest': maxes['as_items'][1],
                'assessment_3_highest': maxes['as_items'][2],
                'assessment': assessment,
                'assessment_highest': assessment_highest,
                'written_work_weight': weights['ww'],
                'performance_task_weight': weights['pt'],
                'assessment_weight': weights['as'],
                'quarter_grade': quarter_grade,
                'final_grade': quarter_grade,
                'remarks': remarks,
                'status': status,
                'encoded_by': existing_grade.encoded_by if existing_grade else request.user,
                'updated_by': request.user,
            }
        )
        
        action_desc = 'grade_encode' if created else 'grade_update'
        AuditLog.objects.create(
            user=request.user,
            action=action_desc,
            model_name='Grade',
            object_id=str(grade.id),
            description=f'{"Encoded" if created else "Updated"} grade for {student.full_name} in {assignment.subject}'
        )
    
    if locked_skipped:
        messages.warning(
            request,
            f'{locked_skipped} validated grade(s) are locked and could not be modified. '
            'Contact the Registrar to return them for correction.'
        )
    
    if action == 'submit':
        submission, created = GradeSubmission.objects.get_or_create(
            teacher=request.user,
            subject=assignment.subject,
            section=assignment.section,
            school_year=assignment.school_year,
            grading_period=grading_period,
            defaults={'status': 'pending'}
        )
        if not created:
            # Resubmission after the Registrar returned the grades: reset the
            # status so it immediately reflects as under review for the Registrar.
            submission.status = 'pending'
            submission.reviewed_at = None
            submission.submitted_at = timezone.now()
            submission.save(update_fields=['status', 'reviewed_at', 'submitted_at'])
        Grade.objects.filter(
            student__id__in=student_ids_with_data,
            subject=assignment.subject,
            section=assignment.section,
            school_year=assignment.school_year,
            grading_period=grading_period,
            status='draft'
        ).update(status='submitted')
        
        AuditLog.objects.create(
            user=request.user,
            action='grade_submit',
            model_name='GradeSubmission',
            object_id=str(submission.id),
            description=f'Submitted grades for {assignment.subject} - {assignment.section} ({grading_period.name})'
        )
        messages.success(request, f'Grades submitted for {grading_period.name}. Status: Under Review — awaiting Registrar validation.')
    else:
        messages.success(request, 'Grades saved as draft.')
    
    return redirect(f'{reverse("grades:grade_encode_select")}?assignment={assignment_pk}&period={grading_period.pk}')


@role_required('admin', 'registrar', 'teacher')
def submission_list(request):
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    
    period_filter = request.GET.get('period', '')
    selected_period = None
    if period_filter:
        selected_period = GradingPeriod.objects.filter(pk=period_filter).first()
    
    if request.user.is_teacher:
        submissions = GradeSubmission.objects.filter(
            teacher=request.user, school_year=current_sy
        ).select_related('subject', 'section', 'grading_period')
    elif request.user.is_registrar or request.user.is_admin:
        submissions = GradeSubmission.objects.filter(
            school_year=current_sy
        ).select_related('teacher', 'subject', 'section', 'grading_period')
    else:
        submissions = GradeSubmission.objects.none()
    
    if selected_period:
        submissions = submissions.filter(grading_period=selected_period)
    
    # Search across teacher, subject and section (composes with the period filter).
    query = request.GET.get('q', '')
    if query:
        submissions = submissions.filter(
            Q(teacher__first_name__icontains=query)
            | Q(teacher__last_name__icontains=query)
            | Q(subject__name__icontains=query)
            | Q(subject__code__icontains=query)
            | Q(section__name__icontains=query)
        )
    
    # Status summary is computed BEFORE the status filter so the triage cards
    # always reflect the full workload for the current period/search selection.
    summary_counts = {'pending': 0, 'approved': 0, 'returned': 0}
    for row in submissions.values('status').annotate(c=Count('id')):
        if row['status'] in summary_counts:
            summary_counts[row['status']] = row['c']
    summary_total = sum(summary_counts.values())
    
    # Quarter-completion detection for the Registrar's "advance calendar" prompt.
    # Evaluated for the selected quarter (or the current one) independent of the
    # status/search filters: it is complete when every submission is approved
    # (nothing pending or returned remains) and at least one submission exists.
    period_completion = None
    if not request.user.is_teacher and current_sy:
        eval_period = selected_period or GradingPeriod.objects.filter(
            school_year=current_sy, is_current=True
        ).first()
        if eval_period:
            period_subs = GradeSubmission.objects.filter(
                school_year=current_sy, grading_period=eval_period
            )
            total = period_subs.count()
            unresolved = period_subs.filter(status__in=['pending', 'returned']).count()
            if total > 0 and unresolved == 0:
                next_period = GradingPeriod.objects.filter(
                    school_year=current_sy, order__gt=eval_period.order
                ).order_by('order').first()
                period_completion = {
                    'period': eval_period,
                    'total': total,
                    'next_period': next_period,
                }
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        submissions = submissions.filter(status=status_filter)
    
    # Per-submission context (student count, class average, at-risk count) via a
    # single correlated Subquery — avoids N+1 lookups in the template.
    grade_stats = (
        Grade.objects.filter(
            subject=OuterRef('subject'),
            section=OuterRef('section'),
            school_year=OuterRef('school_year'),
            grading_period=OuterRef('grading_period'),
        )
        .values('subject')
        .annotate(
            n=Count('id'),
            avg=Avg('quarter_grade'),
            at_risk=Count('id', filter=Q(quarter_grade__lt=75)),
        )
    )
    submissions = submissions.annotate(
        student_count=Subquery(grade_stats.values('n'), output_field=IntegerField()),
        class_avg=Subquery(grade_stats.values('avg'), output_field=DecimalField(max_digits=5, decimal_places=2)),
        at_risk_count=Subquery(grade_stats.values('at_risk'), output_field=IntegerField()),
        # Triage ordering: pending first, then returned, then approved; oldest
        # submissions surface before newer ones within each status bucket.
        status_priority=Case(
            When(status='pending', then=Value(0)),
            When(status='returned', then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        ),
    ).order_by('status_priority', 'submitted_at')
    
    all_periods = GradingPeriod.objects.filter(school_year=current_sy).order_by('order') if current_sy else GradingPeriod.objects.none()

    paginator = Paginator(submissions, 20)
    page = request.GET.get('page', 1)
    submissions_page = paginator.get_page(page)

    context = {
        'submissions': submissions_page,
        'status_filter': status_filter,
        'status_choices': GradeSubmission.STATUS_CHOICES,
        'all_periods': all_periods,
        'selected_period': selected_period,
        'period_filter': period_filter,
        'query': query,
        'summary_counts': summary_counts,
        'summary_total': summary_total,
        'period_completion': period_completion,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'grades/partials/submission_table.html', context)

    return render(request, 'grades/submission_list.html', context)


@registrar_or_admin_required
def submission_validate(request, pk):
    submission = get_object_or_404(GradeSubmission, pk=pk)

    if submission.status != 'pending':
        messages.error(request, 'This submission is not pending review.')
        return redirect('grades:submission_list')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        remarks = request.POST.get('remarks', '')
        
        if action == 'validate':
            submission.status = 'approved'
            submission.reviewed_at = timezone.now()
            submission.remarks = remarks
            submission.save()
            
            # Approving finalizes the entire class scope for this period, so any
            # grade still in draft/submitted/returned is validated together. This
            # keeps Grade.status in sync with the approved GradeSubmission.
            Grade.objects.filter(
                subject=submission.subject,
                section=submission.section,
                school_year=submission.school_year,
                grading_period=submission.grading_period,
                status__in=['draft', 'submitted', 'returned']
            ).update(status='validated')
            
            GradeValidation.objects.filter(submission=submission).delete()
            GradeValidation.objects.create(
                submission=submission,
                validated_by=request.user,
                status='approved',
                remarks=remarks
            )
            
            AuditLog.objects.create(
                user=request.user,
                action='grade_validate',
                model_name='GradeSubmission',
                object_id=str(submission.id),
                description=f'Validated grades for {submission.subject} - {submission.section}'
            )
            messages.success(request, 'Grades validated successfully.')
        
        elif action == 'return':
            submission.status = 'returned'
            submission.reviewed_at = timezone.now()
            submission.remarks = remarks
            submission.save()
            
            # Returning reopens the class scope: every not-yet-finalized grade
            # (draft/submitted) becomes returned so the teacher can edit and resubmit.
            Grade.objects.filter(
                subject=submission.subject,
                section=submission.section,
                school_year=submission.school_year,
                grading_period=submission.grading_period,
                status__in=['draft', 'submitted']
            ).update(status='returned')
            
            GradeValidation.objects.filter(submission=submission).delete()
            GradeValidation.objects.create(
                submission=submission,
                validated_by=request.user,
                status='returned',
                remarks=remarks
            )
            
            AuditLog.objects.create(
                user=request.user,
                action='grade_return',
                model_name='GradeSubmission',
                object_id=str(submission.id),
                description=f'Returned grades for {submission.subject} - {submission.section}: {remarks}'
            )
            messages.success(request, 'Grades returned for correction.')
        
        return redirect('grades:submission_list')
    
    grades = Grade.objects.filter(
        subject=submission.subject,
        section=submission.section,
        school_year=submission.school_year,
        grading_period=submission.grading_period
    ).select_related('student')
    
    return render(request, 'grades/submission_validate.html', {
        'submission': submission,
        'grades': grades
    })


@registrar_or_admin_required
def submission_delete(request, pk):
    """Delete a grade submission (and its validation record). Grade rows themselves
    are not linked to the submission and remain untouched."""
    if request.method != 'POST':
        return HttpResponse(status=405)

    submission = get_object_or_404(GradeSubmission, pk=pk)
    description = (f'{submission.teacher.get_full_name()} - {submission.subject} '
                   f'- {submission.section} - {submission.grading_period}')
    submission.delete()  # cascades to the related GradeValidation

    AuditLog.objects.create(
        user=request.user,
        action='delete',
        model_name='GradeSubmission',
        object_id=str(pk),
        description=f'Deleted grade submission: {description}',
    )
    messages.success(request, 'Submission deleted.')
    return redirect(request.POST.get('next') or 'grades:submission_list')


@registrar_or_admin_required
def grade_export(request):
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="grades_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student', 'LRN', 'Subject', 'Section', 'Grade Level', 'School Year', 'Grading Period', 'WW 1', 'WW 2', 'WW 3', 'WW Total', 'WW Highest', 'PT 1', 'PT 2', 'PT 3', 'PT Total', 'PT Highest', 'QA 1', 'QA 2', 'QA 3', 'QA Total', 'QA Highest', 'Quarter Grade', 'Final Grade', 'Remarks', 'Status'])
    
    grades = Grade.objects.select_related(
        'student', 'subject', 'section', 'section__grade_level', 'school_year', 'grading_period'
    ).all()
    
    for grade in grades:
        writer.writerow([
            grade.student.full_name,
            grade.student.lrn,
            grade.subject.name,
            grade.section.name,
            grade.section.grade_level,
            grade.school_year.name,
            grade.grading_period.name,
            grade.written_work_1, grade.written_work_2, grade.written_work_3,
            grade.written_work,
            grade.written_work_highest,
            grade.performance_task_1, grade.performance_task_2, grade.performance_task_3,
            grade.performance_task,
            grade.performance_task_highest,
            grade.assessment_1, grade.assessment_2, grade.assessment_3,
            grade.assessment,
            grade.assessment_highest,
            grade.quarter_grade,
            grade.final_grade,
            grade.remarks,
            grade.status,
        ])
    
    return response


@teacher_or_admin_required
def encode_modal(request):
    """Returns a modal listing the teacher's assignments for encoding grades for a selected period."""
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    current_period = GradingPeriod.objects.filter(is_current=True).first()
    
    period_pk = request.GET.get('period')
    if period_pk:
        grading_period = get_object_or_404(GradingPeriod, pk=period_pk)
    else:
        grading_period = current_period
    
    if request.user.is_teacher:
        assignments = TeacherAssignment.objects.filter(
            teacher=request.user, school_year=current_sy
        ).select_related('subject', 'section', 'section__grade_level')
    else:
        assignments = TeacherAssignment.objects.filter(
            school_year=current_sy
        ).select_related('teacher', 'subject', 'section', 'section__grade_level')
    
    # Get submission statuses for the selected period
    submissions_status = {}
    if current_sy and grading_period:
        for sub in GradeSubmission.objects.filter(
            school_year=current_sy, grading_period=grading_period
        ).order_by('-submitted_at'):
            key = (sub.teacher_id, sub.subject_id, sub.section_id)
            if key not in submissions_status:
                submissions_status[key] = sub.status
    
    submission_status_by_pk = {}
    for assignment in assignments:
        key = (assignment.teacher_id, assignment.subject_id, assignment.section_id)
        submission_status_by_pk[assignment.pk] = submissions_status.get(key)
    
    return render(request, 'grades/partials/encode_modal.html', {
        'assignments': assignments,
        'grading_period': grading_period,
        'submission_status_by_pk': submission_status_by_pk,
    })


@never_cache
@teacher_or_admin_required
def grade_encode_select(request):
    """Teacher selects a subject from dropdown and dynamically loads the grade entry table."""
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    current_period = GradingPeriod.objects.filter(is_current=True).first()
    all_periods = list(GradingPeriod.objects.filter(school_year=current_sy).order_by('order')) if current_sy else []
    
    period_pk = request.GET.get('period')
    if period_pk:
        grading_period = get_object_or_404(GradingPeriod, pk=period_pk)
    else:
        grading_period = current_period
    
    if not grading_period:
        messages.error(request, 'No grading period selected.')
        return redirect('grades:grade_list')
    
    if not grading_period.is_submissions_open:
        messages.error(request, 'Grade submissions are not open for this grading period.')
        return redirect('grades:grade_list')
    
    if request.user.is_teacher:
        assignments = TeacherAssignment.objects.filter(
            teacher=request.user, school_year=current_sy
        ).select_related('subject', 'section', 'section__grade_level')
    else:
        assignments = TeacherAssignment.objects.filter(
            school_year=current_sy
        ).select_related('teacher', 'subject', 'section', 'section__grade_level')
    
    selected_assignment = None
    assignment_pk = request.GET.get('assignment')
    if assignment_pk:
        selected_assignment = get_object_or_404(TeacherAssignment, pk=assignment_pk)
        # Ensure teacher can only access their own assignments
        if request.user.is_teacher and selected_assignment.teacher != request.user:
            messages.error(request, 'Access denied.')
            return redirect('grades:grade_encode_select')
    
    context = {
        'assignments': assignments,
        'grading_period': grading_period,
        'all_periods': all_periods,
        'selected_assignment': selected_assignment,
    }
    
    if selected_assignment:
        context.update(_sequence_context(selected_assignment, all_periods, grading_period))

        students = Student.objects.filter(
            grade_level=selected_assignment.section.grade_level,
            section=selected_assignment.section,
            status='active'
        ).order_by('last_name', 'first_name')
        
        existing_grades = {
            g.student_id: g for g in Grade.objects.filter(
                subject=selected_assignment.subject,
                section=selected_assignment.section,
                school_year=selected_assignment.school_year,
                grading_period=grading_period
            ).select_related('student')
        }
        
        grade_data = []
        for student in students:
            grade_data.append({
                'student': student,
                'grade': existing_grades.get(student.id)
            })

        weights = _weights_from_grades(item['grade'] for item in grade_data)
        maxes = _maxes_from_grades(item['grade'] for item in grade_data)
        
        submission = GradeSubmission.objects.filter(
            teacher=request.user,
            subject=selected_assignment.subject,
            section=selected_assignment.section,
            school_year=selected_assignment.school_year,
            grading_period=grading_period
        ).first()
        
        context.update({
            'students': students,
            'grade_data': grade_data,
            'weights': weights,
            'maxes': maxes,
            'submission': submission,
            'can_submit': _can_submit(submission),
        })
        
        if request.headers.get('HX-Request'):
            return render(request, 'grades/partials/grade_encode_select_table.html', context)
    
    return render(request, 'grades/grade_encode_select.html', context)


@never_cache
@teacher_or_admin_required
def grade_encode_all(request):
    """Show all teacher assignments with students so teacher can enter all grades at once."""
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    current_period = GradingPeriod.objects.filter(is_current=True).first()
    all_periods = list(GradingPeriod.objects.filter(school_year=current_sy).order_by('order')) if current_sy else []
    
    period_pk = request.GET.get('period')
    if period_pk:
        grading_period = get_object_or_404(GradingPeriod, pk=period_pk)
    else:
        grading_period = current_period
    
    if not grading_period:
        messages.error(request, 'No grading period selected.')
        return redirect('grades:grade_list')
    
    if not grading_period.is_submissions_open:
        messages.error(request, 'Grade submissions are not open for this grading period.')
        return redirect('grades:grade_list')
    
    if request.user.is_teacher:
        assignments = TeacherAssignment.objects.filter(
            teacher=request.user, school_year=current_sy
        ).select_related('subject', 'section', 'section__grade_level')
    else:
        assignments = TeacherAssignment.objects.filter(
            school_year=current_sy
        ).select_related('teacher', 'subject', 'section', 'section__grade_level')
    
    # Build data structure: assignment -> list of {student, grade}
    # Also compute the strict Q1->Q4 sequential state per assignment and aggregate
    # a shared state for the period tabs at the top of the page.
    assignment_data = []
    locked_periods = set()
    total_assignments = 0
    period_locked_count = {p.pk: 0 for p in all_periods}
    period_has_current = {p.pk: False for p in all_periods}

    for assignment in assignments:
        total_assignments += 1
        access, assignment_locked = _period_access(assignment, all_periods)
        locked_periods |= assignment_locked
        for p in all_periods:
            if access.get(p.pk) == 'locked':
                period_locked_count[p.pk] += 1
            elif access.get(p.pk) == 'current':
                period_has_current[p.pk] = True

        students = Student.objects.filter(
            grade_level=assignment.section.grade_level,
            section=assignment.section,
            status='active'
        ).order_by('last_name', 'first_name')
        
        existing_grades = {
            g.student_id: g for g in Grade.objects.filter(
                subject=assignment.subject,
                section=assignment.section,
                school_year=assignment.school_year,
                grading_period=grading_period
            ).select_related('student')
        }
        
        student_grades = []
        for student in students:
            student_grades.append({
                'student': student,
                'grade': existing_grades.get(student.id)
            })

        weights = _weights_from_grades(sg['grade'] for sg in student_grades)
        maxes = _maxes_from_grades(sg['grade'] for sg in student_grades)
        
        submission = GradeSubmission.objects.filter(
            teacher=request.user,
            subject=assignment.subject,
            section=assignment.section,
            school_year=assignment.school_year,
            grading_period=grading_period
        ).first()

        current_state = access.get(grading_period.pk, 'blocked')
        assignment_data.append({
            'assignment': assignment,
            'student_grades': student_grades,
            'weights': weights,
            'maxes': maxes,
            'submission': submission,
            'locked': current_state == 'locked',
            'blocked': current_state == 'blocked',
            'editable': current_state == 'current',
            'can_submit': current_state == 'current' and _can_submit(submission),
        })

    # Aggregate tab state across all of the teacher's assignments.
    for p in all_periods:
        if total_assignments and period_locked_count[p.pk] == total_assignments:
            p.access_state = 'locked'
        elif period_has_current[p.pk]:
            p.access_state = 'current'
        else:
            p.access_state = 'blocked'

    current_all_locked = total_assignments > 0 and period_locked_count.get(grading_period.pk, 0) == total_assignments
    next_actionable = next((p for p in all_periods if p.access_state == 'current'), None)
    any_submittable = any(item['can_submit'] for item in assignment_data)

    return render(request, 'grades/grade_encode_all.html', {
        'grading_period': grading_period,
        'all_periods': all_periods,
        'assignment_data': assignment_data,
        'locked_periods': locked_periods,
        'any_submittable': any_submittable,
        'current_period_locked': current_all_locked,
        'current_period_editable': period_has_current.get(grading_period.pk, False),
        'current_period_blocked': (not current_all_locked) and not period_has_current.get(grading_period.pk, False),
        'next_actionable_period': next_actionable,
        'prior_periods_locked': [
            p for p in all_periods
            if p.access_state == 'locked' and p.order < grading_period.order
        ],
    })


@teacher_or_admin_required
def grade_save_all(request):
    """Save grades for all teacher assignments at once."""
    if request.method != 'POST':
        return HttpResponse(status=405)
    
    period_pk = request.POST.get('period')
    if period_pk:
        grading_period = get_object_or_404(GradingPeriod, pk=period_pk)
    else:
        grading_period = GradingPeriod.objects.filter(is_current=True).first()
    
    if not grading_period:
        messages.error(request, 'No grading period selected.')
        return redirect('grades:grade_list')
    
    if not grading_period.is_submissions_open:
        messages.error(request, 'Grade submissions are not open for this grading period.')
        return redirect('grades:grade_list')
    
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    
    if request.user.is_teacher:
        assignments = TeacherAssignment.objects.filter(
            teacher=request.user, school_year=current_sy
        ).select_related('subject', 'section')
    else:
        assignments = TeacherAssignment.objects.filter(
            school_year=current_sy
        ).select_related('subject', 'section')
    
    action = request.POST.get('action', 'draft')
    saved_assignments = []
    locked_skipped_total = 0
    blocked_assignments = 0
    under_review_skipped = 0
    
    for assignment in assignments:
        # Backend enforcement of the strict Q1 -> Q2 -> Q3 -> Q4 sequence: skip any
        # assignment whose target quarter is finalized or out of sequence.
        if _sequential_save_block(assignment, grading_period):
            blocked_assignments += 1
            continue

        # Prevent duplicate submissions: skip assignments already under review
        # (pending) or already validated (approved). Only missing/returned may submit.
        under_review = GradeSubmission.objects.filter(
            teacher=request.user,
            subject=assignment.subject,
            section=assignment.section,
            school_year=assignment.school_year,
            grading_period=grading_period,
            status__in=['pending', 'approved'],
        ).exists()
        if under_review:
            under_review_skipped += 1
            continue

        students = Student.objects.filter(
            grade_level=assignment.section.grade_level,
            section=assignment.section,
            status='active'
        )
        
        # Per-class weight config (each assignment's table posts its own weights).
        weights, weight_error = _parse_weights(request.POST, prefix=f'assignment_{assignment.pk}_')
        if weight_error:
            messages.error(request, f'{assignment.subject} — {assignment.section}: {weight_error}')
            continue

        # Class-wide 'highest possible score' per category, posted once per
        # assignment's table and applied to every learner (mirrors grade_save).
        existing_maxes = _maxes_from_grades(Grade.objects.filter(
            subject=assignment.subject, section=assignment.section,
            school_year=assignment.school_year, grading_period=grading_period,
        ))
        maxes, max_error = _parse_maxes(request.POST, prefix=f'assignment_{assignment.pk}_', fallback=existing_maxes)
        if max_error:
            messages.error(request, f'{assignment.subject} — {assignment.section}: {max_error}')
            continue
        written_highest = maxes['ww']
        performance_highest = maxes['pt']
        assessment_highest = maxes['qa']

        student_ids_with_data = []
        has_data = False
        
        for student in students:
            prefix = f'assignment_{assignment.pk}_student_{student.id}'
            ww_items = [request.POST.get(f'{prefix}_written_{i}', '') for i in (1, 2, 3, 4, 5)]
            pt_items = [request.POST.get(f'{prefix}_performance_{i}', '') for i in (1, 2, 3)]
            as_items = [request.POST.get(f'{prefix}_assessment_{i}', '') for i in (1, 2, 3)]
            
            if not any(v.strip() for v in ww_items + pt_items + as_items):
                continue
            
            existing_grade = Grade.objects.filter(
                student=student,
                subject=assignment.subject,
                grading_period=grading_period,
                school_year=assignment.school_year,
            ).first()
            
            # Backend enforcement of sequential locking: validated/locked grades
            # stay immutable to teachers even while submissions are open.
            if existing_grade and existing_grade.status in IMMUTABLE_GRADE_STATUSES:
                locked_skipped_total += 1
                continue
            
            try:
                ww_vals = [float(v) if v.strip() else 0 for v in ww_items]
                pt_vals = [float(v) if v.strip() else 0 for v in pt_items]
                as_vals = [float(v) if v.strip() else 0 for v in as_items]
            except (ValueError, TypeError):
                messages.error(request, f'Invalid grade values for {student.full_name} in {assignment.subject}.')
                continue
            
            written = sum(ww_vals)
            performance = sum(pt_vals)
            assessment = sum(as_vals)
            
            if any(v < 0 for v in ww_vals + pt_vals + as_vals):
                messages.error(request, f'Item scores for {student.full_name} in {assignment.subject} cannot be negative.')
                continue
            
            if not (written <= written_highest and performance <= performance_highest and assessment <= assessment_highest):
                messages.error(request, f'Total scores for {student.full_name} in {assignment.subject} cannot exceed their highest possible score.')
                continue
            
            student_ids_with_data.append(student.id)
            has_data = True
            
            quarter_grade = weighted_quarter_grade(
                written, written_highest,
                performance, performance_highest,
                assessment, assessment_highest,
                weights['ww'], weights['pt'], weights['as'],
            )
            remarks = 'Passed' if quarter_grade >= 75 else ('Incomplete' if quarter_grade >= 60 else 'Failed')
            status = 'submitted' if action == 'submit' else 'draft'
            
            grade, created = Grade.objects.update_or_create(
                student=student,
                subject=assignment.subject,
                grading_period=grading_period,
                school_year=assignment.school_year,
                defaults={
                    'section': assignment.section,
                    'written_work_1': ww_vals[0], 'written_work_2': ww_vals[1], 'written_work_3': ww_vals[2],
                    'written_work_4': ww_vals[3], 'written_work_5': ww_vals[4],
                    'written_work_1_highest': maxes['ww_items'][0], 'written_work_2_highest': maxes['ww_items'][1],
                    'written_work_3_highest': maxes['ww_items'][2], 'written_work_4_highest': maxes['ww_items'][3],
                    'written_work_5_highest': maxes['ww_items'][4],
                    'written_work': written,
                    'written_work_highest': written_highest,
                    'performance_task_1': pt_vals[0], 'performance_task_2': pt_vals[1], 'performance_task_3': pt_vals[2],
                    'performance_task_1_highest': maxes['pt_items'][0], 'performance_task_2_highest': maxes['pt_items'][1],
                    'performance_task_3_highest': maxes['pt_items'][2],
                    'performance_task': performance,
                    'performance_task_highest': performance_highest,
                    'assessment_1': as_vals[0], 'assessment_2': as_vals[1], 'assessment_3': as_vals[2],
                    'assessment_1_highest': maxes['as_items'][0], 'assessment_2_highest': maxes['as_items'][1],
                    'assessment_3_highest': maxes['as_items'][2],
                    'assessment': assessment,
                    'assessment_highest': assessment_highest,
                    'written_work_weight': weights['ww'],
                    'performance_task_weight': weights['pt'],
                    'assessment_weight': weights['as'],
                    'quarter_grade': quarter_grade,
                    'final_grade': quarter_grade,
                    'remarks': remarks,
                    'status': status,
                    'encoded_by': existing_grade.encoded_by if existing_grade else request.user,
                    'updated_by': request.user,
                }
            )

            action_desc = 'grade_encode' if created else 'grade_update'
            AuditLog.objects.create(
                user=request.user,
                action=action_desc,
                model_name='Grade',
                object_id=str(grade.id),
                description=f'{"Encoded" if created else "Updated"} grade for {student.full_name} in {assignment.subject}'
            )
        
        if action == 'submit' and has_data:
            submission, created = GradeSubmission.objects.get_or_create(
                teacher=request.user,
                subject=assignment.subject,
                section=assignment.section,
                school_year=assignment.school_year,
                grading_period=grading_period,
                defaults={'status': 'pending'}
            )
            if not created:
                # Resubmission after return: reset so it immediately shows under review.
                submission.status = 'pending'
                submission.reviewed_at = None
                submission.submitted_at = timezone.now()
                submission.save(update_fields=['status', 'reviewed_at', 'submitted_at'])
            Grade.objects.filter(
                student__id__in=student_ids_with_data,
                subject=assignment.subject,
                section=assignment.section,
                school_year=assignment.school_year,
                grading_period=grading_period,
                status='draft'
            ).update(status='submitted')
            
            AuditLog.objects.create(
                user=request.user,
                action='grade_submit',
                model_name='GradeSubmission',
                object_id=str(submission.id),
                description=f'Submitted grades for {assignment.subject} - {assignment.section} ({grading_period.name})'
            )
            saved_assignments.append(assignment.subject.name)
    
    if locked_skipped_total:
        messages.warning(
            request,
            f'{locked_skipped_total} validated grade(s) are locked and could not be modified. '
            'Contact the Registrar to return them for correction.'
        )
    
    if under_review_skipped:
        messages.warning(
            request,
            f'{under_review_skipped} class(es) were skipped for {grading_period.name}: '
            'already submitted and under review by the Registrar. Duplicate submissions are not allowed.'
        )
    
    if blocked_assignments:
        messages.warning(
            request,
            f'{blocked_assignments} class(es) were skipped for {grading_period.name}: finalized or '
            'not yet reachable in the Q1 → Q2 → Q3 → Q4 sequence.'
        )
    
    if action == 'submit':
        if saved_assignments:
            messages.success(request, f'Grades submitted for {len(saved_assignments)} subject(s) for {grading_period.name}.')
        else:
            messages.info(request, 'No grades were submitted. Make sure to enter grades before submitting.')
    else:
        messages.success(request, 'Grades saved as draft.')
    
    return redirect(f'{reverse("grades:grade_encode_all")}?period={grading_period.pk}')
