# The Registrar Role in SMIS

> Scope note: this document reflects the **current** implementation. The former
> `principal` role has been removed from the system (see [Role Cleanup](#role-cleanup--no-principal-role)).
> All code paths cited below were verified against `accounts/`, `students/`, `grades/`,
> `form137/`, and `reports/`.

## 1. Role Model at a Glance

SMIS defines four roles on `accounts.User.role`:

| Role | Username | Purpose |
|---|---|---|
| `admin` | System Administrator | Full system configuration: users, academics (school years, grade levels, sections, subjects), and everything below |
| `registrar` | Registrar | **Custodian of official academic records**: student registry, grade validation, Form 137 (SF10) issuance, analytics reports |
| `teacher` | Teacher | Grade encoding and submission for assigned sections only |
| `student` | Student/Parent | Read-only view of their own validated grades |

Access is enforced by decorators in `accounts/decorators.py`:

- `role_required(*roles)` — generic gate
- `registrar_or_admin_required` — the Registrar's primary permission boundary
- `teacher_or_admin_required`, `admin_required`

The Registrar effectively holds every record-level authority short of system
configuration: whatever an Admin can do with *academic data*, a Registrar can
(also) do — except deleting students.

---

## 2. Student Management

Implemented in `students/views.py`.

| Capability | Registrar | Admin | Teacher |
|---|---|---|---|
| View the **entire** student roster (search, filter by grade/section/status, sectioned or list view) | ✅ | ✅ | scoped to assigned sections only |
| View a student's profile + per-quarter grade history | ✅ | ✅ | own-section students only |
| Create student (`student_create`) | ✅ | ✅ | ❌ |
| Edit student (`student_edit`) | ✅ | ✅ | ❌ |
| CSV roster export with LRN, personal info, parents' contacts (`student_export`) | ✅ | ✅ | ❌ |
| Delete student | ❌ | ✅ (only) | ❌ |

Key behaviors:

- **Create/update are audited.** Every write logs an `AuditLog` entry
  (`Created student …` / `Updated student …`).
- **Deletion is deliberately Admin-only.** Even then, the system warns the
  Admin when the student has `validated`/`locked` grades, because deleting a
  student cascades to their entire grade history. This makes the Registrar a
  *builder and corrector* of the registry, but never its destroyer. The roster
  Delete control is now hidden for non-admins (`student_table.html`), so the
  UI matches the backend. Students are retired via the record's **status**
  field (`inactive` / `transferred` / `dropped`) instead — the DepEd-aligned
  archive path available to Registrars.
- The Registrar can enroll/move students across grade levels and sections by
  editing the student record (section/grade-level FKs live on `Student`).

---

## 3. Grade Validation Lifecycle

This is the Registrar's central workflow. Two models cooperate:

- **`Grade`** (per student × subject × quarter): `draft → submitted → validated`, with `returned` as the correction state and `locked` retained as a legacy state (historical `locked` rows were migrated to `validated`; queries treat both as "official").
- **`GradeSubmission`** (per teacher × subject × section × quarter): `pending → approved | returned`, plus a `GradeValidation` record capturing who reviewed it, when, and why.

### End-to-end flow

```
 Teacher                          Registrar
 ────────                          ─────────
 1. encode grades (draft)
    WW + PT + Assessment
    quarter = avg, remarks auto
         │
 2. submit ──────────────────────► 3. GradeSubmission = pending
    (draft → submitted)               appears in Submission Review
    period must have                      (submission_list, filter by
    is_submissions_open                     status/grading period)
                                     │
                              4a. VALIDATE              4b. RETURN
                                 submission → approved     submission → returned
                                 Grades → validated       Grades → returned
                                 GradeValidation row      remarks sent back;
                                 + audit grade_validate   teacher may re-encode
                                 + reviewed_at set        and resubmit
         │                                    │
 5. locked for teacher: cannot edit ────────► 6. validated grades feed Form 137,
    until/unless returned                        student-facing dashboard, and
                                                 all reports/analytics
```

### Registrar-side details (`grades/views.py`)

- **Review queue** (`submission_list`): Registrar/Admin see **all** submissions
  school-wide for the current school year (teachers see only their own),
  filterable by grading period and status.
- **Act on a submission** (`submission_validate`, Registrar/Admin only):
  renders the full grade sheet (all students × scores × computed quarter grades)
  for inspection before deciding. Only `pending` submissions can be acted on.
- **Validate** flips every `submitted`/`returned` `Grade` in that
  subject-section-quarter to `validated`, writes a `GradeValidation`
  (`validated_by`, `remarks`, timestamp) and an `AuditLog`
  (`grade_validate`).
- **Return** flips `submitted` grades to `returned` with mandatory-context
  remarks, logs `grade_return`; teachers regain editing rights on those rows.
- **Bulk visibility tools**: `grade_list` (all grades with status counts) and
  `grade_export` (full CSV of every grade record incl. status) — both
  Registrar/Admin.

### Integrity guarantees the workflow gives the Registrar

- Grades are **immutable to teachers once validated** — the only path back is
  a Registrar return action, which is itself audited.
- Every state transition leaves a trail: `encoded_by` / `updated_by` on
  `Grade`, `validated_by` on `GradeValidation`, and `AuditLog` entries for
  submit/validate/return.
- Quarterly averages and Passed/Incomplete/Failed remarks (≥75 / 60–74 / <60)
  are computed consistently at encode time, so the Registrar reviews the same
  numbers everywhere.

---

## 4. Form 137 (SF10-JHS) Issuance

Implemented in `form137/` — this module is **restricted to `@role_required('admin', 'registrar')`** end to end. The Registrar is its sole operational owner.

| Endpoint | What the Registrar does |
|---|---|
| `form137_list` | Search the permanent-record register (by school year, grade level, name, LRN); monitor stats: total / printed / unprinted / generated-this-month |
| `form137_generate` (student × school year) | Issue a record: builds SF10 grade blocks **only from `validated`/`locked` grades**; warns and aborts if none exist; creates a `Form137Record` (unique per student + SY + grade level, `generated_by` = the Registrar on duty) and opens the print view; logs `form137_generate` |
| `form137_bulk_generate` (school year) | Issue records for every student holding validated grades in that year in one pass |
| `form137_preview` | Re-open any previously issued record for reprinting |
| `form137_export` | CSV audit export of all issued records (who generated, when, printed flag) |
| `form137_mark_printed` | **Issuance-loop closure**: POST-only endpoint that sets `is_printed`, records a `form137_print` audit entry, and returns JSON. The print view fires it automatically on `beforeprint` (any real print or Ctrl+P / Save-as-PDF), offers a manual *Mark as Printed* button, and shows a live Printed / Not printed status pill |

Print output (`form137_print.html` + `utils.py`) follows the official SF10-JHS
layout spec (`/.kiro/specs/form137-sf10-print-format`): canonical JHS subject
order, MAPEH composite with indented sub-rows, quarter columns Q1–Q4, per-year
general average, `PROMOTED`/`RETAINED` (≥75), and blank future-year padding.
The "Name of Principal/School Head" and Registrar lines on the print sheet are
**document-format signature fields** required by DepEd — they are paper
artifacts, not app roles.

### Report cards / printable deliverables — current state

SMIS has **no separate report-card generator**. The printable official record
today is the Form 137 (SF10). Interim per-quarter results are served by:

- `grade_list` + `grade_export` (Registrar CSV of the whole gradebook),
- `student_detail` per-quarter grade history (Registrar view of any student),
- the student's own dashboard (`student_dashboard`), which shows **only
  validated/locked** grades — students never see unvalidated data.

If per-quarter report cards are needed, that is a gap to build (see
Recommendations).

---

## 5. Academic Analytics & Reports

The Reports module (`reports/views.py`) was migrated from the removed
Principal role to **`@registrar_or_admin_required`**. The Registrar can now:

- **Grade trends** — averages over quarters/years, filtered by school year and grade level
- **Section performance** — per-section general averages
- **Subject performance** — per-subject averages across sections
- **At-risk students** — students below the passing threshold, filterable by year/grade level
- **Student history** — full longitudinal record for any single student

Reports are reachable from the sidebar for Admin/Registrar only.

---

## 6. Role Cleanup — No Principal Role

- `principal` was removed from `ROLE_CHOICES`, the `is_principal` property was
  deleted, and the `principal_or_admin_required` decorator is gone.
- Data migration `accounts/0002_alter_user_role` reassigned every
  `principal` user to **`registrar`** (their former oversight duties — reports
  and record custody — are exactly the Registrar's).
- Data migration `accounts/0003_retire_principal_demo_account` **renamed the
  leftover demo account to `registrar2` and deactivated it**, so no credential
  implies the removed role and Registrar access is no longer duplicated.
  Former audit records (`validated_by`, `generated_by`) keep pointing at it.
- Views that formerly admitted the Principal now either drop it (students,
  grades, Form 137) or substitute the Registrar (reports).

### Sidebar navigation

The staff sidebar follows the documented lifecycle order: **Dashboard →
Students → (Academics, admin) → Grades → Submission Review → Form 137 →
Reports**. *Submission Review* (`grades:submission_list`, active also on
`submission_validate`) is surfaced directly for staff, giving the Registrar a
one-click entry to the pending-approval queue between encoding and issuance.

---

## 7. Recommendations

1. ~~Rename/retire the `principal`-username account~~ — **done** (migration
   `accounts/0003`: renamed to `registrar2`, deactivated).
2. ~~Align UI with backend on student deletion~~ — **done** (Delete control
   hidden for non-admins; archival is handled through student status).
3. **Build per-quarter report cards** on top of validated grades if the school
   prints interim cards — the data pipeline (quarter blocks, remarks, GA)
   already exists in `form137/utils.py` and can be reused.
4. ~~Track Form 137 printing explicitly~~ — **done** (`form137_mark_printed`
   endpoint; auto-mark on print + manual button; covered by
   `form137/tests/test_mark_printed.py`).
5. **Guard un-validation** — there is currently no "revoke approved
   submission" path; when added, require an audit-tracked reason so the
   Registrar's custody remains checkable.
6. **Move to Django groups/permissions** before roles grow again — the
   hand-rolled `role_required(...)` tuples made the Principal removal a
   cross-codebase edit; object-level permissions would make it a config change.
