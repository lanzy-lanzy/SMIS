# Requirements Document

## Introduction

This feature replaces the existing custom Form 137 print template in the SMIS (School Management Information System) Django project with a layout that faithfully replicates the official Philippine Department of Education **SF 10-JHS (School Form 10 – Junior High School)** format. The form serves as the Learner's Permanent Academic Record and must be suitable for direct printing and PDF export via the browser print dialog. The redesign also requires updating the backing view to supply the student's complete multi-year academic history across all grade levels attended.

## Glossary

- **SF 10-JHS**: School Form 10 for Junior High School — the official DepEd Learner's Permanent Academic Record format revised in 2017.
- **Print_Template**: The Django HTML template `templates/form137/form137_print.html` rendered in the browser for printing or saving as PDF.
- **View**: The Django view functions in `form137/views.py` (`form137_generate` and `form137_preview`) that supply context data to the Print_Template.
- **Grade_Block**: A self-contained table section inside the Print_Template representing one grade level and school year that the student attended.
- **School_Info**: Static school metadata — School Name: "PAQUITO S. YU MEMORIAL NHS", School ID: 314235, District: DUMINGAG-1, Division: ZAMBOANGA DEL SUR, Region: IX.
- **Grade**: A Django model record in `grades.Grade` holding a student's `quarter_grade`, `final_grade`, and `status` for a specific subject, grading period, and school year.
- **JHS_Subject_Order**: The canonical ordering of JHS learning areas: Filipino, English, Mathematics, Science, Araling Panlipunan (AP), Edukasyon sa Pagpapakatao (EsP), Technology and Livelihood Education (TLE), MAPEH (with indented sub-components Music, Arts, Physical Education, Health).
- **General_Average**: The arithmetic mean of all subjects' final grades for a given grade level and school year block.
- **Remedial_Classes_Table**: A sub-table within each Grade_Block listing subjects where the student may have undergone remedial classes, with columns: Subject/Learning Areas, Final Rating, Remedial Class Mark, Recomputed Final Grade, Remarks.
- **Certification_Box**: The bottom section of the print form containing the official certification statement, school seal placeholder, and principal/school head signature line.
- **LRN**: Learner Reference Number — the student's unique identifier stored in `students.Student.lrn`.
- **GradingPeriod**: A Django model in `academics.GradingPeriod` representing one quarter (order 1–4) within a school year.
- **Section**: A Django model in `academics.Section` with fields `name` and `adviser` (FK to User).
- **SchoolYear**: A Django model in `academics.SchoolYear` with a `name` field (e.g., "2023-2024").
- **GradeLevel**: A Django model in `academics.GradeLevel` with `name` and `level` (integer) fields.
- **MAPEH_Subcomponents**: The four sub-subjects listed under MAPEH — Music, Arts, Physical Education, Health — stored as individual Subject records whose names match these labels.

---

## Requirements

### Requirement 1: Page Header Row

**User Story:** As a school registrar, I want the printed form to show the official SF 10-JHS page header, so that the document is immediately identifiable as the official DepEd record.

#### Acceptance Criteria

1. THE Print_Template SHALL display "SF 10-JHS" followed by "Pag ___ of ___" fields in the top-left area of the page header row.
2. THE Print_Template SHALL display the School_Info fields — School Name, School ID, District, Division, and Region — on the same header row as the page identifier.
3. THE Print_Template SHALL render the header row as a single-row table spanning the full printable width, with each label-value pair visually aligned.
4. WHEN the Print_Template is rendered, THE Print_Template SHALL display School_Info values as static constants matching the configured school data (School Name: "PAQUITO S. YU MEMORIAL NHS", School ID: 314235, District: DUMINGAG-1, Division: ZAMBOANGA DEL SUR, Region: IX).

---

### Requirement 2: Student Personal Information Header

**User Story:** As a school registrar, I want the student's name, LRN, sex, birthdate, and address to appear at the top of the form, so that the record is unambiguously linked to the correct learner.

#### Acceptance Criteria

