import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from academics.models import SchoolYear, GradeLevel, Section, Subject, TeacherAssignment, GradingPeriod
from students.models import Student
from grades.models import Grade

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed the database with sample data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...')

        # Create admin
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
        self.stdout.write(self.style.SUCCESS('Created admin user (admin/admin123)'))

        # Create registrar
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
        self.stdout.write(self.style.SUCCESS('Created registrar (registrar/registrar123)'))

        # Create principal
        principal, _ = User.objects.get_or_create(
            username='principal',
            defaults={
                'first_name': 'Juan',
                'last_name': 'Dela Cruz',
                'email': 'principal@smis.edu',
                'role': 'principal',
            }
        )
        principal.set_password('principal123')
        principal.save()
        self.stdout.write(self.style.SUCCESS('Created principal (principal/principal123)'))

        # Create teachers
        teachers = []
        teacher_data = [
            ('teacher1', 'Ana', 'Reyes'),
            ('teacher2', 'Pedro', 'Garcia'),
            ('teacher3', 'Carmen', 'Lopez'),
        ]
        for uname, fname, lname in teacher_data:
            t, _ = User.objects.get_or_create(
                username=uname,
                defaults={
                    'first_name': fname,
                    'last_name': lname,
                    'email': f'{uname}@smis.edu',
                    'role': 'teacher',
                }
            )
            t.set_password('teacher123')
            t.save()
            teachers.append(t)
        self.stdout.write(self.style.SUCCESS('Created teachers'))

        # Create school year
        sy, _ = SchoolYear.objects.get_or_create(
            name='2025-2026',
            defaults={'is_current': True}
        )

        # Create grade levels
        grade_levels = []
        for i in range(7, 13):
            gl, _ = GradeLevel.objects.get_or_create(
                level=i,
                defaults={'name': f'Grade {i}', 'description': f'Grade {i} level'}
            )
            grade_levels.append(gl)

        # Create sections
        sections = []
        section_names = ['A', 'B', 'C']
        for gl in grade_levels[:4]:
            for sname in section_names:
                sec, _ = Section.objects.get_or_create(
                    name=f'{gl.name}-{sname}',
                    grade_level=gl,
                    school_year=sy,
                    defaults={'adviser': random.choice(teachers)}
                )
                sections.append(sec)

        # Create subjects
        subjects = []
        subject_data = [
            ('MATH', 'Mathematics', 7),
            ('ENG', 'English', 7),
            ('SCI', 'Science', 7),
            ('FIL', 'Filipino', 7),
            ('AP', 'Araling Panlipunan', 7),
            ('MAPEH', 'MAPEH', 7),
            ('TLE', 'TLE', 7),
            ('ESP', 'ESP', 7),
        ]
        for code, name, level in subject_data:
            sub, _ = Subject.objects.get_or_create(
                code=code,
                defaults={'name': name, 'grade_level': grade_levels[0]}
            )
            subjects.append(sub)

        # Create grading periods
        for i in range(1, 5):
            GradingPeriod.objects.get_or_create(
                order=i,
                school_year=sy,
                defaults={
                    'name': f'Quarter {i}',
                    'is_current': (i == 1)
                }
            )

        # Create teacher assignments
        for teacher in teachers:
            for sub in random.sample(subjects, 3):
                for sec in random.sample(sections, 2):
                    TeacherAssignment.objects.get_or_create(
                        teacher=teacher,
                        subject=sub,
                        section=sec,
                        school_year=sy
                    )

        # Create students
        first_names_m = ['Jose', 'Antonio', 'Luis', 'Miguel', 'Carlos', 'Andres', 'Ramon', 'Ricardo',
                         'Fernando', 'Gabriel', 'Daniel', 'Patrick', 'Mark', 'John', 'Paul']
        first_names_f = ['Maria', 'Rosa', 'Teresa', 'Linda', 'Grace', 'Joy', 'Rose', 'Nora',
                         'Carmen', 'Linda', 'Patricia', 'Jennifer', 'Jessica', 'Michelle', 'Angela']
        last_names = ['Santos', 'Reyes', 'Cruz', 'Garcia', 'Mendoza', 'Torres', 'Ramos', 'Rivera',
                      'Gonzales', 'Aquino', 'Bautista', 'Castillo', 'Dela Cruz', 'Fernandez', 'Lopez']
        
        students = []
        for i in range(40):
            sex = random.choice(['M', 'F'])
            fname = random.choice(first_names_m if sex == 'M' else first_names_f)
            lname = random.choice(last_names)
            gl = random.choice(grade_levels[:4])
            sec = random.choice([s for s in sections if s.grade_level == gl])
            
            student, _ = Student.objects.get_or_create(
                lrn=f'2025{i+1:06d}',
                defaults={
                    'first_name': fname,
                    'last_name': lname,
                    'sex': sex,
                    'birthdate': f'{random.randint(2008,2012)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}',
                    'address': f'{random.randint(1,100)} Sample Street, Barangay Sample',
                    'parent_name': f'{random.choice(last_names)} {lname}',
                    'grade_level': gl,
                    'section': sec,
                    'school_year': sy,
                    'status': 'active',
                }
            )
            students.append(student)

        # Create sample grades
        period = GradingPeriod.objects.filter(school_year=sy, order=1).first()
        for student in students:
            for sub in subjects[:4]:
                written = round(random.uniform(60, 100), 2)
                performance = round(random.uniform(60, 100), 2)
                assessment = round(random.uniform(60, 100), 2)
                quarter = round((written + performance + assessment) / 3, 2)
                remarks = 'Passed' if quarter >= 75 else ('Incomplete' if quarter >= 60 else 'Failed')
                
                Grade.objects.get_or_create(
                    student=student,
                    subject=sub,
                    grading_period=period,
                    school_year=sy,
                    defaults={
                        'section': student.section,
                        'written_work': written,
                        'performance_task': performance,
                        'assessment': assessment,
                        'quarter_grade': quarter,
                        'final_grade': quarter,
                        'remarks': remarks,
                        'status': 'validated',
                        'encoded_by': random.choice(teachers),
                    }
                )

        self.stdout.write(self.style.SUCCESS(f'Created {len(students)} students with grades'))
        self.stdout.write(self.style.SUCCESS('Database seeding complete!'))
