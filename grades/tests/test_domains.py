"""Cognitive/affective/behavioral domain grading tests."""

import datetime
from decimal import Decimal

from django.template.context import BaseContext
from django.test import TestCase
from django.urls import reverse

from academics.models import (
    GradeLevel, GradingPeriod, SchoolYear, Section, Subject, TeacherAssignment,
)
from accounts.models import User
from grades.models import (
    Grade, PT_DOMAIN_SHARES, WW_DOMAIN_SHARES,
    grade_remarks, scores_missing, split_domain_weights, weighted_initial_grade,
)
from grades.views import _maxes_from_grades, _parse_maxes
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


def ww_domains(cog, cog_max, aff=0, aff_max=0):
    return (
        ('cognitive', cog, cog_max, WW_DOMAIN_SHARES['cognitive']),
        ('affective', aff, aff_max, WW_DOMAIN_SHARES['affective']),
    )


def pt_domains(cog, cog_max, aff=0, aff_max=0, beh=0, beh_max=0):
    return (
        ('cognitive', cog, cog_max, PT_DOMAIN_SHARES['cognitive']),
        ('affective', aff, aff_max, PT_DOMAIN_SHARES['affective']),
        ('behavioral', beh, beh_max, PT_DOMAIN_SHARES['behavioral']),
    )


class SplitDomainWeightsTests(TestCase):
    def test_all_active_use_configured_shares(self):
        weights = split_domain_weights(ww_domains(45, 50, 40, 50), 20)
        self.assertEqual(weights, {'cognitive': Decimal('10'), 'affective': Decimal('10')})

    def test_unused_domain_share_folds_into_active(self):
        weights = split_domain_weights(ww_domains(45, 50), 20)
        self.assertEqual(weights, {'cognitive': Decimal('20'), 'affective': Decimal('0')})

    def test_partial_active_renormalizes_proportionally(self):
        weights = split_domain_weights(pt_domains(10, 20, beh=20, beh_max=30), 50)
        self.assertEqual(weights['cognitive'], Decimal('12.5'))
        self.assertEqual(weights['affective'], Decimal('0'))
        self.assertEqual(weights['behavioral'], Decimal('37.5'))

    def test_no_active_domains_get_zero_weight(self):
        weights = split_domain_weights(pt_domains(0, 0), 50)
        self.assertEqual(set(weights.values()), {Decimal('0')})

    def test_configured_highest_activates_domain_even_with_zero_score(self):
        weights = split_domain_weights(ww_domains(45, 50, 0, 50), 20)
        self.assertEqual(weights, {'cognitive': Decimal('10'), 'affective': Decimal('10')})


class WeightedInitialGradeTests(TestCase):
    def test_cognitive_only_matches_legacy_formula(self):
        # PS 90 x 20 + PS 90 x 50 + PS 90 x 30 = 90, exactly the pre-domain result.
        initial = weighted_initial_grade(
            ww_domains(45, 50), pt_domains(27, 30), 27, 30, 20, 50, 30,
        )
        self.assertEqual(initial, Decimal('90'))

    def test_full_domains_match_class_record(self):
        # WW: 90x10 + 80x10; PT: 90x10 + 80x10 + 90x30; QA: 90x30 -> 88.00
        initial = weighted_initial_grade(
            ww_domains(45, 50, 40, 50), pt_domains(27, 30, 24, 30, 27, 30),
            27, 30, 20, 50, 30,
        )
        self.assertEqual(initial, Decimal('88'))

    def test_zero_total_weight_returns_zero(self):
        initial = weighted_initial_grade(
            ww_domains(45, 50), pt_domains(27, 30), 27, 30, 0, 0, 0,
        )
        self.assertEqual(initial, Decimal('0'))


class GradeRemarkTests(TestCase):
    def test_term_grade_thresholds(self):
        self.assertEqual(grade_remarks(75), 'Passed')
        self.assertEqual(grade_remarks(74), 'Failed')
        self.assertEqual(grade_remarks(90, missing=True), 'Incomplete')

    def test_zero_is_complete_but_blank_is_missing(self):
        self.assertFalse(scores_missing([0], [10], 0, 10))
        self.assertTrue(scores_missing([None], [10], 0, 10))
        self.assertFalse(scores_missing([None], [0], 0, 0))


