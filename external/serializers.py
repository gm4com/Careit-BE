from logging import getLogger
from urllib.parse import urlparse, parse_qs

from django.contrib.auth import authenticate
from django.utils import timezone

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from common.exceptions import Errors
from common.models import LOGIN_SUCCESS, LOGIN_NOT_MATCH
from common.admin import log_with_reason
from accounts.models import User
from accounts.serializers import HelperExternalReadOnlySerializer, ProfileCodeSerializer
from missions.models import Mission, Bid, Interaction
from missions.serializers import AddressSerializer
from notification.serializers import NotificationResultSerializer
from .models import ExternalMission, ExternalMissionProduct


logger = getLogger('django')


def get_code_from_request_referer(request):
    if 'HTTP_REFERER' not in request.META or not request.META['HTTP_REFERER']:
        return None
    referer_query = parse_qs(urlparse(request.META['HTTP_REFERER']).query)
    if 'code' not in referer_query or not referer_query['code']:
        return False
    return referer_query['code'][0]


class ExternalAuthTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    외부 인증 토큰 시리얼라이져
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['id']
        # self.fields['information'] = serializers.JSONField(required=True)
        self.fields['code'] = serializers.CharField(required=True)
        self.fields['version'] = serializers.CharField(required=True)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['is_service_blocked'] = user.is_service_blocked
        return token

    def validate(self, attrs):
        code = get_code_from_request_referer(self.context['request'])
        logger.info("attr : %s" % attrs)
        if not code:
            if 'code' in attrs and attrs['code']:
                code = attrs['code']
            else:
                raise Errors.permission_denied

        authenticate_kwargs = {
            'code': code,
            'password': attrs['password'],
            'app_info': {'version': attrs['version']},
        }

        # 단말기 정보 확인
        try:
            authenticate_kwargs.update({
                'device_info': {
                    'REMOTE_ADDR': self.context['request'].META['REMOTE_ADDR'],
                    'HTTP_USER_AGENT': self.context['request'].META['HTTP_USER_AGENT'],
                    'HTTP_ACCEPT_LANGUAGE': self.context['request'].META['HTTP_ACCEPT_LANGUAGE'],
                    'HTTP_REFERER': self.context['request'].META['HTTP_REFERER'],
                }
            })
        except:
            raise Errors.invalid_information

        # 로그인 확인
        external = ExternalMission.objects.filter(login_code=authenticate_kwargs['code']).last()
        if not external \
                or external.created_datetime + timezone.timedelta(days=7) < timezone.now() \
                or not external.user.mobile.endswith(authenticate_kwargs['password']):
            result = LOGIN_NOT_MATCH
        else:
            result = LOGIN_SUCCESS

        User.LOGIN_ATTEMPT_MODEL.objects.create(
            user_id=authenticate_kwargs['code'],
            device_info=authenticate_kwargs['device_info'],
            app_info=authenticate_kwargs['app_info'],
            result=result
        )
        if result is not LOGIN_SUCCESS:
            raise Errors.not_found

        # 로그인 처리
        self.user = external.user
        log_with_reason(self.user, self.user, 'changed', '웹 로그인')
        return self.get_response_data()

    def get_response_data(self):
        refresh = self.get_token(self.user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'code': str(self.user.code),
        }


class ExternalInteractionSerializer(serializers.ModelSerializer):
    """
    외부미션용 인터랙션 시리얼라이져
    """
    receiver = ProfileCodeSerializer(read_only=True, required=False)
    created_user = ProfileCodeSerializer(read_only=True, required=False)
    state = serializers.CharField(read_only=True)

    class Meta:
        model = Interaction
        fields = ('id', 'interaction_type', 'detail', 'state', 'created_user', 'receiver')


class ExternalBidSerializer(serializers.ModelSerializer):
    """
    외부미션용 입찰 시리얼라이져
    """
    state = serializers.CharField(read_only=True)
    due_datetime = serializers.DateTimeField(write_only=True, required=False)
    active_due = serializers.CharField(read_only=True)
    helper = HelperExternalReadOnlySerializer(read_only=True, required=False)
    mobile_to_call = serializers.SerializerMethodField(method_name='get_mobile_to_call')

    class Meta:
        model = Bid
        fields = (
            'id', 'amount', 'helper', 'applied_datetime', 'content', 'due_datetime', 'active_due', 'state',
            'mobile_to_call'
        )
        extra_kwargs = {
            'helper': {'read_only': True},
            'applied_datetime': {'read_only': True},
        }

    def get_mobile_to_call(self, instance):
        return instance.helper_mobile


