from django.db import models

class Machine(models.Model):
    STATUS_CHOICES = [
        ('ONLINE', 'Online'),
        ('OFFLINE', 'Offline'),
        ('UNKNOWN', 'Unknown'),
    ]

    machine_name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField(default=4370)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNKNOWN')
    last_connected = models.DateTimeField(blank=True, null=True)
    last_attendance_time = models.DateTimeField(
        blank=True, 
        null=True, 
        help_text="Timestamp of the last synced attendance log from this machine"
    )
    
    # Configurable settings
    connection_timeout = models.IntegerField(default=5, help_text="Connection timeout in seconds")
    polling_interval = models.IntegerField(default=60, help_text="Sync interval in seconds")
    auto_sync_enabled = models.BooleanField(default=True, help_text="True if automated sync is enabled")
    machine_enabled = models.BooleanField(default=True, help_text="True if this machine is active")
    last_successful_sync = models.DateTimeField(blank=True, null=True, help_text="Timestamp of the last successful synchronization")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.machine_name} ({self.ip_address})"


class BiometricUser(models.Model):
    student = models.ForeignKey('outpass_app.student_master', on_delete=models.CASCADE, null=True, blank=True, db_column='student_id', related_name='biometric_users')
    machine_uid = models.IntegerField(help_text="UID index assigned by the biometric device")
    user_id = models.CharField(max_length=50, unique=True, help_text="User ID string defined on the biometric device")
    name = models.CharField(max_length=150)
    card_number = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (Student ID: {self.student_id})"


class AttendanceLog(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='attendance_logs')
    student = models.ForeignKey('outpass_app.student_master', on_delete=models.SET_NULL, blank=True, null=True, db_column='student_id', related_name='attendance_logs')
    machine_uid = models.IntegerField(blank=True, null=True, help_text="Raw machine UID")
    verify_type = models.IntegerField(help_text="Verification mode (e.g. fingerprint, face, card, password)")
    attendance_time = models.DateTimeField()
    processed = models.BooleanField(default=False, help_text="True if successfully processed against the verification queue")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-attendance_time']
        unique_together = ('machine', 'machine_uid', 'attendance_time')

    def __str__(self):
        return f"User {self.machine_uid} at {self.attendance_time} on {self.machine.machine_name}"


class PendingBiometricVerification(models.Model):
    STATUS_CHOICES = [
        ('WAITING', 'Waiting'),
        ('ACCEPTED', 'Accepted'),
        ('TIME_OUT', 'Timed Out'),
        ('FAILED', 'Failed'),
        ('OUT', 'OUT'),
        ('READY_FOR_IN', 'READY_FOR_IN'),
    ]

    request = models.OneToOneField('outpass_app.outpass_request', on_delete=models.CASCADE, db_column='request_id', related_name='biometric_verification', primary_key=True)
    student = models.ForeignKey('outpass_app.student_master', on_delete=models.CASCADE, db_column='student_id', related_name='biometric_verifications')
    approved_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    verification_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='WAITING')
    verified_at = models.DateTimeField(blank=True, null=True)
    timed_out_at = models.DateTimeField(blank=True, null=True, help_text="Timestamp when the request timed out")
    attendance_log = models.ForeignKey(
        AttendanceLog, 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True, 
        related_name='verifications'
    )
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['approved_at']

    def __str__(self):
        return f"Request {self.request_id} for Student {self.student_id} ({self.verification_status})"


class SyncHistory(models.Model):
    SYNC_TYPES = [
        ('USERS', 'Users Sync'),
        ('LOGS', 'Attendance Logs Sync'),
    ]
    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='sync_histories')
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    total_records = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.sync_type} sync for {self.machine.machine_name} at {self.started_at} ({self.status})"
