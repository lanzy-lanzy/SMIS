from decimal import Decimal, ROUND_HALF_UP

from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from students.models import Student
from grades.models import Grade, GradeSubmission
from academics.models import SchoolYear, GradeLevel, Section, Subject, GradingPeriod
from accounts.models import User
from accounts.decorators import registrar_or_admin_required


def _completed_period_orders(school_year):
    """Return the grading-period orders whose submissions are all approved.

    A term is treated as finished (exportable) when at least one grade
    submission exists for it in the school year and none are left pending or
    returned. This mirrors the completion gate used on the submissions page.
    """
    if not school_year:
        return set()
    completed = set()
    for period in GradingPeriod.objects.filter(school_year=school_year):
        subs = GradeSubmission.objects.filter(school_year=school_year, grading_period=period)
        if subs.exists() and not subs.filter(status__in=['pending', 'returned']).exists():
            completed.add(period.order)
    return completed


def _compute_age(birthdate, reference=None):
    if not birthdate:
        return ''
    reference = reference or timezone.localdate()
    years = reference.year - birthdate.year
    if (reference.month, reference.day) < (birthdate.month, birthdate.day):
        years -= 1
    return years


@registrar_or_admin_required
def reports_index(request):
    return render(request, 'reports/index.html')


@registrar_or_admin_required
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


@registrar_or_admin_required
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


@registrar_or_admin_required
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


@registrar_or_admin_required
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


@registrar_or_admin_required
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


@registrar_or_admin_required
def report_card_select(request):
    """Learner picker that lists students and links to each report card."""
    query = request.GET.get('q', '').strip()
    students = (
        Student.objects
        .select_related('grade_level', 'section', 'school_year')
        .order_by('last_name', 'first_name')
    )
    if query:
        students = students.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(lrn__icontains=query)
        )
    return render(request, 'reports/report_card_select.html', {
        'students_list': students[:300],
        'query': query,
        'total_count': students.count(),
    })


@registrar_or_admin_required
def report_card(request, student_pk):
    """Per-learner Learner's Performance Report (report card) for print/PDF.

    Term columns are populated only for terms whose submissions are all
    approved (finished); incomplete terms render blank so a partially done
    year can still be printed, and export is gated on term completion.
    """
    student = get_object_or_404(Student, pk=student_pk)

    school_years = SchoolYear.objects.all()
    sy_id = request.GET.get('sy', '')
    if sy_id:
        school_year = get_object_or_404(SchoolYear, pk=sy_id)
    else:
        school_year = student.school_year or SchoolYear.objects.filter(is_current=True).first()

    terms = list(
        GradingPeriod.objects.filter(school_year=school_year).order_by('order')
    ) if school_year else []
    completed = _completed_period_orders(school_year)

    grades = (
        Grade.objects
        .filter(student=student, school_year=school_year, status__in=['validated', 'locked'])
        .select_related('subject', 'grading_period')
    ) if school_year else Grade.objects.none()

    subjects_map = {}
    for grade in grades:
        subjects_map.setdefault(grade.subject.name, {})[grade.grading_period.order] = grade

    rows = []
    for name in sorted(subjects_map):
        period_map = subjects_map[name]
        term_cells = []
        included = []
        for period in terms:
            grade = period_map.get(period.order)
            value = None
            if grade is not None and period.order in completed:
                value = grade.quarter_grade
                included.append(value)
            term_cells.append(value)
        final = None
        if included:
            final = int((sum(included) / len(included)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        remarks = ''
        if final is not None:
            if final >= 75:
                remarks = 'Passed'
            elif final >= 60:
                remarks = 'Incomplete'
            else:
                remarks = 'Failed'
        rows.append({
            'name': name,
            'term_cells': term_cells,
            'final': final,
            'remarks': remarks,
        })

    finals = [r['final'] for r in rows if r['final'] is not None]
    general_average = None
    if finals:
        general_average = int((Decimal(sum(finals)) / Decimal(len(finals))).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    section = student.section
    adviser_name = section.adviser.get_full_name() if section and section.adviser else ''

    return render(request, 'reports/report_card.html', {
        'student': student,
        'school_year': school_year,
        'school_years': school_years,
        'terms': terms,
        'completed_orders': completed,
        'rows': rows,
        'general_average': general_average,
        'section_name': section.name if section else '',
        'grade_level': student.grade_level.level if student.grade_level else '',
        'adviser_name': adviser_name,
        'age': _compute_age(student.birthdate),
        'has_exportable_term': bool(completed),
    })