class ParseMaxesDomainTests(TestCase):
    def test_entered_domain_items_sum_into_total(self):
        post = {f'written_affective_highest_{i}': '10' for i in range(1, 6)}
        post.update({f'performance_behavioral_highest_{i}': '5' for i in range(1, 4)})
        maxes, error = _parse_maxes(post)
        self.assertIsNone(error)
        self.assertEqual(maxes['wa'], 50)
        self.assertEqual(maxes['wa_items'], [10.0] * 5)
        self.assertEqual(maxes['pb'], 15)
        self.assertEqual(maxes['pb_items'], [5.0] * 3)

    def test_posted_blank_domain_inputs_mark_domain_unused(self):
        post = {f'written_affective_highest_{i}': '' for i in range(1, 6)}
        maxes, error = _parse_maxes(post, fallback={'wa': 50, 'wa_items': [10.0] * 5})
        self.assertIsNone(error)
        self.assertEqual(maxes['wa'], 0)
        self.assertEqual(maxes['wa_items'], [None] * 5)

    def test_absent_domain_inputs_keep_stored_configuration(self):
        maxes, error = _parse_maxes({}, fallback={'wa': 50, 'wa_items': [10.0] * 5})
        self.assertIsNone(error)
        self.assertEqual(maxes['wa'], 50)
        self.assertEqual(maxes['wa_items'], [10.0] * 5)

    def test_negative_domain_highest_rejected(self):
        post = {'written_affective_highest_1': '-5'}
        maxes, error = _parse_maxes(post)
        self.assertIsNone(maxes)
        self.assertIn('greater than 0', error)

    def test_assessment_items_sum_into_one_total(self):
        post = {f'assessment_highest_{i}': '10' for i in range(1, 4)}
        maxes, error = _parse_maxes(post)
        self.assertIsNone(error)
        self.assertEqual(maxes['qa'], 30)
        self.assertEqual(maxes['as_items'], [10.0] * 3)
        self.assertNotIn('aa', maxes)


class GradeDomainTestCase(TestCase):
    """Shared fixtures: one teacher, one class, one learner, open first term."""

    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user(
            username='teacher', password='pw', role='teacher',
            first_name='Teach', last_name='Er',
        )
        cls.sy = SchoolYear.objects.create(name='2025-2026', is_current=True)
        cls.gl = GradeLevel.objects.create(name='Grade 7', level=7)
        cls.section = Section.objects.create(name='Jade', grade_level=cls.gl, school_year=cls.sy)
        cls.subject = Subject.objects.create(name='Values Education', code='VE7', grade_level=cls.gl)
        cls.period = GradingPeriod.objects.create(
            name='First Term', order=1, school_year=cls.sy,
            is_current=True, is_submissions_open=True,
        )
        cls.assignment = TeacherAssignment.objects.create(
            teacher=cls.teacher, subject=cls.subject, section=cls.section, school_year=cls.sy,
        )
        cls.student = Student.objects.create(
            lrn='123456789012', first_name='Juan', last_name='Dela Cruz',
            sex='M', birthdate=datetime.date(2012, 1, 1), address='Paquito S. Yu MNHS',
            parent_name='Maria Dela Cruz', grade_level=cls.gl, section=cls.section,
            school_year=cls.sy, status='transferred_in',
        )

    def setUp(self):
        self.client.force_login(self.teacher)

    def _post_data(self, prefix='', with_domains=True):
        data = {
            'period': self.period.pk,
            'action': 'draft',
            f'{prefix}written_weight': '20',
            f'{prefix}performance_weight': '50',
            f'{prefix}assessment_weight': '30',
        }
        for i in range(1, 6):
            data[f'{prefix}written_highest_{i}'] = '10'
            data[f'{prefix}student_{self.student.id}_written_{i}'] = '9'
        for i in range(1, 4):
            data[f'{prefix}performance_highest_{i}'] = '10'
            data[f'{prefix}student_{self.student.id}_performance_{i}'] = '9'
            data[f'{prefix}assessment_highest_{i}'] = '10'
            data[f'{prefix}student_{self.student.id}_assessment_{i}'] = '9'
        if with_domains:
            for i in range(1, 6):
                data[f'{prefix}written_affective_highest_{i}'] = '10'
                data[f'{prefix}student_{self.student.id}_written_affective_{i}'] = '8'
            for i in range(1, 4):
                data[f'{prefix}performance_affective_highest_{i}'] = '10'
                data[f'{prefix}student_{self.student.id}_performance_affective_{i}'] = '8'
                data[f'{prefix}performance_behavioral_highest_{i}'] = '10'
                data[f'{prefix}student_{self.student.id}_performance_behavioral_{i}'] = '9'
        return data

    def _grade(self):
        return Grade.objects.get(
            student=self.student, subject=self.subject,
            grading_period=self.period, school_year=self.sy,
        )


