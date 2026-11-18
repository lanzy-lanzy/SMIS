from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.utils.http import urlencode
from .filters import select_school_year
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
from accounts.decorators import admin_required, registrar_or_admin_required
from students.models import Student


@admin_required
def academics_index(request):
    return render(request, "academics/index.html")


@registrar_or_admin_required
def school_year_list(request):
    school_years = SchoolYear.objects.order_by("-is_current", "-name", "pk")
    paginator = Paginator(school_years, 15)
    page = request.GET.get("page", 1)
    school_years_page = paginator.get_page(page)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/school_year_table.html",
            {"school_years": school_years_page},
        )
    return render(
        request, "academics/school_year_list.html", {"school_years": school_years_page}
    )


@registrar_or_admin_required
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


@registrar_or_admin_required
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


@registrar_or_admin_required
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


@admin_required
def grade_level_list(request):
    grade_levels = GradeLevel.objects.all()
    paginator = Paginator(grade_levels, 15)
    page = request.GET.get("page", 1)
    grade_levels_page = paginator.get_page(page)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/grade_level_table.html",
            {"grade_levels": grade_levels_page},
        )
    return render(
        request, "academics/grade_level_list.html", {"grade_levels": grade_levels_page}
    )


@admin_required
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


@admin_required
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


@admin_required
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


@admin_required
def section_list(request):
    school_years = list(SchoolYear.objects.order_by("-is_current", "-name"))
    grade_levels = list(GradeLevel.objects.filter(level__gte=7, level__lte=12))
    valid_grade_ids = {str(grade_level.pk) for grade_level in grade_levels}

    current_year = next((year for year in school_years if year.is_current), None)
    school_year_filter, selected_school_year = select_school_year(request.GET.get("school_year"), school_years)

    grade_filter = request.GET.get("grade_level", "")
    if grade_filter not in valid_grade_ids:
        grade_filter = ""

    search_query = request.GET.get("q", "").strip()
    sections_with_teachers = Section.objects.select_related(
        "grade_level", "school_year", "adviser"
    ).annotate(
        student_count=Count("student", distinct=True),
        teacher_count=Count("assignments__teacher", distinct=True),
        subject_count=Count("assignments__subject", distinct=True),
    )

    if school_year_filter != "all":
        sections_with_teachers = sections_with_teachers.filter(
            school_year_id=school_year_filter
        )
    if grade_filter:
        sections_with_teachers = sections_with_teachers.filter(
            grade_level_id=grade_filter
        )
    if search_query:
        sections_with_teachers = sections_with_teachers.filter(
            Q(name__icontains=search_query)
            | Q(grade_level__name__icontains=search_query)
            | Q(adviser__first_name__icontains=search_query)
            | Q(adviser__last_name__icontains=search_query)
        )

    sections_with_teachers = sections_with_teachers.order_by(
        "-school_year__is_current", "-school_year__name", "grade_level__level", "name"
    )
    paginator = Paginator(sections_with_teachers, 20)
    page = request.GET.get("page", 1)
    sections_page = paginator.get_page(page)
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    pagination_params["school_year"] = school_year_filter
    context = {
        "sections_with_teachers": sections_page,
        "section_selection": True,
        "school_years": school_years,
        "grade_levels": grade_levels,
        "school_year_filter": school_year_filter,
        "grade_filter": grade_filter,
        "search_query": search_query,
        "selected_school_year": selected_school_year,
        "filters_active": bool(
            search_query
            or grade_filter
            or (current_year and school_year_filter != str(current_year.pk))
        ),
        "pagination_query": pagination_params.urlencode(),
    }
    if request.headers.get("HX-Request"):
        return render(
            request, "academics/partials/section_table.html", context
        )
    return render(request, "academics/section_list.html", context)


@admin_required
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


@admin_required
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


@admin_required
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


