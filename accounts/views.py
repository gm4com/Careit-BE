from logging import getLogger
import subprocess
import re
import base64
import sys
import json
import jwt
from datetime import datetime, timedelta

from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.conf import settings
from django.views.generic import TemplateView
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import authenticate
from django.apps import apps
from django.views.decorators.csrf import csrf_exempt

from rest_framework import mixins, response, parsers
from rest_framework.generics import GenericAPIView,RetrieveAPIView
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from common.models import LOGIN_ATTEMPT_COUNT_RESET
from common.admin import log_with_reason
from common.views import swagger_auto_boolean_schema
from common.exceptions import Errors
from common.utils import UploadFileHandler, RSACrypt
from base.views import BaseModelViewSet, BaseLoggingMixin
from base.constants import BANK_CODES
from . import permissions
from . import authentication
from .models import User, Helper, Agreement, MobileVerification, BankAccount, TIN, BannedWord, Quiz
from missions.models import Mission
from notification.models import Notification, Tasker
from .serializers import (
    LogoutSerializer, HelperReadOnlySerializer, AuthTokenRefreshSerializer,
    AuthTokenObtainPairSerializer, SocailAuthTokenObtainPairSerializer, ProfileSerializer, PasswordSerializer,
    PasswordVerifySerializer, MobilePhoneSerializer, HelperProfileSerializer, HelperProfileImageSerializer,
    BankAccountSerializer, TINSerializer, AgreementSerializer, QuizSerializer, IDsActionSerializer
)
from notification.serializers import NotificationSerializer


logger = getLogger('django')


"""
회원
"""


class DeviceLogoutView(GenericAPIView):
    """
    기기 로그아웃 API
    """
    serializer_class = LogoutSerializer

    @swagger_auto_boolean_schema(responses={400: Errors.fields_invalid.as_p()})
    def post(self, request, *args, **kwargs):
        if 'push_token' not in request.data or not request.data['push_token']:
            raise Errors.fields_invalid
        result = False
        for device in self.request.user.device_logout(request.data['push_token']):
            result = True
            log_with_reason(self.request.user, device, 'changed', '기기 로그아웃')
        return response.Response({'result': result})


class AuthTokenObtainPairView(BaseLoggingMixin, TokenObtainPairView):
    """
    인증토큰 pair 발급
    """
    serializer_class = AuthTokenObtainPairSerializer

    @swagger_auto_schema(responses={401: Errors.attempt_count_exceeded.as_p() \
                                         + Errors.account_not_match(1).as_p() \
                                         + Errors.no_active_account.as_p()})
    def post(self, request, *args, **kwargs):
        return super(AuthTokenObtainPairView, self).post(request, *args, **kwargs)


class AuthTokenRefreshView(BaseLoggingMixin, TokenRefreshView):
    """
    인증토큰 리프레시 발급
    """
    serializer_class = AuthTokenRefreshSerializer


class AuthTokenVerifyView(BaseLoggingMixin, TokenVerifyView):
    """
    인증토큰 검증
    """
    pass


class SocialAuthTokenObtainPairView(TokenObtainPairView):
    """
    소셜인증토큰 pair 발급
    """
    serializer_class = SocailAuthTokenObtainPairSerializer


