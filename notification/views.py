from django.conf import settings

from rest_framework import mixins, response
from base.views import BaseModelViewSet
from accounts import permissions

from .models import Notification
from .serializers import NotificationSerializer


class RelayNotificationViewSet(mixins.RetrieveModelMixin,
                               BaseModelViewSet):
    """
    알림 릴레이 처리 API endpoint
    """
    model = Notification
    serializer_class = NotificationSerializer
    pagination_class = None
    permission_classes = (permissions.AllowAny,)

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        if settings.NOTIFICATION['relay_url'] is None:
            return response.Response({'result': obj.send_worker_start()})
        return response.Response({'result': False})
