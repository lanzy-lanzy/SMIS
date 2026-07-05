# Implementation Plan: form137-sf10-print-format

## Overview

Replace the existing custom Form 137 print template and its backing view logic with a fully SF 10-JHS compliant implementation. Work proceeds in four phases: (1) a `build_grade_blocks` helper that assembles all-year grade data; (2) wiring both views to use that helper; (3) a `next_grade` template filter; (4) a fully-rewritten SF 10-JHS HTML template; and (5) property-based and unit/integration tests.

---

## Tasks

- [x] 1. Create `build_grade_blocks` helper and supporting constants
  - [x] 1.1 Add `JHS_SUBJECT_ORDER`, `MAPEH_SUBS`, and `build_grade_blocks(student)` to `form137/utils.py` (create the file)
    - Create `form137/utils.py` with `JHS_SUBJECT_ORDER` list and `MAPEH_SUBS` set as per design constants
    - Implement a single-query fetch: `Grade.objects.filter(student=student, status='validated').select_related('subject', 'subject__grade_level', 'grading_period', 'school_year', 'section', 'section__adviser')`
    - Group grades in Python by `(school_year_id, subject__grade_level_id)` using a `dict`; sort resulting blocks by `grade_level.level` ascending
    - For each block look up the `Section` record (via the grade's `section` FK) to populate `section_name` and `adviser_name`
    - Build `subject_rows` in JHS canonical order: place canonical subjects first, append unknowns alphabetically; insert MAPEH parent row followed by Music/Arts/Physical Education/Health sub-rows (`is_mapeh=True`, `is_mapeh_sub=True`)
    - Map each subject's grades to `q1`–`q4` using `grading_period.order`; populate `final_grade` and `remarks` ("Passed" / "Failed" / "")
    - Call `compute_general_average(subject_rows)` to populate `general_average` on the block dict; exclude `is_mapeh_sub` rows when a MAPEH composite row exists
    - Return the ordered list of block dicts
    - _Requirements: 3.1, 3.2, 5.2, 5.6, 6.1, 6.2_

  - [ ]* 1.2 Write property test: grade block grouping completeness (Property 2)
    - **Property 2: Grade block grouping completeness**
    - For any set of validated Grade records spanning N distinct `(school_year, grade_level)` pairs, `build_grade_blocks` returns exactly N blocks — no pair duplicated, none omitted
    - Use `@given` with a list of `(school_year_id, grade_level_id, final_grade)` tuples; assert `len(blocks) == len(distinct_pairs)`
    - **Validates: Requirements 3.1, 3.3**

  - [ ]* 1.3 Write property test: grade block ascending order (Property 3)
    - **Property 3: Grade block ascending order**
    - For any blocks list returned by `build_grade_blocks`, `[b["grade_level"].level for b in blocks]` is non-decreasing
    - Reuse same input strategy as Property 2
    - **Validates: Requirements 3.2, 3.5**

  - [ ]* 1.4 Write property test: subject ordering within a block (Property 4)
    - **Property 4: Subject ordering within a block**
    - For any random subset of canonical JHS subjects, they appear in `subject_rows` in the same relative order as `JHS_SUBJECT_ORDER`
    - Strategy: `st.lists(st.sampled_from(JHS_SUBJECT_ORDER_NAMES), min_size=1, unique=True)`
    - **Validates: Requirements 5.2**

  - [ ]* 1.5 Write property test: general average arithmetic correctness (Property 7)
    - **Property 7: General average arithmetic correctness**
    - `compute_general_average(subject_rows)` equals `sum(finals) / N` to within `Decimal("0.01")`
    - Strategy: `st.lists(st.decimals(min_value=60, max_value=100, places=2), min_size=1, max_size=12)`
    - **Validates: Requirements 6.1, 6.3**

- [x] 2. Add `compute_remarks` and `compute_promotion_status` pure helpers in `form137/utils.py`
  - [x] 2.1 Implement `compute_remarks(final_grade) -> str` and `compute_promotion_status(general_average) -> str`
    - `compute_remarks`: returns `"Passed"` if `final_grade >= 75`, else `"Failed"`; returns `""` if `final_grade is None`
    - `compute_promotion_status`: returns `"PROMOTED"` if `general_average >= 75`, else `"RETAINED"`
    - Export both from `form137/utils.py`
    - _Requirements: 5.6, 5.9_

  - [ ]* 2.2 Write property test: remarks threshold invariant (Property 6)
    - **Property 6: Remarks threshold invariant**
    - `compute_remarks(grade) == "Passed" if grade >= 75 else "Failed"` for all `Decimal` values in `[0, 100]`
    - Strategy: `st.decimals(min_value=0, max_value=100, places=2)`
    - **Validates: Requirements 5.6**

  - [ ]* 2.3 Write property test: promotion/retention threshold invariant (Property 8)
    - **Property 8: Promotion/retention threshold invariant**
    - `compute_promotion_status(avg) == "PROMOTED" if avg >= 75 else "RETAINED"` for all values in `[0, 100]`
    - Strategy: `st.decimals(min_value=0, max_value=100, places=2)`
    - **Validates: Requirements 5.9**

  - [ ]* 2.4 Write property test: quarter grade rounding (Property 5)
    - **Property 5: Quarter grade rounding**
    - A helper `round_quarter(grade)` returns `round(grade)` for any `Decimal` in `[0, 100]`
    - Strategy: `st.decimals(min_value=0, max_value=100, places=2)`
    - **Validates: Requirements 5.4, 5.5**

- [x] 3. Add `next_grade` template filter to `form137/templatetags/form137_filters.py`
  - [x] 3.1 Implement `next_grade` filter
    - Register `@register.filter(name='next_grade')` in `form137/templatetags/form137_filters.py`
    - When `level == 10`, return the string `"11 (Senior High School)"`; otherwise return `level + 1` (integer)
    - _Requirements: 9.5, 9.6_

  - [ ]* 3.2 Write property test: next grade level computation (Property 9)
    - **Property 9: Next grade level computation**
    - `next_grade(level) == level + 1` for integer inputs 7–9; `next_grade(10) == "11 (Senior High School)"`
    - Strategy: `st.integers(min_value=7, max_value=9)` for the sub-10 case; explicit assert for `level=10`
    - **Validates: Requirements 9.5, 9.6**

- [x] 4. Checkpoint — core logic verified
  - Ensure all tests pass for tasks 1–3 before proceeding to view and template changes. Ask the user if questions arise.

- [x] 5. Update `form137_generate` view in `form137/views.py`
  - [x] 5.1 Refactor `form137_generate` to use `build_grade_blocks`
    - Import `build_grade_blocks` from `form137.utils`
    - Replace the existing grade-grouping / general-average logic with a call to `build_grade_blocks(student)`
    - Redirect to `form137:form137_list` with a `messages.warning` when `build_grade_blocks` returns an empty list (no validated grades)
    - Create or retrieve `Form137Record` using `get_or_create`; the `grade_level` for the record should be taken from `grade_blocks[0]["grade_level"]` (the lowest block) or, for existing records, remain unchanged
    - Pass `grade_blocks` to the template context; remove the old `grade_data`, `periods`, `final_grades`, and top-level `general_average` keys
    - _Requirements: 3.1, 3.2, 6.1, 6.2_

- [x] 6. Update `form137_preview` view in `form137/views.py`
  - [x] 6.1 Refactor `form137_preview` to use `build_grade_blocks`
    - Import `build_grade_blocks` from `form137.utils` (already available after task 5.1)
    - Replace the existing grade-grouping logic with `build_grade_blocks(record.student)`
    - Pass `grade_blocks` to the template context; remove the old `grade_data`, `periods`, and `subjects` keys
    - _Requirements: 3.1, 3.2_

- [x] 7. Fully replace `templates/form137/form137_print.html` with SF 10-JHS compliant template
  - [x] 7.1 Write page header row section
    - Top-level single-row table spanning full printable width with cells for "SF 10-JHS", "Pag ___ of ___", School Name ("PAQUITO S. YU MEMORIAL NHS"), School ID (314235), District (DUMINGAG-1), Division (ZAMBOANGA DEL SUR), Region (IX)
    - Load `form137_filters` at top of template
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 7.2 Write student personal information header section
    - Render full name as `"{{ student.last_name|upper }}, {{ student.first_name|upper }} {% if student.middle_name %}{{ student.middle_name|upper }}{% endif %}{% if student.suffix %} {{ student.suffix|upper }}{% endif %}"`
    - Render LRN, sex (`get_sex_display`), birthdate, address, parent name, parent phone in labelled underline-style cells
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 7.3 Write grade blocks loop
    - `{% for block in grade_blocks %}` — render one block per iteration
    - Block header row: "Classified as Grade: {{ block.grade_level.level }}", "Section: {{ block.section_name|default:'___' }}", "School Year: {{ block.school_year.name }}", "Name of Adviser/Teacher: {{ block.adviser_name|default:'___' }}", "Signature: ___"
    - Grades table with columns LEARNING AREAS, Quarter 1, Quarter 2, Quarter 3, Quarter 4, FINAL RATING, REMARKS
    - Iterate `block.subject_rows`: render MAPEH sub-rows with CSS indent class `mapeh-sub`; use `|floatformat:0` for quarter and final grade cells; render blank cell when value is `None`
    - General Average row at bottom of grades table: FINAL RATING cell shows `{{ block.general_average|floatformat:2 }}`; REMARKS cell shows promotion status via `compute_promotion_status` embedded in view context or inline `{% if block.general_average >= 75 %}PROMOTED{% else %}RETAINED{% endif %}`
    - _Requirements: 3.3, 3.5, 4.1, 4.2, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 6.3_

  - [x] 7.4 Write remedial classes sub-table within each grade block
    - Render Remedial_Classes_Table below grades table with header row: Subject/Learning Areas | Final Rating | Remedial Class Mark | Recomputed Final Grade | Remarks
    - Render at least two blank data rows
    - Render "Conducted from (mm/dd/yyyy) ___ to (mm/dd/yyyy) ___" row below the table
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 7.5 Write transfer/completer section and certification box
    - After `{% endfor %}`, render "For Transfer Out / JHS Completer Only" section with blank fillable lines for transfer date and destination school / JHS completion date
    - Render Certification_Box containing: "I CERTIFY that this is a true record of {{ student.last_name|upper }}, {{ student.first_name|upper }}{% if student.middle_name %} {{ student.middle_name|upper }}{% endif %}{% if student.suffix %} {{ student.suffix|upper }}{% endif %} with LRN {{ student.lrn }} and that he/she is eligible for admission to Grade {% with last_block=grade_blocks|last %}{{ last_block.grade_level.level|next_grade }}{% endwith %}."
    - Include School Name, School ID, Last School Year Attended fields
    - Include "Affix School Seal here" placeholder and Principal/School Head signature line
    - Include "SFRT Revised 2017" note
    - _Requirements: 8.1, 8.2, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x] 7.6 Write print CSS and action buttons
    - Fixed-position action bar with "Back" (`javascript:history.back()`) and "Print / Export PDF" (`onclick="window.print()"`) buttons
    - `@media print` rule: hide `.actions`, remove box-shadow, set page margins for A4 (max 10mm per side), remove background colours
    - Table cells: `border: 1px solid #000`, font-size 9–11px, LEARNING AREAS column left-aligned, grade columns center-aligned, MAPEH sub-rows indented via padding-left
    - Page width 210mm
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

