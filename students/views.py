from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.utils.http import urlencode
from django.views.decorators.http import require_http_methods
from itertools import groupby
from .models import Student, StudentPromotion
from .forms import StudentForm, StudentPromotionForm
from .promotion import (
    default_promotion_source_year, promote_cohort, promote_student, promotion_destinations, promotion_issues,
)
from academics.filters import select_school_year
from academics.models import GradeLevel, SchoolYear, Section
from accounts.models import AuditLog
from grades.models import Grade
from accounts.decorators import (
    role_required,
    admin_required,
    registrar_or_admin_required,
    teacher_or_admin_required,
)


def _teacher_assigned_sections(user):
    """Return section IDs for sections the teacher is assigned to in the current school year."""
    from academics.models import TeacherAssignment, SchoolYear
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    if current_sy:
        return list(TeacherAssignment.objects.filter(
            teacher=user,
            school_year=current_sy
        ).values_list('section_id', flat=True).distinct())
    return []


def _filter_students_by_role(queryset, user):
    """Scope student queryset based on user role."""
    if user.is_teacher:
        assigned_section_ids = _teacher_assigned_sections(user)
        if assigned_section_ids:
            return queryset.filter(section_id__in=assigned_section_ids)
        return queryset.none()
    return queryset


@role_required('admin', 'registrar', 'teacher')
def student_list(request):
    query = request.GET.get("q", "").strip()
    grade_filter = request.GET.get("grade", "")
    section_filter = request.GET.get("section", "")
    status_filter = request.GET.get("status", "")

    sex_filter = request.GET.get("sex", "")
    from academics.models import GradeLevel, Section, SchoolYear

    sections = Section.objects.select_related("grade_level", "school_year")
    if request.user.is_teacher:
        sections = sections.filter(pk__in=_teacher_assigned_sections(request.user))
        grade_levels = GradeLevel.objects.filter(
            pk__in=sections.values("grade_level_id")
        )
    else:
        grade_levels = GradeLevel.objects.all()
    grade_levels = list(grade_levels)
    if grade_filter not in {str(level.pk) for level in grade_levels}:
        grade_filter = ""
    school_years = SchoolYear.objects.order_by("-is_current", "-name")
    if request.user.is_teacher:
        school_years = school_years.filter(pk__in=sections.values("school_year_id"))
    school_years = list(school_years)
    year_filter, selected_school_year = select_school_year(request.GET.get("year"), school_years)
    if selected_school_year:
        sections = sections.filter(school_year=selected_school_year)
    if grade_filter:
        sections = sections.filter(grade_level_id=grade_filter)
    # A grade change must not leave an incompatible section selected.
    sections = list(sections)
    if section_filter not in {str(section.pk) for section in sections}:
        section_filter = ""

    students = Student.objects.select_related(
        "grade_level", "section", "school_year"
    ).all()
    students = _filter_students_by_role(students, request.user)

    if selected_school_year:
        students = students.filter(school_year=selected_school_year)
    if sex_filter in dict(Student.SEX_CHOICES):
        students = students.filter(sex=sex_filter)

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
    students = paginator.get_page(request.GET.get("page", 1))
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    pagination_params.pop("view", None)
    pagination_params["section"] = section_filter
    pagination_params["year"] = year_filter
    pagination_params["grade"] = grade_filter
    pagination_query = pagination_params.urlencode()

    if request.headers.get("HX-Request"):
        return render(request, "students/partials/student_table.html", {
            "students": students,
            "pagination_query": pagination_query,
            "sections": sections,
            "section_filter": section_filter,
            "update_section_filter": True,
            "selected_school_year": selected_school_year,
            "grade_filter": grade_filter,
        })

    return render(
        request,
        "students/student_list.html",
        {
            "students": students,
            "query": query,
            "grade_filter": grade_filter,
            "section_filter": section_filter,
            "status_filter": status_filter,
            "year_filter": year_filter,
            "sex_filter": sex_filter,
            "school_years": school_years,
            "selected_school_year": selected_school_year,
            "sex_choices": Student.SEX_CHOICES,
            "grade_levels": grade_levels,
            "sections": sections,
            "status_choices": Student.STATUS_CHOICES + Student.LEGACY_STATUS_CHOICES,
            "pagination_query": pagination_query,
        },
    )


@registrar_or_admin_required
def student_create(request):
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


@registrar_or_admin_required
@transaction.atomic
def student_edit(request, pk):
    students = Student.objects.select_for_update() if request.method == "POST" else Student.objects.all()
    student = get_object_or_404(students, pk=pk)

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


