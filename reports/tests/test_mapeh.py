"""MAPEH component merge: Music and Arts + PE and Health report as one MAPEH grade."""

import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase
from django.urls import reverse

from academics.models import GradeLevel, GradingPeriod, SchoolYear, Section, Subject
from accounts.models import User
from form137.utils import build_grade_blocks, build_printable_subject_rows
from grades.mapeh import mapeh_component, mapeh_component_label, merge_mapeh_grades, merge_mapeh_periods
from grades.models import Grade, GradeSubmission
from reports.sf6 import _student_finals, build_sf6_summary
from reports.views import _build_grade_rows
from students.models import Student

from .test_sf6 import Python314ContextCopyMixin


class MapehHelperTests(TestCase):
    def test_component_aliases(self):
        cases = [
            ('MUSIC AND ARTS', 'ma'),
            ('Music and Arts', 'ma'),
            ('MA', 'ma'),
            ('PHYSICAL EDUCATION AND HEALTH', 'peh'),
            ('PE and Health', 'peh'),
            ('PEAH', 'peh'),
            ('Mathematics', None),
            ('Music', None),
            ('MAPEH', None),
        ]
        for name, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(mapeh_component(name), expected)

    def test_component_labels(self):
        self.assertEqual(mapeh_component_label('MUSIC AND ARTS'), 'Music and Arts')
        self.assertEqual(mapeh_component_label('peah'), 'Physical Education and Health')
        self.assertIsNone(mapeh_component_label('English'))

    def test_merge_rounds_half_up(self):
        self.assertEqual(merge_mapeh_grades([89, 89]), 89)
        self.assertEqual(merge_mapeh_grades([88, 89]), 89)
        self.assertEqual(merge_mapeh_grades([Decimal('87'), Decimal('88')]), 88)
        self.assertEqual(merge_mapeh_grades([None, 90]), 90)
        self.assertIsNone(merge_mapeh_grades([]))
        self.assertIsNone(merge_mapeh_grades([None, None]))

    def test_merge_periods_aligns_by_order(self):
        merged = merge_mapeh_periods([{1: 88, 2: 90}, {1: 90}])
        self.assertEqual(merged, {1: 89, 2: 90})


class ReportCardMapehRowsTests(TestCase):
    def _rows(self, subjects_map, completed=(1, 2, 3)):
        terms = [SimpleNamespace(order=order) for order in (1, 2, 3)]
        return _build_grade_rows(subjects_map, terms, set(completed))

    def _grade(self, value):
        return SimpleNamespace(quarter_grade=Decimal(value))

    def test_components_merge_into_parent_row(self):
        rows = self._rows({
            'MUSIC AND ARTS': {1: self._grade('88')},
            'PHYSICAL EDUCATION AND HEALTH': {1: self._grade('90')},
        })
        parent = next(row for row in rows if row['name'] == 'MAPEH')
        self.assertEqual(parent['style'], 'parent')
        self.assertEqual(parent['term_cells'], [89, None, None])
        self.assertEqual(parent['final'], 89)
        self.assertEqual(parent['remarks'], 'Passed')
        subs = [row for row in rows if row['style'] == 'sub']
        self.assertEqual([row['name'] for row in subs], ['Music and Arts', 'Physical Education and Health'])
        self.assertEqual([row['final'] for row in subs], [88, 90])

    def test_incomplete_terms_stay_blank(self):
        rows = self._rows({
            'MUSIC AND ARTS': {1: self._grade('80'), 2: self._grade('90')},
            'PHYSICAL EDUCATION AND HEALTH': {1: self._grade('90'), 2: self._grade('90')},
        }, completed=(1,))
        parent = next(row for row in rows if row['name'] == 'MAPEH')
        self.assertEqual(parent['term_cells'], [85, None, None])
        self.assertEqual(parent['final'], 85)

    def test_explicit_mapeh_parent_wins_over_components(self):
        rows = self._rows({
            'MAPEH': {1: self._grade('70')},
            'MUSIC AND ARTS': {1: self._grade('88')},
            'PHYSICAL EDUCATION AND HEALTH': {1: self._grade('90')},
        })
        parent = next(row for row in rows if row['name'] == 'MAPEH')
        self.assertEqual(parent['final'], 70)

    def test_lone_component_still_reports_as_mapeh(self):
        rows = self._rows({'MUSIC AND ARTS': {1: self._grade('88')}})
        parent = next(row for row in rows if row['name'] == 'MAPEH')
        self.assertEqual(parent['style'], 'parent')
        self.assertEqual(parent['final'], 88)


