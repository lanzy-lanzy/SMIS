from django.contrib import admin
from .models import Grade, GradeSubmission, GradeValidation


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'grading_period', 'quarter_grade', 'status')
    list_filter = ('status', 'grading_period', 'school_year')


@admin.register(GradeSubmission)
class GradeSubmissionAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'subject', 'section', 'status', 'submitted_at')
    list_filter = ('status',)


@admin.register(GradeValidation)
class GradeValidationAdmin(admin.ModelAdmin):
    list_display = ('submission', 'validated_by', 'status', 'validated_at')
