from django.contrib.sites.shortcuts import get_current_site

from rest_framework import serializers

from base.models import CachedProperties
from .models import Area, Popup


class AreaSerializer(serializers.ModelSerializer):
    """
    지역 시리얼라이져
    """
    class Meta:
        model = Area
        fields = ('id', 'name', 'parent', 'nearby')


class PopupSerializer(serializers.ModelSerializer):
    """
    팝업 시리얼라이져
    """
    link = serializers.URLField(read_only=True)

    class Meta:
        model = Popup
        fields = ('id', 'location', 'target_type', 'target_id', 'link', 'title', 'content', 'image')

    def to_representation(self, instance):
        base_url = "{0}://{1}".format(self.context['request'].scheme, self.context['request'].get_host())

        if instance.target_type == 'link':
            instance.target_id = ''
            instance.link = base_url + instance.pre_link % (
                self.context['request'].user.code if self.context['request'].user.is_authenticated else '00000'
            )
        elif instance.target_type != 'view':
            instance.target_id = '%s/%s' % (instance.target_type, instance.target_id)
            instance.target_type = 'post'
            instance.link = ''
        else:
            instance.link = ''
        return super(PopupSerializer, self).to_representation(instance)

    # @classmethod
    # def cache_user(cls):
    #     anyman = CachedProperties()
    #     if type(anyman.customer_home) is not dict:
    #         anyman.customer_home = {}
    #     anyman.customer_home['popup_user'] = cls(Popup.objects.current('user'), many=True).data

    # todo: request 별도로 처리하도록 변경해서 캐싱 메소드 다시 구현할 것.
    # todo: 헬포홈이 추가되면 cache_user를 cache로 변경하여 통합하고, 각각의 항목을 캐싱할 것.


class CustomerHomeSearchSerializer(serializers.Serializer):
    """
    고객 홈 검색 시리얼라이져
    """
    keywords = serializers.JSONField()
    template_id = serializers.IntegerField(required=False, default=None)
