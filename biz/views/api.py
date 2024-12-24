import logging

from django.utils import timezone

from rest_framework import mixins, response
from drf_yasg.utils import swagger_auto_schema
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import UntypedToken

from common.exceptions import Errors
from common.utils import get_md5_hash
from common.views import swagger_auto_boolean_schema
from base.views import BaseModelViewSet
from accounts import permissions
from accounts.serializers import AccessTokenSerializer
from accounts.models import User
from missions.models import Mission, MissionTemplate
from missions.serializers import TemplateMissionSerializer, MissionSerializer, TemplateSerializer, TemplateQuestionSerializer
from notification.models import Tasker
from biz.serializers import BizAuthTokenObtainPairSerializer, BizMissionSerializer, BizMissionReadOnlySerializer


logger = logging.getLogger('django')



class BizAuthTokenObtainPairView(TokenObtainPairView):
    """
    애니비즈 인증 토큰 pair 발급
    """
    serializer_class = BizAuthTokenObtainPairSerializer

    @swagger_auto_schema(responses={
        200: AccessTokenSerializer, 
        400: Errors.invalid_information.as_p(),
        401: Errors.no_active_account.as_p(),
        404: Errors.not_found.as_p(), 
    })
    def post(self, request, *args, **kwargs):
        return super(BizAuthTokenObtainPairView, self).post(request, *args, **kwargs)


class BizTokenDataMixin:
    """
    토큰 데이터에 협력사 정보
    """

    def check_token(self, request, *args, **kwargs):
        try:
            token = request.META['HTTP_AUTHORIZATION'].strip().split(' ')[-1]
        except:
            raise Errors.not_usable
        self.token_data = UntypedToken(token)
        if 'partnership' not in self.token_data:
            raise Errors.not_usable

    def get_queryset(self):
        self.check_token(self.request)
        return super().get_queryset()


class BizMissionViewSet(BizTokenDataMixin,
                        mixins.CreateModelMixin,
                        mixins.RetrieveModelMixin,
                        BaseModelViewSet):
    """
    애니비즈 템플릿 미션 API endpoint
    """
    model = Mission
    permission_classes = (permissions.IsActiveUser,)
    serializer_class = BizMissionSerializer
    lookup_url_kwarg = 'code'
    lookup_field = 'code'
    token_data = {}
    
    def get_queryset(self):
        qs = super(BizMissionViewSet, self).get_queryset()
        return qs.filter(template__partnership__code=self.token_data['partnership'])

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BizMissionReadOnlySerializer
        return super().get_serializer_class()

    @swagger_auto_boolean_schema(responses={
        400: Errors.fields_invalid.as_p() + Errors.missing_required_field('field_name').as_p(),
    })
    def create(self, request, *args, **kwargs):
        """애니비즈 템플릿 미션 요청"""
        self.check_token(self.request)
        try:
            template = MissionTemplate.objects.get(id=request.data['template_id'])
        except:
            raise Errors.not_found
        if not template.partnership:
            raise Errors.not_found
        if not template.partnership.get_service_state('apis'):  
            raise Errors.not_found
        if template.partnership.code != self.token_data['partnership']:
            raise Errors.not_found

        data = TemplateMissionSerializer({'data': request.data['data']}).data
        if 'data' not in data or not data['data']:
            raise Errors.fields_invalid
        try:
            username = request.data['username']
        except:
            username = ''

        mobile = ''.join(filter(str.isdigit, request.data['mobile']))

        # 미션 유져 처리
        mission_user = User.objects.get_external_mission_user(mobile, self.token_data['partnership'], username, template.partnership)
        request.user = mission_user

        # 미션 템플릿으로 미션 생성
        mission_data = template.to_mission_data(data['data'])
        if isinstance(mission_data, Exception):
            raise mission_data
        mission_data['user'] = mission_user
        serializer = MissionSerializer(data=mission_data)
        serializer.is_valid(raise_exception=True)
        serializer.context['request'] = request
        mission = serializer.save()
        mission.template = template
        mission.template_data = mission_data['template_data']

        # 자동 경유지 추가
        if mission.template.auto_stopover_address:
            mission.stopovers.add(mission.template.auto_stopover_address)

        # 웹 로그인 코드 추가
        code = str(timezone.now().timestamp())
        while True:
            login_code = get_md5_hash(code)
            if not Mission.objects.filter(login_code=login_code).exists():
                break
            code += str(mission_user.id)
        mission.login_code = login_code
        mission.save()

        # 미션 request
        if mission.request():
            logger.info('[mission %s requested]' % mission.code)
            try:
                result = mission.push_result.check_requested_count()
            except:
                result = 0

            # 고객에게 문자 발송
            Tasker.objects.task('web_requested', user=mission_user, kwargs={'url': mission.shortened_url})
        else:
            logger.info('[mission %s request failed]' % mission.code)
            result = 0

        return response.Response({
            'result': bool(result), 
            'mission_code': mission.code, 
            'push_count': mission.push_result.success_count if mission.push_result else 0
        })

    def retrieve(self, request, *args, **kwargs):
        """애니비즈 템플릿 미션 조회"""
        return super(BizMissionViewSet, self).retrieve(request, *args, **kwargs)


class BizTemplateViewSet(BizTokenDataMixin,
                         mixins.RetrieveModelMixin,
                         mixins.ListModelMixin,
                         BaseModelViewSet):
    """
    애니비즈 템플릿 API endpoint
    """
    model = MissionTemplate
    serializer_class = TemplateSerializer
    pagination_class = None
    permission_classes = (permissions.AllowAny,)
    allowed_partnerships = ('commax',)  # memo: 우선은 코맥스 이외에는 없으므로 수동으로 관리

    def get_queryset(self):
        qs = super(BizTemplateViewSet, self).get_queryset()
        if self.token_data['partnership'] not in self.allowed_partnerships:
            return qs.none()
        else:
            return qs.filter(partnership__code=self.token_data['partnership'])

    def list(self, request, *args, **kwargs):
        """애니비즈 템플릿 목록 조회"""
        return super(BizTemplateViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """애니비즈 템플릿 상세 조회"""
        rtn = super(BizTemplateViewSet, self).retrieve(request, *args, **kwargs)
        obj = self.get_object()
        rtn.data.update({'questions': TemplateQuestionSerializer(obj.ordered_questions, many=True).data})
        return rtn
