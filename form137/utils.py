"""
form137/utils.py

Helper constants and functions for building SF 10-JHS grade blocks.

Extracted from the view layer so they can be unit- and property-tested
independently of the HTTP request/response cycle.
"""

from decimal import Decimal
from types import SimpleNamespace

from grades.models import Grade
from grades.mapeh import is_mapeh_subject, mapeh_component, merge_mapeh_grades


# ---------------------------------------------------------------------------
# JHS canonical subject order (Section 5.2 of the SF 10-JHS spec)
# ---------------------------------------------------------------------------

JHS_SUBJECT_ORDER = [
    "Filipino",
    "English",
    "Mathematics",
    "Science",
    "Araling Panlipunan",
    "Edukasyon sa Pagpapakatao",
    "Technology and Livelihood Education",
    "MAPEH",            # composite parent row
    "Music",            # MAPEH sub-row
    "Arts",             # MAPEH sub-row
    "Physical Education",  # MAPEH sub-row
    "Health",           # MAPEH sub-row
]

# Legacy MAPEH subjects folded into the parent row for printing.
MAPEH_SUBS = {"Music", "Arts", "Physical Education", "Health"}

VALUES_EDUCATION_ALIASES = {
    "esp", "edukasyon sa pagpapakatao", "values education", "gmrc", "gmrc/values education",
}
SF10_TERMS = (1, 2, 3)

FORM137_SUBJECT_LABELS = {
    "Araling Panlipunan": "Araling Panlipunan (AP)",
    "Edukasyon sa Pagpapakatao": "GMRC/Values Education",
    "Technology and Livelihood Education": "Technology and Livelihood Education (TLE)",
}

BLANK_FORM137_SUBJECTS = [
    "Filipino",
    "English",
    "Mathematics",
    "Science",
    "Araling Panlipunan (AP)",
    "GMRC/Values Education",
    "Technology and Livelihood Education (TLE)",
    "MAPEH",
]


# ---------------------------------------------------------------------------
# Pure helper functions (no DB access)
# ---------------------------------------------------------------------------

def compute_remarks(final_grade) -> str:
    """
    Return "Passed" / "Failed" / "" for a subject row.

    Requirements: 5.6
    """
    if final_grade is None:
        return ""
    return "Passed" if final_grade >= Decimal("75") else "Failed"


def compute_promotion_status(general_average) -> str:
    """
    Return "PROMOTED" / "RETAINED" for the general-average row.

    Requirements: 5.9
    """
    return "PROMOTED" if general_average >= Decimal("75") else "RETAINED"


def round_quarter(grade) -> int:
    """
    Round a quarter_grade Decimal to the nearest integer for display.

    Requirements: 5.4, 5.5
    """
    return round(grade)


def compute_general_average(subject_rows: list) -> Decimal:
    """
    Compute the arithmetic mean of non-None final_grade values.

    MAPEH sub-component rows (is_mapeh_sub=True) are excluded when a MAPEH
    composite row with a non-None final_grade exists in the same block.
    If only sub-rows exist and no MAPEH parent final is available, sub-rows
    are included in the average.

    Returns Decimal("0") when no finals are available.

    Requirements: 6.1, 6.2, 6.3
    """
    # Determine whether a MAPEH composite (parent) row has a final grade.
    mapeh_parent_has_final = any(
        row["is_mapeh"] and not row["is_mapeh_sub"] and row["final_grade"] is not None
        for row in subject_rows
    )

    finals = []
    for row in subject_rows:
        if row["final_grade"] is None:
            continue
        # Exclude MAPEH sub-rows when the composite parent covers them.
        if row["is_mapeh_sub"] and mapeh_parent_has_final:
            continue
        finals.append(row["final_grade"])

    if not finals:
        return Decimal("0")

    return sum(finals) / len(finals)


def build_blank_subject_rows() -> list:
    return [
        {
            "subject_name": subject_name,
            "display_name": subject_name,
            "is_mapeh": subject_name == "MAPEH",
            "is_mapeh_sub": False,
            "q1": None,
            "q2": None,
            "q3": None,
            "final_grade": None,
            "remarks": "",
        }
        for subject_name in BLANK_FORM137_SUBJECTS
    ]


def build_printable_subject_rows(subject_rows: list) -> list:
    rows_by_display_name = {}
    extras = []

    for row in subject_rows:
        if row["is_mapeh_sub"]:
            continue
        printable_row = row.copy()
        printable_row["display_name"] = FORM137_SUBJECT_LABELS.get(
            row["subject_name"],
            row["subject_name"],
        )
        if printable_row["display_name"] in BLANK_FORM137_SUBJECTS:
            rows_by_display_name[printable_row["display_name"]] = printable_row
        else:
            extras.append(printable_row)

    return [
        rows_by_display_name.get(blank_row["display_name"], blank_row)
        for blank_row in build_blank_subject_rows()
    ] + extras


FRONT_PAGE_LEVELS = (7, 8)
BACK_PAGE_LEVELS = (9, 10)