- [x] 8. Add property-based tests for name formatting and certification interpolation in `form137/tests/test_properties.py`
  - [x] 8.1 Create `form137/tests/__init__.py` and `form137/tests/test_properties.py`; add `hypothesis[django]` to `requirements.txt`
    - Add `hypothesis` and `hypothesis[django]` to `requirements.txt` with pinned version compatible with the project's Django version
    - Create the `form137/tests/` package if it does not exist
    - Add `@settings(max_examples=100)` decorator to every property test class/function
    - _Requirements: (test infrastructure)_

  - [ ]* 8.2 Write property test: student name formatting (Property 1)
    - **Property 1: Student name formatting**
    - For any combination of `first_name`, `middle_name` (optional), `last_name`, `suffix` (optional), the rendered full-name string matches `"LAST, FIRST [MIDDLE] [SUFFIX]"` — no trailing comma, no double spaces
    - Strategy: `st.text(alphabet=st.characters(whitelist_categories=("Lu","Ll")), min_size=1)` for each part; `st.one_of(st.just(""), st.text(...))` for optional parts
    - **Validates: Requirements 2.1, 9.1**

  - [ ]* 8.3 Write property test: certification box student data interpolation (Property 10)
    - **Property 10: Certification box student data interpolation**
    - Rendered certification HTML contains the student's full name and LRN verbatim, with no truncation
    - Strategy: `st.text(min_size=1)` for full name; `st.text(alphabet=st.characters(whitelist_categories=("Nd",)), min_size=12, max_size=12)` for LRN
    - Use Django `TestCase` with `RequestFactory` to render the template with a mock student
    - **Validates: Requirements 9.1**

