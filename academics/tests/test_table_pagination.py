"""Table refresh swaps must replace the pagination footer, not stack copies."""

from django.test import TestCase
from django.urls import reverse

from academics.models import GradeLevel, SchoolYear, Section, Subject
from accounts.models import User

from .test_section_bulk_delete import Python314ContextCopyMixin


class TablePaginationSwapTests(Python314ContextCopyMixin, TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin', password='x', role='admin'
        )
        self.sy = SchoolYear.objects.create(name='2025-2026', is_current=True)
        self.level = GradeLevel.objects.create(name='Grade 7', level=7)
        for index in range(16):
            Subject.objects.create(
                name=f'Subject {index}', code=f'SUB{index}', grade_level=self.level
            )
        self.client.force_login(self.admin)

    def test_refresh_response_is_a_single_table_including_its_footer(self):
        response = self.client.get(
            reverse('academics:subject_list'), HTTP_HX_REQUEST='true'
        )

        body = response.content.decode().strip()
        self.assertTrue(body.startswith('<table'))
        self.assertTrue(body.endswith('</table>'))
        self.assertIn('<tfoot>', body)
        self.assertEqual(body.count('<table'), 1)

    def test_full_page_renders_one_pagination_footer(self):
        response = self.client.get(reverse('academics:subject_list'))

        self.assertEqual(response.content.count(b'Showing 1-15 of 16'), 1)
        self.assertEqual(response.content.count(b'<tfoot>'), 1)

    def test_shared_section_partial_has_no_selection_ui_outside_sections_page(self):
        Section.objects.create(
            name='7-A', grade_level=self.level, school_year=self.sy
        )
        page = self.client.get(reverse('academics:assignment_list'))
        partial = self.client.get(
            reverse('academics:assignment_list'),
            {'view': 'section'},
            HTTP_HX_REQUEST='true',
        )

        self.assertContains(page, 'sections-table')
        self.assertNotContains(page, 'x-model="selected"')
        self.assertNotContains(partial, 'name="section_ids"')
        self.assertNotContains(partial, 'hx-trigger="refresh"')
