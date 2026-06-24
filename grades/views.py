from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Avg
from django.utils import timezone
from .models import Grade, GradeSubmission, GradeValidation
from academics.models import TeacherAssignment, GradingPeriod, SchoolYear, Section, Subject
from students.models import Student
from accounts.models import AuditLog


@login_required
def grade_list(request):
    from django.db.models import Count, Q
    
    teacher = request.user
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    current_period = GradingPeriod.objects.filter(is_current=True).first()
    
    query = request.GET.get('q', '')
    subject_filter = request.GET.get('subject', '')
    section_filter = request.GET.get('section', '')
    view_type = request.GET.get('view', 'grid')
    
    if request.user.is_teacher:
        assignments = TeacherAssignment.objects.filter(
            teacher=teacher, school_year=current_sy
        ).select_related('subject', 'section', 'section__grade_level')
    else:
        assignments = TeacherAssignment.objects.filter(
            school_year=current_sy
        ).select_related('teacher', 'subject', 'section', 'section__grade_level')
    
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
    
    # Get latest submission status for each assignment
    submissions_status = {}
    if current_sy:
        # Fetch all relevant submissions at once
        all_submissions = GradeSubmission.objects.filter(
            school_year=current_sy
        ).order_by('-submitted_at')
        
        # Build a lookup: (teacher_id, subject_id, section_id) -> status
        for sub in all_submissions:
            key = (sub.teacher_id, sub.subject_id, sub.section_id)
            if key not in submissions_status:
                submissions_status[key] = sub.status
    
    # Map to assignment pks
    submission_status_by_pk = {}
    for assignment in assignments:
        key = (assignment.teacher_id, assignment.subject_id, assignment.section_id)
        submission_status_by_pk[assignment.pk] = submissions_status.get(key)
    
    # Stats
    total_assignments = assignments.count()
    pending_submissions = GradeSubmission.objects.filter(
        status='pending', school_year=current_sy
    ).count() if current_sy else 0
    validated_grades = Grade.objects.filter(
        status='validated', school_year=current_sy
    ).count() if current_sy else 0
    at_risk_count = Grade.objects.filter(
        status='validated', quarter_grade__lt=75, school_year=current_sy
    ).values('student').distinct().count() if current_sy else 0
    
    if request.headers.get('HX-Request'):
        template = 'grades/partials/assignment_table.html' if view_type == 'table' else 'grades/partials/assignment_list.html'
        return render(request, template, {
            'assignments': assignments,
            'current_period': current_period,
            'submissions_status': submission_status_by_pk
        })
    
    subjects = Subject.objects.all()
    sections = Section.objects.filter(school_year=current_sy) if current_sy else Section.objects.all()
    
    return render(request, 'grades/grade_list.html', {
        'assignments': assignments,
        'current_sy': current_sy,
        'current_period': current_period,
        'subjects': subjects,
        'sections': sections,
        'subject_filter': subject_filter,
        'section_filter': section_filter,
        'query': query,
        'total_assignments': total_assignments,
        'pending_submissions': pending_submissions,
        'validated_grades': validated_grades,
        'at_risk_count': at_risk_count,
        'submissions_status': submission_status_by_pk,
    })


@login_required
def grade_encode(request, assignment_pk):
    if not request.user.is_teacher and not request.user.is_admin:
        messages.error(request, 'Access denied.')
        return redirect('grades:grade_list')

    assignment = get_object_or_404(TeacherAssignment, pk=assignment_pk)
    current_period = GradingPeriod.objects.filter(is_current=True).first()
    
    if not current_period:
        messages.error(request, 'No active grading period.')
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
        grading_period=current_period
    ).select_related('student'):
        existing_grades[grade.student_id] = grade
    
    grade_data = []
    for student in students:
        grade = existing_grades.get(student.id)
        grade_data.append({
            'student': student,
            'grade': grade
        })
    
    return render(request, 'grades/grade_encode.html', {
        'assignment': assignment,
        'current_period': current_period,
        'grade_data': grade_data,
        'students': students
    })


@login_required
def grade_save(request, assignment_pk):
    if not request.user.is_teacher and not request.user.is_admin:
        messages.error(request, 'Access denied.')
        return redirect('grades:grade_list')

    if request.method != 'POST':
        return HttpResponse(status=405)
    
    assignment = get_object_or_404(TeacherAssignment, pk=assignment_pk)
    current_period = GradingPeriod.objects.filter(is_current=True).first()

    if not current_period:
        messages.error(request, 'No active grading period.')
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
            grading_period=current_period,
            school_year=assignment.school_year,
        ).first()
        
        grade, created = Grade.objects.update_or_create(
            student=student,
            subject=assignment.subject,
            grading_period=current_period,
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
            grading_period=current_period,
            defaults={'status': 'pending'}
        )
        Grade.objects.filter(
            student__id__in=student_ids_with_data,
            subject=assignment.subject,
            section=assignment.section,
            school_year=assignment.school_year,
            grading_period=current_period,
            status='draft'
        ).update(status='submitted')
        
        AuditLog.objects.create(
            user=request.user,
            action='grade_submit',
            model_name='GradeSubmission',
            object_id=str(submission.id),
            description=f'Submitted grades for {assignment.subject} - {assignment.section}'
        )
        messages.success(request, 'Grades submitted for validation.')
    else:
        messages.success(request, 'Grades saved as draft.')
    
    return redirect('grades:grade_encode', assignment_pk=assignment_pk)


@login_required
def submission_list(request):
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    
    if request.user.is_teacher:
        submissions = GradeSubmission.objects.filter(
            teacher=request.user, school_year=current_sy
        ).select_related('subject', 'section', 'grading_period')
    elif request.user.is_registrar:
        submissions = GradeSubmission.objects.filter(
            school_year=current_sy
        ).select_related('teacher', 'subject', 'section', 'grading_period')
    else:
        submissions = GradeSubmission.objects.none()
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        submissions = submissions.filter(status=status_filter)
    
    if request.headers.get('HX-Request'):
        return render(request, 'grades/partials/submission_table.html', {'submissions': submissions})
    
    return render(request, 'grades/submission_list.html', {
        'submissions': submissions,
        'status_filter': status_filter,
        'status_choices': GradeSubmission.STATUS_CHOICES
    })


@login_required
def submission_validate(request, pk):
    if not request.user.is_registrar:
        messages.error(request, 'Access denied.')
        return redirect('grades:submission_list')
    
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
                status='submitted'
            ).update(status='locked')
            
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


@login_required
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