- [ ] 9. Add unit and integration tests in `form137/tests/test_views.py`
  - [ ] 9.1 Create `form137/tests/test_views.py` with Django `TestCase` fixtures
    - Set up `setUp` with a minimal fixture: one `Student`, two `SchoolYear` records (grades 7 and 8), corresponding `GradeLevel`, `GradingPeriod` (Q1–Q4 each), `Section`, `Subject` (including MAPEH and its four sub-subjects), and `Grade` records with `status='validated'`
    - _Requirements: (test infrastructure)_

  - [ ]* 9.2 Write smoke test: SF 10-JHS static strings present in rendered HTML
    - Assert rendered HTML contains: "SF 10-JHS", "PAQUITO S. YU MEMORIAL NHS", "314235", "SFRT Revised 2017", "Affix School Seal", "For Transfer Out / JHS Completer Only", "Conducted from"
    - _Requirements: 1.4, 9.3, 9.4_

  - [ ]* 9.3 Write column header test
    - Assert rendered HTML contains "LEARNING AREAS", "Quarter 1", "Quarter 2", "Quarter 3", "Quarter 4", "FINAL RATING", "REMARKS"
    - _Requirements: 5.1_

  - [ ]* 9.4 Write MAPEH sub-row test
    - Render a block containing MAPEH; assert all four sub-row labels — "Music", "Arts", "Physical Education", "Health" — appear in the rendered HTML after the MAPEH row
    - _Requirements: 5.3, 11.5_

  - [ ]* 9.5 Write remedial table blank rows test
    - Render with no remedial data; assert at least two blank `<tr>` rows exist within the remedial classes table
    - _Requirements: 7.3_

  - [ ]* 9.6 Write Grade 10 → SHS next grade test
    - Render a certification box where the highest grade block has `grade_level.level == 10`; assert "11 (Senior High School)" appears in rendered HTML
    - _Requirements: 9.5_

  - [ ]* 9.7 Write empty-grade redirect test
    - Call `form137_generate` for a student with zero validated grades; assert HTTP 302 redirect to `form137:form137_list` and that a warning message is present
    - _Requirements: 3.1 (error path), 6.2_

  - [ ]* 9.8 Write print button presence test
    - Assert rendered HTML contains `onclick="window.print()"` and `javascript:history.back()`
    - _Requirements: 10.1, 10.2_

