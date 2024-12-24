"""web URL Configuration"""

from django.views.generic.base import TemplateView

import biz
from missions.models import TemplateCategory
from rest_framework.routers import DefaultRouter
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from django.views.generic import RedirectView

from common.views import WebhookCallbackView
from base.views import (
    CustomerHomeView, CustomerHomeSearchViewSet, MainView, AreaViewSet, PopupViewSet, PopupLinkView
)
from accounts.views import (
    DeviceLogoutView,
    AuthTokenObtainPairView, AuthTokenRefreshView, AuthTokenVerifyView, SocialAuthTokenObtainPairView, ProfileViewSet, AgreementViewSet,
    MobilePhoneViewSet, HelperProfileViewSet, HelperProfileImageViewSet,
    BankAccountViewSet, TINViewSet, QuizViewSet, NotificationViewSet, HelperTokenTemporaryViewSet,
    HelperInformationTemporaryViewSet,
    reset_password_request_token, reset_password_confirm, reset_password_validate_token,
    NiceCIView, NiceCISuccessView, NiceCIFailView
)
from missions.views import (
    TemplateCategoryViewSet, TemplateViewSet, MissionTypeViewSet, AddressViewSet,
    GetByCodeViewSet, MultiMissionViewSet, MissionViewSet, MissionFileViewSet, BidViewSet, BidFileViewSet,
    UserBidsViewSet, AnytalkBidsViewSet, InteractionViewSet, ReviewViewSet, CustomerReviewViewSet,
    HelperReviewViewSet, ReportViewSet, ProfileReportViewSet, UserBlockViewSet, FavoriteUserViewSet,
    HelperTemporaryBidsViewSet
)
from external.views import (
    shorten_url_redirect_view, shorten_web_url_redirect_view,
    ExternalAuthTokenObtainPairView, ExternalMissionViewSet, ExternalMissionProductViewSet, ExternalInteractionViewSet,
    WebAuthTokenObtainPairView, WebTemplateView, WebMissionViewSet, WebInteractionViewSet
)
from payment.views import (
    TransactionView, ExternalPaymentView, PaymentViewSet, BillingPaymentViewSet, GeneralPaymentViewSet,
    PointVoucherViewSet, CouponViewSet, CouponBidViewSet, PointViewSet, CashViewSet, WithdrawViewSet
)
from board.views import BoardViewSet, AttachFileViewSet, CommentViewSet
from biz.views.campaign import CampaignViewSet, CampaignUserDataViewSet, CampaignUserDataFileViewSet, BannerLinkView


"""
일반 api
"""


