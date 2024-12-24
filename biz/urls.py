
from django.conf import urls
from django.urls import path
from django.views.generic import RedirectView

from .views import dashboard, account

urls.handler403 = 'biz.views.dashboard.handler403'
urls.handler404 = 'biz.views.dashboard.handler404'
urls.handler500 = 'biz.views.dashboard.handler500'


app_name = 'biz'

urlpatterns = [
    path('login/', account.Login.as_view(), name='login'),
    path('logout/', account.LogoutView.as_view(), name='logout'),
    path('partnerships/', dashboard.JoinedPartnershipListView.as_view(), name='joined'),
    path('join/', account.JoinView.as_view(), name='join'),
    path('', RedirectView.as_view(url='login/'), name='main'),

    # 협력사 대시보드
    path('<str:code>/dashboard/', dashboard.DashboardView.as_view(), name='dashboard'),
    path('<str:code>/service/<str:service>/', dashboard.ServiceActivationRequestView.as_view(), name='service-request'),

    # 캠페인
    path('<str:code>/campaigns/add/', dashboard.CampaignCreateView.as_view(), name='campaign-create'),
    path('<str:code>/campaigns/<slug:campaign_code>/', dashboard.CampaignUpdateView.as_view(), name='campaign-update'),
    path('<str:code>/campaigns/<slug:campaign_code>/data/', dashboard.CampaignUserDataView.as_view(), name='campaign-user-data'),
    path('<str:code>/campaigns/', dashboard.CampaignListView.as_view(), name='campaign-list'),

    # 기업미션
    path('<str:code>/missions/', dashboard.MissionListView.as_view(), name='mission-list'),

    # 연동 api
    path('<str:code>/apis/secret/reset/', dashboard.ApiSecretResetView.as_view(), name='api-secret-reset'),
    path('<str:code>/apis/<int:template_id>/', dashboard.ApiDataListView.as_view(), name='api-data-list'),
    path('<str:code>/apis/', dashboard.ApiListView.as_view(), name='api-list'),

    # 협력사 프로필
    path('<str:code>/profile/', dashboard.ProfileView.as_view(), name='profile'),
    path('<str:code>/payment/', dashboard.PaymentView.as_view(), name='payment'),

]
