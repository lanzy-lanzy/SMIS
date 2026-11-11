"""School Form 6 (SF6) summary tests."""

import datetime
from decimal import Decimal

from django.template.context import BaseContext
from django.test import TestCase
from django.urls import reverse

from academics.models import GradeLevel, GradingPeriod, SchoolYear, Section, Subject
from accounts.models import User
from grades.models import Grade
from reports.sf6 import build_sf6_summary, classify_finals
from students.models import Student


def _base_context_copy(self):
    duplicate = object.__new__(type(self))
    duplicate.__dict__.update(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate


class Python314ContextCopyMixin:
    """Django 5.1's BaseContext.__copy__ raises on Python 3.14, breaking rendered responses."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._original_context_copy = BaseContext.__copy__
        BaseContext.__copy__ = _base_context_copy

    @classmethod
    def tearDownClass(cls):
        BaseContext.__copy__ = cls._original_context_copy
        super().tearDownClass()


class ClassifyFinalsTests(TestCase):
    def test_no_final_grades_is_unclassified(self):
        self.assertEqual(classify_finals({}), (None, None, None))

    def test_bands_use_the_whole_number_general_average(self):
        cases = [
            (74, 'retained', 'did_not_meet'),
            (75, 'promoted', 'fairly_satisfactory'),
            (79, 'promoted', 'fairly_satisfactory'),
            (80, 'promoted', 'satisfactory'),
            (85, 'promoted', 'very_satisfactory'),
            (90, 'promoted', 'outstanding'),
        ]
        for grade, status, band in cases:
            with self.subTest(grade=grade):
                result = classify_finals({'Filipino': Decimal(grade)})
                self.assertEqual(result, (status, band, grade))

    def test_average_rounds_half_up(self):
        status, band, average = classify_finals({'Filipino': Decimal('89.5')})
        self.assertEqual((status, band, average), ('promoted', 'outstanding', 90))

    def test_one_or_two_failed_subjects_is_conditional(self):
        status, band, average = classify_finals({
            'Filipino': Decimal('80'),
            'English': Decimal('70'),
        })
        self.assertEqual((status, band, average), ('conditional', 'fairly_satisfactory', 75))

    def test_three_failed_subjects_is_retained_even_with_a_passing_average(self):
        status, band, average = classify_finals({
            'Filipino': Decimal('90'),
            'English': Decimal('70'),
            'Mathematics': Decimal('70'),
            'Science': Decimal('70'),
        })
        self.assertEqual((status, band, average), ('retained', 'fairly_satisfactory', 75))


class Sf6SummaryTests(TestCase):
    def setUp(self):
        self.sy = SchoolYear.objects.create(name='2025-2026', is_current=True)
        self.level7 = GradeLevel.objects.create(name='Grade 7', level=7)
        self.level8 = GradeLevel.objects.create(name='Grade 8', level=8)
        self.section7 = Section.objects.create(
            name='7-A', grade_level=self.level7, school_year=self.sy
        )
        self.section8 = Section.objects.create(
            name='8-A', grade_level=self.level8, school_year=self.sy
        )
        self.term1 = GradingPeriod.objects.create(
            name='Term 1', order=1, school_year=self.sy, is_current=True
        )
        self.term2 = GradingPeriod.objects.create(
            name='Term 2', order=2, school_year=self.sy
        )

        self.filipino7 = Subject.objects.create(
            name='Filipino', code='FIL7', grade_level=self.level7
        )
        self.english7 = Subject.objects.create(
            name='English', code='ENG7', grade_level=self.level7
        )
        self.mapeh8 = Subject.objects.create(
            name='MAPEH', code='MAPEH8', grade_level=self.level8
        )
        self.music8 = Subject.objects.create(
            name='Music', code='MUS8', grade_level=self.level8
        )

        self.linda = self._student('Linda', 'Domingo', 'F', self.level7, self.section7, '101')
        self.marco = self._student('Marco', 'Reyes', 'M', self.level7, self.section7, '102')
        self.nina = self._student('Nina', 'Cruz', 'F', self.level7, self.section7, '103')
        self.paul = self._student('Paul', 'Santos', 'M', self.level7, self.section7, '104')
        self.quinn = self._student('Quinn', 'Lopez', 'M', self.level8, self.section8, '105')

        # Linda: term 1 failing, term 2 passing - only the latest final counts.
        self._grade(self.linda, self.filipino7, self.term1, '60', self.section7)
        self._grade(self.linda, self.filipino7, self.term2, '90', self.section7)
        self._grade(self.linda, self.english7, self.term2, '90', self.section7)

        # Marco: passing average with one failed subject.
        self._grade(self.marco, self.filipino7, self.term2, '80', self.section7)
        self._grade(self.marco, self.english7, self.term2, '70', self.section7)

        # Nina: failing average.
        self._grade(self.nina, self.filipino7, self.term2, '60', self.section7)
        self._grade(self.nina, self.english7, self.term2, '60', self.section7)

        # Paul: draft grade only, so he stays unclassified.
        self._grade(self.paul, self.filipino7, self.term2, '60', self.section7, status='draft')

        # Quinn: MAPEH parent covers the Music sub-grade.
        self._grade(self.quinn, self.mapeh8, self.term2, '90', self.section8)
        self._grade(self.quinn, self.music8, self.term2, '50', self.section8)

        self.summary = build_sf6_summary(self.sy)

    def _student(self, first_name, last_name, sex, level, section, lrn):
        return Student.objects.create(
            lrn=lrn,
            first_name=first_name,
            last_name=last_name,
            sex=sex,
            birthdate=datetime.date(2012, 1, 1),
            address='Dumingag',
            parent_name='Parent',
            grade_level=level,
            section=section,
            school_year=self.sy,
            status='active',
        )

    def _grade(self, student, subject, period, final_grade, section, status='validated'):
        Grade.objects.create(
            student=student,
            subject=subject,
            grading_period=period,
            school_year=self.sy,
            section=section,
            final_grade=Decimal(final_grade),
            quarter_grade=Decimal(final_grade),
            status=status,
        )

    def _row(self, label):
        return next(row for row in self.summary['rows'] if row['label'] == label)

    def _cells(self, label):
        return {
            entry['label']: cell
            for entry, cell in zip(self.summary['levels'], self._row(label)['cells'])
        }

    def test_all_six_grade_levels_are_always_columns(self):
        self.assertEqual(
            [level['label'] for level in self.summary['levels']],
            ['GRADE 7', 'GRADE 8', 'GRADE 9', 'GRADE 10', 'GRADE 11', 'GRADE 12'],
        )

    def test_promoted_counts_by_sex_and_grade_level(self):
        cells = self._cells('PROMOTED')
        self.assertEqual(cells['GRADE 7'], {'male': 0, 'female': 1, 'total': 1})
        self.assertEqual(cells['GRADE 8'], {'male': 1, 'female': 0, 'total': 1})
        self.assertEqual(self._row('PROMOTED')['total'], {'male': 1, 'female': 1, 'total': 2})

    def test_conditional_and_retained_counts(self):
        self.assertEqual(
            self._cells('CONDITIONAL')['GRADE 7'],
            {'male': 1, 'female': 0, 'total': 1},
        )
        self.assertEqual(
            self._cells('RETAINED')['GRADE 7'],
            {'male': 0, 'female': 1, 'total': 1},
        )

    def test_achievement_bands_follow_the_general_average(self):
        self.assertEqual(
            self._cells('Outstanding (90%-100%)')['GRADE 7'],
            {'male': 0, 'female': 1, 'total': 1},
        )
        self.assertEqual(
            self._cells('Outstanding (90%-100%)')['GRADE 8'],
            {'male': 1, 'female': 0, 'total': 1},
        )
        self.assertEqual(
            self._cells('Fairly Satisfactory (75%-79%)')['GRADE 7'],
            {'male': 1, 'female': 0, 'total': 1},
        )
        self.assertEqual(
            self._cells('Did Not Meet Expectations (74% and below)')['GRADE 7'],
            {'male': 0, 'female': 1, 'total': 1},
        )

    def test_music_sub_grade_is_folded_into_mapeh(self):
        # Without folding, Quinn's average would be 70 and he would be retained.
        self.assertEqual(
            self._cells('RETAINED')['GRADE 8'],
            {'male': 0, 'female': 0, 'total': 0},
        )
        self.assertEqual(
            self._cells('PROMOTED')['GRADE 8'],
            {'male': 1, 'female': 0, 'total': 1},
        )

    def test_total_counts_enrollment_and_ungraded_learners(self):
        cells = self._cells('TOTAL')
        self.assertEqual(cells['GRADE 7'], {'male': 2, 'female': 2, 'total': 4})
        self.assertEqual(cells['GRADE 8'], {'male': 1, 'female': 0, 'total': 1})
        self.assertEqual(self._row('TOTAL')['total'], {'male': 3, 'female': 2, 'total': 5})
        self.assertEqual(self.summary['enrolled_total'], 5)
        self.assertEqual(self.summary['ungraded_total'], 1)

    def test_other_school_years_are_ignored(self):
        other = SchoolYear.objects.create(name='2026-2027')
        empty = build_sf6_summary(other)
        self.assertEqual(empty['enrolled_total'], 0)
        self.assertEqual(empty['graded_total'], 0)
        self.assertEqual(self._row('TOTAL')['total'], {'male': 3, 'female': 2, 'total': 5})


class Sf6ViewTests(Python314ContextCopyMixin, TestCase):
    def setUp(self):
        self.sy = SchoolYear.objects.create(name='2025-2026', is_current=True)
        self.registrar = User.objects.create_user(
            username='registrar', password='x', role='registrar'
        )
        self.admin = User.objects.create_user(
            username='admin', password='x', role='admin'
        )
        self.teacher = User.objects.create_user(
            username='teacher', password='x', role='teacher'
        )

    def test_registrar_can_open_the_sf6(self):
        self.client.force_login(self.registrar)
        response = self.client.get(reverse('reports:sf6'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'School Form 6 (SF6)')
        self.assertContains(response, 'Summarized Report on Promotion and Learning Progress')
        self.assertContains(response, 'PAQUITO S. YU MEMORIAL NATIONAL HIGH SCHOOL')
        self.assertContains(response, '314235')
        self.assertContains(response, '2025-2026')
        for level in (7, 8, 9, 10, 11, 12):
            self.assertContains(response, f'GRADE {level}')

    def test_admin_can_open_the_sf6(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('reports:sf6')).status_code, 200)

    def test_teacher_is_redirected(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('reports:sf6'))
        self.assertEqual(response.status_code, 302)

    def test_anonymous_user_is_redirected(self):
        response = self.client.get(reverse('reports:sf6'))
        self.assertEqual(response.status_code, 302)

    def test_reports_index_links_to_the_sf6(self):
        self.client.force_login(self.registrar)
        response = self.client.get(reverse('reports:index'))
        self.assertContains(response, reverse('reports:sf6'))
