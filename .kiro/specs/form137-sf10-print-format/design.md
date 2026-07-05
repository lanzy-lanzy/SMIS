# Design Document

## Feature: form137-sf10-print-format

---

## Overview

This feature replaces the existing custom Form 137 print template and its backing view logic with a fully SF 10-JHS (DepEd School Form 10 – Junior High School) compliant implementation. The existing template is a non-standard layout that only covers a single school year. The redesign must:

1. Rewrite `form137_generate` and `form137_preview` in `form137/views.py` to collect **all validated grades** for a student across every school year they attended, group them by `(school_year, grade_level)` pair, compute general averages correctly, and pass a structured block list to the template.
2. Fully replace `templates/form137/form137_print.html` with a multi-block layout that faithfully replicates the official SF 10-JHS paper form: page header row, student personal information header, one grade block per attended grade level, remedial classes sub-table, transfer/completer section, and certification box.

No new models, URLs, or third-party PDF libraries are introduced. The print/PDF export continues to rely on the browser `window.print()` dialog.

---

## Architecture

The feature touches two layers only: the **view layer** (data assembly) and the **template layer** (rendering).

```
Browser
  │
  ├─ GET /form137/generate/<student_pk>/<sy_pk>/  →  form137_generate view
  │                                                      │
  │                                                      ├─ Query Grade (all validated, all SYs)
  │                                                      ├─ Group by (school_year, grade_level)
  │                                                      ├─ Sort by grade_level.level ASC
  │                                                      ├─ Compute general_average per block
  │                                                      ├─ Look up Section + Adviser per block
  │                                                      ├─ Build grade_blocks list
  │                                                      └─ render(form137_print.html, context)
  │
  └─ GET /form137/<record_pk>/preview/           →  form137_preview view
                                                       (same assembly logic, record already exists)
```

The template receives a single `grade_blocks` list in the context. Everything else is rendered from that list plus static school metadata.

---

## Components and Interfaces

### 1. `build_grade_blocks(student)` — view helper function

Extracted as a standalone Python function (inside `form137/views.py` or a `form137/utils.py` module) so it can be unit-tested independently of the HTTP request/response cycle.

**Signature:**
```python
def build_grade_blocks(student: Student) -> list[dict]:
    ...
```

**Returns:** An ordered list of grade block dicts, sorted by `grade_level.level` ascending. Each dict has the shape:

```python
{
    "grade_level": GradeLevel,          # ORM object
    "school_year": SchoolYear,          # ORM object
    "section_name": str | None,         # section name or None
    "adviser_name": str | None,         # adviser full name or None
    "subject_rows": list[dict],         # see below
    "general_average": Decimal,         # arithmetic mean of final_grade per subject
}
```

Each `subject_rows` entry:

```python
{
    "subject_name": str,               # display name, JHS canonical order
    "is_mapeh": bool,
    "is_mapeh_sub": bool,              # True for Music/Arts/PE/Health rows
    "q1": Decimal | None,
    "q2": Decimal | None,
    "q3": Decimal | None,
    "q4": Decimal | None,
    "final_grade": Decimal | None,
    "remarks": str,                    # "Passed" / "Failed" / ""
}
```

### 2. `form137_generate(request, student_pk, sy_pk)` — updated view

- Looks up `Student` and `SchoolYear` (used only for the `Form137Record` generation/lookup, not to filter grades).
- Calls `build_grade_blocks(student)` to get the full history.
- Creates or retrieves `Form137Record`.
- Renders `form137_print.html`.

### 3. `form137_preview(request, record_pk)` — updated view

- Looks up `Form137Record`.
- Calls `build_grade_blocks(record.student)` for the same result.
- Renders `form137_print.html`.

### 4. `templates/form137/form137_print.html` — replaced template

Uses only `{% for block in grade_blocks %}` iteration plus the student object and static school constants. No custom template filters required beyond the already-registered `form137_filters.py`.

### 5. `form137/templatetags/form137_filters.py` — minor addition

