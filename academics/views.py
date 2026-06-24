from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from .models import (
    SchoolYear,
    GradeLevel,
    Section,
    Subject,
    TeacherAssignment,
    GradingPeriod,
)
from .forms import (
    SchoolYearForm,
    GradeLevelForm,
    SectionForm,
    SubjectForm,
    TeacherAssignmentForm,
    GradingPeriodForm,
)
from accounts.models import AuditLog


@login_required
def academics_index(request):
    return render(request, "academics/index.html")


@login_required
def school_year_list(request):
    school_years = SchoolYear.objects.all()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/school_year_table.html",
            {"school_years": school_years},
        )
    return render(
        request, "academics/school_year_list.html", {"school_years": school_years}
    )


@login_required
def school_year_create(request):
    if request.method == "POST":
        form = SchoolYearForm(request.POST)
        if form.is_valid():
            sy = form.save()
            AuditLog.objects.create(
                user=request.user,
                action="create",
                model_name="SchoolYear",
                object_id=str(sy.id),
                description=f"Created school year {sy.name}",
            )
            messages.success(request, f"School year {sy.name} created.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#school-year-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("academics:school_year_list")
    else:
        form = SchoolYearForm()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/school_year_form.html",
            {"form": form, "title": "Add School Year"},
        )
    return render(
        request,
        "academics/school_year_form.html",
        {"form": form, "title": "Add School Year"},
    )


@login_required
def school_year_edit(request, pk):
    sy = get_object_or_404(SchoolYear, pk=pk)
    if request.method == "POST":
        form = SchoolYearForm(request.POST, instance=sy)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action="update",
                model_name="SchoolYear",
                object_id=str(sy.id),
                description=f"Updated school year {sy.name}",
            )
            messages.success(request, f"School year {sy.name} updated.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#school-year-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("academics:school_year_list")
    else:
        form = SchoolYearForm(instance=sy)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/school_year_form.html",
            {"form": form, "title": "Edit School Year"},
        )
    return render(
        request,
        "academics/school_year_form.html",
        {"form": form, "title": "Edit School Year"},
    )


@login_required
def school_year_delete(request, pk):
    sy = get_object_or_404(SchoolYear, pk=pk)
    if request.method == "POST":
        name = sy.name
        sy.delete()
        AuditLog.objects.create(
            user=request.user,
            action="delete",
            model_name="SchoolYear",
            object_id=str(pk),
            description=f"Deleted school year {name}",
        )
        messages.success(request, f"School year {name} deleted.")
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<script>closeModal(); htmx.trigger("#school-year-table", "refresh");</script>',
                headers={"HX-Trigger": "closeModal,refreshTable"},
            )
        return redirect("academics:school_year_list")
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/school_year_confirm_delete.html",
            {"object": sy, "title": "School Year"},
        )
    return render(
        request, "academics/confirm_delete.html", {"object": sy, "title": "School Year"}
    )


@login_required
def grade_level_list(request):
    grade_levels = GradeLevel.objects.all()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/grade_level_table.html",
            {"grade_levels": grade_levels},
        )
    return render(
        request, "academics/grade_level_list.html", {"grade_levels": grade_levels}
    )


@login_required
def grade_level_create(request):
    if request.method == "POST":
        form = GradeLevelForm(request.POST)
        if form.is_valid():
            gl = form.save()
            AuditLog.objects.create(
                user=request.user,
                action="create",
                model_name="GradeLevel",
                object_id=str(gl.id),
                description=f"Created grade level {gl.name}",
            )
            messages.success(request, f"Grade level {gl.name} created.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#grade-level-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("academics:grade_level_list")
    else:
        form = GradeLevelForm()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/grade_level_form.html",
            {"form": form, "title": "Add Grade Level"},
        )
    return render(
        request,
        "academics/grade_level_form.html",
        {"form": form, "title": "Add Grade Level"},
    )


