"""
BLU Projects - URL Configuration
"""
from django.urls import path
from . import views

app_name = 'blu_projects'

urlpatterns = [
    # Projects Home
    path('', views.projects_home, name='projects_home'),
    
    # Projects
    path('all/', views.projects_list, name='projects_list'),
    path('create/', views.project_create, name='project_create'),
    path('<int:project_id>/', views.project_detail, name='project_detail'),
    path('<int:project_id>/edit/', views.project_edit, name='project_edit'),
    path('<int:project_id>/gantt/', views.project_gantt, name='project_gantt'),
    path('<int:project_id>/reports/', views.project_reports, name='project_reports'),
    
    # Tasks
    path('<int:project_id>/tasks/create/', views.task_create, name='task_create'),
    path('tasks/<int:task_id>/', views.task_detail, name='task_detail'),
    path('tasks/<int:task_id>/edit/', views.task_edit, name='task_edit'),
    path('tasks/<int:task_id>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:task_id>/update-status/', views.task_update_status, name='task_update_status'),
    path('tasks/my-tasks/', views.my_tasks, name='my_tasks'),
    
    # Time Tracking
    path('tasks/<int:task_id>/log-time/', views.time_entry_create, name='time_entry_create'),
    path('time-entries/<int:entry_id>/edit/', views.time_entry_edit, name='time_entry_edit'),
    path('time-entries/<int:entry_id>/delete/', views.time_entry_delete, name='time_entry_delete'),
    
    # Milestones
    path('<int:project_id>/milestones/create/', views.milestone_create, name='milestone_create'),
    path('milestones/<int:milestone_id>/edit/', views.milestone_edit, name='milestone_edit'),
    path('milestones/<int:milestone_id>/delete/', views.milestone_delete, name='milestone_delete'),
    
    # Documents
    path('<int:project_id>/documents/upload/', views.document_upload, name='document_upload'),
    path('documents/<int:document_id>/delete/', views.document_delete, name='document_delete'),
    
    # Project Actions
    path('<int:project_id>/delete/', views.project_delete, name='project_delete'),
    path('<int:project_id>/archive/', views.project_archive, name='project_archive'),
    
    # Views
    path('timeline/', views.timeline_view, name='timeline'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('reports/', views.reports_view, name='reports'),
    
    # Settings
    path('team/', views.team_management, name='team'),
    path('settings/', views.project_settings, name='settings'),
    
    # Client Portal
    path('client-portal/', views.client_portal_home, name='client_portal_home'),
    path('client-portal/project/<int:project_id>/', views.client_project_view, name='client_project_view'),
    
    # Issues
    path('<int:project_id>/issues/', views.issue_list, name='issue_list'),
    path('<int:project_id>/issues/create/', views.issue_create, name='issue_create'),
    path('issues/<int:issue_id>/', views.issue_detail, name='issue_detail'),
    path('issues/<int:issue_id>/comment/', views.issue_add_comment, name='issue_add_comment'),
    path('issues/<int:issue_id>/update-status/', views.issue_update_status, name='issue_update_status'),
    path('issues/<int:issue_id>/attach/', views.issue_attach_file, name='issue_attach_file'),
    
    # SLA Management
    path('<int:project_id>/sla/', views.sla_view, name='sla_view'),
    path('<int:project_id>/sla/create/', views.sla_create, name='sla_create'),
    path('<int:project_id>/sla/edit/', views.sla_edit, name='sla_edit'),
    path('sla-dashboard/', views.sla_dashboard, name='sla_dashboard'),

    # Risk Register
    path('<int:project_id>/risks/create/', views.risk_create, name='risk_create'),
    path('risks/<int:risk_id>/edit/', views.risk_edit, name='risk_edit'),
    path('risks/<int:risk_id>/delete/', views.risk_delete, name='risk_delete'),

    # Stakeholder Register
    path('<int:project_id>/stakeholders/create/', views.stakeholder_create, name='stakeholder_create'),
    path('stakeholders/<int:stakeholder_id>/edit/', views.stakeholder_edit, name='stakeholder_edit'),
    path('stakeholders/<int:stakeholder_id>/delete/', views.stakeholder_delete, name='stakeholder_delete'),
]
