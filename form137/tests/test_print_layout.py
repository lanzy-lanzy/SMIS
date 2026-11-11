import datetime
from decimal import Decimal

from django.template.context import BaseContext
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from academics.models import GradeLevel, GradingPeriod, SchoolYear, Section, Subject
from accounts.models import User
from form137.models import Form137Record
from form137.utils import (
    BLANK_FORM137_SUBJECTS,
    build_form137_pages,
)
from grades.models import Grade
from students.models import Student


class _FakeGradeLevel:
    def __init__(self, level):
        self.level = level


class _FakeSchoolYear:
    def __init__(self, name):
        self.name = name


def _subject_row(name="Filipino", q1="90", q4=None, final="91"):
    return {
        "subject_name": name,
        "is_mapeh": False,
        "is_mapeh_sub": False,
        "q1": Decimal(q1) if q1 is not None else None,
        "q2": None,
        "q3": None,
        "q4": Decimal(q4) if q4 is not None else None,
        "final_grade": Decimal(final) if final is not None else None,
        "remarks": "Passed",
    }


def _block(level, school_year="2024-2025", subject_rows=None):
    return {
        "grade_level": _FakeGradeLevel(level),
        "school_year": _FakeSchoolYear(school_year),
        "section_name": f"Section {level}",
        "adviser_name": "Teacher",
        "subject_rows": subject_rows if subject_rows is not None else [_subject_row()],
        "general_average": Decimal("91"),
    }


class Form137PageSplitTests(SimpleTestCase):
    def test_front_page_holds_grades_7_and_8_and_back_holds_9_and_10(self):
        pages = build_form137_pages([
            _block(7, "2022-2023"),
            _block(8, "2023-2024"),
            _block(9, "2024-2025"),
            _block(10, "2025-2026"),
        ])

        self.assertEqual([b["display_grade"] for b in pages["front_blocks"]], [7, 8])
        self.assertEqual([b["display_grade"] for b in pages["back_blocks"]], [9, 10])
        self.assertFalse(any(b["is_blank"] for b in pages["front_blocks"]))
        self.assertFalse(any(b["is_blank"] for b in pages["back_blocks"]))

    def test_missing_grades_are_padded_with_blank_slots(self):
        pages = build_form137_pages([_block(7, "2024-2025")])

        front = pages["front_blocks"]
        back = pages["back_blocks"]

        self.assertFalse(front[0]["is_blank"])
        self.assertTrue(front[1]["is_blank"])
        self.assertTrue(back[0]["is_blank"])
        self.assertTrue(back[1]["is_blank"])
        self.assertEqual([b["display_grade"] for b in front], [7, 8])
        self.assertEqual([b["display_grade"] for b in back], [9, 10])
        self.assertEqual(
            [row["subject_name"] for row in front[1]["subject_rows"]],
            BLANK_FORM137_SUBJECTS,
        )

    def test_populated_block_keeps_full_reference_subject_grid(self):
        pages = build_form137_pages([_block(7, subject_rows=[_subject_row(q1="92", q4="94")])])
        subject_rows = pages["front_blocks"][0]["subject_rows"]

        self.assertEqual(
            [row["display_name"] for row in subject_rows],
            BLANK_FORM137_SUBJECTS,
        )
        self.assertEqual(subject_rows[0]["q1"], Decimal("92"))
        self.assertEqual(subject_rows[0]["q4"], Decimal("94"))
        self.assertIsNone(subject_rows[1]["q1"])

    def test_certification_grade_follows_the_last_jhs_record(self):
        grade_8 = build_form137_pages([_block(7), _block(8)])
        grade_10 = build_form137_pages([_block(9), _block(10)])

        self.assertEqual(grade_8["certification_grade"], 9)
        self.assertEqual(grade_10["certification_grade"], "11 (Senior High School)")
        self.assertEqual(grade_8["certification_school_year"].name, "2024-2025")

    def test_senior_high_grades_are_left_off_the_jhs_form(self):
        pages = build_form137_pages([_block(11), _block(12)])

        self.assertTrue(all(b["is_blank"] for b in pages["front_blocks"]))
        self.assertTrue(all(b["is_blank"] for b in pages["back_blocks"]))
        self.assertFalse(pages["has_jhs_records"])


