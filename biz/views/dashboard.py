import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Prefetch
from django.http.response import Http404
from django.shortcuts import redirect, render_to_response
from django.utils.safestring import mark_safe
from django.views.generic import ListView, FormView, UpdateView
from django.urls import reverse
from django.views.generic.base import RedirectView, TemplateView
from django.views.generic.detail import DetailView
from rest_framework import response
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from missions.models import MissionTemplate, Mission, MultiMission
from biz.forms import CampaignCreateForm, CampaignForm
from biz.models import (Partnership, PartnershipUserRelation, LOCATION_IMAGE_SIZES, LOCATIONS, Campaign,
                        CampaignQuestion, CampaignBanner, CampaignUserData)
from .mixins import PartnershipMixin, AcceptedPartnershipMixin



def handler403(request, exception, template_name="biz/page_403.html"):
    res = render_to_response(template_name)
    res.status_code = 403
    return res


def handler404(request, exception, template_name="biz/page_404.html"):
    res = render_to_response(template_name)
    res.status_code = 404
    return res


def handler500(request, template_name="biz/page_500.html"):
    res = render_to_response(template_name)
    res.status_code = 500
    return res


def get_banner_sizes():
    banner_sizes = []
    for location, image_size in zip(LOCATIONS, LOCATION_IMAGE_SIZES):
        data = {'location': location, 'image_size': image_size[1]}
        banner_sizes.append(data)
    return banner_sizes


class ServiceActivationRequestView(PartnershipMixin, DetailView):
    """
    서비스 활성화 요청 뷰
    """
    model = Partnership

    def get(self, request, *args, **kwargs):
        service = kwargs.get('service')
        if service not in dict(self.model.ABAILABLE_SERVICES):
            raise Http404
        if service in self.partnership.services:
            messages.error(request, '이미 사용중인 서비스입니다.')
        else:
            if service == 'missions':
                # todo: 정기결제 여부 확인후 정기결제 없으면 결제 페이지로 리다이렉트 하도록 변경할 것.
                return redirect(request.META['HTTP_REFERER'])
            self.partnership.services.append(service)
            self.partnership.save()
            messages.success(request, '서비스 사용신청이 완료되었습니다. 지금부터 바로 사용할 수 있습니다.')
        return redirect(request.META['HTTP_REFERER'])


class DashboardView(PartnershipMixin, TemplateView):
    """
    애니비즈 대시보드 뷰
    """
    template_name = 'biz/dashboard.html'