class ExternalMissionReadOnlySerializer(serializers.ModelSerializer):
    """
    외부미션 미션 확인 시리얼라이져
    """
    user_code = serializers.CharField(source='user.code', read_only=True)
    bids = ExternalBidSerializer(read_only=True, many=True, source='external_bids')
    final_address = AddressSerializer(read_only=True)
    push_result = NotificationResultSerializer(read_only=True, required=False)
    state = serializers.CharField(read_only=True)

    class Meta:
        model = Mission
        exclude = ('id', 'stopovers', 'is_due_date_modifiable', 'is_due_time_modifiable', 'budget', 'is_point_reward',
                   'charge_rate', 'is_at_home', 'image_at_home', 'mission_type', 'request_areas', 'user')


class ExternalMissionSerializer(serializers.ModelSerializer):
    """
    외부미션 시리얼라이져
    """
    class Meta:
        model = ExternalMission
        fields = ('data',)


class ExternalMissionProductSerializer(serializers.ModelSerializer):
    """
    외부미션 제품 시리얼라이져
    """
    class Meta:
        model = ExternalMissionProduct
        fields = '__all__'


"""
web template

# todo: 이케아 통합 후 대체할 것
"""


class WebAuthTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    외부 인증 토큰 시리얼라이져
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['id']
        # self.fields['information'] = serializers.JSONField(required=True)
        self.fields['code'] = serializers.CharField(required=True)
        self.fields['version'] = serializers.CharField(required=True)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['is_service_blocked'] = user.is_service_blocked
        return token

    def validate(self, attrs):
        code = get_code_from_request_referer(self.context['request'])
        logger.info("attr : %s" % attrs)
        if not code:
            if 'code' in attrs and attrs['code']:
                code = attrs['code']
            else:
                raise Errors.permission_denied

        authenticate_kwargs = {
            'code': code,
            'password': attrs['password'],
            'app_info': {'version': attrs['version']},
        }

        # 단말기 정보 확인
        try:
            authenticate_kwargs.update({
                'device_info': {
                    'REMOTE_ADDR': self.context['request'].META['REMOTE_ADDR'],
                    'HTTP_USER_AGENT': self.context['request'].META['HTTP_USER_AGENT'],
                    'HTTP_ACCEPT_LANGUAGE': self.context['request'].META['HTTP_ACCEPT_LANGUAGE'],
                    'HTTP_REFERER': self.context['request'].META['HTTP_REFERER'],
                }
            })
        except:
            raise Errors.invalid_information

        # 로그인 확인
        mission = Mission.objects.filter(login_code=authenticate_kwargs['code']).last()
        if not mission \
                or mission.created_datetime + timezone.timedelta(days=7) < timezone.now() \
                or not mission.user.mobile.endswith(authenticate_kwargs['password']):
            result = LOGIN_NOT_MATCH
        else:
            result = LOGIN_SUCCESS

        User.LOGIN_ATTEMPT_MODEL.objects.create(
            user_id=authenticate_kwargs['code'],
            device_info=authenticate_kwargs['device_info'],
            app_info=authenticate_kwargs['app_info'],
            result=result
        )
        if result is not LOGIN_SUCCESS:
            raise Errors.not_found

        # 로그인 처리
        self.user = mission.user
        log_with_reason(self.user, self.user, 'changed', '웹 로그인')
        return self.get_response_data()

    def get_response_data(self):
        refresh = self.get_token(self.user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'code': str(self.user.code),
        }


class WebBidSerializer(serializers.ModelSerializer):
    """
    웹 템플릿용 입찰 시리얼라이져
    """
    state = serializers.CharField(read_only=True)
    due_datetime = serializers.DateTimeField(write_only=True, required=False)
    active_due = serializers.CharField(read_only=True)
    helper = HelperExternalReadOnlySerializer(read_only=True, required=False)
    mobile_to_call = serializers.SerializerMethodField(method_name='get_mobile_to_call')
    location = serializers.SerializerMethodField('get_location', read_only=True, required=False)

    def get_location(self, instance):
        return instance.get_location_display()

    class Meta:
        model = Bid
        fields = (
            'id', 'amount', 'helper', 'applied_datetime', 'content', 'due_datetime', 'active_due',
            'location', 'state', 'mobile_to_call'
        )
        extra_kwargs = {
            'helper': {'read_only': True},
            'applied_datetime': {'read_only': True},
            'location': {'read_only': True},
        }

    def get_mobile_to_call(self, instance):
        return instance.helper_mobile


class WebMissionReadOnlySerializer(serializers.ModelSerializer):
    """
    웹 템플릿 미션 확인 시리얼라이져
    """
    user_code = serializers.CharField(source='user.code', read_only=True)
    bids = WebBidSerializer(read_only=True, many=True, source='external_bids')
    final_address = AddressSerializer(read_only=True)
    push_result = NotificationResultSerializer(read_only=True, required=False)
    state = serializers.CharField(read_only=True)

    class Meta:
        model = Mission
        exclude = ('id', 'stopovers', 'is_due_date_modifiable', 'is_due_time_modifiable', 'budget', 'is_point_reward',
                   'charge_rate', 'is_at_home', 'image_at_home', 'mission_type', 'request_areas', 'user')

