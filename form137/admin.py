from django.contrib import admin
from .models import Form137Record


@admin.register(Form137Record)
class Form137RecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'school_year', 'grade_level', 'generated_by', 'date_generated', 'is_printed')
    list_filter = ('school_year', 'grade_level')