router = DefaultRouter()
router.register('areas', AreaViewSet, basename='area')
router.register('anytalk/bids', AnytalkBidsViewSet, basename='anytalk-bids-list')
router.register('popups', PopupViewSet, basename='popup')
router.register('profile/mobile', MobilePhoneViewSet, basename='mobile')
router.register('profile/favorites', FavoriteUserViewSet, basename='profile-favorites')
router.register('profile/blocks', UserBlockViewSet, basename='profile-blocks')
router.register('profile/(?P<code>\w+)/reviews', CustomerReviewViewSet, basename='customer-reviews')
router.register('profile/(?P<code>\w+)/reports', ProfileReportViewSet, basename='profile-reports')
router.register('profile', ProfileViewSet, basename='profile')
router.register('agreements', AgreementViewSet, basename='agreements')
router.register('quizzes', QuizViewSet, basename='quizzes')
router.register('helpers/account', BankAccountViewSet, basename='helpers-bank-account')
router.register('helpers/images', HelperProfileImageViewSet, basename='helpers-images')
router.register('helpers/tin', TINViewSet, basename='helper-tin')
router.register('helpers/(?P<code>\w+)/reviews', HelperReviewViewSet, basename='helper-reviews')
router.register('helpers', HelperProfileViewSet, basename='helpers')
router.register('missions/types', MissionTypeViewSet, basename='missions-types')
router.register('missions/addresses', AddressViewSet, basename='missions-addresses')
router.register('missions/by_code', GetByCodeViewSet, basename='missions-by-code')
router.register('missions/multi', MultiMissionViewSet, basename='missions-multi')
router.register('missions/multi/(?P<multi_area_mission_id>\d+)/bids', BidViewSet, basename='missions-multi-bids')
router.register('missions/(?P<mission_id>\d+)/bids', BidViewSet, basename='missions-bids')
router.register('missions/(?P<mission_id>\d+)/files', MissionFileViewSet, basename='missions-files')
router.register('missions/(?P<mission_id>\d+)/reports', ReportViewSet, basename='missions-reviews')
router.register('missions/bids/(?P<bid_id>\d+)/files', BidFileViewSet, basename='missions-bid-files')
router.register('missions/bids/(?P<bid_id>\d+)/interactions', InteractionViewSet, basename='missions-interactions')
router.register('missions/bids/(?P<bid_id>\d+)/reviews', ReviewViewSet, basename='missions-reviews')
router.register('missions/bids/(?P<bid_id>\d+)/reports', ReportViewSet, basename='missions-reviews')
router.register('missions/bids', UserBidsViewSet, basename='missions-user-bids')
router.register('missions/web', WebMissionViewSet, basename='web-missions')
router.register('missions/web/bids/(?P<bid_id>\w+)/interactions', WebInteractionViewSet, basename='web-missions-interactions')
router.register('missions', MissionViewSet, basename='missions')
router.register('presets/categories', TemplateCategoryViewSet, basename='template-category')
router.register('presets/templates', TemplateViewSet, basename='template')
router.register('payment/general', GeneralPaymentViewSet, basename='payment-general')
router.register('payment/billing', BillingPaymentViewSet, basename='payment-billing')
# router.register('payment', PaymentViewSet, basename='payment')
router.register('point/voucher', PointVoucherViewSet, basename='point-voucher')
router.register('coupons', CouponViewSet, basename='coupons')
router.register('coupons/usable/(?P<bid_id>\w+)', CouponBidViewSet, basename='coupons-bid')
router.register('point', PointViewSet, basename='point')
router.register('cash/withdraw', WithdrawViewSet, basename='cash-withdraw')
router.register('cash', CashViewSet, basename='cash')
router.register('board/(?P<board>\w+)/(?P<post_id>\d+)/comments', CommentViewSet, basename='board-comment')
router.register('board/(?P<board>\w+)/(?P<post_id>\d+)/attaches', AttachFileViewSet, basename='board-attach')
router.register('board/(?P<board>\w+)', BoardViewSet, basename='board')
router.register('external/missions/(?P<type_code>\w+)', ExternalMissionViewSet, basename='external-missions')
router.register('external/missions/(?P<type_code>\w+)/bids/(?P<bid_id>\w+)/interactions', ExternalInteractionViewSet, basename='external-missions-interactions')
router.register('external/missions/(?P<type_code>\w+)/products', ExternalMissionProductViewSet, basename='external-missions-products')
router.register('notifications', NotificationViewSet, basename='notifications')
router.register('home/customer/search', CustomerHomeSearchViewSet, basename='customer-home-search'),
router.register('campaigns/user_data/(?P<code>\w+)/(?P<question_id>\w+)/file', CampaignUserDataFileViewSet, basename='campaign-user-data-file'),
router.register('campaigns/user_data', CampaignUserDataViewSet, basename='campaign-user-data'),
router.register('campaigns', CampaignViewSet, basename='campaigns'),

