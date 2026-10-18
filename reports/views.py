from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.utils.text import slugify
from students.models import Student, ENROLLED_STATUSES
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


SCHOOL_HEAD_NAME = 'EUGENE A. BATILONG'

# Canonical Learner's Performance Report rows (in print order) mapped to the
# subject names used in this system. MAPEH components render as italic sub-rows
# under a MAPEH parent row, mirroring the DepEd card layout.
CANONICAL_SUBJECT_ROWS = [
    ('Filipino', {'filipino'}),
    ('English', {'english'}),
    ('Mathematics', {'mathematics', 'math'}),
    ('Science', {'science'}),
    ('Araling Panlipunan (AP)', {'araling panlipunan', 'araling panlipunan (ap)', 'ap'}),
    ('GMRC / Values Education', {'edukasyon sa pagpapakatao', 'gmrc', 'gmrc / values education', 'values education', 'esp'}),
    ('EPP/TLE', {'technology and livelihood education', 'epp/tle', 'epp / tle', 'epp', 'tle'}),
    ('MAPEH', {'mapeh'}),
]
MAPEH_COMPONENT_ROWS = [
    ('Music and Arts', {'music and arts', 'music', 'arts'}),
    ('Physical Education and Health', {'physical education and health', 'pe and health', 'peah'}),
]

# Static Grading Scale / Descriptors / Remarks legend printed on the form.
PERFORMANCE_DESCRIPTORS = [
    ('90-100', 'Advancing', 'Passed'),
    ('80-89', 'Benchmarking', 'Passed'),
    ('75-79', 'Connecting', 'Passed'),
    ('65-74', 'Developing', 'Failed'),
    ('0-64', 'Emerging', 'Failed'),
]

# The form always shows three term columns; extra periods are ignored.
REPORT_TERM_COUNT = 3


def _subject_key(name):
    return ' '.join((name or '').lower().split())


def _subject_alias_map():
    aliases = {}
    for label, names in CANONICAL_SUBJECT_ROWS + MAPEH_COMPONENT_ROWS:
        for name in names:
            aliases[name] = label
    return aliases


def _build_grade_rows(subjects_map, terms, completed):
    """Build the report-card grade rows in canonical DepEd order.

    subjects_map: {subject name: {period order: Grade}}. Returns a list of row
    dicts: name, style ('normal' | 'parent' | 'sub'), term_cells (values or
    None aligned to terms), final, remarks. All eight canonical rows are always
    emitted (blank when ungraded, like the fixed printed form); subjects that
    match no canonical row keep their own name and are appended in sorted
    order so no graded subject is ever dropped from the card.
    """
    aliases = _subject_alias_map()
    by_label = {}
    leftovers = {}
    for subject_name, period_map in subjects_map.items():
        label = aliases.get(_subject_key(subject_name))
        if label:
            by_label.setdefault(label, {}).update(period_map)
        else:
            leftovers[subject_name] = period_map

    def make_row(name, period_map, style='normal'):
        term_cells = []
        included = []
        for period in terms[:REPORT_TERM_COUNT]:
            grade = period_map.get(period.order)
            value = None
            if grade is not None and period.order in completed:
                value = grade.quarter_grade
                included.append(value)
            term_cells.append(value)
        term_cells += [None] * (REPORT_TERM_COUNT - len(term_cells))
        final = None
        if included:
            final = int((sum(included) / len(included)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        remarks = ''
        if final is not None:
            remarks = 'Passed' if final >= 75 else 'Failed'
        return {'name': name, 'style': style, 'term_cells': term_cells, 'final': final, 'remarks': remarks}

    rows = []
    for label, _ in CANONICAL_SUBJECT_ROWS:
        if label == 'MAPEH':
            components = [(name, by_label.get(name)) for name, _ in MAPEH_COMPONENT_ROWS]
            components = [(name, pm) for name, pm in components if pm]
            rows.append(make_row('MAPEH', by_label.get('MAPEH') or {}, 'parent' if components else 'normal'))
            for name, pm in components:
                rows.append(make_row(name, pm, 'sub'))
            continue
        rows.append(make_row(label, by_label.get(label) or {}))
    for name in sorted(leftovers):
        rows.append(make_row(name, leftovers[name]))
    return rows


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
        
        student_count = Student.objects.filter(section=section, status__in=ENROLLED_STATUSES).count()
        
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


def _report_card_context(request, student):
    """Assemble everything the Learner's Performance Report needs.

    Shared by the HTML view and the PDF download so both render identical data.
    Term columns are populated only for terms whose submissions are all
    approved (finished); incomplete terms render blank so a partially done
    year can still be printed, and export is gated on term completion.
    """
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

    rows = _build_grade_rows(subjects_map, terms, completed)

    finals = [r['final'] for r in rows if r['final'] is not None]
    general_average = None
    if finals:
        general_average = int((Decimal(sum(finals)) / Decimal(len(finals))).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    section = student.section
    adviser_name = section.adviser.get_full_name().upper() if section and section.adviser else ''

    middle = f" {student.middle_name.upper()}" if student.middle_name else ''
    suffix = f" {student.suffix.upper()}" if student.suffix else ''

    shown_terms = terms[:REPORT_TERM_COUNT]
    term_labels = [f"T{p.order}" for p in shown_terms]
    term_full_labels = [f"Term {p.order}" for p in shown_terms]
    for i in range(len(shown_terms), REPORT_TERM_COUNT):
        term_labels.append(f"T{i + 1}")
        term_full_labels.append(f"Term {i + 1}")

    return {
        'student': student,
        'school_year': school_year,
        'school_years': school_years,
        'terms': shown_terms,
        'completed_orders': completed,
        'rows': rows,
        'general_average': general_average,
        'general_average_remarks': ('Passed' if general_average >= 75 else 'Failed') if general_average is not None else '',
        'learner_name': f"{student.last_name.upper()}, {student.first_name.upper()}{middle}{suffix}",
        'lrn': student.lrn,
        'sex': student.get_sex_display() or '',
        'section_name': section.name.upper() if section else '',
        'grade_level': student.grade_level.level if student.grade_level else '',
        'adviser_name': adviser_name,
        'school_head_name': SCHOOL_HEAD_NAME,
        'age': _compute_age(student.birthdate),
        'term_labels': term_labels,
        'term_full_labels': term_full_labels,
        'parent_sig_rows': [
            {'label': label, 'top': 257.0 + i * 14.3}
            for i, label in enumerate(term_full_labels)
        ],
        'descriptor_rows': PERFORMANCE_DESCRIPTORS,
        'has_exportable_term': bool(completed),
    }


@registrar_or_admin_required
def report_card(request, student_pk):
    """Per-learner Learner's Performance Report (report card) for HTML print."""
    student = get_object_or_404(Student, pk=student_pk)
    return render(request, 'reports/report_card.html', _report_card_context(request, student))


@registrar_or_admin_required
def report_card_pdf(request, student_pk):
    """Server-generated PDF of the same report card (mirrors the HTML layout)."""
    from .report_card_pdf import build_report_card_pdf

    student = get_object_or_404(Student, pk=student_pk)
    context = _report_card_context(request, student)

    buffer = BytesIO()
    build_report_card_pdf(buffer, context)

    filename = slugify(f"report-card-{student.last_name}-{student.first_name}") or 'report-card'
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    return response
