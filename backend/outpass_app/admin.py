from django.contrib import admin
from .models import student_master, system_user, outpass_request

@admin.register(student_master)
class StudentMasterAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'student_name', 'department', 'hostel_name')

@admin.register(system_user)
class SystemUserAdmin(admin.ModelAdmin):
    list_display = ('user_name', 'role', 'created_at')

@admin.register(outpass_request)
class OutpassRequestAdmin(admin.ModelAdmin):
    list_display = ('request_id', 'student_id', 'request_status', 'requested_exit_datetime')