@admin_required
def section_bulk_delete(request):
    if request.method == "POST":
        raw_ids = request.POST.getlist("section_ids")
    else:
        raw_ids = request.GET.get("ids", "").split(",")
    ids = []
    for raw in raw_ids:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    sections = list(
        Section.objects.select_related("grade_level", "school_year").filter(pk__in=ids)
    )
    if not sections:
        messages.error(request, "No sections selected.")
        if request.headers.get("HX-Request"):
            return HttpResponse(
                "<script>closeModal();</script>",
                headers={"HX-Trigger": "closeModal"},
            )
        return redirect("academics:section_list")

    if request.method == "POST":
        deleted = []
        with transaction.atomic():
            for section in sections:
                pk, name = section.pk, str(section)
                section.delete()
                deleted.append(name)
                AuditLog.objects.create(
                    user=request.user,
                    action="delete",
                    model_name="Section",
                    object_id=str(pk),
                    description=f"Deleted section {name} (bulk delete)",
                )
        count = len(deleted)
        messages.success(request, f"{count} section{'s' if count != 1 else ''} deleted.")
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<script>closeModal(); htmx.trigger("#section-table", "refresh");</script>',
                headers={"HX-Trigger": "closeModal,refreshTable"},
            )
        return redirect("academics:section_list")

    context = {
        "sections": sections,
        "learner_count": Student.objects.filter(section__in=sections).count(),
        "assignment_count": TeacherAssignment.objects.filter(
            section__in=sections
        ).count(),
    }
    if request.headers.get("HX-Request"):
        return render(
            request, "academics/partials/section_bulk_confirm_delete.html", context
        )
    return render(request, "academics/section_bulk_confirm_delete.html", context)


@admin_required
def subject_list(request):
    query = request.GET.get("q", "").strip()
    grade_levels = list(GradeLevel.objects.all())
    grade_filter = request.GET.get("grade_level", "")
    status_filter = request.GET.get("status", "")
    sort_options = {
        "grade": ("Grade level", ("grade_level__level", "name", "code")),
        "name": ("Subject name", ("name", "code")),
        "code": ("Subject code", ("code",)),
    }
    sort = request.GET.get("sort", "grade")
    if sort not in sort_options:
        sort = "grade"
    if grade_filter not in {str(level.pk) for level in grade_levels}:
        grade_filter = ""
    if status_filter not in ("active", "inactive"):
        status_filter = ""

    subjects = Subject.objects.select_related("grade_level").order_by(*sort_options[sort][1])
    for term in query.split():
        subjects = subjects.filter(
            Q(name__icontains=term) | Q(code__icontains=term) | Q(description__icontains=term)
        )
    if grade_filter:
        subjects = subjects.filter(grade_level_id=grade_filter)
    if status_filter:
        subjects = subjects.filter(is_active=(status_filter == "active"))

    paginator = Paginator(subjects, 15)
    filters = {
        "q": query, "grade_level": grade_filter, "status": status_filter,
        "sort": sort if sort != "grade" else "",
    }
    context = {
        "subjects": paginator.get_page(request.GET.get("page", 1)),
        "grade_levels": grade_levels,
        "query": query,
        "grade_filter": grade_filter,
        "status_filter": status_filter,
        "sort": sort,
        "sort_options": [(key, label) for key, (label, _) in sort_options.items()],
        "filters_active": bool(query or grade_filter or status_filter),
        "pagination_query": urlencode({name: value for name, value in filters.items() if value}),
    }
    template = "academics/partials/subject_table.html" if request.headers.get("HX-Request") else "academics/subject_list.html"
    return render(request, template, context)


@admin_required
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


@admin_required
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


@admin_required
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


