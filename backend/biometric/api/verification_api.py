from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from biometric.models import PendingBiometricVerification
from biometric.serializers import PendingBiometricVerificationSerializer
from biometric.services.verification import verify_single_request

class PendingVerificationListCreateView(generics.ListCreateAPIView):
    """
    POST /api/pending/ - Create PendingBiometricVerification.
    GET /api/pending/ - Pending queue (verification_status == 'WAITING').
    """
    serializer_class = PendingBiometricVerificationSerializer

    def get_queryset(self):
        return PendingBiometricVerification.objects.filter(verification_status='WAITING')


class VerifiedVerificationListView(generics.ListAPIView):
    """
    GET /api/verified/ - Accepted queue (verification_status == 'ACCEPTED' or 'READY_FOR_OUT').
    """
    serializer_class = PendingBiometricVerificationSerializer

    def get_queryset(self):
        return PendingBiometricVerification.objects.filter(verification_status__in=['ACCEPTED', 'READY_FOR_OUT'])


class TimeoutVerificationListView(generics.ListAPIView):
    """
    GET /api/timeouts/ - Timeout queue (verification_status == 'TIME_OUT').
    """
    serializer_class = PendingBiometricVerificationSerializer

    def get_queryset(self):
        return PendingBiometricVerification.objects.filter(verification_status='TIME_OUT')


@api_view(['POST'])
def verify_request_api_view(request):
    """
    POST /api/verify/
    Input: {"request_id": 101}
    Triggers log fetching and executes the biometric matching logic.
    Returns the structured verification result.
    """
    request_id = request.data.get('request_id')
    if not request_id:
        return Response({"error": "request_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    result = verify_single_request(request_id)
    if result is None:
        return Response({"error": f"Verification request with ID {request_id} not found."}, status=status.HTTP_404_NOT_FOUND)

    return Response(result, status=status.HTTP_200_OK)
