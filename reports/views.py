from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from statistics import mean, median, stdev
from types import SimpleNamespace

from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.utils.text import slugify
from students.models import Student, ENROLLED_STATUSES
from grades.models import Grade, GradeSubmission, grade_descriptor
from grades.mapeh import is_mapeh_subject, mapeh_component, merge_mapeh_grades, merge_mapeh_periods
from academics.models import (
    SchoolYear, GradeLevel, Section, Subject, GradingPeriod, TeacherAssignment,
)
from accounts.models import User
from accounts.decorators import registrar_or_admin_required, role_required
from .sf6 import build_sf6_summary


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
SCHOOL_NAME = 'PAQUITO S. YU MEMORIAL NATIONAL HIGH SCHOOL'
SCHOOL_ID = '314235'
SCHOOL_REGION = 'Region IX'
SCHOOL_DIVISION = 'Zamboanga del Sur'
SCHOOL_DISTRICT = 'Dumingag I'

# Learning-area order used on the Class Summary (Master Grade Sheet), matching
# the printed form: core subjects first, then MAPEH, GMRC/VE and EPP/TLE.
CLASS_SUMMARY_SUBJECT_ORDER = [
    'Filipino',
    'English',
    'Mathematics',
    'Science',
    'Araling Panlipunan (AP)',
    'MAPEH',
    'GMRC / Values Education',
    'EPP/TLE',
]

# Compact column headings for the Class Summary, mirroring the printed sheet.
CLASS_SUMMARY_SHORT_LABELS = {
    'Araling Panlipunan (AP)': 'AP',
    'GMRC / Values Education': 'GMRC/VE',
    'Physical Education and Health': 'PE and Health',
}

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
            parent_map = dict(by_label.get('MAPEH') or {})
            if components:
                merged = merge_mapeh_periods([
                    {order: grade.quarter_grade for order, grade in pm.items()}
                    for _name, pm in components
                ])
                for order, value in merged.items():
                    parent_map.setdefault(order, SimpleNamespace(quarter_grade=Decimal(value)))
            rows.append(make_row('MAPEH', parent_map, 'parent' if components else 'normal'))
            for name, pm in components:
                rows.append(make_row(name, pm, 'sub'))
            continue
        rows.append(make_row(label, by_label.get(label) or {}))
    for name in sorted(leftovers):
        rows.append(make_row(name, leftovers[name]))
    return rows


def _selected_school_year(request):
    sy_id = request.GET.get('sy', '').strip()
    if sy_id:
        school_year = SchoolYear.objects.filter(pk=sy_id).first()
        if school_year:
            return school_year
    return SchoolYear.objects.filter(is_current=True).first() or SchoolYear.objects.first()


def _teacher_section_ids(user, school_year):
    """Section IDs a teacher is assigned to for the given school year."""
    if not school_year:
        return []
    return list(
        TeacherAssignment.objects
        .filter(teacher=user, school_year=school_year)
        .values_list('section_id', flat=True)
        .distinct()
    )


def _teacher_access_section_ids(user, school_year):
    """Sections a teacher may view report cards for: taught or advised."""
    if not school_year:
        return []
    advised = Section.objects.filter(
        adviser=user, school_year=school_year
    ).values_list('id', flat=True)
    return list(set(_teacher_section_ids(user, school_year)) | set(advised))


def _teacher_can_access_student(user, student):
    if not user.is_teacher:
        return True
    if not student.section_id:
        return False
    if TeacherAssignment.objects.filter(teacher=user, section_id=student.section_id).exists():
        return True
    return Section.objects.filter(pk=student.section_id, adviser=user).exists()


def _ordered_subjects(subjects, order=None):
    """Order learning areas using the Class Summary layout, then by name."""
    aliases = _subject_alias_map()
    order = order or CLASS_SUMMARY_SUBJECT_ORDER
    positions = {label: i for i, label in enumerate(order)}
    component_labels = {label for label, _names in MAPEH_COMPONENT_ROWS}

    def position(subject):
        label = aliases.get(_subject_key(subject.name))
        if label in component_labels:
            label = 'MAPEH'
        return positions.get(label, len(order))

    return sorted(
        subjects,
        key=lambda subject: (position(subject), subject.name.lower()),
    )