class MapehReportViewTests(Python314ContextCopyMixin, TestCase):
    def setUp(self):
        self.sy = SchoolYear.objects.create(name='2025-2026', is_current=True)
        self.level = GradeLevel.objects.create(name='Grade 7', level=7)
        self.section = Section.objects.create(
            name='7-A', grade_level=self.level, school_year=self.sy
        )
        self.admin = User.objects.create_user(username='admin', password='x', role='admin')
        self.teacher = User.objects.create_user(username='teacher', password='x', role='teacher')
        self.term1 = GradingPeriod.objects.create(
            name='Term 1', order=1, school_year=self.sy, is_current=True
        )
        self.term2 = GradingPeriod.objects.create(name='Term 2', order=2, school_year=self.sy)
        self.filipino = Subject.objects.create(name='Filipino', code='FIL7', grade_level=self.level)
        self.ma = Subject.objects.create(name='MUSIC AND ARTS', code='MAPEH7-2', grade_level=self.level)
        self.peh = Subject.objects.create(
            name='PHYSICAL EDUCATION AND HEALTH', code='MAPEH7-1', grade_level=self.level
        )
        self.student = Student.objects.create(
            lrn='100000000001', first_name='Juan', last_name='Dela Cruz', sex='M',
            birthdate=datetime.date(2012, 1, 1), status='active',
            grade_level=self.level, section=self.section, school_year=self.sy,
        )
        for subject, value in ((self.filipino, '80'), (self.ma, '88'), (self.peh, '90')):
            Grade.objects.create(
                student=self.student, subject=subject, grading_period=self.term1,
                school_year=self.sy, section=self.section, status='validated',
                quarter_grade=Decimal(value), final_grade=Decimal(value),
            )
        GradeSubmission.objects.create(
            teacher=self.teacher, subject=self.filipino, section=self.section,
            school_year=self.sy, grading_period=self.term1, status='approved',
        )

    def test_report_card_merges_mapeh_and_counts_it_once(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('reports:report_card', args=[self.student.pk]))

        self.assertEqual(response.status_code, 200)
        rows = response.context['rows']
        parent = next(row for row in rows if row['name'] == 'MAPEH')
        self.assertEqual(parent['final'], 89)
        # (80 + 89) / 2 = 84.5 -> 85; counting both components would give 86.
        self.assertEqual(response.context['general_average'], 85)

    def test_class_summary_adds_merged_mapeh_column(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('reports:class_summary'), {'section': self.section.pk})

        self.assertEqual(response.status_code, 200)
        subjects = response.context['subjects']
        self.assertEqual(
            [subject['label'] for subject in subjects],
            ['Filipino', 'Music and Arts', 'PE and Health', 'MAPEH'],
        )
        row = response.context['male_rows'][0]
        self.assertEqual(row['subject_grades'], [80, 88, 90, 89])
        self.assertEqual(row['final_grade'], 85)