class ProfileViewSet(mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin,
                     mixins.CreateModelMixin,
                     mixins.DestroyModelMixin,
                     BaseModelViewSet):
    """
    회원 프로필 API endpoint
    """
    http_method_names = ['get', 'patch', 'post', 'delete']
    model = User
    lookup_field = 'code'

    def _acceptable_check(self, mobile=None, email=None, _recommended_by=None):
        if mobile:
            return not self.model.objects.filter(mobile=mobile).exists()
        if email:
            return not self.model.objects.filter(email=email).exists()
        if _recommended_by:
            return self.model.objects.filter(
                code=_recommended_by,
                is_active=True,
                withdrew_datetime__isnull=True,
            ).exists()
        return None

    @action(detail=False, methods=['post'])
    @swagger_auto_boolean_schema(responses={400: Errors.fields_invalid.as_p()})
    def acceptable_check(self, request, *args, **kwargs):
        """가입 가능한 값 체크"""
        rtn = {}
        # if 'mobile' in request.data and request.data['mobile']:
        #     rtn.update({'mobile': self._acceptable_check(mobile=request.data['mobile'])})
        if 'email' in request.data and request.data['email']:
            rtn.update({'email': self._acceptable_check(email=request.data['email'])})
        if 'username' in request.data and request.data['username']:
            rtn.update({'username': BannedWord.objects.check_username(request.data['username'])})
        if '_recommended_by' in request.data and request.data['_recommended_by']:
            rtn.update({'_recommended_by': self._acceptable_check(_recommended_by=request.data['_recommended_by'])})
        if rtn:
            return response.Response(rtn)
        raise Errors.fields_invalid

    def get_queryset(self):
        if self.action in ('retrieve', 'register_email'):
            return super(ProfileViewSet, self).get_queryset()
        return User.objects.filter(id=self.request.user.id)

    def get_permissions(self):
        if self.action in ('retrieve', 'partial_update', 'change_password', 'destroy'):
            self.permission_classes = (permissions.IsValidUser,)
        elif self.action in ('create', 'register_email', 'acceptable_check'):
            self.permission_classes = (permissions.AllowAny,)
        else:
            self.permission_classes = (permissions.IsAdminUser,)
        return super(ProfileViewSet, self).get_permissions()

    def get_serializer_class(self):
        if self.action == 'change_password':
            return PasswordSerializer
        else:
            return ProfileSerializer

    @action(methods=['post'], detail=False)
    def change_password(self, request, *args, **kwargs):
        if check_password(request.data['old_password'], request.user.password):
            request.user.set_password(request.data['new_password'])
            request.user.save()
            log_with_reason(request.user, request.user, 'changed', 'password')
            return response.Response({'result': True})
        else:
            raise Errors.permission_denied

    @swagger_auto_boolean_schema(responses={
        403: Errors.email_already_exist.as_p() + Errors.mobile_already_exist.as_p()
    })
    def create(self, request, *args, **kwargs):
        # 중복 재확인
        # if not self._acceptable_check(mobile=request.data['mobile']):
        #     raise Errors.mobile_already_exist
        # if not self._acceptable_check(email=request.data['email']):
        #     raise Errors.email_already_exist

        serializer_class = self.get_serializer_class()
        agreed_documents = request.data.pop('agreed_documents')
        verification_id = request.data.pop('verification_id')
        join_reward = True

        # 인증 확인
        if verification_id:
            try:
                verification = MobileVerification.objects.get(id=verification_id)
            except:
                raise Errors.invalid_verification
            if verification.number != request.data['mobile']:
                raise Errors.invalid_verification

        if not verification or 'CI' not in verification.nice_data:
            raise Errors.ci_not_authenticated

        obj = self.model.objects.filter(ci=verification.nice_data['CI']).last()
        if obj:
            if obj.is_withdrawn:
                if obj.is_service_blocked:
                    raise Errors.exist_user_blocked_and_withdrew
                else:
                    self.model.objects.filter(id=obj.id).update(**serializer_class().validate(request.data), withdrew_datetime=None)
                    obj = User.objects.get(id=obj.id)
                    join_reward = False
            else:
                if obj.is_service_blocked:
                    raise Errors.exist_user_blocked
                if obj.is_active:
                    raise Errors.user_already_exist
                else:
                    raise Errors.inactivated_user
        else:
            # 같은 ci가 없는 경우
            before_2_week = timezone.now() - timezone.timedelta(days=14)
            recent_missions = Mission.objects.filter(created_datetime__gt=before_2_week, user__mobile=verification.number) \
                .exclude(login_code='').order_by('-created_datetime')
            if recent_missions.exists():
                # 최근 일주일 내에 같은 번호로 요청된 웹 미션이 있으면 그 번호로 연결
                obj = recent_missions[0].user
                self.model.objects.filter(id=obj.id).update(**serializer_class().validate(request.data))
                obj = User.objects.get(id=obj.id)
            else:
                # 없으면 새 회원으로 가입
                obj = self.model.objects.create(**serializer_class().validate(request.data))
        obj.agreed_documents.set(agreed_documents)

        # 휴대폰 인증시 취득한 정보 유져 데이터에 저장
        verification.verifiy_user_ci(obj, deactivate_same_number=True)

        # 로그인 시도 카운트 초기화
        if User.LOGIN_ATTEMPT_MODEL.objects.get_failed_count(obj.mobile):
            User.LOGIN_ATTEMPT_MODEL.objects.reset_failed_count(obj.mobile)
        if User.LOGIN_ATTEMPT_MODEL.objects.get_failed_count(obj.email):
            User.LOGIN_ATTEMPT_MODEL.objects.reset_failed_count(obj.email)

        if join_reward:
            # 협력사 리워드
            if obj.recommended_partner:
                logger.info('협력사 %s 추천으로 가입' % obj.recommended_partner)
                reward_amount = obj.recommended_partner.reward_when_joined
                if reward_amount:
                    logger.info('추천인 리워드 포인트 : %s' % reward_amount)
                    Point = apps.get_model('payment', 'Point')
                    Point.objects.create(user=obj, amount=reward_amount,
                                        memo='가입시 추천인 입력 %s' % obj.recommended_partner.code)

            # 추천인 리워드
            if obj.recommended_user:
                logger.info('추천인 %s로 가입' % obj.recommended_user)
                Reward = apps.get_model('payment', 'Reward')
                reward = Reward.objects.get_active('customer_joined_by_recommend')
                if reward:
                    point_amount = reward.calculate_reward(0)
                    logger.info('추천인 리워드 포인트 : %s' % point_amount)

                    if point_amount:
                        # 고객 리워드 포인트 처리
                        Point = apps.get_model('payment', 'Point')
                        Point.objects.create(user=obj, amount=point_amount,
                                            memo='가입시 추천인 입력 %s' % obj.recommended_user.code)

            # 가입시 태스커
            Tasker.objects.task('joined', request, user=obj)

        return response.Response(data=serializer_class(instance=obj).data)

    @swagger_auto_schema(request_body=PasswordVerifySerializer)
    def destroy(self, request, *args, **kwargs):
        try:
            obj = self.get_object()
        except:
            raise Errors.permission_denied
        if obj.code != kwargs.get('code', ''):
            raise Errors.permission_denied
        if 'password' not in request.data:
            raise Errors.invalid_password
        if check_password(request.data['password'], request.user.password):
            obj.withdrew_datetime = timezone.now()
            obj.email = ':%s:' % obj.email
            obj.save()
            log_with_reason(obj, obj, 'changed', '탈퇴')
            return response.Response({'result': True})
        return response.Response({'result': False})

    def partial_update(self, request, *args, **kwargs):
        rtn = super(ProfileViewSet, self).partial_update(request, *args, **kwargs)
        log_with_reason(request.user, request.user, 'changed')
        return rtn