@admin_required
def assignment_list(request):
    from accounts.models import User

    school_years = list(SchoolYear.objects.order_by("-is_current", "-name"))
    year_filter, year = select_school_year(request.GET.get("school_year"), school_years)
    query = request.GET.get("q", "").strip()
    subject_filter = request.GET.get("subject", "")
    section_filter = request.GET.get("section", "")
    view_type = "section" if request.GET.get("view") == "section" else "teacher"

    assignments = TeacherAssignment.objects.select_related(
        "teacher", "subject", "section", "section__grade_level", "school_year",
    ).order_by("teacher__last_name", "teacher__first_name", "subject__name", "section__name", "pk")
    sections = Section.objects.select_related("grade_level", "school_year", "adviser")
    if year:
        assignments = assignments.filter(school_year=year)
        sections = sections.filter(school_year=year)

    section_options = list(sections)
    if section_filter in {str(section.pk) for section in section_options}:
        assignments = assignments.filter(section_id=section_filter)
        sections = sections.filter(pk=section_filter)
    else:
        section_filter = ""

    subjects = list(Subject.objects.filter(
        pk__in=assignments.order_by().values("subject_id"),
    ).select_related("grade_level"))
    if subject_filter in {str(subject.pk) for subject in subjects}:
        assignments = assignments.filter(subject_id=subject_filter)
    else:
        subject_filter = ""
    if query:
        assignments = assignments.filter(
            Q(teacher__first_name__icontains=query)
            | Q(teacher__last_name__icontains=query)
            | Q(teacher__email__icontains=query)
        )

    if query or subject_filter:
        sections = sections.filter(pk__in=assignments.order_by().values("section_id"))
    matched_assignments = Q(assignments__pk__in=assignments.order_by().values("pk"))
    sections = sections.annotate(
        student_count=Count("student", distinct=True),
        teacher_count=Count("assignments__teacher", filter=matched_assignments, distinct=True),
        subject_count=Count("assignments__subject", filter=matched_assignments, distinct=True),
    ).order_by("-school_year__name", "grade_level__level", "name", "pk")

    page = request.GET.get("page", 1)
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    pagination_params["school_year"] = year_filter
    pagination_params["section"] = section_filter
    pagination_params["subject"] = subject_filter
    pagination_params.pop("view", None)
    context = {
        "assignments": Paginator(assignments, 15).get_page(page if view_type == "teacher" else 1),
        "sections_with_teachers": Paginator(sections, 15).get_page(page if view_type == "section" else 1),
        "query": query,
        "subject_filter": subject_filter,
        "section_filter": section_filter,
        "school_year_filter": year_filter,
        "selected_school_year": year,
        "school_years": school_years,
        "subjects": subjects,
        "sections": section_options,
        "view_type": view_type,
        "pagination_query": pagination_params.urlencode(),
    }
    if request.headers.get("HX-Request"):
        template = "academics/partials/section_table.html" if view_type == "section" else "academics/partials/assignment_table.html"
        return render(request, template, context)

    active_teachers = User.objects.filter(role="teacher", is_active=True)
    teacher_workloads = active_teachers.annotate(
        assignment_count=Count("assignments", filter=matched_assignments),
    ).order_by("-assignment_count", "last_name", "pk")
    context.update(
        total_assignments=assignments.count(),
        active_teachers=active_teachers.count(),
        unassigned_teachers=teacher_workloads.filter(assignment_count=0).count(),
        sections_covered=assignments.order_by().values("section_id").distinct().count(),
        teacher_workloads=teacher_workloads,
    )
    return render(request, "academics/assignment_list.html", context)


@admin_required
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


@admin_required
def assignment_edit(request, pk):
    assignment = get_object_or_404(TeacherAssignment, pk=pk)
    if request.method == "POST":
        form = TeacherAssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            assignment = form.save()
            AuditLog.objects.create(
                user=request.user,
                action="update",
                model_name="TeacherAssignment",
                object_id=str(assignment.id),
                description=f"Updated assignment for {assignment.teacher.get_full_name()}",
            )
            messages.success(
                request, f"Assignment updated for {assignment.teacher.get_full_name()}."
            )
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#assignment-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("academics:assignment_list")
    else:
        form = TeacherAssignmentForm(instance=assignment)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/assignment_form.html",
            {"form": form, "title": "Edit Teacher Assignment"},
        )
    return render(
        request,
        "academics/assignment_form.html",
        {"form": form, "title": "Edit Teacher Assignment"},
    )


