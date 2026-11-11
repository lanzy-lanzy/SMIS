from django import forms
from .models import Student


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
