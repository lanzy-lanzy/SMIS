from django.db import models
from django.conf import settings


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
    
    written_work = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    performance_task = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    assessment = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
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

    def compute_quarter_grade(self):
        self.quarter_grade = (self.written_work + self.performance_task + self.assessment) / 3
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
        ('pending', 'Pending'),
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