class GradeSaveDomainTests(GradeDomainTestCase):
    def test_domain_scores_round_trip_and_compute_initial_grade(self):
        response = self.client.post(
            reverse('grades:grade_save', args=[self.assignment.pk]), self._post_data(),
        )
        self.assertEqual(response.status_code, 302)
        grade = self._grade()
        self.assertEqual(grade.written_work_affective, Decimal('40'))
        self.assertEqual(grade.written_work_affective_highest, Decimal('50'))
        self.assertEqual(grade.written_work_affective_1, Decimal('8'))
        self.assertEqual(grade.written_work_affective_1_highest, Decimal('10'))
        self.assertEqual(grade.performance_task_affective, Decimal('24'))
        self.assertEqual(grade.performance_task_behavioral, Decimal('27'))
        self.assertEqual(grade.performance_task_behavioral_highest, Decimal('30'))
        self.assertEqual(grade.initial_grade, Decimal('88.00'))
        self.assertEqual(grade.quarter_grade, Decimal('90'))
        self.assertEqual(grade.remarks, 'Passed')

    def test_assessment_scores_use_the_full_category_weight(self):
        response = self.client.post(
            reverse('grades:grade_save', args=[self.assignment.pk]), self._post_data(),
        )
        self.assertEqual(response.status_code, 302)
        grade = self._grade()
        self.assertEqual(grade.assessment, Decimal('27'))
        self.assertEqual(grade.assessment_highest, Decimal('30'))
        self.assertEqual(grade.assessment_ps, Decimal('90'))
        self.assertEqual(grade.assessment_ws, Decimal('27.0'))
        self.assertEqual(grade.initial_grade, Decimal('88.00'))
        self.assertEqual(grade.quarter_grade, Decimal('90'))
        self.assertEqual(grade.remarks, 'Passed')

    def test_post_without_domains_keeps_legacy_computation(self):
        response = self.client.post(
            reverse('grades:grade_save', args=[self.assignment.pk]),
            self._post_data(with_domains=False),
        )
        self.assertEqual(response.status_code, 302)
        grade = self._grade()
        self.assertEqual(grade.written_work_affective, Decimal('0'))
        self.assertEqual(grade.written_work_affective_highest, Decimal('0'))
        self.assertIsNone(grade.written_work_affective_1)
        self.assertEqual(grade.performance_task_behavioral, Decimal('0'))
        # Cognitive-only domains renormalize to the full category weight: PS 90
        # across the board -> 90.00, identical to the pre-domain formula.
        self.assertEqual(grade.initial_grade, Decimal('90.00'))

    def test_domain_total_above_highest_is_rejected(self):
        data = self._post_data()
        for i in range(1, 6):
            data[f'student_{self.student.id}_written_affective_{i}'] = '11'
        response = self.client.post(
            reverse('grades:grade_save', args=[self.assignment.pk]), data,
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Grade.objects.filter(student=self.student).exists())

    def test_clearing_domain_inputs_deactivates_domain(self):
        url = reverse('grades:grade_save', args=[self.assignment.pk])
        self.client.post(url, self._post_data())
        data = self._post_data()
        for i in range(1, 6):
            data[f'written_affective_highest_{i}'] = ''
            data[f'student_{self.student.id}_written_affective_{i}'] = ''
        for i in range(1, 4):
            for cat in ('performance_affective', 'performance_behavioral'):
                data[f'{cat}_highest_{i}'] = ''
                data[f'student_{self.student.id}_{cat}_{i}'] = ''
        self.client.post(url, data)
        grade = self._grade()
        self.assertEqual(grade.written_work_affective, Decimal('0'))
        self.assertEqual(grade.written_work_affective_highest, Decimal('0'))
        self.assertEqual(grade.performance_task_affective, Decimal('0'))
        self.assertEqual(grade.performance_task_behavioral, Decimal('0'))
        self.assertEqual(grade.initial_grade, Decimal('90.00'))

    def test_maxes_display_reads_back_domain_configuration(self):
        self.client.post(reverse('grades:grade_save', args=[self.assignment.pk]), self._post_data())
        maxes = _maxes_from_grades(Grade.objects.filter(subject=self.subject))
        self.assertEqual(maxes['wa'], 50)
        self.assertEqual(maxes['wa_items'], [10.0] * 5)
        self.assertEqual(maxes['pa'], 30)
        self.assertEqual(maxes['pb'], 30)