class Sf6MapehMergeTests(TestCase):
    def setUp(self):
        self.sy = SchoolYear.objects.create(name='2025-2026', is_current=True)
        self.level = GradeLevel.objects.create(name='Grade 7', level=7)
        self.section = Section.objects.create(
            name='7-A', grade_level=self.level, school_year=self.sy
        )
        self.term = GradingPeriod.objects.create(
            name='Term 1', order=1, school_year=self.sy, is_current=True
        )
        self.filipino = Subject.objects.create(name='Filipino', code='FIL7', grade_level=self.level)
        self.ma = Subject.objects.create(name='MUSIC AND ARTS', code='MAPEH7-2', grade_level=self.level)
        self.peh = Subject.objects.create(
            name='PHYSICAL EDUCATION AND HEALTH', code='MAPEH7-1', grade_level=self.level
        )
        self.student = Student.objects.create(
            lrn='100000000001', first_name='Juan', last_name='Dela Cruz', sex='M',
            birthdate=datetime.date(2012, 1, 1), status='active',
            grade_level=self.level, section=self.section, school_year=self.sy,
        )
        for subject, value in ((self.filipino, '80'), (self.ma, '88'), (self.peh, '90')):
            Grade.objects.create(
                student=self.student, subject=subject, grading_period=self.term,
                school_year=self.sy, section=self.section, status='validated',
                quarter_grade=Decimal(value), final_grade=Decimal(value),
            )

    def test_component_finals_merge_into_one_mapeh_final(self):
        finals = _student_finals([self.student], self.sy)
        self.assertEqual(
            finals[self.student.id],
            {'Filipino': Decimal('80'), 'MAPEH': Decimal('89')},
        )

    def test_summary_counts_mapeh_once_in_the_average(self):
        summary = build_sf6_summary(self.sy)
        # (80 + 89) / 2 = 84.5 -> 85, Very Satisfactory; unmerged would be 86.
        band_rows = {
            row['label']: row['cells'][0]
            for row in summary['rows'] if row['kind'] == 'data'
        }
        self.assertEqual(band_rows['Satisfactory (80%-84%)'], {'male': 0, 'female': 0, 'total': 0})
        self.assertEqual(
            band_rows['Very Satisfactory (85%-89%)'], {'male': 1, 'female': 0, 'total': 1}
        )
        self.assertEqual(summary['graded_total'], 1)


class Form137MapehMergeTests(TestCase):
    def setUp(self):
        self.sy = SchoolYear.objects.create(name='2025-2026', is_current=True)
        self.level = GradeLevel.objects.create(name='Grade 7', level=7)
        self.section = Section.objects.create(
            name='7-A', grade_level=self.level, school_year=self.sy
        )
        self.term = GradingPeriod.objects.create(
            name='Term 1', order=1, school_year=self.sy, is_current=True
        )
        self.filipino = Subject.objects.create(name='Filipino', code='FIL7', grade_level=self.level)
        self.ma = Subject.objects.create(name='MUSIC AND ARTS', code='MAPEH7-2', grade_level=self.level)
        self.peh = Subject.objects.create(
            name='PHYSICAL EDUCATION AND HEALTH', code='MAPEH7-1', grade_level=self.level
        )
        self.student = Student.objects.create(
            lrn='100000000001', first_name='Juan', last_name='Dela Cruz', sex='M',
            birthdate=datetime.date(2012, 1, 1), status='active',
            grade_level=self.level, section=self.section, school_year=self.sy,
        )
        for subject, value in ((self.filipino, '80'), (self.ma, '88'), (self.peh, '90')):
            Grade.objects.create(
                student=self.student, subject=subject, grading_period=self.term,
                school_year=self.sy, section=self.section, status='validated',
                quarter_grade=Decimal(value), final_grade=Decimal(value),
            )

    def test_parent_row_is_synthesized_from_components(self):
        block = build_grade_blocks(self.student)[0]
        rows = {row['subject_name']: row for row in block['subject_rows']}
        parent = rows['MAPEH']
        self.assertFalse(parent['is_mapeh_sub'])
        self.assertEqual(parent['q1'], Decimal('89'))
        self.assertEqual(parent['final_grade'], Decimal('89'))
        self.assertEqual(parent['remarks'], 'Passed')
        for name in ('MUSIC AND ARTS', 'PHYSICAL EDUCATION AND HEALTH'):
            self.assertTrue(rows[name]['is_mapeh_sub'])

    def test_general_average_counts_mapeh_once(self):
        block = build_grade_blocks(self.student)[0]
        self.assertEqual(block['general_average'], Decimal('84.5'))

    def test_printable_rows_keep_components_under_mapeh(self):
        block = build_grade_blocks(self.student)[0]
        printable = build_printable_subject_rows(block['subject_rows'])
        names = [row['display_name'] for row in printable]
        mapeh_index = names.index('MAPEH')
        self.assertEqual(names[mapeh_index + 1], 'Music and Arts')
        self.assertEqual(names[mapeh_index + 2], 'Physical Education and Health')
        self.assertEqual(names[mapeh_index + 3], 'Music')