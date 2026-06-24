from django.db import models
from django.conf import settings


class Form137Record(models.Model):
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='form137_records')
    school_year = models.ForeignKey('academics.SchoolYear', on_delete=models.CASCADE, related_name='form137_records')
    grade_level = models.ForeignKey('academics.GradeLevel', on_delete=models.CASCADE, related_name='form137_records')
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    date_generated = models.DateTimeField(auto_now_add=True)
    is_printed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date_generated']
        unique_together = ('student', 'school_year', 'grade_level')

    def __str__(self):
        return f"Form 137 - {self.student} - {self.school_year}"
