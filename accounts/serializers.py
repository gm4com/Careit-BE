import logging

from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.backends import TokenBackend

from common.utils import CachedProperties
from common.fields import FullURLField
from common.exceptions import Errors
from common.models import LOGIN_SUCCESS, LOGIN_ATTEMPT_COUNT_EXCEEDED, LOGIN_ATTEMPT_COUNT_RESET, LOGIN_DEACTIVATED
from common.admin import log_with_reason
from .models import (
    User, LoggedInDevice, MobileVerification, Helper, BannedWord, BankAccount, TIN,
    Agreement, Quiz, QuizAnswer
)


LOGIN_ATTEMPT_TRY = 4

logger = logging.getLogger('django')


class LogoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoggedInDevice
        fields = ('push_token',)


class AuthTokenRefreshSerializer(TokenRefreshSerializer):
    """
    리프레시 토큰 시리얼라이져
    """
    def validate(self, attrs):
        data = super(AuthTokenRefreshSerializer, self).validate(attrs)
        try:
            token_data = TokenBackend(algorithm='HS256').decode(data['access'], verify=False)
            user = User.objects.get(id=token_data['id'])
        except:
            pass
        else:
            user.last_login = timezone.now()
            user.save()
        return data


class AccessTokenSerializer(serializers.Serializer):
    """
    액세스 토큰만 리턴하는 시리얼라이져
    """
    access = serializers.CharField()


class AuthTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    인증 토큰 시리얼라이져
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['information'] = serializers.JSONField(required=True)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['is_service_blocked'] = user.is_service_blocked
        return token

    def validate(self, attrs):
        authenticate_kwargs = {
            'email': attrs['id'],
            'password': attrs['password'],
        }
        try:
            authenticate_kwargs['request'] = self.context['request']
        except KeyError:
            pass

        # 단말기 정보 확인
        # todo: 빈 값도 확인할지 검토할 것.
        try:
            authenticate_kwargs.update({
                'device_info': attrs['information']['deviceInfo'] or {},
                'app_info': attrs['information']['appInfo'] or {},
            })
        except:
            raise Errors.invalid_information

        # 로그인 시도 횟수 검사
        failed_count = User.LOGIN_ATTEMPT_MODEL.objects.get_failed_count(attrs['id'])
        if failed_count > LOGIN_ATTEMPT_TRY:
            User.LOGIN_ATTEMPT_MODEL.objects.create(
                user_id=attrs['id'],
                device_info=authenticate_kwargs['device_info'],
                app_info=authenticate_kwargs['app_info'],
                result=LOGIN_ATTEMPT_COUNT_EXCEEDED
            )  # todo: 이를 기록할지 여부는 다시 고민할 것.
            raise Errors.attempt_count_exceeded

        # 로그인 확인
        self.user = authenticate(**authenticate_kwargs)
        if self.user is None:
            raise Errors.account_not_match(failed_count + 1)

        # 비활성 계정 확인
        if not self.user.is_active or self.user.is_withdrawn:
            User.LOGIN_ATTEMPT_MODEL.objects.create(
                user_id=attrs['id'],
                device_info=authenticate_kwargs['device_info'],
                app_info=authenticate_kwargs['app_info'],
                result=LOGIN_DEACTIVATED
            )
            raise Errors.no_active_account

        # 기기 로그인 처리
        push_token = (attrs['information']['pushToken'] if 'pushToken' in attrs['information'] else '') or ''
        logged_in_device = self.user.device_login(
            push_token,
            authenticate_kwargs['device_info'],
            authenticate_kwargs['app_info']
        )
        log_with_reason(self.user, logged_in_device, 'changed', '기기 로그인')

        self.user.last_login = timezone.now()
        self.user.save()
        return self.get_response_data()

    def get_response_data(self):
        refresh = self.get_token(self.user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'code': str(self.user.code),
        }


