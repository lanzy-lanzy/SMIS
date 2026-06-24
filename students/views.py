from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Student
from .forms import StudentForm
from accounts.models import AuditLog
from grades.models import Grade


@login_required
def student_list(request):
    if not (
        request.user.is_admin or request.user.is_registrar or request.user.is_teacher
    ):
        messages.error(request, "Access denied.")
        return redirect("dashboard:index")

    query = request.GET.get("q", "")
    grade_filter = request.GET.get("grade", "")
    section_filter = request.GET.get("section", "")
    status_filter = request.GET.get("status", "")

    students = Student.objects.select_related(
        "grade_level", "section", "school_year"
    ).all()

    if query:
        students = students.filter(
            Q(lrn__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(middle_name__icontains=query)
        )

    if grade_filter:
        students = students.filter(grade_level_id=grade_filter)

    if section_filter:
        students = students.filter(section_id=section_filter)

    if status_filter:
        students = students.filter(status=status_filter)

    paginator = Paginator(students, 20)
    page = request.GET.get("page", 1)
    students = paginator.get_page(page)

    from academics.models import GradeLevel, Section

    grade_levels = GradeLevel.objects.all()
    sections = Section.objects.all()

    if request.headers.get("HX-Request"):
        return render(
            request, "students/partials/student_table.html", {"students": students}
        )

    return render(
        request,
        "students/student_list.html",
        {
            "students": students,
            "query": query,
            "grade_filter": grade_filter,
            "section_filter": section_filter,
            "status_filter": status_filter,
            "grade_levels": grade_levels,
            "sections": sections,
            "status_choices": Student.STATUS_CHOICES,
        },
    )


@login_required
def student_create(request):
    if not (request.user.is_admin or request.user.is_registrar):
        messages.error(request, "Access denied.")
        return redirect("dashboard:index")

    from academics.models import GradeLevel, Section, SchoolYear

    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            AuditLog.objects.create(
                user=request.user,
                action="create",
                model_name="Student",
                object_id=str(student.id),
                description=f"Created student {student.full_name}",
            )
            messages.success(
                request, f"Student {student.full_name} added successfully."
            )
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#student-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("students:student_list")
    else:
        form = StudentForm()

    context = {
        "form": form,
        "title": "Add Student",
        "grade_levels": GradeLevel.objects.all(),
        "sections": Section.objects.all(),
        "school_years": SchoolYear.objects.all(),
    }
    if request.headers.get("HX-Request"):
        return render(request, "students/partials/student_form.html", context)
    return render(request, "students/student_form.html", context)


@login_required
def student_edit(request, pk):
    if not (request.user.is_admin or request.user.is_registrar):
        messages.error(request, "Access denied.")
        return redirect("dashboard:index")

    student = get_object_or_404(Student, pk=pk)

    from academics.models import GradeLevel, Section, SchoolYear

    if request.method == "POST":
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action="update",
                model_name="Student",
                object_id=str(student.id),
                description=f"Updated student {student.full_name}",
            )
            messages.success(
                request, f"Student {student.full_name} updated successfully."
            )
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#student-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("students:student_list")
    else:
        form = StudentForm(instance=student)

    context = {
        "form": form,
        "student": student,
        "title": "Edit Student",
        "grade_levels": GradeLevel.objects.all(),
        "sections": Section.objects.all(),
        "school_years": SchoolYear.objects.all(),
    }
    if request.headers.get("HX-Request"):
        return render(request, "students/partials/student_form.html", context)
    return render(request, "students/student_form.html", context)


@login_required
def student_delete(request, pk):
    if not request.user.is_admin:
        messages.error(request, "Access denied.")
        return redirect("dashboard:index")

    student = get_object_or_404(Student, pk=pk)

    if request.method == "POST":
        full_name = student.full_name
        has_validated = Grade.objects.filter(
            student=student, status="validated"
        ).exists()
        if has_validated:
            messages.warning(
                request,
                f"Student {full_name} has validated grades. Deleting will remove all grade records.",
            )
        student.delete()
        AuditLog.objects.create(
            user=request.user,
            action="delete",
            model_name="Student",
            object_id=str(pk),
            description=f"Deleted student {full_name}",
        )
        messages.success(request, f"Student {full_name} deleted successfully.")
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<script>closeModal(); htmx.trigger("#student-table", "refresh");</script>',
                headers={"HX-Trigger": "closeModal,refreshTable"},
            )
        return redirect("students:student_list")

    if request.headers.get("HX-Request"):
        return render(
            request,
            "students/partials/student_confirm_delete.html",
            {"student": student, "title": "Student"},
        )
    return render(request, "students/student_confirm_delete.html", {"student": student})


@login_required
def student_detail(request, pk):
    if not (
        request.user.is_admin or request.user.is_registrar or request.user.is_teacher
    ):
        messages.error(request, "Access denied.")
        return redirect("dashboard:index")

    student = get_object_or_404(Student, pk=pk)
    grades = (
        Grade.objects.filter(student=student)
        .select_related("subject", "grading_period", "school_year")
        .order_by("-school_year__name", "-grading_period__order", "subject__name")
    )

    return render(
        request, "students/student_detail.html", {"student": student, "grades": grades}
    )
