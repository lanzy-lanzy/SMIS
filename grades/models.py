from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.conf import settings


# Default category weights (percent of 100): Written Work 20%, Performance Task
# 50%, Quarterly Assessment 30% (matches the class-record / DepEd format). Each
# category's percentage score (PS) is the raw total expressed as a % of its
# highest possible score; the weighted score (WS) is PS x weight, and the
# quarterly grade is the sum of the three weighted scores. Weights are
# configurable per class by the teacher (stored on each Grade row); these
# constants are only the defaults.
WW_WEIGHT = Decimal('20')
PT_WEIGHT = Decimal('50')
AS_WEIGHT = Decimal('30')


def grade_to_letter(value):
    """DepEd Order 8/2015 grading scale, as the letter used on the class record.

    The term grade is the initial (weighted) grade rounded to the nearest whole
    number; the letter is that grade's descriptor band:
      90-100 A (Outstanding) | 85-89 B (Very Satisfactory) |
      80-84 C (Satisfactory) | 75-79 D (Fairly Satisfactory) | <75 E.
    """
    g = int(Decimal(value or 0).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    if g >= 90:
        return 'A'
    if g >= 85:
        return 'B'
    if g >= 80:
        return 'C'
    if g >= 75:
        return 'D'
    return 'E'


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
        """The initial (weighted) quarter grade rounded to the nearest whole number."""
        return int(self.quarter_grade.quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    @property
    def description(self):
        """DepEd letter descriptor for the term grade (A/B/C/D/E)."""
        return grade_to_letter(self.quarter_grade)

    def compute_quarter_grade(self):
        self.quarter_grade = weighted_quarter_grade(
            self.written_work, self.written_work_highest,
            self.performance_task, self.performance_task_highest,
            self.assessment, self.assessment_highest,
            self.written_work_weight, self.performance_task_weight, self.assessment_weight,
        )
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
