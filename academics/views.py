from django.shortcuts import render, redirect, get_object_or_404
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
from accounts.decorators import admin_required


@admin_required
def academics_index(request):
    return render(request, "academics/index.html")


@admin_required
def school_year_list(request):
    school_years = SchoolYear.objects.all()
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


@admin_required
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


@admin_required
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


@admin_required
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
    sections_with_teachers = Section.objects.select_related(
        "grade_level", "school_year", "adviser"
    ).all()
    paginator = Paginator(sections_with_teachers, 15)
    page = request.GET.get("page", 1)
    sections_page = paginator.get_page(page)
    if request.headers.get("HX-Request"):
        return render(
            request, "academics/partials/section_table.html", {"sections_with_teachers": sections_page}
        )
    return render(request, "academics/section_list.html", {"sections_with_teachers": sections_page})


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
def subject_list(request):
    subjects = Subject.objects.select_related("grade_level").all()
    paginator = Paginator(subjects, 15)
    page = request.GET.get("page", 1)
    subjects_page = paginator.get_page(page)
    if request.headers.get("HX-Request"):
        return render(
            request, "academics/partials/subject_table.html", {"subjects": subjects_page}
        )
    return render(request, "academics/subject_list.html", {"subjects": subjects_page})


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
    from django.core.paginator import Paginator
    from django.db.models import Q, Count
    from accounts.models import User
    
    query = request.GET.get("q", "")
    subject_filter = request.GET.get("subject", "")
    section_filter = request.GET.get("section", "")
    school_year_filter = request.GET.get("school_year", "")
    view_type = request.GET.get("view", "teacher")
    
    assignments = TeacherAssignment.objects.select_related(
        "teacher", "subject", "section", "section__grade_level", "school_year"
    ).all().order_by('teacher__last_name', 'teacher__first_name', 'subject__name', 'section__name')
    
    if query:
        assignments = assignments.filter(
            Q(teacher__first_name__icontains=query)
            | Q(teacher__last_name__icontains=query)
            | Q(teacher__email__icontains=query)
        )
    
    if subject_filter:
        assignments = assignments.filter(subject_id=subject_filter)
    
    if section_filter:
        assignments = assignments.filter(section_id=section_filter)
    
    if school_year_filter:
        assignments = assignments.filter(school_year_id=school_year_filter)
    
    # Stats
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    total_assignments = assignments.count()
    active_teachers = User.objects.filter(role='teacher', is_active=True).count()
    assigned_teacher_ids = assignments.values_list('teacher_id', flat=True).distinct()
    unassigned_teachers = active_teachers - len(assigned_teacher_ids)
    sections_covered = assignments.values_list('section_id', flat=True).distinct().count()
    
    # Teacher workloads
    teacher_workloads = User.objects.filter(role='teacher', is_active=True).annotate(
        assignment_count=Count('assignments')
    ).order_by('-assignment_count')
    
    # Sections with teachers for section view
    sections_with_teachers = Section.objects.filter(school_year=current_sy).prefetch_related('assignments__teacher', 'assignments__subject') if current_sy else Section.objects.none()

    # Filter options
    all_subjects = Subject.objects.filter(is_active=True)
    all_sections = Section.objects.filter(school_year=current_sy) if current_sy else Section.objects.none()
    all_school_years = SchoolYear.objects.all()

    # Pagination
    paginator = Paginator(assignments, 15)
    page = request.GET.get("page", 1)
    assignments_page = paginator.get_page(page)

    sections_paginator = Paginator(sections_with_teachers, 15)
    sections_page = sections_paginator.get_page(page)

    if request.headers.get("HX-Request"):
        if view_type == "section":
            return render(
                request,
                "academics/partials/section_table.html",
                {"sections_with_teachers": sections_page},
            )
        return render(
            request,
            "academics/partials/assignment_table.html",
            {
                "assignments": assignments_page,
                "query": query,
                "subject_filter": subject_filter,
                "section_filter": section_filter,
                "school_year_filter": school_year_filter,
            },
        )

    return render(
        request,
        "academics/assignment_list.html",
        {
            "assignments": assignments_page,
            "query": query,
            "subject_filter": subject_filter,
            "section_filter": section_filter,
            "school_year_filter": school_year_filter,
            "total_assignments": total_assignments,
            "active_teachers": active_teachers,
            "unassigned_teachers": unassigned_teachers,
            "sections_covered": sections_covered,
            "teacher_workloads": teacher_workloads,
            "sections_with_teachers": sections_page,
            "subjects": all_subjects,
            "sections": all_sections,
            "school_years": all_school_years,
        },
    )


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


@admin_required
def grading_period_list(request):
    periods = GradingPeriod.objects.select_related("school_year").all()
    paginator = Paginator(periods, 15)
    page = request.GET.get("page", 1)
    periods_page = paginator.get_page(page)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academics/partials/grading_period_table.html",
            {"periods": periods_page},
        )
    return render(request, "academics/grading_period_list.html", {"periods": periods_page})


@admin_required
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


@admin_required
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


@admin_required
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
