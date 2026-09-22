import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User, AuditLog
from academics.models import SchoolYear, GradeLevel, Section, Subject, TeacherAssignment, GradingPeriod
from students.models import Student
from grades.models import Grade, GradeSubmission, GradeValidation
from form137.models import Form137Record


class Command(BaseCommand):
    help = "Seed the database with comprehensive sample data for all roles and workflows."

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing non-admin users and sample data before seeding.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        reset = options.get('reset', False)

        if reset:
            self.stdout.write(self.style.WARNING('Resetting sample data...'))
            self._reset_sample_data()

        self.stdout.write(self.style.NOTICE('Seeding users...'))
        users = self._create_users()

        self.stdout.write(self.style.NOTICE('Seeding academic structure...'))
        school_years = self._create_school_years()
        grade_levels = self._create_grade_levels()
        sections = self._create_sections(school_years, grade_levels, users['teachers'])
        subjects = self._create_subjects(grade_levels)
        grading_periods = self._create_grading_periods(school_years)

        self.stdout.write(self.style.NOTICE('Seeding teacher assignments...'))
        assignments = self._create_teacher_assignments(users['teachers'], subjects, sections, school_years)

        self.stdout.write(self.style.NOTICE('Seeding students...'))
        students = self._create_students(grade_levels, sections, school_years, users['student_users'])

        self.stdout.write(self.style.NOTICE('Seeding grades and submissions...'))
        self._create_grades_and_submissions(students, assignments, grading_periods, school_years, sections, users)

        self.stdout.write(self.style.NOTICE('Seeding Form 137 records...'))
        self._create_form137_records(students, school_years, users['admin'])

        self.stdout.write(self.style.SUCCESS('Database seeded successfully.'))

    def _reset_sample_data(self):
        """Clear data that will be re-seeded. Keep any manually created admin accounts."""
        GradeValidation.objects.all().delete()
        GradeSubmission.objects.all().delete()
        Grade.objects.all().delete()
        Form137Record.objects.all().delete()
        TeacherAssignment.objects.all().delete()
        GradingPeriod.objects.all().delete()
        Section.objects.all().delete()
        Subject.objects.all().delete()
        GradeLevel.objects.all().delete()
        SchoolYear.objects.all().delete()
        Student.objects.all().delete()

        # Delete seeded sample users but preserve existing admins/superusers
        User.objects.filter(is_superuser=False, is_staff=False).delete()

    def _create_users(self):
        """Create sample users for every role."""
        users = {}

        # Admin
        admin, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'first_name': 'System',
                'last_name': 'Administrator',
                'email': 'admin@smis.edu',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin.set_password('admin123')
        admin.save()
        users['admin'] = admin

        # Registrar
        registrar, _ = User.objects.get_or_create(
            username='registrar',
            defaults={
                'first_name': 'Maria',
                'last_name': 'Santos',
                'email': 'registrar@smis.edu',
                'role': 'registrar',
            }
        )
        registrar.set_password('registrar123')
        registrar.save()
        users['registrar'] = registrar

        # Teachers
        teacher_data = [
            ('reyes', 'Ana', 'Reyes'),
            ('lopez', 'Carmen', 'Lopez'),
            ('gonzaga', 'Jose', 'Gonzaga'),
            ('mendoza', 'Elena', 'Mendoza'),
            ('delacruz', 'Antonio', 'Delacruz'),
            ('bautista', 'Sophia', 'Bautista'),
        ]
        teachers = []
        for username, first, last in teacher_data:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': f'{username}@smis.edu',
                    'role': 'teacher',
                }
            )
            user.set_password('teacher123')
            user.save()
            teachers.append(user)
        users['teachers'] = teachers

        # Student users (will be linked to Student records)
        student_user_data = [
            ('student1', 'Luis', 'Castillo'),
            ('student2', 'Jennifer', 'Gonzales'),
            ('student3', 'Angela', 'Mendoza'),
            ('student4', 'Rose', 'Santos'),
            ('student5', 'Mark', 'Ramos'),
        ]
        student_users = []
        for username, first, last in student_user_data:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': f'{username}@smis.edu',
                    'role': 'student',
                }
            )
            user.set_password('student123')
            user.save()
            student_users.append(user)
        users['student_users'] = student_users

        return users

    def _create_school_years(self):
        """Create previous and current school years."""
        sy24_25, _ = SchoolYear.objects.get_or_create(
            name='2024-2025',
            defaults={'is_current': False}
        )
        sy25_26, _ = SchoolYear.objects.get_or_create(
            name='2025-2026',
            defaults={'is_current': True}
        )
        return {'2024-2025': sy24_25, '2025-2026': sy25_26}

    def _create_grade_levels(self):
        """Create Grade 7-12 levels."""
        grade_levels = {}
        for level in range(7, 13):
            gl, _ = GradeLevel.objects.get_or_create(
                level=level,
                defaults={'name': f'Grade {level}', 'description': f'Grade {level} level'}
            )
            grade_levels[level] = gl
        return grade_levels

    def _create_sections(self, school_years, grade_levels, teachers):
        """Create sections A/B/C for each grade level and school year."""
        sections = {}
        section_names = ['A', 'B', 'C']

        for sy_name, sy in school_years.items():
            sections[sy_name] = {}
            for level, gl in grade_levels.items():
                sections[sy_name][level] = []
                for idx, name in enumerate(section_names):
                    section, _ = Section.objects.get_or_create(
                        name=f'Grade {level}-{name}',
                        grade_level=gl,
                        school_year=sy,
                        defaults={
                            'adviser': random.choice(teachers) if teachers else None
                        }
                    )
                    sections[sy_name][level].append(section)

        return sections

    def _create_subjects(self, grade_levels):
        """Create canonical JHS subjects per grade level."""
        subject_codes = {
            'Filipino': 'FIL',
            'English': 'ENG',
            'Mathematics': 'MATH',
            'Science': 'SCI',
            'Araling Panlipunan': 'AP',
            'Edukasyon sa Pagpapakatao': 'EsP',
            'MAPEH': 'MAPEH',
            'Music': 'MUSIC',
            'Arts': 'ARTS',
            'Physical Education': 'PE',
            'Health': 'HEALTH',
            'Technology and Livelihood Education': 'TLE',
        }

        # Core subjects per grade level
        core_subjects = [
            'Filipino', 'English', 'Mathematics', 'Science',
            'Araling Panlipunan', 'Edukasyon sa Pagpapakatao',
            'MAPEH', 'Technology and Livelihood Education'
        ]

        subjects = {}
        for level, gl in grade_levels.items():
            subjects[level] = []
            for name in core_subjects:
                subj, _ = Subject.objects.get_or_create(
                    code=f'{subject_codes[name]}{level}',
                    defaults={
                        'name': name,
                        'description': f'{name} for Grade {level}',
                        'grade_level': gl,
                        'is_active': True,
                    }
                )
                subjects[level].append(subj)

        return subjects

    def _create_grading_periods(self, school_years):
        """Create Q1-Q4 grading periods for each school year."""
        periods = {}
        period_names = {1: 'Quarter 1', 2: 'Quarter 2', 3: 'Quarter 3', 4: 'Quarter 4'}

        for sy_name, sy in school_years.items():
            periods[sy_name] = {}
            for order in range(1, 5):
                is_current = (sy_name == '2025-2026' and order == 1)
                gp, _ = GradingPeriod.objects.get_or_create(
                    order=order,
                    school_year=sy,
                    defaults={
                        'name': period_names[order],
                        'is_current': is_current,
                        'is_submissions_open': is_current,
                    }
                )
                # Ensure current year Q1 is open, others closed by default
                gp.is_current = is_current
                gp.is_submissions_open = is_current
                gp.save()
                periods[sy_name][order] = gp

        return periods

    def _create_teacher_assignments(self, teachers, subjects, sections, school_years):
        """Assign teachers to subjects/sections realistically."""
        assignments = []
        current_sy = school_years['2025-2026']

        # Distribute teachers across subjects/sections
        teacher_idx = 0
        for level in range(7, 13):
            for subject in subjects[level]:
                # Assign 2-3 sections per subject to spread workload
                for section in sections['2025-2026'][level][:2]:
                    teacher = teachers[teacher_idx % len(teachers)]
                    assignment, _ = TeacherAssignment.objects.get_or_create(
                        teacher=teacher,
                        subject=subject,
                        section=section,
                        school_year=current_sy,
                    )
                    assignments.append(assignment)
                    teacher_idx += 1

        return assignments

    def _create_students(self, grade_levels, sections, school_years, student_users):
        """Create students with mixed statuses and link some to user accounts."""
        first_names_m = ['Luis', 'Antonio', 'Mark', 'Jose', 'Carlos', 'Daniel', 'Miguel', 'Gabriel', 'Rafael', 'David']
        first_names_f = ['Jennifer', 'Angela', 'Rose', 'Maria', 'Sofia', 'Isabella', 'Emma', 'Lucia', 'Carmen', 'Linda']
        last_names = ['Castillo', 'Gonzales', 'Mendoza', 'Santos', 'Ramos', 'Reyes', 'Cruz', 'Garcia', 'Torres', 'Rivera',
                      'Flores', 'Dela Cruz', 'Bautista', 'Domingo', 'Villanueva', 'Santiago', 'Aquino', 'Navarro', 'Salazar', 'Lim']

        statuses = ['active'] * 8 + ['inactive'] + ['transferred'] + ['dropped']
        sexes = ['M', 'F']

        students = []
        student_idx = 1

        for level in range(7, 13):
            for section in sections['2025-2026'][level]:
                # 4-6 students per section
                for _ in range(random.randint(4, 6)):
                    sex = random.choice(sexes)
                    first = random.choice(first_names_m if sex == 'M' else first_names_f)
                    last = random.choice(last_names)
                    status = random.choice(statuses)

                    # Generate a 12-digit LRN: 2-digit region + 6-digit school + 4-digit student
                    lrn = f'12{202500:06d}{student_idx:04d}'

                    student, _ = Student.objects.get_or_create(
                        lrn=lrn,
                        defaults={
                            'first_name': first,
                            'last_name': last,
                            'middle_name': random.choice(['', 'A', 'B', 'C', 'D']),
                            'sex': sex,
                            'birthdate': date(2010 - (level - 7), random.randint(1, 12), random.randint(1, 28)),
                            'birthplace': f'{last} City, Philippines',
                            'address': f'{random.randint(1, 999)} {last} St., Paquito S. Yu Memorial NHS District',
                            'phone': f'09{random.randint(100000000, 999999999)}',
                            'email': f'{first.lower()}.{last.lower()}{student_idx}@student.smis.edu',
                            'parent_name': f'{random.choice(first_names_m if sex == "F" else first_names_f)} {last}',
                            'parent_phone': f'09{random.randint(100000000, 999999999)}',
                            'parent_address': f'{random.randint(1, 999)} {last} St.',
                            'grade_level': grade_levels[level],
                            'section': section,
                            'school_year': school_years['2025-2026'],
                            'status': status,
                        }
                    )
                    students.append(student)
                    student_idx += 1

        # Link first 5 students to student user accounts
        for idx, user in enumerate(student_users):
            if idx < len(students):
                student = students[idx]
                student.user_account = user
                student.first_name = user.first_name
                student.last_name = user.last_name
                student.email = user.email
                student.save()

        return students

    def _create_grades_and_submissions(self, students, assignments, grading_periods, school_years, sections, users):
        """Create grades for all quarters with realistic workflow statuses."""
        teachers = users['teachers']
        registrar = users['registrar']
        current_sy = school_years['2025-2026']

        # Build assignment lookup by section/subject
        assignment_map = {}
        for a in assignments:
            key = (a.section_id, a.subject_id)
            assignment_map[key] = a

        # For current school year, create grades for all quarters
        for student in students:
            if student.status != 'active':
                continue

            level = student.grade_level.level
            section = student.section

            for subject in self._get_subjects_for_level(level):
                assignment = assignment_map.get((section.id, subject.id))
                if not assignment:
                    continue

                teacher = assignment.teacher

                for order in range(1, 5):
                    gp = grading_periods['2025-2026'][order]

                    # Determine grade workflow status based on quarter
                    if order == 1:
                        # Q1: fully validated (closed workflow)
                        status = 'validated'
                    elif order == 2:
                        # Q2: mix of pending submissions and validated
                        status = random.choice(['validated', 'submitted'])
                    elif order == 3:
                        # Q3: some drafts, some submitted
                        status = random.choice(['draft', 'submitted', 'validated'])
                    else:
                        # Q4: mostly drafts
                        status = random.choice(['draft', 'draft', 'submitted'])

                    # Generate realistic grades
                    written = random.randint(70, 95)
                    performance = random.randint(70, 95)
                    assessment = random.randint(70, 95)
                    quarter_grade = Decimal((written + performance + assessment) / 3).quantize(Decimal('0.01'))
                    remarks = 'Passed' if quarter_grade >= 75 else ('Incomplete' if quarter_grade >= 60 else 'Failed')

                    grade, _ = Grade.objects.update_or_create(
                        student=student,
                        subject=subject,
                        grading_period=gp,
                        school_year=current_sy,
                        defaults={
                            'section': section,
                            'written_work': written,
                            'performance_task': performance,
                            'assessment': assessment,
                            'quarter_grade': quarter_grade,
                            'final_grade': quarter_grade,
                            'remarks': remarks,
                            'status': status,
                            'encoded_by': teacher,
                            'updated_by': teacher,
                        }
                    )

                    # Create submission records for submitted/validated grades
                    if status in ['submitted', 'validated']:
                        submission, _ = GradeSubmission.objects.get_or_create(
                            teacher=teacher,
                            subject=subject,
                            section=section,
                            school_year=current_sy,
                            grading_period=gp,
                            defaults={
                                'status': 'pending' if status == 'submitted' else 'approved',
                                'remarks': '' if status == 'submitted' else 'Validated by registrar',
                            }
                        )

                        if status == 'validated' and submission.status == 'pending':
                            submission.status = 'approved'
                            submission.remarks = 'Validated by registrar'
                            submission.save()
                            GradeValidation.objects.get_or_create(
                                submission=submission,
                                defaults={
                                    'validated_by': registrar,
                                    'status': 'approved',
                                    'remarks': 'Validated by registrar',
                                }
                            )

        # Create previous-year validated grades for Form 137 history.
        # Every active student in Grade 8-12 gets one prior year of validated
        # grades so that multi-year Form 137 records are realistic.
        prev_sections = sections['2024-2025']
        for student in students:
            if student.status != 'active':
                continue
            level = student.grade_level.level
            if level == 7:
                continue  # No previous year for Grade 7

            prev_level = level - 1
            prev_sy = school_years['2024-2025']
            prev_section = prev_sections[prev_level][0] if prev_sections.get(prev_level) else student.section

            for subject in self._get_subjects_for_level(prev_level):
                for order in range(1, 5):
                    gp = grading_periods['2024-2025'][order]
                    quarter_grade = Decimal(random.randint(75, 92))
                    Grade.objects.get_or_create(
                        student=student,
                        subject=subject,
                        grading_period=gp,
                        school_year=prev_sy,
                        defaults={
                            'section': prev_section,
                            'written_work': random.randint(75, 92),
                            'performance_task': random.randint(75, 92),
                            'assessment': random.randint(75, 92),
                            'quarter_grade': quarter_grade,
                            'final_grade': quarter_grade,
                            'remarks': 'Passed' if quarter_grade >= 75 else 'Failed',
                            'status': 'validated',
                            'encoded_by': random.choice(teachers),
                            'updated_by': random.choice(teachers),
                        }
                    )

    def _get_subjects_for_level(self, level):
        """Helper to fetch subjects for a grade level."""
        from academics.models import Subject
        return list(Subject.objects.filter(grade_level__level=level))

    def _create_form137_records(self, students, school_years, admin_user):
        """Generate Form 137 records for students with validated grades."""
        current_sy = school_years['2025-2026']

        for student in students:
            if student.status != 'active':
                continue

            validated_grades = Grade.objects.filter(
                student=student,
                school_year=current_sy,
                status='validated'
            )

            if validated_grades.exists():
                grade_level = validated_grades.first().subject.grade_level
                Form137Record.objects.get_or_create(
                    student=student,
                    school_year=current_sy,
                    grade_level=grade_level,
                    defaults={'generated_by': admin_user}
                )