class MobilePhoneViewSet(mixins.CreateModelMixin,
                         BaseModelViewSet):
    """
    회원 휴대폰 인증 API endpoint
    """
    model = MobileVerification
    serializer_class = MobilePhoneSerializer
    permission_classes = (permissions.AllowAny,)

    def get_permissions(self):
        if self.action == 'ci':
            self.permission_classes = (permissions.IsValidUser,)
        return super(MobilePhoneViewSet, self).get_permissions()

    @action(detail=False, methods=['patch'])
    @swagger_auto_boolean_schema(responses={
        400: Errors.fields_invalid.as_p(),
        404: Errors.not_found.as_p(),
        406: Errors.timeout.as_p(),
    })
    def verify(self, request, *args, **kwargs):
        """휴대폰 번호 인증 처리"""
        if 'code' in request.data and request.data['code'] and 'id' in request.data and request.data['id']:
            mobile = MobileVerification.objects.filter(id=request.data['id'], verified_datetime__isnull=True).last()
            if not mobile:
                raise Errors.not_found
            result = mobile.verify(request.data['code'])
            if result is None:
                return Errors.timeout
            return response.Response({'result': result})
        raise Errors.fields_invalid

    @action(detail=True, methods=['patch'])
    def ci(self, request, *args, **kwargs):
        """ci 인증 처리"""
        obj = self.get_object()
        result = obj.verifiy_user_ci(request.user)
        return response.Response({'result': result})

    @swagger_auto_boolean_schema(responses={
        400: Errors.fields_invalid.as_p(),
        403: Errors.mobile_already_exist.as_p() + Errors.service_blocked.as_p()
    })
    def create(self, request, *args, **kwargs):
        if 'number' in request.data and request.data['number']:

            # 같은 번호의 회원 있는지 확인
            user = User.objects.filter(mobile=request.data['number']).last()
            if user:
                if request.data['check_duplication'] is True:
                    raise Errors.mobile_already_exist
                if user.is_service_blocked:
                    raise Errors.service_blocked

            mobile = MobileVerification.objects.create(number=request.data['number'], user=user)
            return response.Response({'id': mobile.id, 'user_code': user.code if user else None})
        raise Errors.fields_invalid


class HelperProfileViewSet(mixins.CreateModelMixin,
                           mixins.UpdateModelMixin,
                           mixins.RetrieveModelMixin,
                           mixins.ListModelMixin,
                           BaseModelViewSet):
    """
    헬퍼 프로필 API endpoint
    """
    model = Helper
    http_method_names = ['get', 'post', 'patch']
    serializer_class = HelperProfileSerializer
    lookup_field = 'user__code'
    lookup_url_kwarg = 'code'
    permission_classes = (permissions.IsValidUser,)

    def get_permissions(self):
        if self.action == 'retrieve':
            self.permission_classes = (permissions.AllowAny,)
        if self.action == 'list':
            self.permission_classes = (permissions.IsValidUser,)
        return super(HelperProfileViewSet, self).get_permissions()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            obj = self.get_object()
            if obj.user != self.request.user:
                self.serializer_class = HelperReadOnlySerializer
        elif self.action == 'list':
            self.serializer_class = HelperReadOnlySerializer
        return super(HelperProfileViewSet, self).get_serializer_class()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """헬퍼 신청"""
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if not serializer.is_valid():
            raise Errors.fields_invalid
        if hasattr(request.user, 'helper'):
            raise Errors.allowed_only_one_record
        obj = serializer.save(user=self.request.user)
        last_verification = obj.user.verifications.filter(nice_data__has_key='NAME', verified_datetime__isnull=False) \
            .order_by('verified_datetime').last()
        if last_verification and last_verification.nice_data:
            obj.name = last_verification.nice_data['NAME']
            obj.save()
            # user_data = serializer.validated_data.get('user')
            # obj.user.gender = user_data['gender']
            # obj.user.date_of_birth = user_data['date_of_birth']
            # obj.user.save()
            log_with_reason(request.user, obj, 'added', {'헬퍼승인 요청': True})
            return response.Response(data=self.serializer_class(instance=obj).data)
        raise Errors.ci_not_authenticated

    def partial_update(self, request, *args, **kwargs):
        """헬퍼 정보 수정"""
        obj = self.get_object()
        request_again = request.data.pop('request_again') if 'request_again' in request.data else None
        gender = request.data.pop('gender') if 'gender' in request.data else None
        date_of_birth = request.data.pop('date_of_birth') if 'date_of_birth' in request.data else None

        save_user = False
        if gender is not None and obj.user.gender != gender:
            obj.user.gender = gender
            save_user = True
        if date_of_birth is not None and obj.user.date_of_birth != date_of_birth:
            obj.user.date_of_birth = date_of_birth
            save_user = True
        if save_user:
            obj.user.save()
        if request_again:
            obj.request_again()
            log_with_reason(request.user, obj, 'changed', {'헬퍼승인 재요청': True})
        log_with_reason(request.user, obj, 'changed', request.data)
        return super(HelperProfileViewSet, self).partial_update(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        rtn = super(HelperProfileViewSet, self).retrieve(request, *args, **kwargs)
        obj = self.get_object()
        rtn.data['liked'] = obj.user.liked_bys.filter(created_user_id=request.user.id).exists()
        return rtn
    
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'service_tags',
                openapi.IN_QUERY,
                description='Filter by category id',
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_INTEGER)
            ),
            openapi.Parameter(
                'areas',
                openapi.IN_QUERY,
                description='Filter by areas id',
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_INTEGER)
            )
        ],
        operation_description='헬퍼 리스트'
    )
    def list(self, request, *args, **kwargs):
        """헬퍼 리스트"""
        return super(HelperProfileViewSet, self).list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super(HelperProfileViewSet, self).get_queryset()
        if self.action == 'retrieve':
            qs = qs.filter(user__withdrew_datetime__isnull=True, is_active=True)
        elif self.action == 'list':
            services = self.request.query_params.getlist('services')
            areas = self.request.query_params.getlist('areas')
            if services:
                qs = qs.filter(services__id__in=services)
            if areas:
                qs = qs.filter(accept_area__id__in=areas)
            qs.order_by('-id')
        elif self.action == 'partial_update':
            qs = qs.filter(user__withdrew_datetime__isnull=True, user=self.request.user)
        return qs