class Python314ContextCopyMixin:
    """Django 5.1's BaseContext.__copy__ breaks on Python 3.14."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._original_context_copy = BaseContext.__copy__
        BaseContext.__copy__ = _base_context_copy

    @classmethod
    def tearDownClass(cls):
        BaseContext.__copy__ = cls._original_context_copy
        super().tearDownClass()


def _base_context_copy(self):
    duplicate = object.__new__(type(self))
    duplicate.__dict__.update(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate


class Form137PrintViewTests(Python314ContextCopyMixin, TestCase):
    def setUp(self):
        self.registrar = User.objects.create_user(
            username='registrar', password='x', role='registrar',
            first_name='R', last_name='G',
        )
        self.student = Student.objects.create(
            lrn='123456789099', first_name='Ana', middle_name='Santos',
            last_name='Dela Cruz', suffix='Jr', sex='F',
            birthdate=datetime.date(2012, 1, 1),
            address='Purok 1', parent_name='Juan',
        )
        self.sy1 = SchoolYear.objects.create(name='2024-2025')
        self.sy2 = SchoolYear.objects.create(name='2025-2026')
        self.gl7 = GradeLevel.objects.create(name='Grade 7', level=7)
        self.gl8 = GradeLevel.objects.create(name='Grade 8', level=8)
        self.section7 = Section.objects.create(
            name='Diamond', grade_level=self.gl7, school_year=self.sy1,
            adviser=self.registrar,
        )
        self.section8 = Section.objects.create(
            name='Diamond', grade_level=self.gl8, school_year=self.sy2,
            adviser=self.registrar,
        )
        self.period1 = GradingPeriod.objects.create(
            name='Term 1', order=1, school_year=self.sy1,
        )
        self.period2 = GradingPeriod.objects.create(
            name='Term 1', order=1, school_year=self.sy2,
        )
        self._make_grade(self.gl7, self.sy1, self.section7, self.period1, '90')
        self._make_grade(self.gl8, self.sy2, self.section8, self.period2, '95')
        self.record = Form137Record.objects.create(
            student=self.student, school_year=self.sy2,
            grade_level=self.gl8, generated_by=self.registrar,
        )

    def _make_grade(self, grade_level, school_year, section, period, value):
        subject = Subject.objects.create(
            name='Filipino', code=f'FIL{grade_level.level}', grade_level=grade_level,
        )
        Grade.objects.create(
            student=self.student, subject=subject, grading_period=period,
            school_year=school_year, section=section,
            quarter_grade=Decimal(value), final_grade=Decimal(value),
            status='validated',
        )

    def test_print_view_renders_front_and_back_pages(self):
        self.client.force_login(self.registrar)
        response = self.client.get(
            reverse('form137:form137_preview', args=[self.record.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LEARNER'S INFORMATION")
        self.assertContains(response, 'ELIGIBILITY FOR JHS ENROLMENT')
        self.assertContains(response, 'data-form-page="form137-front"')
        self.assertContains(response, 'data-form-page="form137-back"')
        self.assertContains(response, 'id="form137-back" hidden')
        self.assertContains(response, 'Page 1 of 2')
        self.assertContains(response, 'Page 2 of 2')
        self.assertContains(response, 'SCHOLASTIC RECORD (CONTINUATION)')
        self.assertContains(response, 'deped-logo.png')
        self.assertContains(response, 'psyu-logo.png')
        self.assertContains(response, 'DELA CRUZ')
        self.assertContains(response, '<strong>9</strong>')

    def test_print_view_uses_four_quarter_columns(self):
        self.client.force_login(self.registrar)
        response = self.client.get(
            reverse('form137:form137_preview', args=[self.record.pk])
        )

        self.assertContains(response, 'QUARTERLY RATING')
        self.assertContains(response, '<th class="quarter">4</th>')
        self.assertContains(response, '2024-2025')
        self.assertContains(response, '2025-2026')
