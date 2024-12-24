"""Notification Server URL Configuration"""

from rest_framework.routers import DefaultRouter
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from django.views.generic import RedirectView

from notification.views import RelayNotificationViewSet
from missions.views import RelaySafetyNumberViewSet


router = DefaultRouter()
router.register('notification', RelayNotificationViewSet, basename='notification')
router.register('safety_number', RelaySafetyNumberViewSet, basename='safety_number')


api_urlpatterns = [
    path('api/', include(router.urls)),
]


schema_view = get_schema_view(
    openapi.Info(
        title="Anyman Relay API",
        default_version='v1',
        description="Anyman Relay API Specification - Swagger",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    patterns=api_urlpatterns,
)


urlpatterns = api_urlpatterns + [
    path('api/explore/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/spec<str:format>', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('api/doc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('admin/', admin.site.urls),
    path('favicon.ico', RedirectView.as_view(url='/static/images/favicon.ico')),
]


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
