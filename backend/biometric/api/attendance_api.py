from rest_framework import generics
from biometric.models import AttendanceLog
from biometric.serializers import AttendanceLogSerializer

class AttendanceLogListView(generics.ListAPIView):
    """
    GET /api/attendance/ - Returns the list of all stored attendance logs.
    """
    queryset = AttendanceLog.objects.all()
    serializer_class = AttendanceLogSerializer