class SocailAuthTokenObtainPairSerializer(AuthTokenObtainPairSerializer):
    """
    소셜 인증 토큰 시리얼라이져
    """

    def __init__(self, *args, **kwargs):
        super(serializers.Serializer, self).__init__(*args, **kwargs)

    def get_fields(self):
        return {
            'email': serializers.CharField(),
            'social_id': serializers.CharField(),
            'social_type': serializers.CharField(),
            'access_token': serializers.CharField(),
            'refresh_token': serializers.CharField(),
        }

    def validate(self, attrs):
        identifier = {}
        field_values = {}

        # social_id validation
        if not attrs['social_id']:
            raise Errors.invalid_social_id

        # social_type validation
        if attrs['social_type'] == 'kakao':
            identifier.update({'kakao_id': attrs['social_id']})
        elif attrs['social_type'] == 'naver':
            identifier.update({'naver_id': attrs['social_id']})
        else:
            raise Errors.invalid_social_type

        # email validation
        # try:
        #     EmailValidator()(attrs['email'])
        #     field_values.update({'email': attrs['email']})
        # except:
        #     raise Error.invalid_email

        self.user, is_created = User.objects.get_or_create(**identifier)

        # 소셜계정 정보 저장
        for key, value in field_values.items():
            setattr(self.user, key, value)
        self.user.save()

        # todo: 토큰 검증 및 기발급 토큰 무력화 추가

        return self.get_response_data()


class PasswordVerifySerializer(serializers.ModelSerializer):
    """
    비밀번호 확인 시리얼라이져
    """
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('password',)


class PasswordSerializer(serializers.ModelSerializer):
    """
    사용자 시리얼라이져
    """
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('old_password', 'new_password')


class SimpleProfileSerializer(serializers.ModelSerializer):
    """
    간단 사용자 프로필 시리얼라이져
    """
    state = serializers.CharField(required=False, read_only=True)

    class Meta:
        model = User
        fields = (
            'code', 'mobile', 'email', 'username', 'state'
        )


class ProfileSerializer(serializers.ModelSerializer):
    """
    사용자 프로필 시리얼라이져
    """
    state = serializers.CharField(required=False, read_only=True)
    mission_requested_count = serializers.IntegerField(required=False, read_only=True)
    mission_canceled_count = serializers.IntegerField(required=False, read_only=True)
    user_review_average = serializers.FloatField(required=False, read_only=True)
    user_review_count = serializers.IntegerField(required=False, read_only=True)
    point_balance = serializers.IntegerField(required=False, read_only=True)
    is_ci = serializers.BooleanField(required=False, read_only=True)
    is_adult = serializers.NullBooleanField(required=False, read_only=True)
    verification_id = serializers.IntegerField(write_only=True)
    information = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = User
        fields = (
            'code', 'mobile', 'email', 'password', 'username', 'date_of_birth', 'gender', 'is_ad_allowed',
            'is_push_allowed', 'agreed_documents', 'level', 'created_datetime', 'state', '_recommended_by',
            'mission_requested_count', 'mission_canceled_count', 'user_review_average', 'user_review_count',
            'point_balance', 'is_ci', 'is_adult', 'is_helper_main', 'is_staff', 'verification_id', 'information'
        )
        extra_kwargs = {
            'code': {'read_only': True},
            'password': {'write_only': True},
            # 'mobile': {'read_only': True},
            'agreed_documents': {'read_only': True},
            'created_datetime': {'read_only': True},
            'level': {'read_only': True},
            'is_staff': {'read_only': True},
        }

    def validate(self, attrs):
        if 'username' in attrs and not BannedWord.objects.check_username(attrs['username']):
            raise Errors.invalid_username
        if '_recommended_by' in attrs and len(attrs['_recommended_by']) > 5:
            raise Errors.invalid_recommended_by
        if 'password' in attrs:
            attrs['password'] = make_password(attrs['password'])
        if 'information' in attrs and self.instance:
            try:
                self.instance.update_push_token(
                    push_token=attrs['information']['pushToken'] or '',
                    device_info=attrs['information']['deviceInfo'] or {},
                    app_info=attrs['information']['appInfo'] or {}
                )
            except:
                logger.error('[Auth] [%s] 푸쉬토큰 업데이트 실패.\n%s' % (self.instance.code, attrs))
        return super(ProfileSerializer, self).validate(attrs)


class ProfileCodeSerializer(serializers.ModelSerializer):
    """
    고객 코드 시리얼라이져
    """
    class Meta:
        model = User
        fields = ('code', 'id', 'username')
        extra_kwargs = {
            'code': {'read_only': True},
            'id': {'read_only': True},
            'username': {'read_only': True},
        }