1. THE Print_Template SHALL display the student's full name in "LAST NAME, FIRST NAME MIDDLE NAME SUFFIX" format.
2. THE Print_Template SHALL display the student's LRN.
3. THE Print_Template SHALL display the student's date of birth, sex, and address.
4. THE Print_Template SHALL display the student's parent or guardian name and contact number.

---

### Requirement 3: Grade-Level Block Structure

**User Story:** As a school registrar, I want one Grade_Block rendered per grade level and school year the student attended, so that the complete JHS academic history is visible on a single form.

#### Acceptance Criteria

1. THE View SHALL query all validated Grade records for the student across all school years and group them by (school_year, grade_level) pair.
2. THE View SHALL pass the grouped academic history to the Print_Template as an ordered list of Grade_Block data structures, sorted by GradeLevel.level ascending.
3. THE Print_Template SHALL render exactly one Grade_Block per (school_year, grade_level) entry provided by the View.
4. WHEN a student has no validated grades for a given grade level slot, THE Print_Template SHALL render an empty Grade_Block with blank grade cells to preserve the standard SF 10-JHS layout (up to 4 grade-level blocks for Grades 7–10).
5. THE Print_Template SHALL render Grade_Blocks stacked vertically in ascending grade level order.

---

### Requirement 4: Grade-Block Header Row

**User Story:** As a school registrar, I want each Grade_Block to show the grade classification, section, school year, and adviser information, so that each block is fully contextualized.

#### Acceptance Criteria

1. THE Print_Template SHALL render a header row at the top of each Grade_Block containing: "Classified as Grade: [level]", "Section: [section name]", "School Year: [school year name]", "Name of Adviser/Teacher: [adviser full name]", and "Signature: ___".
2. WHEN a section or adviser is not recorded for a grade level and school year, THE Print_Template SHALL render the corresponding field as a blank underline placeholder.

---

### Requirement 5: Grades Table Layout

**User Story:** As a school registrar, I want each Grade_Block to contain a grades table with the correct columns and subject rows, so that all quarterly and final grades are displayed in the official SF 10-JHS format.

#### Acceptance Criteria

1. THE Print_Template SHALL render a grades table inside each Grade_Block with columns: LEARNING AREAS, Quarter 1, Quarter 2, Quarter 3, Quarter 4, FINAL RATING, REMARKS.
2. THE Print_Template SHALL list subjects in JHS_Subject_Order within each grades table.
3. WHEN a subject is MAPEH, THE Print_Template SHALL render MAPEH as a primary row followed by four indented sub-rows for Music, Arts, Physical Education, and Health.
4. THE Print_Template SHALL populate each quarter cell with the corresponding `quarter_grade` value from the Grade record, rounded to the nearest whole number.
5. THE Print_Template SHALL populate the FINAL RATING cell with the `final_grade` value from the Grade record, rounded to the nearest whole number.
6. THE Print_Template SHALL populate the REMARKS cell with "Passed" WHEN the final_grade is 75 or above, and "Failed" WHEN the final_grade is below 75.
7. WHEN no Grade record exists for a subject-quarter combination, THE Print_Template SHALL render the cell as blank.
8. THE Print_Template SHALL render a "General Average" row at the bottom of each grades table, spanning the LEARNING AREAS column as a merged label, with the computed General_Average value in the FINAL RATING column.
9. THE Print_Template SHALL render "PROMOTED" in the REMARKS cell of the General Average row WHEN the General_Average is 75 or above, and "RETAINED" WHEN the General_Average is below 75.

---

### Requirement 6: General Average Computation

**User Story:** As a school registrar, I want the General Average computed correctly per grade block, so that promotion or retention status is accurate.

#### Acceptance Criteria

1. THE View SHALL compute the General_Average for each (school_year, grade_level) block as the arithmetic mean of the `final_grade` values of all subjects with validated Grade records in that block.
2. WHEN a grade block has no validated Grade records, THE View SHALL set the General_Average for that block to zero.
3. THE Print_Template SHALL display the General_Average value rounded to two decimal places in the General Average row.

---

### Requirement 7: Remedial Classes Sub-Table

