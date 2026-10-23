from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.conf import settings


# Default category weights (percent of 100): Written Work 20%, Performance Task
# 50%, Quarterly Assessment 30% (matches the class-record / DepEd format). Each
# category's percentage score (PS) is the raw total expressed as a % of its
# highest possible score; the weighted score (WS) is PS x weight, and the sum of
# the three weighted scores is the INITIAL grade. That initial grade is then run
# through the transmutation table below to produce the official TERM grade
# stored in `Grade.quarter_grade` and consumed by reports, Form 137 and exports.
# Weights are configurable per class by the teacher (stored on each Grade row);
# these constants are only the defaults.
WW_WEIGHT = Decimal('20')
PT_WEIGHT = Decimal('50')
AS_WEIGHT = Decimal('30')


# Transmutation table: the weighted total of the three categories is the
# INITIAL grade; the school's official TERM grade is the value this table maps
# it to. Ordered by descending initial grade; each band is inclusive of both
# bounds and the bands are contiguous across 0.00-100.00 at 2-decimal precision.
TRANSMUTATION_BANDS = [
    (Decimal('99.50'), Decimal('100.00'), 100),
    (Decimal('98.32'), Decimal('99.49'), 99),
    (Decimal('97.14'), Decimal('98.31'), 98),
    (Decimal('95.96'), Decimal('97.13'), 97),
    (Decimal('94.78'), Decimal('95.95'), 96),
    (Decimal('93.60'), Decimal('94.77'), 95),
    (Decimal('92.42'), Decimal('93.59'), 94),
    (Decimal('91.24'), Decimal('92.41'), 93),
    (Decimal('90.06'), Decimal('91.23'), 92),
    (Decimal('88.88'), Decimal('90.05'), 91),
    (Decimal('87.70'), Decimal('88.87'), 90),
    (Decimal('86.52'), Decimal('87.69'), 89),
    (Decimal('85.34'), Decimal('86.51'), 88),
    (Decimal('84.16'), Decimal('85.33'), 87),
    (Decimal('82.98'), Decimal('84.15'), 86),
    (Decimal('81.80'), Decimal('82.97'), 85),
    (Decimal('80.62'), Decimal('81.79'), 84),
    (Decimal('79.44'), Decimal('80.61'), 83),
    (Decimal('78.26'), Decimal('79.43'), 82),
    (Decimal('77.08'), Decimal('78.25'), 81),
    (Decimal('75.90'), Decimal('77.07'), 80),
    (Decimal('74.72'), Decimal('75.89'), 79),
    (Decimal('73.54'), Decimal('74.71'), 78),
    (Decimal('72.36'), Decimal('73.53'), 77),
    (Decimal('71.18'), Decimal('72.35'), 76),
    (Decimal('70.00'), Decimal('71.17'), 75),
    (Decimal('65.34'), Decimal('69.99'), 74),
    (Decimal('60.67'), Decimal('65.33'), 73),
    (Decimal('56.01'), Decimal('60.66'), 72),
    (Decimal('51.34'), Decimal('56.00'), 71),
    (Decimal('46.67'), Decimal('51.33'), 70),
    (Decimal('42.01'), Decimal('46.66'), 69),
    (Decimal('37.34'), Decimal('42.00'), 68),
    (Decimal('32.68'), Decimal('37.33'), 67),
    (Decimal('28.01'), Decimal('32.67'), 66),
    (Decimal('23.35'), Decimal('28.00'), 65),
    (Decimal('18.68'), Decimal('23.34'), 64),
    (Decimal('14.01'), Decimal('18.67'), 63),
    (Decimal('9.35'), Decimal('14.00'), 62),
    (Decimal('4.68'), Decimal('9.34'), 61),
    (Decimal('0.00'), Decimal('4.67'), 60),
]