class ProfilePhotoSerializer(serializers.ModelSerializer):
    """
    고객 프로필 사진 시리얼라이져
    """
    profile_photo = FullURLField()

    class Meta:
        model = User
        fields = ('code', 'id', 'username', 'profile_photo')
        extra_kwargs = {
            'code': {'read_only': True},
            'id': {'read_only': True},
            'username': {'read_only': True},
        }


class MissionProfileSerializer(serializers.ModelSerializer):
    """
    미션 표시용 고객 시리얼라이져
    """
    class Meta:
        model = User
        fields = ('code', 'id', 'username', 'mission_requested_count', 'user_review_average', 'user_review_count')
        extra_kwargs = {
            'code': {'read_only': True},
            'id': {'read_only': True},
            'username': {'read_only': True},
        }


class AdminProfileSerializer(serializers.ModelSerializer):
    """
    관리자 프로필 시리얼라이져
    """
    class Meta:
        model = User
        fields = ('code', 'id', 'username', 'mobile')
        extra_kwargs = {
            'code': {'read_only': True},
            'id': {'read_only': True},
            'username': {'read_only': True},
            'mobile': {'read_only': True},
        }


class MobilePhoneSerializer(serializers.ModelSerializer):
    """
    사용자 휴대폰 인증 시리얼라이져
    """
    check_duplication = serializers.BooleanField(label='중복 확인', write_only=True)

    class Meta:
        model = MobileVerification
        fields = ('id', 'number', 'code', 'check_duplication')


