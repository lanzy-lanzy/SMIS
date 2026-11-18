from datetime import date

from django.test import TestCase
from django.urls import reverse

from academics.models import GradeLevel, GradingPeriod, SchoolYear, Section, Subject, TeacherAssignment
from accounts.models import User
from form137.models import Form137Record
from grades.models import Grade, GradeSubmission
from students.models import Student


class DashboardSchoolYearTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admin', role='admin')
        cls.teacher = User.objects.create_user(username='teacher', role='teacher')
        cls.current_year = SchoolYear.objects.create(name='2026-2027', is_current=True)
        previous_year = SchoolYear.objects.create(name='2025-2026')
        grade_level = GradeLevel.objects.create(name='Grade 7', level=7)
        subject = Subject.objects.create(name='Mathematics', code='MATH7', grade_level=grade_level)
        year_cases = (
            (cls.current_year, cls.teacher, 'M'),
            (previous_year, User.objects.create_user(username='previous', role='teacher'), 'F'),
        )
        for index, (year, teacher, sex) in enumerate(year_cases):
            section = Section.objects.create(name='A', school_year=year, grade_level=grade_level)
            period = GradingPeriod.objects.create(name=f'Term {index}', order=1, school_year=year, is_current=True)
            learner = Student.objects.create(
                lrn=str(index), first_name='Learner', last_name=str(index), sex=sex,
                birthdate=date(2012, 1, 1), status='active', grade_level=grade_level,
                section=section, school_year=year,
            )
            TeacherAssignment.objects.create(teacher=teacher, subject=subject, section=section, school_year=year)
            GradeSubmission.objects.create(
                teacher=cls.teacher, subject=subject, section=section, school_year=year, grading_period=period,
            )
            Grade.objects.create(
                student=learner, subject=subject, section=section, school_year=year,
                grading_period=period, status='validated', quarter_grade=70,
            )
            Form137Record.objects.create(student=learner, school_year=year, grade_level=grade_level)

    def test_admin_dashboard_excludes_previous_year_from_totals(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard:index'))
        self.assertContains(response, '2026-2027')
        for metric in ('total_students', 'total_teachers', 'pending_submissions',
                       'validated_grades', 'form137_generated', 'at_risk_count'):
            self.assertEqual(response.context[metric], 1, metric)
        self.assertEqual(response.context['female_learners'], 0)
        self.assertEqual(response.context['grade_validation_total'], 2)

    def test_teacher_dashboard_uses_current_year_period_and_pending_count(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.context['total_learners'], 1)
        self.assertEqual(response.context['pending_submissions'], 1)
        self.assertEqual(response.context['current_period'].school_year, self.current_year)

    def test_no_current_year_shows_zero_counts(self):
        SchoolYear.objects.update(is_current=False)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard:index'))
        self.assertContains(response, 'No school year is marked current.')
        self.assertEqual(response.context['total_students'], 0)
        self.assertEqual(response.context['pending_submissions'], 0)
