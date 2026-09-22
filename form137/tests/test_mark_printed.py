"""Tests for the Form 137 mark-as-printed endpoint (issuance loop)."""

import datetime

from django.test import TestCase
from django.urls import reverse

from accounts.models import AuditLog, User
from academics.models import GradeLevel, SchoolYear
from form137.models import Form137Record
from students.models import Student


class Form137MarkPrintedTests(TestCase):
    def setUp(self):
        self.registrar = User.objects.create_user(
            username='registrar', password='x', role='registrar',
            first_name='R', last_name='G',
        )
        self.teacher = User.objects.create_user(
            username='teacher', password='x', role='teacher',
            first_name='T', last_name='E',
        )
        self.school_year = SchoolYear.objects.create(name='2025-2026')
        self.grade_level = GradeLevel.objects.create(name='Grade 7', level=7)
        self.student = Student.objects.create(
            lrn='123456789012', first_name='Ana', last_name='Dela Cruz',
            sex='F', birthdate=datetime.date(2012, 1, 1),
            birthplace='Zamboanga', address='Purok 1', parent_name='Juan',
            grade_level=self.grade_level, school_year=self.school_year,
        )
        self.record = Form137Record.objects.create(
            student=self.student, school_year=self.school_year,
            grade_level=self.grade_level, generated_by=self.registrar,
        )

    def _url(self):
        return reverse('form137:form137_mark_printed', args=[self.record.pk])

    def test_registrar_post_marks_printed_and_audits(self):
        self.client.force_login(self.registrar)
        response = self.client.post(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        self.assertTrue(response.json()['newly_marked'])

        self.record.refresh_from_db()
        self.assertTrue(self.record.is_printed)
        self.assertTrue(
            AuditLog.objects.filter(
                user=self.registrar, action='form137_print',
                model_name='Form137Record', object_id=str(self.record.pk),
            ).exists()
        )

    def test_repeat_post_is_idempotent_and_not_reaudited(self):
        self.client.force_login(self.registrar)
        self.client.post(self._url())
        response = self.client.post(self._url())

        self.assertFalse(response.json()['newly_marked'])
        self.assertEqual(
            AuditLog.objects.filter(action='form137_print').count(), 1
        )

    def test_get_not_allowed(self):
        self.client.force_login(self.registrar)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 405)

    def test_teacher_cannot_mark_printed(self):
        self.client.force_login(self.teacher)
        response = self.client.post(self._url())

        # role_required redirects to login instead of performing the action.
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(reverse('accounts:login')))
        self.record.refresh_from_db()
        self.assertFalse(self.record.is_printed)
