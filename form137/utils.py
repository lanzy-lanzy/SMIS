"""
form137/utils.py

Helper constants and functions for building SF 10-JHS grade blocks.

Extracted from the view layer so they can be unit- and property-tested
independently of the HTTP request/response cycle.
"""

from decimal import Decimal

from grades.models import Grade


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

# Subjects that are displayed as indented sub-rows under the MAPEH parent row.
MAPEH_SUBS = {"Music", "Arts", "Physical Education", "Health"}

FORM137_SUBJECT_LABELS = {
    "Araling Panlipunan": "Araling Panlipunan (AP)",
    "Edukasyon sa Pagpapakatao": "Edukasyon sa Pagpapakatao (EsP)",
    "Technology and Livelihood Education": "Technology and Livelihood Education (TLE)",
}

BLANK_FORM137_SUBJECTS = [
    "Filipino",
    "English",
    "Mathematics",
    "Science",
    "Araling Panlipunan (AP)",
    "Edukasyon sa Pagpapakatao (EsP)",
    "Technology and Livelihood Education (TLE)",
    "MAPEH",
    "Music",
    "Arts",
    "Physical Education",
    "Health",
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
            "is_mapeh": subject_name in {"MAPEH", "Music", "Arts", "Physical Education", "Health"},
            "is_mapeh_sub": subject_name in MAPEH_SUBS,
            "q1": None,
            "q2": None,
            "q3": None,
            "q4": None,
            "final_grade": None,
            "remarks": "",
        }
        for subject_name in BLANK_FORM137_SUBJECTS
    ]


def build_printable_subject_rows(subject_rows: list) -> list:
    rows_by_display_name = {}
    extras = []

    for row in subject_rows:
        printable_row = row.copy()
        printable_row["display_name"] = FORM137_SUBJECT_LABELS.get(
            row["subject_name"],
            row["subject_name"],
        )
        if printable_row["display_name"] in BLANK_FORM137_SUBJECTS:
            rows_by_display_name[printable_row["display_name"]] = printable_row
        else:
            extras.append(printable_row)

    printable_rows = []
    for blank_row in build_blank_subject_rows():
        printable_rows.append(rows_by_display_name.get(
            blank_row["display_name"],
            blank_row,
        ))

    printable_rows.extend(extras)
    return printable_rows


def build_printable_grade_blocks(grade_blocks: list, minimum_blocks: int = 3) -> list:
    """
    Return grade blocks shaped for the compact SF 10-JHS print template.

    The attached reference keeps at least one blank future-year block after the
    populated records. Padding to three blocks reproduces that structure for
    typical Grade 9/10 records while preserving longer histories.
    """
    printable_blocks = []

    for block in grade_blocks:
        printable_block = block.copy()
        printable_block["subject_rows"] = build_printable_subject_rows(block["subject_rows"])
        printable_block["is_blank"] = False
        printable_blocks.append(printable_block)

    while len(printable_blocks) < minimum_blocks:
        printable_blocks.append({
            "grade_level": None,
            "school_year": None,
            "section_name": "",
            "adviser_name": "",
            "subject_rows": build_blank_subject_rows(),
            "general_average": None,
            "is_blank": True,
        })

    return printable_blocks


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
            "q4":            Decimal | None,
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
        .filter(student=student, status__in=["validated", "locked"])
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
            }

        subject_name = grade.subject.name
        if subject_name not in raw_blocks[key]["subjects"]:
            raw_blocks[key]["subjects"][subject_name] = {}

        period_order = grade.grading_period.order  # 1–4
        raw_blocks[key]["subjects"][subject_name][period_order] = grade

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

        # Bucket the names.
        canonical_names = [
            name for name in JHS_SUBJECT_ORDER
            if name in present_subjects
        ]
        unknown_names = sorted(
            name for name in present_subjects
            if name not in set(JHS_SUBJECT_ORDER)
        )

        # Determine whether a MAPEH composite subject (named "MAPEH") exists.
        has_mapeh_composite = "MAPEH" in present_subjects
        # Determine whether any MAPEH sub-subjects exist.
        present_mapeh_subs = [n for n in MAPEH_SUBS if n in present_subjects]

        subject_rows = []

        def _build_row(subject_name: str, is_mapeh: bool, is_mapeh_sub: bool) -> dict:
            """Build a single subject-row dict from the grade lookup."""
            period_map = present_subjects.get(subject_name, {})

            def _grade_val(order: int):
                g = period_map.get(order)
                return g.final_grade if g is not None else None

            def _quarter_val(order: int):
                g = period_map.get(order)
                return g.quarter_grade if g is not None else None

            # For MAPEH sub-rows each Grade row holds a quarter_grade and
            # final_grade per grading period; we display them the same way.
            q1 = _quarter_val(1)
            q2 = _quarter_val(2)
            q3 = _quarter_val(3)
            q4 = _quarter_val(4)

            # final_grade: use the grade record's own final_grade field.
            # For sub-rows this is the sub-subject final; for regular rows
            # it is the subject's final grade for the whole year.
            # We take the last (highest-order) grading period's final_grade
            # as the representative final for the subject row, because the
            # Grade model stores a running final_grade per grading period.
            # If there are multiple periods, we prefer the one with the
            # highest order (most recent).
            if period_map:
                max_order = max(period_map.keys())
                final_grade = period_map[max_order].final_grade
                # Treat 0 as "no grade" when the grade record exists but is empty.
                # (The model defaults final_grade to 0.)
                # We only treat it as None if there are literally no records.
            else:
                final_grade = None

            remarks = compute_remarks(final_grade)

            return {
                "subject_name": subject_name,
                "is_mapeh": is_mapeh,
                "is_mapeh_sub": is_mapeh_sub,
                "q1": q1,
                "q2": q2,
                "q3": q3,
                "q4": q4,
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
                continue

            if name in MAPEH_SUBS:
                # Sub-row that appeared in canonical_names because "MAPEH"
                # composite is absent — will be inserted below when we process
                # un-parented sub-rows.
                continue

            subject_rows.append(_build_row(name, is_mapeh=False, is_mapeh_sub=False))

        # If MAPEH composite is absent but sub-rows exist, insert them now
        # (after all canonical non-MAPEH subjects, before unknowns).
        if not has_mapeh_composite and present_mapeh_subs:
            for sub_name in ["Music", "Arts", "Physical Education", "Health"]:
                if sub_name in present_subjects:
                    subject_rows.append(
                        _build_row(sub_name, is_mapeh=True, is_mapeh_sub=True)
                    )

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