@login_required
def grade_level_edit(request, pk):
    gl = get_object_or_404(GradeLevel, pk=pk)
    if request.method == "POST":
        form = GradeLevelForm(request.POST, instance=gl)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action="update",
                model_name="GradeLevel",
                object_id=str(gl.id),
                description=f"Updated grade level {gl.name}",
            )
            messages.success(request, f"Grade level {gl.name} updated.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#grade-level-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("academics:grade_level_list")
    else:
        form = GradeLevelForm(instance=gl)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/grade_level_form.html",
            {"form": form, "title": "Edit Grade Level"},
        )
    return render(
        request,
        "academics/grade_level_form.html",
        {"form": form, "title": "Edit Grade Level"},
    )


@login_required
def grade_level_delete(request, pk):
    gl = get_object_or_404(GradeLevel, pk=pk)
    if request.method == "POST":
        name = gl.name
        gl.delete()
        AuditLog.objects.create(
            user=request.user,
            action="delete",
            model_name="GradeLevel",
            object_id=str(pk),
            description=f"Deleted grade level {name}",
        )
        messages.success(request, f"Grade level {name} deleted.")
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<script>closeModal(); htmx.trigger("#grade-level-table", "refresh");</script>',
                headers={"HX-Trigger": "closeModal,refreshTable"},
            )
        return redirect("academics:grade_level_list")
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/grade_level_confirm_delete.html",
            {"object": gl, "title": "Grade Level"},
        )
    return render(
        request, "academics/confirm_delete.html", {"object": gl, "title": "Grade Level"}
    )


@login_required
def section_list(request):
    sections = Section.objects.select_related(
        "grade_level", "school_year", "adviser"
    ).all()
    if request.headers.get("HX-Request"):
        return render(
            request, "academics/partials/section_table.html", {"sections": sections}
        )
    return render(request, "academics/section_list.html", {"sections": sections})


@login_required
def section_create(request):
    if request.method == "POST":
        form = SectionForm(request.POST)
        if form.is_valid():
            section = form.save()
            AuditLog.objects.create(
                user=request.user,
                action="create",
                model_name="Section",
                object_id=str(section.id),
                description=f"Created section {section.name}",
            )
            messages.success(request, f"Section {section.name} created.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#section-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("academics:section_list")
    else:
        form = SectionForm()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/section_form.html",
            {"form": form, "title": "Add Section"},
        )
    return render(
        request, "academics/section_form.html", {"form": form, "title": "Add Section"}
    )


@login_required
def section_edit(request, pk):
    section = get_object_or_404(Section, pk=pk)
    if request.method == "POST":
        form = SectionForm(request.POST, instance=section)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action="update",
                model_name="Section",
                object_id=str(section.id),
                description=f"Updated section {section.name}",
            )
            messages.success(request, f"Section {section.name} updated.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#section-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("academics:section_list")
    else:
        form = SectionForm(instance=section)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/section_form.html",
            {"form": form, "title": "Edit Section"},
        )
    return render(
        request, "academics/section_form.html", {"form": form, "title": "Edit Section"}
    )


@login_required
def section_delete(request, pk):
    section = get_object_or_404(Section, pk=pk)
    if request.method == "POST":
        name = section.name
        section.delete()
        AuditLog.objects.create(
            user=request.user,
            action="delete",
            model_name="Section",
            object_id=str(pk),
            description=f"Deleted section {name}",
        )
        messages.success(request, f"Section {name} deleted.")
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<script>closeModal(); htmx.trigger("#section-table", "refresh");</script>',
                headers={"HX-Trigger": "closeModal,refreshTable"},
            )
        return redirect("academics:section_list")
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/section_confirm_delete.html",
            {"object": section, "title": "Section"},
        )
    return render(
        request,
        "academics/confirm_delete.html",
        {"object": section, "title": "Section"},
    )


@login_required
def subject_list(request):
    subjects = Subject.objects.select_related("grade_level").all()
    if request.headers.get("HX-Request"):
        return render(
            request, "academics/partials/subject_table.html", {"subjects": subjects}
        )
    return render(request, "academics/subject_list.html", {"subjects": subjects})


@login_required
def subject_create(request):
    if request.method == "POST":
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save()
            AuditLog.objects.create(
                user=request.user,
                action="create",
                model_name="Subject",
                object_id=str(subject.id),
                description=f"Created subject {subject.name}",
            )
            messages.success(request, f"Subject {subject.name} created.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#subject-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("academics:subject_list")
    else:
        form = SubjectForm()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/subject_form.html",
            {"form": form, "title": "Add Subject"},
        )
    return render(
        request, "academics/subject_form.html", {"form": form, "title": "Add Subject"}
    )


