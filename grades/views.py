from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count
from django.utils import timezone
from .models import Grade, GradeSubmission, GradeValidation
from academics.models import TeacherAssignment, GradingPeriod, SchoolYear, Section, Subject
from students.models import Student
from accounts.models import AuditLog
from accounts.decorators import (
    role_required,
    admin_required,
    registrar_or_admin_required,
    teacher_or_admin_required,
)


@role_required('admin', 'registrar', 'teacher', 'principal')
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
    
    all_periods = GradingPeriod.objects.filter(
        school_year=assignment.school_year
    ).order_by('order')
    
    submission = GradeSubmission.objects.filter(
        teacher=request.user,
        subject=assignment.subject,
        section=assignment.section,
        school_year=assignment.school_year,
        grading_period=grading_period
    ).first()
    
    return render(request, 'grades/grade_encode.html', {
        'assignment': assignment,
        'current_period': grading_period,
        'all_periods': all_periods,
        'grade_data': grade_data,
        'students': students,
        'submission': submission,
    })


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

    action = request.POST.get('action', 'draft')
    
    students = Student.objects.filter(
        grade_level=assignment.section.grade_level,
        section=assignment.section,
        status='active'
    )
    
    student_ids_with_data = []

    for student in students:
        prefix = f'student_{student.id}'
        written = request.POST.get(f'{prefix}_written', '')
        performance = request.POST.get(f'{prefix}_performance', '')
        assessment = request.POST.get(f'{prefix}_assessment', '')

        if written == '' and performance == '' and assessment == '':
            continue

        try:
            written = float(written) if written else 0
            performance = float(performance) if performance else 0
            assessment = float(assessment) if assessment else 0
        except (ValueError, TypeError):
            messages.error(request, f'Invalid grade values for {student.full_name}.')
            continue

        if not (0 <= written <= 100 and 0 <= performance <= 100 and 0 <= assessment <= 100):
            messages.error(request, f'Grade values for {student.full_name} must be between 0 and 100.')
            continue

        student_ids_with_data.append(student.id)

        quarter_grade = (written + performance + assessment) / 3
        remarks = 'Passed' if quarter_grade >= 75 else ('Incomplete' if quarter_grade >= 60 else 'Failed')
        
        status = 'submitted' if action == 'submit' else 'draft'

        existing_grade = Grade.objects.filter(
            student=student,
            subject=assignment.subject,
            grading_period=grading_period,
            school_year=assignment.school_year,
        ).first()
        
        grade, created = Grade.objects.update_or_create(
            student=student,
            subject=assignment.subject,
            grading_period=grading_period,
            school_year=assignment.school_year,
            defaults={
                'section': assignment.section,
                'written_work': written,
                'performance_task': performance,
                'assessment': assessment,
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
    
    if action == 'submit':
        submission, _ = GradeSubmission.objects.get_or_create(
            teacher=request.user,
            subject=assignment.subject,
            section=assignment.section,
            school_year=assignment.school_year,
            grading_period=grading_period,
            defaults={'status': 'pending'}
        )
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
        messages.success(request, f'Grades submitted for {grading_period.name}.')
    else:
        messages.success(request, 'Grades saved as draft.')
    
    return redirect(f'{reverse("grades:grade_encode_select")}?assignment={assignment_pk}&period={grading_period.pk}')


@role_required('admin', 'registrar', 'teacher', 'principal')
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
    elif request.user.is_registrar or request.user.is_admin or request.user.is_principal:
        submissions = GradeSubmission.objects.filter(
            school_year=current_sy
        ).select_related('teacher', 'subject', 'section', 'grading_period')
    else:
        submissions = GradeSubmission.objects.none()
    
    if selected_period:
        submissions = submissions.filter(grading_period=selected_period)
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        submissions = submissions.filter(status=status_filter)
    
    all_periods = GradingPeriod.objects.filter(school_year=current_sy).order_by('order') if current_sy else GradingPeriod.objects.none()

    paginator = Paginator(submissions, 20)
    page = request.GET.get('page', 1)
    submissions_page = paginator.get_page(page)

    if request.headers.get('HX-Request'):
        return render(request, 'grades/partials/submission_table.html', {
            'submissions': submissions_page,
            'status_filter': status_filter,
            'selected_period': selected_period,
        })

    return render(request, 'grades/submission_list.html', {
        'submissions': submissions_page,
        'status_filter': status_filter,
        'status_choices': GradeSubmission.STATUS_CHOICES,
        'all_periods': all_periods,
        'selected_period': selected_period,
    })


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
            
            Grade.objects.filter(
                subject=submission.subject,
                section=submission.section,
                school_year=submission.school_year,
                grading_period=submission.grading_period,
                status__in=['submitted', 'returned']
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
            
            Grade.objects.filter(
                subject=submission.subject,
                section=submission.section,
                school_year=submission.school_year,
                grading_period=submission.grading_period,
                status='submitted'
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
def grade_export(request):
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="grades_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student', 'LRN', 'Subject', 'Section', 'Grade Level', 'School Year', 'Grading Period', 'Written Work', 'Performance Task', 'Assessment', 'Quarter Grade', 'Final Grade', 'Remarks', 'Status'])
    
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
            grade.written_work,
            grade.performance_task,
            grade.assessment,
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


@teacher_or_admin_required
def grade_encode_select(request):
    """Teacher selects a subject from dropdown and dynamically loads the grade entry table."""
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    current_period = GradingPeriod.objects.filter(is_current=True).first()
    all_periods = GradingPeriod.objects.filter(school_year=current_sy).order_by('order') if current_sy else GradingPeriod.objects.none()
    
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
            'submission': submission,
        })
        
        if request.headers.get('HX-Request'):
            return render(request, 'grades/partials/grade_encode_select_table.html', context)
    
    return render(request, 'grades/grade_encode_select.html', context)


@teacher_or_admin_required
def grade_encode_all(request):
    """Show all teacher assignments with students so teacher can enter all grades at once."""
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    current_period = GradingPeriod.objects.filter(is_current=True).first()
    all_periods = GradingPeriod.objects.filter(school_year=current_sy).order_by('order') if current_sy else GradingPeriod.objects.none()
    
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
    assignment_data = []
    for assignment in assignments:
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
        
        submission = GradeSubmission.objects.filter(
            teacher=request.user,
            subject=assignment.subject,
            section=assignment.section,
            school_year=assignment.school_year,
            grading_period=grading_period
        ).first()
        
        assignment_data.append({
            'assignment': assignment,
            'student_grades': student_grades,
            'submission': submission,
        })
    
    return render(request, 'grades/grade_encode_all.html', {
        'grading_period': grading_period,
        'all_periods': all_periods,
        'assignment_data': assignment_data,
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
    
    for assignment in assignments:
        students = Student.objects.filter(
            grade_level=assignment.section.grade_level,
            section=assignment.section,
            status='active'
        )
        
        student_ids_with_data = []
        has_data = False
        
        for student in students:
            prefix = f'assignment_{assignment.pk}_student_{student.id}'
            written = request.POST.get(f'{prefix}_written', '')
            performance = request.POST.get(f'{prefix}_performance', '')
            assessment = request.POST.get(f'{prefix}_assessment', '')
            
            if written == '' and performance == '' and assessment == '':
                continue
            
            try:
                written = float(written) if written else 0
                performance = float(performance) if performance else 0
                assessment = float(assessment) if assessment else 0
            except (ValueError, TypeError):
                messages.error(request, f'Invalid grade values for {student.full_name} in {assignment.subject}.')
                continue
            
            if not (0 <= written <= 100 and 0 <= performance <= 100 and 0 <= assessment <= 100):
                messages.error(request, f'Grade values for {student.full_name} in {assignment.subject} must be between 0 and 100.')
                continue
            
            student_ids_with_data.append(student.id)
            has_data = True
            
            quarter_grade = (written + performance + assessment) / 3
            remarks = 'Passed' if quarter_grade >= 75 else ('Incomplete' if quarter_grade >= 60 else 'Failed')
            status = 'submitted' if action == 'submit' else 'draft'
            
            existing_grade = Grade.objects.filter(
                student=student,
                subject=assignment.subject,
                grading_period=grading_period,
                school_year=assignment.school_year,
            ).first()
            
            grade, created = Grade.objects.update_or_create(
                student=student,
                subject=assignment.subject,
                grading_period=grading_period,
                school_year=assignment.school_year,
                defaults={
                    'section': assignment.section,
                    'written_work': written,
                    'performance_task': performance,
                    'assessment': assessment,
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
            submission, _ = GradeSubmission.objects.get_or_create(
                teacher=request.user,
                subject=assignment.subject,
                section=assignment.section,
                school_year=assignment.school_year,
                grading_period=grading_period,
                defaults={'status': 'pending'}
            )
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
    
    if action == 'submit':
        if saved_assignments:
            messages.success(request, f'Grades submitted for {len(saved_assignments)} subject(s) for {grading_period.name}.')
        else:
            messages.info(request, 'No grades were submitted. Make sure to enter grades before submitting.')
    else:
        messages.success(request, 'Grades saved as draft.')
    
    return redirect(f'{reverse("grades:grade_encode_all")}?period={grading_period.pk}')
