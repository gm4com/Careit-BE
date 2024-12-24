import logging
from re import template

import requests

from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q

from rest_framework import mixins, response, parsers
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet, ViewSet
from drf_yasg.utils import swagger_auto_schema, no_body
from drf_yasg import openapi

from common.views import swagger_auto_boolean_schema
from common.exceptions import Errors
from common.admin import log_with_reason
from common.utils import get_md5_hash, CachedProperties
from base.models import BannedWord
from base.exceptions import ExternalErrors
from base.constants import MISSION_STATUS
from base.views import BaseModelViewSet
from accounts import permissions
from accounts import authentication
from accounts.models import MobileVerification
from notification.models import Notification, Tasker
from .models import (
    MissionTemplate, MissionType, Address, MultiMission, MultiAreaMission, Mission, MissionFile, Bid, BidFile, Interaction,
    Review, Report, TemplateCategory, TemplateQuestion, UserBlock, FavoriteUser, SafetyNumber
)
from .serializers import (
    TemplateCategorySerializer, TemplateQuestionSerializer, TemplateSerializer, TemplateMissionSerializer,
    MissionTypeSerializer, MissionAvailableSerializer, TemplateWithTagsSerializer,
    AddressSerializer, MultiMissionSerializer, MissionSerializer, MissionReadOnlySerializer, MissionFileSerializer,
    AnytalkBidSerializer, BidFileSerializer, BidSerializer, UserBidSerializer, InteractionSerializer,
    ReviewSerializer, ReportSerializer, UserBlockSerializer,
    FavoriteUserSerializer, ReportRequestBody, ReviewRequestBody, UserBlockRequestBody, FavoriteUserRequestBody,
    UserBidTemporarySerializer
)
from .utils import IkeaProductCrawler


logger = logging.getLogger('payment')

anyman = CachedProperties()


"""
responses
"""


bid_responses = {
    403: Errors.mission_state_not_allowed.as_p(),
    404: Errors.not_found.as_p(),
}


interaction_responses = {
    403: Errors.mission_state_not_allowed.as_p() + \
         Errors.permission_denied.as_p(),
    404: Errors.not_found.as_p(),
    406: Errors.interaction_before_not_ended.as_p(),
}


state_code_description = '[state]\n' + '\n'.join(['%s %s' % (state, display) for state, display in MISSION_STATUS])


# state_param = openapi.Parameter('state', openapi.IN_QUERY, description="state로 필터링",
#                                 type=openapi.TYPE_ARRAY, items=openapi.SwaggerDict(type=openapi.TYPE_STRING))


"""
base viewsets and mixins
"""


class ViewListMixin:

    def view_list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return response.Response(serializer.data)


class MissionBaseViewSet(BaseModelViewSet):
    """
    미션에 의존하는 viewset base
    """
    mission = None
    area_mission = None
    _mission = None

    def dispatch(self, request, *args, **kwargs):
        mission_id = self.kwargs.get('mission_id')
        multi_area_mission_id = self.kwargs.get('multi_area_mission_id')
        if mission_id:
            try:
                self.mission = Mission.objects.get(id=mission_id)
                self._mission = self.mission
            except:
                pass
        if multi_area_mission_id:
            try:
                self.area_mission = MultiAreaMission.objects.get(id=multi_area_mission_id)
                self._mission = self.area_mission
            except:
                pass
        return super(MissionBaseViewSet, self).dispatch(request, *args, **kwargs)

    def mission_owner_only(self):
        if not self._mission:
            raise Errors.not_found
        if self.request.user != self._mission.user:
            raise Errors.permission_denied


class BidBaseViewSet(BaseModelViewSet):
    """
    미션 입찰에 의존하는 viewset base
    """
    bid = None

    def dispatch(self, request, *args, **kwargs):
        try:
            self.bid = Bid.objects.get(id=self.kwargs.get('bid_id'))
        except:
            pass
        return super(BidBaseViewSet, self).dispatch(request, *args, **kwargs)

    def check_bid(self):
        if not self.bid:
            raise Errors.not_found
        if self.request.user not in (self.bid._mission.user, self.bid.helper.user):
            raise Errors.permission_denied


class ProfileBaseViewSet(BaseModelViewSet):
    """
    사용자 프로필에 의존하는 viewset base
    """
    user = None

    def dispatch(self, request, *args, **kwargs):
        try:
            self.user = get_user_model().objects.get(code=self.kwargs.get('code'))
        except:
            pass
        return super(ProfileBaseViewSet, self).dispatch(request, *args, **kwargs)

    def check_user(self):
        if not self.user:
            raise Errors.not_found


"""
미션 기본 viewsets
"""


class MissionTypeViewSet(mixins.ListModelMixin,
                      BaseModelViewSet):
    """
    미션타입 API endpoint
    """
    model = MissionType
    serializer_class = MissionTypeSerializer
    pagination_class = None
    permission_classes = (permissions.AllowAny,)


