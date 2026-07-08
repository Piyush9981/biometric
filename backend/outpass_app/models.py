from django.db import models
from django.utils import timezone


class student_master(models.Model):
    HOSTEL_CHOICES = [
        ('Hostel A', 'Hostel A'),
        ('Hostel B', 'Hostel B'),
        ('Hostel C', 'Hostel C'),
        ('Hostel D', 'Hostel D'),
        ('Hostel E', 'Hostel E'),
    ]
    student_id = models.CharField(max_length=50, primary_key=True)
    student_name = models.CharField(max_length=150, db_index=True)
    mobile_no = models.CharField(max_length=15)
    department = models.CharField(max_length=150)
    course = models.CharField(max_length=150)
    semester = models.IntegerField()
    hostel_name = models.CharField(max_length=100, choices=HOSTEL_CHOICES)
    email = models.EmailField(blank=True, null=True)
    profile_image = models.ImageField(
        upload_to='student_profiles/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'student_master'

    def __str__(self):
        return f"{self.student_name} ({self.student_id})"

    @property
    def scholar_id(self):
        return self.student_id

    @property
    def mobile_number(self):
        return self.mobile_no

    @property
    def biometric_status(self):
        latest_req = outpass_request.objects.filter(
            student_id=self).order_by('-requested_at').first()
        if latest_req and latest_req.request_status == 'OUT':
            return 'OUT'
        return 'IN'


class system_user(models.Model):
    user_id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    contact = models.CharField(max_length=15)
    profile_picture = models.ImageField(
        upload_to='user_profiles/', null=True, blank=True)
    user_name = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=255)
    department = models.CharField(max_length=150)
    hostel_name = models.CharField(max_length=100)
    gate_name = models.CharField(max_length=100, default='N/A')
    role = models.CharField(max_length=50)  # Super Admin, Warden, Gatekeeper
    allowed_purposes = models.CharField(max_length=255, default='Emergency,Sunday Outing')
    is_first_login = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'system_user'

    def __str__(self):
        return f"{self.user_name} - {self.role}"


class outpass_request(models.Model):
    STATUS_CHOICES = [
        ('Initiate', 'Initiate'),
        ('Approved', 'Approved'),
        ('ACCEPTED', 'ACCEPTED'),
        ('Accept', 'Accept'),
        ('Decline', 'Decline'),
        ('Reject', 'Reject'),
        ('OUT', 'OUT'),
        ('IN', 'IN'),
        ('TIME_OUT', 'TIME_OUT'),
        ('Time out', 'Time out'),
        ('TIME OUT', 'TIME OUT'),
        ('TIMEOUT_PROCESSED', 'TIME OUT'),
    ]


    PURPOSE_CHOICES = [
        ('Medical', 'Medical'),
        ('Personal', 'Personal'),
        ('Education leave', 'Education leave'),
        ('Sunday Outing', 'Sunday Outing'),
        ('Semester Break', 'Semester Break'),
        ('Emergency', 'Emergency'),
    ]

    request_id = models.AutoField(primary_key=True)
    student_id = models.ForeignKey(
        student_master,
        on_delete=models.CASCADE,
        db_column='student_id')
    requested_exit_datetime = models.DateTimeField()
    actual_exit_datetime = models.DateTimeField(null=True, blank=True)
    requested_entry_datetime = models.DateTimeField()
    actual_entry_datetime = models.DateTimeField(null=True, blank=True)
    outing_reason = models.CharField(max_length=255, choices=PURPOSE_CHOICES)
    destination = models.CharField(max_length=255)
    leave_reason = models.TextField(blank=True, null=True)
    parent_confirmed = models.BooleanField(default=False)
    note = models.TextField(blank=True, null=True)
    request_status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='Initiate',
        db_index=True)
    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    early_grace = models.IntegerField(default=0)
    late_grace = models.IntegerField(default=0)
    # Could be user_name of the Warden
    requested_by = models.CharField(max_length=100)
    approved_by = models.CharField(max_length=100, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    recovery_attempts = models.IntegerField(default=0)
    recovery_started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'outpass_request'

    def __str__(self):
        return f"Request {self.request_id} for {self.student_id.student_id}"

    @property
    def warden_contact(self):
        if self.approved_by:
            user = system_user.objects.filter(user_name=self.approved_by).first()
            if user:
                return user.contact
        return 'N/A'

    @property
    def timeout_state(self):
        if self.request_status not in ['Time out', 'TIME_OUT', 'TIME OUT']:
            return None
        if self.recovery_attempts == 0:
            if self.terminated_at is None:
                return 'Recovery Available'
            else:
                return 'Recovery Window Expired'
        else:
            return 'Second Timeout After Recovery'



class RolePermission(models.Model):
    role = models.CharField(max_length=50, unique=True)
    can_view_students = models.BooleanField(default=True)
    can_view_details = models.BooleanField(default=True)
    can_approve = models.BooleanField(default=True)  # Used for Warden
    allowed_purposes = models.CharField(max_length=255, default='All') # Used for Warden
    can_mark_out = models.BooleanField(default=True) # Used for Gatekeeper
    can_mark_in = models.BooleanField(default=True)  # Used for Gatekeeper

    class Meta:
        db_table = 'role_permission'

    def __str__(self):
        return f"Permissions for {self.role}"
