# SMIS - School Management Information System

**Paquito S. Yu Memorial National High School**

Web-Based School Management System with Automated Grade Management and Form 137 Generation

---

## Tech Stack

- **Backend:** Django 5.1+
- **Frontend:** Django Templates + HTMX + Alpine.js
- **Styling:** Tailwind CSS 4 (compiled locally)
- **Database:** SQLite (development) / PostgreSQL (production)
- **Offline-first:** No CDN dependencies

---

## Features

- Role-based access control (Admin, Registrar, Teacher, Student) — see [docs/registrar-role.md](docs/registrar-role.md) for the Registrar's end-to-end workflow (student registry, grade validation, Form 137 issuance, reports)
- Student information management
- Grade encoding, submission, and validation workflow
- Automatic Form 137 generation with PDF export
- Dashboard analytics and reports
- At-risk student identification
- Audit trail logging
- Dark mode support
- Mobile-responsive design

---

## Installation Guide

### 1. Clone the repository

```bash
git clone <repository-url>
cd SMIS
```

### 2. Create virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

Or using uv:

```bash
uv sync
uv run pip install -r requirements.txt
```

### 4. Install Node.js dependencies (for Tailwind CSS)

```bash
npm install
```

### 5. Download HTMX and Alpine.js (already included in static/js/)

If not present, download:
```bash
curl -o static/js/htmx.min.js https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js
curl -o static/js/alpine.min.js https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js
```

### 6. Compile Tailwind CSS

```bash
npx @tailwindcss/cli -i static/src/input.css -o static/css/output.css --watch
```

### 7. Set up environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 8. Run migrations

```bash
uv run python manage.py makemigrations accounts students academics grades form137
uv run python manage.py migrate
```

### 9. Create superuser

```bash
uv run python manage.py createsuperuser
```

### 10. Seed sample data

```bash
uv run python manage.py seed_data
```

### 11. Run development server

```bash
uv run python manage.py runserver
```

Visit: http://127.0.0.1:8000

---

## Default Login Credentials

| Role       | Username   | Password     |
|-----------|-----------|-------------|
| Admin     | admin     | admin123    |
| Registrar | registrar | registrar123|
| Teacher   | teacher1  | teacher123  |

---

## Design System — "Aurora Glass"

All templates share one design system defined in `static/src/input.css`. It
combines two material languages over a single aurora canvas:

| Layer      | Purpose                                                              |
|------------|----------------------------------------------------------------------|
| **Canvas** | `.app-shell` paints blurred colour blooms on a fixed layer, so glass has something stable to refract. |
| **Glass**  | Translucent, blurred surfaces with a gradient hairline, a top specular edge and a pointer-tracked sheen. |
| **Neumorph** | Soft extruded / recessed surfaces built from paired light-and-shadow shadows. |

### Core tokens

Colours, shadows and surfaces live in CSS custom properties on `:root` and
`:root.dark`, so a single rule serves both themes:

- `--glass-bg`, `--glass-bg-strong`, `--glass-bg-weak` — glass tints
- `--glass-sheen`, `--glass-specular`, `--glass-hairline` — highlight colours
- `--neu-shadow`, `--neu-shadow-sm`, `--neu-shadow-inset` — neumorphic depth
- `--field-bg`, `--field-border`, `--field-color` — form controls
- `--ink`, `--ink-muted`, `--ink-soft` — text hierarchy

### Component classes

```
Surfaces   .glass  .glass-card  .surface-card  .stat-card  .form-card
           .neu-card  .neu-inset  .neu-tile  .info-banner  .profile-banner
Controls   .btn .btn-primary .btn-secondary .btn-danger .btn-accent .btn-ghost
           .field  .segmented .segmented-btn  .tab-btn  .app-icon-button
Data       .data-table  .data-table-head  .page-link  .link-action  .chip
Feedback   .modal-card  .toast  .alert  .empty-state
Layout     .app-shell  .app-sidebar  .app-topbar  .app-footer  .page-head
```

### Two rules to keep in mind

1. **Prefer component classes over raw utilities.** The component layer sits
   below Tailwind's utility layer, so a utility like `hover:shadow-md` will
   silently override the glass treatment. If you need to style a card, reach
   for the component class rather than adding utilities on top.
2. **Form widgets are unified in CSS, not in Python.** Django widgets carry
   their own utility classes, so the rules that re-skin every control are
   written *outside* any cascade layer (unlayered rules outrank every
   layered rule). You do not need to change `accounts/forms.py` to restyle a
   field.

### Liquid glass sheen

`static/js/app.js` tracks the pointer and feeds the position into the `--mx`
/ `--my` custom properties, so the specular highlight travels across a
surface the way light behaves on real glass. The position is coalesced into a
single animation frame, and the effect is skipped entirely for visitors who
prefer reduced motion.

### Visual verification

The project ships a Playwright harness for checking the rendered result:

```bash
npm run shots              # every route, light + dark, into tmp/shots/
npm run shots -- --viewport  # above-the-fold only
npm run shots:landing      # full-page public landing page
npm run shots:modal        # glass modal over a blurred backdrop
npm run shots:student      # student-role view
npm run smoke              # HTMX / Alpine / modal / pagination smoke test
```

Run the dev server on port 8899 first (or set `SMIS_BASE`).

---

## Grade Workflow

1. Admin creates school year, grade levels, sections, subjects
2. Admin assigns teachers to subjects and sections
3. Teacher encodes grades → saves as draft
4. Teacher submits grades for validation
5. Registrar reviews and validates/returns grades
6. Validated grades are locked
7. Registrar generates Form 137 from validated grades
8. Registrar/Admin views reports and analytics

---

## UV Commands

```bash
# Install all dependencies
uv sync

# Run Django management commands
uv run python manage.py migrate
uv run python manage.py runserver
uv run python manage.py seed_data

# Add a dependency
uv add django-cors-headers

# Run tests
uv run pytest
```

---

## Project Structure

```
SMIS/
├── config/              # Django project settings
├── accounts/            # User management & authentication
├── students/            # Student information management
├── academics/           # School year, sections, subjects
├── grades/              # Grade encoding & validation
├── form137/             # Form 137 generation
├── reports/             # Analytics & reports
├── dashboard/           # Main dashboard
├── templates/           # HTML templates
├── static/              # Static files (CSS, JS, icons)
│   ├── css/
│   ├── js/
│   ├── src/
│   └── icons/
├── tools/               # Playwright visual-verification harness
├── manage.py
├── pyproject.toml
├── requirements.txt
├── tailwind.config.js
├── package.json
└── README.md
```

---

## License

Educational Use Only - Paquito S. Yu Memorial National High School
