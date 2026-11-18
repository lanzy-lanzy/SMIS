from datetime import date

from django.test import TestCase
from django.urls import reverse

from academics.models import GradeLevel, GradingPeriod, SchoolYear, Section, Subject, TeacherAssignment
from accounts.models import User
from form137.models import Form137Record
from grades.models import Grade
from students.models import Student


class SchoolYearFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admin', role='admin')
        teacher = User.objects.create_user(username='teacher', role='teacher')
        cls.current = SchoolYear.objects.create(name='2026-2027', is_current=True)
        cls.previous = SchoolYear.objects.create(name='2025-2026')
        grade = GradeLevel.objects.create(name='Grade 7', level=7)
        subject = Subject.objects.create(name='Math', code='MATH7', grade_level=grade)

        for index, year in enumerate((cls.current, cls.previous)):
            label = 'Current' if index == 0 else 'Previous'
            section = Section.objects.create(name=f'{label} Section', grade_level=grade, school_year=year)
            student = Student.objects.create(
                lrn=str(index), first_name=label, last_name='Learner', sex='F',
                birthdate=date(2012, 1, 1), grade_level=grade, school_year=year, section=section,
            )
            term = GradingPeriod.objects.create(name=f'{label} Term', order=1, school_year=year)
            TeacherAssignment.objects.create(
                teacher=teacher, subject=subject, section=section, school_year=year,
            )
            Form137Record.objects.create(student=student, school_year=year, grade_level=grade)
            Grade.objects.create(
                student=student, section=section, school_year=year, grading_period=term,
                subject=subject, status='validated', quarter_grade=60 + index * 10,
            )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_lists_default_to_current_and_allow_prior_or_all_years(self):
        lists = (
            ('students:student_list', 'year', 'Current Learner', 'Previous Learner'),
            ('academics:assignment_list', 'school_year', 'Current Section', 'Previous Section'),
            ('academics:section_list', 'school_year', 'Current Section', 'Previous Section'),
            ('academics:grading_period_list', 'school_year', 'Current Term', 'Previous Term'),
            ('form137:form137_list', 'sy', 'Current Learner', 'Previous Learner'),
            ('reports:section_performance', 'sy', 'Current Section', 'Previous Section'),
            ('reports:grade_trends', 'sy', 'Current Term', 'Previous Term'),
            ('reports:at_risk_students', 'sy', 'Current Learner', 'Previous Learner'),
        )
        for name, field, current_row, previous_row in lists:
            with self.subTest(list=name):
                url = reverse(name)
                response = self.client.get(url)
                self.assertContains(response, '2026-2027 (Current)')
                self.assertContains(response, current_row)
                self.assertNotContains(response, previous_row)

                response = self.client.get(url, {field: self.previous.pk})
                self.assertContains(response, previous_row)
                self.assertNotContains(response, current_row)

                response = self.client.get(url, {field: 'all'})
                self.assertContains(response, current_row)
                self.assertContains(response, previous_row)

    def test_student_year_change_clears_stale_section_and_preserves_year_on_paging(self):
        stale_section = Section.objects.get(school_year=self.current)
        response = self.client.get(
            reverse('students:student_list'),
            {'year': self.previous.pk, 'section': stale_section.pk},
            HTTP_HX_REQUEST='true',
        )
        self.assertContains(response, 'Previous Learner')
        self.assertNotContains(response, 'Current Section')
        self.assertContains(response, f'year={self.previous.pk}')
        self.assertContains(response, 'hx-swap-oob="outerHTML"')

    def test_assignment_section_view_honors_school_year_on_refresh(self):
        response = self.client.get(
            reverse('academics:assignment_list'),
            {'view': 'section', 'school_year': self.previous.pk},
            HTTP_HX_REQUEST='true',
        )
        self.assertContains(response, 'Previous Section')
        self.assertNotContains(response, 'Current Section')

    def test_no_current_year_falls_back_to_all(self):
        SchoolYear.objects.update(is_current=False)
        response = self.client.get(reverse('students:student_list'))
        self.assertContains(response, 'Current Learner')
        self.assertContains(response, 'Previous Learner')