@admin_required
def assignment_bulk_create(request):
    from accounts.models import User
    
    if request.method == "POST":
        teacher_id = request.POST.get("teacher")
        subject_ids = request.POST.getlist("subjects")
        section_ids = request.POST.getlist("sections")
        school_year_id = request.POST.get("school_year")
        
        teacher = get_object_or_404(User, pk=teacher_id)
        school_year = get_object_or_404(SchoolYear, pk=school_year_id)
        
        created_count = 0
        for subject_id in subject_ids:
            for section_id in section_ids:
                _, created = TeacherAssignment.objects.get_or_create(
                    teacher=teacher,
                    subject_id=subject_id,
                    section_id=section_id,
                    school_year=school_year,
                )
                if created:
                    created_count += 1
        
        AuditLog.objects.create(
            user=request.user,
            action="create",
            model_name="TeacherAssignment",
            description=f"Bulk created {created_count} assignments for {teacher.get_full_name()}",
        )
        messages.success(request, f"{created_count} assignments created for {teacher.get_full_name()}.")
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<script>closeModal(); htmx.trigger("#assignment-table", "refresh");</script>',
                headers={"HX-Trigger": "closeModal,refreshTable"},
            )
        return redirect("academics:assignment_list")
    
    context = {
        "teachers": User.objects.filter(role='teacher', is_active=True),
        "subjects": Subject.objects.filter(is_active=True),
        "sections": Section.objects.filter(school_year=SchoolYear.objects.filter(is_current=True).first()),
        "school_years": SchoolYear.objects.all(),
    }
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/assignment_bulk_form.html",
            context,
        )
    return render(
        request,
        "academics/assignment_bulk_form.html",
        context,
    )


@admin_required
def assignment_export(request):
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="teacher_assignments.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Teacher', 'Email', 'Subject', 'Section', 'Grade Level', 'School Year'])
    
    assignments = TeacherAssignment.objects.select_related(
        "teacher", "subject", "section", "section__grade_level", "school_year"
    ).all()
    
    for assignment in assignments:
        writer.writerow([
            assignment.teacher.get_full_name(),
            assignment.teacher.email,
            assignment.subject.name,
            assignment.section.name,
            assignment.section.grade_level,
            assignment.school_year.name,
        ])
    
    return response


@admin_required
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


@registrar_or_admin_required
def grading_period_list(request):
    school_years = list(SchoolYear.objects.order_by("-is_current", "-name"))
    year_filter, year = select_school_year(request.GET.get("school_year"), school_years)
    periods = GradingPeriod.objects.select_related("school_year").order_by(
        "-school_year__is_current", "-school_year__name", "order",
    )
    if year:
        periods = periods.filter(school_year=year)
    paginator = Paginator(periods, 15)
    page = request.GET.get("page", 1)
    periods_page = paginator.get_page(page)
    context = {"periods": periods_page, "school_years": school_years, "year_filter": year_filter}
    template = "academics/partials/grading_period_table.html" if request.headers.get("HX-Request") else "academics/grading_period_list.html"
    return render(request, template, context)


@registrar_or_admin_required
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


@registrar_or_admin_required
def grading_period_edit(request, pk):
    period = get_object_or_404(GradingPeriod, pk=pk)
    if request.method == "POST":
        form = GradingPeriodForm(request.POST, instance=period)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action="update",
                model_name="GradingPeriod",
                object_id=str(period.id),
                description=f"Updated grading period {period.name} ({period.month_range or 'no months'})",
            )
            messages.success(request, f"Grading period {period.name} updated.")
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<script>closeModal(); htmx.trigger("#grading-period-table", "refresh");</script>',
                    headers={"HX-Trigger": "closeModal,refreshTable"},
                )
            return redirect("academics:grading_period_list")
    else:
        form = GradingPeriodForm(instance=period)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/grading_period_form.html",
            {"form": form, "title": "Edit Grading Period"},
        )
    return render(
        request,
        "academics/grading_period_form.html",
        {"form": form, "title": "Edit Grading Period"},
    )