@admin_required
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)

    if request.method == "POST":
        full_name = student.full_name
        has_validated = Grade.objects.filter(
            student=student, status__in=['validated', 'locked']
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


@registrar_or_admin_required
@require_http_methods(["GET", "POST"])
def bulk_promotion(request):
    # The form posts back to its preview URL so the reviewed cohort and destination
    # are explicit even if the active school year changes before confirmation.
    filters = request.GET
    school_years = list(SchoolYear.objects.order_by("-name"))
    school_year = next((year for year in school_years if str(year.pk) == filters.get("year")), None)
    school_year = school_year or default_promotion_source_year(school_years)
    cohort = Student.objects.filter(school_year=school_year) if school_year else Student.objects.none()

    grade_levels = list(GradeLevel.objects.all())
    grade_level = next((level for level in grade_levels if str(level.pk) == filters.get("grade")), None)
    if grade_level is None:
        cohort_grades = set(cohort.order_by().values_list("grade_level_id", flat=True).distinct())
        grade_level = next((level for level in grade_levels if level.pk in cohort_grades), next(iter(grade_levels), None))
    cohort = cohort.filter(grade_level=grade_level) if grade_level else Student.objects.none()

    source_sections = list(Section.objects.filter(school_year=school_year, grade_level=grade_level))
    source_section = next((section for section in source_sections if str(section.pk) == filters.get("section")), None)
    if source_section:
        cohort = cohort.filter(section=source_section)
    query = filters.get("q", "").strip()
    for term in query.split():
        cohort = cohort.filter(
            Q(lrn__icontains=term) | Q(first_name__icontains=term)
            | Q(middle_name__icontains=term) | Q(last_name__icontains=term)
        )

    destinations = list(promotion_destinations(school_year, grade_level)) if school_year and grade_level else []
    destination = next((section for section in destinations if str(section.pk) == filters.get("destination")), None)
    params = {
        "year": school_year.pk if school_year else None,
        "grade": grade_level.pk if grade_level else None,
        "section": source_section.pk if source_section else None,
        "destination": destination.pk if destination else None,
        "q": query,
    }
    preview_query = urlencode({key: value for key, value in params.items() if value})
    batch_limit = 25
    errors = []
    selected_ids = []
    if request.method == "POST":
        submitted_ids = request.POST.getlist("student")
        explicit_cohort = (
            school_year and grade_level and filters.get("year") == str(school_year.pk)
            and filters.get("grade") == str(grade_level.pk)
            and (not filters.get("section") or source_section)
        )
        if not destination or not explicit_cohort:
            errors = ["Load the cohort and select a destination section before confirming promotion."]
        elif not submitted_ids or len(submitted_ids) > batch_limit or any(
            not value.isascii() or not value.isdecimal() or len(value) > 19
            or not 0 < int(value) <= 2**63 - 1 for value in submitted_ids
        ):
            errors = [f"Select between 1 and {batch_limit} students from the roster."]
        else:
            selected_ids = list(dict.fromkeys(map(int, submitted_ids)))
            try:
                promote_cohort(cohort, selected_ids, school_year, grade_level, destination.pk, request.user)
            except ValidationError as error:
                errors = error.messages
            else:
                count = len(selected_ids)
                noun = "student was" if count == 1 else "students were"
                messages.success(request, f"{count} {noun} promoted to {destination} ({destination.school_year}).")
                return redirect(f"{reverse('students:bulk_promotion')}?{preview_query}")

    page = Paginator(
        cohort.select_related("section").order_by("last_name", "first_name", "pk"), batch_limit,
    ).get_page(filters.get("page"))
    students = list(page)
    issues = promotion_issues(students, school_year, grade_level, destination)
    history = StudentPromotion.objects.filter(from_school_year=school_year, from_grade_level=grade_level)
    if source_section:
        history = history.filter(from_section=source_section)
    history = history.select_related(
        "student", "from_section", "to_grade_level", "to_section", "to_school_year", "promoted_by",
    ).order_by("-promoted_at", "-pk")
    return render(request, "students/bulk_promotion.html", {
        "school_years": school_years, "school_year": school_year,
        "grade_levels": grade_levels, "grade_level": grade_level,
        "source_sections": source_sections, "source_section": source_section,
        "destinations": destinations, "destination": destination, "query": query,
        "preview_query": preview_query, "page": page, "errors": errors,
        "rows": [(student, issues.get(student.pk)) for student in students],
        "eligible_count": len(students) - len(issues), "blocked_count": len(issues),
        "history": history[:10], "promoted_count": history.count(), "selected_ids": selected_ids,
    })


@registrar_or_admin_required
@require_http_methods(["GET", "POST"])
def student_promote(request, pk):
    student = get_object_or_404(Student, pk=pk)
    is_modal = request.headers.get("HX-Request") == "true"
    form = StudentPromotionForm(request.POST if request.method == "POST" else None, student=student)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            promote_student(pk, data["source_year"], data["source_grade"], data["section"].pk, request.user)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"{student.full_name} was promoted to {data['section']} ({data['section'].school_year}).")
            if is_modal:
                return HttpResponse(headers={"HX-Redirect": reverse("students:student_detail", args=[pk])})
            return redirect("students:student_detail", pk=pk)

    template = "students/partials/student_promote.html" if is_modal else "students/student_promote.html"
    response = render(request, template, {
        "student": student,
        "form": form,
        "is_modal": is_modal,
        "destination": form.fields["section"].queryset.first(),
    })
    patch_vary_headers(response, ["HX-Request"])
    return response


