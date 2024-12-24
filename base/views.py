import logging
import traceback
import ast

from django.views import generic
from django.views.generic import RedirectView, TemplateView
from django.http.response import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings

from rest_framework import viewsets, mixins, views, response, parsers
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from common.utils import CachedProperties, add_comma
from accounts import permissions
from accounts.models import User
from accounts.serializers import CustomerHomeHelperSerializer
from missions.serializers import CustomerHomeMissionSerializer, CustomerHomeTemplateSerializer
from notification.models import Notification, Tasker
from missions.models import Review, MissionTemplate, TemplateKeyword, TemplateTag
from missions.serializers import CustomerHomeReviewSerializer, TemplateSerializer, TemplateTagSerializer
from biz.models import CampaignBanner
from biz.serializers import CampaignBannerSerializer
from .serializers import AreaSerializer, PopupSerializer, CustomerHomeSearchSerializer
from .models import Area, Popup


logger = logging.getLogger('api.request')
anyman = CachedProperties()


"""
Mixins and Extensions
"""


class BaseResponseDataMixin:
    """
    API 전반에 사용할 기본 Response
    """
    permission_classes = (permissions.IsValidUser,)

    def finalize_response(self, request, response, *args, **kwargs):
        res = super(BaseResponseDataMixin, self).finalize_response(request, response, *args, **kwargs)
        if res.status_code < 300 and res.data is not None and 'data' not in res.data and 'available' not in res.data:
            res.data = {'data': res.data}
        # if request.user.is_authenticated:
        #     res.data['is_blocked'] = request.user.is_blocked
        # todo: 현재 토큰의 유효성 검사 추가
        return res


class BaseLoggingMixin:
    """
    API 로깅용 mixin
    """
    log_methods = '__all__'
    not_logging_fields = ['password', 'old_password', 'new_password']
    log_prefix = ''

    def initial(self, request, *args, **kwargs):
        self.log = {}
        self.log['requested_datetime'] = timezone.now()
        self.log['data'] = self._clean_data(request.body)
        super(BaseLoggingMixin, self).initial(request, *args, **kwargs)

        try:
            data = request.data.dict()
        except AttributeError:
            data = request.data
        self.log['data'] = self._clean_data(data)

    def handle_exception(self, exc):
        try:
            res = super(BaseLoggingMixin, self).handle_exception(exc)
        except:
            res = response.Response(status=500)
        self.log['errors'] = traceback.format_exc()
        return res

    def finalize_response(self, request, response, *args, **kwargs):
        response = super(BaseLoggingMixin, self).finalize_response(request, response, *args, **kwargs)

        if self.log_methods == '__all__' or request.method in self.log_methods:
            self.write_log(request, response)
        return response

    def write_log(self, request, response=None, level=None):
        # if response.streaming:
        #     rendered_content = None
        # elif hasattr(response, 'rendered_content'):
        #     rendered_content = response.rendered_content
        # else:
        #     rendered_content = response.getvalue()

        self.log.update(
            {
                'uuid': request.headers['uuid'] if 'uuid' in request.headers else '',
                'user_agent': request.headers['User-Agent'] if 'User-Agent' in request.headers else '',
                'remote_address': self._get_ip_address(request),
                'view': self._get_view_name(request),
                'view_method': self._get_view_method(request),
                'path': request.path,
                'method': self.log_prefix + request.method,
                'query_string': request.META['QUERY_STRING'],
                'user_code': self._get_user_code(request),
                'response_ms': self._get_response_ms(),
                # 'response': self._clean_data(rendered_content),
                'status_code': response.status_code if response else 400,
            }
        )
        if self.log['query_string']:
            self.log['query_string'] = '?' + self.log['query_string']
        level = level or (logging.INFO if self.log['status_code'] < 300 else logging.WARNING)

        if response.status_code in (301, 302):
            self.log['data'] = '=> %s' % response.url

        msg_list = ['[{view}.{view_method}] {user_code}@{remote_address} "{method} {path}{query_string}" {status_code} {response_ms}ms {data}        {user_agent} {uuid}'.format(**self.log)]

        if 'errors' in self.log and response and response.status_code == 500:
            level = logging.ERROR
            msg_list.append(self.log['errors'])

        msg = '\n'.join(msg_list)
        try:
            logger.log(level, msg)
            if len(msg_list) > 1:
                anyman.slack.channel('anyman__80dev').section_msg(
                    ['%s Server Error' % anyman.server, msg_list[0]],
                    [{'color': '#ff0000', 'contents': msg_list[1]}]
                )
        except Exception:
            # logger.exception('Logging API call raise exception!')
            pass

    def _get_ip_address(self, request):
        ipaddr = request.META.get("HTTP_X_FORWARDED_FOR", None)
        if ipaddr:
            return ipaddr.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def _get_view_name(self, request):
        method = request.method.lower()
        try:
            attributes = getattr(self, method)
            view_name = type(attributes.__self__).__module__ + '.' + type(attributes.__self__).__name__
            return view_name
        except AttributeError:
            return None

    def _get_view_method(self, request):
        if hasattr(self, 'action'):
            return self.action if self.action else None
        return request.method.lower()

    def _get_user_code(self, request):
        if request.user.is_anonymous:
            return '-'
        return request.user.code

    def _get_response_ms(self):
        response_timedelta = timezone.now() - self.log['requested_datetime']
        response_ms = int(response_timedelta.total_seconds() * 1000)
        return max(response_ms, 0)

    def _clean_data(self, data):
        if isinstance(data, bytes):
            data = data.decode(errors='replace')

        if isinstance(data, list):
            return [self._clean_data(d) for d in data]
        if isinstance(data, dict):
            data = dict(data)

            for key, value in data.items():
                try:
                    value = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    pass
                if isinstance(value, list) or isinstance(value, dict):
                    data[key] = self._clean_data(value)
                if key.lower() in self.not_logging_fields:
                    data[key] = '***'
        return data


