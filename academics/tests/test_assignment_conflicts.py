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

    def test_schedule_creation_conflict_detection_and_display(self):
        english = Subject.objects.create(name='English', code='ENG7', grade_level=self.subject.grade_level)

        # 1. Assign schedule to existing assignment (Ana Reyes, Math, Grade 7-A, Mon/Wed 08:00-09:00, Room 101)
        edit_url = reverse('academics:assignment_edit', args=[self.assignment.pk])
        res = self.client.post(edit_url, {
            'teacher': self.teacher.pk,
            'subject': self.subject.pk,
            'section': self.section.pk,
            'school_year': self.year.pk,
            'days': ['Mon', 'Wed'],
            'start_time': '08:00',
            'end_time': '09:00',
            'room': 'Room 101',
        })
        self.assertRedirects(res, reverse('academics:assignment_list'))
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.days_display, 'Mon, Wed')
        self.assertEqual(self.assignment.time_range, '8:00 AM – 9:00 AM')
        self.assertEqual(self.assignment.room, 'Room 101')

        # 2. Invalid time range (end <= start) rejected
        res_bad = self.client.post(reverse('academics:assignment_create'), {
            'teacher': self.other_teacher.pk,
            'subject': english.pk,
            'section': self.free_section.pk,
            'school_year': self.year.pk,
            'days': ['Mon'],
            'start_time': '10:00',
            'end_time': '09:00',
        })
        self.assertContains(res_bad, 'End time must be later than start time.')

        # 3. Teacher schedule conflict: Ana Reyes on Mon 08:30-09:30 in Section B
        res_teacher_conflict = self.client.post(reverse('academics:assignment_create'), {
            'teacher': self.teacher.pk,
            'subject': english.pk,
            'section': self.free_section.pk,
            'school_year': self.year.pk,
            'days': ['Mon', 'Fri'],
            'start_time': '08:30',
            'end_time': '09:30',
        })
        self.assertContains(res_teacher_conflict, 'Teacher schedule conflict')

        # 4. Section schedule conflict: Another teacher in Grade 7-A on Wed 08:00-09:00
        res_section_conflict = self.client.post(reverse('academics:assignment_create'), {
            'teacher': self.other_teacher.pk,
            'subject': english.pk,
            'section': self.section.pk,
            'school_year': self.year.pk,
            'days': ['Wed'],
            'start_time': '08:00',
            'end_time': '09:00',
        })
        self.assertContains(res_section_conflict, 'Section schedule conflict')

        # 5. Back-to-back non-overlapping slot (09:00-10:00) succeeds
        res_ok = self.client.post(reverse('academics:assignment_create'), {
            'teacher': self.other_teacher.pk,
            'subject': english.pk,
            'section': self.section.pk,
            'school_year': self.year.pk,
            'days': ['Mon', 'Wed'],
            'start_time': '09:00',
            'end_time': '10:00',
            'room': 'Room 102',
        })
        self.assertRedirects(res_ok, reverse('academics:assignment_list'))
        list_resp = self.client.get(reverse('academics:assignment_list'))
        self.assertContains(list_resp, '8:00 AM – 9:00 AM')
        self.assertContains(list_resp, 'Room 102')