# Qualitative descriptor for each term-grade band, shown beside the numeric
# grade on the class record and report card.
DESCRIPTOR_BANDS = [
    (90, 'Advancing', 'Consistently demonstrates skills and understanding that '
                      'meet or exceed standards with independence, flexibility, and depth.'),
    (80, 'Benchmarking', 'Demonstrates expected grade-level skills and understanding '
                         'competently and independently.'),
    (75, 'Connecting', 'Demonstrates sufficient understanding and application of '
                       'grade-level standards with occasional guidance.'),
    (65, 'Developing', 'Demonstrates partial understanding and inconsistent application '
                       'of skills, requires targeted support and scaffolding.'),
    (0, 'Emerging', 'Does not yet demonstrate foundational skills and understanding; '
                    'requires intensive support.'),
]


def transmute_grade(value):
    """Official term grade for an initial (weighted) grade, per the table above.

    The input is quantized to 2 decimals first, matching the stored precision of
    `Grade.initial_grade`, so the live preview and the saved record transmute identically.
    """
    initial = Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    initial = max(Decimal('0.00'), min(initial, Decimal('100.00')))
    for low, _high, transmuted in TRANSMUTATION_BANDS:
        if initial >= low:
            return transmuted


def grade_descriptor(value):
    """Descriptor name for a term grade (Advancing/Benchmarking/...)."""
    grade = int(Decimal(value or 0).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    for low, name, _description in DESCRIPTOR_BANDS:
        if grade >= low:
            return name


def category_ps(score, highest):
    """Percentage score of a category: raw total as a % of its highest possible.

    Falls back to treating the raw value as an already-percentage score when no
    highest is given (legacy grades stored 0-100 with no maximum).
    """
    score = Decimal(score or 0)
    highest = Decimal(highest or 0)
    if highest > 0:
        return score / highest * Decimal('100')
    return score


def weighted_quarter_grade(written, written_max, performance, performance_max,
                           assessment, assessment_max,
                           ww_weight=WW_WEIGHT, pt_weight=PT_WEIGHT, as_weight=AS_WEIGHT):
    """Sum of the three categories' weighted scores.

    Weights are percentages that should total 100 (default WW 20 + PT 50 + QA 30);
    they are normalised so the aggregate always reflects the student's share of
    the configured weight total.
    """
    total_weight = Decimal(ww_weight or 0) + Decimal(pt_weight or 0) + Decimal(as_weight or 0)
    if total_weight <= 0:
        return Decimal('0')
    return (category_ps(written, written_max) * Decimal(ww_weight)
            + category_ps(performance, performance_max) * Decimal(pt_weight)
            + category_ps(assessment, assessment_max) * Decimal(as_weight)) / total_weight


class Grade(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('validated', 'Validated'),
        ('returned', 'Returned'),
        ('locked', 'Locked'),
    )

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='grades')
    subject = models.ForeignKey('academics.Subject', on_delete=models.CASCADE, related_name='grades')
    grading_period = models.ForeignKey('academics.GradingPeriod', on_delete=models.CASCADE, related_name='grades')
    school_year = models.ForeignKey('academics.SchoolYear', on_delete=models.CASCADE, related_name='grades')
    section = models.ForeignKey('academics.Section', on_delete=models.CASCADE, related_name='grades')
    
    # Written Work (20%): five component scores summed into written_work (total).
    # Each item also has a class-wide "highest possible score"; the category max
    # (written_work_highest) is the sum of the item maxima and drives the PS.
    written_work_1 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    written_work_2 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    written_work_3 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    written_work_4 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    written_work_5 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    written_work_1_highest = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    written_work_2_highest = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    written_work_3_highest = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    written_work_4_highest = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    written_work_5_highest = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    written_work = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    written_work_highest = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    # Performance Tasks (50%): three component scores summed into performance_task.
    performance_task_1 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    performance_task_2 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    performance_task_3 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    performance_task_1_highest = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    performance_task_2_highest = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    performance_task_3_highest = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    performance_task = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    performance_task_highest = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    # Quarterly Assessment (30%): three component scores summed into assessment.
    assessment_1 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    assessment_2 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    assessment_3 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    assessment_1_highest = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    assessment_2_highest = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    assessment_3_highest = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    assessment = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    assessment_highest = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    
    # Configurable category weights (percent, teacher-set; default WW 20 / PT 20 / QA 50).
    written_work_weight = models.DecimalField(max_digits=5, decimal_places=2, default=WW_WEIGHT)
    performance_task_weight = models.DecimalField(max_digits=5, decimal_places=2, default=PT_WEIGHT)
    assessment_weight = models.DecimalField(max_digits=5, decimal_places=2, default=AS_WEIGHT)

    # Initial grade: the weighted total of the three categories before
    # transmutation. `quarter_grade` holds the transmuted official term grade.
    initial_grade = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    quarter_grade = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    final_grade = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    remarks = models.CharField(max_length=20, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    encoded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='encoded_grades')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_grades')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student__last_name', 'subject__name']
        unique_together = ('student', 'subject', 'grading_period', 'school_year')

    def __str__(self):
        return f"{self.student} - {self.subject} - {self.quarter_grade}"

    @property
    def written_work_ps(self):
        return category_ps(self.written_work, self.written_work_highest)

    @property
    def performance_task_ps(self):
        return category_ps(self.performance_task, self.performance_task_highest)

    @property
    def assessment_ps(self):
        return category_ps(self.assessment, self.assessment_highest)

    @property
    def written_work_ws(self):
        return self.written_work_ps * self.written_work_weight / 100

    @property
    def performance_task_ws(self):
        return self.performance_task_ps * self.performance_task_weight / 100

    @property
    def assessment_ws(self):
        return self.assessment_ps * self.assessment_weight / 100

    @property
    def term_grade(self):
        """The official term grade (transmuted initial grade) as a whole number."""
        return int(self.quarter_grade)

    @property
    def description(self):
        """Qualitative descriptor for the term grade (Advancing/Benchmarking/...)."""
        return grade_descriptor(self.quarter_grade)

    def compute_initial_grade(self):
        self.initial_grade = weighted_quarter_grade(
            self.written_work, self.written_work_highest,
            self.performance_task, self.performance_task_highest,
            self.assessment, self.assessment_highest,
            self.written_work_weight, self.performance_task_weight, self.assessment_weight,
        )
        return self.initial_grade

    def compute_quarter_grade(self):
        self.compute_initial_grade()
        self.quarter_grade = transmute_grade(self.initial_grade)
        self.compute_remarks()
        self.save()

    def compute_remarks(self):
        if self.quarter_grade >= 75:
            self.remarks = 'Passed'
        elif self.quarter_grade >= 60:
            self.remarks = 'Incomplete'
        else:
            self.remarks = 'Failed'


class GradeSubmission(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Under Review'),
        ('approved', 'Approved'),
        ('returned', 'Returned'),
    )

    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='grade_submissions')
    subject = models.ForeignKey('academics.Subject', on_delete=models.CASCADE)
    section = models.ForeignKey('academics.Section', on_delete=models.CASCADE)
    school_year = models.ForeignKey('academics.SchoolYear', on_delete=models.CASCADE)
    grading_period = models.ForeignKey('academics.GradingPeriod', on_delete=models.CASCADE)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    remarks = models.TextField(blank=True)
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']
        unique_together = ('teacher', 'subject', 'section', 'school_year', 'grading_period')

    def __str__(self):
        return f"{self.teacher.get_full_name()} - {self.subject} - {self.section} - {self.grading_period}"


class GradeValidation(models.Model):
    submission = models.OneToOneField(GradeSubmission, on_delete=models.CASCADE, related_name='validation')
    validated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=GradeSubmission.STATUS_CHOICES, default='pending')
    remarks = models.TextField(blank=True)
    validated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Validation for {self.submission}"
