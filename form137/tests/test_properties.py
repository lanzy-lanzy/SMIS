"""
form137/tests/test_properties.py

Property-based tests for the form137-sf10-print-format feature.

Each test is decorated with @settings(max_examples=100) and tagged with:
  # Feature: form137-sf10-print-format, Property N: <property text>

Pure-function tests use plain unittest.TestCase.
DB-touching tests use Django TestCase with hypothesis @given + @settings.
"""

import os
import unittest
from decimal import Decimal

import django
from django.test import TestCase as DjangoTestCase

from hypothesis import given, settings, assume
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase as HypothesisTestCase

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# ---------------------------------------------------------------------------
# Imports from the feature under test
# ---------------------------------------------------------------------------
from form137.utils import (
    JHS_SUBJECT_ORDER,
    MAPEH_SUBS,
    build_grade_blocks,
    compute_general_average,
    compute_promotion_status,
    compute_remarks,
    round_quarter,
)
from form137.templatetags.form137_filters import next_grade


# ===========================================================================
# Helper: format a full name the same way the template does
# ===========================================================================

def format_full_name(last_name: str, first_name: str,
                     middle_name: str = "", suffix: str = "") -> str:
    """
    Replicates the template's name-formatting logic:
        "LAST, FIRST [MIDDLE] [SUFFIX]"
    Parts are uppercased; absent optional parts are omitted without leaving
    trailing spaces or extra commas.
    """
    parts = [first_name.upper()]
    if middle_name:
        parts.append(middle_name.upper())
    if suffix:
        parts.append(suffix.upper())
    return f"{last_name.upper()}, {' '.join(parts)}"


# ===========================================================================
# Pure-function property tests  (no DB, plain unittest.TestCase)
# ===========================================================================

class TestNameFormattingProperty(unittest.TestCase):
    # Feature: form137-sf10-print-format, Property 1: Student name formatting
    # Validates: Requirements 2.1, 9.1

    _alpha = st.characters(whitelist_categories=("Lu", "Ll"))
    _name_text = st.text(alphabet=_alpha, min_size=1)
    _optional = st.one_of(st.just(""), st.text(alphabet=_alpha, min_size=1))

    @given(
        last_name=_name_text,
        first_name=_name_text,
        middle_name=_optional,
        suffix=_optional,
    )
    @settings(max_examples=100)
    def test_name_format_no_trailing_comma_no_double_spaces(
        self, last_name, first_name, middle_name, suffix
    ):
        # Feature: form137-sf10-print-format, Property 1: Student name formatting
        result = format_full_name(last_name, first_name, middle_name, suffix)

        # Must contain a comma separating last name from the rest
        assert ", " in result, f"Missing ', ' separator in: {result!r}"

        # No trailing comma
        assert not result.endswith(","), f"Trailing comma in: {result!r}"

        # No double spaces
        assert "  " not in result, f"Double space in: {result!r}"

        # Last name part (before the comma) must be non-empty
        last_part, first_part = result.split(", ", 1)
        assert last_part.strip() != "", f"Empty last name in: {result!r}"
        assert first_part.strip() != "", f"Empty first+rest in: {result!r}"

        # Optional middle name is present iff it was non-empty
        if middle_name:
            assert middle_name.upper() in result
        if suffix:
            assert suffix.upper() in result


class TestRemarksThresholdProperty(unittest.TestCase):
    # Feature: form137-sf10-print-format, Property 6: Remarks threshold invariant
    # Validates: Requirements 5.6

    @given(st.decimals(min_value=0, max_value=100, places=2, allow_nan=False))
    @settings(max_examples=100)
    def test_remarks_passed_iff_gte_75(self, grade):
        # Feature: form137-sf10-print-format, Property 6: Remarks threshold invariant
        expected = "Passed" if grade >= Decimal("75") else "Failed"
        assert compute_remarks(grade) == expected, (
            f"compute_remarks({grade}) should be {expected!r}"
        )


class TestPromotionThresholdProperty(unittest.TestCase):
    # Feature: form137-sf10-print-format, Property 8: Promotion/retention threshold invariant
    # Validates: Requirements 5.9

    @given(st.decimals(min_value=0, max_value=100, places=2, allow_nan=False))
    @settings(max_examples=100)
    def test_promotion_status_promoted_iff_gte_75(self, avg):
        # Feature: form137-sf10-print-format, Property 8: Promotion/retention threshold invariant
        expected = "PROMOTED" if avg >= Decimal("75") else "RETAINED"
        assert compute_promotion_status(avg) == expected, (
            f"compute_promotion_status({avg}) should be {expected!r}"
        )


