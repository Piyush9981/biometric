from django.contrib import admin
from biometric.models import Machine, BiometricUser, AttendanceLog, PendingBiometricVerification, SyncHistory

@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = (
        'machine_name', 
        'ip_address', 
        'port', 
        'status', 
        'machine_enabled', 
        'auto_sync_enabled', 
        'connection_timeout', 
        'polling_interval', 
        'last_connected', 
        'last_successful_sync'
    )
    list_filter = ('status', 'machine_enabled', 'auto_sync_enabled')
    search_fields = ('machine_name', 'ip_address', 'serial_number')
    fieldsets = (
        ('Basic Information', {
            'fields': ('machine_name', 'ip_address', 'port', 'location', 'serial_number')
        }),
        ('Status', {
            'fields': ('status', 'last_connected', 'last_attendance_time', 'last_successful_sync')
        }),
        ('Configuration Settings', {
            'fields': ('machine_enabled', 'auto_sync_enabled', 'connection_timeout', 'polling_interval')
        }),
    )
    readonly_fields = ('last_connected', 'last_attendance_time', 'last_successful_sync', 'status')


@admin.register(BiometricUser)
class BiometricUserAdmin(admin.ModelAdmin):
    list_display = ('name', 'student_id', 'user_id', 'machine_uid', 'card_number', 'is_active', 'last_sync')
    list_filter = ('is_active',)
    search_fields = ('name', 'user_id', 'card_number')


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ('machine', 'student_id', 'machine_uid', 'verify_type', 'attendance_time', 'processed')
    list_filter = ('processed', 'machine', 'verify_type')
    search_fields = ('student_id', 'machine_uid')


@admin.register(PendingBiometricVerification)
class PendingBiometricVerificationAdmin(admin.ModelAdmin):
    list_display = ('request_id', 'student_id', 'approved_at', 'expires_at', 'verification_status', 'verified_at', 'timed_out_at')
    list_filter = ('verification_status',)
    search_fields = ('request_id', 'student_id')


@admin.register(SyncHistory)
class SyncHistoryAdmin(admin.ModelAdmin):
    list_display = ('machine', 'sync_type', 'started_at', 'completed_at', 'total_records', 'status')
    list_filter = ('sync_type', 'status', 'machine')
    search_fields = ('remarks',)
