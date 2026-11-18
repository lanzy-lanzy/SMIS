from django import forms
from .models import Student
from .promotion import promotion_sections


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ('lrn', 'first_name', 'middle_name', 'last_name', 'suffix', 'sex', 
                  'birthdate', 'birthplace', 'address', 'phone',
                  'parent_name', 'parent_phone', 'parent_address',
                  'grade_level', 'section', 'school_year', 'status')
        widgets = {
            'birthdate': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'sex' and field_name != 'status':
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent dark:bg-gray-700 dark:text-white'
                })
            else:
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent dark:bg-gray-700 dark:text-white'
                })

        # The address fields are TextAreas, which default to a ten-row box and a
        # draggable resize handle. Pin them to one line so they match every other
        # field's height, and drop the handle so the box cannot be stretched.
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['rows'] = 1
                field.widget.attrs['class'] += ' resize-none'

        # Status describes the pupil's enrolment (Transferred In / Out,
        # Balik-Aral, Repeater), so it is chosen explicitly. A record saved
        # under the old status set keeps its value when edited.
        status_field = self.fields['status']
        status_field.required = True
        options = [('', 'Select status')] + list(Student.STATUS_CHOICES)
        current = self.instance.status
        if self.instance.pk and current and current not in dict(Student.STATUS_CHOICES):
            options.append((current, self.instance.get_status_display()))
        status_field.choices = options

    def clean_grade_level(self):
        level = self.cleaned_data['grade_level']
        current_level = self.instance.grade_level
        if self.instance.pk and current_level and level and level.level > current_level.level:
            raise forms.ValidationError('Use Promote on the student profile to move to a higher grade.')
        return level


class StudentPromotionForm(forms.Form):
    section = forms.ModelChoiceField(queryset=None, label='Destination section')
    source_year = forms.IntegerField(widget=forms.HiddenInput)
    source_grade = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, student, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['section'].queryset = promotion_sections(student)
        self.fields['section'].label_from_instance = (
            lambda section: f'{section} ({section.school_year})'
        )
        self.initial.update(source_year=student.school_year_id, source_grade=student.grade_level_id)
