from rest_framework import serializers

from common.exceptions import Errors
from accounts.serializers import ProfileCodeSerializer
from base.models import BannedWord
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """
    알림 시리얼라이져
    """
    is_new = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = Notification
        fields = ('id', 'subject', 'content', 'data_page', 'data_type', 'data_obj_id', 'created_datetime', 'is_new')
        order_by = ('-created_datetime',)

    def get_is_new(self, obj):
        is_new = 'read' not in obj.result or self.context['request'].user.code not in obj.result['read']
        return is_new

    def to_representation(self, instance):
        data = super(NotificationSerializer, self).to_representation(instance)
        if data['is_new']:
            instance.read(self.context['request'].user.code)
        return data


class NotificationResultSerializer(serializers.ModelSerializer):
    """
    알림 시리얼라이져
    """
    success_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Notification
        fields = ('success_count',)
