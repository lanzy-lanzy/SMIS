from django.db import models
from accounts.models import User

# Statuses that count as currently enrolled in this school. The legacy
# "active" value is included so records saved before the status set changed
# still count as enrolled.
ENROLLED_STATUSES = ('active', 'transferred_in', 'balik_aral', 'repeater')


class Student(models.Model):
    SEX_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
    )
    
    STATUS_CHOICES = (
        ('transferred_in', 'Transferred In'),
        ('transferred_out', 'Transferred Out'),
        ('balik_aral', 'Balik-Aral'),
        ('repeater', 'Repeater'),
    )

    # Values from the previous status set. Kept in the field choices so older
    # records still display and validate; they are no longer offered when
    # adding or editing a student.
    LEGACY_STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('transferred', 'Transferred'),
        ('dropped', 'Dropped'),
    )

    lrn = models.CharField(max_length=20, unique=True, verbose_name='Learner Reference Number')
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    suffix = models.CharField(max_length=20, blank=True)
    sex = models.CharField(max_length=1, choices=SEX_CHOICES)
    birthdate = models.DateField()
    birthplace = models.CharField(max_length=200, blank=True)
    address = models.TextField()
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    parent_name = models.CharField(max_length=200)
    parent_phone = models.CharField(max_length=20, blank=True)
    parent_address = models.TextField(blank=True)
    
    grade_level = models.ForeignKey('academics.GradeLevel', on_delete=models.SET_NULL, null=True)
    section = models.ForeignKey('academics.Section', on_delete=models.SET_NULL, null=True, blank=True)
    school_year = models.ForeignKey('academics.SchoolYear', on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES + LEGACY_STATUS_CHOICES, blank=True, default='')
    
    user_account = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_profile')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.last_name}, {self.first_name} ({self.lrn})"

    @property
    def full_name(self):
        name = f"{self.first_name}"
        if self.middle_name:
            name += f" {self.middle_name}"
        name += f" {self.last_name}"
        if self.suffix:
            name += f" {self.suffix}"
        return name
