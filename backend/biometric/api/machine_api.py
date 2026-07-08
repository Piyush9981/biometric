from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from biometric.models import Machine
from biometric.serializers import MachineSerializer
from biometric.services.sync import sync_all_logs

class MachineViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows machines to be viewed or edited.
    """
    queryset = Machine.objects.all()
    serializer_class = MachineSerializer


@api_view(['GET'])
def machine_status_view(request):
    """
    GET /api/status/
    Returns the connection and operational status of all registered machines, including config settings.
    """
    machines = Machine.objects.all()
    data = []
    for m in machines:
        data.append({
            'id': m.id,
            'machine_name': m.machine_name,
            'ip_address': m.ip_address,
            'port': m.port,
            'status': m.status,
            'machine_enabled': m.machine_enabled,
            'auto_sync_enabled': m.auto_sync_enabled,
            'connection_timeout': m.connection_timeout,
            'polling_interval': m.polling_interval,
            'last_connected': m.last_connected,
            'last_attendance_time': m.last_attendance_time,
            'last_successful_sync': m.last_successful_sync,
        })
    return Response(data, status=status.HTTP_200_OK)


@api_view(['POST'])
def trigger_sync_view(request):
    """
    POST /api/sync/
    Manually triggers downloading of new attendance logs from all devices.
    """
    try:
        total_synced = sync_all_logs()
        return Response({
            'status': 'success',
            'message': 'Log sync completed.',
            'total_synced_logs': total_synced
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Sync failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
