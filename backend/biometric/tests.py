import datetime
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from biometric.models import Machine, BiometricUser, AttendanceLog, PendingBiometricVerification
from biometric.services.machine import MachineService, MachineConnectionError
from biometric.services.users import sync_users_from_machine
from biometric.services.attendance import download_new_logs
from biometric.services.verification import verify_single_request, check_expired_verifications
from outpass_app.models import student_master, outpass_request


class BiometricServiceTestCase(TestCase):
    def setUp(self):
        # Create standard mock machine
        self.machine = Machine.objects.create(
            machine_name="Test Office Machine",
            ip_address="127.0.0.1",
            port=4370,
            location="Main Entrance",
            connection_timeout=3,
            machine_enabled=True
        )
        self.now = timezone.now()

    def test_machine_service_mock_connection_settings(self):
        """Test that machine service uses settings-based connection params."""
        service = MachineService(self.machine)
        conn = service.connect()
        self.assertIsNotNone(conn)
        self.assertEqual(self.machine.status, 'ONLINE')
        self.assertIsNotNone(self.machine.last_connected)
        service.disconnect()

    def test_machine_service_failure_modes(self):
        """Test mock offline/timeout simulation and mapping to FAILED status."""
        offline_machine = Machine.objects.create(
            machine_name="Offline Device",
            ip_address="192.0.2.1",
            port=4370
        )
        service = MachineService(offline_machine)
        with self.assertRaises(MachineConnectionError):
            service.connect()
        self.assertEqual(offline_machine.status, 'OFFLINE')

    def test_sync_users_from_device(self):
        """Test downloading and registering users from biometric device."""
        count = sync_users_from_machine(self.machine)
        self.assertEqual(count, 2)
        
        # Check that biometric users exist in DB
        alice = BiometricUser.objects.get(user_id='101')
        self.assertEqual(alice.name, 'Piyush')
        self.assertEqual(alice.machine_uid, 1)

    def test_verification_workflow_success_and_timeout(self):
        """Test that single request verification returns structured dicts and saves timed_out_at."""
        # Create student_master objects first
        student_alice = student_master.objects.create(
            student_id='1001',
            student_name='Alice Student',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel A'
        )
        student_bob = student_master.objects.create(
            student_id='1002',
            student_name='Bob Student',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel B'
        )

        # 1. Sync users to create BiometricUser records
        sync_users_from_machine(self.machine)
        
        # Map biometric users to student IDs
        alice = BiometricUser.objects.get(user_id='101')
        alice.student = student_alice
        alice.save()

        bob = BiometricUser.objects.get(user_id='102')
        bob.student = student_bob
        bob.save()

        # Create outpass_request objects which automatically creates PendingBiometricVerification via signals
        req_alice = outpass_request.objects.create(
            request_id=999,
            student_id=student_alice,
            requested_exit_datetime=self.now - datetime.timedelta(minutes=5),
            requested_entry_datetime=self.now,
            early_grace=15,
            late_grace=15,
            request_status='Approved'
        )
        req_bob = outpass_request.objects.create(
            request_id=888,
            student_id=student_bob,
            requested_exit_datetime=self.now - datetime.timedelta(minutes=10),
            requested_entry_datetime=self.now,
            early_grace=15,
            late_grace=5,
            request_status='Approved'
        )

        # Update the approved/expiry times of the auto-created PendingBiometricVerification records
        alice_req = PendingBiometricVerification.objects.get(request=req_alice)
        alice_req.approved_at = self.now - datetime.timedelta(minutes=10)
        alice_req.expires_at = self.now + datetime.timedelta(minutes=10)
        alice_req.save()

        bob_req = PendingBiometricVerification.objects.get(request=req_bob)
        bob_req.approved_at = self.now - datetime.timedelta(minutes=20)
        bob_req.expires_at = self.now - datetime.timedelta(minutes=5)  # Expired 5 mins ago
        bob_req.save()

        # 3. Call verify_single_request
        # For Alice (should be ACCEPTED)
        alice_res = verify_single_request(alice_req.request_id)
        self.assertEqual(alice_res["verification_status"], "ACCEPTED")
        self.assertEqual(alice_res["request_id"], 999)
        self.assertEqual(alice_res["student_id"], '1001')
        self.assertIn("attendance_time", alice_res)

        alice_req.refresh_from_db()
        self.assertEqual(alice_req.verification_status, 'ACCEPTED')
        self.assertIsNotNone(alice_req.verified_at)
        self.assertIsNone(alice_req.timed_out_at)

        # For Bob (should be TIME_OUT)
        bob_res = verify_single_request(bob_req.request_id)
        self.assertEqual(bob_res["verification_status"], "TIME_OUT")
        self.assertEqual(bob_res["request_id"], 888)
        self.assertNotIn("attendance_time", bob_res)

        bob_req.refresh_from_db()
        self.assertEqual(bob_req.verification_status, 'TIME_OUT')
        self.assertIsNotNone(bob_req.timed_out_at)
        self.assertIsNone(bob_req.verified_at)

    def test_verification_failure_status(self):
        """Test that verification sets status to FAILED when machine is offline."""
        offline_machine = Machine.objects.create(
            machine_name="Broken Offline Device",
            ip_address="192.0.2.1",
            port=4370,
            machine_enabled=True
        )
        # Disable the standard working machine to force offline machine to be tested
        self.machine.machine_enabled = False
        self.machine.save()

        student_charlie = student_master.objects.create(
            student_id='1003',
            student_name='Charlie Student',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel C'
        )
        req_charlie = outpass_request.objects.create(
            request_id=777,
            student_id=student_charlie,
            requested_exit_datetime=self.now,
            requested_entry_datetime=self.now,
            request_status='Approved'
        )

        req = PendingBiometricVerification.objects.get(request=req_charlie)
        req.approved_at = self.now - datetime.timedelta(minutes=10)
        req.expires_at = self.now + datetime.timedelta(minutes=10)
        req.save()

        # Verify should set request status to FAILED
        res = verify_single_request(req.request_id)
        self.assertEqual(res["verification_status"], "FAILED")

        req.refresh_from_db()
        self.assertEqual(req.verification_status, 'FAILED')
        self.assertIn("Machine offline", req.remarks)

    def test_new_request_after_previous_successful_verification(self):
        """Verify that a subsequent approved request does not auto-accept using a previously processed scan."""
        student = student_master.objects.create(
            student_id="test_new_req",
            student_name="Test Student New",
            mobile_no="1234567890",
            department="CS",
            course="BTech",
            semester=1,
            hostel_name="Hostel A"
        )
        BiometricUser.objects.create(
            student=student,
            machine_uid=10,
            user_id="test_new_req",
            name="Test Student New"
        )
        
        # 1. Create and verify request #1
        req1 = outpass_request.objects.create(
            request_id=8001,
            student_id=student,
            requested_exit_datetime=self.now,
            requested_entry_datetime=self.now + datetime.timedelta(hours=2),
            early_grace=15,
            late_grace=15,
            request_status='Approved'
        )
        pbv1 = PendingBiometricVerification.objects.get(request=req1)
        pbv1.approved_at = self.now - datetime.timedelta(minutes=10)
        pbv1.expires_at = self.now + datetime.timedelta(minutes=20)
        pbv1.save()

        # Create valid log for request #1
        log = AttendanceLog.objects.create(
            machine=self.machine,
            student=student,
            machine_uid=10,
            verify_type=1,
            attendance_time=self.now - datetime.timedelta(minutes=5),
            processed=False
        )

        res1 = verify_single_request(8001)
        self.assertEqual(res1["verification_status"], "ACCEPTED")
        log.refresh_from_db()
        self.assertTrue(log.processed)

        # 2. Create request #2 for same student
        req2 = outpass_request.objects.create(
            request_id=8002,
            student_id=student,
            requested_exit_datetime=self.now + datetime.timedelta(hours=2),
            requested_entry_datetime=self.now + datetime.timedelta(hours=4),
            early_grace=15,
            late_grace=15,
            request_status='Approved'
        )
        pbv2 = PendingBiometricVerification.objects.get(request=req2)
        pbv2.approved_at = self.now + datetime.timedelta(minutes=5)
        pbv2.expires_at = self.now + datetime.timedelta(minutes=35)
        pbv2.save()

        # Run verification for request #2 (should remain WAITING since previous log is processed)
        res2 = verify_single_request(8002)
        self.assertEqual(res2["verification_status"], "WAITING")

    def test_student_never_scans_times_out_automatically(self):
        """Verify that a waiting request is transitioned to TIME_OUT automatically when current time > expires_at."""
        student = student_master.objects.create(
            student_id="test_timeout",
            student_name="Test Student Timeout",
            mobile_no="1234567890",
            department="CS",
            course="BTech",
            semester=1,
            hostel_name="Hostel A"
        )
        req = outpass_request.objects.create(
            request_id=8003,
            student_id=student,
            requested_exit_datetime=self.now - datetime.timedelta(minutes=30),
            requested_entry_datetime=self.now + datetime.timedelta(hours=2),
            early_grace=15,
            late_grace=15,
            request_status='Approved'
        )
        pbv = PendingBiometricVerification.objects.get(request=req)
        # Set expires_at to 5 minutes ago
        pbv.expires_at = self.now - datetime.timedelta(minutes=5)
        pbv.save()

        # Run the timeout checker
        timed_out_count = check_expired_verifications()
        self.assertEqual(timed_out_count, 1)

        pbv.refresh_from_db()
        self.assertEqual(pbv.verification_status, "TIME_OUT")
        self.assertIsNotNone(pbv.timed_out_at)
        
        req.refresh_from_db()
        self.assertEqual(req.request_status, "TIME OUT")

    def test_attendance_before_approval_ignored(self):
        """Verify that attendance logs with attendance_time < approved_at are ignored."""
        student = student_master.objects.create(
            student_id="test_before_appr",
            student_name="Test Student Before",
            mobile_no="1234567890",
            department="CS",
            course="BTech",
            semester=1,
            hostel_name="Hostel A"
        )
        req = outpass_request.objects.create(
            request_id=8004,
            student_id=student,
            requested_exit_datetime=self.now,
            requested_entry_datetime=self.now + datetime.timedelta(hours=2),
            early_grace=15,
            late_grace=15,
            request_status='Approved'
        )
        pbv = PendingBiometricVerification.objects.get(request=req)
        pbv.approved_at = self.now
        pbv.expires_at = self.now + datetime.timedelta(minutes=30)
        pbv.save()

        # Create attendance log 5 minutes BEFORE approved_at
        AttendanceLog.objects.create(
            machine=self.machine,
            student=student,
            machine_uid=1,
            verify_type=1,
            attendance_time=self.now - datetime.timedelta(minutes=5),
            processed=False
        )

        res = verify_single_request(8004)
        self.assertEqual(res["verification_status"], "WAITING")

    def test_attendance_after_expiry_ignored(self):
        """Verify that attendance logs with attendance_time > expires_at are ignored."""
        student = student_master.objects.create(
            student_id="test_after_exp",
            student_name="Test Student After",
            mobile_no="1234567890",
            department="CS",
            course="BTech",
            semester=1,
            hostel_name="Hostel A"
        )
        req = outpass_request.objects.create(
            request_id=8005,
            student_id=student,
            requested_exit_datetime=self.now,
            requested_entry_datetime=self.now + datetime.timedelta(hours=2),
            early_grace=15,
            late_grace=20,
            request_status='Approved'
        )
        pbv = PendingBiometricVerification.objects.get(request=req)
        pbv.approved_at = self.now - datetime.timedelta(minutes=10)
        pbv.expires_at = self.now + datetime.timedelta(minutes=10)
        pbv.save()

        # Create attendance log 15 minutes after now (exceeding expires_at by 5 mins, but within late_grace 20 mins)
        AttendanceLog.objects.create(
            machine=self.machine,
            student=student,
            machine_uid=1,
            verify_type=1,
            attendance_time=self.now + datetime.timedelta(minutes=15),
            processed=False
        )

        res = verify_single_request(8005)
        # Should remain WAITING (ignored scan since it is > expires_at)
        self.assertEqual(res["verification_status"], "WAITING")

    def test_duplicate_attendance_cannot_verify_another_request(self):
        """Verify that a single attendance log cannot verify multiple outpass requests."""
        student = student_master.objects.create(
            student_id="test_dup",
            student_name="Test Student Dup",
            mobile_no="1234567890",
            department="CS",
            course="BTech",
            semester=1,
            hostel_name="Hostel A"
        )
        req1 = outpass_request.objects.create(
            request_id=8006,
            student_id=student,
            requested_exit_datetime=self.now,
            requested_entry_datetime=self.now + datetime.timedelta(hours=2),
            early_grace=15,
            late_grace=15,
            request_status='Approved'
        )
        pbv1 = PendingBiometricVerification.objects.get(request=req1)
        pbv1.approved_at = self.now - datetime.timedelta(minutes=10)
        pbv1.expires_at = self.now + datetime.timedelta(minutes=20)
        pbv1.save()

        req2 = outpass_request.objects.create(
            request_id=8007,
            student_id=student,
            requested_exit_datetime=self.now + datetime.timedelta(minutes=5),
            requested_entry_datetime=self.now + datetime.timedelta(hours=2),
            early_grace=15,
            late_grace=15,
            request_status='Approved'
        )
        pbv2 = PendingBiometricVerification.objects.get(request=req2)
        pbv2.approved_at = self.now - datetime.timedelta(minutes=10)
        pbv2.expires_at = self.now + datetime.timedelta(minutes=20)
        pbv2.save()

        # Create one attendance log that fits both requests' windows
        AttendanceLog.objects.create(
            machine=self.machine,
            student=student,
            machine_uid=1,
            verify_type=1,
            attendance_time=self.now,
            processed=False
        )

        # Verify request 1 -> should succeed
        res1 = verify_single_request(8006)
        self.assertEqual(res1["verification_status"], "ACCEPTED")

        # Verify request 2 -> should remain WAITING
        res2 = verify_single_request(8007)
        self.assertEqual(res2["verification_status"], "WAITING")