class JoinedPartnershipListView(LoginRequiredMixin, ListView):
    """
    참여중인 파트너쉽 리스트 뷰
     """
    template_name = 'biz/joined_partnership.html'
    model = PartnershipUserRelation

    def __init__(self):
        super().__init__()
        self.partnership_user_relation = None

    def dispatch(self, request, *args, **kwargs):
        self.partnership_user_relation = PartnershipUserRelation.objects\
            .select_related('partnership', 'user', 'partnership__address_area__parent')\
            .filter(user=self.request.user).order_by('-id')
        if self.partnership_user_relation.count() == 1:
            return redirect('biz:profile', self.partnership_user_relation[0].partnership.code)
        return super(JoinedPartnershipListView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return self.partnership_user_relation


"""
캠페인 뷰
"""


class CampaignCreateView(AcceptedPartnershipMixin, FormView):
    """
    애니비즈 캠페인 생성 뷰
    """
    template_name = 'biz/campaign_create.html'
    success_url = ''
    form_class = CampaignCreateForm

    def get_context_data(self, **kwargs):
        context = super(CampaignCreateView, self).get_context_data(**kwargs)
        context['banner_sizes'] = get_banner_sizes()
        context['question_type_list'] = CampaignQuestion.QUESTION_TYPES
        return context

    @transaction.atomic
    def form_valid(self, form):
        form.instance.partnership = self.partnership
        campaign = form.save()
        # 배너 이미지 등록
        images = form.cleaned_data.pop('image')
        locations = form.cleaned_data.pop('location')
        if images and locations:
            file_bulk_list = []
            images = self.request.FILES.getlist('image')
            location_index = 0
            for location in json.loads(locations):
                if location.get('file'):
                    data = CampaignBanner(campaign=campaign, location=location.get('location_number'),
                                          image=images[location_index])
                    file_bulk_list.append(data)
                    location_index += 1
            CampaignBanner.objects.bulk_create(file_bulk_list)
        # 질문 등록
        campaign_questions = form.cleaned_data.pop('campaign_questions')
        question_bulk_list = []
        for i, question in enumerate(json.loads(campaign_questions)):
            data = CampaignQuestion(
                campaign=campaign,
                order_no=i,
                question_type=question.get('question_type'),
                name=question.get('name'),
                title=question.get('title'),
                description=question.get('description'),
                options=question.get('options'),
                has_etc_input=question.get('has_etc_input'),
                is_required=question.get('is_required'),
            )
            question_bulk_list.append(data)
        CampaignQuestion.objects.bulk_create(question_bulk_list)
        return super().form_valid(form)

    def form_invalid(self, form):
        return super(CampaignCreateView, self).form_invalid(form)

    def get_success_url(self):
        return reverse('biz:campaign-list', kwargs={'code': self.kwargs.get('code')})


class CampaignUpdateView(AcceptedPartnershipMixin, UpdateView):
    """
    애니비즈 캠페인 업데이트 뷰
    """
    template_name = 'biz/campaign_update.html'
    success_url = ''
    form_class = CampaignForm
    model = Campaign
    slug_url_kwarg = 'campaign_code'
    slug_field = 'campaign_code'

    def get_form_kwargs(self):
        return super(CampaignUpdateView, self).get_form_kwargs()

    def get_context_data(self, **kwargs):
        context = super(CampaignUpdateView, self).get_context_data(**kwargs)
        campaign_code = self.kwargs.get('campaign_code')
        banners = CampaignBanner.objects.select_related('campaign').filter(campaign__campaign_code=campaign_code,
                                                                           is_active=True)
        # 현재 배너 이미지 미리보기
        old_banner_dict = {}
        for banner in banners:
            if banner.image:
                accepted_datetime = banner.accepted_datetime.strftime('%Y.%m.%d') if banner.accepted_datetime else None
                old_banner_dict[banner.location] = {
                    'image': banner.image.url,
                    'accepted_datetime': accepted_datetime
                }
        context['banner_sizes'] = get_banner_sizes()
        context['old_banner_dict'] = json.dumps(old_banner_dict, ensure_ascii=False)
        context['questions'] = CampaignQuestion.objects.select_related('campaign').filter(campaign__campaign_code=campaign_code)
        return context

    @transaction.atomic
    def form_valid(self, form):
        campaign_id = form.instance.id
        # 배너 이미지 추가
        image = form.cleaned_data.pop('image')
        locations = form.cleaned_data.pop('location')
        if image and locations:
            images = self.request.FILES.getlist('image')
            location_index = 0
            file_bulk_list = []
            for location in json.loads(locations):
                if location.get('file'):
                    location_number = location.get('location_number')
                    CampaignBanner.objects.filter(campaign_id=campaign_id, location=location_number).update(is_active=False)
                    file_bulk_list.append(CampaignBanner(campaign_id=campaign_id, location=location_number,
                                          image=images[location_index]))
                    location_index += 1
            CampaignBanner.objects.bulk_create(file_bulk_list)
        return super().form_valid(form)

    def form_invalid(self, form):
        return super(CampaignUpdateView, self).form_invalid(form)

    def get_success_url(self):
        return reverse('biz:campaign-list', kwargs={'code': self.kwargs.get('code')})


class CampaignListView(AcceptedPartnershipMixin, ListView):
    """
    애니비즈 캠페인 리스트 뷰
    """
    template_name = 'biz/campaign_list.html'
    model = Campaign
    paginate_by = 10

    def get_queryset(self):
        qs = super(CampaignListView, self).get_queryset()
        qs = qs.select_related('partnership').filter(partnership=self.partnership).prefetch_related(
                Prefetch('banners', queryset=CampaignBanner.objects.filter(is_active=True).order_by('location')),'questions'
            ).order_by('-id')
        return qs


class CampaignUserDataView(AcceptedPartnershipMixin, ListView):
    """
    애니비즈 캠페인 유져 데이터 뷰
    """
    template_name = 'biz/campaign_user_data_list.html'
    model = CampaignUserData
    paginate_by = 20
    campaign = None

    def dispatch(self, request, *args, **kwargs):
        campaign_code = self.kwargs.get('campaign_code')
        self.campaign = Campaign.objects.filter(campaign_code=campaign_code).last()
        rtn = super(CampaignUserDataView, self).dispatch(request, *args, **kwargs)
        if not self.campaign or self.campaign.partnership != self.partnership:
            raise Http404
        return rtn

    def get_queryset(self):
        qs = super(CampaignUserDataView, self).get_queryset()
        qs = qs.filter(banner__campaign__partnership=self.partnership, banner__campaign=self.campaign)
        return qs

    def get_context_data(self, **kwargs):
        context = super(CampaignUserDataView, self).get_context_data(**kwargs)
        context['campaign'] = self.campaign
        return context


"""
기업미션 뷰
"""


class MissionListView(AcceptedPartnershipMixin, ListView):
    """
    애니비즈 기업미션 리스트 뷰
    """
    template_name = 'biz/mission_list.html'
    model = MultiMission
    paginate_by = 10


"""
API 연동 뷰
"""


class ApiSecretResetView(AcceptedPartnershipMixin, UpdateView):
    """
    API Secret Reset 뷰
    """
    model = Partnership

    def post(self, request, *args, **kwargs):
        secret = self.partnership.make_secret()
        messages.error(request, mark_safe('다음의 새로 생성된 시크릿을 지금 바로 복사하여 귀사의 연동 서비스에 적용하십시오.<br/>새로 생성된 시크릿은 지금 처음이자 마지막으로 화면에 표시되며, 이후로는 알 수 없습니다.<br/><br/><h5>%s</h5>' % secret))
        return redirect(request.META['HTTP_REFERER'])


class ApiListView(AcceptedPartnershipMixin, ListView):
    """
    애니비즈 미션 api 뷰
    """
    template_name = 'biz/api_list.html'
    model = MissionTemplate
    paginate_by = 10

    def get_queryset(self):
        qs = super(ApiListView, self).get_queryset()
        return qs.filter(partnership=self.partnership)

    def get_context_data(self, **kwargs):
        context = super(ApiListView, self).get_context_data(**kwargs)
        return context


class ApiDataListView(AcceptedPartnershipMixin, ListView):
    """
    애니비즈 미션 api 데이터 뷰
    """
    template_name = 'biz/api_data_list.html'
    model = Mission
    paginate_by = 10
    ordering = ('-id',)

    def dispatch(self, request, *args, **kwargs):
        try:
            self.template = MissionTemplate.objects.get(id=kwargs.get('template_id'))
        except:
            raise Http404
        self.query = request.GET.get('q', '') or ''
        rtn = super().dispatch(request, *args, **kwargs)
        if self.template.partnership != self.partnership:
            raise Http404
        return rtn

    def get_queryset(self):
        qs = super(ApiDataListView, self).get_queryset().filter(template=self.template)
        if self.query:
            qs = qs.search(self.query)
        return qs
    
    def get_context_data(self, **kwargs):
        context = super(ApiDataListView, self).get_context_data(**kwargs)
        context['template'] = self.template
        return context


"""
프로필 뷰
"""


class ProfileView(PartnershipMixin, ListView):
    """
     애니비즈 프로필 뷰
     """
    template_name = 'biz/profile.html'
    model = PartnershipUserRelation

    def get_queryset(self):
        return self.partnership


class PaymentView(PartnershipMixin, TemplateView):
    """
    애니비즈 결제 뷰
    """
    template_name = 'biz/payment.html'