class BaseModelViewSet(BaseResponseDataMixin, BaseLoggingMixin, viewsets.GenericViewSet):
    """
    사이트 전반에 사용할 기본 ModelViewSet
    """
    model = None

    def get_queryset(self):
        return self.model.objects.all()


class BaseModelLogView(BaseLoggingMixin):
    """
    사이트 전반에 사용할 기본 ModelView
    """
    log_prefix = 'Web '

    def dispatch(self, request, *args, **kwargs):
        self.log = {}
        self.log['requested_datetime'] = timezone.now()
        self.log['data'] = self._clean_data(request.body)
        try:
            rtn = super(BaseModelLogView, self).dispatch(request, *args, **kwargs)
        except Exception as e:
            self.log['errors'] = traceback.format_exc()
            self.write_log(request)
            raise e
        if self.log_methods == '__all__' or request.method in self.log_methods:
            self.write_log(request, rtn)
        return rtn


"""
API Viewsets
"""


class CustomerHomeView(views.APIView):
    """
    고객 홈 뷰
    """
    permission_classes = (permissions.AllowAny,)

    def _is_valid_user(self, user):
        if not user.is_authenticated or not user.is_active or user.is_withdrawn or user.is_service_blocked:
            return False
        return True

    def get(self, request, *args, **kwargs):
        if self._is_valid_user(request.user):
            new_count = Notification.objects.get_by_usercode(request.user.code, exclude_read=True).count()
        else:
            new_count = 0

        keywords = TemplateTag.objects.get_personalized(request.user)
        templates = MissionTemplate.objects.get_recommended(request.user)
        campaign_banners = CampaignBanner.objects.current('user')
        user_popup = Popup.objects.current('user')

        data = {
            'display': [
                {'templates': '이런 서비스는 어떠세요?'},
                {'new_templates': '신규 서비스가 추가되었어요.'},
                {'helpers': '추천 헬퍼'},
                {'reviews': '다른 고객님의 이용 후기에요.'},
            ],
            'new_count': new_count,
            'keywords': TemplateTagSerializer(keywords, many=True).data,
            'templates': TemplateSerializer(templates, many=True).data,
            'popup': PopupSerializer(user_popup, many=True, context={'request': request}).data \
                     + CampaignBannerSerializer(campaign_banners, many=True, context={'request': request}).data,
            'helpers': anyman.customer_home['helpers'],
            'new_templates': anyman.customer_home['new_templates'],
            'reviews': anyman.customer_home['reviews'],
            'missions': anyman.customer_home['missions']  # todo: 업데이트 이후로는 불필요한 항목
        }
        return response.Response(data)

    @classmethod
    def cache_all(cls):
        CustomerHomeHelperSerializer.cache()
        CustomerHomeMissionSerializer.cache()
        CustomerHomeTemplateSerializer.cache()
        CustomerHomeReviewSerializer.cache()
        # PopupSerializer.cache_user()
        Tasker.objects.cache_taskers()


class CustomerHomeSearchViewSet(mixins.ListModelMixin,
                                mixins.CreateModelMixin,
                                BaseModelViewSet):
    """
    고객 홈 검색 뷰
    """
    serializer_class = CustomerHomeSearchSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None

    def list(self, request, *args, **kwargs):
        query = request.GET.get('query', '')
        if not query:
            return response.Response(data={})
        templates = TemplateKeyword.objects.search(request.user, query)
        return response.Response(data=TemplateSerializer(templates, many=True).data)

    def create(self, request, *args, **kwargs):
        TemplateKeyword.objects.save_result(request.user, request.data['keywords'], request.data['template_id'] or None)
        return response.Response(data={})


class AreaViewSet(mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  BaseModelViewSet):
    """
    지역 API endpoint
    """
    model = Area
    serializer_class = AreaSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None


@method_decorator(swagger_auto_schema(manual_parameters=[openapi.Parameter(
        'location', openapi.IN_QUERY, description="Location", type=openapi.TYPE_STRING
    )]), name='list')
class PopupViewSet(mixins.ListModelMixin,
                   BaseModelViewSet):
    """
    팝업 API endpoint
    """
    model = Popup
    serializer_class = PopupSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        location = self.request.query_params.get('location', '')
        return self.model.objects.current(location)


class PopupLinkView(BaseModelLogView, RedirectView):
    """
    팝업 링크 뷰
    """
    def get_redirect_url(self, *args, **kwargs):
        try:
            obj = Popup.objects.current().get(id=kwargs.get('id'))
        except:
            pass
        else:
            if obj.target_type == 'link':
                # todo: 링크 이동에 따른 tracking action 추가
                return obj.target_id

        raise Http404


"""
Views
"""


class MainView(TemplateView):
    template_name = 'main.html'

    def dispatch(self, request, *args, **kwargs):
        self.health_check()
        return super(MainView, self).dispatch(request, *args, **kwargs)

    def health_check(self):
        now = timezone.now()
        if now.minute == 0 and now.second <= 30:
            CustomerHomeView.cache_all()