Add a `floatformat_nodec` filter (or rely on Django's built-in `|floatformat:0` and `|floatformat:2`) and optionally a `next_grade` filter that returns `"11 (Senior High School)"` when level is 10, otherwise `level + 1`.

---

## Data Models

No model changes. The existing models are used as follows:

| Model | Usage |
|---|---|
| `students.Student` | Source of personal info: `lrn`, `first_name`, `middle_name`, `last_name`, `suffix`, `sex`, `birthdate`, `address`, `parent_name`, `parent_phone` |
| `academics.SchoolYear` | `name` field displayed in block header; used to filter `GradingPeriod` records |
| `academics.GradeLevel` | `level` integer used for block ordering and next-grade computation; `name` displayed in block header |
| `academics.Section` | `name` and `adviser` looked up per `(school_year, grade_level)` to populate block header |
| `academics.Subject` | `name` used to map to JHS canonical order |
| `academics.GradingPeriod` | `order` (1–4) used to map grades to Q1–Q4 columns; queried per `school_year` |
| `grades.Grade` | Filtered by `student`, `status='validated'`; supplies `quarter_grade`, `final_grade` |
| `form137.Form137Record` | Created/retrieved on generate; read on preview; `is_printed` marked after print |

### Query Strategy for `build_grade_blocks`

```python
# Single optimised query — all validated grades for the student
grades_qs = (
    Grade.objects
    .filter(student=student, status='validated')
    .select_related(
        'subject', 'subject__grade_level',
        'grading_period',
        'school_year',
        'section', 'section__adviser',
    )
    .order_by('school_year__name', 'subject__grade_level__level', 'grading_period__order')
)
```

Grouping is done in Python (not a second DB query) using `itertools.groupby` or a dict keyed on `(school_year_id, grade_level_id)`.

### JHS Subject Order Mapping

```python
JHS_SUBJECT_ORDER = [
    "Filipino",
    "English",
    "Mathematics",
    "Science",
    "Araling Panlipunan",
    "Edukasyon sa Pagpapakatao",
    "Technology and Livelihood Education",
    "MAPEH",          # parent row
    "Music",          # sub-row
    "Arts",           # sub-row
    "Physical Education",  # sub-row
    "Health",         # sub-row
]

MAPEH_SUBS = {"Music", "Arts", "Physical Education", "Health"}
```

Subjects present in the grade data that are not in this list are appended at the end in alphabetical order (graceful degradation).

### General Average Computation

```python
def compute_general_average(subject_rows: list[dict]) -> Decimal:
    finals = [
        row["final_grade"]
        for row in subject_rows
        if row["final_grade"] is not None and not row["is_mapeh_sub"]
        # MAPEH sub-components are excluded; only top-level subject rows count
        # If only sub-rows exist and no MAPEH parent final exists, include subs instead
    ]
    if not finals:
        return Decimal("0")
    return sum(finals) / len(finals)
```

> **Design decision — MAPEH averaging:** The official SF 10 uses the MAPEH composite `final_grade` row (not the four sub-component rows) for the general average. If a MAPEH composite row exists, include it and exclude sub-rows. If only sub-rows exist (data model stores only sub-subjects), average the sub-rows and use the average as the MAPEH contribution.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

---

### Property 1: Student name formatting

*For any* combination of `first_name`, `middle_name` (optional), `last_name`, and `suffix` (optional), the formatted full name displayed in the Print_Template header and Certification_Box SHALL always follow the pattern `"LAST NAME, FIRST NAME [MIDDLE NAME] [SUFFIX]"` — with absent optional parts omitted (no trailing spaces or extra commas).

**Validates: Requirements 2.1, 9.1**

---

### Property 2: Grade block grouping completeness

*For any* student with validated `Grade` records spanning N distinct `(school_year, grade_level)` pairs, `build_grade_blocks` SHALL return a list of exactly N blocks, each corresponding to exactly one of those pairs — no pair is duplicated and none is omitted.

**Validates: Requirements 3.1, 3.3**

---

### Property 3: Grade block ascending order

*For any* list of grade blocks returned by `build_grade_blocks`, the sequence of `grade_level.level` values SHALL be non-decreasing (sorted ascending), regardless of the order in which grades were recorded in the database.

**Validates: Requirements 3.2, 3.5**

---

### Property 4: Subject ordering within a block

*For any* subset of JHS subjects present in a grade block, the order in which they appear in `subject_rows` SHALL respect the canonical `JHS_SUBJECT_ORDER` — that is, for any two subjects A and B where A precedes B in the canonical list, A SHALL appear before B in the rendered block.

**Validates: Requirements 5.2**

---

### Property 5: Quarter grade rounding

*For any* `quarter_grade` decimal value in a validated `Grade` record, the value displayed in the corresponding quarter cell SHALL equal `round(quarter_grade)` (nearest integer, no decimal places).

**Validates: Requirements 5.4, 5.5**

---

### Property 6: Remarks threshold invariant

*For any* `final_grade` value in a subject row, the `remarks` field SHALL be exactly `"Passed"` if `final_grade >= 75`, and exactly `"Failed"` if `final_grade < 75`. This property must hold for every subject row in every grade block, with no exceptions.

**Validates: Requirements 5.6**

---

### Property 7: General average arithmetic correctness

*For any* grade block containing N subject rows with non-None `final_grade` values (counting only top-level rows, not MAPEH sub-components when a MAPEH composite exists), the `general_average` computed by `build_grade_blocks` SHALL equal the arithmetic mean `sum(final_grades) / N`, accurate to at least two decimal places.

**Validates: Requirements 6.1, 6.3**

---

### Property 8: Promotion/retention threshold invariant

*For any* `general_average` value in a grade block, the promotion status displayed in the General Average REMARKS cell SHALL be exactly `"PROMOTED"` if `general_average >= 75`, and exactly `"RETAINED"` if `general_average < 75`. This must hold for every grade block rendered.

**Validates: Requirements 5.9**

---

### Property 9: Next grade level computation

*For any* student whose highest completed grade level is in the integer range 7–9, the next grade level shown in the Certification_Box SHALL equal `current_level + 1`. When the highest completed grade level is 10, the next grade SHALL display as `"11 (Senior High School)"`.

**Validates: Requirements 9.5, 9.6**

---

### Property 10: Certification box student data interpolation

*For any* student (arbitrary `full_name`, arbitrary `lrn`), the Certification_Box text rendered by the Print_Template SHALL contain the student's exact full name and exact LRN embedded in the certification statement, with no truncation or substitution.

**Validates: Requirements 9.1**

---

## Error Handling

| Scenario | Handling |
|---|---|
| Student has no validated grades at all | `build_grade_blocks` returns an empty list; template renders the student header and an empty state message; no `Form137Record` is created; `form137_generate` redirects to list with a warning message. |
| A grade block exists but a subject has no grade for one or more quarters | Quarter cell renders as blank (empty string). No error raised. |
| Section or adviser is not recorded for a `(school_year, grade_level)` | `section_name` and `adviser_name` default to `None`; template renders blank underline placeholders. |
| `Form137Record` already exists for `(student, school_year, grade_level)` | `get_or_create` returns the existing record without raising an error; the view re-renders with fresh data each time (non-cached). |
| Subject name does not match any entry in `JHS_SUBJECT_ORDER` | Subject is appended at the end of the subject rows in the block, after all canonical subjects. |
| `GradingPeriod` records are missing for a school year | Quarters without a matching period appear as blank; no exception. |
| `general_average` computation on an empty subject list | Returns `Decimal("0")`; REMARKS cell shows `"RETAINED"`. |

---

## Testing Strategy

### Unit Tests (example-based)

Located in `form137/tests/test_views.py` and `form137/tests/test_utils.py`.

- **Template smoke tests**: Render the template with a fixture context and assert static strings appear: "SF 10-JHS", school name, "PAQUITO S. YU MEMORIAL NHS", school ID "314235", "SFRT Revised 2017", "Affix School Seal", "For Transfer Out / JHS Completer Only", "Conducted from".
- **Column header test**: Assert LEARNING AREAS, Quarter 1–4, FINAL RATING, REMARKS headers appear.
- **MAPEH sub-row test**: Render a block containing MAPEH and assert all four sub-rows (Music, Arts, Physical Education, Health) appear indented after the MAPEH row.
- **Remedial table blank rows**: Render with no remedial data; assert at least two blank rows exist in the remedial table.
- **Print button test**: Assert `onclick="window.print()"` and a back-navigation element appear in rendered HTML.
- **Grade 10 → SHS next grade**: Render certification box with grade level 10; assert "11 (Senior High School)" appears.
- **Empty grade list redirect**: Call `form137_generate` for a student with no validated grades; assert redirect to list with warning.

### Property-Based Tests

Located in `form137/tests/test_properties.py`. Use **Hypothesis** (already a viable choice for Django projects; add `hypothesis[django]` to `requirements.txt`).

Each property test runs a minimum of **100 iterations** via `@settings(max_examples=100)`.

```python
# Tag format used in each test:
# Feature: form137-sf10-print-format, Property N: <property text>
```

**Property 1 — Student name formatting**
- Strategy: `st.text()` for each name part with optional middle name / suffix.
- Assert: formatted output matches regex `^[A-Z ,.\-']+, [A-Z ,.\-']+$`-style pattern; no trailing comma; no double spaces.

**Property 2 — Grade block grouping completeness**
- Strategy: Generate a list of `(school_year_id, grade_level_id, final_grade)` tuples (random N up to 12).
- Assert: `build_grade_blocks` output length equals number of distinct `(sy, gl)` pairs; each pair appears exactly once.

**Property 3 — Grade block ascending order**
- Strategy: Same input as Property 2.
- Assert: `[b["grade_level"].level for b in blocks]` is non-decreasing.

**Property 4 — Subject ordering within a block**
- Strategy: Random subsets of `JHS_SUBJECT_ORDER` (excluding MAPEH sub-rows from the pick).
- Assert: For all pairs (A, B) where canonical_index(A) < canonical_index(B), index_in_block(A) < index_in_block(B).

**Property 5 — Quarter grade rounding**
- Strategy: `st.decimals(min_value=0, max_value=100, places=2)`.
- Assert: `render_quarter_cell(grade) == str(round(grade))`.

**Property 6 — Remarks threshold invariant**
- Strategy: `st.decimals(min_value=0, max_value=100, places=2)`.
- Assert: `compute_remarks(grade) == "Passed" if grade >= 75 else "Failed"`.

**Property 7 — General average arithmetic correctness**
- Strategy: `st.lists(st.decimals(min_value=60, max_value=100, places=2), min_size=1, max_size=12)`.
- Assert: `abs(compute_general_average(grades) - sum(grades)/len(grades)) < Decimal("0.01")`.

**Property 8 — Promotion/retention threshold invariant**
- Strategy: `st.decimals(min_value=0, max_value=100, places=2)`.
- Assert: `promotion_status(avg) == "PROMOTED" if avg >= 75 else "RETAINED"`.

**Property 9 — Next grade level computation**
- Strategy: `st.integers(min_value=7, max_value=9)` for the sub-10 case; explicit test for level 10.
- Assert: `next_grade(level) == level + 1` for 7–9; `next_grade(10) == "11 (Senior High School)"`.

**Property 10 — Certification box student data interpolation**
- Strategy: `st.text(min_size=1)` for full name; `st.text(alphabet=st.characters(whitelist_categories=("Nd",)), min_size=12, max_size=12)` for LRN.
- Assert: Rendered certification HTML contains `full_name` and `lrn` verbatim.

### Integration / Manual Tests

- **Print preview in browser**: Load preview page for a real student; verify layout matches SF 10-JHS paper form visually (4 grade blocks for Grades 7–10, column widths, font size, borders).
- **Browser print dialog**: Trigger `window.print()`; verify action buttons disappear and page margins are A4-compatible.
- **PDF export**: Save as PDF from Chrome print dialog; verify text is selectable and page count is reasonable (1–2 pages for a complete JHS record).