class BiometricAPITestCase(APITestCase):
    def setUp(self):
        self.machine = Machine.objects.create(
            machine_name="Test Office Machine",
            ip_address="127.0.0.1",
            port=4370,
            location="Main Entrance",
            machine_enabled=True
        )
        self.now = timezone.now()

    def test_create_pending_verification_api(self):
        student_test = student_master.objects.create(
            student_id='1005',
            student_name='Test Student',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel A'
        )
        req_test = outpass_request.objects.create(
            request_id=555,
            student_id=student_test,
            requested_exit_datetime=self.now,
            requested_entry_datetime=self.now,
            request_status='Initiate'  # Keep it as Initiate so the signal doesn't auto-create the pending verification yet
        )

        url = reverse('pending-verifications')
        data = {
            "request": 555,
            "student": "1005",
            "approved_at": (self.now - datetime.timedelta(minutes=2)).isoformat(),
            "expires_at": (self.now + datetime.timedelta(minutes=10)).isoformat(),
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PendingBiometricVerification.objects.count(), 1)
        self.assertEqual(PendingBiometricVerification.objects.first().verification_status, 'WAITING')

    def test_verify_endpoint_api(self):
        """Test POST /api/verify/ returns structured validation result."""
        student_alice = student_master.objects.create(
            student_id='2001',
            student_name='Alice Student',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel A'
        )
        # Setup BiometricUser
        BiometricUser.objects.create(
            student=student_alice,
            machine_uid=1,
            user_id='101',
            name="Alice Student"
        )
        
        # Setup pending request
        req_alice = outpass_request.objects.create(
            request_id=100,
            student_id=student_alice,
            requested_exit_datetime=self.now - datetime.timedelta(minutes=5),
            requested_entry_datetime=self.now,
            early_grace=15,
            late_grace=15,
            request_status='Approved'
        )

        req = PendingBiometricVerification.objects.get(request=req_alice)
        req.approved_at = self.now - datetime.timedelta(minutes=10)
        req.expires_at = self.now + datetime.timedelta(minutes=10)
        req.save()

        url = reverse('verify-request')
        data = {"request_id": 100}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["request_id"], 100)
        self.assertEqual(response.data["verification_status"], "ACCEPTED")
        self.assertIn("attendance_time", response.data)

    def test_gatekeeper_mark_in_biometric_validation(self):
        """Test that gatekeeper mark-in checks biometric verification status."""
        from outpass_app.models import RolePermission
        RolePermission.objects.get_or_create(role='Gatekeeper', defaults={'can_mark_in': True})

        student = student_master.objects.create(
            student_id='3001',
            student_name='Dave Student',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel A'
        )

        req_out = outpass_request.objects.create(
            request_id=123,
            student_id=student,
            requested_exit_datetime=self.now,
            requested_entry_datetime=self.now,
            request_status='OUT',
            actual_exit_datetime=self.now
        )

        # 1. First attempt when biometric verification is WAITING
        session = self.client.session
        session['user_id'] = 1
        session['role'] = 'Gatekeeper'
        session.save()

        # Create WAITING PendingBiometricVerification
        pbv = PendingBiometricVerification.objects.create(
            request=req_out,
            student=student,
            approved_at=self.now,
            expires_at=self.now,
            verification_status='WAITING'
        )

        url = reverse('api_gatekeeper_mark_in')
        response = self.client.post(url, {"request_id": 123}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertIn("Student has not completed biometric verification", response.json()['message'])

        # 2. Second attempt when biometric verification status is READY_FOR_IN
        pbv.verification_status = 'READY_FOR_IN'
        pbv.save()
        
        response = self.client.post(url, {"request_id": 123}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    def test_default_grace_periods(self):
        """Test that default grace periods (early=15, late=0) are applied when not configured."""
        student_test = student_master.objects.create(
            student_id='3005',
            student_name='Grace Test',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel A'
        )
        # Setup BiometricUser
        BiometricUser.objects.create(
            student=student_test,
            machine_uid=1,
            user_id='3005',
            name="Grace Test"
        )
        # Setup request with 0 grace values, set exit to 10 mins in the future
        req = outpass_request.objects.create(
            request_id=444,
            student_id=student_test,
            requested_exit_datetime=self.now + datetime.timedelta(minutes=10),
            requested_entry_datetime=self.now + datetime.timedelta(hours=2),
            early_grace=0,
            late_grace=0,
            request_status='Approved'
        )
        
        # Set approved_at back in time so that logs are not filtered out by the GTE approved_at check
        pbv = PendingBiometricVerification.objects.get(request=req)
        pbv.approved_at = self.now - datetime.timedelta(minutes=20)
        pbv.save()
        
        # 1. Too early scan (16 minutes before start_time, which is now - 6 mins) should be ignored
        AttendanceLog.objects.create(
            machine=self.machine,
            student=student_test,
            machine_uid=1,
            verify_type=1,
            attendance_time=self.now - datetime.timedelta(minutes=6)
        )
        verify_single_request(444)
        pbv.refresh_from_db()
        self.assertEqual(pbv.verification_status, 'WAITING')

        # 2. Inside default early window (14 minutes before start_time, which is now - 4 mins) should be ACCEPTED
        log = AttendanceLog.objects.create(
            machine=self.machine,
            student=student_test,
            machine_uid=1,
            verify_type=1,
            attendance_time=self.now - datetime.timedelta(minutes=4)
        )
        verify_single_request(444)
        pbv.refresh_from_db()
        self.assertEqual(pbv.verification_status, 'ACCEPTED')

    def test_in_workflow_no_timeout_and_time_diff(self):
        """Test that the return scan (IN) does not use timeout logic and logs time difference."""
        student_test = student_master.objects.create(
            student_id='3006',
            student_name='Return Test',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel A'
        )
        # Setup BiometricUser
        BiometricUser.objects.create(
            student=student_test,
            machine_uid=2,
            user_id='3006',
            name="Return Test"
        )
        # Setup OUT request by first creating Approved then updating to OUT
        req = outpass_request.objects.create(
            request_id=445,
            student_id=student_test,
            requested_exit_datetime=self.now - datetime.timedelta(hours=2),
            requested_entry_datetime=self.now - datetime.timedelta(minutes=30),  # Requested entry was 30 mins ago (late return)
            early_grace=15,
            late_grace=15,
            request_status='Approved'
        )
        req.request_status = 'OUT'
        req.actual_exit_datetime = self.now - datetime.timedelta(hours=1, minutes=45)
        req.save()
        
        # Verify the PendingBiometricVerification exists and got reset to OUT by the signal
        pbv = PendingBiometricVerification.objects.get(request=req)
        self.assertEqual(pbv.verification_status, 'OUT')
        self.assertIsNone(pbv.verified_at)

        # Create return scan (happened now, 30 minutes after requested entry - so late!)
        log = AttendanceLog.objects.create(
            machine=self.machine,
            student=student_test,
            machine_uid=2,
            verify_type=1,
            attendance_time=self.now
        )
        
        # Verify single request
        verify_single_request(445)
        
        pbv.refresh_from_db()
        # Should be READY_FOR_IN, not TIME_OUT, despite being late!
        self.assertEqual(pbv.verification_status, 'READY_FOR_IN')
        self.assertEqual(pbv.verified_at, self.now)

        # Call gatekeeper mark IN API
        session = self.client.session
        session['user_id'] = 1
        session['role'] = 'Gatekeeper'
        session.save()
        
        from outpass_app.models import RolePermission
        RolePermission.objects.get_or_create(role='Gatekeeper', defaults={'can_mark_in': True})

        url = reverse('api_gatekeeper_mark_in')
        response = self.client.post(url, {"request_id": 445}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        req.refresh_from_db()
        self.assertEqual(req.request_status, 'IN')
        self.assertEqual(req.actual_entry_datetime, self.now)
        # Note should contain return difference (30m late)
        self.assertIn("30m late", req.note)

    @override_settings(BIOMETRIC_SYNC_INTERVAL_SECONDS=30)
    def test_scheduler_registration(self):
        """Test that the scheduler starts and registers the sync job correctly."""
        from biometric import scheduler
        # Shut down scheduler if it's currently running to avoid thread leak
        if scheduler.scheduler.running:
            scheduler.scheduler.shutdown(wait=False)
            
        scheduler.start()
        self.assertTrue(scheduler.scheduler.running)
        
        job = scheduler.scheduler.get_job('sync_logs_job')
        self.assertIsNotNone(job)
        self.assertEqual(job.trigger.interval.total_seconds(), 30.0)

        job_timeout = scheduler.scheduler.get_job('check_timeouts_job')
        self.assertIsNotNone(job_timeout)
        self.assertEqual(job_timeout.trigger.interval.total_seconds(), 30.0)
        
        # Shut down the test scheduler
        scheduler.scheduler.shutdown(wait=False)

    def test_in_button_visibility_on_dashboard(self):
        """Test that the gatekeeper dashboard shows the IN button only when biometric verification is completed."""
        student = student_master.objects.create(
            student_id="S12345",
            student_name="Dashboard Student",
            mobile_no="1234567890",
            department="CS",
            course="BTech",
            semester=1,
            hostel_name="Hostel A"
        )
        req = outpass_request.objects.create(
            request_id=9999,
            student_id=student,
            requested_exit_datetime=self.now,
            requested_entry_datetime=self.now + timezone.timedelta(hours=2),
            request_status='OUT',
            actual_exit_datetime=self.now
        )
        pbv = PendingBiometricVerification.objects.create(
            request=req,
            student=student,
            approved_at=self.now,
            expires_at=self.now + timezone.timedelta(minutes=30),
            verification_status='WAITING'
        )

        session = self.client.session
        session['user_id'] = 1
        session['role'] = 'Gatekeeper'
        session.save()

        # Gatekeeper marks OUT -> verification status is WAITING -> IN button should NOT be in HTML
        url = reverse('gatekeeper_dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Waiting for Biometric Scan")
        self.assertNotContains(response, 'class="btn-action gatekeeper-mark-in-btn"')

        # After successful return scan -> verification status becomes READY_FOR_IN -> IN button should be in HTML
        pbv.verification_status = 'READY_FOR_IN'
        pbv.save()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="btn-action gatekeeper-mark-in-btn"')
        self.assertNotContains(response, "Waiting for Biometric Scan")

    def test_exit_scan_not_matched_as_return_scan(self):
        """Test that an exit scan (or clock-drifted exit scan) is never matched as a return scan."""
        # 1. Create student and request
        student = student_master.objects.create(
            student_id="S999",
            student_name="Security Student",
            mobile_no="1234567890",
            department="CS",
            course="BTech",
            semester=1,
            hostel_name="Hostel A"
        )
        
        # Superuser and machine for context
        from django.contrib.auth.models import User
        admin_user = User.objects.create_superuser('admin_sec', 'admin@sec.com', 'adminpass')
        machine = Machine.objects.create(
            machine_name="Test Office Machine",
            ip_address="127.0.0.1",
            port=4370,
            status="ONLINE",
            machine_enabled=True
        )
        
        # Link student to biometric user
        BiometricUser.objects.create(
            student=student,
            machine_uid=1,
            user_id="103",
            name="Security Student"
        )
        
        req = outpass_request.objects.create(
            request_id=999,
            student_id=student,
            requested_exit_datetime=self.now,
            requested_entry_datetime=self.now + timezone.timedelta(hours=2),
            request_status='Approved'
        )
        
        pbv, _ = PendingBiometricVerification.objects.get_or_create(
            request=req,
            student=student,
            defaults={
                'approved_at': self.now,
                'expires_at': self.now + timezone.timedelta(minutes=30),
                'verification_status': 'WAITING'
            }
        )
        
        # 2. Gatekeeper marks student OUT.
        req.request_status = 'OUT'
        req.actual_exit_datetime = self.now
        req.save()
        
        # Reset pbv status to OUT (normally done by signal, let's verify or set manually)
        pbv.verification_status = 'OUT'
        pbv.save()
        
        # 3. Simulate an exit scan log that is in the database but unprocessed
        # Timestamp is slightly after actual_exit_datetime (e.g. 30 seconds after due to clock drift)
        exit_log = AttendanceLog.objects.create(
            machine=machine,
            student=student,
            machine_uid=1,
            verify_type=1,
            attendance_time=self.now + timezone.timedelta(seconds=30),
            processed=False
        )
        
        # 4. Trigger verification matching
        from biometric.services.verification import match_pending_verifications
        match_pending_verifications()
        
        # 5. Verify the exit log is NOT matched as return scan
        exit_log.refresh_from_db()
        pbv.refresh_from_db()
        
        # The exit log should be marked as processed (as a stale/exit scan log)
        self.assertTrue(exit_log.processed)
        # Verification status remains OUT
        self.assertEqual(pbv.verification_status, 'OUT')
        
        # Gatekeeper attempts to mark student IN
        session = self.client.session
        session['user_id'] = 1
        session['role'] = 'Gatekeeper'
        session.save()
        
        url_mark_in = reverse('api_gatekeeper_mark_in')
        response = self.client.post(url_mark_in, {"request_id": 999}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        
        # Dashboard does not display the IN button
        url_dashboard = reverse('gatekeeper_dashboard')
        response_dash = self.client.get(url_dashboard)
        self.assertNotContains(response_dash, 'class="btn-action gatekeeper-mark-in-btn"')
        
        # 6. Now, student scans fingerprint to return (e.g., 3 minutes after actual exit)
        return_log = AttendanceLog.objects.create(
            machine=machine,
            student=student,
            machine_uid=1,
            verify_type=1,
            attendance_time=self.now + timezone.timedelta(minutes=3),
            processed=False
        )
        
        match_pending_verifications()
        
        # 7. Verify return scan IS matched and READY_FOR_IN
        return_log.refresh_from_db()
        pbv.refresh_from_db()
        
        self.assertTrue(return_log.processed)
        self.assertEqual(pbv.verification_status, 'READY_FOR_IN')
        
        # Dashboard now displays the IN button
        response_dash = self.client.get(url_dashboard)
        self.assertContains(response_dash, 'class="btn-action gatekeeper-mark-in-btn"')
        
        # Gatekeeper successfully marks student IN
        from outpass_app.models import RolePermission
        RolePermission.objects.get_or_create(role='Gatekeeper', defaults={'can_mark_in': True})
        response = self.client.post(url_mark_in, {"request_id": 999}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        req.refresh_from_db()
        self.assertEqual(req.request_status, 'IN')

    def test_return_scan_strictly_new(self):
        """
        Verify that return scan verification respects the 2-minute physical event buffer
        and rejects scans that occur too close to the exit event.
        """
        from outpass_app.models import student_master
        from outpass_app.models import outpass_request
        from biometric.models import Machine, BiometricUser, AttendanceLog, PendingBiometricVerification
        from biometric.services.verification import match_pending_verifications
        
        machine = self.machine
        student = student_master.objects.create(
            student_id='220101999',
            student_name='John Doe',
            mobile_no='9999999999',
            department='Computer Science Department',
            course='B.Sc. IT',
            semester=3,
            hostel_name='Boys Hostel A',
            email='john@school.com'
        )
        BiometricUser.objects.create(
            student=student,
            machine_uid=1,
            user_id='220101999',
            name='John Doe'
        )
        
        # 1. Create a request and biometric verification in WAITING state
        req = outpass_request.objects.create(
            request_id=889,
            student_id=student,
            requested_exit_datetime=self.now,
            requested_entry_datetime=self.now + timezone.timedelta(hours=2),
            early_grace=15,
            late_grace=15,
            request_status='Initiate'
        )
        pbv = PendingBiometricVerification.objects.create(
            request=req,
            student=student,
            approved_at=self.now,
            expires_at=self.now + timezone.timedelta(minutes=30),
            verification_status='WAITING'
        )
        
        # 2. Gatekeeper marks student OUT.
        req.request_status = 'OUT'
        req.actual_exit_datetime = self.now
        req.save()
        
        pbv.verification_status = 'OUT'
        pbv.save()

        # 3. Simulate a scan that occurs 1 minute after exit (inside 2-minute buffer)
        too_early_log = AttendanceLog.objects.create(
            machine=machine,
            student=student,
            machine_uid=1,
            verify_type=1,
            attendance_time=self.now + timezone.timedelta(minutes=1),
            processed=False
        )
        
        # 4. Trigger bulk verification
        match_pending_verifications()
        
        # 5. Verify the state is STILL OUT and too_early_log is NOT matched as return scan
        pbv.refresh_from_db()
        too_early_log.refresh_from_db()
        self.assertEqual(pbv.verification_status, 'OUT')
        self.assertTrue(too_early_log.processed)
        
        # 6. Now simulate a scan that occurs 3 minutes after exit (outside 2-minute buffer)
        valid_log = AttendanceLog.objects.create(
            machine=machine,
            student=student,
            machine_uid=1,
            verify_type=1,
            attendance_time=self.now + timezone.timedelta(minutes=3),
            processed=False
        )
        
        # 7. Trigger bulk verification again
        match_pending_verifications()
        
        # 8. Verify the status is now transitioned to READY_FOR_IN
        pbv.refresh_from_db()
        valid_log.refresh_from_db()
        self.assertEqual(pbv.verification_status, 'READY_FOR_IN')
        self.assertTrue(valid_log.processed)

    def test_sync_history_only_created_when_records_synced(self):
        """
        Verify that SyncHistory records are only created when logs or users count > 0.
        """
        from unittest.mock import patch
        from biometric.models import SyncHistory
        from biometric.services.sync import sync_all_logs, sync_all_users

        SyncHistory.objects.all().delete()

        # 1. Test logs sync where count is 0
        with patch('biometric.services.sync.download_new_logs', return_value=0):
            sync_all_logs()
            self.assertEqual(SyncHistory.objects.filter(sync_type='LOGS').count(), 0)

        # 2. Test logs sync where count > 0
        with patch('biometric.services.sync.download_new_logs', return_value=5):
            sync_all_logs()
            self.assertEqual(SyncHistory.objects.filter(sync_type='LOGS').count(), 1)
            history = SyncHistory.objects.filter(sync_type='LOGS').first()
            self.assertEqual(history.total_records, 5)
            self.assertEqual(history.status, 'SUCCESS')

        SyncHistory.objects.all().delete()

        # 3. Test users sync where count is 0
        with patch('biometric.services.sync.sync_users_from_machine', return_value=0):
            sync_all_users()
            self.assertEqual(SyncHistory.objects.filter(sync_type='USERS').count(), 0)

        # 4. Test users sync where count > 0
        with patch('biometric.services.sync.sync_users_from_machine', return_value=3):
            sync_all_users()
            self.assertEqual(SyncHistory.objects.filter(sync_type='USERS').count(), 1)
            history = SyncHistory.objects.filter(sync_type='USERS').first()
            self.assertEqual(history.total_records, 3)
            self.assertEqual(history.status, 'SUCCESS')


class BiometricRegressionTestCase(APITestCase):
    def setUp(self):
        self.machine = Machine.objects.create(
            machine_name="Test Office Machine",
            ip_address="127.0.0.1",
            port=4370,
            location="Main Entrance",
            machine_enabled=True
        )
        self.now = timezone.now()

    def test_unmapped_biometric_scans_skipped(self):
        """Verify that download_new_logs skips logs for unmapped users."""
        from unittest.mock import patch
        from biometric.services.machine import MockZKConnection
        
        student_alice = student_master.objects.create(
            student_id='101',
            student_name='Alice Student',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel A'
        )
        sync_users_from_machine(self.machine)
        alice = BiometricUser.objects.get(user_id='101')
        alice.student = student_alice
        alice.save()

        class DummyLog:
            def __init__(self, uid, user_id, timestamp):
                self.uid = uid
                self.user_id = user_id
                self.timestamp = timestamp
                self.status = 1
                self.punch = 0

        mock_logs = [
            DummyLog(1, '101', self.now),
            DummyLog(2, '999', self.now + datetime.timedelta(minutes=1)), # completely unmapped
        ]

        with patch.object(MockZKConnection, 'get_attendance', return_value=mock_logs):
            count = download_new_logs(self.machine)
            self.assertEqual(count, 1)
            self.assertEqual(AttendanceLog.objects.filter(student__isnull=True).count(), 0)
            self.assertEqual(AttendanceLog.objects.count(), 1)
            self.machine.refresh_from_db()
            self.assertIsNotNone(self.machine.last_attendance_time)

    def test_utc_timezone_storage(self):
        """Verify that create_request endpoint correctly stores UTC datetimes."""
        import json
        import zoneinfo
        session = self.client.session
        session['user_id'] = 1
        session['role'] = 'Warden'
        session['user_name'] = 'test_warden'
        session.save()

        student = student_master.objects.create(
            student_id='2424113',
            student_name='Ankit',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel A'
        )
        
        kolkata_tz = zoneinfo.ZoneInfo('Asia/Kolkata')
        now_ist = self.now.astimezone(kolkata_tz)
        exit_dt = now_ist + datetime.timedelta(hours=1)
        entry_dt = now_ist + datetime.timedelta(hours=3)
        
        exit_dt_str = exit_dt.strftime('%Y-%m-%d %H:%M:%S')
        entry_dt_str = entry_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        url = reverse('create_request')
        response = self.client.post(url, json.dumps({
            'scholar_id': '2424113',
            'requested_exit_datetime': exit_dt_str,
            'requested_entry_datetime': entry_dt_str,
            'purpose': 'Emergency',
            'destination': 'Market'
        }), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        req = outpass_request.objects.filter(student_id=student).first()
        self.assertIsNotNone(req)
        # Check that stored value corresponds to the exit_dt UTC value
        self.assertEqual(req.requested_exit_datetime.replace(microsecond=0), exit_dt.astimezone(zoneinfo.ZoneInfo('UTC')).replace(microsecond=0))

    def test_expires_at_calculation(self):
        """Verify that expires_at is calculated as requested_exit_datetime + late_grace."""
        student = student_master.objects.create(
            student_id='1005',
            student_name='Grace Student',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel A'
        )
        req = outpass_request.objects.create(
            request_id=9001,
            student_id=student,
            requested_exit_datetime=self.now + datetime.timedelta(hours=2),
            requested_entry_datetime=self.now + datetime.timedelta(hours=4),
            early_grace=15,
            late_grace=25,
            request_status='Initiate'
        )
        req.request_status = 'Approved'
        req.save()
        
        pbv = PendingBiometricVerification.objects.get(request=req)
        expected_expiry = req.requested_exit_datetime + datetime.timedelta(minutes=25)
        self.assertEqual(pbv.expires_at, expected_expiry)

    def test_automatic_timeout_transition(self):
        """Verify that check_expired_verifications transitions WAITING requests to TIME_OUT automatically."""
        student = student_master.objects.create(
            student_id='1006',
            student_name='Timeout Student',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel A'
        )
        req = outpass_request.objects.create(
            request_id=9002,
            student_id=student,
            requested_exit_datetime=self.now - datetime.timedelta(hours=1),
            requested_entry_datetime=self.now + datetime.timedelta(hours=1),
            early_grace=15,
            late_grace=15,
            request_status='Initiate'
        )
        req.request_status = 'Approved'
        req.save()
        
        pbv = PendingBiometricVerification.objects.get(request=req)
        pbv.expires_at = self.now - datetime.timedelta(minutes=5)
        pbv.save()
        
        count = check_expired_verifications()
        self.assertEqual(count, 1)
        
        pbv.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual(pbv.verification_status, 'TIME_OUT')
        self.assertEqual(req.request_status, 'TIME OUT')

    def test_successful_biometric_verification(self):
        """Verify the complete end-to-end success path of biometric verification."""
        from biometric.services.verification import match_pending_verifications
        
        student = student_master.objects.create(
            student_id='1007',
            student_name='Success Student',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel A'
        )
        BiometricUser.objects.create(
            student=student,
            machine_uid=7,
            user_id='1007',
            name='Success Student'
        )
        
        exit_time = self.now + datetime.timedelta(minutes=5)
        req = outpass_request.objects.create(
            request_id=9003,
            student_id=student,
            requested_exit_datetime=exit_time,
            requested_entry_datetime=exit_time + datetime.timedelta(hours=2),
            early_grace=15,
            late_grace=15,
            request_status='Initiate'
        )
        req.request_status = 'Approved'
        req.save()
        
        pbv = PendingBiometricVerification.objects.get(request=req)
        
        AttendanceLog.objects.create(
            machine=self.machine,
            student=student,
            machine_uid=7,
            verify_type=1,
            attendance_time=exit_time,
            processed=False
        )
        
        results = match_pending_verifications()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['verification_status'], 'ACCEPTED')
        
        pbv.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual(pbv.verification_status, 'ACCEPTED')
        self.assertEqual(req.request_status, 'ACCEPTED')


class WardenTimeoutRecoveryTestCase(TestCase):
    def setUp(self):
        self.machine = Machine.objects.create(
            machine_name="Test Office Machine",
            ip_address="127.0.0.1",
            port=4370,
            machine_enabled=True
        )
        self.now = timezone.now()
        self.student = student_master.objects.create(
            student_id='99999',
            student_name='Recovery Student',
            mobile_no='1234567890',
            department='CS',
            course='BTech',
            semester=1,
            hostel_name='Hostel A'
        )
        BiometricUser.objects.create(
            student=self.student,
            machine_uid=99,
            user_id='1099',
            name='Recovery Student'
        )
        
    def test_reconfigure_grace_recovery_flow(self):
        """Test API reconfiguration of grace time for a timed out student."""
        # 1. Create a request that reaches TIME_OUT
        req = outpass_request.objects.create(
            request_id=12345,
            student_id=self.student,
            requested_exit_datetime=self.now - datetime.timedelta(hours=1),
            requested_entry_datetime=self.now + datetime.timedelta(hours=2),
            early_grace=15,
            late_grace=15,
            request_status='Approved'
        )
        pbv = PendingBiometricVerification.objects.get(request=req)
        pbv.approved_at = self.now - datetime.timedelta(hours=1)
        pbv.expires_at = self.now - datetime.timedelta(minutes=10)
        pbv.verification_status = 'TIME_OUT'
        pbv.timed_out_at = self.now - datetime.timedelta(minutes=10)
        pbv.save()
        
        req.request_status = 'TIME OUT'
        req.save()
        
        # 2. Call API to recover / reconfigure grace
        from django.test import Client
        client = Client()
        session = client.session
        session['user_id'] = 1
        session['role'] = 'Warden'
        session['hostel_name'] = 'Hostel A'
        session.save()
        
        url = reverse('api_reconfigure_grace')
        response = client.post(url, {
            'request_id': 12345,
            'early_grace': 10,
            'late_grace': 20
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Verify request and PV are reset correctly
        req.refresh_from_db()
        pbv.refresh_from_db()
        
        self.assertEqual(req.request_status, 'Approved')
        self.assertEqual(req.recovery_attempts, 1)
        self.assertIsNotNone(req.recovery_started_at)
        self.assertEqual(req.early_grace, 10)
        self.assertEqual(req.late_grace, 20)
        
        self.assertEqual(pbv.verification_status, 'WAITING')
        self.assertIsNone(pbv.timed_out_at)
        
        # 3. Verify exit scan within the recovered window is successfully matched
        recovery_time = req.recovery_started_at
        AttendanceLog.objects.create(
            machine=self.machine,
            student=self.student,
            machine_uid=99,
            verify_type=1,
            attendance_time=recovery_time + datetime.timedelta(minutes=5),
            processed=False
        )
        
        res = verify_single_request(12345)
        self.assertEqual(res["verification_status"], "ACCEPTED")
        
        pbv.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual(pbv.verification_status, 'ACCEPTED')
        self.assertEqual(req.request_status, 'ACCEPTED')

    def test_second_timeout_leads_to_termination(self):
        """Test that a recovered request that times out a second time is marked as TERMINATED."""
        req = outpass_request.objects.create(
            request_id=12346,
            student_id=self.student,
            requested_exit_datetime=self.now - datetime.timedelta(hours=2),
            requested_entry_datetime=self.now + datetime.timedelta(hours=2),
            early_grace=15,
            late_grace=15,
            request_status='Approved',
            recovery_attempts=1,
            recovery_started_at=self.now - datetime.timedelta(hours=1)
        )
        pbv = PendingBiometricVerification.objects.get(request=req)
        pbv.approved_at = self.now - datetime.timedelta(hours=2)
        pbv.expires_at = self.now - datetime.timedelta(minutes=10) # expired recovery window
        pbv.verification_status = 'WAITING'
        pbv.save()
        
        # Run checker
        timed_out_count = check_expired_verifications()
        self.assertEqual(timed_out_count, 1)
        
        req.refresh_from_db()
        pbv.refresh_from_db()
        
        self.assertEqual(pbv.verification_status, 'TIME_OUT')
        self.assertEqual(req.request_status, 'TIME OUT')
        self.assertIsNotNone(req.terminated_at)

    def test_auto_termination_of_unrecovered_timeouts(self):
        """Test that requests timed out for more than 30 minutes are automatically terminated."""
        req = outpass_request.objects.create(
            request_id=12347,
            student_id=self.student,
            requested_exit_datetime=self.now - datetime.timedelta(hours=2),
            requested_entry_datetime=self.now + datetime.timedelta(hours=2),
            early_grace=15,
            late_grace=15,
            request_status='Approved'
        )
        pbv = PendingBiometricVerification.objects.get(request=req)
        pbv.verification_status = 'TIME_OUT'
        pbv.timed_out_at = self.now - datetime.timedelta(minutes=35) # Timed out 35 minutes ago
        pbv.save()
        
        req.request_status = 'TIME OUT'
        req.save()
        
        # Run checker
        check_expired_verifications()
        
        req.refresh_from_db()
        self.assertEqual(req.request_status, 'TIMEOUT_PROCESSED')
        self.assertIsNotNone(req.terminated_at)
