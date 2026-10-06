from decimal import Decimal

from django.db import models
from django.conf import settings


# DepEd Home-School quarterly weights: Written Work 20%, Performance Tasks 50%,
# Quarterly Assessment 30%. Each category's percentage score (PS) is the raw
# total expressed as a % of its highest possible score; the weighted score (WS)
# is PS x weight, and the quarterly grade is the sum of the three weighted scores.
WW_WEIGHT = Decimal('0.20')
PT_WEIGHT = Decimal('0.50')
AS_WEIGHT = Decimal('0.30')


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
                           assessment, assessment_max):
    """Sum of the three categories' weighted scores (WW 20% + PT 50% + QA 30%)."""
    return (category_ps(written, written_max) * WW_WEIGHT
            + category_ps(performance, performance_max) * PT_WEIGHT
            + category_ps(assessment, assessment_max) * AS_WEIGHT)


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
    
    # Written Work (20%): three component scores summed into written_work (total).
    written_work_1 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    written_work_2 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    written_work_3 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    written_work = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    written_work_highest = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    # Performance Tasks (50%): three component scores summed into performance_task.
    performance_task_1 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    performance_task_2 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    performance_task_3 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    performance_task = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    performance_task_highest = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    # Quarterly Assessment (30%): three component scores summed into assessment.
    assessment_1 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    assessment_2 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    assessment_3 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    assessment = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    assessment_highest = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    
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
        return self.written_work_ps * WW_WEIGHT

    @property
    def performance_task_ws(self):
        return self.performance_task_ps * PT_WEIGHT

    @property
    def assessment_ws(self):
        return self.assessment_ps * AS_WEIGHT

    def compute_quarter_grade(self):
        self.quarter_grade = weighted_quarter_grade(
            self.written_work, self.written_work_highest,
            self.performance_task, self.performance_task_highest,
            self.assessment, self.assessment_highest,
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
