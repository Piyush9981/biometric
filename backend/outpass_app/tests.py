from django.test import TestCase, Client
from outpass_app.models import system_user, student_master, outpass_request
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
import json

class UserManagementTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        # Create Super Admin session
        session = self.client.session
        session['user_id'] = 9999
        session['role'] = 'Super Admin'
        session['user_name'] = 'superadmin'
        session.save()

    def test_create_user(self):
        # 1. Create Warden
        response = self.client.post(
            reverse('api_create_user'),
            data={
                'full_name': 'Test Warden',
                'username': 'test_warden',
                'email': 'staff@school.com',
                'contact_number': '1234567890',
                'password': 'Warden@1234567',
                'role': 'Warden',
                'hostel_name': 'Hostel C',
                'department': 'CSE'
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Verify model exists
        self.assertTrue(system_user.objects.filter(user_name='test_warden').exists())
        sys_user = system_user.objects.get(user_name='test_warden')
        self.assertEqual(sys_user.role, 'Warden')
        self.assertEqual(sys_user.email, 'staff@school.com')
        self.assertEqual(sys_user.hostel_name, 'Hostel C')

    def test_update_user(self):
        # Create user first
        sys_user = system_user.objects.create(
            full_name='Old Name',
            user_name='old_user',
            email='old@school.com',
            contact='1234567890',
            password='hashedpassword',
            role='Warden',
            hostel_name='Hostel A',
            department='CSE'
        )

        # Update to Gatekeeper
        response = self.client.post(
            reverse('api_update_user'),
            data={
                'id': sys_user.user_id,
                'full_name': 'New Name',
                'username': 'new_user',
                'email': 'new@school.com',
                'contact_number': '9876543210',
                'password': 'Gatekeeper@123456',
                'role': 'Gatekeeper',
                'hostel_name': 'Main Gate',
                'department': 'Security'
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        # Verify database
        sys_user.refresh_from_db()
        self.assertEqual(sys_user.full_name, 'New Name')
        self.assertEqual(sys_user.user_name, 'new_user')
        self.assertEqual(sys_user.email, 'new@school.com')
        self.assertEqual(sys_user.role, 'Gatekeeper')

    def test_reset_password(self):
        sys_user = system_user.objects.create(
            full_name='Warden Jo',
            user_name='warden_jo',
            email='jo@school.com',
            contact='1234567890',
            password='oldpassword',
            role='Warden',
            hostel_name='Hostel B',
            department='CSE'
        )

        response = self.client.post(
            reverse('api_reset_password'),
            data=json.dumps({
                'user_id': sys_user.user_id,
                'new_password': 'Warden@1234567'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        sys_user.refresh_from_db()
        self.assertEqual(sys_user.password, 'Warden@1234567')

    def test_delete_user(self):
        sys_user = system_user.objects.create(
            full_name='Gatekeeper A',
            user_name='gate_a',
            email='gatea@school.com',
            contact='1234567890',
            password='password123',
            role='Gatekeeper',
            hostel_name='Library Gate',
            department='Security'
        )

        response = self.client.post(
            reverse('api_delete_user'),
            data=json.dumps({
                'user_id': sys_user.user_id
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        # Verify deletion
        self.assertFalse(system_user.objects.filter(user_id=sys_user.user_id).exists())

    def test_system_user_login(self):
        system_user.objects.create(
            full_name='Warden Login Test',
            user_name='warden_test',
            email='warden@school.com',
            contact='1234567890',
            password='correct_password',
            role='Warden',
            hostel_name='Hostel D',
            department='CSE'
        )

        client = Client()
        response = client.post(
            reverse('login'),
            data=json.dumps({
                'email': 'warden_test',
                'password': 'correct_password',
                'role': 'Admin'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['redirect'], '/')
        self.assertEqual(client.session['role'], 'Warden')

    def test_profile_image_upload_and_validation(self):
        good_file = SimpleUploadedFile("avatar.png", b"fake_png_data", content_type="image/png")
        response = self.client.post(
            reverse('api_create_user'),
            data={
                'full_name': 'Test Warden Image 2',
                'username': 'warden_img_good',
                'email': 'staff@school.com',
                'contact_number': '9876543210',
                'password': 'Warden@1234567',
                'role': 'Warden',
                'hostel_name': 'Hostel C',
                'department': 'CSE',
                'profile_image': good_file
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        user = system_user.objects.get(user_name='warden_img_good')
        self.assertTrue(user.profile_picture)

        if user.profile_picture:
            user.profile_picture.delete()

    def test_user_management_page_load(self):
        response = self.client.get(reverse('user_management'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'script.js')

    def test_other_views_render(self):
        for view_name in ['superadmin_dashboard', 'students', 'history']:
            response = self.client.get(reverse(view_name))
            self.assertEqual(response.status_code, 200)


class StudentManagementTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        session = self.client.session
        session['user_id'] = 9999
        session['role'] = 'Super Admin'
        session['user_name'] = 'superadmin'
        session.save()

    def test_create_student_success(self):
        good_file = SimpleUploadedFile("student_avatar.jpg", b"fake_image_bytes", content_type="image/jpeg")

        response = self.client.post(
            reverse('api_create_student'),
            data={
                'scholar_id': '230101001',
                'student_name': 'Alice Smith',
                'mobile_number': '9876543210',
                'department': 'Computer Science Department',
                'course': 'B.Sc. Information Technology (BSc.IT) (Honors)',
                'semester': '5',
                'hostel_name': 'Boys Hostel A',
                'email': 'alice@school.com',
                'profile_image': good_file
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        student = student_master.objects.get(student_id='230101001')
        self.assertEqual(student.student_name, 'Alice Smith')
        self.assertEqual(student.email, 'alice@school.com')
        self.assertEqual(student.department, 'Computer Science Department')
        self.assertEqual(student.course, 'B.Sc. Information Technology (BSc.IT) (Honors)')
        self.assertTrue(student.profile_image)

        if student.profile_image:
            student.profile_image.delete()

    def test_create_student_duplicate_id(self):
        student_master.objects.create(
            student_id='230101003',
            student_name='Charlie Brown',
            mobile_no='9876543210',
            department='Computer Science Department',
            course='B.Sc. Information Technology (BSc.IT) (Honors)',
            semester=3,
            hostel_name='Boys Hostel A',
            email='charlie@school.com'
        )

        response = self.client.post(
            reverse('api_create_student'),
            data={
                'scholar_id': '230101003',
                'student_name': 'Charlie Double',
                'mobile_number': '9876543210',
                'department': 'Computer Science Department',
                'course': 'B.Sc. Information Technology (BSc.IT) (Honors)',
                'semester': '3',
                'hostel_name': 'Boys Hostel A',
                'email': 'charlie2@school.com',
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertIn('Student ID already exists', response.json()['message'])

    def test_update_student_success(self):
        student = student_master.objects.create(
            student_id='230101005',
            student_name='Daisy',
            mobile_no='9876543210',
            department='Computer Science Department',
            course='B.Sc. Information Technology (BSc.IT) (Honors)',
            semester=3,
            hostel_name='Boys Hostel A',
            email='daisy@school.com'
        )

        good_file = SimpleUploadedFile("new_avatar.png", b"new_fake_image_bytes", content_type="image/png")

        response = self.client.post(
            reverse('api_update_student'),
            data={
                'scholar_id': '230101005',
                'student_name': 'Daisy Updated',
                'mobile_number': '9876543210',
                'department': 'Computer Science Department',
                'course': 'M.C.A. Master of Computer Applications (Data Science)',
                'semester': '4',
                'hostel_name': 'Boys Hostel A',
                'email': 'daisy_new@school.com',
                'profile_image': good_file
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        student.refresh_from_db()
        self.assertEqual(student.student_name, 'Daisy Updated')
        self.assertEqual(student.email, 'daisy_new@school.com')
        self.assertEqual(student.semester, 4)
        self.assertEqual(student.course, 'M.C.A. Master of Computer Applications (Data Science)')
        self.assertTrue(student.profile_image)

        if student.profile_image:
            student.profile_image.delete()


class BiometricScanTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        # Create a test student
        self.student = student_master.objects.create(
            student_id='230101999',
            student_name='John Doe',
            mobile_no='9999999999',
            department='Computer Science Department',
            course='B.Sc. IT',
            semester=3,
            hostel_name='Boys Hostel A',
            email='john@school.com'
        )

    def test_biometric_scan_student_not_found(self):
        response = self.client.post(
            reverse('api_biometric_scan'),
            data=json.dumps({'scholar_id': '999999999'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['success'])
        self.assertIn('Student not found', response.json()['message'])

    def test_biometric_scan_no_request(self):
        response = self.client.post(
            reverse('api_biometric_scan'),
            data=json.dumps({'scholar_id': self.student.student_id}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['success'])
        self.assertIn('No outpass request found', response.json()['message'])

    def test_biometric_scan_lifecycle(self):
        # Create an outpass request and set status to Accept
        now = timezone.now()
        req = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now,
            requested_entry_datetime=now + timezone.timedelta(hours=2),
            outing_reason='Personal',
            destination='Market',
            request_status='Accept',
            early_grace=15,
            late_grace=30,
            requested_by='warden'
        )

        # 1. First scan: Should mark OUT
        response = self.client.post(
            reverse('api_biometric_scan'),
            data=json.dumps({'scholar_id': self.student.student_id}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertIn('marked OUT', response.json()['message'])

        req.refresh_from_db()
        self.assertEqual(req.request_status, 'OUT')
        self.assertIsNotNone(req.actual_exit_datetime)

        # 2. Second scan: Should verify return (READY_FOR_IN)
        response = self.client.post(
            reverse('api_biometric_scan'),
            data=json.dumps({'scholar_id': self.student.student_id}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertIn('return scan verified', response.json()['message'])

        # Now simulate gatekeeper mark IN
        session = self.client.session
        session['user_id'] = 1
        session['role'] = 'Gatekeeper'
        session.save()
        
        from outpass_app.models import RolePermission
        RolePermission.objects.get_or_create(role='Gatekeeper', defaults={'can_mark_in': True})

        response = self.client.post(
            reverse('api_gatekeeper_mark_in'),
            data=json.dumps({'request_id': req.request_id}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        req.refresh_from_db()
        self.assertEqual(req.request_status, 'IN')
        self.assertIsNotNone(req.actual_entry_datetime)

    def test_biometric_scan_early_exit_denied(self):
        now = timezone.now()
        # Exit requested 1 hour from now, early grace is 10 mins
        req = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now + timezone.timedelta(hours=1),
            requested_entry_datetime=now + timezone.timedelta(hours=3),
            outing_reason='Medical',
            destination='Hospital',
            request_status='Accept',
            early_grace=10,
            late_grace=10,
            requested_by='warden'
        )

        response = self.client.post(
            reverse('api_biometric_scan'),
            data=json.dumps({'scholar_id': self.student.student_id}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertIn('Too early to exit', response.json()['message'])

        req.refresh_from_db()
        self.assertEqual(req.request_status, 'Accept') # remains Accept

    def test_biometric_scan_expired_exit_denied(self):
        now = timezone.now()
        # Exit requested 1 hour ago, late grace is 15 mins (so window expired 45 mins ago)
        req = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now - timezone.timedelta(hours=1),
            requested_entry_datetime=now + timezone.timedelta(hours=1),
            outing_reason='Medical',
            destination='Hospital',
            request_status='Accept',
            early_grace=15,
            late_grace=15,
            requested_by='warden'
        )

        response = self.client.post(
            reverse('api_biometric_scan'),
            data=json.dumps({'scholar_id': self.student.student_id}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertIn('exit window has expired', response.json()['message'])

        req.refresh_from_db()
        self.assertIn(req.request_status, ['Time out', 'TIME_OUT', 'TIME OUT']) # status changed to Time out

    def test_one_request_per_date_limit(self):
        # Set Warden / Admin session
        session = self.client.session
        session['user_id'] = 9999
        session['role'] = 'Warden'
        session['user_name'] = 'warden_user'
        session.save()

        now = timezone.now()
        exit_dt1 = (now + timezone.timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        entry_dt1 = (now + timezone.timedelta(days=2, hours=3)).strftime("%Y-%m-%d %H:%M:%S")

        exit_dt2 = (now + timezone.timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        entry_dt2 = (now + timezone.timedelta(days=3, hours=3)).strftime("%Y-%m-%d %H:%M:%S")

        # 1. Create first request for exit date 1
        res1 = self.client.post(
            reverse('create_request'),
            data=json.dumps({
                'scholar_id': self.student.student_id,
                'requested_exit_datetime': exit_dt1,
                'requested_entry_datetime': entry_dt1,
                'purpose': 'Personal',
                'destination': 'Market'
            }),
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.json()['success'])

        # 2. Create second request in the same day but for exit date 2 (should be allowed)
        res2 = self.client.post(
            reverse('create_request'),
            data=json.dumps({
                'scholar_id': self.student.student_id,
                'requested_exit_datetime': exit_dt2,
                'requested_entry_datetime': entry_dt2,
                'purpose': 'Medical',
                'destination': 'Clinic'
            }),
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()['success'])

        # 3. Attempt to create a third request for the same student for exit date 1 (should be blocked)
        res3 = self.client.post(
            reverse('create_request'),
            data=json.dumps({
                'scholar_id': self.student.student_id,
                'requested_exit_datetime': exit_dt1,
                'requested_entry_datetime': entry_dt1,
                'purpose': 'Personal',
                'destination': 'Mall'
            }),
            content_type='application/json'
        )
        self.assertEqual(res3.status_code, 200)
        self.assertFalse(res3.json()['success'])
        self.assertIn('Only one active request can exist', res3.json()['message'])

        # 4. Mark the first request as completed ('IN') and attempt to create a new request on exit date 1 (should be allowed)
        first_req = outpass_request.objects.filter(student_id=self.student).order_by('requested_at').first()
        first_req.request_status = 'IN'
        first_req.save()

        res4 = self.client.post(
            reverse('create_request'),
            data=json.dumps({
                'scholar_id': self.student.student_id,
                'requested_exit_datetime': exit_dt1,
                'requested_entry_datetime': entry_dt1,
                'purpose': 'Personal',
                'destination': 'Mall'
            }),
            content_type='application/json'
        )
        self.assertEqual(res4.status_code, 200)
        self.assertTrue(res4.json()['success'])

        # 5. Mark the newly created request as 'Decline' and verify another request on exit date 1 can be created
        second_req = outpass_request.objects.filter(student_id=self.student).order_by('requested_at').last()
        second_req.request_status = 'Decline'
        second_req.save()

        res5 = self.client.post(
            reverse('create_request'),
            data=json.dumps({
                'scholar_id': self.student.student_id,
                'requested_exit_datetime': exit_dt1,
                'requested_entry_datetime': entry_dt1,
                'purpose': 'Personal',
                'destination': 'Hospital'
            }),
            content_type='application/json'
        )
        self.assertEqual(res5.status_code, 200)
        self.assertTrue(res5.json()['success'])

        # 6. Mark this third request as 'Time out' and verify another request on exit date 1 is BLOCKED (active timeout)
        third_req = outpass_request.objects.filter(student_id=self.student).order_by('requested_at').last()
        third_req.request_status = 'Time out'
        third_req.save()

        res6 = self.client.post(
            reverse('create_request'),
            data=json.dumps({
                'scholar_id': self.student.student_id,
                'requested_exit_datetime': exit_dt1,
                'requested_entry_datetime': entry_dt1,
                'purpose': 'Personal',
                'destination': 'Gym'
            }),
            content_type='application/json'
        )
        self.assertEqual(res6.status_code, 200)
        self.assertFalse(res6.json()['success'])
        self.assertIn('Student already has an active outpass request', res6.json()['message'])

        # 6.b Mark the third request as 'TIMEOUT_PROCESSED' and verify another request on exit date 1 can be created
        third_req.request_status = 'TIMEOUT_PROCESSED'
        third_req.save()

        res6_b = self.client.post(
            reverse('create_request'),
            data=json.dumps({
                'scholar_id': self.student.student_id,
                'requested_exit_datetime': exit_dt1,
                'requested_entry_datetime': entry_dt1,
                'purpose': 'Personal',
                'destination': 'Gym'
            }),
            content_type='application/json'
        )
        self.assertEqual(res6_b.status_code, 200)
        self.assertTrue(res6_b.json()['success'])

        # 7. Now that the fourth request is active (Initiate), verify a fifth request on exit date 1 is blocked
        res7 = self.client.post(
            reverse('create_request'),
            data=json.dumps({
                'scholar_id': self.student.student_id,
                'requested_exit_datetime': exit_dt1,
                'requested_entry_datetime': entry_dt1,
                'purpose': 'Personal',
                'destination': 'Park'
            }),
            content_type='application/json'
        )
        self.assertEqual(res7.status_code, 200)
        self.assertFalse(res7.json()['success'])
        self.assertIn('Only one active request can exist', res7.json()['message'])


class DashboardPollingAPITests(TestCase):
    def setUp(self):
        from outpass_app.models import student_master, system_user, outpass_request
        from biometric.models import Machine, PendingBiometricVerification
        # Create student
        self.student = student_master.objects.create(
            student_id="230101001",
            student_name="Test Student",
            mobile_no="9876543210",
            department="CSE",
            course="B.Tech",
            semester=4,
            hostel_name="Hostel A",
            email="student@test.com"
        )
        # Create warden user
        self.warden = system_user.objects.create(
            full_name="Warden A",
            email="warden@test.com",
            contact="1234567890",
            user_name="warden_a",
            password="password",
            department="Admin",
            hostel_name="Hostel A",
            role="Warden",
            allowed_purposes="Emergency"
        )
        # Create gatekeeper user
        self.gatekeeper = system_user.objects.create(
            full_name="GK 1",
            email="gk@test.com",
            contact="0987654321",
            user_name="gatekeeper_1",
            password="password",
            department="Security",
            hostel_name="Hostel A",
            role="Gatekeeper"
        )
        # Create outpass request
        now = timezone.now()
        self.req = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now + timezone.timedelta(hours=1),
            requested_entry_datetime=now + timezone.timedelta(hours=3),
            outing_reason='Medical',
            destination='Hospital',
            request_status='Initiate',
            requested_by='warden_a'
        )

    def test_api_warden_updates_authorized(self):
        session = self.client.session
        session['user_id'] = self.warden.user_id
        session['role'] = 'Warden'
        session['hostel_name'] = 'Hostel A'
        session.save()

        response = self.client.get(reverse('api_warden_updates'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('stats', data)
        self.assertIn('requests', data)
        self.assertEqual(data['stats']['total_students'], 1)
        self.assertEqual(data['stats']['initial_requests'], 1)

    def test_api_gatekeeper_updates_authorized(self):
        session = self.client.session
        session['user_id'] = self.gatekeeper.user_id
        session['role'] = 'Gatekeeper'
        session.save()

        # Approve request first so it shows up in gatekeeper dashboard
        self.req.request_status = 'Accept'
        self.req.save()

        response = self.client.get(reverse('api_gatekeeper_updates'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('stats', data)
        self.assertIn('requests', data)

    def test_api_biometric_queue_updates_authorized(self):
        session = self.client.session
        session['user_id'] = self.gatekeeper.user_id
        session['role'] = 'Gatekeeper'
        session.save()

        response = self.client.get(reverse('api_biometric_queue_updates'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('queue', data)

    def test_api_biometric_machines_updates_authorized(self):
        session = self.client.session
        session['user_id'] = self.gatekeeper.user_id
        session['role'] = 'Gatekeeper'
        session.save()

        response = self.client.get(reverse('api_biometric_machines_updates'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('machines', data)


class WardenDashboardTerminalStatusTests(TestCase):
    def setUp(self):
        from outpass_app.models import student_master, system_user
        from django.utils import timezone
        
        self.student = student_master.objects.create(
            student_id="230101999",
            student_name="Terminal Test Student",
            mobile_no="9876543210",
            department="CSE",
            course="B.Tech",
            semester=4,
            hostel_name="Hostel A",
            email="term@test.com"
        )
        self.warden = system_user.objects.create(
            full_name="Warden A",
            email="warden_a@test.com",
            contact="1234567890",
            user_name="warden_a",
            password="password",
            department="Admin",
            hostel_name="Hostel A",
            role="Warden"
        )

    def test_warden_dashboard_terminal_status_visibility(self):
        from outpass_app.models import outpass_request
        from django.utils import timezone
        from django.urls import reverse

        now = timezone.now()

        # 1. Request marked IN 5 hours ago (should be visible)
        req_in_recent = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now - timezone.timedelta(hours=6),
            requested_entry_datetime=now - timezone.timedelta(hours=4),
            outing_reason='Medical',
            destination='Hospital',
            request_status='IN',
            terminated_at=now - timezone.timedelta(hours=5),
            requested_by='warden_a'
        )

        # 2. Request marked IN 25 hours ago (should be hidden)
        req_in_old = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now - timezone.timedelta(hours=30),
            requested_entry_datetime=now - timezone.timedelta(hours=28),
            outing_reason='Medical',
            destination='Hospital',
            request_status='IN',
            terminated_at=now - timezone.timedelta(hours=25),
            requested_by='warden_a'
        )

        # 3. Request marked Decline 5 hours ago (should be visible)
        req_decline_recent = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now - timezone.timedelta(hours=6),
            requested_entry_datetime=now - timezone.timedelta(hours=4),
            outing_reason='Medical',
            destination='Hospital',
            request_status='Decline',
            terminated_at=now - timezone.timedelta(hours=5),
            requested_by='warden_a'
        )

        # 4. Request marked Decline 25 hours ago (should be hidden)
        req_decline_old = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now - timezone.timedelta(hours=30),
            requested_entry_datetime=now - timezone.timedelta(hours=28),
            outing_reason='Medical',
            destination='Hospital',
            request_status='Decline',
            terminated_at=now - timezone.timedelta(hours=25),
            requested_by='warden_a'
        )

        # 5. Request marked TIME_OUT 1 hour ago (should be hidden)
        req_timeout_recent = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now - timezone.timedelta(hours=4),
            requested_entry_datetime=now - timezone.timedelta(hours=2),
            outing_reason='Medical',
            destination='Hospital',
            request_status='TIME OUT',
            terminated_at=now - timezone.timedelta(hours=1),
            requested_by='warden_a'
        )

        # Log in the warden client
        session = self.client.session
        session['user_id'] = self.warden.user_id
        session['role'] = 'Warden'
        session['hostel_name'] = 'Hostel A'
        session.save()

        # Check Warden dashboard view requests context
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        requests_in_context = list(response.context['requests'])
        
        req_ids = [r.request_id for r in requests_in_context]
        self.assertIn(req_in_recent.request_id, req_ids)
        self.assertIn(req_decline_recent.request_id, req_ids)
        self.assertNotIn(req_in_old.request_id, req_ids)
        self.assertNotIn(req_decline_old.request_id, req_ids)
        self.assertNotIn(req_timeout_recent.request_id, req_ids)

        # Check Warden updates polling API
        api_response = self.client.get(reverse('api_warden_updates'))
        self.assertEqual(api_response.status_code, 200)
        data = api_response.json()
        self.assertTrue(data['success'])
        
        api_req_ids = [r['request_id'] for r in data['requests']]
        self.assertIn(req_in_recent.request_id, api_req_ids)
        self.assertIn(req_decline_recent.request_id, api_req_ids)
        self.assertNotIn(req_in_old.request_id, api_req_ids)
        self.assertNotIn(req_decline_old.request_id, api_req_ids)
        self.assertNotIn(req_timeout_recent.request_id, api_req_ids)


class SuperAdminDashboardTerminalStatusTests(TestCase):
    def setUp(self):
        from outpass_app.models import student_master, system_user
        from django.utils import timezone
        
        self.student = student_master.objects.create(
            student_id="230101888",
            student_name="SA Test Student",
            mobile_no="9876543210",
            department="CSE",
            course="B.Tech",
            semester=4,
            hostel_name="Hostel A",
            email="sa_term@test.com"
        )
        self.superadmin = system_user.objects.create(
            full_name="Super Admin A",
            email="sa@test.com",
            contact="1234567890",
            user_name="sa_a",
            password="password",
            department="Admin",
            hostel_name="Hostel A",
            role="Super Admin"
        )

    def test_superadmin_dashboard_terminal_status_visibility(self):
        from outpass_app.models import outpass_request
        from django.utils import timezone
        from django.urls import reverse

        now = timezone.now()

        # 1. Request marked IN 5 hours ago (should be visible)
        req_in_recent = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now - timezone.timedelta(hours=6),
            requested_entry_datetime=now - timezone.timedelta(hours=4),
            outing_reason='Medical',
            destination='Hospital',
            request_status='IN',
            terminated_at=now - timezone.timedelta(hours=5),
            requested_by='warden_a'
        )

        # 2. Request marked IN 25 hours ago (should be hidden)
        req_in_old = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now - timezone.timedelta(hours=30),
            requested_entry_datetime=now - timezone.timedelta(hours=28),
            outing_reason='Medical',
            destination='Hospital',
            request_status='IN',
            terminated_at=now - timezone.timedelta(hours=25),
            requested_by='warden_a'
        )

        # 3. Request marked Decline 5 hours ago (should be visible)
        req_decline_recent = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now - timezone.timedelta(hours=6),
            requested_entry_datetime=now - timezone.timedelta(hours=4),
            outing_reason='Medical',
            destination='Hospital',
            request_status='Decline',
            terminated_at=now - timezone.timedelta(hours=5),
            requested_by='warden_a'
        )

        # 4. Request marked Decline 25 hours ago (should be hidden)
        req_decline_old = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now - timezone.timedelta(hours=30),
            requested_entry_datetime=now - timezone.timedelta(hours=28),
            outing_reason='Medical',
            destination='Hospital',
            request_status='Decline',
            terminated_at=now - timezone.timedelta(hours=25),
            requested_by='warden_a'
        )

        # 5. Request marked TIME_OUT 1 hour ago (should be hidden)
        req_timeout_recent = outpass_request.objects.create(
            student_id=self.student,
            requested_exit_datetime=now - timezone.timedelta(hours=4),
            requested_entry_datetime=now - timezone.timedelta(hours=2),
            outing_reason='Medical',
            destination='Hospital',
            request_status='TIME OUT',
            terminated_at=now - timezone.timedelta(hours=1),
            requested_by='warden_a'
        )

        # Log in the super admin client
        session = self.client.session
        session['user_id'] = self.superadmin.user_id
        session['role'] = 'Super Admin'
        session.save()

        # Check Super Admin dashboard view requests context
        response = self.client.get(reverse('superadmin_dashboard'))
        self.assertEqual(response.status_code, 200)
        requests_in_context = list(response.context['requests'])
        
        req_ids = [r.request_id for r in requests_in_context]
        self.assertIn(req_in_recent.request_id, req_ids)
        self.assertIn(req_decline_recent.request_id, req_ids)
        self.assertNotIn(req_in_old.request_id, req_ids)
        self.assertNotIn(req_decline_old.request_id, req_ids)
        self.assertNotIn(req_timeout_recent.request_id, req_ids)




