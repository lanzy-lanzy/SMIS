# Form 137 Legal Print Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Form 137 print/export screen match the attached legal-size SF 10-JHS layout.

**Architecture:** Keep grade collection in `form137.utils`, add a small print-layout helper that pads grade blocks with blank blocks, and render those blocks in the existing print template. The browser print dialog remains the export path because WeasyPrint is not installed in this environment.

**Tech Stack:** Django 5.1 templates and views, Python unit tests, CSS print media on legal paper.

---

### Task 1: Printable Grade Block Helper

**Files:**
- Modify: `form137/utils.py`
- Test: `form137/tests/test_print_layout.py`

- [ ] **Step 1: Write the failing test**

Create tests that import `build_printable_grade_blocks` and assert it pads to three blocks with canonical blank subject rows.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python manage.py test form137.tests.test_print_layout -v 2`
Expected: import failure because `build_printable_grade_blocks` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add canonical subject rows and `build_printable_grade_blocks(grade_blocks, minimum_blocks=3)` to `form137/utils.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python manage.py test form137.tests.test_print_layout -v 2`
Expected: all tests pass.

### Task 2: View Context

**Files:**
- Modify: `form137/views.py`

- [ ] **Step 1: Pass print blocks**

Import `build_printable_grade_blocks`, compute `print_blocks`, and pass it to both generate and preview render contexts.

- [ ] **Step 2: Run form137 tests**

Run: `uv run python manage.py test form137 -v 2`
Expected: all form137 tests pass.

### Task 3: Legal-Size Template

**Files:**
- Modify: `templates/form137/form137_print.html`

- [ ] **Step 1: Replace A4 layout**

Change the print page to legal portrait, compact grade block sections, reference-style headers, blank padded block rendering, transfer line, and compact certification footer.

- [ ] **Step 2: Smoke render**

Run the Django dev server and open a Form 137 preview page. Print/export from the browser should show the legal-size reference structure.

### Task 4: Verify

**Files:**
- No new files.

- [ ] **Step 1: Automated tests**

Run: `uv run python manage.py test form137 -v 2`
Expected: all form137 tests pass.

- [ ] **Step 2: Manual layout check**

Open the print preview and compare against `C:\Users\gerla\Downloads\MUTIAKAISHA-1.pdf`: one legal page, stacked grade blocks, compact remedial sections, transfer line, and certification box at the bottom.