class TestQuarterGradeRoundingProperty(unittest.TestCase):
    # Feature: form137-sf10-print-format, Property 5: Quarter grade rounding
    # Validates: Requirements 5.4, 5.5

    @given(st.decimals(min_value=0, max_value=100, places=2, allow_nan=False))
    @settings(max_examples=100)
    def test_round_quarter_equals_builtin_round(self, grade):
        # Feature: form137-sf10-print-format, Property 5: Quarter grade rounding
        assert round_quarter(grade) == round(grade), (
            f"round_quarter({grade}) != round({grade})"
        )


class TestNextGradeLevelProperty(unittest.TestCase):
    # Feature: form137-sf10-print-format, Property 9: Next grade level computation
    # Validates: Requirements 9.5, 9.6

    @given(st.integers(min_value=7, max_value=9))
    @settings(max_examples=100)
    def test_next_grade_is_level_plus_one_for_7_to_9(self, level):
        # Feature: form137-sf10-print-format, Property 9: Next grade level computation
        assert next_grade(level) == level + 1, (
            f"next_grade({level}) should be {level + 1}"
        )

    def test_next_grade_for_grade_10_is_senior_high(self):
        # Feature: form137-sf10-print-format, Property 9: Next grade level computation
        assert next_grade(10) == "11 (Senior High School)", (
            "next_grade(10) should be '11 (Senior High School)'"
        )


class TestGeneralAverageArithmeticProperty(unittest.TestCase):
    # Feature: form137-sf10-print-format, Property 7: General average arithmetic correctness
    # Validates: Requirements 6.1, 6.3

    @given(
        st.lists(
            st.decimals(min_value=60, max_value=100, places=2, allow_nan=False),
            min_size=1,
            max_size=12,
        )
    )
    @settings(max_examples=100)
    def test_general_average_equals_arithmetic_mean(self, finals):
        # Feature: form137-sf10-print-format, Property 7: General average arithmetic correctness
        # Build minimal subject_rows dicts that compute_general_average expects
        subject_rows = [
            {
                "subject_name": f"Subject{i}",
                "is_mapeh": False,
                "is_mapeh_sub": False,
                "q1": None,
                "q2": None,
                "q3": None,
                "q4": None,
                "final_grade": grade,
                "remarks": compute_remarks(grade),
            }
            for i, grade in enumerate(finals)
        ]

        result = compute_general_average(subject_rows)
        expected = sum(finals) / len(finals)

        assert abs(result - expected) < Decimal("0.01"), (
            f"compute_general_average result {result} differs from "
            f"expected {expected} by more than 0.01"
        )


# ===========================================================================
# DB-touching property tests  (Django TestCase)
# ===========================================================================

# Canonical subject names excluding MAPEH subs (they're injected automatically)
JHS_SUBJECT_ORDER_NAMES = [
    name for name in JHS_SUBJECT_ORDER if name not in MAPEH_SUBS
]