class GradeRemarkSaveTests(GradeDomainTestCase):
    def test_complete_zero_scores_are_failed_not_incomplete(self):
        data = self._post_data(with_domains=False)
        for category, count in (('written', 5), ('performance', 3), ('assessment', 3)):
            for i in range(1, count + 1):
                data[f'student_{self.student.id}_{category}_{i}'] = '0'
        response = self.client.post(
            reverse('grades:grade_save', args=[self.assignment.pk]), data,
        )
        self.assertEqual(response.status_code, 302)
        grade = self._grade()
        self.assertEqual(grade.written_work_1, Decimal('0'))
        self.assertEqual(grade.initial_grade, Decimal('0'))
        self.assertEqual(grade.quarter_grade, Decimal('60'))
        self.assertEqual(grade.remarks, 'Failed')

    def test_blank_required_item_is_incomplete_even_with_passing_grade(self):
        data = self._post_data(with_domains=False)
        data[f'student_{self.student.id}_written_3'] = ''
        response = self.client.post(
            reverse('grades:grade_save', args=[self.assignment.pk]), data,
        )
        self.assertEqual(response.status_code, 302)
        grade = self._grade()
        self.assertIsNone(grade.written_work_3)
        self.assertGreaterEqual(grade.quarter_grade, 75)
        self.assertEqual(grade.remarks, 'Incomplete')

    def test_clearing_all_existing_scores_marks_grade_incomplete(self):
        url = reverse('grades:grade_save', args=[self.assignment.pk])
        self.client.post(url, self._post_data(with_domains=False))
        data = self._post_data(with_domains=False)
        for category, count in (('written', 5), ('performance', 3), ('assessment', 3)):
            for i in range(1, count + 1):
                data[f'student_{self.student.id}_{category}_{i}'] = ''
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        grade = self._grade()
        self.assertIsNone(grade.written_work_1)
        self.assertIsNone(grade.performance_task_1)
        self.assertIsNone(grade.assessment_1)
        self.assertEqual(grade.remarks, 'Incomplete')

    def test_blank_item_with_zero_maximum_is_optional(self):
        data = self._post_data(with_domains=False)
        data['written_highest_5'] = '0'
        data[f'student_{self.student.id}_written_5'] = ''
        response = self.client.post(
            reverse('grades:grade_save', args=[self.assignment.pk]), data,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._grade().remarks, 'Passed')