**User Story:** As a school registrar, I want a Remedial Classes section beneath each grades table, so that any remedial interventions are documented in compliance with the SF 10-JHS format.

#### Acceptance Criteria

1. THE Print_Template SHALL render a Remedial_Classes_Table below the grades table in each Grade_Block with the header row: Subject/Learning Areas | Final Rating | Remedial Class Mark | Recomputed Final Grade | Remarks.
2. THE Print_Template SHALL include a row below the Remedial_Classes_Table showing: "Conducted from (mm/dd/yyyy) ___ to (mm/dd/yyyy) ___".
3. WHEN no remedial class data is available in the system, THE Print_Template SHALL render at least two blank data rows in the Remedial_Classes_Table to preserve the official form layout.

---

### Requirement 8: Transfer Out / JHS Completer Section

**User Story:** As a school registrar, I want the "For Transfer Out / JHS Completer Only" section to appear after all Grade_Blocks, so that transfer and completion details can be filled in during printing.

#### Acceptance Criteria

1. THE Print_Template SHALL render a "For Transfer Out / JHS Completer Only" section below the last Grade_Block.
2. THE Print_Template SHALL render blank fillable lines in this section for: date of transfer or completion, school transferred to or JHS completion date.

---

### Requirement 9: Certification Box

**User Story:** As a school registrar, I want the official certification statement with student name, LRN, and eligibility at the bottom of the form, so that the document meets the legal requirements of an official DepEd record.

#### Acceptance Criteria

1. THE Print_Template SHALL render a Certification_Box at the bottom of the form containing the statement: "I CERTIFY that this is a true record of [STUDENT FULL NAME] with LRN [LRN] and that he/she is eligible for admission to Grade [NEXT GRADE LEVEL]."
2. THE Print_Template SHALL display the School Name, School ID, and Last School Year Attended fields within the Certification_Box.
3. THE Print_Template SHALL render a Principal/School Head signature line with the label "Affix School Seal here" inside the Certification_Box.
4. THE Print_Template SHALL display "SFRT Revised 2017" as a note within or adjacent to the Certification_Box.
5. WHEN the student's current grade level is 10, THE Print_Template SHALL show the next grade as "11 (Senior High School)".
6. WHEN the student's current grade level is below 10, THE Print_Template SHALL compute the next grade as the current grade level integer plus 1.

---

### Requirement 10: Print and PDF Export

**User Story:** As a school registrar, I want a Print / Export PDF button that uses the browser print dialog, so that no server-side PDF library is required.

#### Acceptance Criteria

1. THE Print_Template SHALL render a "Print / Export PDF" button that calls `window.print()` when clicked.
2. THE Print_Template SHALL render a "Back" button that navigates to the previous page when clicked.
3. WHEN the browser print dialog is active, THE Print_Template SHALL hide the action buttons using a CSS `@media print` rule.
4. THE Print_Template SHALL apply `@media print` CSS rules that remove background colors and shadows and set the page margins to match standard A4 paper dimensions.

---

### Requirement 11: Visual Fidelity to the Official SF 10-JHS Format

**User Story:** As a school registrar, I want the printed form to visually match the official DepEd SF 10-JHS document, so that it is accepted as an official record.

#### Acceptance Criteria

1. THE Print_Template SHALL use a compact tabular layout with thin 1px solid borders on all table cells, matching the official form's grid-based appearance.
2. THE Print_Template SHALL use a font size of 9–11px for table cell content to ensure all grade blocks fit within a standard A4 page or span to a second page cleanly.
3. THE Print_Template SHALL render column headers (Quarter 1–4, FINAL RATING, REMARKS) in uppercase bold text.
4. THE Print_Template SHALL render the LEARNING AREAS column left-aligned and all grade columns center-aligned.
5. THE Print_Template SHALL render MAPEH sub-component rows (Music, Arts, Physical Education, Health) with visible indentation relative to the MAPEH parent row.
6. THE Print_Template SHALL set the page width to 210mm (A4) with a print-safe padding of no more than 10mm on each side.