api_urlpatterns = [
    path('api/auth/password_reset/validate_token/', reset_password_validate_token, name="reset-password-validate"),
    path('api/auth/password_reset/confirm/', reset_password_confirm, name="reset-password-confirm"),
    path('api/auth/password_reset/', reset_password_request_token, name="reset-password-request"),
    path('api/auth/device/logout/', DeviceLogoutView.as_view(), name='device-logout'),
    path('api/auth/social/', SocialAuthTokenObtainPairView.as_view(), name='social_token_obtain_pair'),
    path('api/auth/refresh/', AuthTokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/verify/', AuthTokenVerifyView.as_view(), name='token_verify'),
    path('api/auth/web/', WebAuthTokenObtainPairView.as_view(), name='web-token-obtain-pair'),
    path('api/auth/helper/', HelperTokenTemporaryViewSet.as_view(), name='helper-token-temporary'),
    path('api/helpers/temporary/', HelperInformationTemporaryViewSet.as_view(), name='helper-temporary'),
    path('api/missions/bids/helper/temporary/done/', HelperTemporaryBidsViewSet.as_view({'get': 'done'}), name='helper-missions-bid-temporary'),
    path('api/auth/', AuthTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/external/auth/', ExternalAuthTokenObtainPairView.as_view(), name='external-token_obtain_pair'),
    path('api/home/customer/', CustomerHomeView.as_view(), name='customer-home'),
    path('api/', include(router.urls)),
]

schema_view = get_schema_view(
    openapi.Info(
        title="Anyman API",
        default_version='v1',
        description="Anyman API Specification - Swagger",
    ),
    public=True,
    # permission_classes=(permissions.IsAdminUser,),
    permission_classes=(permissions.AllowAny,),
    patterns=api_urlpatterns,
)

main_urlpatterns = [
    path('api/explore/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/spec<str:format>', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('api/doc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('admin/', admin.site.urls),
    path('summernote/', include('django_summernote.urls')),
    path('webhook/callback/', WebhookCallbackView.as_view({'post': 'create'}), name='webhook-callback'),

    # 외부 연결
    # path('b/<int:id>/', campaign.BannerView.as_view(), name='campaign-banner'),
    path('link/<str:code>/<int:id>/', PopupLinkView.as_view(), name='popup-link'),
    path('l/<int:id>/<str:code>/', BannerLinkView.as_view(), name='campaign-banner-link'),
    path('l/<int:id>/', BannerLinkView.as_view(), name='campaign-banner-link'),
    path('e/<slug:shortened>/', shorten_url_redirect_view, name='shortened-url-redirect'),
    path('t/<slug:shortened>/', shorten_web_url_redirect_view, name='shortened-web-url-redirect'),

    path('accounts/ci/', NiceCIView.as_view(), name='ci-start'),
    path('accounts/ci/success/', NiceCISuccessView.as_view(), name='ci-success'),
    path('accounts/ci/fail/', NiceCIFailView.as_view(), name='ci-fail'),
    path('payment/transaction/<int:bid_id>/', TransactionView.as_view(), name='payments-transaction'),
    path('payment/external/<int:bid_id>/', ExternalPaymentView.as_view(), name='external-payments-callback'),
    path('favicon.ico', RedirectView.as_view(url='/static/images/favicon.ico')),
    # path('', MainView.as_view(), name='main'),
    path('', RedirectView.as_view(url='https://www.anyman.co.kr/'), name='main'),
    path('template/<int:template_id>/<str:template_name>/', WebTemplateView.as_view(), name='web-template'),
    # path('mission/<str:code>/', WebMissionView.as_view(), name='web-mission')
]


"""
애니비즈 api
"""


from biz.views.api import BizAuthTokenObtainPairView, BizMissionViewSet, BizTemplateViewSet


biz_router = DefaultRouter()
biz_router.register('missions', BizMissionViewSet, basename='biz-missions')
biz_router.register('templates', BizTemplateViewSet, basename='biz-templates')

biz_api_urlpatterns = [
    path('api/v1/auth/', BizAuthTokenObtainPairView.as_view(), name='biz-auth-token_obtain_pair'),
    path('api/v1/', include(biz_router.urls)),
]

biz_schema_view = get_schema_view(
    openapi.Info(
        title="Anybiz API",
        default_version='v1',
        description="Anybiz API Specification\n--------------------\n애니비즈 협력사 공통 api 모듈 스펙입니다.\n요청에 필요한 상세 데이터는 협력사마다 구조가 다르며, 이에 대한 문의사항이 있는 경우 애니맨으로 연락 바랍니다.\n1. 인증 요청\n>> - 우선 /api/v1/auth/ 에 POST 요청으로 인증을 해서 토큰을 발급받아야 합니다.\n>> - 인증에 필요한 code와 secret은 사전에 메일로 전달드립니다.\n>> - 요청을 통해 받은 access 토큰을 헤더에 추가하여 미션 요청 등 인증이 필요한 요청에 사용합니다.\n>> - 요청을 통해 받은 access token은 24시간동안 유효하며, 만료 이후에는 다시 인증을 요청해야 합니다. (refresh 토큰을 함께 발급하고 있으나, refresh 토큰을 통한 재인증은 현재 제공하지 않습니다.)\n>>> [헤더 추가 예시]\n>>> Authorization: Bearer &lt;access token&gt;\n2. 미션 요청\n>> - 미션을 발생시켜야 하는 경우 회원의 이름과 연락처, 그리고 사전에 협의된 데이터를 형식에 맞춰서 data에 넣어서 POST 요청합니다.\n>> - 요청 헤더에 반드시 액세스 토큰을 추가해서 요청해야 합니다.\n>> - template_id는 미션 종류에 따라서 값이 달라지며, 각 미션 종류의 id 값에 대해서는 메일로 안내합니다.",
    ),
    public=True,
    # permission_classes=(permissions.IsAdminUser,),
    permission_classes=(permissions.AllowAny,),
    patterns=biz_api_urlpatterns,
)

biz_urlpatterns = [
    path('api/v1/explore/', biz_schema_view.with_ui('swagger', cache_timeout=0), name='anybiz-schema-swagger-ui'),
    path('biz/', include('biz.urls')),
]


urlpatterns = biz_api_urlpatterns + api_urlpatterns + biz_urlpatterns + main_urlpatterns

if settings.DEBUG:
	if 'debug_toolbar' in settings.INSTALLED_APPS:
		import debug_toolbar
		urlpatterns.insert(0, path("__debug__/", include(debug_toolbar.urls)))

	from django.conf.urls.static import static
	from django.contrib.staticfiles.urls import staticfiles_urlpatterns

	urlpatterns.extend(
		staticfiles_urlpatterns()
		+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
	)