def _class_summary_label(subject):
    label = _subject_alias_map().get(_subject_key(subject.name), subject.name)
    return CLASS_SUMMARY_SHORT_LABELS.get(label, label)


def _average_grade(values):
    """Whole-number average of the given term grades, or None when empty."""
    present = [Decimal(value) for value in values if value is not None]
    if not present:
        return None
    return int((sum(present) / Decimal(len(present))).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _exam_analysis(grades, terms):
    analyses = []
    for term in terms:
        term_grades = [grade for grade in grades if grade.grading_period_id == term.pk]
        items = []
        for number, label in enumerate(('ST1', 'ST2', 'TE'), start=1):
            scores = []
            maxima = []
            for grade in term_grades:
                score = getattr(grade, f'assessment_{number}')
                highest = getattr(grade, f'assessment_{number}_highest')
                if score is not None:
                    scores.append(float(score))
                if highest is not None:
                    maxima.append(float(highest))

            examinees = len(scores)
            highest_possible = max(maxima) if maxima else None
            average = mean(scores) if scores else None
            has_percentage_base = highest_possible is not None and highest_possible > 0
            passed = (
                sum(score >= highest_possible * 0.75 for score in scores)
                if has_percentage_base else None
            )
            below = examinees - passed if passed is not None else None
            items.append({
                'label': label,
                'examinees': examinees,
                'highest_possible': highest_possible,
                'passed_count': passed,
                'passed_percent': passed / examinees * 100 if examinees and passed is not None else None,
                'below_count': below,
                'below_percent': below / examinees * 100 if examinees and below is not None else None,
                'mean': average,
                'median': median(scores) if scores else None,
                'sd': stdev(scores) if len(scores) > 1 else None,
                'mps': average / highest_possible * 100 if average is not None and has_percentage_base else None,
                'highest_score': max(scores) if scores else None,
                'lowest_score': min(scores) if scores else None,
                'total_score': sum(scores) if scores else None,
            })

        rows = []

        def add_row(label, key, number_format):
            rows.append({
                'label': label,
                'cells': [item[key] for item in items],
                'format': number_format,
                'class': 'analysis-mps' if key == 'mps' else '',
            })

        add_row('Number of Examinees', 'examinees', '0')
        add_row('Highest Possible Score', 'highest_possible', 'g')
        rows.append({'group': 'Criterion-Referenced'})
        add_row('75% & Above (n)', 'passed_count', '0')
        add_row('75% & Above (%)', 'passed_percent', '2')
        add_row('Below 75% (n)', 'below_count', '0')
        add_row('Below 75% (%)', 'below_percent', '2')
        rows.append({'group': 'Norm-Referenced'})
        add_row('Mean', 'mean', '2')
        add_row('Median', 'median', '2')
        add_row('Standard Deviation', 'sd', '2')
        add_row('MPS/PL (%)', 'mps', '2')
        rows.append({'group': 'Other Information'})
        add_row('Highest Score', 'highest_score', 'g')
        add_row('Lowest Score', 'lowest_score', 'g')
        add_row('Total Score', 'total_score', 'g')
        analyses.append({'term': term, 'items': items, 'rows': rows})
    return analyses


def _assign_ranks(rows, key='final_grade'):
    """Rank rows by descending grade, averaging the ranks of tied learners."""
    ranked = sorted(
        (row for row in rows if row.get(key) is not None),
        key=lambda row: row[key],
        reverse=True,
    )
    index = 0
    while index < len(ranked):
        end = index
        while end + 1 < len(ranked) and ranked[end + 1][key] == ranked[index][key]:
            end += 1
        average_rank = Decimal(index + 1 + end + 1) / Decimal(2)
        label = int(average_rank) if average_rank == average_rank.to_integral_value() else float(average_rank)
        for position in range(index, end + 1):
            ranked[position]['rank'] = label
        index = end + 1
    return rows


def _school_header(school_year):
    return {
        'school_region': SCHOOL_REGION,
        'school_division': SCHOOL_DIVISION,
        'school_name': SCHOOL_NAME,
        'school_id': SCHOOL_ID,
        'school_head_name': SCHOOL_HEAD_NAME,
        'school_year': school_year,
    }


@registrar_or_admin_required
def reports_index(request):
    return render(request, 'reports/index.html')


@registrar_or_admin_required
def sf6_report(request):
    """School Form 6 - Summarized Report on Promotion and Learning Progress."""
    school_year = _selected_school_year(request)
    return render(request, 'reports/sf6.html', {
        **_school_header(school_year),
        'school_district': SCHOOL_DISTRICT,
        'school_years': SchoolYear.objects.all(),
        'selected_sy': school_year,
        'sf6': build_sf6_summary(school_year),
    })


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


@role_required('admin', 'registrar', 'teacher')
def report_card_select(request):
    """Learner picker that lists students and links to each report card."""
    query = request.GET.get('q', '').strip()
    students = (
        Student.objects
        .select_related('grade_level', 'section', 'school_year')
        .order_by('last_name', 'first_name')
    )
    if request.user.is_teacher:
        section_ids = _teacher_access_section_ids(request.user, _selected_school_year(request))
        students = students.filter(section_id__in=section_ids)
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
    mapeh_component_rows = {}
    for grade in grades:
        # MAPEH is one Subject but two Grade rows per learner/term (component
        # 'ma' / 'peh'); roll them up into one MAPEH parent row so the report
        # card matches the DepEd layout. Legacy combined rows (component='')
        # pass through unchanged.
        if is_mapeh_subject(grade.subject.name) and grade.component:
            mapeh_component_rows.setdefault(grade.grading_period.order, []).append(grade)
            continue
        subjects_map.setdefault(grade.subject.name, {})[grade.grading_period.order] = grade
    if mapeh_component_rows:
        parent_map = subjects_map.setdefault('MAPEH', {})
        for order, component_grades in mapeh_component_rows.items():
            avg = merge_mapeh_grades(g.quarter_grade for g in component_grades)
            if avg is not None:
                parent_map[order] = SimpleNamespace(quarter_grade=Decimal(avg))

    rows = _build_grade_rows(subjects_map, terms, completed)

    mapeh_parent = next((r for r in rows if r['name'] == 'MAPEH' and r['final'] is not None), None)
    finals = [
        r['final'] for r in rows
        if r['final'] is not None and not (mapeh_parent is not None and r['style'] == 'sub')
    ]
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


@role_required('admin', 'registrar', 'teacher')
def report_card(request, student_pk):
    """Per-learner Learner's Performance Report (report card) for HTML print."""
    student = get_object_or_404(Student, pk=student_pk)
    if not _teacher_can_access_student(request.user, student):
        messages.error(request, 'Access denied. This learner is not in one of your classes.')
        return redirect('reports:report_card_select')
    return render(request, 'reports/report_card.html', _report_card_context(request, student))


@role_required('admin', 'registrar', 'teacher')
def report_card_pdf(request, student_pk):
    """Server-generated PDF of the same report card (mirrors the HTML layout)."""
    from .report_card_pdf import build_report_card_pdf

    student = get_object_or_404(Student, pk=student_pk)
    if not _teacher_can_access_student(request.user, student):
        messages.error(request, 'Access denied. This learner is not in one of your classes.')
        return redirect('reports:report_card_select')
    context = _report_card_context(request, student)

    buffer = BytesIO()
    build_report_card_pdf(buffer, context)

    filename = slugify(f"report-card-{student.last_name}-{student.first_name}") or 'report-card'
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    return response


@role_required('admin', 'registrar', 'teacher')
def report_templates(request):
    """Hub for the printable templates: Class Record, Class Summary, Report Cards."""
    school_year = _selected_school_year(request)
    is_adviser = True
    if request.user.is_teacher:
        is_adviser = bool(
            school_year
            and Section.objects.filter(adviser=request.user, school_year=school_year).exists()
        )
    return render(request, 'reports/templates.html', {
        'selected_sy': school_year,
        'is_adviser': is_adviser,
    })


@role_required('admin', 'registrar', 'teacher')
def class_record(request):
    """Class Record - Final Grades for one subject/section, per the printed form."""
    school_year = _selected_school_year(request)
    school_years = SchoolYear.objects.all()

    sections = (
        Section.objects.filter(school_year=school_year)
        .select_related('grade_level')
        .order_by('grade_level__level', 'name')
    ) if school_year else Section.objects.none()

    if request.user.is_teacher:
        sections = sections.filter(id__in=_teacher_section_ids(request.user, school_year))

    section_id = request.GET.get('section', '').strip()
    section = sections.filter(pk=section_id).first() if section_id else sections.first()

    if section:
        if request.user.is_teacher:
            subjects = Subject.objects.filter(
                is_active=True,
                assignments__teacher=request.user,
                assignments__section=section,
                assignments__school_year=school_year,
            ).distinct()
        else:
            subjects = Subject.objects.filter(
                grade_level=section.grade_level, is_active=True
            )
        subjects = _ordered_subjects(subjects)
    else:
        subjects = []

    subject_id = request.GET.get('subject', '').strip()
    subject = next((s for s in subjects if str(s.pk) == subject_id), None)
    if subject is None and subjects:
        subject = subjects[0]

    terms = list(
        GradingPeriod.objects.filter(school_year=school_year).order_by('order')
    ) if school_year else []

    rows_by_sex = {'M': [], 'F': []}
    is_mapeh = bool(subject and is_mapeh_subject(subject.name))
    if section and subject and terms:
        students = (
            Student.objects
            .filter(section=section, status__in=ENROLLED_STATUSES)
            .order_by('last_name', 'first_name')
        )
        grades = (
            Grade.objects
            .filter(
                section=section,
                subject=subject,
                school_year=school_year,
                status__in=['validated', 'locked'],
            )
            .select_related('student', 'grading_period')
        )
        grades_map = {}
        # MAPEH keeps its Music & Arts / PE & Health rows so the record can show
        # one column per component alongside the merged term grade.
        mapeh_components = {}
        mapeh_component_values = {}
        for grade in grades:
            if is_mapeh and grade.component:
                key = (grade.student_id, grade.grading_period.order)
                mapeh_components.setdefault(key, {})[grade.component] = grade.quarter_grade
                mapeh_component_values.setdefault(key, []).append(grade.quarter_grade)
                continue
            grades_map.setdefault(grade.student_id, {})[grade.grading_period.order] = grade.quarter_grade
        for (student_id, order), values in mapeh_component_values.items():
            avg = merge_mapeh_grades(values)
            if avg is not None:
                grades_map.setdefault(student_id, {})[order] = Decimal(avg)

        for student in students:
            if student.sex not in rows_by_sex:
                continue
            period_grades = grades_map.get(student.id, {})
            term_values = [period_grades.get(period.order) for period in terms]
            if is_mapeh:
                term_cells = [
                    {
                        'ma': mapeh_components.get((student.id, period.order), {}).get('ma'),
                        'peh': mapeh_components.get((student.id, period.order), {}).get('peh'),
                        'term': period_grades.get(period.order),
                    }
                    for period in terms
                ]
            else:
                term_cells = term_values
            final_grade = _average_grade(term_values)
            rows_by_sex[student.sex].append({
                'student': student,
                'term_cells': term_cells,
                'final_grade': final_grade,
                'descriptor': grade_descriptor(final_grade) if final_grade is not None else '',
                'remark': ('Passed' if final_grade >= 75 else 'Failed') if final_grade is not None else '',
            })

        rows_by_sex['M'] = [
            dict(row, no=number)
            for number, row in enumerate(rows_by_sex['M'], start=1)
        ]
        rows_by_sex['F'] = [
            dict(row, no=number)
            for number, row in enumerate(rows_by_sex['F'], start=1)
        ]

    teacher_name = request.user.get_full_name().upper()
    if not request.user.is_teacher and subject and section and school_year:
        assignment = (
            subject.assignments
            .filter(section=section, school_year=school_year)
            .select_related('teacher')
            .first()
        )
        teacher_name = assignment.teacher.get_full_name().upper() if assignment else ''

    context = {
        **_school_header(school_year),
        'school_years': school_years,
        'sections': sections,
        'subjects': subjects,
        'terms': terms,
        'section': section,
        'subject': subject,
        'male_rows': rows_by_sex['M'],
        'female_rows': rows_by_sex['F'],
        'teacher_name': teacher_name,
        'selected_sy': school_year,
        # MAPEH spreads every term across 3 columns (MA / PEH / Term Grade).
        'is_mapeh': is_mapeh,
        'term_colspan': len(terms) * 3 if is_mapeh else len(terms),
        'body_colspan': (len(terms) * 3 if is_mapeh else len(terms)) + 5,
    }
    return render(request, 'reports/class_record.html', context)


@role_required('admin', 'registrar', 'teacher')
def exam_analysis(request):
    """Test/Exam Results Analysis for one subject/section across terms.

    Previously embedded at the foot of the Class Record; broken out into its
    own printable report so the Class Record stays a pure final-grades sheet.
    """
    school_year = _selected_school_year(request)
    school_years = SchoolYear.objects.all()

    sections = (
        Section.objects.filter(school_year=school_year)
        .select_related('grade_level')
        .order_by('grade_level__level', 'name')
    ) if school_year else Section.objects.none()

    if request.user.is_teacher:
        sections = sections.filter(id__in=_teacher_section_ids(request.user, school_year))

    section_id = request.GET.get('section', '').strip()
    section = sections.filter(pk=section_id).first() if section_id else sections.first()

    if section:
        if request.user.is_teacher:
            subjects = Subject.objects.filter(
                is_active=True,
                assignments__teacher=request.user,
                assignments__section=section,
                assignments__school_year=school_year,
            ).distinct()
        else:
            subjects = Subject.objects.filter(
                grade_level=section.grade_level, is_active=True
            )
        subjects = _ordered_subjects(subjects)
    else:
        subjects = []

    subject_id = request.GET.get('subject', '').strip()
    subject = next((s for s in subjects if str(s.pk) == subject_id), None)
    if subject is None and subjects:
        subject = subjects[0]

    terms = list(
        GradingPeriod.objects.filter(school_year=school_year).order_by('order')
    ) if school_year else []

    analyses = []
    if section and subject and terms:
        grades = (
            Grade.objects
            .filter(
                section=section,
                subject=subject,
                school_year=school_year,
                status__in=['validated', 'locked'],
            )
            .select_related('student', 'grading_period')
        )
        analyses = _exam_analysis(grades, terms)

    context = {
        **_school_header(school_year),
        'school_years': school_years,
        'sections': sections,
        'subjects': subjects,
        'terms': terms,
        'section': section,
        'subject': subject,
        'exam_analysis': analyses,
        'selected_sy': school_year,
    }
    return render(request, 'reports/exam_analysis.html', context)


@role_required('admin', 'registrar', 'teacher')
def class_summary(request):
    """Class Summary (Master Grade Sheet) for a section and quarter."""
    school_year = _selected_school_year(request)
    school_years = SchoolYear.objects.all()

    sections = (
        Section.objects.filter(school_year=school_year)
        .select_related('grade_level', 'adviser')
        .order_by('grade_level__level', 'name')
    ) if school_year else Section.objects.none()

    if request.user.is_teacher:
        sections = sections.filter(adviser=request.user)

    section_id = request.GET.get('section', '').strip()
    section = sections.filter(pk=section_id).first() if section_id else sections.first()

    periods = list(
        GradingPeriod.objects.filter(school_year=school_year).order_by('order')
    ) if school_year else []
    term_id = request.GET.get('term', '').strip()
    term = next((p for p in periods if str(p.pk) == term_id), None)
    if term is None:
        term = next((p for p in periods if p.is_current), periods[0] if periods else None)

    subjects = [
        {'model': subject, 'label': _class_summary_label(subject)}
        for subject in _ordered_subjects(
            Subject.objects.filter(grade_level=section.grade_level, is_active=True)
        )
    ] if section else []

    mapeh_entry = None
    component_entries = [entry for entry in subjects if mapeh_component(entry['model'].name)]
    if component_entries:
        mapeh_entry = {
            'model': None,
            'label': 'MAPEH',
            'component_ids': [entry['model'].id for entry in component_entries],
        }
        insert_at = max(subjects.index(entry) for entry in component_entries) + 1
        subjects.insert(insert_at, mapeh_entry)

    male_rows, female_rows = [], []
    if section:
        students = (
            Student.objects
            .filter(section=section, status__in=ENROLLED_STATUSES)
            .order_by('last_name', 'first_name')
        )
        grades = (
            Grade.objects
            .filter(
                section=section,
                school_year=school_year,
                status__in=['validated', 'locked'],
            )
            .select_related('student', 'subject', 'grading_period')
        )
        grades_map = {}
        mapeh_summary = {}
        for grade in grades:
            if is_mapeh_subject(grade.subject.name) and grade.component:
                mapeh_summary.setdefault(
                    (grade.student_id, grade.subject_id, grade.grading_period.order), []
                ).append(grade.quarter_grade)
                continue
            grades_map.setdefault(grade.student_id, {}).setdefault(
                grade.subject_id, {}
            )[grade.grading_period.order] = grade.quarter_grade
        for (student_id, subject_id, order), values in mapeh_summary.items():
            avg = merge_mapeh_grades(values)
            if avg is not None:
                grades_map.setdefault(student_id, {}).setdefault(subject_id, {})[order] = Decimal(avg)

        for student in students:
            student_grades = grades_map.get(student.id, {})
            subject_grades = []
            for subject in subjects:
                if subject['model'] is None:
                    values = [
                        student_grades.get(component_id, {}).get(term.order) if term else None
                        for component_id in subject['component_ids']
                    ]
                    subject_grades.append(merge_mapeh_grades(values))
                else:
                    subject_grades.append(
                        student_grades.get(subject['model'].id, {}).get(term.order)
                        if term else None
                    )
            if mapeh_entry is not None:
                component_ids = set(mapeh_entry['component_ids'])
                average_values = [
                    value for subject, value in zip(subjects, subject_grades)
                    if subject['model'] is None or subject['model'].id not in component_ids
                ]
            else:
                average_values = subject_grades
            final_grade = _average_grade(average_values)
            row = {
                'student': student,
                'subject_grades': subject_grades,
                'final_grade': final_grade,
                'age': _compute_age(student.birthdate),
                'rank': None,
            }
            if student.sex == 'M':
                male_rows.append(row)
            elif student.sex == 'F':
                female_rows.append(row)

        _assign_ranks(male_rows + female_rows)

    context = {
        **_school_header(school_year),
        'school_years': school_years,
        'sections': sections,
        'section': section,
        'subjects': subjects,
        'periods': periods,
        'term': term,
        'male_rows': male_rows,
        'female_rows': female_rows,
        'adviser_name': section.adviser.get_full_name().upper() if section and section.adviser else '',
        'selected_sy': school_year,
    }
    return render(request, 'reports/class_summary.html', context)
