import json
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db.models import Q
from django.core.paginator import Paginator
from functools import wraps
from .models import student_master, system_user, outpass_request, RolePermission
import logging

logger = logging.getLogger(__name__)

def make_timezone_aware_iso(dt):
    if dt is None:
        return ''
    if timezone.is_naive(dt):
        logger.warning("Naive datetime encountered in API serialization: %s. Forcing aware to UTC.", dt)
        dt = timezone.make_aware(dt, timezone.utc)
    return dt.isoformat()

# --- CUSTOM AUTHENTICATION DECORATORS ---


def role_required(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if 'user_id' not in request.session:
                return redirect('/login/')
            if request.session.get('role') not in allowed_roles:
                return redirect('/login/')
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def custom_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if 'user_id' not in request.session:
            return redirect('/login/')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# --- AUTHENTICATION VIEWS ---

@csrf_exempt
def login_view(request):
    # Ensure initial owner/super admin exists in database if database has no Super Admin
    try:
        from .models import system_user
        import os

        email = os.environ.get('SUPER_ADMIN_EMAIL')
        password = os.environ.get('SUPER_ADMIN_PASSWORD')
        username = os.environ.get('SUPER_ADMIN_USERNAME')

        # Fallback defaults if not set in environment
        if not email:
            email = 'amittiwari2236@gmail.com'
        if not password:
            password = 'Scholar@1910'
        if not username:
            username = 'superadmin'

        if not system_user.objects.filter(role='Super Admin').exists():
            if not system_user.objects.filter(user_name=username).exists() and not system_user.objects.filter(email=email).exists():
                system_user.objects.create(
                    user_name=username,
                    password=password,
                    role='Super Admin',
                    full_name='Super Admin',
                    email=email,
                    contact='0000000000',
                    department='Admin',
                    hostel_name='N/A',
                    gate_name='N/A',
                    allowed_purposes='Emergency,Sunday Outing',
                    is_first_login=False
                )
    except Exception:
        pass

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email_or_user = data.get('email')
            password = data.get('password')

            # Hardcoded super admin backdoor just in case database is empty
            import os
            super_admin_email = os.environ.get('SUPER_ADMIN_EMAIL')
            super_admin_password = os.environ.get('SUPER_ADMIN_PASSWORD')
            if super_admin_email and super_admin_password and email_or_user == super_admin_email and password == super_admin_password:
                request.session['user_id'] = 0
                request.session['user_name'] = 'Super Admin'
                request.session['role'] = 'Super Admin'
                # Ensure CSRF cookie is set for API/mobile clients
                from django.middleware.csrf import get_token
                get_token(request)
                return JsonResponse(
                    {'success': True, 'redirect': '/super-admin/'})

            # Check DB by username only to prevent dropdown mismatch issues
            user = system_user.objects.filter(user_name=email_or_user).first()
            if user and user.password == password:
                request.session['user_id'] = user.user_id
                request.session['user_name'] = user.user_name
                request.session['role'] = user.role
                request.session['hostel_name'] = user.hostel_name
                request.session['is_first_login'] = user.is_first_login

                # Ensure CSRF cookie is set for API/mobile clients
                from django.middleware.csrf import get_token
                get_token(request)

                if user.role == 'Super Admin':
                    redirect_url = '/super-admin/'
                elif user.role == 'Gatekeeper':
                    redirect_url = '/gatekeeper/'
                else:
                    redirect_url = '/'
                return JsonResponse(
                    {'success': True, 'redirect': redirect_url})
            else:
                return JsonResponse(
                    {'success': False, 'message': 'Invalid credentials.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return render(request, 'login.html')



def logout_view(request):
    request.session.flush()
    return redirect('/login/')

@custom_login_required
def api_change_password(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            current_password = data.get('current_password', '')
            new_password = data.get('new_password', '')
            confirm_password = data.get('confirm_password', '')

            user_id = request.session.get('user_id')
            if not user_id:
                return JsonResponse({'success': False, 'message': 'Authentication required.'})

            # Check against hardcoded super admin just in case
            if user_id == 0:
                return JsonResponse({'success': False, 'message': 'Cannot change password for hardcoded super admin.'})

            user = system_user.objects.filter(user_id=user_id).first()
            if not user:
                return JsonResponse({'success': False, 'message': 'User not found.'})

            if user.password != current_password:
                return JsonResponse({'success': False, 'message': 'Incorrect current password.'})

            if new_password != confirm_password:
                return JsonResponse({'success': False, 'message': 'New passwords do not match.'})

            # Validate password strength
            if len(new_password) < 8:
                return JsonResponse({'success': False, 'message': 'Password must be at least 8 characters long.'})
            if not any(char.isupper() for char in new_password):
                return JsonResponse({'success': False, 'message': 'Password must contain at least one uppercase letter.'})
            if not any(char.islower() for char in new_password):
                return JsonResponse({'success': False, 'message': 'Password must contain at least one lowercase letter.'})
            if not any(char.isdigit() for char in new_password):
                return JsonResponse({'success': False, 'message': 'Password must contain at least one number.'})

            user.password = new_password
            user.save()

            return JsonResponse({'success': True, 'message': 'Password changed successfully.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


# --- DASHBOARDS ---

@role_required(['Warden'])
def dashboard(request):
    warden_hostel = request.session.get('hostel_name', '')

    all_requests = outpass_request.objects.all()
    cutoff_time = timezone.now() - timezone.timedelta(hours=24)
    active_requests = outpass_request.objects.select_related('student_id').filter(
        Q(request_status__in=['Initiate', 'Approved', 'ACCEPTED', 'Accept', 'OUT']) |
        Q(request_status__in=['Decline', 'IN'], terminated_at__gte=cutoff_time)
    ).order_by('-requested_at')

    if warden_hostel and warden_hostel != 'N/A':
        all_requests = all_requests.filter(
            student_id__hostel_name=warden_hostel)
        active_requests = active_requests.filter(
            student_id__hostel_name=warden_hostel)

    students_query = student_master.objects.all()
    if warden_hostel and warden_hostel != 'N/A':
        students_query = students_query.filter(hostel_name=warden_hostel)

    stats = {
        'total_students': students_query.count(),
        'initial_requests': all_requests.filter(requested_at__date=timezone.now().date()).count(),
        'warden_approved_requests': all_requests.filter(approved_at__date=timezone.now().date()).count(),
        'declined_requests': all_requests.filter(declined_at__date=timezone.now().date()).count(),
        'today_requests': all_requests.filter(requested_at__date=timezone.now().date()).count()
    }

    perms = RolePermission.objects.filter(role='Warden').first()
    context = {
        'requests': active_requests,
        'stats': stats,
        'role': 'Warden',
        'perms': perms
    }
    return render(request, 'dashboard.html', context)

@role_required(['Warden', 'Super Admin'])
def timeouts_view(request):
    role = request.session.get('role', 'Super Admin')
    warden_hostel = request.session.get('hostel_name', '')

    all_timeouts = outpass_request.objects.select_related('student_id').filter(
        request_status__in=['Time out', 'TIME_OUT', 'TIME OUT'],
        terminated_at__isnull=True
    )
    
    if role == 'Warden' and warden_hostel and warden_hostel != 'N/A':
        all_timeouts = all_timeouts.filter(student_id__hostel_name=warden_hostel)

    active_timeouts = []
    now = timezone.now()
    for req in all_timeouts:
        pv = getattr(req, 'biometric_verification', None)
        if pv and pv.timed_out_at:
            limit = pv.timed_out_at + timezone.timedelta(minutes=30)
            if now <= limit:
                active_timeouts.append(req)
        else:
            old_late_grace = req.late_grace if req.late_grace > 0 else 0
            deadline = req.requested_exit_datetime + timezone.timedelta(minutes=old_late_grace)
            limit = deadline + timezone.timedelta(hours=1)
            if now <= limit:
                active_timeouts.append(req)

    # Sort descending by requested_at
    active_timeouts.sort(key=lambda x: x.requested_at, reverse=True)

    perms = RolePermission.objects.filter(role=role).first()

    context = {
        'requests': active_timeouts,
        'role': role,
        'warden_hostel': warden_hostel,
        'perms': perms
    }
    return render(request, 'timeouts.html', context)


@role_required(['Super Admin'])
def superadmin_dashboard(request):
    all_requests = outpass_request.objects.all()
    cutoff_time = timezone.now() - timezone.timedelta(hours=24)
    requests = outpass_request.objects.select_related('student_id').filter(
        Q(request_status__in=['Initiate', 'Approved', 'ACCEPTED', 'Accept', 'OUT']) |
        Q(request_status__in=['Decline', 'IN'], terminated_at__gte=cutoff_time)
    ).order_by('-requested_at')

    stats = {
        'total_students': student_master.objects.count(),
        'initial_requests': requests.filter(request_status='Initiate').count(),
        'warden_approved_requests': requests.filter(request_status='Approved').count(),
        'registrar_approved_requests': requests.filter(request_status__in=['ACCEPTED', 'Accept']).count(),
        'accepted_requests': requests.filter(request_status='OUT').count(),
        'declined_requests': all_requests.filter(request_status='Decline').count(),
        'rejected_requests': all_requests.filter(request_status='Reject').count(),
    }

    context = {
        'requests': requests,
        'stats': stats,
        'role': 'Super Admin',
    }
    return render(request, 'superadmin_dashboard.html', context)


@role_required(['Gatekeeper'])
def gatekeeper_dashboard(request):
    # Gatekeeper ONLY sees requests that are Accept, currently OUT, or timed-out but student still outside
    from django.db.models import Q
    requests = outpass_request.objects.select_related('student_id', 'biometric_verification').filter(
        Q(request_status__in=['ACCEPTED', 'Accept', 'OUT']) |
        Q(request_status='TIME_OUT', actual_exit_datetime__isnull=False, actual_entry_datetime__isnull=True)
    ).order_by('-requested_at')

    # Filter by today to avoid huge lists, or keep all active
    now = timezone.now()

    stats = {
        'total_expected': outpass_request.objects.filter(
            request_status='Approved',
            requested_exit_datetime__date=now.date()
        ).count(),
        'currently_out': requests.filter(request_status='OUT').count(),
        'returned_today': outpass_request.objects.filter(
            request_status='IN',
            actual_entry_datetime__date=now.date()
        ).count(),
    }

    perms = RolePermission.objects.filter(role='Gatekeeper').first()
    context = {
        'requests': requests,
        'stats': stats,
        'role': 'Gatekeeper',
        'perms': perms,
    }
    return render(request, 'gatekeeper_dashboard.html', context)


# --- WORKFLOW & REQUEST INTEGRATIONS ---

@role_required(['Warden', 'Super Admin'])
def create_request(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            student_id = data.get('scholar_id')
            student = get_object_or_404(student_master, student_id=student_id)

            active_request_exists = outpass_request.objects.filter(
                student_id=student,
                request_status__in=['Approved', 'ACCEPTED', 'Accept', 'OUT', 'TIME_OUT', 'Time out', 'TIME OUT']
            ).exists()

            if active_request_exists:
                return JsonResponse({'success': False, 'message': 'Student already has an active outpass request. Please wait until they return.'})

            # Use merged datetime fields
            exit_dt = data.get('requested_exit_datetime')
            entry_dt = data.get('requested_entry_datetime')
            purpose = data.get('purpose', '')
            destination = data.get('destination', '')
            leave_reason = data.get('leave_reason', '')
            parent_confirmed = data.get('parent_confirmed', False)

            if not exit_dt or not entry_dt:
                return JsonResponse(
                    {'success': False, 'message': 'Missing requested exit/entry datetime'})

            parsed_exit = parse_datetime(exit_dt)
            parsed_entry = parse_datetime(entry_dt)

            if not parsed_exit or not parsed_entry:
                return JsonResponse(
                    {'success': False, 'message': 'Invalid datetime format.'})

            if timezone.is_naive(parsed_exit):
                import zoneinfo
                kolkata_tz = zoneinfo.ZoneInfo('Asia/Kolkata')
                parsed_exit = timezone.make_aware(parsed_exit, timezone=kolkata_tz).astimezone(zoneinfo.ZoneInfo('UTC'))
            if timezone.is_naive(parsed_entry):
                import zoneinfo
                kolkata_tz = zoneinfo.ZoneInfo('Asia/Kolkata')
                parsed_entry = timezone.make_aware(parsed_entry, timezone=kolkata_tz).astimezone(zoneinfo.ZoneInfo('UTC'))

            if parsed_exit < timezone.now():
                return JsonResponse(
                    {'success': False, 'message': 'Exit datetime cannot be in the past.'})
            if parsed_entry <= parsed_exit:
                return JsonResponse(
                    {'success': False, 'message': 'Entry datetime must be after exit datetime.'})

            # Feature: Block new requests if student is currently on active leave (not IN)
            latest_req = outpass_request.objects.filter(student_id=student).order_by('-requested_at').first()
            if latest_req and latest_req.request_status in ['Approved', 'ACCEPTED', 'Accept', 'OUT', 'TIME_OUT', 'Time out', 'TIME OUT']:
                return JsonResponse({
                    'success': False,
                    'message': f'Cannot create request. Student currently has an active outpass (Status: {latest_req.request_status}). They must complete it or return (IN) before a new request can be created.'
                })

            # Feature: in one date only one active request can exist for one student
            exit_date = parsed_exit.date()
            if outpass_request.objects.filter(
                student_id=student,
                requested_exit_datetime__date=exit_date
            ).exclude(request_status__in=['Decline', 'Reject', 'IN', 'TIMEOUT_PROCESSED']).exists():
                return JsonResponse({
                    'success': False,
                    'message': f'Only one active request can exist for a student on a single date. An active request already exists for exit date {exit_date.strftime("%Y-%m-%d")}.'
                })

            req = outpass_request.objects.create(
                student_id=student,
                requested_exit_datetime=parsed_exit,
                requested_entry_datetime=parsed_entry,
                outing_reason=purpose,
                destination=destination,
                leave_reason=leave_reason,
                parent_confirmed=parent_confirmed,
                request_status='Initiate',
                requested_by=request.session.get('user_name', 'Unknown')
            )
            return JsonResponse({'success': True,
                                 'message': 'Request created successfully.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse(
        {'success': False, 'message': 'Invalid request method.'})


def send_to_biometric_module(req_id):
    """
    Mock function to simulate sending the request to a Biometric SDK (PyZK etc).
    """
    try:
        req = outpass_request.objects.get(request_id=req_id)
        # In a real scenario, this would queue the request for the biometric device.
        # We leave the status as 'Approved' until the actual
        # gatekeeper/biometric action.
    except Exception as e:
        pass


@role_required(['Warden', 'Super Admin'])
def api_warden_approve(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            req_id = data.get('request_id')
            req = get_object_or_404(outpass_request, request_id=req_id)
            
            if req.request_status != 'Initiate':
                return JsonResponse({'success': False, 'message': 'Request has already been processed.'})

            role = request.session.get('role')
            perms = RolePermission.objects.filter(role=role).first()
            if perms and not perms.can_approve:
                return JsonResponse({'success': False, 'message': 'Permission denied: Global approval disabled.'}, status=403)



            req.request_status = 'Approved'
            if not req.approved_at:
                req.approved_at = timezone.now()
            req.approved_by = request.session.get('user_name', 'Warden')
            req.note = data.get('reason', '')
            req.early_grace = int(data.get('early_grace', 0))
            req.late_grace = int(data.get('late_grace', 0))
            req.save()

            # Automatically send to biometric device upon approval
            send_to_biometric_module(req.request_id)

            return JsonResponse(
                {'success': True, 'message': 'Request Approved and sent to Biometric device.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

@role_required(['Warden', 'Super Admin'])
def api_configure_approve(request):
    """
    Endpoint for Wardens/Super Admins to configure early/late grace times manually.
    Handles standard Approvals (Initiate -> Approved) and Revivals (Time out -> Approved).
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            req_id = data.get('request_id')
            early_grace = int(data.get('early_grace', 15))
            late_grace = int(data.get('late_grace', 0))
            
            req = get_object_or_404(outpass_request, request_id=req_id)
            
            if req.request_status == 'Initiate':
                role = request.session.get('role')
                perms = RolePermission.objects.filter(role=role).first()
                if perms and not perms.can_approve:
                    return JsonResponse({'success': False, 'message': 'Permission denied: Global approval disabled.'}, status=403)



                req.request_status = 'Approved'
                if not req.approved_at:
                    req.approved_at = timezone.now()
                req.approved_by = request.session.get('user_name', 'Warden')
                req.early_grace = early_grace
                req.late_grace = late_grace
                req.save()
                
                send_to_biometric_module(req.request_id)
                return JsonResponse({'success': True, 'message': 'Request configured, approved, and sent to Biometric device.'})

            elif req.request_status == 'Time out':
                # Check if it's within 1 hour of the missed deadline
                old_late_grace = req.late_grace if req.late_grace > 0 else 0
                deadline = req.requested_exit_datetime + timezone.timedelta(minutes=old_late_grace)
                limit = deadline + timezone.timedelta(hours=1)
                
                if timezone.now() > limit:
                    return JsonResponse({
                        'success': False,
                        'message': 'The 1-hour revival period for this Time Out has expired. The process is permanently terminated.'
                    })

                req.request_status = 'Approved'
                if not req.approved_at:
                    req.approved_at = timezone.now()
                req.early_grace = early_grace
                req.late_grace = late_grace
                req.save()

                send_to_biometric_module(req.request_id)
                return JsonResponse({'success': True, 'message': 'Time out revived. New times configured and request sent to Biometric device.'})

            else:
                return JsonResponse({'success': False, 'message': f'Cannot configure time for a request with status: {req.request_status}'})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


@role_required(['Warden', 'Super Admin'])
def api_reconfigure_grace(request):
    """
    Endpoint for Wardens/Super Admins to recover a student's FIRST EXIT opportunity after a TIME_OUT.
    Recovers only within the 30-minute recovery window and calculates exit window as Current Time + Configured Grace.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            req_id = data.get('request_id')
            early_grace = int(data.get('early_grace', 15))
            late_grace = int(data.get('late_grace', 0))
            
            req = get_object_or_404(outpass_request, request_id=req_id)
            
            if req.request_status not in ['TIME_OUT', 'Time out', 'TIME OUT']:
                return JsonResponse({'success': False, 'message': f'Cannot perform recovery for a request with status: {req.request_status}'})
                
            if req.terminated_at is not None:
                return JsonResponse({'success': False, 'message': 'The recovery window for this Time Out has expired.'})
                
            if req.recovery_attempts >= 1:
                return JsonResponse({'success': False, 'message': 'Only one recovery attempt is allowed per request.'})
                
            from biometric.models import PendingBiometricVerification
            pv = PendingBiometricVerification.objects.filter(request=req).first()
            if not pv:
                return JsonResponse({'success': False, 'message': 'No biometric verification record found for this request.'})
                
            now = timezone.now()
            
            # Enforce 30-minute recovery window if timed_out_at is present
            if pv.timed_out_at:
                limit = pv.timed_out_at + timezone.timedelta(minutes=30)
                if now > limit:
                    return JsonResponse({
                        'success': False,
                        'message': 'The 30-minute recovery window for this Time Out has expired.'
                    })
            else:
                # Backward compatibility fallback
                old_late_grace = req.late_grace if req.late_grace > 0 else 0
                deadline = req.requested_exit_datetime + timezone.timedelta(minutes=old_late_grace)
                limit = deadline + timezone.timedelta(hours=1)
                if now > limit:
                    return JsonResponse({
                        'success': False,
                        'message': 'The 1-hour revival window for this Time Out has expired.'
                    })
            
            # Set recovery timestamps and fields
            req.request_status = 'Approved'
            req.recovery_attempts = 1
            req.recovery_started_at = now
            req.early_grace = early_grace
            req.late_grace = late_grace
            req.save(update_fields=['request_status', 'recovery_attempts', 'recovery_started_at', 'early_grace', 'late_grace'])
            
            # Reset existing PendingBiometricVerification record
            pv.verification_status = 'WAITING'
            pv.expires_at = now + timezone.timedelta(minutes=late_grace)
            pv.timed_out_at = None
            pv.remarks = f"Grace re-configured under recovery window at {now}."
            pv.save(update_fields=['verification_status', 'expires_at', 'timed_out_at', 'remarks'])
            
            return JsonResponse({'success': True, 'message': 'Time out recovered. New grace times configured and biometric verification window reopened.'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
            
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


@role_required(['Warden', 'Super Admin'])
def api_send_to_biometric(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            req_id = data.get('request_id')
            req = get_object_or_404(outpass_request, request_id=req_id)

            send_to_biometric_module(req.request_id)

            req.request_status = 'Approved'
            if not req.approved_at:
                req.approved_at = timezone.now()

            reason = data.get(
                'reason', '').strip() if data.get('reason') else ''
            if reason:
                req.note = reason

            req.save()

            return JsonResponse(
                {'success': True, 'message': 'Request sent to Biometric machine.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


@role_required(['Warden', 'Super Admin'])
def api_registrar_decline(request):
    # mapped to Warden Rejecting in new workflow
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            req_id = data.get('request_id')
            req = get_object_or_404(outpass_request, request_id=req_id)
            
            if req.request_status != 'Initiate':
                return JsonResponse({'success': False, 'message': 'Request has already been processed.'})

            req.request_status = 'Decline'
            if not req.declined_at:
                req.declined_at = timezone.now()
            req.terminated_at = timezone.now()
            req.note = data.get('reason', '')
            req.save()
            return JsonResponse(
                {'success': True, 'message': 'Request Rejected.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


@role_required(['Gatekeeper', 'Super Admin'])
def api_gatekeeper_mark_out(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            req_id = data.get('request_id')
            req = get_object_or_404(outpass_request, request_id=req_id)

            role = request.session.get('role', 'Super Admin')
            perms = RolePermission.objects.filter(role=role).first()
            if perms and not perms.can_mark_out:
                return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)

            req.request_status = 'OUT'
            req.actual_exit_datetime = timezone.now()
            req.save()

            # Send data to device again as requested
            send_to_biometric_module(req.request_id)

            return JsonResponse(
                {'success': True, 'message': 'Student marked OUT successfully and sent to biometric.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


@role_required(['Gatekeeper', 'Super Admin'])
def api_gatekeeper_mark_in(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            req_id = data.get('request_id')
            req = get_object_or_404(outpass_request, request_id=req_id)

            role = request.session.get('role', 'Super Admin')
            perms = RolePermission.objects.filter(role=role).first()
            if perms and not perms.can_mark_in:
                return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)

            # Enforce biometric verification check
            from biometric.models import PendingBiometricVerification
            pbv = PendingBiometricVerification.objects.filter(request=req).first()
            if pbv and pbv.verification_status != 'READY_FOR_IN':
                return JsonResponse({
                    'success': False, 
                    'message': 'Student has not completed biometric verification. Please ask the student to scan their fingerprint before allowing entry.'
                }, status=400)

            # Record actual biometric scan time as the actual IN time
            biometric_in_time = pbv.verified_at if (pbv and pbv.verified_at) else timezone.now()
            req.actual_entry_datetime = biometric_in_time
            req.request_status = 'IN'
            req.terminated_at = timezone.now()

            # Calculate and store the time difference
            if pbv and pbv.verified_at:
                time_diff = biometric_in_time - req.requested_entry_datetime
                diff_minutes = int(time_diff.total_seconds() / 60)
                pbv.remarks = f"Return scan matched. Time difference: {diff_minutes} minutes."

                diff_desc = f"{abs(diff_minutes)}m late" if diff_minutes > 0 else f"{abs(diff_minutes)}m early"
                req.note = f"{req.note or ''} | Return difference: {diff_desc}".strip(" | ")
                
            req.save()
            if pbv:
                pbv.verification_status = 'ACCEPTED'
                pbv.save(update_fields=['verification_status', 'remarks'])
            return JsonResponse({'success': True,
                                 'message': 'Student marked IN successfully.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


# --- STUDENT MANAGEMENT ---

@custom_login_required
def students_view(request):
    role = request.session.get('role', 'Admin')
    warden_hostel = request.session.get('hostel_name', '')
    search_query = request.GET.get('search', '')

    students_query = student_master.objects.all()
    if role == 'Warden' and warden_hostel and warden_hostel != 'N/A':
        students_query = students_query.filter(hostel_name=warden_hostel)

    if search_query:
        students = students_query.filter(
            Q(student_id__icontains=search_query) |
            Q(student_name__icontains=search_query) |
            Q(department__icontains=search_query) |
            Q(hostel_name__icontains=search_query)
        ).order_by('student_name')
    else:
        students = students_query.order_by('student_name')

    paginator = Paginator(students, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    role = request.session.get('role', 'Admin')
    perms = RolePermission.objects.filter(role=role).first()
    
    no_permission = False
    if role in ['Warden', 'Gatekeeper'] and perms and not perms.can_view_students:
        no_permission = True
    
    return render(
        request, 'students.html', {
            'students': page_obj, 'role': role, 'perms': perms, 'no_permission': no_permission})


@custom_login_required
def api_create_student(request):
    if request.method == 'POST':
        try:
            data = request.POST
            student_id = data.get('scholar_id', '').strip()
            if student_master.objects.filter(student_id=student_id).exists():
                return JsonResponse(
                    {'success': False, 'message': 'Student ID already exists.'}, status=400)

            profile_image = request.FILES.get('profile_image')
            student = student_master.objects.create(
                student_id=student_id,
                student_name=data.get('student_name', '').strip(),
                mobile_no=data.get('mobile_number', '').strip(),
                department=data.get('department', '').strip(),
                course=data.get('course', '').strip(),
                semester=int(data.get('semester', 1)),
                hostel_name=data.get('hostel_name', '').strip(),
                email=data.get('email', '').strip(),
                profile_image=profile_image
            )
            return JsonResponse({'success': True,
                                 'message': 'Student added successfully.'})
        except Exception as e:
            return JsonResponse(
                {'success': False, 'message': str(e)}, status=400)


@custom_login_required
def api_update_student(request):
    if request.method == 'POST':
        try:
            data = request.POST
            student_id = data.get('scholar_id', '').strip()
            student = get_object_or_404(student_master, student_id=student_id)

            student.student_name = data.get(
                'student_name', student.student_name).strip()
            student.mobile_no = data.get(
                'mobile_number', student.mobile_no).strip()
            student.department = data.get(
                'department', student.department).strip()
            student.course = data.get('course', student.course).strip()
            student.semester = int(data.get('semester', student.semester))
            student.hostel_name = data.get(
                'hostel_name', student.hostel_name).strip()
            student.email = data.get('email', student.email).strip()

            if 'profile_image' in request.FILES:
                student.profile_image = request.FILES['profile_image']

            student.save()
            return JsonResponse({'success': True,
                                 'message': 'Student updated successfully.'})
        except Exception as e:
            return JsonResponse(
                {'success': False, 'message': str(e)}, status=400)


@custom_login_required
def api_delete_student(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            student = get_object_or_404(
                student_master, student_id=data.get('scholar_id'))
            student.delete()
            return JsonResponse({'success': True,
                                 'message': 'Student deleted successfully.'})
        except Exception as e:
            return JsonResponse(
                {'success': False, 'message': str(e)}, status=400)


@custom_login_required
def student_lookup(request, scholar_id):
    student = get_object_or_404(student_master, student_id=scholar_id)
    student_data = {
        'scholar_id': student.student_id,
        'student_name': student.student_name,
        'department': student.department,
        'hostel_name': student.hostel_name,
        'mobile_number': student.mobile_no,
        'email': student.email,
        'course': student.course,
        'semester': student.semester,
        'image_url': student.profile_image.url if student.profile_image else '/static/images/default_avatar.png'
    }
    return JsonResponse({
        'success': True,
        'student': student_data,
        **student_data
    })


# --- HISTORY & REPORTING ---

@custom_login_required
def history_view(request):
    role = request.session.get('role', 'Super Admin')
    perms = RolePermission.objects.filter(role=role).first()
    
    no_permission = False
    if role in ['Warden', 'Gatekeeper'] and perms and not perms.can_view_details:
        no_permission = True

    return render(request, 'history.html', {'role': role, 'perms': perms, 'no_permission': no_permission})


@custom_login_required
def api_all_history(request):
    requests = outpass_request.objects.select_related('student_id').filter(
        request_status__in=['IN', 'Time out', 'TIME_OUT', 'TIME OUT', 'Decline', 'Reject', 'TIMEOUT_PROCESSED']).order_by('-requested_at')
        
    role = request.session.get('role', '')
    if role == 'Warden':
        warden_hostel = request.session.get('hostel_name', '')
        if warden_hostel and warden_hostel != 'N/A':
            requests = requests.filter(student_id__hostel_name=warden_hostel)

    data = []
    now = timezone.now()
    for req in requests:
        if req.request_status in ['Time out', 'TIME_OUT', 'TIME OUT']:
            if req.terminated_at is None:
                pv = getattr(req, 'biometric_verification', None)
                if pv and pv.timed_out_at:
                    limit = pv.timed_out_at + timezone.timedelta(minutes=30)
                    if now <= limit:
                        continue
                else:
                    old_late_grace = req.late_grace if req.late_grace > 0 else 0
                    deadline = req.requested_exit_datetime + timezone.timedelta(minutes=old_late_grace)
                    limit = deadline + timezone.timedelta(hours=1)
                    if now <= limit:
                        continue

        data.append({
            'id': req.request_id,
            'scholar_id': req.student_id.student_id,
            'student_name': req.student_id.student_name,
            'course': req.student_id.course,
            'semester': req.student_id.semester,
            'requested_exit_datetime': make_timezone_aware_iso(req.requested_exit_datetime),
            'requested_entry_datetime': make_timezone_aware_iso(req.requested_entry_datetime),
            'actual_exit_datetime': make_timezone_aware_iso(req.actual_exit_datetime),
            'actual_entry_datetime': make_timezone_aware_iso(req.actual_entry_datetime),
            'is_late': bool(req.actual_entry_datetime and req.requested_entry_datetime and req.actual_entry_datetime > req.requested_entry_datetime),
            'outing_reason': req.outing_reason,
            'destination': req.destination,
            'request_status': 'TIME OUT' if req.request_status == 'TIMEOUT_PROCESSED' else req.request_status,
            'timeout_state': req.timeout_state,
            'leave_reason': req.leave_reason or '',
            'parent_confirmed': req.parent_confirmed,
            'note': req.note or '',
            'profile_image': req.student_id.profile_image.url if req.student_id.profile_image else '',
        })
    return JsonResponse({'success': True, 'history': data})


@custom_login_required
def student_history(request, scholar_id):
    student = get_object_or_404(student_master, student_id=scholar_id)
    
    role = request.session.get('role', '')
    if role == 'Warden':
        warden_hostel = request.session.get('hostel_name', '')
        if warden_hostel and warden_hostel != 'N/A':
            if student.hostel_name != warden_hostel:
                return JsonResponse({'success': False, 'message': 'Permission denied: Student belongs to another hostel.'}, status=403)
                
    requests = outpass_request.objects.filter(
        student_id=student).order_by('-requested_at')

    total = requests.count()
    completed = requests.filter(request_status='IN').count()
    pending = requests.filter(request_status='Initiate').count()
    rejected = requests.filter(
        request_status__in=[
            'Decline',
            'Reject']).count()

    history_data = []
    now = timezone.now()
    for req in requests:
        if req.request_status in ['Time out', 'TIME_OUT', 'TIME OUT']:
            if req.terminated_at is None:
                pv = getattr(req, 'biometric_verification', None)
                if pv and pv.timed_out_at:
                    limit = pv.timed_out_at + timezone.timedelta(minutes=30)
                    if now <= limit:
                        continue
                else:
                    old_late_grace = req.late_grace if req.late_grace > 0 else 0
                    deadline = req.requested_exit_datetime + timezone.timedelta(minutes=old_late_grace)
                    limit = deadline + timezone.timedelta(hours=1)
                    if now <= limit:
                        continue

        history_data.append({
            'requested_exit_datetime': make_timezone_aware_iso(req.requested_exit_datetime),
            'requested_entry_datetime': make_timezone_aware_iso(req.requested_entry_datetime),
            'actual_exit_datetime': make_timezone_aware_iso(req.actual_exit_datetime),
            'actual_entry_datetime': make_timezone_aware_iso(req.actual_entry_datetime),
            'is_late': bool(req.actual_entry_datetime and req.requested_entry_datetime and req.actual_entry_datetime > req.requested_entry_datetime),
            'outing_reason': req.outing_reason,
            'destination': req.destination,
            'request_status': 'TIME OUT' if req.request_status == 'TIMEOUT_PROCESSED' else req.request_status,
            'timeout_state': req.timeout_state,
            'leave_reason': req.leave_reason or '',
            'parent_confirmed': req.parent_confirmed,
            'warden_remarks': req.note
        })

    return JsonResponse({
        'success': True,
        'scholar_id': student.student_id,
        'student_name': student.student_name,
        'stats': {
            'total': total,
            'approved': completed,
            'completed': completed,
            'pending': pending,
            'rejected': rejected
        },
        'history': history_data
    })


# --- SYSTEM USER MANAGEMENT ---

@role_required(['Super Admin'])
def user_management(request):
    users_list = system_user.objects.all().order_by('-created_at')
    paginator = Paginator(users_list, 10)
    page_number = request.GET.get('page')
    users = paginator.get_page(page_number)
    return render(request, 'user_management.html', {
        'users': users,
        'role': 'Super Admin'
    })


@role_required(['Super Admin'])
def api_create_user(request):
    if request.method == 'POST':
        try:
            data = request.POST
            user_name = data.get('username', '').strip()
            password = data.get('password', '').strip()
            role = data.get('role', '').strip()
            full_name = data.get('full_name', '').strip()
            email = data.get('email', '').strip()
            contact = data.get('contact_number', '').strip()
            department = data.get('department', '').strip()
            hostel_name = data.get('hostel_name', '').strip()
            gate_name = data.get('gate_name', '').strip()

            if not (
                    user_name and password and role and full_name and email and contact):
                return JsonResponse(
                    {'success': False, 'message': 'Missing required fields.'}, status=400)

            if system_user.objects.filter(user_name=user_name).exists():
                return JsonResponse(
                    {'success': False, 'message': 'Username already exists.'}, status=400)

            if system_user.objects.filter(email=email).exists():
                return JsonResponse(
                    {'success': False, 'message': 'Email already exists.'}, status=400)

            profile_pic = request.FILES.get('profile_image')

            allowed_purposes = data.get('allowed_purposes', 'Emergency,Sunday Outing')

            system_user.objects.create(
                user_name=user_name,
                password=password,
                role=role,
                full_name=full_name,
                email=email,
                contact=contact,
                department=department,
                hostel_name=hostel_name or 'N/A',
                gate_name=gate_name or 'N/A',
                allowed_purposes=allowed_purposes,
                profile_picture=profile_pic
            )
            return JsonResponse(
                {'success': True, 'message': 'User created successfully.'})
        except Exception as e:
            return JsonResponse(
                {'success': False, 'message': str(e)}, status=500)


@role_required(['Super Admin'])
def api_update_user(request):
    if request.method == 'POST':
        try:
            data = request.POST
            user_id = data.get('id')
            user = get_object_or_404(system_user, user_id=user_id)

            user_name = data.get('username', '').strip()
            role = data.get('role', '').strip()
            full_name = data.get('full_name', '').strip()
            email = data.get('email', '').strip()
            contact = data.get('contact_number', '').strip()
            department = data.get('department', '').strip()
            hostel_name = data.get('hostel_name', '').strip()
            gate_name = data.get('gate_name', '').strip()
            password = data.get('password', '').strip()

            if not (user_name and role and full_name and email and contact):
                return JsonResponse(
                    {'success': False, 'message': 'Missing required fields.'}, status=400)

            if system_user.objects.filter(
                    user_name=user_name).exclude(
                    user_id=user_id).exists():
                return JsonResponse(
                    {'success': False, 'message': 'Username already exists.'}, status=400)

            if system_user.objects.filter(
                    email=email).exclude(
                    user_id=user_id).exists():
                return JsonResponse(
                    {'success': False, 'message': 'Email already exists.'}, status=400)

            user.username = user_name
            user.user_id = user_id
            user.user_name = user_name
            user.role = role
            user.full_name = full_name
            user.email = email
            user.contact = contact
            user.department = department
            if role == 'Gatekeeper':
                user.gate_name = gate_name or 'N/A'
                user.hostel_name = 'N/A'
            elif role == 'Warden':
                user.hostel_name = hostel_name or 'N/A'
                user.gate_name = 'N/A'
                if 'allowed_purposes' in data:
                    user.allowed_purposes = data.get('allowed_purposes')
            if password:
                user.password = password

            if 'profile_image' in request.FILES:
                user.profile_picture = request.FILES['profile_image']

            user.save()
            return JsonResponse(
                {'success': True, 'message': 'User updated successfully.'})
        except Exception as e:
            return JsonResponse(
                {'success': False, 'message': str(e)}, status=500)


@role_required(['Super Admin'])
def api_delete_user(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('id') or data.get('user_id')
            user = get_object_or_404(system_user, user_id=user_id)
            user.delete()
            return JsonResponse(
                {'success': True, 'message': 'User deleted successfully.'})
        except Exception as e:
            return JsonResponse(
                {'success': False, 'message': str(e)}, status=400)


@role_required(['Super Admin'])
def api_reset_password(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('id') or data.get('user_id')
            user = get_object_or_404(system_user, user_id=user_id)
            user.password = data.get('password') or data.get('new_password')
            user.save()
            return JsonResponse({'success': True,
                                 'message': 'Password reset successfully.'})
        except Exception as e:
            return JsonResponse(
                {'success': False, 'message': str(e)}, status=400)


@role_required(['Warden'])
def api_warden_first_login_setup(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_username = data.get('new_username')
            new_password = data.get('new_password')
            user_id = request.session.get('user_id')

            if not new_username or not new_password:
                return JsonResponse(
                    {'success': False, 'message': 'Username and password are required.'}, status=400)

            if len(new_password) < 6:
                return JsonResponse(
                    {'success': False, 'message': 'Password must be at least 6 characters.'}, status=400)

            # Check if username exists and belongs to someone else
            existing = system_user.objects.filter(
                user_name=new_username).exclude(
                user_id=user_id).exists()
            if existing:
                return JsonResponse(
                    {'success': False, 'message': 'Username is already taken.'}, status=400)

            user = get_object_or_404(system_user, user_id=user_id)
            user.user_name = new_username
            user.password = new_password
            user.is_first_login = False
            user.save()

            # Update session
            request.session['user_name'] = new_username
            request.session['is_first_login'] = False

            return JsonResponse({'success': True,
                                 'message': 'Setup completed successfully.'})
        except Exception as e:
            return JsonResponse(
                {'success': False, 'message': str(e)}, status=400)


@csrf_exempt
def api_biometric_scan(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            scholar_id = data.get('scholar_id', '').strip()
            if not scholar_id:
                return JsonResponse(
                    {'success': False, 'message': 'Scholar ID is required.'}, status=400)

            student = student_master.objects.filter(
                student_id=scholar_id).first()
            if not student:
                return JsonResponse(
                    {'success': False, 'message': 'Student not found in the database.'}, status=404)

            # Find the latest outpass request for this student
            req = outpass_request.objects.filter(
                student_id=student).order_by('-requested_at').first()
            if not req:
                return JsonResponse(
                    {
                        'success': False,
                        'message': f'No outpass request found for student {student.student_name}.'},
                    status=404)

            now = timezone.now()

            if req.request_status in ['ACCEPTED', 'Accept'] or (req.request_status == 'TIME_OUT' and req.actual_exit_datetime is None):
                # Ensure a machine exists
                from biometric.models import Machine, AttendanceLog, PendingBiometricVerification
                from biometric.services.verification import verify_single_request

                machine = Machine.objects.filter(machine_enabled=True).first()
                if not machine:
                    machine = Machine.objects.create(
                        machine_name="Main Gate Machine",
                        ip_address="127.0.0.1",
                        port=4370,
                        machine_enabled=True
                    )

                # Create simulated AttendanceLog
                log = AttendanceLog.objects.create(
                    machine=machine,
                    student_id=student.student_id,
                    verify_type=1,
                    attendance_time=now,
                    processed=False
                )

                # Delegate verification to service layer
                result = verify_single_request(req.request_id)
                
                pv = PendingBiometricVerification.objects.filter(request=req).first()
                if pv and pv.verification_status == 'ACCEPTED':
                    # Successful verification
                    req.request_status = 'OUT'
                    req.actual_exit_datetime = now
                    req.save()
                    return JsonResponse({
                        'success': True,
                        'message': f'Access Granted. Student {student.student_name} ({scholar_id}) marked OUT.'
                    })
                elif pv and pv.verification_status == 'TIME_OUT':
                    # Expired window
                    return JsonResponse({
                        'success': False,
                        'message': 'Access Denied. Outpass exit window has expired. Status updated to Time out.'
                    }, status=400)
                else:
                    # Too early or other WAITING/FAILED status
                    early_grace = req.early_grace if req.early_grace > 0 else 15
                    ref_time = req.recovery_started_at if (getattr(req, 'recovery_attempts', 0) > 0 and req.recovery_started_at) else req.requested_exit_datetime
                    start_window = ref_time - timezone.timedelta(minutes=early_grace)
                    if now < start_window:
                        time_diff = start_window - now
                        minutes_left = int(time_diff.total_seconds() / 60)
                        return JsonResponse({
                            'success': False,
                            'message': f'Access Denied. Too early to exit. Departure window starts at {start_window.strftime("%Y-%m-%d %H:%M")} (in {minutes_left} minutes).'
                        }, status=400)
                    else:
                        return JsonResponse({
                            'success': False,
                            'message': 'Access Denied. Biometric verification failed or is waiting for log processing.'
                        }, status=400)

            elif req.request_status == 'OUT':
                # Simulate a biometric return fingerprint scan for the student via direct service calls
                from biometric.models import Machine, BiometricUser, AttendanceLog, PendingBiometricVerification
                from biometric.services.verification import verify_single_request

                # 1. Ensure a machine exists
                machine = Machine.objects.filter(machine_enabled=True).first()
                if not machine:
                    machine = Machine.objects.create(
                        machine_name="Main Gate Machine",
                        ip_address="127.0.0.1",
                        port=4370,
                        machine_enabled=True
                    )

                # 2. Ensure a BiometricUser mapping exists
                biometric_user = BiometricUser.objects.filter(student=student).first()
                if not biometric_user:
                    next_uid = (BiometricUser.objects.order_by('-machine_uid').values_list('machine_uid', flat=True).first() or 0) + 1
                    biometric_user = BiometricUser.objects.create(
                        student=student,
                        machine_uid=next_uid,
                        user_id=f"sim_{student.student_id}",
                        name=student.student_name,
                        is_active=True
                    )

                # 3. Create mock AttendanceLog
                attendance_time = now
                if req.actual_exit_datetime and attendance_time < req.actual_exit_datetime + timezone.timedelta(minutes=2):
                    attendance_time = req.actual_exit_datetime + timezone.timedelta(minutes=3)

                AttendanceLog.objects.get_or_create(
                    machine=machine,
                    machine_uid=biometric_user.machine_uid,
                    attendance_time=attendance_time,
                    defaults={
                        'student': student,
                        'verify_type': 1,
                        'processed': False
                    }
                )

                # 4. Trigger the verification service
                verification_result = verify_single_request(req.request_id)

                if verification_result and verification_result.get('verification_status') == 'READY_FOR_IN':
                    return JsonResponse({
                        'success': True,
                        'message': f'Student {student.student_name} ({scholar_id}) return scan verified. Request is now READY_FOR_IN.'
                    })
                else:
                    err_msg = "Verification failed."
                    pending_ver = PendingBiometricVerification.objects.filter(request=req).first()
                    if pending_ver and pending_ver.remarks:
                        err_msg = f"Verification failed: {pending_ver.remarks}"
                    return JsonResponse({
                        'success': False,
                        'message': err_msg
                    }, status=400)

            elif req.request_status == 'Initiate':
                return JsonResponse({
                    'success': False,
                    'message': 'Access Denied. Outpass request is pending Warden approval.'
                }, status=400)

            elif req.request_status == 'Approved':
                # Simulate a biometric fingerprint scan for the student via direct service calls
                from biometric.models import Machine, BiometricUser, AttendanceLog, PendingBiometricVerification
                from biometric.services.verification import verify_single_request

                # 1. Ensure a machine exists
                machine = Machine.objects.filter(machine_enabled=True).first()
                if not machine:
                    machine = Machine.objects.create(
                        machine_name="Main Gate Machine",
                        ip_address="127.0.0.1",
                        port=4370,
                        machine_enabled=True
                    )

                # 2. Ensure a BiometricUser mapping exists
                biometric_user = BiometricUser.objects.filter(student=student).first()
                if not biometric_user:
                    next_uid = (BiometricUser.objects.order_by('-machine_uid').values_list('machine_uid', flat=True).first() or 0) + 1
                    biometric_user = BiometricUser.objects.create(
                        student=student,
                        machine_uid=next_uid,
                        user_id=f"sim_{student.student_id}",
                        name=student.student_name,
                        is_active=True
                    )

                # 3. Create mock AttendanceLog
                AttendanceLog.objects.get_or_create(
                    machine=machine,
                    machine_uid=biometric_user.machine_uid,
                    attendance_time=now,
                    defaults={
                        'student': student,
                        'verify_type': 1,
                        'processed': False
                    }
                )

                # 4. Trigger the verification service
                verification_result = verify_single_request(req.request_id)

                if verification_result and verification_result.get('verification_status') == 'ACCEPTED':
                    return JsonResponse({
                        'success': True,
                        'message': f'Student {student.student_name} ({scholar_id}) fingerprint verified. Request is now Accepted.'
                    })
                elif verification_result and verification_result.get('verification_status') == 'TIME_OUT':
                    return JsonResponse({
                        'success': False,
                        'message': 'Access Denied. Outpass exit window has expired. Status updated to Time out.'
                    }, status=400)
                else:
                    err_msg = "Verification failed."
                    pending_ver = PendingBiometricVerification.objects.filter(request=req).first()
                    if pending_ver and pending_ver.remarks:
                        err_msg = f"Verification failed: {pending_ver.remarks}"
                    return JsonResponse({
                        'success': False,
                        'message': err_msg
                    }, status=400)

            else:
                return JsonResponse({
                    'success': False,
                    'message': f'Access Denied. No active approved outpass found (Current Status: {req.request_status}).'
                }, status=400)

        except Exception as e:
            return JsonResponse(
                {'success': False, 'message': str(e)}, status=500)

    return JsonResponse(
        {'success': False, 'message': 'Invalid request method.'}, status=405)


# --- STUBS FOR UNUSED / DELETED ENDPOINTS TO PREVENT ERRORS TEMPORARILY ---
def update_status(request): pass
def api_biometric_history(request, scholar_id): pass
def api_hostel_transfer_history(request, scholar_id): pass
def api_gatekeeper_reject(request): pass
@role_required(['Super Admin'])
def permissions_view(request):
    warden_perms, _ = RolePermission.objects.get_or_create(role='Warden')
    gatekeeper_perms, _ = RolePermission.objects.get_or_create(role='Gatekeeper')
    
    context = {
        'role': 'Super Admin',
        'warden_perms': warden_perms,
        'gatekeeper_perms': gatekeeper_perms
    }
    return render(request, 'permissions.html', context)

@role_required(['Super Admin'])
def api_permissions(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            warden_data = data.get('Warden', {})
            gatekeeper_data = data.get('Gatekeeper', {})

            # Update Warden
            warden, _ = RolePermission.objects.get_or_create(role='Warden')
            if 'can_view_students' in warden_data:
                warden.can_view_students = warden_data['can_view_students']
            if 'can_view_details' in warden_data:
                warden.can_view_details = warden_data['can_view_details']
            if 'can_approve' in warden_data:
                warden.can_approve = warden_data['can_approve']
            warden.save()

            # Update Gatekeeper
            gatekeeper, _ = RolePermission.objects.get_or_create(role='Gatekeeper')
            if 'can_view_students' in gatekeeper_data:
                gatekeeper.can_view_students = gatekeeper_data['can_view_students']
            if 'can_view_details' in gatekeeper_data:
                gatekeeper.can_view_details = gatekeeper_data['can_view_details']
            if 'can_mark_out' in gatekeeper_data:
                gatekeeper.can_mark_out = gatekeeper_data['can_mark_out']
            if 'can_mark_in' in gatekeeper_data:
                gatekeeper.can_mark_in = gatekeeper_data['can_mark_in']
            gatekeeper.save()

            return JsonResponse({'success': True, 'message': 'Permissions successfully updated.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)
def api_registrar_approve(request): pass

@role_required(['Gatekeeper', 'Super Admin'])
def biometric_diagnostics(request):
    from biometric.models import Machine, PendingBiometricVerification
    role = request.session.get('role', 'Gatekeeper')
    machines = Machine.objects.all()
    pending_verifications = PendingBiometricVerification.objects.select_related('request', 'student').all().order_by('-approved_at')[:30]
    
    # Check if a machine test connection parameter was provided
    test_machine_id = request.GET.get('test_connection')
    test_result = None
    if test_machine_id:
        try:
            m = Machine.objects.get(id=test_machine_id)
            from biometric.services.machine import BiometricMachineConnection
            conn = BiometricMachineConnection(m)
            conn.connect()
            conn.disconnect()
            test_result = {'success': True, 'message': f"Successfully connected to machine '{m.machine_name}'!"}
        except Exception as e:
            test_result = {'success': False, 'message': f"Connection failed to '{m.machine_name}': {str(e)}"}

    # Check if sync trigger parameter was provided
    if request.GET.get('trigger_sync') == 'true':
        try:
            from biometric.services.sync import sync_all_logs
            total_synced = sync_all_logs()
            test_result = {'success': True, 'message': f"Log synchronization complete. Synced {total_synced} logs."}
        except Exception as e:
            test_result = {'success': False, 'message': f"Log sync failed: {str(e)}"}
            
    context = {
        'role': role,
        'machines': machines,
        'pending_verifications': pending_verifications,
        'test_result': test_result
    }
    return render(request, 'biometric_diagnostics.html', context)


@role_required(['Warden', 'Super Admin'])
def api_warden_updates(request):
    role = request.session.get('role', 'Warden')
    warden_hostel = request.session.get('hostel_name', '')

    all_requests = outpass_request.objects.all()
    cutoff_time = timezone.now() - timezone.timedelta(hours=24)
    active_requests = outpass_request.objects.select_related('student_id').filter(
        Q(request_status__in=['Initiate', 'Approved', 'ACCEPTED', 'Accept', 'OUT']) |
        Q(request_status__in=['Decline', 'IN'], terminated_at__gte=cutoff_time)
    ).order_by('-requested_at')

    if role == 'Warden' and warden_hostel and warden_hostel != 'N/A':
        all_requests = all_requests.filter(student_id__hostel_name=warden_hostel)
        active_requests = active_requests.filter(student_id__hostel_name=warden_hostel)

    if role == 'Warden':
        students_query = student_master.objects.all()
        if warden_hostel and warden_hostel != 'N/A':
            students_query = students_query.filter(hostel_name=warden_hostel)
        stats = {
            'total_students': students_query.count(),
            'initial_requests': all_requests.filter(requested_at__date=timezone.now().date()).count(),
            'warden_approved_requests': all_requests.filter(approved_at__date=timezone.now().date()).count(),
            'declined_requests': all_requests.filter(declined_at__date=timezone.now().date()).count(),
            'today_requests': all_requests.filter(requested_at__date=timezone.now().date()).count()
        }
    else:  # Super Admin
        stats = {
            'total_students': student_master.objects.count(),
            'initial_requests': active_requests.filter(request_status='Initiate').count(),
            'warden_approved_requests': active_requests.filter(request_status='Approved').count(),
            'registrar_approved_requests': active_requests.filter(request_status__in=['ACCEPTED', 'Accept']).count(),
            'accepted_requests': active_requests.filter(request_status='OUT').count(),
            'declined_requests': all_requests.filter(request_status='Decline').count(),
            'rejected_requests': all_requests.filter(request_status='Reject').count(),
        }

    perms = RolePermission.objects.filter(role=role).first()
    can_approve = not perms or perms.can_approve

    requests_data = []
    for req in active_requests:
        requests_data.append({
            'request_id': req.request_id,
            'student_id': req.student_id.student_id,
            'student_name': req.student_id.student_name,
            'student_mobile': req.student_id.mobile_no,
            'course': req.student_id.course,
            'semester': req.student_id.semester,
            'hostel_name': req.student_id.hostel_name,
            'outing_reason': req.outing_reason,
            'destination': req.destination,
            'requested_exit_datetime': make_timezone_aware_iso(req.requested_exit_datetime),
            'requested_entry_datetime': make_timezone_aware_iso(req.requested_entry_datetime),
            'actual_exit_datetime': make_timezone_aware_iso(req.actual_exit_datetime),
            'actual_entry_datetime': make_timezone_aware_iso(req.actual_entry_datetime),
            'early_grace': req.early_grace,
            'late_grace': req.late_grace,
            'note': req.note or '',
            'approved_by': req.approved_by or '',
            'warden_contact': req.warden_contact or '',
            'requested_by': req.requested_by or '',
            'leave_reason': req.leave_reason or '',
            'parent_confirmed': req.parent_confirmed,
            'request_status': 'TIME OUT' if req.request_status == 'TIMEOUT_PROCESSED' else req.request_status,
            'profile_image': req.student_id.profile_image.url if req.student_id.profile_image else '',
        })

    return JsonResponse({
        'success': True,
        'stats': stats,
        'requests': requests_data,
        'can_approve': can_approve
    })


@role_required(['Gatekeeper', 'Super Admin'])
def api_gatekeeper_updates(request):
    from django.db.models import Q
    requests = outpass_request.objects.select_related('student_id', 'biometric_verification').filter(
        Q(request_status__in=['ACCEPTED', 'Accept', 'OUT']) |
        Q(request_status='TIME_OUT', actual_exit_datetime__isnull=False, actual_entry_datetime__isnull=True)
    ).order_by('-requested_at')

    now = timezone.now()

    stats = {
        'total_expected': outpass_request.objects.filter(
            request_status='Approved',
            requested_exit_datetime__date=now.date()
        ).count(),
        'currently_out': requests.filter(request_status='OUT').count(),
        'returned_today': outpass_request.objects.filter(
            request_status='IN',
            actual_entry_datetime__date=now.date()
        ).count(),
        'declined': outpass_request.objects.filter(
            request_status='Decline',
            requested_exit_datetime__date=now.date()
        ).count()
    }

    perms = RolePermission.objects.filter(role='Gatekeeper').first()
    can_mark_out = not perms or perms.can_mark_out
    can_mark_in = not perms or perms.can_mark_in

    requests_data = []
    for req in requests:
        verification_status = ''
        if hasattr(req, 'biometric_verification'):
            verification_status = req.biometric_verification.verification_status

        requests_data.append({
            'request_id': req.request_id,
            'student_id': req.student_id.student_id,
            'student_name': req.student_id.student_name,
            'student_mobile': req.student_id.mobile_no,
            'course': req.student_id.course,
            'semester': req.student_id.semester,
            'hostel_name': req.student_id.hostel_name,
            'outing_reason': req.outing_reason,
            'destination': req.destination,
            'requested_exit_datetime': make_timezone_aware_iso(req.requested_exit_datetime),
            'requested_entry_datetime': make_timezone_aware_iso(req.requested_entry_datetime),
            'actual_exit_datetime': make_timezone_aware_iso(req.actual_exit_datetime),
            'actual_entry_datetime': make_timezone_aware_iso(req.actual_entry_datetime),
            'early_grace': req.early_grace,
            'late_grace': req.late_grace,
            'note': req.note or '',
            'approved_by': req.approved_by or '',
            'warden_contact': req.warden_contact or '',
            'requested_by': req.requested_by or '',
            'leave_reason': req.leave_reason or '',
            'parent_confirmed': req.parent_confirmed,
            'request_status': 'TIME OUT' if req.request_status == 'TIMEOUT_PROCESSED' else req.request_status,
            'verification_status': verification_status,
            'profile_image': req.student_id.profile_image.url if req.student_id.profile_image else ''
        })

    return JsonResponse({
        'success': True,
        'stats': stats,
        'requests': requests_data,
        'can_mark_out': can_mark_out,
        'can_mark_in': can_mark_in
    })


@role_required(['Gatekeeper', 'Super Admin'])
def api_biometric_queue_updates(request):
    from biometric.models import PendingBiometricVerification
    pending_verifications = PendingBiometricVerification.objects.select_related('request', 'student').all().order_by('-approved_at')[:30]

    data = []
    for pv in pending_verifications:
        data.append({
            'approved_at': make_timezone_aware_iso(pv.approved_at),
            'student_id': pv.student.student_id,
            'student_name': pv.student.student_name,
            'request_id': pv.request.request_id,
            'verification_status': pv.verification_status,
            'remarks': pv.remarks or ''
        })

    return JsonResponse({
        'success': True,
        'queue': data
    })


@role_required(['Gatekeeper', 'Super Admin'])
def api_biometric_machines_updates(request):
    from biometric.models import Machine
    machines = Machine.objects.all()

    data = []
    for m in machines:
        data.append({
            'id': m.id,
            'machine_name': m.machine_name,
            'ip_address': m.ip_address,
            'port': m.port,
            'status': m.status,
            'last_connected': make_timezone_aware_iso(m.last_connected),
            'last_successful_sync': make_timezone_aware_iso(m.last_successful_sync),
        })

    return JsonResponse({
        'success': True,
        'machines': data
    })

