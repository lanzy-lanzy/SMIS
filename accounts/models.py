from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'System Administrator'),
        ('registrar', 'Registrar'),
        ('teacher', 'Teacher'),
        ('principal', 'Principal/Academic Head'),
        ('student', 'Student/Parent'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='teacher')
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_registrar(self):
        return self.role == 'registrar'

    @property
    def is_teacher(self):
        return self.role == 'teacher'

    @property
    def is_principal(self):
        return self.role == 'principal'

    @property
    def is_student_user(self):
        return self.role == 'student'


class AuditLog(models.Model):
    ACTION_CHOICES = (
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('grade_encode', 'Grade Encoded'),
        ('grade_update', 'Grade Updated'),
        ('grade_submit', 'Grade Submitted'),
        ('grade_validate', 'Grade Validated'),
        ('grade_return', 'Grade Returned'),
        ('form137_generate', 'Form 137 Generated'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} - {self.get_action_display()} - {self.model_name}"
