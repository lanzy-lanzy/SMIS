from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from statistics import mean

from django.db.models.functions import Coalesce

from academics.models import GradeLevel
from grades.mapeh import is_mapeh_subject, mapeh_component, merge_mapeh_grades


def term_achievement(school_year, learners, official_grades, requested_period):
    periods = list(school_year.grading_periods.all()) if school_year else []
    selected = next((period for period in periods if str(period.pk) == requested_period), None)
    selected = selected or next((period for period in periods if period.is_current), None) or next(iter(periods), None)
    counts = [{'male': 0, 'female': 0, 'total': 0} for _ in range(5)]
    subjects_by_student = defaultdict(lambda: defaultdict(dict))
    sexes = dict(learners.values_list('pk', 'sex'))
    if selected:
        grades = official_grades.filter(
            student__in=learners, grading_period=selected, quarter_grade__gt=0, quarter_grade__lte=100,
        ).order_by().values_list('student_id', 'subject_id', 'subject__name', 'component', 'quarter_grade')
        for student, subject, name, component, mark in grades:
            subjects_by_student[student][(subject, name)][component] = mark
    included = 0
    for student, subjects in subjects_by_student.items():
        marks = _complete_subject_marks(subjects)
        if not marks:
            continue
        average = mean(marks).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        band = sum(average >= threshold for threshold in (75, 80, 85, 90))
        counts[band]['total'] += 1
        sex = {'M': 'male', 'F': 'female'}.get(sexes[student])
        if sex:
            counts[band][sex] += 1
        included += 1
    labels = ['74 and below', '75–79', '80–84', '85–89', '90–100']
    return {
        'periods': periods, 'selected': selected, 'counts': counts,
        'rows': list(zip(labels, counts)), 'included': included,
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
