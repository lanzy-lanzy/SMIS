from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import datetime
from students.models import Student
from grades.models import Grade, GradeSubmission
from academics.models import SchoolYear, GradeLevel, Section, TeacherAssignment
from accounts.models import User, AuditLog
from form137.models import Form137Record


def landing(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    return render(request, 'landing.html')


@login_required
def index(request):
    # Redirect students to their own dashboard
    if request.user.is_student_user:
        return redirect('students:student_dashboard')

    current_sy = SchoolYear.objects.filter(is_current=True).first()

    total_students = Student.objects.filter(status='active').count()
    total_teachers = User.objects.filter(role='teacher', is_active=True).count()

    pending_submissions = GradeSubmission.objects.filter(status='pending').count()
    returned_submissions = GradeSubmission.objects.filter(status='returned').count()

    # Validated / locked grades
    validated_grades = Grade.objects.filter(
        status__in=['validated', 'locked']
    ).count() if current_sy else 0

    # Form 137 generated this school year
    form137_generated = Form137Record.objects.filter(
        school_year=current_sy
    ).count() if current_sy else 0

    at_risk_count = Grade.objects.filter(
        status__in=['validated', 'locked'], quarter_grade__lt=75
    ).values('student').distinct().count() if current_sy else 0

    # Recent submissions (legacy fallback data)
    recent_submissions = GradeSubmission.objects.select_related(
        'teacher', 'subject', 'section'
    ).order_by('-submitted_at')[:5]

    # Recent activity (legacy fallback data)
    recent_activity = Grade.objects.select_related(
        'student', 'subject', 'encoded_by'
    ).order_by('-updated_at')[:10]

    # Students by grade level for bar chart
    students_by_level = Student.objects.filter(status='active').values(
        'grade_level__name'
    ).annotate(count=Count('id')).order_by('grade_level__level')

    # Grade validation workflow counts for donut chart
    grade_validation_counts = {
        'draft': Grade.objects.filter(status='draft').count() if current_sy else 0,
        'pending': GradeSubmission.objects.filter(status='pending').count() if current_sy else 0,
        'returned': GradeSubmission.objects.filter(status='returned').count() if current_sy else 0,
        'validated': Grade.objects.filter(status__in=['validated', 'locked']).count() if current_sy else 0,
    }
    grade_validation_total = sum(grade_validation_counts.values())

    # At-risk students details (top 5)
    at_risk_students = []
    if current_sy:
        failing_grades = Grade.objects.filter(
            status__in=['validated', 'locked'],
            quarter_grade__lt=75
        ).select_related('student', 'subject', 'student__grade_level', 'student__section')

        at_risk_map = {}
        for grade in failing_grades:
            student = grade.student
            if student.id not in at_risk_map:
                at_risk_map[student.id] = {
                    'student': student,
                    'grades': [],
                    'average': 0,
                }
            at_risk_map[student.id]['grades'].append(grade)

        for data in at_risk_map.values():
            total = sum(float(g.quarter_grade) for g in data['grades'])
            data['average'] = round(total / len(data['grades']), 2)
            if len(data['grades']) > 1:
                data['reason'] = 'Multiple failing subjects'
            else:
                avg = data['average']
                if avg >= 70:
                    data['reason'] = 'Low quarterly average'
                else:
                    data['reason'] = 'Attendance concern'

        at_risk_students = sorted(
            at_risk_map.values(),
            key=lambda x: x['average']
        )[:5]

    # Recent activities (from audit logs when available)
    recent_activities = []
    try:
        logs = AuditLog.objects.select_related('user').order_by('-timestamp')[:6]
        for log in logs:
            recent_activities.append({
                'actor': log.user.get_full_name() if log.user else 'System',
                'action': _describe_audit_action(log),
                'time_ago': _natural_time(log.timestamp),
                'icon': _audit_action_icon(log.action),
                'color': _audit_action_color(log.action),
            })
    except Exception:
        # Fallback to grade submissions if audit logs are not populated
        for sub in recent_submissions[:5]:
            recent_activities.append({
                'actor': sub.teacher.get_full_name(),
                'action': f'submitted {sub.subject} grades for {sub.section}',
                'time_ago': _natural_time(sub.submitted_at),
                'icon': 'clipboard',
                'color': 'primary',
            })

    # Announcements (static for now; replace with model when available)
    announcements = [
        {
            'title': 'Quarterly Assessment',
            'content': 'The 4th Quarter Assessment will be on May 26 - 30, 2025.',
            'date': 'May 16, 2025',
            'icon': 'bullhorn',
        },
        {
            'title': 'Form 137 Processing',
            'content': 'Form 137 generation is ongoing. Please verify your students\' data.',
            'date': 'May 15, 2025',
            'icon': 'file',
        },
        {
            'title': 'Brigada Eskwela 2025',
            'content': 'Brigada Eskwela will be on May 27 - 31, 2025. Thank you!',
            'date': 'May 14, 2025',
            'icon': 'school',
        },
    ]

    return render(request, 'dashboard/index.html', {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_sections': Section.objects.filter(school_year=current_sy).count() if current_sy else 0,
        'pending_submissions': pending_submissions,
        'returned_submissions': returned_submissions,
        'validated_grades': validated_grades,
        'form137_generated': form137_generated,
        'at_risk_count': at_risk_count,
        'recent_submissions': recent_submissions,
        'recent_activity': recent_activity,
        'students_by_level': students_by_level,
        'grade_validation_counts': grade_validation_counts,
        'grade_validation_total': grade_validation_total,
        'at_risk_students': at_risk_students,
        'recent_activities': recent_activities,
        'announcements': announcements,
        'current_sy': current_sy,
        'today': timezone.now(),
    })


def _describe_audit_action(log):
    action_map = {
        'create': 'created',
        'update': 'updated',
        'delete': 'deleted',
        'login': 'logged in',
        'logout': 'logged out',
        'grade_encode': 'encoded grades',
        'grade_update': 'updated grades',
        'grade_submit': 'submitted grades',
        'grade_validate': 'validated grades',
        'grade_return': 'returned grades',
        'form137_generate': 'generated Form 137',
    }
    verb = action_map.get(log.action, log.action)
    if log.model_name and log.object_id:
        return f'{verb} {log.model_name} #{log.object_id}'
    return verb


def _audit_action_icon(action):
    if action in ('grade_encode', 'grade_update', 'grade_submit'):
        return 'clipboard'
    if action == 'grade_validate':
        return 'check'
    if action == 'grade_return':
        return 'refresh'
    if action == 'form137_generate':
        return 'file'
    if action == 'login':
        return 'login'
    if action == 'logout':
        return 'logout'
    return 'cog'


def _audit_action_color(action):
    if action in ('grade_encode', 'grade_update'):
        return 'primary'
    if action == 'grade_submit':
        return 'secondary'
    if action == 'grade_validate':
        return 'primary'
    if action == 'grade_return':
        return 'danger'
    if action == 'form137_generate':
        return 'purple'
    return 'gray'


def _natural_time(value):
    if not value:
        return ''
    now = timezone.now()
    if timezone.is_naive(value):
        value = timezone.make_aware(value)
    delta = now - value
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return 'Just now'
    if seconds < 3600:
        minutes = seconds // 60
        return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
    if seconds < 86400:
        hours = seconds // 3600
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    if seconds < 604800:
        days = seconds // 86400
        return f'{days} day{"s" if days != 1 else ""} ago'
    return value.strftime('%b %d, %Y')