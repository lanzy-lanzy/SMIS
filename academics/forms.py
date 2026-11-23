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
    days = forms.MultipleChoiceField(
        choices=TeacherAssignment.DAY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Class Days',
    )

    class Meta:
        model = TeacherAssignment
        fields = ('teacher', 'subject', 'section', 'school_year', 'days', 'start_time', 'end_time', 'room')
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'end_time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'room': forms.TextInput(attrs={'placeholder': 'e.g. Room 101, Science Lab'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['teacher'].label_from_instance = lambda user: user.get_full_name() or user.username
        self.fields['section'].queryset = Section.objects.select_related('grade_level', 'school_year')
        self.fields['section'].label_from_instance = lambda section: f'{section} ({section.school_year})'
        self.fields['start_time'].label = 'Start Time'
        self.fields['end_time'].label = 'End Time'
        self.fields['room'].label = 'Room (Optional)'
        if self.instance and self.instance.pk and not self.is_bound:
            self.initial['days'] = self.instance.day_list
        if not self.is_bound and not (self.instance and self.instance.pk):
            self.initial.setdefault('school_year', SchoolYear.objects.filter(is_current=True).first())
        for name, field in self.fields.items():
            if name == 'days':
                continue
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent dark:bg-gray-700 dark:text-white'
            })

    def clean_days(self):
        selected = self.cleaned_data.get('days') or []
        ordered = [code for code in TeacherAssignment.DAY_ORDER if code in selected]
        return ','.join(ordered)

    def clean(self):
        cleaned = super().clean()
        section = cleaned.get('section')
        year = cleaned.get('school_year')
        if section and year and section.school_year_id != year.pk:
            self.add_error('section', 'Select a section from the selected school year.')
        self.add_occupied_error()
        self._validate_schedule(cleaned)
        return cleaned

    def _validate_schedule(self, cleaned):
        days_csv = cleaned.get('days') or ''
        selected_days = {d for d in days_csv.split(',') if d}
        start_time = cleaned.get('start_time')
        end_time = cleaned.get('end_time')

        if not selected_days and not start_time and not end_time:
            return

        if not selected_days:
            self.add_error('days', 'Select at least one class day when setting a schedule time.')
        if not start_time:
            self.add_error('start_time', 'Enter a start time for the class schedule.')
        if not end_time:
            self.add_error('end_time', 'Enter an end time for the class schedule.')
        if not (selected_days and start_time and end_time):
            return

        if end_time <= start_time:
            self.add_error('end_time', 'End time must be later than start time.')
            return

        teacher = cleaned.get('teacher')
        section = cleaned.get('section')
        year = cleaned.get('school_year')
        if not year:
            return

        overlapping = (
            TeacherAssignment.objects.filter(
                school_year=year,
                start_time__lt=end_time,
                end_time__gt=start_time,
            )
            .exclude(pk=self.instance.pk)
            .exclude(days='')
            .select_related('teacher', 'subject', 'section', 'section__grade_level')
        )

        if teacher:
            for existing in overlapping.filter(teacher=teacher):
                shared = [d for d in TeacherAssignment.DAY_ORDER if d in selected_days and d in existing.day_list]
                if shared:
                    teacher_name = teacher.get_full_name() or teacher.username
                    self.add_error(
                        'start_time',
                        f"Teacher schedule conflict: {teacher_name} already handles {existing.subject.name} "
                        f"for {existing.section} on {', '.join(shared)} ({existing.time_range}).",
                    )
                    break

        if section:
            for existing in overlapping.filter(section=section):
                shared = [d for d in TeacherAssignment.DAY_ORDER if d in selected_days and d in existing.day_list]
                if shared:
                    other_teacher = existing.teacher.get_full_name() or existing.teacher.username
                    self.add_error(
                        'section',
                        f"Section schedule conflict: {section} already has {existing.subject.name} "
                        f"with {other_teacher} on {', '.join(shared)} ({existing.time_range}).",
                    )
                    break

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
