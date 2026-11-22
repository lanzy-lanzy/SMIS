from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from statistics import mean

from django.db.models.functions import Coalesce

from academics.models import GradeLevel
from grades.mapeh import is_mapeh_subject, mapeh_component, merge_mapeh_grades


def term_achievement(school_year, learners, official_grades, requested_period=None, requested_grade=None):
    periods = list(school_year.grading_periods.all()) if school_year else []
    learners_with_level = learners.annotate(
        level_id=Coalesce('grade_level_id', 'section__grade_level_id')
    )
    grade_levels = list(
        GradeLevel.objects.filter(pk__in=learners_with_level.order_by().values('level_id'))
    )

    selected_grade = next(
        (level for level in grade_levels if str(level.pk) == str(requested_grade or '')),
        None,
    )
    scoped_learners = (
        learners_with_level.filter(level_id=selected_grade.pk)
        if selected_grade else learners_with_level
    )

    is_all_terms = (requested_period == 'all')
    if is_all_terms:
        selected = None
    else:
        selected = next((period for period in periods if str(period.pk) == str(requested_period or '')), None)
        selected = selected or next((period for period in periods if period.is_current), None) or next(iter(periods), None)

    counts = [{'male': 0, 'female': 0, 'total': 0} for _ in range(5)]
    sexes = dict(scoped_learners.values_list('pk', 'sex'))
    included = 0

    if is_all_terms and periods:
        period_subjects = defaultdict(lambda: defaultdict(dict))
        grades = official_grades.filter(
            student__in=scoped_learners, grading_period__in=periods,
            quarter_grade__gt=0, quarter_grade__lte=100,
        ).order_by().values_list(
            'grading_period_id', 'student_id', 'subject_id', 'subject__name', 'component', 'quarter_grade'
        )
        for period_id, student, subject, name, component, mark in grades:
            period_subjects[(student, period_id)][(subject, name)][component] = mark

        student_term_averages = defaultdict(list)
        for (student, _period_id), subjects in period_subjects.items():
            marks = _complete_subject_marks(subjects)
            if marks:
                student_term_averages[student].append(mean(marks))

        for student, term_averages in student_term_averages.items():
            average = mean(term_averages).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            band = sum(average >= threshold for threshold in (75, 80, 85, 90))
            counts[band]['total'] += 1
            sex = {'M': 'male', 'F': 'female'}.get(sexes.get(student))
            if sex:
                counts[band][sex] += 1
            included += 1
    elif selected:
        subjects_by_student = defaultdict(lambda: defaultdict(dict))
        grades = official_grades.filter(
            student__in=scoped_learners, grading_period=selected,
            quarter_grade__gt=0, quarter_grade__lte=100,
        ).order_by().values_list('student_id', 'subject_id', 'subject__name', 'component', 'quarter_grade')
        for student, subject, name, component, mark in grades:
            subjects_by_student[student][(subject, name)][component] = mark

        for student, subjects in subjects_by_student.items():
            marks = _complete_subject_marks(subjects)
            if not marks:
                continue
            average = mean(marks).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            band = sum(average >= threshold for threshold in (75, 80, 85, 90))
            counts[band]['total'] += 1
            sex = {'M': 'male', 'F': 'female'}.get(sexes.get(student))
            if sex:
                counts[band][sex] += 1
            included += 1

    labels = ['74 and below', '75–79', '80–84', '85–89', '90–100']
    return {
        'periods': periods,
        'selected': selected,
        'is_all_terms': is_all_terms,
        'selected_term_key': 'all' if is_all_terms else (str(selected.pk) if selected else ''),
        'selected_term_label': 'All terms' if is_all_terms else (selected.name if selected else 'Term achievement'),
        'grade_levels': grade_levels,
        'selected_grade': selected_grade,
        'selected_grade_key': str(selected_grade.pk) if selected_grade else 'all',
        'selected_grade_label': selected_grade.name if selected_grade else 'All grade levels',
        'counts': counts,
        'rows': list(zip(labels, counts)),
        'included': included,
        'missing': len(sexes) - included,
    }


def grade_performance(school_year, learners, official_grades):
    """Return term averages with one equally weighted result per learner."""
    periods = list(school_year.grading_periods.all()) if school_year else []
    grades = official_grades.filter(
        student__in=learners, grading_period__in=periods, quarter_grade__gt=0, quarter_grade__lte=100,
    ).annotate(level_id=Coalesce('student__grade_level_id', 'student__section__grade_level_id'))

    learner_marks = defaultdict(lambda: defaultdict(dict))
    for period, student, level, subject, name, component, mark in grades.order_by().values_list(
        'grading_period_id', 'student_id', 'level_id', 'subject_id', 'subject__name', 'component', 'quarter_grade',
    ):
        learner_marks[(period, student, level)][(subject, name)][component] = mark

    school_averages = defaultdict(list)
    grade_averages = defaultdict(lambda: defaultdict(list))
    for (period, _student, level), subjects in learner_marks.items():
        marks = _complete_subject_marks(subjects)
        if marks:
            result = mean(marks)
            school_averages[period].append(result)
            if level:
                grade_averages[level][period].append(result)

    options = [('school', 'All grade levels', school_averages)]
    learner_levels = learners.annotate(level_id=Coalesce('grade_level_id', 'section__grade_level_id')).order_by()
    options.extend(
        (str(level.pk), level.name, grade_averages[level.pk])
        for level in GradeLevel.objects.filter(pk__in=learner_levels.values('level_id'))
    )
    return [
        {
            'key': key,
            'label': label,
            'has_grades': bool(averages),
            'terms': [
                {
                    'name': period.name,
                    'average': mean(averages[period.pk]).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                    if period.pk in averages else None,
                    'learners': len(averages.get(period.pk, ())),
                }
                for period in periods
            ],
        }
        for key, label, averages in options
    ]


def _complete_subject_marks(subjects):
    marks = []
    mapeh = None
    legacy_components = {}
    for (_subject_id, name), components in subjects.items():
        mark = components.get('')
        if is_mapeh_subject(name):
            if mark is not None:
                mapeh = mark
            elif 'ma' in components and 'peh' in components:
                mapeh = Decimal(merge_mapeh_grades([components['ma'], components['peh']]))
        elif component := mapeh_component(name):
            legacy_components[component] = mark
        elif mark is not None:
            marks.append(mark)

    if mapeh is None and all(legacy_components.get(key) is not None for key in ('ma', 'peh')):
        mapeh = Decimal(merge_mapeh_grades(legacy_components.values()))
    if mapeh is not None:
        marks.append(mapeh)
    return marks