def _printable_block(block: dict, display_grade: int) -> dict:
    printable_block = block.copy()
    printable_block["subject_rows"] = build_printable_subject_rows(block["subject_rows"])
    printable_block["is_blank"] = False
    printable_block["display_grade"] = display_grade
    return printable_block


def _blank_block(display_grade: int) -> dict:
    return {
        "grade_level": None,
        "display_grade": display_grade,
        "school_year": None,
        "section_name": "",
        "adviser_name": "",
        "subject_rows": build_blank_subject_rows(),
        "general_average": None,
        "is_blank": True,
    }


def build_page_blocks(grade_blocks: list, levels: tuple) -> list:
    """
    Fit *grade_blocks* into the fixed grade slots of one SF 10-JHS page.

    Each slot is always rendered so the printed form keeps its official
    structure; slots without validated grades become blank fill-in blocks.
    """
    by_level = {}
    for block in grade_blocks:
        level = block["grade_level"].level
        if level in levels:
            by_level[level] = block

    return [
        _printable_block(by_level[level], level) if level in by_level else _blank_block(level)
        for level in levels
    ]


def admission_grade(level: int):
    """Return the grade a learner may be admitted to after finishing *level*."""
    if level >= 10:
        return "11 (Senior High School)"
    return level + 1


def build_form137_pages(grade_blocks: list) -> dict:
    """
    Split the scholarly record across the two SF 10-JHS pages.

    Page 1 (front) carries the learner information plus Grades 7-8 and the
    certification; page 2 (back) carries Grades 9-10. SHS grades are not part
    of the JHS permanent record and are intentionally left off this form.
    """
    front_blocks = build_page_blocks(grade_blocks, FRONT_PAGE_LEVELS)
    back_blocks = build_page_blocks(grade_blocks, BACK_PAGE_LEVELS)

    jhs_blocks = [block for block in grade_blocks if block["grade_level"].level <= 10]
    last_block = jhs_blocks[-1] if jhs_blocks else None

    return {
        "front_blocks": front_blocks,
        "back_blocks": back_blocks,
        "certification_grade": admission_grade(last_block["grade_level"].level) if last_block else "",
        "certification_school_year": last_block["school_year"] if last_block else None,
        "has_jhs_records": bool(jhs_blocks),
    }


# ---------------------------------------------------------------------------
# Main data-assembly function
# ---------------------------------------------------------------------------