class HelperProfileImageViewSet(mixins.UpdateModelMixin,
                                mixins.RetrieveModelMixin,
                                BaseModelViewSet):
    """
    헬퍼 이미지 업로드 API endpoint
    """
    model = Helper
    http_method_names = ['post', 'get']
    serializer_class = HelperProfileImageSerializer
    lookup_field = 'user__code'
    lookup_url_kwarg = 'code'
    parser_classes = (parsers.MultiPartParser,)

    @action(detail=False, methods=['post'])
    @swagger_auto_schema(responses={400: Errors.fields_invalid.as_p()})
    def upload(self, request, *args, **kwargs):
        if not len(request.data):
            raise Errors.fields_invalid

        obj = getattr(request.user, 'helper')
        if not obj:
            raise Errors.not_found

        rtn = {}
        for field_name, file_data in request.data.items():
            if field_name in request.data and file_data:
                file = UploadFileHandler(obj, file_data).with_timestamp()
                rtn.update({field_name: request.build_absolute_uri(settings.MEDIA_URL + file.save(to=field_name))})
                if field_name == 'profile_photo_applied':
                    obj.is_profile_photo_accepted = None
                    obj.save()
        return response.Response(rtn)

    def get_queryset(self):
        return super(HelperProfileImageViewSet, self).get_queryset().filter(user=self.request.user)


bank_code_description = '[bank_code]\n' + '\n'.join(['%s %s' % (code, bank) for code, bank in BANK_CODES])


class BankAccountViewSet(mixins.RetrieveModelMixin,
                         mixins.CreateModelMixin,
                         BaseModelViewSet):
    """
    은행 계좌 API endpoint
    """
    model = BankAccount
    serializer_class = BankAccountSerializer
    lookup_field = 'helper__user__code'
    lookup_url_kwarg = 'code'

    def perform_create(self, serializer):
        serializer.save(helper=self.request.user.helper)

    @swagger_auto_schema(operation_description='등록된 은행계좌 조회\n\n---\n%s' % bank_code_description)
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_queryset().last()
        serializer = self.get_serializer(instance)
        return response.Response(data=serializer.data)

    @swagger_auto_schema(operation_description='은행계좌 등록\n\n---\n%s' % bank_code_description)
    def create(self, request, *args, **kwargs):
        return super(BankAccountViewSet, self).create(request, *args, **kwargs)

    def get_queryset(self):
        qs = super(BankAccountViewSet, self).get_queryset().filter(helper__user=self.request.user)
        code = self.request.query_params.get('code', None)
        if code:
            qs = qs.filter(bank_code=code)
        return qs


class TINViewSet(mixins.CreateModelMixin,
                 mixins.RetrieveModelMixin,
                 BaseModelViewSet):
    """
    주민번호 API endpoint
    """
    model = TIN
    serializer_class = TINSerializer
    rsa = RSACrypt(public_pem=settings.PUBLIC_KEY_FILE)
    permission_classes = (permissions.IsHelper,)
    lookup_field = 'helper__user__code'
    lookup_url_kwarg = 'code'

    def get_queryset(self):
        return super(TINViewSet, self).get_queryset().filter(helper__user_id=self.request.user.id)

    def create(self, request, *args, **kwargs):
        number = self.rsa.encrypt(request.data['number'])
        old_objects = TIN.objects.filter(helper=request.user.helper)
        log_action = 'added'
        if old_objects.exists():
            old_objects.delete()
            log_action = 'changed'
        obj = TIN.objects.create(helper=request.user.helper, number=number)
        obj.save()
        if not request.user.date_of_birth:
            # 생년월일 비어있으면 업데이트
            birth_string = request.data['number'][:6]
            if int(birth_string[:2]) < 21:
                birth_string = '20' + birth_string
            else:
                birth_string = '19' + birth_string
            request.user.date_of_birth = timezone.datetime.strptime(birth_string, '%Y%m%d').date()
            request.user.save()
        log_with_reason(request.user, obj, log_action, '주민등록번호')
        return response.Response(data=self.serializer_class(instance=obj).data)


class HelperTokenTemporaryViewSet(GenericAPIView):
    """
    기기 로그아웃 API
    """

    @swagger_auto_schema(operation_description='헬퍼에게 수락 임시 토큰')
    def post(self, request, *args, **kwargs):
        expires = datetime.now() + timedelta(hours=1)
        exp_timestamp = expires.timestamp()
        payload = {'user_id': request.user.id, 'exp': exp_timestamp}
        secret_key = settings.HELPER_SECRET_KEY

        token = jwt.encode(payload, secret_key)

        return response.Response({'token': token})
    

