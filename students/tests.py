from datetime import date
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse

from academics.models import GradeLevel, GradingPeriod, SchoolYear, Section, Subject
from accounts.models import AuditLog, User
from grades.models import Grade
from reports.sf6 import build_sf6_summary
from students.models import Student, StudentPromotion


class StudentPromotionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.registrar = User.objects.create_user(username='registrar', role='registrar')
        cls.source_year = SchoolYear.objects.create(name='2025-2026')
        cls.destination_year = SchoolYear.objects.create(name='2026-2027', is_current=True)
        cls.grade7 = GradeLevel.objects.create(name='Grade 7', level=7)
        cls.grade8 = GradeLevel.objects.create(name='Grade 8', level=8)
        cls.source_section = Section.objects.create(
            name='A', grade_level=cls.grade7, school_year=cls.source_year,
        )
        cls.destination_section = Section.objects.create(
            name='B', grade_level=cls.grade8, school_year=cls.destination_year,
        )
        cls.student = Student.objects.create(
            lrn='123', first_name='Ana', last_name='Santos', sex='F',
            birthdate=date(2012, 1, 1), grade_level=cls.grade7, status='active',
            school_year=cls.source_year, section=cls.source_section,
        )
        cls.subject = Subject.objects.create(name='English', code='ENG7', grade_level=cls.grade7)
        for order, name in GradingPeriod.PERIOD_CHOICES:
            term = GradingPeriod.objects.create(name=name, order=order, school_year=cls.source_year)
            Grade.objects.create(
                student=cls.student, section=cls.source_section, school_year=cls.source_year,
                subject=cls.subject, grading_period=term, status='validated', quarter_grade=80,
                final_grade=80,
            )

    def setUp(self):
        self.client.force_login(self.registrar)
        self.url = reverse('students:student_promote', args=[self.student.pk])
        self.data = {
            'source_year': self.source_year.pk,
            'source_grade': self.grade7.pk,
            'section': self.destination_section.pk,
        }

    def test_promotion_updates_placement_and_preserves_history(self):
        self.assertContains(self.client.get(self.url), 'Confirm promotion')
        self.assertFalse(StudentPromotion.objects.exists())
        response = self.client.post(self.url, self.data)
        self.assertRedirects(response, reverse('students:student_detail', args=[self.student.pk]))
        self.student.refresh_from_db()
        self.assertEqual(self.student.grade_level, self.grade8)
        self.assertEqual(self.student.school_year, self.destination_year)
        self.assertEqual(self.student.section, self.destination_section)
        self.assertEqual(Grade.objects.filter(student=self.student, section=self.source_section).count(), 3)
        promotion = StudentPromotion.objects.get(student=self.student)
        self.assertEqual(promotion.from_section, self.source_section)
        self.assertEqual(promotion.promoted_by, self.registrar)
        self.assertTrue(AuditLog.objects.filter(description__startswith='Promoted Ana Santos').exists())
        summary = build_sf6_summary(self.source_year)
        promoted = next(row for row in summary['rows'] if row['label'] == 'PROMOTED')
        self.assertEqual(promoted['cells'][0]['total'], 1)
        self.client.post(self.url, self.data)
        self.assertEqual(StudentPromotion.objects.count(), 1)

    def test_draft_and_failing_grades_block_promotion(self):
        term_grade = Grade.objects.get(student=self.student, grading_period__order=1)
        Grade.objects.filter(pk=term_grade.pk).update(status='draft')
        self.assertContains(self.client.post(self.url, self.data), 'Finalized grades are missing')
        Grade.objects.filter(pk=term_grade.pk).update(status='locked', quarter_grade=50)
        self.assertContains(self.client.post(self.url, self.data), 'A final grade of at least 75')
        self.student.refresh_from_db()
        self.assertEqual(self.student.grade_level, self.grade7)
        self.assertFalse(StudentPromotion.objects.exists())

    def test_invalid_section_and_teacher_cannot_promote(self):
        response = self.client.post(self.url, {**self.data, 'section': self.source_section.pk})
        self.assertContains(response, 'Select a valid choice')
        teacher = User.objects.create_user(username='teacher', role='teacher')
        self.client.force_login(teacher)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)
        self.assertFalse(StudentPromotion.objects.exists())

    def test_mapeh_requires_both_components_and_uses_the_combined_mark(self):
        subject = Subject.objects.create(name='MAPEH', code='MAPEH7', grade_level=self.grade7)
        for term in GradingPeriod.objects.filter(school_year=self.source_year):
            Grade.objects.create(
                student=self.student, section=self.source_section, school_year=self.source_year,
                subject=subject, grading_period=term, status='validated', component='ma',
                quarter_grade=70, final_grade=70,
            )
        self.assertContains(self.client.post(self.url, self.data), 'Finalized grades are missing')
        for term in GradingPeriod.objects.filter(school_year=self.source_year):
            Grade.objects.create(
                student=self.student, section=self.source_section, school_year=self.source_year,
                subject=subject, grading_period=term, status='locked', component='peh',
                quarter_grade=80, final_grade=80,
            )
        self.assertRedirects(self.client.post(self.url, self.data),
                             reverse('students:student_detail', args=[self.student.pk]))

    def _bulk_url(self, **filters):
        params = {
            'year': self.source_year.pk, 'grade': self.grade7.pk,
            'destination': self.destination_section.pk, **filters,
        }
        return f"{reverse('students:bulk_promotion')}?{urlencode(params)}"

    def _second_student(self, *, passing):
        student = Student.objects.create(
            lrn='456', first_name='Luis', last_name='Reyes', sex='M',
            birthdate=date(2012, 1, 1), grade_level=self.grade7, status='active',
            school_year=self.source_year, section=self.source_section,
        )
        if passing:
            for term in GradingPeriod.objects.filter(school_year=self.source_year):
                Grade.objects.create(
                    student=student, section=self.source_section, school_year=self.source_year,
                    subject=self.subject, grading_period=term, status='validated',
                    quarter_grade=85, final_grade=85,
                )
        return student

    def test_bulk_promotes_selected_students_and_lists_history(self):
        second = self._second_student(passing=True)
        url = self._bulk_url(section=self.source_section.pk)
        preview = self.client.get(url)
        self.assertContains(preview, '2 ready on this page')
        self.assertFalse(StudentPromotion.objects.exists())

        response = self.client.post(url, {'student': [self.student.pk, second.pk]}, follow=True)
        self.assertContains(response, '2 students were promoted')
        self.assertContains(response, '2 recorded for the selected year')
        self.assertEqual(StudentPromotion.objects.filter(to_section=self.destination_section).count(), 2)
        for student in (self.student, second):
            student.refresh_from_db()
            self.assertEqual(student.grade_level, self.grade8)
            self.assertEqual(student.section, self.destination_section)
            self.assertEqual(student.school_year, self.destination_year)
        self.assertEqual(Grade.objects.filter(school_year=self.source_year).count(), 6)
        self.assertContains(self.client.post(url, {'student': [second.pk]}), 'no longer in this cohort')

    def test_bulk_preview_explains_blocked_students_and_revalidates_the_batch(self):
        second = self._second_student(passing=True)
        url = self._bulk_url()
        self.assertContains(self.client.get(url), '2 ready on this page')
        Grade.objects.filter(student=second, grading_period__order=1).update(status='returned')
        response = self.client.post(url, {'student': [self.student.pk, second.pk]})
        self.assertContains(response, 'Luis Reyes (456): Finalized grades are missing')
        self.assertContains(response, '1 blocked on this page')
        self.assertFalse(StudentPromotion.objects.exists())
        self.student.refresh_from_db()
        self.assertEqual(self.student.grade_level, self.grade7)

    def test_bulk_rejects_wrong_destination_and_teachers(self):
        url = self._bulk_url(destination=self.source_section.pk)
        response = self.client.post(url, {'student': [self.student.pk]})
        self.assertContains(response, 'select a destination section before confirming')
        teacher = User.objects.create_user(username='bulk-teacher', role='teacher')
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.post(url, {'student': [self.student.pk]}).status_code, 302)
        self.assertFalse(StudentPromotion.objects.exists())
