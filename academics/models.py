from django.db import models
from accounts.models import User


class SchoolYear(models.Model):
    name = models.CharField(max_length=20)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_current:
            SchoolYear.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)


class GradeLevel(models.Model):
    name = models.CharField(max_length=50)
    level = models.IntegerField()
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['level']

    def __str__(self):
        return self.name


class Section(models.Model):
    name = models.CharField(max_length=50)
    grade_level = models.ForeignKey(GradeLevel, on_delete=models.CASCADE, related_name='sections')
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE, related_name='sections')
    adviser = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='advised_sections')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['grade_level', 'name']
        unique_together = ('name', 'grade_level', 'school_year')

    def __str__(self):
        return f"{self.grade_level} - {self.name}"


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    grade_level = models.ForeignKey(GradeLevel, on_delete=models.CASCADE, related_name='subjects')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['grade_level', 'name']

    def __str__(self):
        return f"{self.code} - {self.name}"


class TeacherAssignment(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assignments')
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='assignments')
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE, related_name='assignments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('teacher', 'subject', 'section', 'school_year')

    def __str__(self):
        return f"{self.teacher.get_full_name()} - {self.subject} - {self.section}"


class GradingPeriod(models.Model):
    PERIOD_CHOICES = (
        (1, 'First Quarter'),
        (2, 'Second Quarter'),
        (3, 'Third Quarter'),
        (4, 'Fourth Quarter'),
    )
    
    name = models.CharField(max_length=50)
    order = models.IntegerField(choices=PERIOD_CHOICES)
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE, related_name='grading_periods')
    is_current = models.BooleanField(default=False)
    is_submissions_open = models.BooleanField(default=False, verbose_name="Open for Grade Submissions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        unique_together = ('order', 'school_year')

    def __str__(self):
        return f"{self.name} - {self.school_year}"

    def save(self, *args, **kwargs):
        if self.is_current:
            GradingPeriod.objects.filter(
                is_current=True, school_year=self.school_year
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)