@login_required
def subject_edit(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == "POST":
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action="update",
                model_name="Subject",
                object_id=str(subject.id),
                description=f"Updated subject {subject.name}",
            )
            messages.success(request, f"Subject {subject.name} updated.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#subject-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("academics:subject_list")
    else:
        form = SubjectForm(instance=subject)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/subject_form.html",
            {"form": form, "title": "Edit Subject"},
        )
    return render(
        request, "academics/subject_form.html", {"form": form, "title": "Edit Subject"}
    )


@login_required
def subject_delete(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == "POST":
        name = subject.name
        subject.delete()
        AuditLog.objects.create(
            user=request.user,
            action="delete",
            model_name="Subject",
            object_id=str(pk),
            description=f"Deleted subject {name}",
        )
        messages.success(request, f"Subject {name} deleted.")
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<script>closeModal(); htmx.trigger("#subject-table", "refresh");</script>',
                headers={"HX-Trigger": "closeModal,refreshTable"},
            )
        return redirect("academics:subject_list")
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/subject_confirm_delete.html",
            {"object": subject, "title": "Subject"},
        )
    return render(
        request,
        "academics/confirm_delete.html",
        {"object": subject, "title": "Subject"},
    )


@login_required
def assignment_list(request):
    assignments = TeacherAssignment.objects.select_related(
        "teacher", "subject", "section", "school_year"
    ).all()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/assignment_table.html",
            {"assignments": assignments},
        )
    return render(
        request, "academics/assignment_list.html", {"assignments": assignments}
    )


@login_required
def assignment_create(request):
    if request.method == "POST":
        form = TeacherAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save()
            AuditLog.objects.create(
                user=request.user,
                action="create",
                model_name="TeacherAssignment",
                object_id=str(assignment.id),
                description=f"Created assignment for {assignment.teacher.get_full_name()}",
            )
            messages.success(
                request, f"Assignment created for {assignment.teacher.get_full_name()}."
            )
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#assignment-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("academics:assignment_list")
    else:
        form = TeacherAssignmentForm()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/assignment_form.html",
            {"form": form, "title": "Add Teacher Assignment"},
        )
    return render(
        request,
        "academics/assignment_form.html",
        {"form": form, "title": "Add Teacher Assignment"},
    )


@login_required
def assignment_delete(request, pk):
    assignment = get_object_or_404(TeacherAssignment, pk=pk)
    if request.method == "POST":
        assignment.delete()
        AuditLog.objects.create(
            user=request.user,
            action="delete",
            model_name="TeacherAssignment",
            object_id=str(pk),
            description=f"Deleted assignment",
        )
        messages.success(request, "Assignment deleted.")
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<script>closeModal(); htmx.trigger("#assignment-table", "refresh");</script>',
                headers={"HX-Trigger": "closeModal,refreshTable"},
            )
        return redirect("academics:assignment_list")
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/assignment_confirm_delete.html",
            {"object": assignment, "title": "Assignment"},
        )
    return render(
        request,
        "academics/confirm_delete.html",
        {"object": assignment, "title": "Assignment"},
    )


@login_required
def grading_period_list(request):
    periods = GradingPeriod.objects.select_related("school_year").all()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/grading_period_table.html",
            {"periods": periods},
        )
    return render(request, "academics/grading_period_list.html", {"periods": periods})


@login_required
def grading_period_create(request):
    if request.method == "POST":
        form = GradingPeriodForm(request.POST)
        if form.is_valid():
            period = form.save()
            AuditLog.objects.create(
                user=request.user,
                action="create",
                model_name="GradingPeriod",
                object_id=str(period.id),
                description=f"Created grading period {period.name}",
            )
            messages.success(request, f"Grading period {period.name} created.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#grading-period-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("academics:grading_period_list")
    else:
        form = GradingPeriodForm()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/grading_period_form.html",
            {"form": form, "title": "Add Grading Period"},
        )
    return render(
        request,
        "academics/grading_period_form.html",
        {"form": form, "title": "Add Grading Period"},
    )