class HelperInformationTemporaryViewSet(RetrieveAPIView):
    authentication_classes = [authentication.HelperTemporaryAuthentication]
    serializer_class = HelperReadOnlySerializer
    permission_classes = (permissions.IsHelper,)

    def get_serializer_class(self):
        MyNewModelSerializer = type('MyNewModelSerializer', (HelperReadOnlySerializer,), {
            'Meta': type('Meta', (HelperReadOnlySerializer.Meta,), {
                'fields': ('id', 'user_id') + HelperReadOnlySerializer.Meta.fields,
            })
        })
        return MyNewModelSerializer

    @swagger_auto_schema(operation_description='헬퍼 정보')
    def get_object(self):
        user_id=self.request.user.id
        queryset = Helper.objects.filter(user_id=user_id)
        return queryset.get()

class NotificationViewSet(mixins.ListModelMixin,
                          mixins.UpdateModelMixin,
                          BaseModelViewSet):
    """
    알림 API endpoint
    """
    model = Notification
    permission_classes = (permissions.IsValidUser,)
    serializer_class = NotificationSerializer
    pagination_class = None
    http_method_names = ('get', 'put')

    def get_queryset(self):
        if self.action == 'update':
            qs = self.model.objects.get_by_usercode(self.request.user.code, days=None)
        else:
            qs = self.model.objects.get_by_usercode(self.request.user.code)
        return qs

    @action(methods=['GET'], detail=False)
    def count(self, request, *args, **kwargs):
        new_count = self.model.objects.get_by_usercode(request.user.code, exclude_read=True).count()
        return response.Response(data={'new_count': new_count})

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.did_action(request.user.code)
        return response.Response(data={})


"""
추가 정보
"""


@method_decorator(swagger_auto_schema(manual_parameters=[openapi.Parameter(
        'code', openapi.IN_QUERY, description="Page Code", type=openapi.TYPE_STRING
    )]), name='list')
class AgreementViewSet(mixins.ListModelMixin,
                       BaseModelViewSet):
    """
    약관 API endpoint
    """
    model = Agreement
    serializer_class = AgreementSerializer
    http_method_names = ('get', 'post')
    permission_classes = (permissions.IsValidUser,)

    @action(detail=False, methods=['post'])
    @swagger_auto_boolean_schema(request_body=IDsActionSerializer, responses={400: Errors.invalid_ids.as_p()})
    def agree(self, request, *args, **kwargs):
        """약관에 동의 처리"""
        if 'ids' in request.data and type(request.data['ids']) is list and request.data['ids']:
            serializer = self.get_serializer()
            serializer.agree(request.user, request.data['ids'])
            return response.Response({'result': True})
        return response.Response({'result': False})

    @action(detail=False, methods=['post'])
    @swagger_auto_boolean_schema(request_body=IDsActionSerializer, responses={400: Errors.invalid_ids.as_p()})
    def disagree(self, request, *args, **kwargs):
        """약관에 동의 철회 처리"""
        if 'ids' in request.data and type(request.data['ids']) is list and request.data['ids']:
            serializer = self.get_serializer()
            serializer.disagree(request.user, request.data['ids'])
            return response.Response({'result': True})
        return response.Response({'result': False})

    def get_permissions(self):
        if self.action == 'list':
            self.permission_classes = (permissions.AllowAny,)
        return super(AgreementViewSet, self).get_permissions()

    def get_queryset(self):
        qs = super(AgreementViewSet, self).get_queryset()
        code = self.request.query_params.get('code', 'sign')
        if code not in ('billing', 'sign'):
            code = 'sign'
        return qs.filter(page_code=code)


class QuizViewSet(mixins.ListModelMixin,
                  BaseModelViewSet):
    """
    헬퍼 퀴즈 API endpoint
    """
    model = Quiz
    serializer_class = QuizSerializer


"""
본인인증
"""


class NiceCIBase:

    def __init__(self):
        super(NiceCIBase, self).__init__()
        # NICE평가정보에서 발급한 안심본인인증 서비스 개발정보 (사이트코드, 사이트패스워드)
        self.sitecode = settings.NICE_SITE_CODE
        self.sitepasswd = settings.NICE_SITE_PW

        # 안심본인인증 모듈의 절대경로 (권한:755, FTP업로드방식: 바이너리)
        self.cb_encode_path = settings.NICE_ENCODE_PATH

    def get_by_key(self, plaindata, key):
        """인증결과 데이터 추출 함수"""
        value = ''
        keyIndex = -1
        valLen = 0

        # 복호화 데이터 분할
        arrData = plaindata.split(':')
        cnt = len(arrData)
        for i in range(cnt):
            item = arrData[i]
            itemKey = re.sub('[\d]+$', '', item)

            # 키값 검색
            if itemKey == key:
                keyIndex = i

                # 데이터 길이값 추출
                valLen = int(item.replace(key, '', 1))

                if key != 'NAME':
                    # 실제 데이터 추출
                    value = arrData[keyIndex + 1][:valLen]
                else:
                    # 이름 데이터 추출 (한글 깨짐 대응)
                    value = re.sub('[\d]+$', '', arrData[keyIndex + 1])

                break

        return value


