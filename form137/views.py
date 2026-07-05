from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from .models import Form137Record
from .utils import build_grade_blocks, build_printable_grade_blocks
from students.models import Student
from grades.models import Grade
from academics.models import SchoolYear, GradeLevel, GradingPeriod, Subject
from accounts.models import AuditLog
from accounts.decorators import role_required


def _form137_print_context(student, school_year, record):
    grade_blocks = build_grade_blocks(student)
    return {
        'student': student,
        'school_year': school_year,
        'record': record,
        'grade_blocks': grade_blocks,
        'print_blocks': build_printable_grade_blocks(grade_blocks),
    }


@role_required('admin', 'registrar', 'principal')
def form137_list(request):
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

    paginator = Paginator(records, 15)
    page = request.GET.get('page', 1)
    records_page = paginator.get_page(page)

    return render(request, 'form137/form137_list.html', {
        'records': records_page,
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


@role_required('admin', 'registrar', 'principal')
def form137_generate(request, student_pk, sy_pk):
    student = get_object_or_404(Student, pk=student_pk)
    school_year = get_object_or_404(SchoolYear, pk=sy_pk)

    grade_blocks = build_grade_blocks(student)

    if not grade_blocks:
        messages.warning(request, 'No validated grades found for this student.')
        return redirect('form137:form137_list')

    grade_level = grade_blocks[0]["grade_level"]

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

    return render(request, 'form137/form137_print.html', _form137_print_context(
        student,
        school_year,
        record,
    ))


@role_required('admin', 'registrar', 'principal')
def form137_preview(request, record_pk):
    record = get_object_or_404(Form137Record, pk=record_pk)

    return render(request, 'form137/form137_print.html', _form137_print_context(
        record.student,
        record.school_year,
        record,
    ))


@role_required('admin', 'registrar', 'principal')
def form137_bulk_generate(request):
    if request.method == 'POST':
        sy_pk = request.POST.get('school_year')
        school_year = get_object_or_404(SchoolYear, pk=sy_pk)
        
        students_with_grades = Student.objects.filter(
            grades__school_year=school_year,
            grades__status__in=['validated', 'locked']
        ).distinct()
        
        count = 0
        for student in students_with_grades:
            grades = Grade.objects.filter(
                student=student,
                school_year=school_year,
                status__in=['validated', 'locked']
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


@role_required('admin', 'registrar', 'principal')
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
