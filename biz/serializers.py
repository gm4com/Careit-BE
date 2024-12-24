from logging import getLogger

from django.utils import timezone

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from common.exceptions import Errors
from common.models import LOGIN_SUCCESS, LOGIN_NOT_MATCH
from common.admin import log_with_reason
from accounts.models import User
from missions.models import Mission
from biz.models import Campaign, CampaignQuestion, CampaignUserData, CampaignUserDataFile, Partnership, CampaignBanner


logger = getLogger('django')


class BizAuthTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    제휴사 외부 인증 토큰 시리얼라이져
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['id']
        del self.fields['password']
        # self.fields['information'] = serializers.JSONField(required=True)
        self.fields['code'] = serializers.CharField(required=True)
        self.fields['secret'] = serializers.CharField(required=True)
        self.fields['device_info'] = serializers.JSONField(required=False)
        self.fields['app_info'] = serializers.JSONField(required=False)
        # self.fields['version'] = serializers.CharField(required=True)

    @classmethod
    def get_token(cls, user, **kwargs):
        token = super().get_token(user)
        for key, val in kwargs.items():
            token[key] = val
        token['username'] = user.username
        return token

    def validate(self, attrs):
        logger.info('attr : %s' % attrs)
        authenticate_kwargs = {
            'code': attrs['code'],
            'secret': attrs['secret'],
            'device_info': attrs['device_info'] if 'device_info' in attrs else {},
            'app_info': attrs['app_info'] if 'app_info' in attrs else {},
            # 'app_info': {'version': attrs['version']},
        }

        # 단말기 정보 확인
        for item in ('REMOTE_ADDR', 'HTTP_USER_AGENT', 'HTTP_ACCEPT_LANGUAGE', 'HTTP_REFERER'):
            if item in self.context['request'].META:
                authenticate_kwargs['device_info'].update({item: self.context['request'].META[item]})
        if not authenticate_kwargs['device_info']:
            logger.warning(self.context['request'].META)
            raise Errors.invalid_information

        # 로그인 확인
        partnership = Partnership.objects.get_activated().filter(code=authenticate_kwargs['code']).last()
        if not partnership:
            raise Errors.no_active_account
        if partnership.check_secret(authenticate_kwargs['secret']):
            result = LOGIN_SUCCESS
        else:
            result = LOGIN_NOT_MATCH

        relation = partnership.user_relations.filter().first()
        if not relation:
            raise Errors.no_active_account

        User.LOGIN_ATTEMPT_MODEL.objects.create(
            user_id=authenticate_kwargs['code'],
            device_info=authenticate_kwargs['device_info'],
            app_info=authenticate_kwargs['app_info'],
            result=result
        )
        if result is not LOGIN_SUCCESS:
            raise Errors.not_found

        # 로그인 처리
        self.user = relation.user
        log_with_reason(self.user, partnership, 'changed', 'api 로그인')
        return self.get_response_data(partnership=partnership.code)

    def get_response_data(self, **kwargs):
        token = self.get_token(self.user, **kwargs)
        return {
            'refresh': str(token),
            'access': str(token.access_token),
        }


class BizMissionSerializer(serializers.ModelSerializer):
    """
    제휴사 외부 미션 시리얼라이져
    """
    template_id = serializers.IntegerField()
    username = serializers.CharField(required=False)
    mobile = serializers.CharField()
    data = serializers.JSONField()

    class Meta:
        model = Mission
        fields = ('template_id', 'username', 'mobile', 'data')


class BizMissionReadOnlySerializer(serializers.ModelSerializer):
    """
    제휴사 외부 미션 조회전용 시리얼라이져
    """
    # username = serializers.CharField(read_only=True, required=False, source='user.username')
    # mobile = serializers.CharField(read_only=True, required=False, source='user.mobile')
    state = serializers.SerializerMethodField(read_only=True, required=False)
    timeline = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = Mission
        fields = ('code', 'state', 'timeline')

    def get_state(self, obj):
        return obj.get_state_display()

    def get_timeline(self, obj):
        rtn = []
        for t in obj.timeline[1:]:
            prefix = '[헬퍼] ' if obj.user != t[1] else ''
            rtn.append([t[0], prefix + t[2]])
        return rtn


class CampaignBannerSerializer(serializers.ModelSerializer):
    """
    캠페인 배너 시리얼라이져
    """
    link = serializers.URLField(read_only=True)
    location = serializers.SerializerMethodField(read_only=True)
    target_type = serializers.SerializerMethodField(read_only=True)
    target_id = serializers.SerializerMethodField(read_only=True)
    title = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CampaignBanner
        fields = ('id', 'location', 'target_type', 'target_id', 'link', 'title', 'image')

    def get_location(self, obj):
        locations = {
            1: 'helper',
            2: 'user',
            3: 'web'
        }
        return locations[obj.location]

    def get_target_type(self, obj):
        return 'webview'

    def get_target_id(self, obj):
        return ''

    def get_title(self, obj):
        return obj.campaign.title

    def to_representation(self, instance):
        base_url = "{0}://{1}".format(self.context['request'].scheme, self.context['request'].get_host())
        instance.link = base_url + instance.pre_link % (
            self.context['request'].user.code if self.context['request'].user.is_authenticated else '0'
        )
        return super(CampaignBannerSerializer, self).to_representation(instance)


class CampaignQuestionSerializer(serializers.ModelSerializer):
    """
    캠페인 질문 시리얼라이져
    """
    class Meta:
        model = CampaignQuestion
        fields = ('id', 'question_type', 'name', 'title', 'description', 'select_options', 'has_etc_input', 'is_required')


class CampaignSerializer(serializers.ModelSerializer):
    """
    캠페인 템플릿 시리얼라이져
    """
    class Meta:
        model = Campaign
        fields = ('title',)


class CampaignUserDataSerializer(serializers.Serializer):
    """
    캠페인 유져 데이터 시리얼라이져
    """
    data = serializers.ListField('템플릿 요청 데이터')


class CampaignUserDataFileSerializer(serializers.ModelSerializer):
    """
    캠페인 유져 데이터 파일 시리얼라이져
    """
    class Meta:
        model = CampaignUserDataFile
        fields = ('attach',)
