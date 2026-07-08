import logging
from django.utils import timezone
from zk import ZK
from zk.exception import ZKError

# Structured logger for machine connections and errors
logger = logging.getLogger('biometric.machine')

class MachineConnectionError(Exception):
    """Custom exception raised when biometric machine communication fails."""
    pass


class MockZKConnection:
    """Mock implementation of a pyzk connection for local development and testing."""
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.enabled = True
        # Keep mock users in memory
        self.users = [
            {'uid': 1, 'user_id': '101', 'name': 'Piyush', 'privilege': 0, 'password': '', 'group_id': '', 'card_number': '12345678'},
            {'uid': 2, 'user_id': '102', 'name': 'Ankit Nag', 'privilege': 0, 'password': '', 'group_id': '', 'card_number': '87654321'},
        ]
        self.logs = []

    def disable_device(self):
        self.enabled = False
        logger.info("[MockZK] Device disabled.")

    def enable_device(self):
        self.enabled = True
        logger.info("[MockZK] Device enabled.")

    def get_device_name(self):
        return "Mock eSSL MB160+ID"

    def get_firmware_version(self):
        return "v1.0.0-Mock"

    def get_serial_number(self):
        return "MOCKSERIAL123"

    def restart(self):
        logger.info("[MockZK] Device restarted.")
        return True

    def disconnect(self):
        logger.info("[MockZK] Disconnected.")

    class DummyUser:
        def __init__(self, uid, user_id, name, privilege=0, password='', group_id='', card_number=''):
            self.uid = uid
            self.user_id = user_id
            self.name = name
            self.privilege = privilege
            self.password = password
            self.group_id = group_id
            self.card = card_number

    class DummyAttendance:
        def __init__(self, uid, user_id, timestamp, status=0, punch=0):
            self.uid = uid
            self.user_id = user_id
            self.timestamp = timestamp
            self.status = status
            self.punch = punch

    def get_users(self):
        return [self.DummyUser(**u) for u in self.users]

    def get_attendance(self):
        # Simulate corrupted attendance logs scenario
        if self.ip == 'mock_corrupt':
            logger.error("[MockZK] Simulating corrupted attendance data exception.")
            raise Exception("Corrupted attendance data (mock)")

        # Generate some mock logs if empty
        if not self.logs:
            import datetime
            now = timezone.now()
            # Piyush checked in 5 minutes ago
            self.logs.append(self.DummyAttendance(1, '101', now - datetime.timedelta(minutes=5)))
            # Ankit checked in 2 minutes ago
            self.logs.append(self.DummyAttendance(2, '102', now - datetime.timedelta(minutes=2)))
        return self.logs

    def set_user(self, uid, name, privilege, password, group_id, user_id, card=0):
        for u in self.users:
            if u['user_id'] == str(user_id) or u['uid'] == uid:
                u['name'] = name
                u['privilege'] = privilege
                u['password'] = password
                u['group_id'] = group_id
                u['card_number'] = str(card)
                logger.info(f"[MockZK] Updated user {user_id} in mock storage.")
                return True
        
        self.users.append({
            'uid': uid,
            'user_id': str(user_id),
            'name': name,
            'privilege': privilege,
            'password': password,
            'group_id': group_id,
            'card_number': str(card),
        })
        logger.info(f"[MockZK] Added user {user_id} to mock storage.")
        return True

    def delete_user(self, uid=0, user_id=''):
        original_count = len(self.users)
        if uid:
            self.users = [u for u in self.users if u['uid'] != uid]
        elif user_id:
            self.users = [u for u in self.users if u['user_id'] != str(user_id)]
        
        if len(self.users) < original_count:
            logger.info(f"[MockZK] Deleted user (uid={uid}, user_id={user_id}) from mock storage.")
            return True
        return False