- [ ] 10. Final checkpoint — all tests pass
  - Ensure all unit, property, and integration tests pass. Verify the template renders correctly for a student with grades across multiple school years. Ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Property tests require `hypothesis[django]`; add it to `requirements.txt` before running
- `build_grade_blocks` is extracted to `form137/utils.py` so it can be tested without the HTTP request cycle
- The `Grade.section` FK gives the section context per grade record; use it to look up `section_name` and `adviser_name` within each block
- The existing `getitem` filter in `form137_filters.py` is no longer needed by the new template (grade data comes pre-structured), but it should be kept to avoid breaking other templates
- All correctness property tests live in `form137/tests/test_properties.py`; unit/integration tests in `form137/tests/test_views.py`
- Each property test must be decorated with `@settings(max_examples=100)` and tagged with the feature and property number

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "1.5", "2.2", "2.3", "2.4", "3.2"] },
    { "id": 2, "tasks": ["5.1", "6.1"] },
    { "id": 3, "tasks": ["7.1", "7.2"] },
    { "id": 4, "tasks": ["7.3", "7.4"] },
    { "id": 5, "tasks": ["7.5", "7.6"] },
    { "id": 6, "tasks": ["8.1"] },
    { "id": 7, "tasks": ["8.2", "8.3", "9.1"] },
    { "id": 8, "tasks": ["9.2", "9.3", "9.4", "9.5", "9.6", "9.7", "9.8"] }
  ]
}
```
