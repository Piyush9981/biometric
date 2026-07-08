from django.urls import path, include
from rest_framework.routers import DefaultRouter
from biometric.api.machine_api import MachineViewSet, machine_status_view, trigger_sync_view
from biometric.api.verification_api import (
    PendingVerificationListCreateView,
    VerifiedVerificationListView,
    TimeoutVerificationListView,
    verify_request_api_view
)
from biometric.api.attendance_api import AttendanceLogListView

router = DefaultRouter()
router.register(r'machine', MachineViewSet, basename='machine')

urlpatterns = [
    path('', include(router.urls)),
    path('status/', machine_status_view, name='machine-status'),
    path('sync/', trigger_sync_view, name='trigger-sync'),
    path('pending/', PendingVerificationListCreateView.as_view(), name='pending-verifications'),
    path('verified/', VerifiedVerificationListView.as_view(), name='verified-verifications'),
    path('timeouts/', TimeoutVerificationListView.as_view(), name='timeout-verifications'),
    path('attendance/', AttendanceLogListView.as_view(), name='attendance-logs'),
    path('verify/', verify_request_api_view, name='verify-request'),
]