class NiceCIView(NiceCIBase, TemplateView):
    """
    나이스본연인증
    """
    template_name = 'checkplus_main.html'

    def get_context_data(self, **kwargs):
        context = super(NiceCIView, self).get_context_data(**kwargs)

        # 인증성공 시 결과데이터 받는 리턴URL (방식:절대주소, 필수항목:프로토콜)
        returnurl = 'https://%s/accounts/ci/success/' % settings.MAIN_HOST

        # 인증실패 시 결과데이터 받는 리턴URL (방식:절대주소, 필수항목:프로토콜)
        errorurl = 'https://%s/accounts/ci/fail/' % settings.MAIN_HOST

        # 팝업화면 설정
        authtype = 'M'  # 인증타입 (공백:기본 선택화면, X:공인인증서, M:핸드폰, C:카드)
        popgubun = 'Y'  # 취소버튼 (Y:있음, N:없음)
        customize = ''  # 화면타입 (공백:PC페이지, Mobile:모바일페이지)
        gender = ''  # 성별설정 (공백:기본 선택화면, 0:여자, 1:남자)

        # 요청번호 초기화
        # :세션에 저장해 사용자 특정 및 데이타 위변조 검사에 이용하는 변수 (인증결과와 함께 전달됨)
        reqseq = ''

        # 인증요청 암호화 데이터 초기화
        enc_data = ''

        # 처리결과 메세지 초기화
        returnMsg = ''

        # 요청번호 생성
        try:
            # 파이썬 버전이 3.5 미만인 경우 check_output 함수 이용
             reqseq = subprocess.check_output([self.cb_encode_path, 'SEQ', self.sitecode])
            # reqseq = subprocess.run([cb_encode_path, 'SEQ', sitecode], capture_output=True, encoding='euc-kr').stdout
        except subprocess.CalledProcessError as e:
            # check_output 함수 이용하는 경우 1 이외의 결과는 에러로 처리됨
            reqseq = e.output.decode('euc-kr')
        #     print('cmd:', e.cmd, '\n output:', e.output)
        # finally:
        #     print('reqseq:', reqseq)

        # 요청번호 세션에 저장 (세션 이용하지 않는 경우 생략)
        # session['REQ_SEQ'] = reqseq

        # plain 데이터 생성 (형식 수정불가)
        plaindata = '7:REQ_SEQ' + str(len(reqseq)) + ':' + reqseq + '8:SITECODE' + str(
            len(self.sitecode)) + ':' + self.sitecode + '9:AUTH_TYPE' + str(len(authtype)) + ':' + authtype + '7:RTN_URL' + str(
            len(returnurl)) + ':' + returnurl + '7:ERR_URL' + str(
            len(errorurl)) + ':' + errorurl + '11:POPUP_GUBUN' + str(
            len(popgubun)) + ':' + popgubun + '9:CUSTOMIZE' + str(len(customize)) + ':' + customize + '6:GENDER' + str(
            len(gender)) + ':' + gender

        # 인증요청 암호화 데이터 생성
        try:
            # 파이썬 버전이 3.5 미만인 경우 check_output 함수 이용
             enc_data = subprocess.check_output([self.cb_encode_path, 'ENC', self.sitecode, self.sitepasswd, plaindata])
            # enc_data = subprocess.run([cb_encode_path, 'ENC', sitecode, sitepasswd, plaindata], capture_output=True,
            #                           encoding='euc-kr').stdout
        except subprocess.CalledProcessError as e:
            # check_output 함수 이용하는 경우 1 이외의 결과는 에러로 처리됨
            enc_data = e.output.decode('euc-kr')
        #     print('cmd:', e.cmd, '\n output:\n', e.output)
        # finally:
        #     print('enc_data:\n', enc_data)

        # 화면 렌더링 변수 설정
        render_params = {}
        render_params['enc_data'] = enc_data
        render_params['returnMsg'] = returnMsg

        context.update(render_params)

        return context


