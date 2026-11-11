from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_index, name='index'),
    path('sf6/', views.sf6_report, name='sf6'),
    path('grade-trends/', views.grade_trends, name='grade_trends'),
    path('section-performance/', views.section_performance, name='section_performance'),
    path('subject-performance/', views.subject_performance, name='subject_performance'),
    path('at-risk-students/', views.at_risk_students, name='at_risk_students'),
    path('student-history/<int:student_pk>/', views.student_history, name='student_history'),
    path('report-cards/', views.report_card_select, name='report_card_select'),
    path('report-card/<int:student_pk>/', views.report_card, name='report_card'),
    path('report-card/<int:student_pk>/pdf/', views.report_card_pdf, name='report_card_pdf'),
    path('templates/', views.report_templates, name='report_templates'),
    path('class-record/', views.class_record, name='class_record'),
    path('class-summary/', views.class_summary, name='class_summary'),
]
