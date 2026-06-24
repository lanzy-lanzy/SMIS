from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from .models import Form137Record
from students.models import Student
from grades.models import Grade
from academics.models import SchoolYear, GradeLevel, GradingPeriod, Subject
from accounts.models import AuditLog


@login_required
def form137_list(request):
    if not request.user.is_registrar and not request.user.is_admin:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:index')

    school_years = SchoolYear.objects.all()
    grade_levels = GradeLevel.objects.all()
    
    sy_filter = request.GET.get('sy', '')
    gl_filter = request.GET.get('gl', '')
    query = request.GET.get('q', '')
    
    records = Form137Record.objects.select_related(
        'student', 'school_year', 'grade_level', 'generated_by'
    ).all()
    
    if sy_filter:
        records = records.filter(school_year_id=sy_filter)
    if gl_filter:
        records = records.filter(grade_level_id=gl_filter)
    if query:
        records = records.filter(
            Q(student__first_name__icontains=query) |
            Q(student__last_name__icontains=query) |
            Q(student__lrn__icontains=query)
        )
    
    # Stats
    all_records = Form137Record.objects.all()
    total_records = all_records.count()
    printed_count = all_records.filter(is_printed=True).count()
    unprinted_count = all_records.filter(is_printed=False).count()
    this_month_count = all_records.filter(
        date_generated__year=timezone.now().year,
        date_generated__month=timezone.now().month
    ).count()
    
    return render(request, 'form137/form137_list.html', {
        'records': records,
        'school_years': school_years,
        'grade_levels': grade_levels,
        'sy_filter': sy_filter,
        'gl_filter': gl_filter,
        'query': query,
        'total_records': total_records,
        'printed_count': printed_count,
        'unprinted_count': unprinted_count,
        'this_month_count': this_month_count,
    })


@login_required
def form137_generate(request, student_pk, sy_pk):
    if not request.user.is_registrar:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:index')
    
    student = get_object_or_404(Student, pk=student_pk)
    school_year = get_object_or_404(SchoolYear, pk=sy_pk)
    
    grades = Grade.objects.filter(
        student=student,
        school_year=school_year,
        status='validated'
    ).select_related('subject', 'grading_period').order_by(
        'grading_period__order', 'subject__name'
    )
    
    if not grades.exists():
        messages.warning(request, 'No validated grades found for this student.')
        return redirect('form137:form137_list')
    
    grade_level = grades.first().subject.grade_level
    
    record, created = Form137Record.objects.get_or_create(
        student=student,
        school_year=school_year,
        grade_level=grade_level,
        defaults={'generated_by': request.user}
    )
    
    if created:
        AuditLog.objects.create(
            user=request.user,
            action='form137_generate',
            model_name='Form137Record',
            object_id=str(record.id),
            description=f'Generated Form 137 for {student.full_name}'
        )
    
    periods = GradingPeriod.objects.filter(school_year=school_year).order_by('order')
    
    subjects = Subject.objects.filter(
        id__in=grades.values_list('subject_id', flat=True).distinct()
    )
    
    grade_data = {}
    for subject in subjects:
        grade_data[subject.name] = {}
        for period in periods:
            grade = grades.filter(subject=subject, grading_period=period).first()
            grade_data[subject.name][period.order] = grade
    
    # Calculate general average
    if grades.exists():
        total_final = sum(grade.final_grade for grade in grades)
        general_average = total_final / grades.count()
    else:
        general_average = 0
    
    # Create final grades dictionary for easy lookup
    final_grades = {}
    for grade in grades:
        final_grades[grade.subject.name] = {
            'final_grade': grade.final_grade,
            'remarks': 'Passed' if grade.final_grade >= 75 else 'Failed'
        }
    
    return render(request, 'form137/form137_print.html', {
        'student': student,
        'school_year': school_year,
        'grades': grades,
        'grade_data': grade_data,
        'periods': periods,
        'record': record,
        'general_average': general_average,
        'final_grades': final_grades
    })


@login_required
def form137_preview(request, record_pk):
    if not request.user.is_registrar and not request.user.is_admin:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:index')

    record = get_object_or_404(Form137Record, pk=record_pk)
    
    grades = Grade.objects.filter(
        student=record.student,
        school_year=record.school_year,
        status='validated'
    ).select_related('subject', 'grading_period').order_by(
        'grading_period__order', 'subject__name'
    )
    
    periods = GradingPeriod.objects.filter(
        school_year=record.school_year
    ).order_by('order')
    
    subjects = Subject.objects.filter(
        id__in=grades.values_list('subject_id', flat=True).distinct()
    )
    
    grade_data = {}
    for subject in subjects:
        grade_data[subject.name] = {}
        for period in periods:
            grade = grades.filter(subject=subject, grading_period=period).first()
            grade_data[subject.name][period.order] = grade
    
    return render(request, 'form137/form137_print.html', {
        'student': record.student,
        'school_year': record.school_year,
        'grades': grades,
        'grade_data': grade_data,
        'periods': periods,
        'record': record
    })


@login_required
def form137_bulk_generate(request):
    if not request.user.is_registrar and not request.user.is_admin:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:index')
    
    if request.method == 'POST':
        sy_pk = request.POST.get('school_year')
        school_year = get_object_or_404(SchoolYear, pk=sy_pk)
        
        students_with_grades = Student.objects.filter(
            grades__school_year=school_year,
            grades__status='validated'
        ).distinct()
        
        count = 0
        for student in students_with_grades:
            grades = Grade.objects.filter(
                student=student,
                school_year=school_year,
                status='validated'
            ).select_related('subject')
            
            if grades.exists():
                grade_level = grades.first().subject.grade_level
                record, created = Form137Record.objects.get_or_create(
                    student=student,
                    school_year=school_year,
                    grade_level=grade_level,
                    defaults={'generated_by': request.user}
                )
                if created:
                    count += 1
        
        messages.success(request, f'{count} Form 137 records generated successfully.')
        return redirect('form137:form137_list')
    
    school_years = SchoolYear.objects.all()
    return render(request, 'form137/bulk_generate.html', {
        'school_years': school_years
    })


@login_required
def form137_export(request):
    import csv
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="form137_records_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student Name', 'LRN', 'School Year', 'Grade Level', 'Generated By', 'Date Generated', 'Printed'])
    
    records = Form137Record.objects.select_related(
        'student', 'school_year', 'grade_level', 'generated_by'
    ).all()
    
    for record in records:
        writer.writerow([
            record.student.full_name,
            record.student.lrn,
            record.school_year.name,
            record.grade_level.name,
            record.generated_by.get_full_name() if record.generated_by else '',
            record.date_generated.strftime('%Y-%m-%d'),
            'Yes' if record.is_printed else 'No',
        ])
    
    return response
