"""Bulk deletion of sections from the Sections page."""

import datetime

from django.template.context import BaseContext
from django.test import TestCase
from django.urls import reverse

from academics.models import (
    GradeLevel,
    SchoolYear,
    Section,
    Subject,
    TeacherAssignment,
)
from accounts.models import AuditLog, User
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


class SectionBulkDeleteTests(Python314ContextCopyMixin, TestCase):
    def setUp(self):
        self.sy = SchoolYear.objects.create(name='2025-2026', is_current=True)
        self.level = GradeLevel.objects.create(name='Grade 7', level=7)
        self.section_a, self.section_b, self.section_c = (
            Section.objects.create(
                name=f'7-{letter}', grade_level=self.level, school_year=self.sy
            )
            for letter in 'ABC'
        )
        self.admin = User.objects.create_user(
            username='admin', password='x', role='admin'
        )
        self.registrar = User.objects.create_user(
            username='registrar', password='x', role='registrar'
        )
        self.teacher = User.objects.create_user(
            username='teacher', password='x', role='teacher'
        )
        self.subject = Subject.objects.create(
            name='Mathematics', code='MATH7', grade_level=self.level
        )
        self.student = Student.objects.create(
            lrn='123456789012',
            first_name='Ana',
            last_name='Santos',
            sex='F',
            birthdate=datetime.date(2012, 1, 1),
            address='Dumingag',
            parent_name='Parent',
            grade_level=self.level,
            section=self.section_a,
            school_year=self.sy,
            status='active',
        )
        self.assignment = TeacherAssignment.objects.create(
            teacher=self.teacher,
            subject=self.subject,
            section=self.section_a,
            school_year=self.sy,
        )
        self.url = reverse('academics:section_bulk_delete')

    def test_confirm_modal_lists_selection_and_side_effects(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            self.url,
            {'ids': f'{self.section_a.pk},{self.section_b.pk}'},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Delete 2 sections')
        self.assertContains(response, str(self.section_a))
        self.assertContains(response, str(self.section_b))
        self.assertNotContains(response, str(self.section_c))
        self.assertContains(response, '1 learner will lose their section assignment')
        self.assertContains(response, '1 teaching assignment will be removed')
        self.assertContains(response, f'name="section_ids" value="{self.section_a.pk}"')

    def test_post_deletes_only_the_selected_sections(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            self.url,
            {'section_ids': [self.section_a.pk, self.section_b.pk]},
        )

        self.assertRedirects(response, reverse('academics:section_list'))
        self.assertFalse(
            Section.objects.filter(
                pk__in=[self.section_a.pk, self.section_b.pk]
            ).exists()
        )
        self.assertTrue(Section.objects.filter(pk=self.section_c.pk).exists())

    def test_deleting_a_section_unassigns_learners_and_drops_assignments(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {'section_ids': [self.section_a.pk]})

        self.student.refresh_from_db()
        self.assertIsNone(self.student.section)
        self.assertFalse(
            TeacherAssignment.objects.filter(pk=self.assignment.pk).exists()
        )

    def test_each_deleted_section_is_audited(self):
        self.client.force_login(self.admin)
        self.client.post(
            self.url, {'section_ids': [self.section_a.pk, self.section_b.pk]}
        )

        logs = AuditLog.objects.filter(action='delete', model_name='Section')
        self.assertEqual(logs.count(), 2)
        self.assertEqual(
            set(logs.values_list('object_id', flat=True)),
            {str(self.section_a.pk), str(self.section_b.pk)},
        )
        self.assertTrue(all(log.user_id == self.admin.pk for log in logs))

    def test_htmx_post_closes_modal_and_refreshes_table(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            self.url, {'section_ids': [self.section_a.pk]}, HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'closeModal();')
        self.assertContains(response, 'htmx.trigger("#section-table", "refresh");')
        self.assertEqual(response.headers['HX-Trigger'], 'closeModal,refreshTable')

    def test_unknown_and_malformed_ids_delete_nothing(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            self.url, {'section_ids': ['abc', '', '999999']}
        )

        self.assertRedirects(response, reverse('academics:section_list'))
        self.assertEqual(Section.objects.count(), 3)

    def test_empty_selection_deletes_nothing(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {})

        self.assertRedirects(response, reverse('academics:section_list'))
        self.assertEqual(Section.objects.count(), 3)

    def test_confirm_without_ids_redirects_with_an_error(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)

        self.assertRedirects(response, reverse('academics:section_list'))
        self.assertEqual(Section.objects.count(), 3)

    def test_registrar_and_teacher_cannot_bulk_delete(self):
        for user in (self.registrar, self.teacher):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.url).status_code, 302)
                self.assertEqual(
                    self.client.post(
                        self.url, {'section_ids': [self.section_a.pk]}
                    ).status_code,
                    302,
                )
        self.assertEqual(Section.objects.count(), 3)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.post(self.url, {'section_ids': [self.section_a.pk]})

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        self.assertEqual(Section.objects.count(), 3)

    def test_list_page_exposes_selection_bulk_bar_and_row_actions(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('academics:section_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'sectionSelection()')
        self.assertContains(response, 'name="section_ids"')
        self.assertContains(response, 'Delete selected')
        self.assertContains(
            response, reverse('academics:section_edit', args=[self.section_a.pk])
        )
        self.assertContains(
            response, reverse('academics:section_delete', args=[self.section_a.pk])
        )
        self.assertContains(response, 'hx-trigger="refresh"')
