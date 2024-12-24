from django.contrib import admin
from django.utils.safestring import mark_safe


from common.admin import (
    RelatedAdminMixin, ChangeFormSplitMixin, AdditionalAdminUrlsMixin, ImageWidgetMixin,
    log_with_reason
)
from common.views import ModelExportBaseView
from common.utils import BaseExcelImportConverter
from common.admin import AdminFilter
from base.models import Area
from base.constants import MISSION_STATUS
from base.admin import BaseAdmin
from accounts.models import LoggedInDevice
from accounts.admin import UserCodeSearchMixin
from notification.models import Notification
from .models import ExternalMission, ExternalMissionProduct



@admin.register(ExternalMission)
class ExternalMissionAdmin(BaseAdmin):
    """
    외부요청 미션 어드민
    """
    list_display = ('get_mission_display', 'mission_type', 'get_excpected_cost_display', 'get_product_summary')

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def get_mission_display(self, obj):
        if obj._mission:
            prefix = '<i class="fa fa-lg fa-user%s text-secondary"></i> ' % ('s' if obj.multi_mission else '')
            return mark_safe(prefix + str(obj._mission))
        else:
            return '- 미션 변환 실패 -'
    get_mission_display.short_description = '미션'

    def get_excpected_cost_display(self, obj):
        if 'expected_min_cost' in obj.data and 'expected_max_cost' in obj.data:
            return '%s ~ %s' % (obj.data['expected_min_cost'], obj.data['expected_max_cost'])
        return ''
    get_excpected_cost_display.short_description = '예상수행비용'

    def get_product_summary(self, obj):
        try:
            return ['%s * %s' % (i['itemId'], i['quantity']) for i in obj.data['items']]
        except:
            return ''
    get_product_summary.short_description = '제품요약'