class TestGradeBlockGroupingCompletenessProperty(HypothesisTestCase):
    """
    Property 2: Grade block grouping completeness
    Validates: Requirements 3.1, 3.3
    """

    def setUp(self):
        from academics.models import GradeLevel, SchoolYear, Section, Subject, GradingPeriod
        from students.models import Student
        from accounts.models import User

        # Shared adviser user
        self._user = User.objects.create_user(
            username="adviser_prop2", password="x",
            first_name="Test", last_name="Adviser",
        )

        # Two school years
        self._sy1 = SchoolYear.objects.create(name="2021-2022")
        self._sy2 = SchoolYear.objects.create(name="2022-2023")

        # Three grade levels (7, 8, 9)
        self._gl7 = GradeLevel.objects.create(name="Grade 7", level=7)
        self._gl8 = GradeLevel.objects.create(name="Grade 8", level=8)
        self._gl9 = GradeLevel.objects.create(name="Grade 9", level=9)

        # Sections
        self._sec7 = Section.objects.create(
            name="Sect7", grade_level=self._gl7, school_year=self._sy1,
            adviser=self._user,
        )
        self._sec8 = Section.objects.create(
            name="Sect8", grade_level=self._gl8, school_year=self._sy1,
            adviser=self._user,
        )
        self._sec9 = Section.objects.create(
            name="Sect9", grade_level=self._gl9, school_year=self._sy2,
            adviser=self._user,
        )

        # Subjects — one per grade level
        self._subj7 = Subject.objects.create(
            name="Filipino", code="FIL7", grade_level=self._gl7,
        )
        self._subj8 = Subject.objects.create(
            name="Filipino", code="FIL8", grade_level=self._gl8,
        )
        self._subj9 = Subject.objects.create(
            name="Filipino", code="FIL9", grade_level=self._gl9,
        )

        # Grading periods (Q1 only is enough)
        self._gp1_sy1 = GradingPeriod.objects.create(
            name="Q1 2021-2022", order=1, school_year=self._sy1,
        )
        self._gp1_sy2 = GradingPeriod.objects.create(
            name="Q1 2022-2023", order=1, school_year=self._sy2,
        )

        # Student
        import datetime
        self._student = Student.objects.create(
            lrn="100000000001",
            first_name="Ana", last_name="Santos", sex="F",
            birthdate=datetime.date(2008, 1, 1),
            address="Somewhere",
            parent_name="Parent",
            grade_level=self._gl7,
            school_year=self._sy1,
        )

    def _make_grade(self, student, subject, grading_period, school_year, section,
                    final_grade=80):
        from grades.models import Grade
        return Grade.objects.create(
            student=student,
            subject=subject,
            grading_period=grading_period,
            school_year=school_year,
            section=section,
            quarter_grade=Decimal(str(final_grade)),
            final_grade=Decimal(str(final_grade)),
            status="validated",
        )

    @given(
        # Choose a non-empty subset of available (subject, section, grading_period, school_year) combos
        include_gl7_sy1=st.booleans(),
        include_gl8_sy1=st.booleans(),
        include_gl9_sy2=st.booleans(),
        final_grade=st.decimals(min_value=60, max_value=100, places=2, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_block_count_equals_distinct_pairs(
        self, include_gl7_sy1, include_gl8_sy1, include_gl9_sy2, final_grade
    ):
        # Feature: form137-sf10-print-format, Property 2: Grade block grouping completeness
        from grades.models import Grade

        # At least one pair must be included
        assume(include_gl7_sy1 or include_gl8_sy1 or include_gl9_sy2)

        # Clean up grades from previous hypothesis examples
        Grade.objects.filter(student=self._student).delete()

        distinct_pairs = set()
        if include_gl7_sy1:
            self._make_grade(
                self._student, self._subj7, self._gp1_sy1,
                self._sy1, self._sec7, final_grade,
            )
            distinct_pairs.add((self._sy1.pk, self._gl7.pk))
        if include_gl8_sy1:
            self._make_grade(
                self._student, self._subj8, self._gp1_sy1,
                self._sy1, self._sec8, final_grade,
            )
            distinct_pairs.add((self._sy1.pk, self._gl8.pk))
        if include_gl9_sy2:
            self._make_grade(
                self._student, self._subj9, self._gp1_sy2,
                self._sy2, self._sec9, final_grade,
            )
            distinct_pairs.add((self._sy2.pk, self._gl9.pk))

        blocks = build_grade_blocks(self._student)

        assert len(blocks) == len(distinct_pairs), (
            f"Expected {len(distinct_pairs)} blocks, got {len(blocks)}"
        )

        # Verify no duplicates
        seen_pairs = set()
        for b in blocks:
            pair = (b["school_year"].pk, b["grade_level"].pk)
            assert pair not in seen_pairs, f"Duplicate block for pair {pair}"
            seen_pairs.add(pair)

        # Verify all expected pairs present
        assert seen_pairs == distinct_pairs


class TestGradeBlockAscendingOrderProperty(HypothesisTestCase):
    """
    Property 3: Grade block ascending order
    Validates: Requirements 3.2, 3.5
    """

    def setUp(self):
        from academics.models import GradeLevel, SchoolYear, Section, Subject, GradingPeriod
        from students.models import Student
        from accounts.models import User
        import datetime

        self._user = User.objects.create_user(
            username="adviser_prop3", password="x",
            first_name="Test", last_name="Adviser",
        )
        self._sy = SchoolYear.objects.create(name="2023-2024")
        self._gls = {}
        self._subjects = {}
        self._sections = {}
        for lvl in (7, 8, 9, 10):
            gl = GradeLevel.objects.create(name=f"Grade {lvl}", level=lvl)
            self._gls[lvl] = gl
            subj = Subject.objects.create(
                name="Filipino", code=f"FIL{lvl}P3", grade_level=gl,
            )
            self._subjects[lvl] = subj
            sec = Section.objects.create(
                name=f"S{lvl}", grade_level=gl, school_year=self._sy,
                adviser=self._user,
            )
            self._sections[lvl] = sec

        self._gp = GradingPeriod.objects.create(
            name="Q1", order=1, school_year=self._sy,
        )
        self._student = Student.objects.create(
            lrn="100000000002",
            first_name="Bea", last_name="Reyes", sex="F",
            birthdate=datetime.date(2007, 5, 10),
            address="Somewhere",
            parent_name="Parent",
            grade_level=self._gls[7],
            school_year=self._sy,
        )

    @given(
        levels=st.lists(
            st.sampled_from([7, 8, 9, 10]),
            min_size=1,
            unique=True,
        )
    )
    @settings(max_examples=100)
    def test_blocks_are_in_non_decreasing_level_order(self, levels):
        # Feature: form137-sf10-print-format, Property 3: Grade block ascending order
        from grades.models import Grade

        Grade.objects.filter(student=self._student).delete()

        for lvl in levels:
            Grade.objects.create(
                student=self._student,
                subject=self._subjects[lvl],
                grading_period=self._gp,
                school_year=self._sy,
                section=self._sections[lvl],
                quarter_grade=Decimal("80"),
                final_grade=Decimal("80"),
                status="validated",
            )

        blocks = build_grade_blocks(self._student)
        block_levels = [b["grade_level"].level for b in blocks]

        assert block_levels == sorted(block_levels), (
            f"Blocks not in ascending order: {block_levels}"
        )


class TestSubjectOrderingWithinBlockProperty(HypothesisTestCase):
    """
    Property 4: Subject ordering within a block
    Validates: Requirements 5.2
    """

    def setUp(self):
        from academics.models import GradeLevel, SchoolYear, Section, Subject, GradingPeriod
        from students.models import Student
        from accounts.models import User
        import datetime

        self._user = User.objects.create_user(
            username="adviser_prop4", password="x",
            first_name="Test", last_name="Adviser",
        )
        self._sy = SchoolYear.objects.create(name="2024-2025")
        self._gl = GradeLevel.objects.create(name="Grade 7", level=7)
        self._sec = Section.objects.create(
            name="Sec7P4", grade_level=self._gl, school_year=self._sy,
            adviser=self._user,
        )
        self._gp = GradingPeriod.objects.create(
            name="Q1 P4", order=1, school_year=self._sy,
        )

        # Create one Subject per canonical non-sub name so we can use them
        self._subject_objs = {}
        for i, name in enumerate(JHS_SUBJECT_ORDER_NAMES):
            subj = Subject.objects.create(
                name=name, code=f"P4S{i:02d}", grade_level=self._gl,
            )
            self._subject_objs[name] = subj

        self._student = Student.objects.create(
            lrn="100000000003",
            first_name="Clara", last_name="Cruz", sex="F",
            birthdate=datetime.date(2009, 3, 20),
            address="Somewhere",
            parent_name="Parent",
            grade_level=self._gl,
            school_year=self._sy,
        )

    @given(
        subject_names=st.lists(
            st.sampled_from(JHS_SUBJECT_ORDER_NAMES),
            min_size=1,
            unique=True,
        )
    )
    @settings(max_examples=100)
    def test_subjects_appear_in_canonical_order(self, subject_names):
        # Feature: form137-sf10-print-format, Property 4: Subject ordering within a block
        from grades.models import Grade

        Grade.objects.filter(student=self._student).delete()

        for name in subject_names:
            subj = self._subject_objs[name]
            Grade.objects.create(
                student=self._student,
                subject=subj,
                grading_period=self._gp,
                school_year=self._sy,
                section=self._sec,
                quarter_grade=Decimal("80"),
                final_grade=Decimal("80"),
                status="validated",
            )

        blocks = build_grade_blocks(self._student)
        assert len(blocks) == 1
        subject_rows = blocks[0]["subject_rows"]

        # Collect top-level (non-MAPEH-sub) subject names in the order they appear
        rendered_names = [
            row["subject_name"]
            for row in subject_rows
            if not row["is_mapeh_sub"]
        ]

        # Filter the canonical order to only the subjects we inserted
        chosen_set = set(subject_names)
        canonical_filtered = [
            name for name in JHS_SUBJECT_ORDER
            if name in chosen_set and name not in MAPEH_SUBS
        ]

        assert rendered_names == canonical_filtered, (
            f"Subject order mismatch.\n"
            f"  Rendered:  {rendered_names}\n"
            f"  Canonical: {canonical_filtered}"
        )
