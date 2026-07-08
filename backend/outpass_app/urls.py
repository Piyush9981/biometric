from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('super-admin/', views.superadmin_dashboard, name='superadmin_dashboard'),
    path('timeouts/', views.timeouts_view, name='timeouts'),
    path('gatekeeper/', views.gatekeeper_dashboard, name='gatekeeper_dashboard'),
    path('biometric/diagnostics/', views.biometric_diagnostics, name='biometric_diagnostics'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Students
    path('students/', views.students_view, name='students'),
    path('api/student/create/', views.api_create_student, name='api_create_student'),
    path('api/student/update/', views.api_update_student, name='api_update_student'),
    path('api/student/delete/', views.api_delete_student, name='api_delete_student'),
    path('api/student/<str:scholar_id>/', views.student_lookup, name='student_lookup'),
    
    # Outpass Request
    path('api/request/create/', views.create_request, name='create_request'),
    path('api/request/warden-approve/', views.api_warden_approve, name='api_warden_approve'),
    path('api/request/configure-approve/', views.api_configure_approve, name='api_configure_approve'),
    path('api/request/reconfigure-grace/', views.api_reconfigure_grace, name='api_reconfigure_grace'),
    path('api/request/registrar-decline/', views.api_registrar_decline, name='api_registrar_decline'),
    
    # Gatekeeper Actions
    path('api/outpass/send-to-biometric/', views.api_send_to_biometric, name='api_send_to_biometric'),
    path('api/outpass/gatekeeper-mark-out/', views.api_gatekeeper_mark_out, name='api_gatekeeper_mark_out'),
    path('api/outpass/gatekeeper-mark-in/', views.api_gatekeeper_mark_in, name='api_gatekeeper_mark_in'),
    path('api/biometric-scan/', views.api_biometric_scan, name='api_biometric_scan'),
    
    # History
    path('history/', views.history_view, name='history'),
    path('api/history/', views.api_all_history, name='api_all_history'),
    path('api/student/<str:scholar_id>/history/', views.student_history, name='student_history'),
    
    # User Management
    path('super-admin/users/', views.user_management, name='user_management'),
    path('api/user/create/', views.api_create_user, name='api_create_user'),
    path('api/user/update/', views.api_update_user, name='api_update_user'),
    path('api/user/delete/', views.api_delete_user, name='api_delete_user'),
    path('api/user/reset-password/', views.api_reset_password, name='api_reset_password'),
    path('api/user/warden-first-login/', views.api_warden_first_login_setup, name='api_warden_first_login_setup'),
    path('api/change-password/', views.api_change_password, name='api_change_password'),
    
    # Global Permissions
    path('super-admin/permissions/', views.permissions_view, name='permissions'),
    path('api/permissions/', views.api_permissions, name='api_permissions'),

    # Real-Time Polling APIs
    path('api/dashboard/warden/updates/', views.api_warden_updates, name='api_warden_updates'),
    path('api/dashboard/gatekeeper/updates/', views.api_gatekeeper_updates, name='api_gatekeeper_updates'),
    path('api/dashboard/biometric/queue/updates/', views.api_biometric_queue_updates, name='api_biometric_queue_updates'),
    path('api/dashboard/biometric/machines/updates/', views.api_biometric_machines_updates, name='api_biometric_machines_updates'),
]

