from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import User, AuditLog
from .forms import (
    LoginForm,
    UserCreationFormAdmin,
    UserEditForm,
    ProfileForm,
    PasswordChangeForm,
)
from .decorators import admin_required


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:index")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            AuditLog.objects.create(
                user=user,
                action="login",
                model_name="User",
                object_id=str(user.id),
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            messages.success(request, f"Welcome back, {user.first_name}!")
            return redirect("dashboard:index")
    else:
        form = LoginForm()
    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_view(request):
    AuditLog.objects.create(
        user=request.user,
        action="logout",
        model_name="User",
        object_id=str(request.user.id),
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("accounts:login")


@admin_required
def user_list(request):
    query = request.GET.get("q", "")
    role_filter = request.GET.get("role", "")

    users = User.objects.all()

    stats = {
        'total': users.count(),
        'active': users.filter(is_active=True).count(),
        'inactive': users.filter(is_active=False).count(),
        'admins': users.filter(role='admin', is_active=True).count(),
        'teachers': users.filter(role='teacher', is_active=True).count(),
    }

    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )

    if role_filter:
        users = users.filter(role=role_filter)

    paginator = Paginator(users, 12)
    page = request.GET.get("page", 1)
    users = paginator.get_page(page)

    if request.headers.get("HX-Request"):
        return render(request, "accounts/partials/user_table.html", {"users": users})

    return render(
        request,
        "accounts/user_list.html",
        {
            "users": users,
            "query": query,
            "role_filter": role_filter,
            "roles": User.ROLE_CHOICES,
            "stats": stats,
        },
    )


@admin_required
def user_create(request):
    if request.method == "POST":
        form = UserCreationFormAdmin(request.POST)
        if form.is_valid():
            user = form.save()
            AuditLog.objects.create(
                user=request.user,
                action="create",
                model_name="User",
                object_id=str(user.id),
                description=f"Created user {user.username}",
            )
            messages.success(request, f"User {user.username} created successfully.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#user-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("accounts:user_list")
    else:
        form = UserCreationFormAdmin()

    if request.headers.get("HX-Request"):
        return render(
            request,
            "accounts/partials/user_form.html",
            {"form": form, "title": "Create User"},
        )
    return render(
        request, "accounts/user_form.html", {"form": form, "title": "Create User"}
    )


@admin_required
def user_edit(request, pk):
    user_obj = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        form = UserEditForm(request.POST, instance=user_obj)
        if form.is_valid():
            if user_obj.pk == request.user.pk:
                if form.cleaned_data.get("role") != request.user.role:
                    messages.error(request, "You cannot change your own role.")
                    if request.headers.get("HX-Request"):
                        return HttpResponse(
                            "<script>closeModal();</script>",
                            headers={"HX-Trigger": "closeModal"},
                        )
                    return redirect("accounts:user_list")
                if not form.cleaned_data.get("is_active"):
                    messages.error(request, "You cannot deactivate your own account.")
                    if request.headers.get("HX-Request"):
                        return HttpResponse(
                            "<script>closeModal();</script>",
                            headers={"HX-Trigger": "closeModal"},
                        )
                    return redirect("accounts:user_list")
            if (
                user_obj.is_admin
                and form.cleaned_data.get("role") != "admin"
                and User.objects.filter(role="admin", is_active=True).count() <= 1
            ):
                messages.error(request, "Cannot demote the last admin user.")
                if request.headers.get("HX-Request"):
                    return HttpResponse(
                        "<script>closeModal();</script>",
                        headers={"HX-Trigger": "closeModal"},
                    )
                return redirect("accounts:user_list")
            password_changed = bool(form.cleaned_data.get("new_password1"))
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action="update",
                model_name="User",
                object_id=str(user_obj.id),
                description=(
                    f"Reset password for user {user_obj.username}"
                    if password_changed
                    else f"Updated user {user_obj.username}"
                ),
            )
            if password_changed:
                messages.success(
                    request,
                    f"User {user_obj.username} updated and password has been reset.",
                )
            else:
                messages.success(request, f"User {user_obj.username} updated successfully.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#user-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("accounts:user_list")
    else:
        form = UserEditForm(instance=user_obj)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "accounts/partials/user_form.html",
            {"form": form, "user_obj": user_obj, "title": "Edit User"},
        )
    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "user_obj": user_obj, "title": "Edit User"},
    )


@admin_required
def user_delete(request, pk):
    user_obj = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        if user_obj.pk == request.user.pk:
            messages.error(request, "You cannot delete your own account.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    "<script>closeModal();</script>",
                    headers={"HX-Trigger": "closeModal"},
                )
            return redirect("accounts:user_list")
        if (
            user_obj.is_admin
            and User.objects.filter(role="admin", is_active=True).count() <= 1
        ):
            messages.error(request, "Cannot delete the last admin user.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    "<script>closeModal();</script>",
                    headers={"HX-Trigger": "closeModal"},
                )
            return redirect("accounts:user_list")
        username = user_obj.username
        user_obj.delete()
        AuditLog.objects.create(
            user=request.user,
            action="delete",
            model_name="User",
            object_id=str(pk),
            description=f"Deleted user {username}",
        )
        messages.success(request, f"User {username} deleted successfully.")
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<script>closeModal(); htmx.trigger("#user-table", "refresh");</script>',
                headers={"HX-Trigger": "closeModal,refreshTable"},
            )
        return redirect("accounts:user_list")

    if request.headers.get("HX-Request"):
        return render(
            request,
            "accounts/partials/user_confirm_delete.html",
            {"user_obj": user_obj, "title": "User"},
        )
    return render(request, "accounts/user_confirm_delete.html", {"user_obj": user_obj})


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def change_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.POST)
        if form.is_valid():
            if not request.user.check_password(form.cleaned_data["old_password"]):
                messages.error(request, "Current password is incorrect.")
            else:
                try:
                    validate_password(form.cleaned_data["new_password1"], request.user)
                    if (
                        form.cleaned_data["new_password1"]
                        != form.cleaned_data["new_password2"]
                    ):
                        messages.error(request, "New passwords do not match.")
                    else:
                        request.user.set_password(form.cleaned_data["new_password1"])
                        request.user.save()
                        update_session_auth_hash(request, request.user)
                        messages.success(request, "Password changed successfully.")
                        return redirect("accounts:profile")
                except Exception as e:
                    messages.error(request, str(e))
    else:
        form = PasswordChangeForm()
    return render(request, "accounts/change_password.html", {"form": form})


@admin_required
def audit_log_list(request):
    """View audit logs (admin only)."""
    action_filter = request.GET.get("action", "")
    model_filter = request.GET.get("model", "")
    query = request.GET.get("q", "")
    
    logs = AuditLog.objects.select_related("user").all()
    
    if action_filter:
        logs = logs.filter(action=action_filter)
    if model_filter:
        logs = logs.filter(model_name__icontains=model_filter)
    if query:
        logs = logs.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(description__icontains=query)
            | Q(model_name__icontains=query)
        )
    
    paginator = Paginator(logs, 30)
    page = request.GET.get("page", 1)
    logs = paginator.get_page(page)
    
    actions = AuditLog.ACTION_CHOICES
    
    return render(request, "accounts/audit_log_list.html", {
        "logs": logs,
        "actions": actions,
        "action_filter": action_filter,
        "model_filter": model_filter,
        "query": query,
    })
