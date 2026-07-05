from django.contrib.auth.decorators import user_passes_test, login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """
    Decorator that restricts view access to users with one of the given roles.
    
    Usage:
        @role_required('admin')
        def my_view(request): ...
        
        @role_required('admin', 'registrar')
        def my_view(request): ...
    """
    def check_role(user):
        if not user.is_authenticated:
            return False
        return any(
            getattr(user, f'is_{role}', False) for role in roles
        )
    
    return user_passes_test(check_role, login_url='accounts:login')


def admin_required(view_func):
    """Shortcut decorator for admin-only views."""
    return role_required('admin')(view_func)


def registrar_or_admin_required(view_func):
    """Shortcut for registrar/admin views."""
    return role_required('registrar', 'admin')(view_func)


def teacher_or_admin_required(view_func):
    """Shortcut for teacher/admin views."""
    return role_required('teacher', 'admin')(view_func)


def principal_or_admin_required(view_func):
    """Shortcut for principal/admin views."""
    return role_required('principal', 'admin')(view_func)