@registrar_or_admin_required
def grading_period_delete(request, pk):
    if request.method != "POST":
        return HttpResponse(status=405)

    period = get_object_or_404(GradingPeriod, pk=pk)
    name = period.name
    year = period.school_year.name
    # WARNING: GradingPeriod is a CASCADE target for Grade and GradeSubmission,
    # so this permanently removes all grades and submissions for the quarter.
    period.delete()

    AuditLog.objects.create(
        user=request.user,
        action="delete",
        model_name="GradingPeriod",
        object_id=str(pk),
        description=f"Deleted grading period {name} ({year})",
    )
    messages.success(request, f"Grading period {name} ({year}) deleted.")
    return redirect("academics:grading_period_list")


@registrar_or_admin_required
def grading_period_toggle_submissions(request, pk):
    if request.method != 'POST':
        return HttpResponse(status=405)
    
    period = get_object_or_404(GradingPeriod, pk=pk)
    period.is_submissions_open = not period.is_submissions_open
    period.save()
    
    status = "opened" if period.is_submissions_open else "closed"
    AuditLog.objects.create(
        user=request.user,
        action="update",
        model_name="GradingPeriod",
        object_id=str(period.id),
        description=f"Grade submissions {status} for {period.name}",
    )
    messages.success(request, f"Grade submissions {status} for {period.name}.")
    
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/grading_period_row.html",
            {"gp": period},
        )
    return redirect("academics:grading_period_list")


@registrar_or_admin_required
def grading_period_toggle_current(request, pk):
    if request.method != 'POST':
        return HttpResponse(status=405)
    
    period = get_object_or_404(GradingPeriod, pk=pk)
    period.is_current = not period.is_current
    period.save()
    
    status = "activated" if period.is_current else "deactivated"
    AuditLog.objects.create(
        user=request.user,
        action="update",
        model_name="GradingPeriod",
        object_id=str(period.id),
        description=f"Grading period {status}: {period.name}",
    )
    messages.success(request, f"Grading period {period.name} {status}.")
    
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/grading_period_row.html",
            {"gp": period},
        )
    return redirect("academics:grading_period_list")


@registrar_or_admin_required
def grading_period_open_next(request, pk):
    """Advance the academic calendar: close the completed quarter's submissions and
    open + activate the next quarter so teachers can begin encoding it."""
    if request.method != 'POST':
        return HttpResponse(status=405)

    current_period = get_object_or_404(GradingPeriod, pk=pk)
    next_period = GradingPeriod.objects.filter(
        school_year=current_period.school_year,
        order__gt=current_period.order,
    ).order_by('order').first()

    if not next_period:
        messages.info(request, f"{current_period.name} is the final quarter — there is no next quarter to open.")
        return redirect(request.POST.get('next') or 'academics:grading_period_list')

    # Close the finished quarter, then open and activate the next one.
    current_period.is_submissions_open = False
    current_period.is_current = False
    current_period.save(update_fields=['is_submissions_open', 'is_current'])

    next_period.is_submissions_open = True
    next_period.is_current = True
    next_period.save()  # save() enforces a single is_current per school year

    AuditLog.objects.create(
        user=request.user,
        action="update",
        model_name="GradingPeriod",
        object_id=str(next_period.id),
        description=f"Advanced calendar: closed {current_period.name}, opened {next_period.name} for grade submissions",
    )
    messages.success(request, f"{current_period.name} closed. {next_period.name} is now open for grade submissions.")
    return redirect(request.POST.get('next') or 'academics:grading_period_list')
