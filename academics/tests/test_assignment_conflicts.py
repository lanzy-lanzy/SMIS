from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from academics.models import GradeLevel, SchoolYear, Section, Subject, TeacherAssignment
from accounts.models import User


class AssignmentConflictTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admin', role='admin')
        cls.teacher = User.objects.create_user(
            username='existing', first_name='Ana', last_name='Reyes', role='teacher',
        )
        cls.other_teacher = User.objects.create_user(username='another', role='teacher')
        cls.year = SchoolYear.objects.create(name='2026-2027', is_current=True)
        level = GradeLevel.objects.create(name='Grade 7', level=7)
        cls.subject = Subject.objects.create(name='Mathematics', code='MATH7', grade_level=level)
        cls.section = Section.objects.create(name='A', grade_level=level, school_year=cls.year)
        cls.free_section = Section.objects.create(name='B', grade_level=level, school_year=cls.year)
        cls.assignment = TeacherAssignment.objects.create(
            teacher=cls.teacher, subject=cls.subject, section=cls.section, school_year=cls.year,
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.data = {
            'teacher': self.other_teacher.pk,
            'subject': self.subject.pk,
            'section': self.section.pk,
            'school_year': self.year.pk,
        }

    def test_single_create_shows_the_existing_teacher_in_the_modal(self):
        response = self.client.post(
            reverse('academics:assignment_create'), self.data, HTTP_HX_REQUEST='true',
        )
        self.assertContains(response, 'is already assigned to Ana Reyes')
        self.assertEqual(TeacherAssignment.objects.count(), 1)

    def test_edit_can_reassign_its_own_slot_but_cannot_take_another(self):
        free = TeacherAssignment.objects.create(
            teacher=self.other_teacher, subject=self.subject, section=self.free_section, school_year=self.year,
        )
        response = self.client.post(reverse('academics:assignment_edit', args=[free.pk]), self.data)
        self.assertContains(response, 'is already assigned to Ana Reyes')
        free.refresh_from_db()
        self.assertEqual(free.section, self.free_section)

        response = self.client.post(reverse('academics:assignment_edit', args=[self.assignment.pk]), self.data)
        self.assertRedirects(response, reverse('academics:assignment_list'))
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.teacher, self.other_teacher)

    def test_bulk_batch_is_all_or_nothing_and_preserves_selections(self):
        url = reverse('academics:assignment_bulk_create')
        data = {
            'teacher': self.other_teacher.pk, 'school_year': self.year.pk,
            'subjects': [self.subject.pk], 'sections': [self.section.pk, self.free_section.pk],
        }
        response = self.client.post(url, data, HTTP_HX_REQUEST='true')
        self.assertContains(response, 'is already assigned to Ana Reyes')
        self.assertContains(response, f'<option value="{self.free_section.pk}" selected>')
        self.assertEqual(TeacherAssignment.objects.count(), 1)
        response = self.client.post(url, {**data, 'sections': [self.free_section.pk]}, HTTP_HX_REQUEST='true')
        self.assertEqual(response['HX-Trigger'], 'close-modal,refreshTable')
        self.assertTrue(TeacherAssignment.objects.filter(section=self.free_section, teacher=self.other_teacher).exists())

    def test_database_rejects_duplicate_slots(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            TeacherAssignment.objects.create(
                teacher=self.other_teacher, subject=self.subject, section=self.section, school_year=self.year,
            )
