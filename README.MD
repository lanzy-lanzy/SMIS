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
