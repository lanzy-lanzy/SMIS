from django.contrib import admin
from .models import SchoolYear, GradeLevel, Section, Subject, TeacherAssignment, GradingPeriod


@admin.register(SchoolYear)
class SchoolYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_current')


@admin.register(GradeLevel)
class GradeLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'level')


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'grade_level', 'school_year', 'adviser')
    list_filter = ('grade_level', 'school_year')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'grade_level')
    list_filter = ('grade_level',)


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'subject', 'section', 'school_year')


@admin.register(GradingPeriod)
class GradingPeriodAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'school_year', 'is_current')
