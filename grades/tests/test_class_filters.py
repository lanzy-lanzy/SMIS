from django.test import TestCase
from django.urls import reverse

from academics.models import GradeLevel, GradingPeriod, SchoolYear, Section, Subject, TeacherAssignment
from accounts.models import User
from grades.models import GradeSubmission


class ClassFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admin', role='admin')
        cls.teacher = User.objects.create_user(username='ana', role='teacher', first_name='Ana', last_name='Reyes')
        another_teacher = User.objects.create_user(username='other', role='teacher')
        year = SchoolYear.objects.create(name='2026-2027', is_current=True)
        prior_year = SchoolYear.objects.create(name='2025-2026')
        cls.period = GradingPeriod.objects.create(name='First Term', order=1, school_year=year, is_current=True)
        cls.prior_period = GradingPeriod.objects.create(name='Old Term', order=1, school_year=prior_year, is_current=True)

        cls.level = GradeLevel.objects.create(name='Grade 7', level=7)
        math = Subject.objects.create(name='Mathematics', code='MATH7', grade_level=cls.level)
        cls.sections = [
            Section.objects.create(name=f'Nar{index:02}', grade_level=cls.level, school_year=year)
            for index in range(16)
        ]
        TeacherAssignment.objects.bulk_create([
            TeacherAssignment(teacher=cls.teacher, subject=math, section=section, school_year=year)
            for section in cls.sections
        ])
        GradeSubmission.objects.bulk_create([
            GradeSubmission(teacher=cls.teacher, subject=math, section=section, school_year=year,
                            grading_period=cls.period, status='approved')
            for section in cls.sections
        ])

        other_level = GradeLevel.objects.create(name='Grade 8', level=8)
        other_section = Section.objects.create(name='Other Section', grade_level=other_level, school_year=year)
        english = Subject.objects.create(name='English', code='ENG8', grade_level=other_level)
        TeacherAssignment.objects.create(
            teacher=another_teacher, subject=english, section=other_section, school_year=year,
        )

    def test_combined_filters_and_table_view_survive_paging_and_refresh(self):
        self.client.force_login(self.admin)
        url = reverse('grades:grade_list')
        filters = {'q': 'Ana Math', 'grade_level': self.level.pk, 'status': 'approved', 'view': 'table'}
        response = self.client.get(url, filters)
        self.assertContains(response, '16 class assignments')
        self.assertContains(response, 'Approved')
        self.assertNotContains(response, 'Other Section')
        self.assertContains(response, 'view=table&amp;page=2')

        response = self.client.get(url, {**filters, 'page': 2}, HTTP_HX_REQUEST='true')
        self.assertContains(response, 'Nar15')
        self.assertNotContains(response, 'Nar00')
        self.assertContains(response, 'q=Ana+Math')
        self.assertContains(response, f'period={self.period.pk}&amp;view=table')

    def test_teacher_scope_and_current_year_period(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('grades:grade_list'), {'period': self.prior_period.pk})
        self.assertContains(response, 'First Term (Current)')
        self.assertNotContains(response, 'Old Term')
        self.assertNotContains(response, 'Other Section')
        self.assertNotContains(response, 'ENG8')

    def test_missing_submission_and_empty_results(self):
        self.client.force_login(self.admin)
        url = reverse('grades:grade_list')
        response = self.client.get(url, {'status': 'unsubmitted'})
        self.assertContains(response, '1 class assignment')
        self.assertContains(response, 'Other Section')
        response = self.client.get(url, {'status': 'unsubmitted', 'grade_level': self.level.pk})
        self.assertContains(response, 'No classes match these filters')
