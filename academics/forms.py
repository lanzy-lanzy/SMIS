from django import forms
from accounts.models import User
from .models import SchoolYear, GradeLevel, Section, Subject, TeacherAssignment, GradingPeriod


class SchoolYearForm(forms.ModelForm):
    class Meta:
        model = SchoolYear
        fields = ('name', 'is_current')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent dark:bg-gray-700 dark:text-white'
            })


class GradeLevelForm(forms.ModelForm):
    class Meta:
        model = GradeLevel
        fields = ('name', 'level', 'description')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent dark:bg-gray-700 dark:text-white'
            })


class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ('name', 'grade_level', 'school_year', 'adviser')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent dark:bg-gray-700 dark:text-white'
            })


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ('name', 'code', 'description', 'grade_level', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent dark:bg-gray-700 dark:text-white'
            })


class TeacherAssignmentForm(forms.ModelForm):
    class Meta:
        model = TeacherAssignment
        fields = ('teacher', 'subject', 'section', 'school_year')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['teacher'].label_from_instance = lambda user: user.get_full_name() or user.username
        self.fields['section'].queryset = Section.objects.select_related('grade_level', 'school_year')
        self.fields['section'].label_from_instance = lambda section: f'{section} ({section.school_year})'
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent dark:bg-gray-700 dark:text-white'
            })

    def clean(self):
        cleaned = super().clean()
        section = cleaned.get('section')
        year = cleaned.get('school_year')
        if section and year and section.school_year_id != year.pk:
            self.add_error('section', 'Select a section from the selected school year.')
        self.add_occupied_error()
        return cleaned

    def add_occupied_error(self):
        subject = self.cleaned_data.get('subject')
        section = self.cleaned_data.get('section')
        year = self.cleaned_data.get('school_year')
        if subject and section and year:
            occupied = TeacherAssignment.objects.filter(
                subject=subject, section=section, school_year=year,
            ).exclude(pk=self.instance.pk).select_related('teacher', 'subject', 'section__grade_level').first()
            if occupied:
                self.add_error('subject', _occupied_assignment_message(occupied))
                return True
        return False


class BulkTeacherAssignmentForm(forms.Form):
    teacher = forms.ModelChoiceField(queryset=User.objects.filter(role='teacher', is_active=True))
    school_year = forms.ModelChoiceField(queryset=SchoolYear.objects.order_by('-is_current', '-name'))
    subjects = forms.ModelMultipleChoiceField(queryset=Subject.objects.filter(is_active=True).select_related('grade_level'))
    sections = forms.ModelMultipleChoiceField(queryset=Section.objects.select_related('grade_level', 'school_year'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault('school_year', SchoolYear.objects.filter(is_current=True).first())
        self.fields['teacher'].label_from_instance = lambda user: user.get_full_name() or user.username
        self.fields['subjects'].label_from_instance = lambda subject: f'{subject} ({subject.grade_level})'
        self.fields['sections'].label_from_instance = lambda section: f'{section} ({section.school_year})'
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'w-full rounded-lg border px-3 py-2'
            if name in ('subjects', 'sections'):
                field.widget.attrs['size'] = 5

    def clean(self):
        cleaned = super().clean()
        sections = cleaned.get('sections')
        year = cleaned.get('school_year')
        if sections is not None and year and sections.exclude(school_year=year).exists():
            self.add_error('sections', 'Select only sections from the selected school year.')
        self.add_occupied_errors()
        return cleaned

    def add_occupied_errors(self):
        subjects = self.cleaned_data.get('subjects')
        sections = self.cleaned_data.get('sections')
        year = self.cleaned_data.get('school_year')
        if subjects is None or sections is None or not year:
            return False
        occupied = list(TeacherAssignment.objects.filter(
            subject__in=subjects, section__in=sections, school_year=year,
        ).select_related('teacher', 'subject', 'section__grade_level').order_by('section__name', 'subject__name'))
        for assignment in occupied:
            self.add_error(None, _occupied_assignment_message(assignment))
        return bool(occupied)


def _occupied_assignment_message(assignment):
    teacher = assignment.teacher.get_full_name() or assignment.teacher.username
    return f'{assignment.subject.name} in {assignment.section} is already assigned to {teacher}.'


class GradingPeriodForm(forms.ModelForm):
    class Meta:
        model = GradingPeriod
        fields = ('name', 'order', 'start_month', 'end_month', 'school_year', 'is_current', 'is_submissions_open')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent dark:bg-gray-700 dark:text-white'
            })
