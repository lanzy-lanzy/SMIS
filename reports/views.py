from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from students.models import Student
from grades.models import Grade, GradeSubmission
from academics.models import SchoolYear, GradeLevel, Section, Subject
from accounts.models import User
from accounts.decorators import principal_or_admin_required


@principal_or_admin_required
def reports_index(request):
    return render(request, 'reports/index.html')


@principal_or_admin_required
def grade_trends(request):
    sy_filter = request.GET.get('sy', '')
    gl_filter = request.GET.get('gl', '')
    
    grades = Grade.objects.filter(status__in=['validated', 'locked']).select_related(
        'subject', 'grading_period', 'school_year', 'section', 'section__grade_level'
    )

    if sy_filter:
        grades = grades.filter(school_year_id=sy_filter)
    if gl_filter:
        grades = grades.filter(section__grade_level_id=gl_filter)
    
    subject_averages = grades.values('subject__name').annotate(
        avg_grade=Avg('quarter_grade')
    ).order_by('-avg_grade')
    
    period_averages = grades.values('grading_period__name').annotate(
        avg_grade=Avg('quarter_grade')
    ).order_by('grading_period__order')
    
    school_years = SchoolYear.objects.all()
    grade_levels = GradeLevel.objects.all()
    
    return render(request, 'reports/grade_trends.html', {
        'subject_averages': subject_averages,
        'period_averages': period_averages,
        'school_years': school_years,
        'grade_levels': grade_levels,
        'sy_filter': sy_filter,
        'gl_filter': gl_filter
    })


@principal_or_admin_required
def section_performance(request):
    sy_filter = request.GET.get('sy', '')
    
    sections = Section.objects.all()
    
    section_data = []
    for section in sections:
        avg = Grade.objects.filter(
            section=section, status__in=['validated', 'locked']
        ).aggregate(avg=Avg('quarter_grade'))['avg'] or 0
        
        student_count = Student.objects.filter(section=section, status='active').count()
        
        section_data.append({
            'section': section,
            'average': round(avg, 2),
            'student_count': student_count
        })
    
    school_years = SchoolYear.objects.all()
    
    return render(request, 'reports/section_performance.html', {
        'section_data': section_data,
        'school_years': school_years,
        'sy_filter': sy_filter
    })


@principal_or_admin_required
def subject_performance(request):
    subjects = Subject.objects.all()
    
    subject_data = []
    for subject in subjects:
        avg = Grade.objects.filter(
            subject=subject, status__in=['validated', 'locked']
        ).aggregate(avg=Avg('quarter_grade'))['avg'] or 0
        
        subject_data.append({
            'subject': subject,
            'average': round(avg, 2)
        })
    
    return render(request, 'reports/subject_performance.html', {
        'subject_data': subject_data
    })


@principal_or_admin_required
def at_risk_students(request):
    sy_filter = request.GET.get('sy', '')
    gl_filter = request.GET.get('gl', '')
    
    grades = Grade.objects.filter(
        status__in=['validated', 'locked'],
        quarter_grade__lt=75
    ).select_related('student', 'subject', 'school_year', 'section', 'section__grade_level')

    if sy_filter:
        grades = grades.filter(school_year_id=sy_filter)
    if gl_filter:
        grades = grades.filter(section__grade_level_id=gl_filter)
    
    at_risk = {}
    for grade in grades:
        student = grade.student
        if student.id not in at_risk:
            at_risk[student.id] = {
                'student': student,
                'failing_grades': [],
                'average': 0
            }
        at_risk[student.id]['failing_grades'].append({
            'subject': grade.subject.name,
            'grade': grade.quarter_grade,
            'remarks': grade.remarks
        })
    
    for data in at_risk.values():
        total = sum(g['grade'] for g in data['failing_grades'])
        data['average'] = round(total / len(data['failing_grades']), 2)
    
    school_years = SchoolYear.objects.all()
    grade_levels = GradeLevel.objects.all()
    
    return render(request, 'reports/at_risk_students.html', {
        'at_risk': sorted(at_risk.values(), key=lambda x: x['average']),
        'school_years': school_years,
        'grade_levels': grade_levels,
        'sy_filter': sy_filter,
        'gl_filter': gl_filter
    })


@principal_or_admin_required
def student_history(request, student_pk):
    from students.models import Student
    student = Student.objects.get(pk=student_pk)
    
    grades = Grade.objects.filter(
        student=student, status__in=['validated', 'locked']
    ).select_related('subject', 'grading_period', 'school_year').order_by(
        '-school_year__name', 'grading_period__order', 'subject__name'
    )
    
    return render(request, 'reports/student_history.html', {
        'student': student,
        'grades': grades
    })
