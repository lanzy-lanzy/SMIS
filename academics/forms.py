from datetime import time as dt_time
from django import forms
from accounts.models import User
from .models import (
    SchoolYear, GradeLevel, Section, Subject, TeacherAssignment, AssignmentSchedule, GradingPeriod,
)


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


def _parse_time_str(value):
    value = (value or '').strip()
    if not value:
        return None
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            parts = [int(p) for p in value.split(':')]
            if len(parts) == 2:
                return dt_time(parts[0], parts[1])
            if len(parts) == 3:
                return dt_time(parts[0], parts[1], parts[2])
        except (ValueError, TypeError):
            continue
    return None


def _format_time_12h(value):
    return value.strftime('%I:%M %p').lstrip('0')


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
        if not self.is_bound and not (self.instance and self.instance.pk):
            self.initial.setdefault('school_year', SchoolYear.objects.filter(is_current=True).first())
        for name, field in self.fields.items():
            if name == 'days':
                continue
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent dark:bg-gray-700 dark:text-white'
            })

        self.parsed_slots = []
        self.schedule_slots = self._initial_schedule_slots()

    def _initial_schedule_slots(self):
        if self.is_bound:
            slot_days = self.data.getlist('slot_day')
            slot_starts = self.data.getlist('slot_start')
            slot_ends = self.data.getlist('slot_end')
            slot_rooms = self.data.getlist('slot_room')
            count = max(len(slot_days), len(slot_starts), len(slot_ends), len(slot_rooms))
            if count > 0:
                return [
                    {
                        'day': slot_days[i] if i < len(slot_days) else '',
                        'start_time': slot_starts[i] if i < len(slot_starts) else '',
                        'end_time': slot_ends[i] if i < len(slot_ends) else '',
                        'room': slot_rooms[i] if i < len(slot_rooms) else '',
                    }
                    for i in range(count)
                ]
            return []

        if self.instance and self.instance.pk:
            existing = list(self.instance.schedules.all())
            if existing:
                day_rank = {code: idx for idx, code in enumerate(TeacherAssignment.DAY_ORDER)}
                existing.sort(key=lambda s: (day_rank.get(s.day, 99), s.start_time))
                return [
                    {
                        'day': s.day,
                        'start_time': s.start_time.strftime('%H:%M'),
                        'end_time': s.end_time.strftime('%H:%M'),
                        'room': s.room or '',
                    }
                    for s in existing
                ]
            if self.instance.day_list and self.instance.start_time and self.instance.end_time:
                return [
                    {
                        'day': d,
                        'start_time': self.instance.start_time.strftime('%H:%M'),
                        'end_time': self.instance.end_time.strftime('%H:%M'),
                        'room': self.instance.room or '',
                    }
                    for d in self.instance.day_list
                ]
        return []

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
        self._validate_schedule_slots(cleaned)
        return cleaned

    def _collect_submitted_slots(self, cleaned):
        """Support both multi-row per-day slots (slot_day/slot_start/slot_end/slot_room)
        and legacy single-slot fields (days/start_time/end_time/room)."""
        has_slot_inputs = any(
            k in self.data for k in ('slot_day', 'slot_start', 'slot_end', 'slot_room')
        )
        valid_day_codes = set(TeacherAssignment.DAY_ORDER)
        slots = []

        if has_slot_inputs:
            slot_days = self.data.getlist('slot_day')
            slot_starts = self.data.getlist('slot_start')
            slot_ends = self.data.getlist('slot_end')
            slot_rooms = self.data.getlist('slot_room')
            count = max(len(slot_days), len(slot_starts), len(slot_ends), len(slot_rooms))

            for idx in range(count):
                day = (slot_days[idx] if idx < len(slot_days) else '').strip()
                raw_start = (slot_starts[idx] if idx < len(slot_starts) else '').strip()
                raw_end = (slot_ends[idx] if idx < len(slot_ends) else '').strip()
                room = (slot_rooms[idx] if idx < len(slot_rooms) else '').strip()

                if not (day or raw_start or raw_end or room):
                    continue

                row_label = f"Schedule row #{idx + 1}"
                start_t = _parse_time_str(raw_start)
                end_t = _parse_time_str(raw_end)

                if day not in valid_day_codes:
                    self.add_error(None, f"{row_label}: Select a valid class day.")
                    continue
                if not start_t:
                    self.add_error(None, f"{row_label}: Enter a valid start time.")
                    continue
                if not end_t:
                    self.add_error(None, f"{row_label}: Enter a valid end time.")
                    continue
                if end_t <= start_t:
                    self.add_error(None, f"{row_label} ({day}): End time must be later than start time.")
                    continue

                slots.append({
                    'day': day,
                    'start_time': start_t,
                    'end_time': end_t,
                    'room': room,
                })
            return slots

        # Legacy single-slot fallback (e.g., older tests or direct form posts)
        days_csv = cleaned.get('days') or ''
        selected_days = [d for d in TeacherAssignment.DAY_ORDER if d in {x for x in days_csv.split(',') if x}]
        start_t = cleaned.get('start_time')
        end_t = cleaned.get('end_time')
        room = (cleaned.get('room') or '').strip()

        if not selected_days and not start_t and not end_t:
            return []
        if not selected_days:
            self.add_error('days', 'Select at least one class day when setting a schedule time.')
        if not start_t:
            self.add_error('start_time', 'Enter a start time for the class schedule.')
        if not end_t:
            self.add_error('end_time', 'Enter an end time for the class schedule.')
        if not (selected_days and start_t and end_t):
            return []
        if end_t <= start_t:
            self.add_error('end_time', 'End time must be later than start time.')
            return []

        return [
            {'day': d, 'start_time': start_t, 'end_time': end_t, 'room': room}
            for d in selected_days
        ]

    def _validate_schedule_slots(self, cleaned):
        slots = self._collect_submitted_slots(cleaned)
        self.parsed_slots = slots
        if not slots:
            return

        day_labels = dict(TeacherAssignment.DAY_CHOICES)

        # 1. Check intra-form overlapping slots on the same day
        by_day = {}
        for slot in slots:
            by_day.setdefault(slot['day'], []).append(slot)
        for day, day_slots in by_day.items():
            ordered = sorted(day_slots, key=lambda s: (s['start_time'], s['end_time']))
            for first, second in zip(ordered, ordered[1:]):
                if first['end_time'] > second['start_time']:
                    self.add_error(
                        None,
                        f"Overlapping schedule on {day_labels.get(day, day)}: "
                        f"{_format_time_12h(first['start_time'])} – {_format_time_12h(first['end_time'])} "
                        f"conflicts with {_format_time_12h(second['start_time'])} – {_format_time_12h(second['end_time'])}.",
                    )

        teacher = cleaned.get('teacher')
        section = cleaned.get('section')
        year = cleaned.get('school_year')
        if not year:
            return

        # 2. Check conflicts against existing AssignmentSchedule rows in the same school year
        base_qs = (
            AssignmentSchedule.objects.filter(assignment__school_year=year)
            .exclude(assignment_id=self.instance.pk)
            .select_related('assignment__teacher', 'assignment__subject', 'assignment__section', 'assignment__section__grade_level')
        )

        reported_teacher = set()
        reported_section = set()

        for slot in slots:
            day = slot['day']
            start_t = slot['start_time']
            end_t = slot['end_time']
            day_name = day_labels.get(day, day)

            day_overlaps = base_qs.filter(
                day=day,
                start_time__lt=end_t,
                end_time__gt=start_t,
            )

            if teacher:
                for existing in day_overlaps.filter(assignment__teacher=teacher):
                    key = (day, existing.pk)
                    if key not in reported_teacher:
                        reported_teacher.add(key)
                        teacher_name = teacher.get_full_name() or teacher.username
                        self.add_error(
                            None,
                            f"Teacher schedule conflict on {day_name}: {teacher_name} already handles "
                            f"{existing.assignment.subject.name} for {existing.assignment.section} ({existing.time_range}).",
                        )

            if section:
                for existing in day_overlaps.filter(assignment__section=section):
                    key = (day, existing.pk)
                    if key not in reported_section:
                        reported_section.add(key)
                        other_teacher = existing.assignment.teacher.get_full_name() or existing.assignment.teacher.username
                        self.add_error(
                            None,
                            f"Section schedule conflict on {day_name}: {section} already has "
                            f"{existing.assignment.subject.name} with {other_teacher} ({existing.time_range}).",
                        )

    def save(self, commit=True):
        assignment = super().save(commit=False)
        if self.parsed_slots:
            ordered_days = [
                d for d in TeacherAssignment.DAY_ORDER
                if d in {s['day'] for s in self.parsed_slots}
            ]
            assignment.days = ','.join(ordered_days)
            assignment.start_time = self.parsed_slots[0]['start_time']
            assignment.end_time = self.parsed_slots[0]['end_time']
            assignment.room = self.parsed_slots[0]['room']
        else:
            assignment.days = ''
            assignment.start_time = None
            assignment.end_time = None
            assignment.room = ''

        if commit:
            assignment.save()
            assignment.schedules.all().delete()
            if self.parsed_slots:
                AssignmentSchedule.objects.bulk_create([
                    AssignmentSchedule(
                        assignment=assignment,
                        day=s['day'],
                        start_time=s['start_time'],
                        end_time=s['end_time'],
                        room=s['room'],
                    )
                    for s in self.parsed_slots
                ])
        return assignment

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