class AddressViewSet(mixins.CreateModelMixin,
                     mixins.ListModelMixin,
                     mixins.DestroyModelMixin,
                     BaseModelViewSet):
    """
    미션용 주소 API endpoint
    """
    model = Address
    serializer_class = AddressSerializer
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        qs = super(AddressViewSet, self).get_queryset().filter(user=self.request.user)
        if self.action == 'recent':
            self.pagination_class = None
            return qs.filter(name='').order_by('-id')[:3]
        return qs.exclude(name='')

    @action(detail=False, methods=['get'])
    def recent(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class GetByCodeViewSet(mixins.RetrieveModelMixin,
                       BaseModelViewSet):
    """
    미션코드로 미션 조회 API
    """
    model = Mission
    lookup_field = 'code'
    lookup_url_kwarg = 'code'

    def retrieve(self, request, *args, **kwargs):
        code = kwargs.get('code').upper()
        obj = self.get_queryset().filter(code=code).last()
        if obj:
            serializer_class = MissionReadOnlySerializer
        else:
            obj = MultiMission.objects.filter(code=code, requested_datetime__isnull=False).last()
            if not obj:
                raise Errors.not_found
            serializer_class = MultiMissionSerializer
        return response.Response(data=serializer_class(instance=obj).data)


class MultiMissionViewSet(mixins.ListModelMixin,
                          mixins.RetrieveModelMixin,
                          BaseModelViewSet):
    """
    다중 미션 API endpoint
    """
    model = MultiMission
    serializer_class = MultiMissionSerializer

    def get_queryset(self):
        qs = super(MultiMissionViewSet, self).get_queryset()
        if self.action == 'list':
            qs = qs.available(self.request.user)
        if self.action == 'in_action':
            qs = qs.filter(user=self.request.user, requested_datetime__isnull=False)
        return qs.distinct('id').order_by('-id')

    def get_permissions(self):
        if self.action == 'in_action':
            self.permission_classes = (permissions.IsAdminUser,)
        return super(MultiMissionViewSet, self).get_permissions()

    @swagger_auto_schema(operation_description='수행중인 내 담당 미션 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def in_action(self, request, *args, **kwargs):
        """수행중인 내 담당 미션 목록"""
        return self.list(request, *args, **kwargs)


class MissionViewSet(mixins.CreateModelMixin,
                     mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin,
                     BaseModelViewSet):
    """
    미션 API endpoint
    """
    model = Mission
    serializer_class = MissionSerializer
    permission_classes = (permissions.IsValidUser,)
    lookup_url_kwarg = 'mission_id'
    area_ids = []

    def get_permissions(self):
        if self.action in ('all', 'acceptable_check'):
            self.permission_classes = (permissions.AllowAny,)
        return super(MissionViewSet, self).get_permissions()

    def get_queryset(self):
        qs = super(MissionViewSet, self).get_queryset()
        if self.action in ('all', 'available'):
            qs = qs.all_view_only()
        if self.action == 'available' and self.request.user.is_helper:
            # 헬퍼로 승인된 사람일 때만 필터링
            # 헬퍼가 아닌 경우 전체 입찰중인 미션 뿌려줌
            qs = qs.available(self.request.user, self.area_ids)
        elif self.action == 'list':
            qs = qs.filter(user=self.request.user, requested_datetime__isnull=False)
        elif self.action == 'assigned':
            qs = qs.assigned(self.request.user)
        elif self.action == 'canceled':
            qs = qs.filter(user_id=self.request.user.id).canceled().distinct('id')
        elif self.action == 'done':
            qs = qs.filter(user_id=self.request.user.id).done().distinct('id')
        elif self.action == 'recent':
            self.pagination_class = None
            qs = qs.filter(user_id=self.request.user.id).recent(days=30)
        elif self.action == 'active':
            self.pagination_class = None
            qs = qs.active(user_id=self.request.user.id)
        elif self.action == 'in_bidding':
            qs = qs.in_bidding(user_id=self.request.user.id)
        elif self.action == 'in_action':
            qs = qs.filter(user_id=self.request.user.id).in_action()
        elif self.action == 'update':
            qs = qs.filter(user_id=self.request.user.id, requested_datetime__isnull=True)
        elif self.action == 'destroy':
            qs = qs.filter(user_id=self.request.user.id, canceled_datetime__isnull=True)
        return qs.order_by('-id')

    def get_serializer_class(self):
        if self.action in ('all', 'available', 'assigned'):
            return MissionAvailableSerializer
        if self.action not in ('create', 'update', 'partial_update', 'destroy'):
            return MissionReadOnlySerializer
        return super(MissionViewSet, self).get_serializer_class()

    @action(methods=['post'], detail=False)
    def acceptable_check(self, request, *args, **kwargs):
        if 'content' in request.data and request.data['content']:
            banned = BannedWord.objects.check_words(request.data['content'])
            return response.Response({'content': banned or ''})
        else:
            return response.Response({})

    @swagger_auto_schema(
        responses={
            400: Errors.invalid_content().as_p(),
        }
    )
    def create(self, request, *args, **kwargs):
        # 입찰중 미션이 있는 경우에는 미션을 새로 요청할 수 없음
        if self.model.objects.check_user_bidding(request.user.id):
            raise Errors.bidding_mission_exist

        created = super(MissionViewSet, self).create(request, *args, **kwargs)
        obj = self.model.objects.get(id=created.data['id'])
        logger.info('[mission %s created] POST data : %s' % (obj.code, request.data))
        if obj.request():
            logger.info('[mission %s requested]' % obj.code)
            try:
                result = obj.push_result.check_requested_count()
            except:
                result = 0
        else:
            logger.info('[mission %s request failed]' % obj.code)
            result = 0
        return response.Response({
            'id': obj.id,
            'result': result,
            'bidding_limit': obj.mission_type.bidding_limit
        })

    @swagger_auto_boolean_schema(
        responses={
            400: Errors.invalid_due_datetime.as_p(),
            403: Errors.mission_state_not_allowed.as_p(),
        },
        request_body=no_body
    )
    def update(self, request, *args, **kwargs):
        """작성된 미션 request"""
        obj = self.get_object()
        if obj.requested_datetime:
            raise Errors.mission_state_not_allowed
        if obj.due_datetime and obj.due_datetime < timezone.now():
            raise Errors.invalid_due_datetime
        if obj.request():
            try:
                result = obj.push_result.check_requested_count()
            except:
                result = 0
        else:
            result = 0
        return response.Response({'result': result})

    @swagger_auto_boolean_schema(
        responses={
            403: Errors.mission_state_not_allowed.as_p(),
            404: Errors.not_found.as_p(),
        },
    )
    def destroy(self, request, *args, **kwargs):
        """미션 취소"""
        # detail = request.data['canceled_detail'] if 'canceled_detail' in request.data else ''
        detail = request.GET.get('canceled_detail', '')
        obj = self.get_object()
        result = obj.cancel(detail)

        if result:
            if obj.bids.exists():
                for assigned in obj.bids.filter(is_assigned=True):
                    # Notification.objects.push_preset(assigned.helper.user, 'assigned_mission_canceled', [obj.user.username])
                    Tasker.objects.task('assigned_mission_canceled', user=assigned.helper.user,
                                        kwargs={'sender': obj.user.username})
                for bidded in obj.bids.filter(is_assigned=False):
                    # Notification.objects.push_preset(bidded.helper.user, 'bidded_mission_canceled', [obj.content_short])
                    Tasker.objects.task('bidded_mission_canceled', user=bidded.helper.user,
                                        kwargs={'mission': obj.content_short})

            log_with_reason(request.user, obj, 'changed', '"%s" 미션 취소' % obj.content_short)

        return response.Response({'result': result})

    @swagger_auto_schema(operation_description='내 미션 목록\n\n---\n%s' % state_code_description)
    def list(self, request, *args, **kwargs):
        """내 미션 목록"""
        return super(MissionViewSet, self).list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description='전체 미션 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def all(self, request, *args, **kwargs):
        """전체 미션 목록"""
        return self.list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description='고객 홈 미션 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def active(self, request, *args, **kwargs):
        """고객 홈 미션 목록"""
        return self.list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description='입찰 가능한 미션 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def available(self, request, *args, **kwargs):
        """입찰 가능한 미션 목록"""
        if request.user.helper:
            self.area_ids = request.user.helper.accept_area_ids
        available_view = self.list(request, *args, **kwargs)
        multi = MultiMission.objects.available(request.user, self.area_ids).distinct('id')
        assigned = Mission.objects.assigned(request.user)
        new_count = Notification.objects.get_by_usercode(request.user.code, exclude_read=True).count()
        return response.Response({
            'assigned': {'data': MissionAvailableSerializer(assigned, many=True).data},
            'multi': {'data': MultiMissionSerializer(multi, many=True, context={'request': request}).data},
            'available': available_view.data,
            'new_count': new_count
        })

    @swagger_auto_schema(operation_description='지정 미션 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def assigned(self, request, *args, **kwargs):
        """지정 미션 목록"""
        return self.list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description='취소된 내 미션 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def canceled(self, request, *args, **kwargs):
        """취소된 내 미션 목록"""
        return self.list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description='내 최근 미션 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def recent(self, request, *args, **kwargs):
        """내 최근 미션 목록"""
        return self.list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description='완료된 내 미션 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def done(self, request, *args, **kwargs):
        """완료된 내 미션 목록"""
        return self.list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description='입찰중인 내 미션 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def in_bidding(self, request, *args, **kwargs):
        """입찰중인 내 미션 목록"""
        return super(MissionViewSet, self).list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description='수행중인 내 미션 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def in_action(self, request, *args, **kwargs):
        """수행중인 내 미션 목록"""
        return super(MissionViewSet, self).list(request, *args, **kwargs)


class MissionFileViewSet(mixins.CreateModelMixin,
                         mixins.ListModelMixin,
                         mixins.DestroyModelMixin,
                         MissionBaseViewSet):
    """
    미션 수행 관련 파일 API endpoint
    """
    model = MissionFile
    serializer_class = MissionFileSerializer
    parser_classes = (parsers.MultiPartParser,)

    def get_queryset(self):
        qs = super(MissionFileViewSet, self).get_queryset().filter(mission=self.mission)
        if self.action == 'destroy':
            qs = qs.filter(mission__user=self.request.user)
        return qs

    @swagger_auto_schema(responses={400: Errors.fields_invalid.as_p()})
    def create(self, request, *args, **kwargs):
        self.mission_owner_only()
        if 'attach' not in request.data:
            raise Errors.fields_invalid
        file_obj = request.data['attach']
        obj = self.model.objects.create(mission=self.mission)
        filename = obj.handle_attach(file_obj)
        url = request.build_absolute_uri(settings.MEDIA_URL + filename)
        return response.Response({'attach': url})

    def destroy(self, request, *args, **kwargs):
        super(MissionFileViewSet, self).destroy(request, *args, **kwargs)
        return response.Response({'result': True})


"""
입찰 및 수행 관련 viewsets
"""


class BidViewSet(mixins.CreateModelMixin,
                 mixins.ListModelMixin,
                 MissionBaseViewSet):
    """
    미션 입찰 API endpoint
    """
    model = Bid
    serializer_class = BidSerializer
    permission_classes = (permissions.IsValidUser,)

    def _clean_data(self, data):
        # todo: 글로벌 설정으로 변경해도 문제 없는지 확인 후 이동할 것
        if type(data) is bytes:
            data = data.decode("utf-8", errors="replace").replace("\x00", "\uFFFD")
        return data

    def check_mission(self):
        if not self._mission:
            raise Errors.not_found
        if self._mission.get_state_code() not in ('bidding', 'waiting_assignee'):
            self._mission.set_state()
            raise Errors.mission_state_not_allowed

    def get_queryset(self):
        qs = super(BidViewSet, self).get_queryset().filter(mission=self.mission)
        qs = qs.filter(_canceled_datetime__isnull=True).order_by('applied_datetime')
        if self.action == 'list':
            for bid in qs.filter(customer_checked_datetime__isnull=True):
                bid.customer_checked_datetime = timezone.now()
                bid.save()
        return qs

    def get_permissions(self):
        if self.action == 'create':
            self.permission_classes = (permissions.IsHelper,)
        return super(BidViewSet, self).get_permissions()

    @swagger_auto_schema(
        responses={
            400: Errors.invalid_amount.as_p(),
            403: Errors.mission_state_not_allowed.as_p(),
            404: Errors.not_found.as_p(),
        },
        operation_description='미션 입찰\n\n---\n%s' % state_code_description
    )
    def create(self, request, *args, **kwargs):
        """미션 입찰"""
        self.check_mission()
        if self.request.user == self._mission.user:
            raise Errors.permission_denied

        self.request.data.update({
            'helper_id': self.request.user.helper.id,
            '_canceled_datetime': None,
        })

        if self.mission:
            if int(request.data['amount']) < 1000 \
                    or (self.mission.amount_low and self.mission.amount_low > request.data['amount']) \
                    or (self.mission.amount_high and request.data['amount'] > self.mission.amount_high):
                raise Errors.invalid_amount
            if self.mission.is_timeout:
                raise Errors.mission_state_not_allowed
            self.request.data.update({'mission_id': self.mission.id})

            # 지정미션에 입찰인 경우 update, 아니면 create 처리
            assigned = self.model.objects.filter(
                    mission_id=self.mission.id,
                    helper_id=self.request.user.helper.id,
            )
            is_created = None
            if assigned.exists() and assigned.update(**request.data):
                obj = assigned.last()
            else:
                obj, is_created = self.model.objects.get_or_create(**request.data)
            obj.applied_datetime = timezone.now()
            obj.set_state()
            if is_created is False:
                raise Errors.bid_already_exist

        elif self.area_mission:
            self.request.data.update({
                'area_mission_id': self.area_mission.id,
                'amount': self.area_mission.amount,
            })
            obj = self.model.objects.create(**request.data)
            obj.win_single()  # 입찰 후 바로 낙찰 처리

        else:
            raise Errors.not_usable

        # 알림
        if obj.is_external:
            # Notification.objects.sms_preset(self._mission.user, 'external_bidded',
            #                                 args=[self._mission.bidded_count, self._mission.shortened_url])
            Tasker.objects.task('web_bidded', user=self._mission.user, kwargs={
                'count': self._mission.bidded_count,
                'url': self._mission.shortened_url
            })
        else:
            if obj.is_assigned:
                # Notification.objects.push_preset(self._mission.user, 'assigned_mission_bidded',
                #                                  args=[obj.helper.user.username],
                #                                  kwargs={'obj_id': self._mission.id})
                Tasker.objects.task('assigned_mission_bidded', user=self._mission.user,
                                    kwargs={'sender': obj.helper.user.username}, data={'obj_id': self._mission.id})
            else:
                # Notification.objects.push_preset(self._mission.user, 'mission_bidded',
                #                                  args=[self._mission.bidded_count],
                #                                  kwargs={'obj_id': self._mission.id})
                Tasker.objects.task('mission_bidded', user=self._mission.user,
                                    kwargs={'count': self._mission.bidded_count}, data={'obj_id': self._mission.id})

        # 좌표 있는 경우 행정동 검색 추가
        if obj.longitude and obj.latitude:
            headers = {
                'Authorization': 'KakaoAK %s' % settings.KAKAO_REST_API_KEY,
                'content-type': 'application/json',
            }
            params = {
                'x': str(obj.longitude),
                'y': str(obj.latitude)
            }
            res = requests.get(settings.KAKAO_LOCATION_URL, headers=headers, params=params)
            if res.status_code == 200:
                try:
                    result = res.json()
                    obj.location = result['documents'][0]['address_name']
                    obj.save()
                except:
                    pass

        log_with_reason(request.user, obj, 'added', '"%s" 미션 %s원으로 입찰' % (self._mission.content_short, obj.amount))
        return response.Response(data=self.serializer_class(instance=obj).data)

    @swagger_auto_schema(
        operation_description='입찰 목록\n\n---\n%s' % state_code_description
    )
    def list(self, request, *args, **kwargs):
        """입찰 목록"""
        self.mission_owner_only()
        return super(BidViewSet, self).list(request, *args, **kwargs)


class UserBidsViewSet(mixins.ListModelMixin,
                      mixins.RetrieveModelMixin,
                      mixins.DestroyModelMixin,
                      mixins.UpdateModelMixin,
                      BaseModelViewSet):
    """
    사용자 입찰 목록
    """
    model = Bid
    serializer_class = UserBidSerializer
    permission_classes = (permissions.IsValidUser,)
    http_method_names = ['get', 'post', 'put', 'delete']
    lookup_url_kwarg = 'bid_id'

    def get_queryset(self):
        qs = super(UserBidsViewSet, self).get_queryset()
        if self.action == 'update':
            qs = qs.filter(
                Q(mission__user_id=self.request.user.id)
                | Q(area_mission__parent__user_id=self.request.user.id)
            )
        elif self.action == 'retrieve':
            qs = qs.filter(
                Q(mission__user_id=self.request.user.id)
                | Q(helper__user_id=self.request.user.id)
            )
        elif self.action == 'lock':
            qs = qs.filter(mission__user_id=self.request.user.id)
        else:
            qs = qs.filter(helper__user_id=self.request.user.id)
            if self.action == 'in_bidding':
                qs = qs.in_bidding()
            elif self.action == 'canceled':
                qs = qs.canceled(days=2)
            elif self.action == 'in_action':
                qs = qs.in_action()
            elif self.action == 'done':
                qs = qs.done(days=2)
        return qs.order_by('-id')

    def get_permissions(self):
        if action == 'destroy':
            self.permission_classes = (permissions.IsHelper,)
        return super(UserBidsViewSet, self).get_permissions()

    @swagger_auto_schema(operation_description='취소된 내 입찰 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def canceled(self, request, *args, **kwargs):
        """취소된 내 입찰 목록"""
        return super(UserBidsViewSet, self).list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description='입찰중인 내 입찰 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def in_bidding(self, request, *args, **kwargs):
        """입찰중인 내 입찰 목록"""
        return super(UserBidsViewSet, self).list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description='수행중인 내 입찰 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def in_action(self, request, *args, **kwargs):
        """수행중인 내 입찰 목록"""
        return super(UserBidsViewSet, self).list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description='수행완료한 내 입찰 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def done(self, request, *args, **kwargs):
        """수행완료한 내 입찰 목록"""
        return super(UserBidsViewSet, self).list(request, *args, **kwargs)

    @swagger_auto_schema(responses=bid_responses)
    def retrieve(self, request, *args, **kwargs):
        """입찰 상세"""
        return super(UserBidsViewSet, self).retrieve(request, *args, **kwargs)

    @swagger_auto_schema(responses=bid_responses)
    def destroy(self, request, *args, **kwargs):
        """입찰 취소"""
        obj = self.get_object()
        if obj.is_locked:
            raise Errors.bid_locked
        result = obj.cancel_bidding()
        if result:
            log_with_reason(request.user, obj, 'changed', '"%s" 미션 입찰 취소' % obj._mission.content_short)
        return response.Response({'result': result})

    @swagger_auto_boolean_schema(responses=bid_responses, request_body=no_body)
    def update(self, request, *args, **kwargs):
        """해당 입찰을 낙찰 처리 (deprecated)"""
        # obj = self.get_object()
        # if obj.state != 'applied':
        #     raise Errors.bid_state_not_applied
        # if not obj.mission.is_timeout and obj.win_single():
        #     Notification.objects.push_preset(obj.helper.user, 'bidded_mission_matched',
        #                                      args=[obj.mission.content_short], kwargs={'obj_id': obj.mission.active_bid.id})
        #     for bid in obj.mission.bids.exclude(id=obj.id):
        #         Notification.objects.push_preset(bid.helper.user, 'bidded_mission_failed',
        #                                          args=[obj.mission.content_short])
        #         log_with_reason(bid.helper.user, bid, 'changed', '"%s" 미션 패찰' % obj.mission.content_short)
        #     log_with_reason(request.user, obj, 'changed', '"%s" 미션에 %s 낙찰' % (obj.mission.content_short, str(obj.helper)))
        return response.Response({'result': None})

    @action(detail=True, methods=['post'])
    def lock(self, request, *args, **kwargs):
        obj = self.get_object()
        result = obj.lock()
        if result:
            logger.info('[Payment] [bid id %s (%s)] locked' % (obj.id, obj._mission.code))
        else:
            logger.info('[Payment] [bid id %s (%s)] lock failed' % (obj.id, obj._mission.code))
        return response.Response({'result': result})


class HelperTemporaryBidsViewSet(mixins.ListModelMixin,
                      BaseModelViewSet):
    """
    사용자 입찰 목록
    """
    model = Bid
    serializer_class = UserBidTemporarySerializer
    permission_classes = (permissions.IsHelper,)
    http_method_names = ['get']
    lookup_url_kwarg = 'bid_id'
    authentication_classes = [authentication.HelperTemporaryAuthentication]

    def get_queryset(self):
        qs = super(HelperTemporaryBidsViewSet, self).get_queryset()
        qs = qs.filter(helper__user_id=self.request.user.id)
        qs = qs.done()
        return qs.order_by('-id')


    @swagger_auto_schema(operation_description='수행완료한 내 입찰 목록\n\n---\n%s' % state_code_description)
    @action(detail=False, methods=['get'])
    def done(self, request, *args, **kwargs):
        """수행완료한 내 입찰 목록"""
        return super(HelperTemporaryBidsViewSet, self).list(request, *args, **kwargs)

class AnytalkBidsViewSet(mixins.ListModelMixin,
                         BaseModelViewSet):
    """
    애니톡용 입찰 목록
    """
    model = Bid
    permission_classes = (permissions.IsValidUser,)
    pagination_class = None
    serializer_class = AnytalkBidSerializer
    http_method_names = ('get', 'post')

    def get_queryset(self):
        qs = super(AnytalkBidsViewSet, self).get_queryset()
        if self.action == 'warning':
            qs = qs.filter(_anytalk_closed_datetime__isnull=True)
        else:
            qs = qs.in_action() | qs.done(days=1)
            qs = qs.filter(
                mission__login_code='',
                _anytalk_closed_datetime__isnull=True
            ).filter(
                Q(mission__user_id=self.request.user.id)
                | Q(area_mission__parent__user_id=self.request.user.id)
                | Q(helper__user_id=self.request.user.id)
            )
        return qs

    @action(detail=False, methods=['get'])
    def ids(self, request, *args, **kwargs):
        return response.Response({'data': self.get_queryset().values_list('id', flat=True)})

    @action(detail=True, methods=['post'])
    def warning(self, request, *args, **kwargs):
        obj = self.get_object()
        anyman.slack.channel('anyman__17-1').script_msg(
            '개인거래 유도 의심',
            '%s 미션 수행중 애니톡에서 휴대폰 번호 공유가 검출되었습니다.\nhttps://%s/admin/missions/bid/%s/change/' % (
                obj.mission.code, settings.MAIN_HOST, obj.id
            )
        )
        return response.Response({})


class BidFileViewSet(mixins.CreateModelMixin,
                     mixins.ListModelMixin,
                     mixins.DestroyModelMixin,
                     BidBaseViewSet):
    """
    미션 수행중 애니톡 교환 파일 API endpoint
    """
    model = BidFile
    serializer_class = BidFileSerializer
    parser_classes = (parsers.MultiPartParser,)
    pagination_class = None

    def get_queryset(self):
        qs = super(BidFileViewSet, self).get_queryset().filter(bid=self.bid)
        if self.action == 'destroy':
            qs = qs.filter(created_user=self.request.user)
        return qs

    @swagger_auto_schema(responses={400: Errors.fields_invalid.as_p()})
    def create(self, request, *args, **kwargs):
        file_obj = request.data['attach']
        obj = self.model.objects.create(bid=self.bid, created_user=request.user)
        filename = obj.handle_attach(file_obj)
        url = request.build_absolute_uri(settings.MEDIA_URL + filename)
        return response.Response({'attach': url})

    def destroy(self, request, *args, **kwargs):
        super(BidFileViewSet, self).destroy(request, *args, **kwargs)
        return response.Response({'result': True})


class InteractionViewSet(mixins.CreateModelMixin,
                         mixins.ListModelMixin,
                         mixins.DestroyModelMixin,
                         mixins.UpdateModelMixin,
                         BidBaseViewSet):
    """
    미션 수행 인터랙션 API endpoint
    """
    model = Interaction
    serializer_class = InteractionSerializer
    pagination_class = None
    http_method_names = ['get', 'post', 'put', 'delete']

    def check_state(self):
        if self.get_object().state != 'requested':
            raise Errors.mission_state_not_allowed

    def get_queryset(self):
        return super(InteractionViewSet, self).get_queryset().filter(bid=self.bid)

    @swagger_auto_boolean_schema(responses=interaction_responses)
    def create(self, request, *args, **kwargs):
        """미션 수행 인터랙션 요청"""
        self.check_bid()
        if self.model.objects.filter(bid_id=self.bid.id, accepted_datetime__isnull=True, rejected_datetime__isnull=True,
                                     canceled_datetime__isnull=True).exists():
            raise Errors.interaction_before_not_ended
        if self.bid._done_datetime:
            raise Errors.mission_already_done
        self.request.data.update({'bid_id': self.bid.id, 'created_user_id': self.request.user.id})
        obj = self.model.objects.create(**request.data)
        self._send_notification('create', obj.receiver, obj)
        return response.Response(data=self.serializer_class(instance=obj).data)

    @swagger_auto_boolean_schema(responses=interaction_responses)
    def list(self, request, *args, **kwargs):
        """미션 수행 인터랙션 목록"""
        self.check_bid()
        return super(InteractionViewSet, self).list(request, *args, **kwargs)

    @swagger_auto_boolean_schema(responses=interaction_responses)
    def destroy(self, request, *args, **kwargs):
        """미션 수행 인터랙션 취소/거절"""
        self.check_bid()
        self.check_state()
        obj = self.get_object()
        if request.user == obj.created_user:
            result = obj.cancel()
            self._send_notification('cancel', obj.receiver, obj)
        elif request.user == obj.receiver:
            result = obj.reject()
            self._send_notification('destroy', obj.created_user, obj)
        else:
            raise Errors.permission_denied
        return response.Response({'result': result})

    @swagger_auto_boolean_schema(responses=interaction_responses, request_body=no_body)
    def update(self, request, *args, **kwargs):
        """미션 수행 인터랙션 수락"""
        self.check_bid()
        self.check_state()
        obj = self.get_object()
        if request.user != obj.receiver:
            raise Errors.permission_denied
        result = obj.accept()
        if result:
            self._send_notification('update', obj.created_user, obj)
            log_with_reason(obj.created_user, obj.bid, 'changed', obj.get_interaction_type_display() + ' 확정')
        return response.Response({'result': result})

    def _send_notification(self, action, receiver, obj):
        presets = {
            'create': {
                1: 'cancel_interaction_requested',
                5: 'due_interaction_requested',
                9: 'done_interaction_requested',
            },
            'cancel': {
                1: 'cancel_interaction_canceled',
                5: 'due_interaction_canceled',
                9: 'done_interaction_canceled',
            },
            'destroy': {
                1: 'cancel_interaction_rejected',
                5: 'due_interaction_rejected',
                9: 'done_interaction_rejected',
            },
            'update': {
                1: 'cancel_interaction_accepted',
                5: 'due_interaction_accepted',
                9: 'done_interaction_accepted',
            }
        }
        if obj.is_created_user_helper:
            if action in ('create', 'cancel'):
                suffix = '_by_helper'
            else:
                suffix = '_by_customer'
        else:
            if action in ('create', 'cancel'):
                suffix = '_by_customer'
            else:
                suffix = '_by_helper'

        push_object_id = obj.bid.id if suffix == '_by_customer' else obj.bid._mission.id

        try:
            preset = presets[action][obj.interaction_type] + suffix
        except:
            return None

        if obj.bid.is_external and not receiver.push_tokens:
            # Notification.objects.sms_preset(receiver, preset, args=[obj.bid._mission.shortened_url])
            Tasker.objects.task('web_' + preset, user=receiver, kwargs={'url': obj.bid._mission.shortened_url})
        else:
            # Notification.objects.push_preset(receiver, preset, args=[obj.bid._mission.content_short],
            #                                  kwargs={'obj_id': push_object_id})
            Tasker.objects.task(preset, user=receiver, data={'obj_id': push_object_id}, kwargs={
                'mission': obj.bid._mission.content_short,
                'sender': obj.created_user.username,
            })


"""
미션 수행 이후의 viewsets
"""


class ReportViewSet(mixins.CreateModelMixin,
                    BidBaseViewSet):
    """
    신고 API endpoint
    """
    model = Report
    serializer_class = ReportSerializer

    def check_if_exist(self):
        """한 미션 수행에 고객/헬퍼 각각 하나씩만 남길 수 있음"""
        if self.model.objects.filter(bid=self.bid, created_user=self.request.user).exists():
            raise Errors.allowed_only_one_record

    @swagger_auto_boolean_schema(
        responses={
            403: Errors.mission_state_not_allowed.as_p(),
            404: Errors.not_found.as_p(),
            406: Errors.allowed_only_one_record.as_p(),
        },
        request_body=ReportRequestBody,
    )
    def create(self, request, *args, **kwargs):
        """작성"""
        if self.bid:
            self.check_bid()
            self.check_if_exist()
            self.request.data.update({'bid_id': self.bid.id, 'created_user_id': self.request.user.id})
        else:
            try:
                self.mission = Mission.objects.get(id=self.kwargs.get('mission_id'))
            except:
                raise Errors.not_found
            self.request.data.update({'mission_id': self.mission.id, 'created_user_id': self.request.user.id})
        obj = self.model.objects.create(**request.data)
        return response.Response(data={'result': True})


class ProfileReportViewSet(ViewListMixin,
                           ProfileBaseViewSet):
    """
    신고 API endpoint
    """
    model = Report
    serializer_class = ReportSerializer

    def get_queryset(self):
        qs = super(ProfileReportViewSet, self).get_queryset()
        if self.action == 'created':
            qs = qs.filter(created_user=self.user)
        if self.action == 'received':
            qs = qs.filter(bid__helper__user=self.user)
        return qs

    @action(detail=False, methods=['get'])
    def created(self, request, *args, **kwargs):
        self.check_user()
        return self.view_list(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def received(self, request, *args, **kwargs):
        self.check_user()
        return self.view_list(request, *args, **kwargs)


class ReviewViewSet(mixins.UpdateModelMixin,
                    mixins.DestroyModelMixin,
                    ReportViewSet):
    """
    미션 수행 리뷰 API endpoint
    """
    model = Review
    serializer_class = ReviewSerializer
    http_method_names = ('get', 'post', 'patch', 'delete')

    def get_queryset(self):
        qs = super(ReviewViewSet, self).get_queryset()
        return qs.filter(is_active=True)

    def check_if_exist(self):
        if self.bid.reviews.filter(created_user=self.request.user, is_active=True).exists():
            raise Errors.allowed_only_one_record

        """수행 완료된 경우에만 남길 수 있음 (1월 10일 이지언 확인)"""
        if not self.bid.done_datetime:
            raise Errors.mission_state_not_allowed

    def get_if_editable(self):
        obj = self.get_object()
        if obj.created_datetime + timezone.timedelta(days=2) < timezone.now():
            raise Errors.timeout
        if self.request.user.id != obj.created_user_id:
            raise Errors.permission_denied
        return obj

    @swagger_auto_boolean_schema(
        responses={
            403: Errors.mission_state_not_allowed.as_p(),
            406: Errors.allowed_only_one_record.as_p(),
        },
        request_body=ReviewRequestBody,
    )
    def create(self, request, *args, **kwargs):
        return super(ReviewViewSet, self).create(request, *args, **kwargs)

    @swagger_auto_boolean_schema(
        responses={
            404: Errors.not_found.as_p(),
            406: Errors.timeout.as_p(),
        },
        request_body=ReviewRequestBody,
    )
    def partial_update(self, request, *args, **kwargs):
        self.get_if_editable()
        return super(ReviewViewSet, self).partial_update(request, *args, **kwargs)

    @swagger_auto_boolean_schema(
        responses={
            403: Errors.permission_denied.as_p(),
            404: Errors.not_found.as_p(),
        },
    )
    def destroy(self, request, *args, **kwargs):
        obj = self.get_if_editable()
        obj.is_active = False
        obj.save()
        return response.Response(data={'result': True})


class CustomerReviewViewSet(ProfileReportViewSet):
    """
    고객 리뷰 API endpoint
    """
    model = Review
    serializer_class = ReviewSerializer

    def get_queryset(self):
        qs = self.model.objects.filter(is_active=True)
        if self.action == 'created':
            qs = qs.filter(bid__mission__user_id=self.user.id, created_user_id=self.user.id)
        if self.action == 'received':
            qs = qs.filter(bid__mission__user_id=self.user.id).exclude(created_user_id=self.user.id)
        return qs.order_by('-created_datetime')

    def finalize_response(self, request, response, *args, **kwargs):
        res = super(CustomerReviewViewSet, self).finalize_response(request, response, *args, **kwargs)
        if res.status_code < 300 and res.data is not None and self.action == 'received':
            res.data['mean'] = self.model.objects.get_customer_received(self.user).mean()
        return res


class HelperReviewViewSet(CustomerReviewViewSet):
    """
    헬퍼 리뷰 API endpoint
    """

    def get_queryset(self):
        qs = self.model.objects.filter(is_active=True)
        if self.action == 'created':
            qs = qs.filter(bid__helper__user_id=self.user.id, created_user_id=self.user.id)
        if self.action == 'received':
            qs = self.model.objects.get_helper_received(self.user)
        return qs.order_by('-created_datetime')

    def finalize_response(self, request, response, *args, **kwargs):
        res = super(CustomerReviewViewSet, self).finalize_response(request, response, *args, **kwargs)
        if res.status_code < 300 and res.data is not None and self.action == 'received':
            res.data['mean'] = self.model.objects.get_helper_received(self.user).mean()
        return res


class UserBlockViewSet(mixins.CreateModelMixin,
                       mixins.ListModelMixin,
                       mixins.DestroyModelMixin,
                       BaseModelViewSet):
    """
    사용자 차단 API endpoint
    """
    model = UserBlock
    serializer_class = UserBlockSerializer
    lookup_url_kwarg = 'code'
    lookup_field = 'user__code'

    def get_queryset(self):
        qs = super(UserBlockViewSet, self).get_queryset()
        return qs.filter(created_user_id=self.request.user.id)

    @swagger_auto_boolean_schema(
        responses={
            404: Errors.not_found.as_p(),
        },
        request_body=UserBlockRequestBody,
    )
    def create(self, request, *args, **kwargs):
        """사용자 차단 추가"""
        user = get_user_model().objects.filter(code=self.request.data['code']).last()
        if not user:
            raise Errors.not_found
        request.data.update({'user_id': user.id, 'created_user_id': self.request.user.id})
        query = {'user': user, 'created_user_id': self.request.user.id}
        obj, is_created = self.model.objects.get_or_create(**query)
        if 'related_mission' in request.data and request.data['related_mission']:
            # todo: 실제로 연관된 미션인지 검사할 것.
            obj.related_mission_id = request.data['related_mission']
            obj.save()
        return response.Response(data={'result': is_created})


class FavoriteUserViewSet(mixins.CreateModelMixin,
                          mixins.ListModelMixin,
                          mixins.DestroyModelMixin,
                          BaseModelViewSet):
    """
    사용자 찜 API endpoint
    """
    model = FavoriteUser
    serializer_class = FavoriteUserSerializer
    lookup_url_kwarg = 'code'
    lookup_field = 'user__code'
    pagination_class = None

    def get_queryset(self):
        qs = super(FavoriteUserViewSet, self).get_queryset()
        return qs.filter(created_user_id=self.request.user.id)

    @swagger_auto_boolean_schema(
        responses={
            404: Errors.not_found.as_p(),
        },
        request_body=FavoriteUserRequestBody,
    )
    def create(self, request, *args, **kwargs):
        """사용자 찜 추가"""
        user = get_user_model().objects.filter(code=self.request.data['code']).last()
        if not user:
            raise Errors.not_found
        query = {'user': user, 'created_user_id': self.request.user.id}
        obj, is_created = self.model.objects.get_or_create(**query)
        return response.Response(data={'result': is_created})


class RelaySafetyNumberViewSet(mixins.RetrieveModelMixin,
                               mixins.DestroyModelMixin,
                               BaseModelViewSet):
    """
    안심번호 릴레이 처리 API endpoint
    """
    model = Bid
    serializer_class = BidSerializer
    pagination_class = None
    permission_classes = (permissions.AllowAny,)

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        SafetyNumber.objects.assign_pair_from_bid(obj)
        return response.Response({'result': True})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        SafetyNumber.objects.unassign_pair_from_bid(obj)
        return response.Response({'result': True})


class TemplateCategoryViewSet(mixins.ListModelMixin,
                              mixins.RetrieveModelMixin,
                              BaseModelViewSet):
    """
    템플릿 카테고리 API endpoint
    """
    model = TemplateCategory
    serializer_class = TemplateCategorySerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        qs = super(TemplateCategoryViewSet, self).get_queryset()
        if self.action == 'list':
            qs = qs.root()
        return qs

    def retrieve(self, request, *args, **kwargs):
        rtn = super(TemplateCategoryViewSet, self).retrieve(request, *args, **kwargs)
        category_id = kwargs.get('pk')
        children = self.model.objects.get_children(category_id)
        templates = MissionTemplate.objects.get_by_category(category_id)
        rtn.data.update({'children': self.serializer_class(children, many=True).data})
        rtn.data.update({'templates': TemplateSerializer(templates, many=True).data})
        return rtn


class TemplateViewSet(mixins.RetrieveModelMixin,
                      mixins.ListModelMixin,
                      BaseModelViewSet):
    """
    미션 템플릿 API endpoint
    """
    model = MissionTemplate
    serializer_class = TemplateSerializer
    pagination_class = None
    permission_classes = (permissions.AllowAny,)

    def get_serializer_class(self):
        if self.action == 'mission':
            self.serializer_class = TemplateMissionSerializer
        if self.action == 'list':
            self.serializer_class = TemplateWithTagsSerializer
        return self.serializer_class

    def get_queryset(self):
        qs = super(TemplateViewSet, self).get_queryset().filter(is_active=True)
        if self.action == 'home':
            # todo: 예시로 추가한 것임. 큐레이션 로직 추가할 것.
            from random import sample
            curated = list(qs)
            qs = sample(curated, min(len(curated), 10))
        return qs

    def retrieve(self, request, *args, **kwargs):
        rtn = super(TemplateViewSet, self).retrieve(request, *args, **kwargs)
        obj = self.get_object()
        rtn.data.update({'questions': TemplateQuestionSerializer(obj.ordered_questions, many=True).data})
        return rtn

    @action(methods=['get'], detail=False)
    def home(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    @action(methods=['get'], detail=False)
    def ikea_products(self, request, *args, **kwargs):
        code = request.GET.get('code', None)
        crawler = IkeaProductCrawler()
        if not code:
            raise Errors.fields_invalid
        data = crawler.search(code)
        if data:
            return response.Response(data=data)
        else:
            raise Errors.not_found

    @action(methods=['post'], detail=True)
    def mission(self, request, *args, **kwargs):
        # 입찰중 미션이 있는 경우에는 미션을 새로 요청할 수 없음
        if Mission.objects.check_user_bidding(request.user.id):
            raise Errors.bidding_mission_exist

        obj = self.get_object()
        data = TemplateMissionSerializer(request.data).data
        if 'data' not in data or not data['data']:
            raise Errors.fields_invalid

        mission_data = obj.to_mission_data(data['data'])
        if isinstance(mission_data, Exception):
            raise mission_data

        if 'mobile' in request.data and 'verification_id' in request.data:
            # 웹 요청인 경우 처리
            user = self.handle_web_mission(request, obj.mission_type.code)
            mission_data['user'] = user
            request.user = user
        else:
            # 웹 요청이 아닌 경우 처리
            if not request.user.is_authenticated:
                raise Errors.permission_denied

        serializer = MissionSerializer(data=mission_data)
        serializer.is_valid(raise_exception=True)
        serializer.context['request'] = request
        mission = serializer.save()
        mission.template = obj
        mission.template_data = mission_data['template_data']

        # request
        if mission.request():
            logger.info('[mission %s requested]' % mission.code)
            try:
                result = mission.push_result.check_requested_count()
            except:
                result = 0

            # 웹 요청인 경우 추가 데이터 처리
            if 'mobile' in request.data and 'verification_id' in request.data:
                # 웹 로그인 코드 추가
                code = str(timezone.now().timestamp())
                while True:
                    login_code = get_md5_hash(code)
                    if not Mission.objects.filter(login_code=login_code).exists():
                        break
                    code += str(user.id)
                mission.login_code = login_code
                mission.save()

                # 고객에게 문자 발송
                # Notification.objects.sms_preset(request.user, 'web_requested', args=[mission.shortened_url])
                Tasker.objects.task('web_requested', user=request.user, kwargs={'url': mission.shortened_url})
        else:
            logger.info('[mission %s request failed]' % mission.code)
            result = 0

        return response.Response({
            'id': mission.id,
            'result': result,
            'bidding_limit': mission.mission_type.bidding_limit
        })

    def handle_web_mission(self, request, recommended_by=''):
        # 회원 변환
        verification = MobileVerification.objects.get_verified_recently(
            id=request.data['verification_id'],
            mobile=request.data['mobile']
        )
        if not verification:
            raise ExternalErrors.VERIFICATION_NOT_FOUND.exception
        UserModel = get_user_model()
        recommended_by = (recommended_by + '_W') if recommended_by else 'WEB'
        user = UserModel.objects.get_external_mission_user(verification.number, recommended_by)
        if not verification.user:
            verification.user = user
            verification.save()

        return user