def build_grade_blocks(student) -> list:
    """
    Fetch all validated Grade records for *student* and return an ordered
    list of grade-block dicts suitable for rendering the SF 10-JHS template.

    Each block corresponds to one (school_year, grade_level) pair and is
    sorted by grade_level.level ascending.

    Block dict shape:
        {
            "grade_level":   GradeLevel,
            "school_year":   SchoolYear,
            "section_name":  str | None,
            "adviser_name":  str | None,
            "subject_rows":  list[dict],
            "general_average": Decimal,
        }

    Subject-row dict shape:
        {
            "subject_name":  str,
            "is_mapeh":      bool,
            "is_mapeh_sub":  bool,
            "q1":            Decimal | None,
            "q2":            Decimal | None,
            "q3":            Decimal | None,
            "final_grade":   Decimal | None,
            "remarks":       str,   # "Passed" / "Failed" / ""
        }

    Requirements: 3.1, 3.2, 5.2, 5.6, 6.1, 6.2
    """
    # ------------------------------------------------------------------
    # 1. Single optimised query — all validated grades for the student.
    # ------------------------------------------------------------------
    grades_qs = (
        Grade.objects
        .filter(
            student=student,
            status__in=["validated", "locked"],
            grading_period__order__in=SF10_TERMS,
        )
        .select_related(
            "subject",
            "subject__grade_level",
            "grading_period",
            "school_year",
            "section",
            "section__adviser",
        )
        .order_by(
            "school_year__name",
            "subject__grade_level__level",
            "grading_period__order",
        )
    )

    # ------------------------------------------------------------------
    # 2. Group grades in Python by (school_year_id, grade_level_id).
    #    Each bucket maps  subject_name  ->  {period_order: grade_obj}
    # ------------------------------------------------------------------
    # Structure:
    #   raw_blocks: dict keyed by (sy_id, gl_id) ->
    #       {
    #           "grade_level": GradeLevel,
    #           "school_year": SchoolYear,
    #           "section":     Section | None,   (first one found for this block)
    #           "subjects":    { subject_name: { period_order: Grade } }
    #       }
    raw_blocks: dict = {}

    for grade in grades_qs:
        sy_id = grade.school_year_id
        gl_id = grade.subject.grade_level_id
        key = (sy_id, gl_id)

        if key not in raw_blocks:
            raw_blocks[key] = {
                "grade_level": grade.subject.grade_level,
                "school_year": grade.school_year,
                "section": grade.section,   # may be overwritten; consistent per block
                "subjects": {},
                "mapeh_components": {},
            }

        subject_name = grade.subject.name
        subject_key = " ".join(subject_name.lower().split())
        period_order = grade.grading_period.order
        bucket = raw_blocks[key]
        combined_mapeh = is_mapeh_subject(subject_name)
        if combined_mapeh and grade.component:
            bucket["mapeh_components"].setdefault(period_order, {})[grade.component] = grade
        else:
            if combined_mapeh:
                subject_name = "MAPEH"
            elif subject_key.replace(" / ", "/") in VALUES_EDUCATION_ALIASES:
                subject_name = "Edukasyon sa Pagpapakatao"
            bucket["subjects"].setdefault(subject_name, {})[period_order] = grade

        # Prefer the most recent section record (last write wins, but all
        # grades in the same block should share the same section).
        if grade.section is not None:
            raw_blocks[key]["section"] = grade.section

    # ------------------------------------------------------------------
    # 3. Sort blocks by grade_level.level ascending.
    # ------------------------------------------------------------------
    sorted_keys = sorted(
        raw_blocks.keys(),
        key=lambda k: raw_blocks[k]["grade_level"].level,
    )

    # ------------------------------------------------------------------
    # 4. Build the final block list.
    # ------------------------------------------------------------------
    blocks = []

    for key in sorted_keys:
        rb = raw_blocks[key]
        grade_level = rb["grade_level"]
        school_year = rb["school_year"]
        section = rb["section"]

        # Section / adviser info from the Section FK on the Grade record.
        if section is not None:
            section_name = section.name
            adviser = section.adviser
            adviser_name = adviser.get_full_name() if adviser else None
        else:
            section_name = None
            adviser_name = None

        # --------------------------------------------------------------
        # 5. Build subject_rows in JHS canonical order.
        # --------------------------------------------------------------
        present_subjects: dict = rb["subjects"]   # subject_name -> {order: Grade}

        # Use the combined subject's component results first, followed by
        # stored MAPEH marks and legacy component subjects for the same term.
        component_names = sorted(
            name for name in present_subjects
            if mapeh_component(name.replace("&", "and")) or name.strip().lower() == "peh"
        )
        legacy_names = component_names + [name for name in JHS_SUBJECT_ORDER if name in MAPEH_SUBS]
        parent_map = present_subjects.get("MAPEH", {}).copy()
        for order in SF10_TERMS:
            component_grades = list(rb["mapeh_components"].get(order, {}).values())
            if not component_grades and order not in parent_map:
                component_grades = [
                    present_subjects[name][order]
                    for name in legacy_names if order in present_subjects.get(name, {})
                ]
            if component_grades:
                parent_map[order] = SimpleNamespace(
                    quarter_grade=Decimal(merge_mapeh_grades(grade.quarter_grade for grade in component_grades)),
                    final_grade=Decimal(merge_mapeh_grades(grade.final_grade for grade in component_grades)),
                )
        if parent_map:
            present_subjects["MAPEH"] = parent_map

        # Bucket the names.
        canonical_names = [
            name for name in JHS_SUBJECT_ORDER
            if name in present_subjects
        ]
        unknown_names = sorted(
            name for name in present_subjects
            if name not in set(JHS_SUBJECT_ORDER) and name not in component_names
        )

        subject_rows = []

        def _build_row(subject_name: str, is_mapeh: bool, is_mapeh_sub: bool) -> dict:
            """Build a single subject-row dict from the grade lookup."""
            period_map = present_subjects.get(subject_name, {})

            term_marks = {
                f"q{order}": period_map[order].quarter_grade if order in period_map else None
                for order in SF10_TERMS
            }
            final_grade = period_map[max(period_map)].final_grade if period_map else None

            remarks = compute_remarks(final_grade)

            return {
                "subject_name": subject_name,
                "is_mapeh": is_mapeh,
                "is_mapeh_sub": is_mapeh_sub,
                **term_marks,
                "final_grade": final_grade,
                "remarks": remarks,
            }

        # Walk through the canonical order; handle MAPEH specially.
        for name in canonical_names:
            if name == "MAPEH":
                # Insert MAPEH composite parent row.
                subject_rows.append(_build_row("MAPEH", is_mapeh=True, is_mapeh_sub=False))
                # Immediately follow with sub-rows in canonical sub-order.
                for sub_name in ["Music", "Arts", "Physical Education", "Health"]:
                    if sub_name in present_subjects:
                        subject_rows.append(
                            _build_row(sub_name, is_mapeh=True, is_mapeh_sub=True)
                        )
                for sub_name in component_names:
                    subject_rows.append(
                        _build_row(sub_name, is_mapeh=True, is_mapeh_sub=True)
                    )
                continue

            if name in MAPEH_SUBS:
                continue

            subject_rows.append(_build_row(name, is_mapeh=False, is_mapeh_sub=False))

        # Append unknown (non-canonical) subjects alphabetically.
        for name in unknown_names:
            subject_rows.append(_build_row(name, is_mapeh=False, is_mapeh_sub=False))

        # --------------------------------------------------------------
        # 6. Compute general average for the block.
        # --------------------------------------------------------------
        general_average = compute_general_average(subject_rows)

        blocks.append({
            "grade_level": grade_level,
            "school_year": school_year,
            "section_name": section_name,
            "adviser_name": adviser_name,
            "subject_rows": subject_rows,
            "general_average": general_average,
        })

    return blocks
