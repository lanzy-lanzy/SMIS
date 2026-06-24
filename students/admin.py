from django.contrib import admin
from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('lrn', 'first_name', 'last_name', 'sex', 'grade_level', 'section', 'status')
    list_filter = ('sex', 'status', 'grade_level', 'school_year')
    search_fields = ('lrn', 'first_name', 'last_name')
