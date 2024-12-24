import logging

from django.shortcuts import get_object_or_404, redirect, reverse
from django.conf import settings
from django.views.generic import DetailView, TemplateView
from django.http.response import Http404

from rest_framework import mixins, response
from rest_framework.decorators import action
from drf_yasg.utils import swagger_auto_schema, no_body
from rest_framework_simplejwt.views import TokenObtainPairView
import short_url

from common.exceptions import Errors
from common.admin import log_with_reason
from common.utils import add_comma
from base.exceptions import ExternalErrors
from base.views import BaseModelViewSet
from accounts import permissions
from notification.models import Notification
from missions.models import MissionType, Bid, Interaction, Mission, MissionTemplate, Review
from missions.views import InteractionViewSet
from .models import ExternalMission, ExternalMissionProduct
from .serializers import (
    ExternalAuthTokenObtainPairSerializer, ExternalMissionSerializer, ExternalMissionReadOnlySerializer,
    ExternalInteractionSerializer, ExternalMissionProductSerializer, ExternalBidSerializer,
    get_code_from_request_referer,
    WebAuthTokenObtainPairSerializer, WebMissionReadOnlySerializer
)


logger = logging.getLogger('django')


"""
responses
"""


try:
    type_code_description = '[type_code]\n' + '\n'.join(['%s %s' % (o.code.lower(), o.description)
                                                         for o in MissionType.objects.exclude(code='')])
except:
    type_code_description = ''


"""
viewsets
"""


def shorten_url_redirect_view(request, shortened):
    """줄인 url 리다이렉트"""
    try:
        id = short_url.decode_url(shortened)
    except:
        raise Errors.not_found

    obj = get_object_or_404(ExternalMission, pk=id)
    url = '%s?code=%s' % (settings.EXTERNAL_MISSION_SMS_URLS[obj.mission_type.code], obj.login_code)
    return redirect(url)


class ExternalAuthTokenObtainPairView(TokenObtainPairView):
    """
    외부 인증 토큰 pair 발급
    """
    serializer_class = ExternalAuthTokenObtainPairSerializer

    @swagger_auto_schema(responses={404: Errors.not_found.as_p()})
    def post(self, request, *args, **kwargs):
        return super(ExternalAuthTokenObtainPairView, self).post(request, *args, **kwargs)


class ExternalMissionViewSet(mixins.CreateModelMixin,
                             mixins.RetrieveModelMixin,
                             BaseModelViewSet):
    """
    외부 미션요청 API endpoint
    """
    model = ExternalMission
    serializer_class = ExternalMissionSerializer
    permission_classes = (permissions.AllowAny,)
    lookup_url_kwarg = 'code'
    lookup_field = 'login_code'

    def get_serializer_class(self):
        if self.action == 'retrieve':
            self.serializer_class = ExternalMissionReadOnlySerializer
        return super(ExternalMissionViewSet, self).get_serializer_class()

    @swagger_auto_schema(operation_description='미션타입 코드\n\n---\n%s' % type_code_description)
    def create(self, request, *args, **kwargs):
        type_code = kwargs.get('type_code', '').upper()
        try:
            mission_type = MissionType.objects.get(code=type_code)
        except:
            raise Errors.not_found
        obj = ExternalMission.objects.create(mission_type=mission_type, data=request.data['data'])
        result = obj.request_mission()
        if isinstance(result, ExternalErrors):
            raise result.exception
        return response.Response({'result': result})

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.user != request.user:
            raise Errors.permission_denied
        if not obj._mission:
            return Errors.mission_state_not_allowed
        return response.Response(data=self.get_serializer_class()(instance=obj._mission).data)


class ExternalMissionProductViewSet(mixins.RetrieveModelMixin,
                                    BaseModelViewSet):
    """
    외부 미션요청 제품 API endpoint
    """
    model = ExternalMissionProduct
    serializer_class = ExternalMissionProductSerializer
    permission_classes = (permissions.AllowAny,)
    lookup_url_kwarg = 'identifier'
    lookup_field = 'identifier'

    @swagger_auto_schema(operation_description='미션타입 코드\n\n---\n%s' % type_code_description)
    def retrieve(self, request, *args, **kwargs):
        return response.Response({})


class ExternalInteractionViewSet(InteractionViewSet):
    """
    외부 미션요청 인터랙션 API endpoint
    """


"""
웹 템플릿
; 이후에 External을 대체하도록 고려할 것
"""


def shorten_web_url_redirect_view(request, shortened):
    """web template shorten url redirect"""
    try:
        id = short_url.decode_url(shortened)
    except:
        raise Errors.not_found

    obj = get_object_or_404(Mission, pk=id)
    if obj.url:
        return redirect(obj.url)
    raise Errors.not_found


class WebTemplateView(TemplateView):
    """
    웹 템플릿 미션요청 뷰
    """
    template_name = 'mission_template.html'

    def dispatch(self, request, *args, **kwargs):
        self.template = get_object_or_404(MissionTemplate, id=kwargs['template_id'])
        if kwargs['template_name'] != self.template.slug or not self.template.is_active:
            raise Http404
        self.reviews = Review.objects.get_helper_received().filter(bid__mission__template=self.template).order_by('-created_datetime')
        return super(WebTemplateView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(WebTemplateView, self).get_context_data(**kwargs)
        context.update({
            'title': self.template.name,
            'title_image_url': 'https://%s%s' % (settings.MAIN_HOST, self.template.image.url) if self.template.image else '',
            'reviews': self.reviews[:4],
            'review_count': add_comma(self.reviews.count()),
            'review_average': '%.2f' % self.reviews.mean(round_digit=2)[0],
            'template_url': 'https://%s/mission/?template_id=%s' % (settings.STATIC_HOST, self.template.id),
            'keywords': ', '.join(self.template.tag_list),
            'description': self.template.description,
        })
        return context


# class WebMissionView(DetailView):
#     """
#     웹 템플릿 미션 뷰
#     """
#     template_name = 'mission_bid.html'
#     slug_url_kwarg = 'code'
#     slug_field = 'code'
#     model = Mission
#
#     def dispatch(self, request, *args, **kwargs):
#         rtn = super(WebMissionView, self).dispatch(request, *args, **kwargs)
#         if not self.object.template:
#             raise Http404
#         return rtn


class WebAuthTokenObtainPairView(TokenObtainPairView):
    """
    웹 템플릿 인증 토큰 pair 발급
    """
    serializer_class = WebAuthTokenObtainPairSerializer

    @swagger_auto_schema(responses={404: Errors.not_found.as_p()})
    def post(self, request, *args, **kwargs):
        return super(WebAuthTokenObtainPairView, self).post(request, *args, **kwargs)


class WebMissionViewSet(mixins.RetrieveModelMixin,
                        BaseModelViewSet):
    """
    웹 템플릿 미션 API endpoint
    """
    model = Mission
    serializer_class = WebMissionReadOnlySerializer
    permission_classes = (permissions.AllowAny,)
    lookup_url_kwarg = 'code'
    lookup_field = 'login_code'

    def get_queryset(self):
        return super(WebMissionViewSet, self).get_queryset().filter(template__isnull=False)

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.user != request.user:
            raise Errors.permission_denied
        return response.Response(data=self.serializer_class(instance=obj).data)


class WebInteractionViewSet(InteractionViewSet):
    """
    웹 템플릿 미션 인터랙션 API endpoint
    """
