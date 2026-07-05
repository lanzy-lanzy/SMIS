from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    path('', views.academics_index, name='index'),
    path('school-years/', views.school_year_list, name='school_year_list'),
    path('school-years/create/', views.school_year_create, name='school_year_create'),
    path('school-years/<int:pk>/edit/', views.school_year_edit, name='school_year_edit'),
    path('school-years/<int:pk>/delete/', views.school_year_delete, name='school_year_delete'),
    path('grade-levels/', views.grade_level_list, name='grade_level_list'),
    path('grade-levels/create/', views.grade_level_create, name='grade_level_create'),
    path('grade-levels/<int:pk>/edit/', views.grade_level_edit, name='grade_level_edit'),
    path('grade-levels/<int:pk>/delete/', views.grade_level_delete, name='grade_level_delete'),
    path('sections/', views.section_list, name='section_list'),
    path('sections/create/', views.section_create, name='section_create'),
    path('sections/<int:pk>/edit/', views.section_edit, name='section_edit'),
    path('sections/<int:pk>/delete/', views.section_delete, name='section_delete'),
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    path('subjects/<int:pk>/edit/', views.subject_edit, name='subject_edit'),
    path('subjects/<int:pk>/delete/', views.subject_delete, name='subject_delete'),
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/create/', views.assignment_create, name='assignment_create'),
    path('assignments/<int:pk>/edit/', views.assignment_edit, name='assignment_edit'),
    path('assignments/<int:pk>/delete/', views.assignment_delete, name='assignment_delete'),
    path('assignments/bulk-create/', views.assignment_bulk_create, name='assignment_bulk_create'),
    path('assignments/export/', views.assignment_export, name='assignment_export'),
    path('grading-periods/', views.grading_period_list, name='grading_period_list'),
    path('grading-periods/create/', views.grading_period_create, name='grading_period_create'),
    path('grading-periods/<int:pk>/toggle-submissions/', views.grading_period_toggle_submissions, name='grading_period_toggle_submissions'),
    path('grading-periods/<int:pk>/toggle-current/', views.grading_period_toggle_current, name='grading_period_toggle_current'),
]