@role_required('admin', 'registrar', 'teacher')
def student_detail(request, pk):
    student = get_object_or_404(Student, pk=pk)
    
    # For teachers, check if they are assigned to the student's section
    if request.user.is_teacher:
        assigned_section_ids = _teacher_assigned_sections(request.user)
        if student.section_id not in assigned_section_ids:
            messages.error(request, "Access denied. You are not assigned to this section.")
            return redirect("students:student_list")
    
    query = request.GET.get("q", "").strip()
    quarter_filter = request.GET.get("quarter", "").strip()

    grades = (
        Grade.objects.filter(student=student)
        .select_related("subject", "grading_period", "school_year")
        .order_by("-school_year__name", "-grading_period__order", "subject__name")
    )

    # Search by subject name or code
    if query:
        grades = grades.filter(
            Q(subject__name__icontains=query) | Q(subject__code__icontains=query)
        )

    # Filter by selected quarter
    if quarter_filter:
        grades = grades.filter(grading_period_id=quarter_filter)

    # Group grades by school year and grading period (quarter)
    quarter_groups = []
    for key, group in groupby(
        grades, key=lambda g: (g.school_year, g.grading_period)
    ):
        quarter_groups.append(
            {
                "school_year": key[0],
                "grading_period": key[1],
                "grades": list(group),
            }
        )

    # Paginate by quarter group (one quarter per page)
    paginator = Paginator(quarter_groups, 1)
    page = request.GET.get("page", 1)
    quarter_page = paginator.get_page(page)

    # Distinct quarters for the dropdown (based on all student grades)
    available_quarters = (
        Grade.objects.filter(student=student)
        .select_related("grading_period", "school_year")
        .values_list("grading_period_id", "grading_period__name", "school_year__name")
        .distinct()
        .order_by("-school_year__name", "grading_period__order")
    )

    return render(
        request,
        "students/student_detail.html",
        {
            "student": student,
            "quarter_page": quarter_page,
            "available_quarters": available_quarters,
            "query": query,
            "quarter_filter": quarter_filter,
        },
    )


@registrar_or_admin_required
def student_export(request):
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="students_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['LRN', 'First Name', 'Middle Name', 'Last Name', 'Suffix', 'Sex', 'Birthdate', 'Birthplace', 'Address', 'Grade Level', 'Section', 'Status', 'Parent Name', 'Parent Phone'])
    
    students = Student.objects.select_related('grade_level', 'section').all()
    
    for student in students:
        writer.writerow([
            student.lrn,
            student.first_name,
            student.middle_name,
            student.last_name,
            student.suffix,
            student.get_sex_display(),
            student.birthdate,
            student.birthplace,
            student.address,
            student.grade_level,
            student.section,
            student.get_status_display(),
            student.parent_name,
            student.parent_phone,
        ])
    
    return response


@login_required
def student_dashboard(request):
    """Dashboard for student users showing their own grades and records."""
    if not request.user.is_student_user:
        messages.error(request, "Access denied.")
        return redirect("dashboard:index")
    
    if not request.user.student_profile:
        messages.error(request, "No student profile linked to this account.")
        return redirect("dashboard:index")
    
    student = request.user.student_profile
    grades = (
        Grade.objects.filter(student=student, status__in=['validated', 'locked'])
        .select_related("subject", "grading_period", "school_year")
        .order_by("-school_year__name", "-grading_period__order", "subject__name")
    )
    
    return render(request, "students/student_dashboard.html", {
        "student": student,
        "grades": grades,
    })
