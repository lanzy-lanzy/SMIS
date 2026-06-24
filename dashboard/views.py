from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Avg
from students.models import Student
from grades.models import Grade, GradeSubmission
from academics.models import SchoolYear, GradeLevel, Section, TeacherAssignment
from accounts.models import User
from form137.models import Form137Record


@login_required
def index(request):
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    
    total_students = Student.objects.filter(status='active').count()
    total_teachers = User.objects.filter(role='teacher', is_active=True).count()
    total_sections = Section.objects.filter(school_year=current_sy).count() if current_sy else 0
    
    pending_submissions = GradeSubmission.objects.filter(status='pending').count()
    validated_records = Form137Record.objects.count()
    
    at_risk_count = Grade.objects.filter(
        status='validated', quarter_grade__lt=75
    ).values('student').distinct().count() if current_sy else 0
    
    recent_submissions = GradeSubmission.objects.select_related(
        'teacher', 'subject', 'section'
    ).order_by('-submitted_at')[:5]
    
    recent_activity = Grade.objects.select_related(
        'student', 'subject', 'encoded_by'
    ).order_by('-updated_at')[:10]
    
    students_by_level = Student.objects.filter(status='active').values(
        'grade_level__name'
    ).annotate(count=Count('id')).order_by('grade_level__level')
    
    return render(request, 'dashboard/index.html', {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_sections': total_sections,
        'pending_submissions': pending_submissions,
        'validated_records': validated_records,
        'at_risk_count': at_risk_count,
        'recent_submissions': recent_submissions,
        'recent_activity': recent_activity,
        'students_by_level': students_by_level,
        'current_sy': current_sy
    })