class MachineService:
    """Service wrapper for interacting with the eSSL biometric machine via pyzk."""

    def __init__(self, machine):
        self.machine = machine
        self.zk = None
        self.conn = None
        self.is_mock = machine.ip_address in [
            '127.0.0.1', 'mock', 'mock_offline', 'mock_timeout', 'mock_comm_fail', 'mock_corrupt',
            '192.0.2.1', '192.0.2.2', '192.0.2.3'
        ] or (machine.ip_address and machine.ip_address.startswith('192.0.2.'))

    def connect(self):
        """Establish connection to the machine. Returns connection object."""
        # Simulate connection failures in mock mode
        if self.is_mock:
            if self.machine.ip_address in ['mock_offline', '192.0.2.1']:
                logger.error(f"[MockZK] Connecting to {self.machine.machine_name} failed: Machine offline.")
                self.machine.status = 'OFFLINE'
                self.machine.save(update_fields=['status'])
                raise MachineConnectionError("Machine offline (mock)")
            
            if self.machine.ip_address in ['mock_timeout', '192.0.2.2']:
                logger.error(f"[MockZK] Connecting to {self.machine.machine_name} failed: Connection timeout.")
                self.machine.status = 'OFFLINE'
                self.machine.save(update_fields=['status'])
                raise MachineConnectionError("Connection timeout (mock)")
                
            if self.machine.ip_address in ['mock_comm_fail', '192.0.2.3']:
                logger.error(f"[MockZK] Connecting to {self.machine.machine_name} failed: Communication failure.")
                self.machine.status = 'OFFLINE'
                self.machine.save(update_fields=['status'])
                raise MachineConnectionError("Communication failure (mock)")

            logger.info(f"Connecting to Mock biometric machine {self.machine.machine_name}...")
            self.conn = MockZKConnection(self.machine.ip_address, self.machine.port)
            self.machine.status = 'ONLINE'
            self.machine.last_connected = timezone.now()
            self.machine.save(update_fields=['status', 'last_connected'])
            return self.conn

        try:
            logger.info(f"Connecting to biometric machine {self.machine.machine_name} at {self.machine.ip_address}:{self.machine.port} (Timeout: {self.machine.connection_timeout}s)...")
            self.zk = ZK(self.machine.ip_address, port=self.machine.port, timeout=self.machine.connection_timeout)
            self.conn = self.zk.connect()
            
            # Fetch device info to verify and store serial number
            try:
                sn = self.conn.get_serial_number()
                if sn and not self.machine.serial_number:
                    self.machine.serial_number = sn
            except Exception as e:
                logger.warning(f"Failed to fetch serial number for machine {self.machine.id}: {e}")

            self.machine.status = 'ONLINE'
            self.machine.last_connected = timezone.now()
            self.machine.save(update_fields=['status', 'last_connected', 'serial_number'])
            return self.conn
        except (ZKError, Exception) as e:
            logger.error(f"Failed to connect to machine {self.machine.machine_name}: {e}")
            self.machine.status = 'OFFLINE'
            self.machine.save(update_fields=['status'])
            raise MachineConnectionError(f"Connection failed: {e}")

    def disconnect(self):
        """Close connection to the machine."""
        if self.conn:
            try:
                self.conn.disconnect()
                logger.info(f"Disconnected from machine {self.machine.machine_name}.")
            except Exception as e:
                logger.warning(f"Error disconnecting from machine: {e}")
            finally:
                self.conn = None

    def disable_device(self):
        """Disable device (locks machine inputs during operations)."""
        if self.conn:
            self.conn.disable_device()

    def enable_device(self):
        """Enable device (unlocks machine inputs)."""
        if self.conn:
            self.conn.enable_device()

    def restart_device(self):
        """Restarts the device."""
        self.connect()
        try:
            self.disable_device()
            if hasattr(self.conn, 'restart'):
                self.conn.restart()
                logger.info(f"Issued restart command to machine {self.machine.machine_name}.")
            else:
                logger.warning("Restart command not supported directly by connection helper.")
        except Exception as e:
            logger.error(f"Failed to restart machine: {e}")
            raise MachineConnectionError(f"Restart failed: {e}")
        finally:
            self.disconnect()

    def get_users(self):
        """Fetch list of users from the device."""
        self.connect()
        try:
            self.disable_device()
            users = self.conn.get_users()
            self.enable_device()
            logger.info(f"Retrieved {len(users)} users from machine {self.machine.machine_name}.")
            return users
        except Exception as e:
            logger.error(f"Failed to retrieve users from machine: {e}")
            raise MachineConnectionError(f"Failed to get users: {e}")
        finally:
            self.disconnect()

    def get_attendance(self):
        """Fetch list of attendance logs from the device."""
        self.connect()
        try:
            self.disable_device()
            attendance = self.conn.get_attendance()
            self.enable_device()
            logger.info(f"Retrieved {len(attendance)} attendance records from machine {self.machine.machine_name}.")
            return attendance
        except Exception as e:
            logger.error(f"Failed to retrieve attendance logs from machine: {e}")
            raise MachineConnectionError(f"Failed to get attendance: {e}")
        finally:
            self.disconnect()

    def add_user(self, uid, name, privilege, password, group_id, user_id, card_number=0):
        """Add user to the machine."""
        self.connect()
        try:
            self.disable_device()
            card = int(card_number) if card_number and str(card_number).isdigit() else 0
            self.conn.set_user(
                uid=int(uid),
                name=name,
                privilege=int(privilege),
                password=str(password),
                group_id=str(group_id),
                user_id=str(user_id),
                card=card
            )
            self.enable_device()
            logger.info(f"Added user {user_id} ({name}) to machine {self.machine.machine_name}.")
        except Exception as e:
            logger.error(f"Failed to add user to machine: {e}")
            raise MachineConnectionError(f"Failed to add user: {e}")
        finally:
            self.disconnect()

    def update_user(self, uid, name, privilege, password, group_id, user_id, card_number=0):
        """Update existing user on the machine (uses set_user API)."""
        self.add_user(uid, name, privilege, password, group_id, user_id, card_number)

    def delete_user(self, uid=0, user_id=''):
        """Delete user from the machine."""
        self.connect()
        try:
            self.disable_device()
            self.conn.delete_user(uid=int(uid) if uid else 0, user_id=str(user_id))
            self.enable_device()
            logger.info(f"Deleted user uid={uid}/user_id={user_id} from machine {self.machine.machine_name}.")
        except Exception as e:
            logger.error(f"Failed to delete user from machine: {e}")
            raise MachineConnectionError(f"Failed to delete user: {e}")
        finally:
            self.disconnect()
