from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.response import APIResponse
from apps.notifications.models import Notification

from . import swagger
from .serializers import NotificationSerializer


# Every endpoint here works on the signed-in user's own notifications only,
# so there is no module permission: anyone signed in has a bell.


@swagger.notification_list
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user)
    # Newest first; meta also carries how many are unread in all.
    page, meta = paginate(request, notifications)
    meta['unread'] = notifications.filter(read_at__isnull=True).count()
    return APIResponse(NotificationSerializer(page, many=True).data, 'Notifications fetched successfully.', meta=meta)


@swagger.notification_read
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=['read_at'])
    return APIResponse(NotificationSerializer(notification).data, 'Notification marked read.')


@swagger.notification_read_all
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notification_read_all(request):
    count = Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(
        read_at=timezone.now(), updated_at=timezone.now()
    )
    return APIResponse({'marked': count}, 'Notifications marked read.')
