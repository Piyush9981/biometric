from rest_framework import serializers
from biometric.models import Machine, BiometricUser, AttendanceLog, PendingBiometricVerification, SyncHistory

class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = '__all__'
        read_only_fields = ['status', 'last_connected', 'last_attendance_time', 'last_successful_sync', 'created_at', 'updated_at']


class BiometricUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiometricUser
        fields = '__all__'
        read_only_fields = ['last_sync', 'created_at', 'updated_at']


class AttendanceLogSerializer(serializers.ModelSerializer):
    machine_name = serializers.CharField(source='machine.machine_name', read_only=True)

    class Meta:
        model = AttendanceLog
        fields = '__all__'
        read_only_fields = ['processed', 'created_at']


class PendingBiometricVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PendingBiometricVerification
        fields = '__all__'
        read_only_fields = ['verified_at', 'timed_out_at', 'attendance_log', 'remarks']

    def validate(self, data):
        """
        Validate that expires_at is after approved_at.
        """
        approved_at = data.get('approved_at')
        expires_at = data.get('expires_at')
        if approved_at and expires_at and expires_at <= approved_at:
            raise serializers.ValidationError("Expiry time must be after approval time.")
        return data


class SyncHistorySerializer(serializers.ModelSerializer):
    machine_name = serializers.CharField(source='machine.machine_name', read_only=True)

    class Meta:
        model = SyncHistory
        fields = '__all__'
        read_only_fields = ['started_at', 'completed_at', 'total_records', 'status', 'remarks']