@method_decorator(csrf_exempt, name='dispatch')
class NiceCISuccessView(NiceCIBase, TemplateView):
    """
    나이스본연인증 성공시 뷰
    """
    template_name = 'checkplus_success.html'
    http_method_names = ['post', 'get']

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(NiceCISuccessView, self).get_context_data(**kwargs)
        data = dict()

        # CP요청번호 초기화
        reqseq = ''

        # 인증결과 복호화 데이터 초기화
        plaindata = ''

        # 처리결과 메세지 초기화
        returnMsg = ''

        # 인증결과 복호화 시간 초기화
        ciphertime = ''

        # NICE에서 전달받은 인증결과 암호화 데이터 취득
        # GET 요청 처리
        if self.request.method == 'GET':
            enc_data = self.request.GET.get('EncodeData', '')
        # POST 요청 처리
        else:
            enc_data = self.request.POST.get('EncodeData', '')

        ################################### 문자열 점검 ######################################
        errChars = re.findall('[^0-9a-zA-Z+/=]', enc_data)
        if len(re.findall('[^0-9a-zA-Z+/=]', enc_data)) > 0:
            data['returnMsg'] = '문자열오류: 입력값 확인이 필요합니다'
        if (base64.b64encode(base64.b64decode(enc_data))).decode() != enc_data:
            data['returnMsg'] = '변환오류: 입력값 확인이 필요합니다'
        #####################################################################################

        # checkplus_main에서 세션에 저장한 요청번호 취득 (세션 이용하지 않는 경우 생략)
        # try:
        #     reqseq = session['REQ_SEQ']
        # except Exception as e:
        #     print('ERR: reqseq=', reqseq)
        # finally:
        #     print('reqseq:', reqseq)

        if enc_data != '':
            # 인증결과 암호화 데이터 복호화 처리
            try:
                # 파이썬 버전이 3.5 미만인 경우 check_output 함수 이용
                plaindata = subprocess.check_output([self.cb_encode_path, 'DEC', self.sitecode, self.sitepasswd, enc_data])
                # plaindata = subprocess.run([cb_encode_path, 'DEC', sitecode, self.sitepasswd, enc_data], capture_output=True,
                #                            encoding='euc-kr').stdout
            except subprocess.CalledProcessError as e:
                # check_output 함수 이용하는 경우 1 이외의 결과는 에러로 처리됨
                plaindata = e.output.decode('euc-kr')
        else:
            data['returnMsg'] = '처리할 암호화 데이타가 없습니다.'

        # 복호화 처리결과 코드 확인
        if plaindata == -1:
            data['returnMsg'] = '암/복호화 시스템 오류'
        elif plaindata == -4:
            data['returnMsg'] = '복호화 처리 오류'
        elif plaindata == -5:
            data['returnMsg'] = 'HASH값 불일치 - 복호화 데이터는 리턴됨'
        elif plaindata == -6:
            data['returnMsg'] = '복호화 데이터 오류'
        elif plaindata == -9:
            data['returnMsg'] = '입력값 오류'
        elif plaindata == -12:
            data['returnMsg'] = '사이트 비밀번호 오류'
        else:
            # 요청번호 추출
            # requestnumber = self.get_by_key(plaindata, 'REQ_SEQ')

            # 데이터 위변조 검사 (세션 이용하지 않는 경우 분기처리 생략)
            # : checkplus_main에서 세션에 저장한 요청번호와 결과 데이터의 추출값 비교하는 추가적인 보안처리
            # if reqseq == requestnumber:
            # 인증결과 복호화 시간 생성 (생략불가)
            try:
                # 파이썬 버전이 3.5 미만인 경우 check_output 함수 이용
                ciphertime = subprocess.check_output([self.cb_encode_path, 'CTS', self.sitecode, self.sitepasswd, enc_data])
                # ciphertime = subprocess.run([cb_encode_path, 'CTS', sitecode, sitepasswd, enc_data],
                #                             capture_output=True, encoding='euc-kr').stdout
            except subprocess.CalledProcessError as e:
                # check_output 함수 이용하는 경우 1 이외의 결과는 에러로 처리됨
                ciphertime = e.output.decode('euc-kr')
            # else:
            #   returnMsg = '세션 불일치 오류'

        # 인증결과 복호화 시간 확인
        if ciphertime != '':
            #####################################################################################
            # 인증결과 데이터 추출
            # : 결과 데이터의 통신이 필요한 경우 암호화 데이터(EncodeData)로 통신 후 복호화 해주십시오
            #   복호화된 데이터를 통신하는 경우 데이터 유출에 주의해주십시오 (세션처리 권장)
            #####################################################################################
            data['returnMsg'] = "인증 성공"

            data['RES_SEQ'] = self.get_by_key(plaindata, 'RES_SEQ')
            data['AUTH_TYPE'] = self.get_by_key(plaindata, 'AUTH_TYPE')
            data['NAME'] = self.get_by_key(plaindata, 'NAME')
            data['UTF8_NAME'] = self.get_by_key(plaindata, 'UTF8_NAME')
            data['BIRTHDATE'] = self.get_by_key(plaindata, 'BIRTHDATE')
            data['GENDER'] = self.get_by_key(plaindata, 'GENDER')
            data['NATIONALINFO'] = self.get_by_key(plaindata, 'NATIONALINFO')
            data['DI'] = self.get_by_key(plaindata, 'DI')
            data['CI'] = self.get_by_key(plaindata, 'CI')
            data['MOBILE_NO'] = self.get_by_key(plaindata, 'MOBILE_NO')
            data['MOBILE_CO'] = self.get_by_key(plaindata, 'MOBILE_CO')

        obj, user = MobileVerification.objects.create_by_nice(data)
        if obj:
            result = {
                'name': data['NAME'],
                'mobile': obj.number,
                'verification_id': obj.id,
                'exist_user_code': user.code if user else '',
            }
        else:
            result = None

        context.update({'result': mark_safe(json.dumps(result))})
        return context


class NiceCIFailView(TemplateView):
    """
    나이스본연인증 실패시 뷰
    """
    template_name = 'checkplus_fail.html'
    http_method_names = ['post', 'get']

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(NiceCIFailView, self).get_context_data(**kwargs)
        data = dict()

        # CP요청번호 초기화
        reqseq = ''

        # 인증결과 복호화 데이터 초기화
        plaindata = ''

        # 인증결과 복호화 시간 초기화
        ciphertime = ''

        # GET 요청 처리
        if self.request.method == 'GET':
            enc_data = self.request.GET.get('EncodeData', '')
        # POST 요청 처리
        else:
            enc_data = self.request.POST.get('EncodeData', '')

        ################################### 문자열 점검 ######################################
        errChars = re.findall('[^0-9a-zA-Z+/=]', enc_data)
        if len(re.findall('[^0-9a-zA-Z+/=]', enc_data)) > 0:
            data['returnMsg'] = '문자열오류: 입력값 확인이 필요합니다'
        if (base64.b64encode(base64.b64decode(enc_data))).decode() != enc_data:
            data['returnMsg'] = '변환오류: 입력값 확인이 필요합니다'
        #####################################################################################

        if enc_data != '':
            try:
                # 인증결과 암호화 데이터 복호화 처리
                 plaindata = subprocess.check_output([self.cb_encode_path, 'DEC', self.sitecode, self.sitepasswd, enc_data])
                # plaindata = subprocess.run([cb_encode_path, 'DEC', sitecode, sitepasswd, enc_data], capture_output=True,
                #                            encoding='euc-kr').stdout
            except subprocess.CalledProcessError as e:
                # check_output 함수 이용하는 경우 1 이외의 결과는 에러로 처리됨
                plaindata = e.output.decode('euc-kr')
            #     print('cmd:', e.cmd, '\n output:\n', e.output)
            # finally:
            #     print('plaindata:\n', plaindata)
        else:
            data['returnMsg'] = '처리할 암호화 데이타가 없습니다.'

        # 복호화 처리결과 코드 확인
        if plaindata == -1:
            data['returnMsg'] = '암/복호화 시스템 오류'
        elif plaindata == -4:
            data['returnMsg'] = '복호화 처리 오류'
        elif plaindata == -5:
            data['returnMsg'] = 'HASH값 불일치 - 복호화 데이터는 리턴됨'
        elif plaindata == -6:
            data['returnMsg'] = '복호화 데이터 오류'
        elif plaindata == -9:
            data['returnMsg'] = '입력값 오류'
        elif plaindata == -12:
            data['returnMsg'] = '사이트 비밀번호 오류'
        else:
            # 인증결과 복호화 시간 생성
            try:
                # 파이썬 버전이 3.5 미만인 경우 check_output 함수 이용
                 ciphertime = subprocess.check_output([self.cb_encode_path, 'CTS', self.sitecode, self.sitepasswd, enc_data])
                # ciphertime = subprocess.run([cb_encode_path, 'CTS', sitecode, sitepasswd, enc_data],
                #                             capture_output=True, encoding='euc-kr').stdout
            except subprocess.CalledProcessError as e:
                # check_output 함수 이용하는 경우 1 이외의 결과는 에러로 처리됨
                ciphertime = e.output.decode('euc-kr')

            # 인증결과 데이터 추출
            data['RES_SEQ'] = self.get_by_key(plaindata, 'RES_SEQ')
            data['ERR_CODE'] = self.get_by_key(plaindata, 'ERR_CODE')
            data['AUTH_TYPE'] = self.get_by_key(plaindata, 'AUTH_TYPE')

        context.update(data)

        return context


