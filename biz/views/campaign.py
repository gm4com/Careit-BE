import logging

from django.utils import timezone
from django.conf import settings
from django.views import generic
from django.shortcuts import redirect

from rest_framework import mixins, response, parsers
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
from biz.models import Campaign, CampaignBanner, CampaignUserData, CampaignUserDataFile
from biz.serializers import CampaignSerializer, CampaignQuestionSerializer, CampaignUserDataSerializer, CampaignUserDataFileSerializer


logger = logging.getLogger('django')


class BannerLinkView(generic.DetailView):
    """
    배너 링크 뷰
    """
    model = CampaignBanner
    pk_url_kwarg = 'id'

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        user = User.objects.filter(code=kwargs.get('code')).last()
        if user:
            if CampaignUserData.objects.filter(created_user=user, answered_datetime__isnull=False, banner__campaign=obj.campaign).exists():
                return redirect('https://%s/campaign/duplicated.html?title=%s' % (settings.STATIC_HOST, obj.campaign.title))
            identifier = ''
        else:
            hash = request.META['HTTP_USER_AGENT']
            if 'Accept-Language' in request.headers:
                hash += request.headers['Accept-Language']
            if 'HTTP_REFERER' in request.META:
                hash += request.META['HTTP_REFERER']
            identifier = get_md5_hash(hash)
        data_obj = CampaignUserData.objects.create(
            banner=obj,
            created_user=user,
            created_user_identifier=identifier,
            clicked_datetime=timezone.now()
        )
        return redirect('https://%s/campaign/?code=%s' % (settings.STATIC_HOST, data_obj.code))


class CampaignViewSet(mixins.RetrieveModelMixin,
                      BaseModelViewSet):
    """
    캠페인 viewsets
    """
    model = CampaignUserData
    lookup_field = 'code'
    lookup_url_kwarg = 'code'
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        qs = super(CampaignViewSet, self).get_queryset()
        before_one_day = timezone.now() - timezone.timedelta(days=1)
        return qs.filter(clicked_datetime__gt=before_one_day)

    def retrieve(self, request, *args, **kwargs):
        user_data = self.get_object()
        data = CampaignSerializer(user_data.banner.campaign).data
        data.update({'questions': CampaignQuestionSerializer(user_data.banner.campaign.ordered_questions, many=True).data})
        return response.Response(data)


class CampaignUserDataViewSet(mixins.UpdateModelMixin,
                              BaseModelViewSet):
    """
    캠페인 유져 데이터 viewsets
    """
    model = CampaignUserData
    lookup_url_kwarg = 'code'
    lookup_field = 'code'
    http_method_names = ['patch']
    serializer_class = CampaignUserDataSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        qs = super(CampaignUserDataViewSet, self).get_queryset()
        before_one_day = timezone.now() - timezone.timedelta(days=1)
        return qs.filter(clicked_datetime__gt=before_one_day)

    def update(self, request, *args, **kwargs):
        user_data = self.get_object()
        result = user_data.banner.campaign.to_user_data(request.data['data'], answered_datetime=timezone.now())
        if isinstance(result, Exception):
            raise result

        self.model.objects.filter(id=user_data.id).update(**result)
        return response.Response({'result': True})


class CampaignUserDataFileViewSet(mixins.CreateModelMixin,
                                  BaseModelViewSet):
    """
    캠페인 유져 데이터 파일 viewsets
    """
    model = CampaignUserDataFile
    permission_classes = (permissions.AllowAny,)
    serializer_class = CampaignUserDataFileSerializer
    parser_classes = (parsers.MultiPartParser,)

    @swagger_auto_schema(responses={400: Errors.fields_invalid.as_p()})
    def create(self, request, *args, **kwargs):
        """유저 데이터 파일 업로드"""
        # 첨부파일 체크
        if 'attach' not in request.data:
            raise Errors.fields_invalid

        # 유져 데이터 코드 체크
        before_one_day = timezone.now() - timezone.timedelta(days=1)
        user_data = CampaignUserData.objects.filter(code=kwargs.get('code'), clicked_datetime__gt=before_one_day).last()
        if not user_data:
            raise Errors.not_found

        # 질문 id 처리
        question_id = kwargs.get('question_id')

        # 오브젝트 처리
        file_obj = request.data['attach']
        obj = self.model.objects.create(user_data=user_data, question_id=question_id)
        filename = obj.handle_attach(file_obj)
        url = request.build_absolute_uri(settings.MEDIA_URL + filename)

        return response.Response({'attach': url})