class GradeSaveAllDomainTests(GradeDomainTestCase):
    def test_encode_all_saves_domain_scores_with_assignment_prefix(self):
        prefix = f'assignment_{self.assignment.pk}_'
        response = self.client.post(
            reverse('grades:grade_save_all'), self._post_data(prefix=prefix),
        )
        self.assertEqual(response.status_code, 302)
        grade = self._grade()
        self.assertEqual(grade.written_work_affective, Decimal('40'))
        self.assertEqual(grade.performance_task_behavioral, Decimal('27'))
        self.assertEqual(grade.initial_grade, Decimal('88.00'))
        self.assertEqual(grade.quarter_grade, Decimal('90'))

    def test_encode_all_preserves_blank_scores(self):
        prefix = f'assignment_{self.assignment.pk}_'
        data = self._post_data(prefix=prefix)
        data[f'{prefix}student_{self.student.id}_written_3'] = ''
        response = self.client.post(reverse('grades:grade_save_all'), data)
        self.assertEqual(response.status_code, 302)
        grade = self._grade()
        self.assertEqual(grade.assessment, Decimal('27'))
        self.assertEqual(grade.assessment_highest, Decimal('30'))
        self.assertIsNone(grade.written_work_3)
        self.assertEqual(grade.remarks, 'Incomplete')

    def test_encode_all_clearing_existing_scores_marks_grade_incomplete(self):
        prefix = f'assignment_{self.assignment.pk}_'
        self.client.post(
            reverse('grades:grade_save_all'),
            self._post_data(prefix=prefix, with_domains=False),
        )
        data = self._post_data(prefix=prefix, with_domains=False)
        for category, count in (('written', 5), ('performance', 3), ('assessment', 3)):
            for i in range(1, count + 1):
                data[f'{prefix}student_{self.student.id}_{category}_{i}'] = ''
        response = self.client.post(reverse('grades:grade_save_all'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._grade().remarks, 'Incomplete')


class GradeComputeInitialTests(GradeDomainTestCase):
    def test_compute_initial_grade_is_domain_aware(self):
        grade = Grade(
            student=self.student, subject=self.subject, section=self.section,
            grading_period=self.period, school_year=self.sy,
            written_work=45, written_work_highest=50,
            written_work_affective=40, written_work_affective_highest=50,
            performance_task=27, performance_task_highest=30,
            performance_task_affective=24, performance_task_affective_highest=30,
            performance_task_behavioral=27, performance_task_behavioral_highest=30,
            assessment=27, assessment_highest=30,
        )
        self.assertEqual(grade.compute_initial_grade(), Decimal('88'))
        self.assertEqual(grade.written_work_cognitive_ws, Decimal('9'))
        self.assertEqual(grade.written_work_affective_ws, Decimal('8'))
        self.assertEqual(grade.performance_task_behavioral_ws, Decimal('27'))
        self.assertEqual(grade.written_work_ws, Decimal('17'))
        self.assertEqual(grade.performance_task_ws, Decimal('44'))


class EncodePageRenderTests(Python314ContextCopyMixin, GradeDomainTestCase):
    def test_encode_page_renders_domain_blocks(self):
        response = self.client.get(
            reverse('grades:grade_encode', args=[self.assignment.pk]),
            {'period': self.period.pk},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Cognitive', content)
        self.assertIn('Affective', content)
        self.assertIn('Behavioral', content)
        self.assertIn(f'name="student_{self.student.id}_written_affective_1"', content)
        self.assertIn(f'name="student_{self.student.id}_performance_affective_3"', content)
        self.assertIn(f'name="student_{self.student.id}_performance_behavioral_3"', content)
        self.assertNotIn('assessment_affective', content)
        self.assertIn('name="written_affective_highest_5"', content)
        self.assertIn('name="performance_behavioral_highest_1"', content)
        self.assertIn('grade-domain', content)
        self.assertEqual(content.count('Cognitive<br>'), 2)
        self.assertEqual(content.count('Affective<br>'), 2)
        self.assertEqual(
            content.count('<div class="grade-item-labels"><span>ST1</span><span>ST2</span><span>TE</span></div>'),
            2,
        )
        self.assertIn('<th colspan="2"', content)
        self.assertIn('<th colspan="3"', content)

    def test_encode_select_partial_renders_domain_blocks(self):
        response = self.client.get(
            reverse('grades:grade_encode_select'),
            {'assignment': self.assignment.pk, 'period': self.period.pk},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(f'name="student_{self.student.id}_written_affective_1"', content)
        self.assertIn('Behavioral', content)

    def test_encode_all_renders_prefixed_domain_blocks(self):
        response = self.client.get(
            reverse('grades:grade_encode_all'), {'period': self.period.pk},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        prefix = f'assignment_{self.assignment.pk}_student_{self.student.id}'
        self.assertIn(f'name="{prefix}_written_affective_1"', content)
        self.assertIn(f'name="{prefix}_performance_behavioral_3"', content)
        self.assertIn(f'name="assignment_{self.assignment.pk}_written_affective_highest_1"', content)


class SubjectIsEspTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gl = GradeLevel.objects.create(name='Grade 7', level=7)

    def test_esp_aliases_are_detected(self):
        cases = [
            ('Edukasyon sa Pagpapakatao', 'EsP', True),
            ('Values Education', 'VE7', True),
            ('GMRC / Values Education', 'GMRC', True),
            ('Edukasyon sa Pagpapakatao', 'ESP7', True),
            ('Values Ed', 'EsP', True),  # matched by code alone
            ('Mathematics', 'MATH7', False),
            ('English', 'EN7', False),
            ('Science', 'SCI7', False),
        ]
        for name, code, expected in cases:
            with self.subTest(name=name, code=code):
                subject = Subject(name=name, code=code, grade_level=self.gl)
                self.assertEqual(subject.is_esp, expected)


class ParseMaxesNonEspTests(TestCase):
    def test_non_esp_forces_domains_unused_even_when_posted(self):
        post = {f'written_affective_highest_{i}': '10' for i in range(1, 6)}
        post.update({f'performance_behavioral_highest_{i}': '10' for i in range(1, 4)})
        maxes, error = _parse_maxes(
            post, fallback={'wa': 50, 'wa_items': [10.0] * 5}, is_esp=False,
        )
        self.assertIsNone(error)
        self.assertEqual(maxes['wa'], 0)
        self.assertEqual(maxes['wa_items'], [None] * 5)
        self.assertEqual(maxes['pa'], 0)
        self.assertEqual(maxes['pb'], 0)
        self.assertEqual(maxes['pb_items'], [None] * 3)

    def test_non_esp_ignores_invalid_domain_input(self):
        maxes, error = _parse_maxes({'written_affective_highest_1': '-5'}, is_esp=False)
        self.assertIsNone(error)
        self.assertEqual(maxes['wa'], 0)


class NonEspGradeTests(Python314ContextCopyMixin, GradeDomainTestCase):
    """A non-ESP subject keeps the plain layout and ignores domain data."""

    def setUp(self):
        super().setUp()
        self.math = Subject.objects.create(name='Mathematics', code='MATH7', grade_level=self.gl)
        self.math_assignment = TeacherAssignment.objects.create(
            teacher=self.teacher, subject=self.math, section=self.section, school_year=self.sy,
        )

    def _math_grade(self):
        return Grade.objects.get(
            student=self.student, subject=self.math,
            grading_period=self.period, school_year=self.sy,
        )

    def test_encode_page_hides_domains_for_non_esp(self):
        response = self.client.get(
            reverse('grades:grade_encode', args=[self.math_assignment.pk]),
            {'period': self.period.pk},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn('Cognitive', content)
        self.assertNotIn('Affective', content)
        self.assertNotIn('Behavioral', content)
        self.assertNotIn('grade-domain-head', content)
        self.assertNotIn(f'name="student_{self.student.id}_written_affective_1"', content)
        self.assertNotIn(f'name="student_{self.student.id}_assessment_affective_1"', content)
        self.assertNotIn('name="written_affective_highest_1"', content)
        self.assertNotIn('name="assessment_affective_highest_1"', content)
        # Plain item inputs still render.
        self.assertIn(f'name="student_{self.student.id}_written_1"', content)
        self.assertIn(f'name="student_{self.student.id}_performance_1"', content)
        self.assertIn(f'name="student_{self.student.id}_assessment_1"', content)
        self.assertIn('ST1', content)
        self.assertIn('ST2', content)
        self.assertIn('TE', content)

    def test_save_ignores_posted_domains_for_non_esp(self):
        response = self.client.post(
            reverse('grades:grade_save', args=[self.math_assignment.pk]),
            self._post_data(with_domains=True),
        )
        self.assertEqual(response.status_code, 302)
        grade = self._math_grade()
        self.assertEqual(grade.written_work_affective, Decimal('0'))
        self.assertEqual(grade.written_work_affective_highest, Decimal('0'))
        self.assertIsNone(grade.written_work_affective_1)
        self.assertEqual(grade.performance_task_behavioral, Decimal('0'))
        self.assertIsNone(grade.performance_task_behavioral_1)
        # Cognitive-only renormalizes to the full category weights: PS 90 -> 90.00.
        self.assertEqual(grade.initial_grade, Decimal('90.00'))

    def test_save_all_ignores_posted_domains_for_non_esp(self):
        prefix = f'assignment_{self.math_assignment.pk}_'
        response = self.client.post(
            reverse('grades:grade_save_all'),
            self._post_data(prefix=prefix, with_domains=True),
        )
        self.assertEqual(response.status_code, 302)
        grade = self._math_grade()
        self.assertEqual(grade.written_work_affective, Decimal('0'))
        self.assertEqual(grade.performance_task_behavioral, Decimal('0'))
        self.assertEqual(grade.initial_grade, Decimal('90.00'))