"""
django_rest_passwordreset customizing
"""

from django.utils import timezone
from django.dispatch import Signal

from rest_framework import serializers

from django_rest_passwordreset.models import ResetPasswordToken, clear_expired, get_password_reset_token_expiry_time, \
    get_password_reset_lookup_field
from django_rest_passwordreset.signals import reset_password_token_created

from django_rest_passwordreset.views import (
    HTTP_USER_AGENT_HEADER, HTTP_IP_ADDRESS_HEADER,
    ResetPasswordValidateToken, ResetPasswordConfirm, ResetPasswordRequestToken
)


reset_password_token_created_by_mobile = Signal(
    providing_args=['instance', 'reset_password_token', 'mobile_number'],
)


class EmailMobileSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    mobile = serializers.CharField(required=False)


class CustomizedResetPasswordRequestToken(ResetPasswordRequestToken):
    serializer_class = EmailMobileSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        # before we continue, delete all existing expired tokens
        password_reset_token_validation_time = get_password_reset_token_expiry_time()

        # datetime.now minus expiry hours
        now_minus_expiry_time = timezone.now() - timezone.timedelta(hours=password_reset_token_validation_time)

        # delete all tokens where created_at < now - 24 hours
        clear_expired(now_minus_expiry_time)

        if 'email' in serializer.validated_data:
            email = serializer.validated_data['email']
            mobile = None
            users = User.objects.filter(**{'{}__iexact'.format(get_password_reset_lookup_field()): email})
        elif 'mobile' in serializer.validated_data:
            email = None
            mobile = serializer.validated_data['mobile']
            users = User.objects.filter(**{
                'mobile': mobile,
            })
        else:
            raise Errors.fields_invalid

        active_user_found = False

        # iterate over all users and check if there is any user that is active
        # also check whether the password can be changed (is useable), as there could be users that are not allowed
        # to change their password (e.g., LDAP user)
        for user in users:
            if user.eligible_for_reset():
                active_user_found = True

        # No active user found, raise a validation error
        # but not if DJANGO_REST_PASSWORDRESET_NO_INFORMATION_LEAKAGE == True
        if not active_user_found and not getattr(settings, 'DJANGO_REST_PASSWORDRESET_NO_INFORMATION_LEAKAGE', False):
            raise Errors.not_found

        # last but not least: iterate over all users that are active and can change their password
        # and create a Reset Password Token and send a signal with the created token
        for user in users:
            if user.eligible_for_reset():
                # define the token as none for now
                token = None

                # check if the user already has a token
                if user.password_reset_tokens.all().count() > 0:
                    # yes, already has a token, re-use this token
                    token = user.password_reset_tokens.all()[0]
                else:
                    # no token exists, generate a new token
                    token = ResetPasswordToken.objects.create(
                        user=user,
                        user_agent=request.META.get(HTTP_USER_AGENT_HEADER, ''),
                        ip_address=request.META.get(HTTP_IP_ADDRESS_HEADER, ''),
                    )
                # send a signal that the password token was created
                # let whoever receives this signal handle sending the email for the password reset
                if email:
                    reset_password_token_created.send(sender=self.__class__, instance=self, reset_password_token=token)
                    log_with_reason(user, token, 'added', '비밀번호 재설정 인증요청 (email)')
                if mobile:
                    reset_password_token_created_by_mobile.send(
                        sender=self.__class__,
                        instance=self,
                        reset_password_token=token,
                        mobile_number=mobile,
                    )
                    log_with_reason(user, token, 'added', '비밀번호 재설정 인증요청 (SMS)')
        # done
        return response.Response({'status': 'OK'})


reset_password_validate_token = ResetPasswordValidateToken.as_view()
reset_password_confirm = ResetPasswordConfirm.as_view()
reset_password_request_token = CustomizedResetPasswordRequestToken.as_view()

