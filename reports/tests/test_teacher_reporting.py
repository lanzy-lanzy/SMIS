"""Teacher-scoped reporting: dashboard cards, Class Record, Class Summary, report cards."""

import datetime
from decimal import Decimal

from django.template.context import BaseContext
from django.test import TestCase
from django.urls import reverse

from academics.models import (
    GradeLevel,
    GradingPeriod,
    SchoolYear,
    Section,
    Subject,
    TeacherAssignment,
)
from accounts.models import User
from grades.models import Grade
from students.models import Student


def _base_context_copy(self):
    duplicate = object.__new__(type(self))
    duplicate.__dict__.update(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate


class Python314ContextCopyMixin:
    """Django 5.1's BaseContext.__copy__ raises on Python 3.14, breaking response.context."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._original_context_copy = BaseContext.__copy__
        BaseContext.__copy__ = _base_context_copy

    @classmethod
    def tearDownClass(cls):
        BaseContext.__copy__ = cls._original_context_copy
        super().tearDownClass()


class TeacherReportingTests(Python314ContextCopyMixin, TestCase):
    def setUp(self):
        self.sy = SchoolYear.objects.create(name='2025-2026', is_current=True)
        self.level = GradeLevel.objects.create(name='Grade 7', level=7)
        self.section_a = Section.objects.create(
            name='7-A', grade_level=self.level, school_year=self.sy
        )
        self.section_b = Section.objects.create(
            name='7-B', grade_level=self.level, school_year=self.sy
        )

        self.adviser = User.objects.create_user(
            username='adviser', password='x', role='teacher',
            first_name='Ada', last_name='Reyes',
        )
        self.other = User.objects.create_user(
            username='other', password='x', role='teacher',
            first_name='Ben', last_name='Cruz',
        )
        self.section_a.adviser = self.adviser
        self.section_a.save()
        self.section_b.adviser = self.other
        self.section_b.save()

        self.filipino = Subject.objects.create(
            name='Filipino', code='FIL', grade_level=self.level
        )
        self.english = Subject.objects.create(
            name='English', code='ENG', grade_level=self.level
        )
        for subject in (self.filipino, self.english):
            TeacherAssignment.objects.create(
                teacher=self.adviser, subject=subject,
                section=self.section_a, school_year=self.sy,
            )
        TeacherAssignment.objects.create(
            teacher=self.other, subject=self.english,
            section=self.section_b, school_year=self.sy,
        )

        self.terms = [
            GradingPeriod.objects.create(
                name=f'Term {order}', order=order,
                school_year=self.sy, is_current=(order == 1),
            )
            for order in (1, 2, 3)
        ]

        self.boy = self._student('Juan', 'M', self.section_a, '100000000001')
        self.girl = self._student('Maria', 'F', self.section_a, '100000000002')
        self.outsider = self._student('Pedro', 'M', self.section_b, '100000000003')

    def _student(self, first_name, sex, section, lrn):
        return Student.objects.create(
            lrn=lrn, first_name=first_name, last_name='Dela Cruz', sex=sex,
            birthdate=datetime.date(2012, 1, 1), status='active',
            grade_level=self.level, section=section, school_year=self.sy,
        )

    def _grade(self, student, subject, order, quarter_grade):
        return Grade.objects.create(
            student=student, subject=subject,
            grading_period=self.terms[order - 1],
            school_year=self.sy, section=student.section,
            status='validated', quarter_grade=quarter_grade,
        )

    def test_teacher_dashboard_counts_learners_by_sex(self):
        self.client.force_login(self.adviser)
        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_learners'], 2)
        self.assertEqual(response.context['male_learners'], 1)
        self.assertEqual(response.context['female_learners'], 1)
        self.assertContains(response, 'No. of Learners')

    def test_class_record_scoped_to_taught_subjects(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse('reports:class_record'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['section'], self.section_b)
        self.assertEqual(
            [subject.name for subject in response.context['subjects']],
            ['English'],
        )

    def test_class_record_lists_grades_and_final(self):
        for order, value in ((1, 90), (2, 88), (3, 86)):
            self._grade(self.boy, self.filipino, order, value)
        self.client.force_login(self.adviser)
        response = self.client.get(
            reverse('reports:class_record'), {'subject': self.filipino.pk}
        )

        rows = response.context['male_rows'] + response.context['female_rows']
        row = next(r for r in rows if r['student'] == self.boy)
        self.assertEqual(row['term_cells'], [90, 88, 86])
        self.assertEqual(row['final_grade'], 88)
        self.assertEqual(row['remark'], 'Passed')

    def test_class_record_includes_validated_exam_analysis_and_mps(self):
        for student, scores in ((self.boy, (8, 9, 10)), (self.girl, (6, 7, 8))):
            grade = self._grade(student, self.filipino, 1, 90)
            for number, score in enumerate(scores, start=1):
                setattr(grade, f'assessment_{number}', score)
                setattr(grade, f'assessment_{number}_highest', 10)
            grade.save()

        draft_student = self._student('Draft', 'M', self.section_a, '100000000004')
        draft = self._grade(draft_student, self.filipino, 1, 90)
        draft.status = 'draft'
        draft.assessment_1 = 10
        draft.assessment_1_highest = 10
        draft.save()

        self.client.force_login(self.adviser)
        response = self.client.get(
            reverse('reports:class_record'), {'subject': self.filipino.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['exam_analysis']), 3)
        st1 = response.context['exam_analysis'][0]['items'][0]
        self.assertEqual(st1['label'], 'ST1')
        self.assertEqual(st1['examinees'], 2)
        self.assertEqual(st1['highest_possible'], 10)
        self.assertEqual(st1['passed_count'], 1)
        self.assertEqual(st1['passed_percent'], 50)
        self.assertEqual(st1['below_count'], 1)
        self.assertEqual(st1['below_percent'], 50)
        self.assertEqual(st1['mean'], 7)
        self.assertEqual(st1['median'], 7)
        self.assertAlmostEqual(st1['sd'], 1.41421356)
        self.assertEqual(st1['mps'], 70)
        self.assertEqual(st1['highest_score'], 8)
        self.assertEqual(st1['lowest_score'], 6)
        self.assertEqual(st1['total_score'], 14)
        self.assertContains(response, 'Test/Exam Results Analysis')
        self.assertContains(response, 'MPS/PL (%)')
        self.assertContains(response, 'Standard Deviation')

    def test_class_summary_shows_only_advised_section(self):
        self._grade(self.boy, self.filipino, 1, 90)
        self._grade(self.boy, self.english, 1, 86)
        self.client.force_login(self.adviser)
        response = self.client.get(reverse('reports:class_summary'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['section'], self.section_a)
        self.assertEqual(
            [subject['label'] for subject in response.context['subjects']],
            ['Filipino', 'English'],
        )
        listed = [
            row['student']
            for row in response.context['male_rows'] + response.context['female_rows']
        ]
        self.assertIn(self.boy, listed)
        self.assertIn(self.girl, listed)
        self.assertNotIn(self.outsider, listed)

    def test_class_summary_ranks_class_wide(self):
        self._grade(self.boy, self.filipino, 1, 90)
        self._grade(self.girl, self.filipino, 1, 95)
        self.client.force_login(self.adviser)
        response = self.client.get(reverse('reports:class_summary'))

        rank_by_student = {
            row['student']: row['rank']
            for row in response.context['male_rows'] + response.context['female_rows']
        }
        self.assertEqual(rank_by_student[self.girl], 1)
        self.assertEqual(rank_by_student[self.boy], 2)

    def test_class_summary_hidden_from_non_adviser(self):
        self.section_b.adviser = None
        self.section_b.save()
        self.client.force_login(self.other)
        response = self.client.get(reverse('reports:class_summary'))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['section'])
        self.assertContains(response, 'Class Summary is available to section advisers')

    def test_templates_hub_lists_document_cards(self):
        self.client.force_login(self.adviser)
        response = self.client.get(reverse('reports:report_templates'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Class Record')
        self.assertContains(response, 'Class Summary')
        self.assertContains(response, 'Report Cards')

    def test_templates_hub_hides_class_summary_from_non_adviser(self):
        self.section_b.adviser = None
        self.section_b.save()
        self.client.force_login(self.other)
        response = self.client.get(reverse('reports:report_templates'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Adviser only')
        self.assertNotContains(response, reverse('reports:class_summary'))

    def test_sidebar_groups_documents_under_templates(self):
        self.client.force_login(self.adviser)
        response = self.client.get(reverse('dashboard:index'))

        self.assertContains(response, reverse('reports:report_templates'))
        self.assertContains(response, '<span>Templates</span>', html=True)
        self.assertNotContains(response, '<span>Class Record</span>', html=True)
        self.assertNotContains(response, '<span>Report Cards</span>', html=True)

    def test_report_card_select_scoped_to_taught_or_advised_sections(self):
        self.client.force_login(self.adviser)
        response = self.client.get(reverse('reports:report_card_select'))

        listed = list(response.context['students_list'])
        self.assertIn(self.boy, listed)
        self.assertIn(self.girl, listed)
        self.assertNotIn(self.outsider, listed)

    def test_report_card_allowed_for_advisee(self):
        self.client.force_login(self.adviser)
        response = self.client.get(
            reverse('reports:report_card', args=[self.boy.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_report_card_denied_for_other_section(self):
        self.client.force_login(self.adviser)
        response = self.client.get(
            reverse('reports:report_card', args=[self.outsider.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('reports:report_card_select'))


class AverageGradeTests(TestCase):
    def test_average_grade_rounds_half_up(self):
        from reports.views import _average_grade

        self.assertEqual(_average_grade([90, 88, 86]), 88)
        self.assertEqual(_average_grade([89, 90, 90]), 90)
        self.assertIsNone(_average_grade([]))

    def test_assign_ranks_averages_ties(self):
        from reports.views import _assign_ranks

        rows = [
            {'final_grade': Decimal('95'), 'rank': None},
            {'final_grade': Decimal('90'), 'rank': None},
            {'final_grade': Decimal('90'), 'rank': None},
            {'final_grade': None, 'rank': None},
        ]
        _assign_ranks(rows)

        self.assertEqual([row['rank'] for row in rows], [1, 2.5, 2.5, None])