class HelperProfileSerializer(serializers.ModelSerializer):
    """
    헬퍼 프로필 시리얼라이져
    """
    # todo: request가 연속으로 두번 일어나지 않도록 이 부분에 반환할 정보 추가할 것.
    code = serializers.CharField(source='user.code', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    gender = serializers.BooleanField(source='user.gender', read_only=True)
    date_of_birth = serializers.DateField(source='user.date_of_birth', read_only=True)
    request_again = serializers.BooleanField(write_only=True, default=False)
    request_state = serializers.CharField(read_only=True)
    cash_balance = serializers.IntegerField(read_only=True)
    withdrawable_cash_balance = serializers.IntegerField(read_only=True)
    service_tags = serializers.ListField(required=False)
    helper_review_average = serializers.FloatField(source='review_average', read_only=True)
    helper_review_count = serializers.IntegerField(source='review_count', read_only=True)
    mission_done_count = serializers.IntegerField(read_only=True)
    mission_done_in_30_days_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Helper
        fields = (
            'code', 'username', 'profile_photo', 'push_allowed_from', 'push_allowed_to',
            'is_mission_request_push_allowed', 'is_online_acceptable', 'accept_area',
            'gender', 'date_of_birth', 'is_profile_public', 'is_nearby_push_allowed', 'has_pet',
            'introduction', 'best_moment', 'service_tags', 'experience', 'licenses', 'means_of_transport',
            'usable_tools', 'level', 'has_crime_report', 'name', 'accepted_datetime',
            'address_area', 'address_detail_1', 'address_detail_2', 'id_photo', 'id_person_photo',
            'request_state', 'rejected_datetime', 'rejected_reason', 'cash_balance',
            'withdrawable_cash_balance', 'helper_review_average', 'helper_review_count', 'mission_done_count',
            'mission_done_in_30_days_count', 'request_again'
        )
        extra_kwargs = {
            'level': {'read_only': True},
            'name': {'required': False, 'read_only': True},
            'profile_photo': {'required': False, 'read_only': True},
            'id_photo': {'read_only': True},
            'id_person_photo': {'read_only': True},
            'rejected_datetime': {'read_only': True},
            'rejected_reason': {'read_only': True},
            'accepted_datetime': {'read_only': True},
        }

    def create(self, validated_data):
        if 'request_again' in validated_data:
            validated_data.pop('request_again')
        service_tags = validated_data.pop('service_tags') if 'service_tags' in validated_data else None
        obj = super(HelperProfileSerializer, self).create(validated_data)
        if service_tags:
            obj.service_tags = service_tags
        return obj


class HelperReadOnlySerializer(serializers.ModelSerializer):
    """
    헬퍼 조회용 시리얼라이져
    """
    code = serializers.CharField(source='user.code', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    gender = serializers.BooleanField(source='user.gender', read_only=True)
    mobile = serializers.CharField(source='user.mobile', read_only=True)
    date_of_birth = serializers.DateField(source='user.date_of_birth', read_only=True)
    helper_review_average = serializers.FloatField(source='review_average', read_only=True)
    helper_review_count = serializers.IntegerField(source='review_count', read_only=True)
    mission_done_count = serializers.IntegerField()
    mission_done_in_30_days_count = serializers.IntegerField()
    service_tags = serializers.ListField()
    profile_photo = FullURLField()

    class Meta:
        model = Helper
        fields = (
            'code', 'profile_photo', 'is_profile_public', 'username', 'name', 'gender', 'mobile', 'date_of_birth',
            'has_pet', 'accept_area', 'introduction', 'best_moment', 'service_tags', 'experience', 'licenses',
            'means_of_transport', 'usable_tools', 'level', 'accepted_datetime', 'helper_review_average',
            'helper_review_count', 'mission_done_count', 'mission_done_in_30_days_count',
        )
        extra_kwargs = {
            'code': {'read_only': True},
            'level': {'read_only': True},
            'profile_photo': {'required': False, 'read_only': True},
            'id_photo': {'read_only': True},
            'id_person_photo': {'read_only': True},
        }


class HelperExternalReadOnlySerializer(HelperReadOnlySerializer):
    """
    헬퍼 외부 조회용 시리얼라이져
    """
    accept_area = serializers.SerializerMethodField(method_name='get_accept_area')

    def get_accept_area(self, instance):
        return [str(area) for area in instance.accept_area.all()]


class HelperProfileImageSerializer(serializers.Serializer):
    """
    헬퍼 이미지 시리얼라이져
    """
    profile_photo = serializers.ImageField(required=False)
    profile_photo_applied = serializers.ImageField(required=False)
    is_profile_photo_accepted = serializers.NullBooleanField(required=False, read_only=True)
    profile_photo_rejected = serializers.ImageField(required=False, read_only=True)
    id_photo = serializers.ImageField(required=False)
    id_person_photo = serializers.ImageField(required=False)


class BankAccountSerializer(serializers.ModelSerializer):
    """
    은행 계좌 시리얼라이져
    """
    class Meta:
        model = BankAccount
        fields = ('bank_code', 'number')


class TINSerializer(serializers.ModelSerializer):
    """
    주민번호 시리얼라이져
    """
    number = serializers.CharField()

    class Meta:
        model = TIN
        fields = ('number',)

    def to_representation(self, instance):
        instance.number = '*************'
        return super(TINSerializer, self).to_representation(instance)


class QuizAnswerSerializer(serializers.ModelSerializer):
    """
    퀴즈 답안 시리얼라이져
    """
    class Meta:
        model = QuizAnswer
        fields = ('text', 'is_correct')


class QuizSerializer(serializers.ModelSerializer):
    """
    퀴즈 시리얼라이져
    """
    answers = QuizAnswerSerializer(many=True)

    class Meta:
        model = Quiz
        fields = ('title', 'answers')


class AgreementSerializer(serializers.HyperlinkedModelSerializer):
    """
    약관 시리얼라이져
    """
    class Meta:
        model = Agreement
        fields = ('id', 'title', 'content', 'is_required')

    def agree(self, user, ids):
        try:
            user.agreed_documents.add(*ids)
            return ids
        except:
            raise Errors.invalid_ids

    def disagree(self, user, ids):
        try:
            user.agreed_documents.remove(*ids)
            return ids
        except:
            raise Errors.invalid_ids


class IDsActionSerializer(serializers.Serializer):
    """
    ID 액션 시리얼라이져
    """
    ids = serializers.ListField(label='IDs', child=serializers.IntegerField(), help_text='id')


"""
홈 화면용 시리얼라이져 캐싱
"""


class CustomerHomeHelperSerializer(HelperReadOnlySerializer):
    """
    고객 홈 표시용 헬퍼 시리얼라이져
    """
    service_tags = serializers.ListField(read_only=True)

    class Meta:
        model = Helper
        fields = (
            'id', 'code', 'username', 'gender', 'date_of_birth', 'helper_review_average', 'helper_review_count',
            'mission_done_count', 'service_tags', 'profile_photo', 'mission_done_in_30_days_count'
        )

    @classmethod
    def cache(cls):
        anyman = CachedProperties()
        if type(anyman.customer_home) is not dict:
            anyman.customer_home = {}
        try:
            anyman.customer_home['helpers'] = cls(Helper.objects.filter(is_at_home=True, is_profile_public=True), many=True).data
        except:
            pass

