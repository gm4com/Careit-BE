from collections import Counter
from collections import OrderedDict
import statistics

from django.template import Library
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count, F, Q
from django.db.models.functions import Length, Concat
from django.utils import timezone
from django.core.cache import cache

from common.utils import add_comma
from common.admin import ChartDataBase, MultiLineChart, ChartDashboard
from base.constants import MISSION_STATUS
from accounts.models import User, Helper, LoggedInDevice, ServiceBlock
from missions.models import Mission, Bid, Interaction, Review, Report
from payment.models import PointVoucher, Cash, Point, Payment, Withdraw
from notification.models import Notification


register = Library()


@register.simple_tag
def view_active_user_count():
    return add_comma(User.objects.filter(
        is_active=True, _is_service_blocked=False, withdrew_datetime__isnull=True
    ).count())


@register.simple_tag
def view_active_helper_count():
    return add_comma(Helper.objects.get_active_helpers().count())


@register.simple_tag
def view_logged_in_device_count():
    return add_comma(LoggedInDevice.objects.get_logged_in().count())


@register.simple_tag
def view_mission_done_count():
    return add_comma(Mission.objects.get_queryset().done().count())


@register.simple_tag
def view_mission_in_bidding_count():
    return add_comma(Mission.objects.get_queryset().in_bidding().count())


@register.simple_tag
def view_mission_in_action_count():
    return add_comma(Mission.objects.get_queryset().in_action().count())


@register.simple_tag
def view_cash_balance():
    cashes = Cash.objects.filter(
        helper__user__is_active=True, helper__user___is_service_blocked=False, helper__user__withdrew_datetime__isnull=True,
        helper__accepted_datetime__isnull=False, helper__is_active=True
    ).order_by('helper_id', '-id').distinct('helper_id').values_list('balance', flat=True)
    withdrawable = [c for c in cashes if c >= 10000]
    return mark_safe(add_comma(sum(cashes)) + '<br/><small>(인출가능 ' + add_comma(sum(withdrawable)) + ')</small>')

@register.simple_tag
def view_point_balance():
    points = Point.objects.filter(
        user__is_active=True, user___is_service_blocked=False, user__withdrew_datetime__isnull=True,
    ).order_by('user_id', '-id').distinct('user_id').values_list('balance', flat=True)
    usable = [(c // 1000) * 1000 for c in points if c >= 1000]
    return mark_safe(add_comma(sum(points)) + '<br/><small>(사용가능 ' + add_comma(sum(usable)) + ')</small>')


"""
통계
"""


class UserDailyChart(MultiLineChart):
    """
    회원 차트
    """
    model = User
    chart_class = 'col-12'
    # table_class = 'col-12'
    # sub_chart_class = 'col-6 mt-5'
    sub_table_class = 'col-12'
    # description_class = 'col-6'

    def get_entries(self):
        return {
            'total': {
                'label': '회원 가입',
                'color': '#ffcb18',
                'query': self.get_queryset().values('created_datetime__date') \
                    .annotate(user_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'user_count')
            },
            'recommended': {
                'label': '추천 가입 회원',
                'color': '#996600',
                'query': self.get_queryset().filter(recommended_user__isnull=False) \
                    .values('created_datetime__date') \
                    .annotate(user_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'user_count')
            },
            'paid_users': {
                'label': '전환 회원 (CV)',
                'color': '#ccaa00',
                'query': self.get_queryset().filter(missions__bids__payment__is_succeeded=True) \
                    .values('created_datetime__date') \
                    .annotate(user_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'user_count')
            },
            'helper_requested': {
                'label': '헬퍼 신청',
                'color': '#0d5aa7',
                'query': self.get_queryset(Helper, 'requested_datetime') \
                    .values('requested_datetime__date') \
                    .annotate(requested_count=Count('requested_datetime__date')) \
                    .order_by('requested_datetime__date') \
                    .values_list('requested_datetime__date', 'requested_count')
            },
            'helper_accepted': {
                'label': '헬퍼 승인',
                'color': '#008a00',
                'query': self.get_queryset(Helper, 'accepted_datetime') \
                    .values('accepted_datetime__date') \
                    .annotate(accepted_count=Count('accepted_datetime__date')) \
                    .order_by('accepted_datetime__date') \
                    .values_list('accepted_datetime__date', 'accepted_count')
            },
            'helper_mission_completed': {
                'label': '미션수행 헬퍼',
                'color': '#004a00',
                'query': self.get_queryset(Helper, 'accepted_datetime') \
                    .filter(bids__saved_state='done') \
                    .values('accepted_datetime__date') \
                    .annotate(accepted_count=Count('accepted_datetime__date')) \
                    .order_by('accepted_datetime__date') \
                    .values_list('accepted_datetime__date', 'accepted_count')
            },
            'blocked': {
                'label': '계정 블록',
                'color': '#e51400',
                'query': self.get_queryset(ServiceBlock, 'start_datetime') \
                    .values('start_datetime__date') \
                    .annotate(start_count=Count('start_datetime__date')) \
                    .order_by('start_datetime__date') \
                    .values_list('start_datetime__date', 'start_count')
            },
            'withdrew': {
                'label': '회원 탈퇴',
                'color': '#999999',
                'query': self.get_queryset(User, 'withdrew_datetime') \
                    .values('withdrew_datetime__date') \
                    .annotate(withdrew_count=Count('withdrew_datetime__date')) \
                    .order_by('withdrew_datetime__date') \
                    .values_list('withdrew_datetime__date', 'withdrew_count')
            },
        }

    def get_sub_table_data(self):
        i = 0
        data = []
        sub_data = self.get_sub_chart_data()
        for label in sub_data['labels']:
            data.append((label, add_comma(sub_data['datasets'][0]['data'][i])))
            i += 1
        return {
            'title': '',
            'data': data
        }


class UserMissionDoneDailyChart(MultiLineChart):
    """
    미션 완료 회수별 회원수
    """
    model = User
    base_term_field = 'missions__bids___done_datetime'
    chart_class = ''
    sub_chart_class = 'col-8'
    sub_table_class = 'col-4'
    queryset = None
    count_data = {}
    type = 'pie'

    def get_queryset(self, model=None, term_field=None):
        qs = super(UserMissionDoneDailyChart, self).get_queryset(model=model, term_field=term_field)
        return qs.annotate(done_count=Count('id')) \
                    .values_list('done_count', flat=True)

    def handle_labels(self):
        self.labels = []
        self.queryset = self.get_queryset()
        count_data = {}
        for cnt in self.queryset:
            if cnt not in count_data:
                count_data[cnt] = 1
            else:
                count_data[cnt] += 1
        self.count_data = OrderedDict()
        for cnt in sorted(count_data.keys()):
            self.count_data[cnt] = count_data[cnt]
            self.labels.append('%s회' % cnt)

    def handle_data(self):
        # 데이터 정리
        self.datasets = []
        for label, cnt in self.count_data.items():
            self.datasets.append(self.make_dataset(
                label='%s회' % label,
                data=[cnt],
                one_color=self._get_count_label_color(label),
                type='pie'
            ))

    def _get_count_label_color(self, count_label):
        colors = ('#eee', '#ddd', '#ccc', '#bbb', '#aaa', '#999', '#888', '#777', '#666', '#555', '#444', '#333', '#222')
        return colors[(count_label - 1)] if count_label < 13 else colors[-1]


class HelperMissionDoneDailyChart(MultiLineChart):
    """
    미션 완료 회수별 헬퍼수
    """
    model = Helper
    base_term_field = 'bids___done_datetime'
    chart_class = ''
    sub_chart_class = 'col-8'
    sub_table_class = 'col-4'
    queryset = None
    count_data = {}
    type = 'pie'

    def get_queryset(self, model=None, term_field=None):
        qs = super(HelperMissionDoneDailyChart, self).get_queryset(model=model, term_field=term_field)
        return qs.annotate(done_count=Count('bids__mission_id')).values_list('done_count', flat=True)

    def handle_labels(self):
        self.labels = []
        self.queryset = [c for c in self.get_queryset() if c]
        count_data = {}
        for cnt in self.queryset:
            if cnt not in count_data:
                count_data[cnt] = 1
            else:
                count_data[cnt] += 1
        self.count_data = OrderedDict()
        for cnt in sorted(count_data.keys()):
            self.count_data[cnt] = count_data[cnt]
            self.labels.append('%s회' % cnt)

    def handle_data(self):
        # 데이터 정리
        self.datasets = []
        for label, cnt in self.count_data.items():
            self.datasets.append(self.make_dataset(
                label='%s회' % label,
                data=[cnt],
                one_color=self._get_count_label_color(label),
                type='pie'
            ))

    def _get_count_label_color(self, count_label):
        colors = ('#eee', '#ddd', '#ccc', '#bbb', '#aaa', '#999', '#888', '#777', '#666', '#555', '#444', '#333', '#222')
        return colors[(count_label - 1)] if count_label < 13 else colors[-1]


class FirstRequestDaysChart(MultiLineChart):
    """
    가입후 첫 미션요청까지 걸리는 기간
    """
    model = User
    queryset = None
    sub_chart_class = 'col-8'
    sub_table_class = 'col-4'
    type = 'pie'
    colors = ('#e55', '#d55', '#c55', '#b55', '#a55', '#955', '#855', '#755', '#655', '#555', '#455', '#355', '#255')

    def get_queryset(self, model=None, term_field=None):
        qs = super(FirstRequestDaysChart, self).get_queryset(model=model, term_field=term_field)
        qs = qs.annotate(requested_term=F('missions__requested_datetime') - F('created_datetime'))
        qs = qs.order_by('code', 'requested_term').values('code', 'requested_term').distinct('code')
        return qs

    def handle_labels(self):
        self.labels = []
        if self.queryset is None:
            self.queryset = Counter([(c['requested_term'].days if c['requested_term'] else -1) for c in self.get_queryset()])
            self.count_data = OrderedDict()
            for cnt in sorted(self.queryset.keys()):
                self.count_data[cnt] = self.queryset[cnt]

    def handle_data(self):
        self.datasets = []
        i = 0
        for label, cnt in self.count_data.items():
            if label == -1:
                label = '미션요청 없음'
            elif label == 0:
                label = '가입당일'
            else:
                label = '%s일후' % label
            self.datasets.append(self.make_dataset(
                label=label,
                data=[cnt],
                one_color=self.colors[i] if i < len(self.colors) else self.colors[-1],
                type='pie'
            ))
            i += 1


class DeviceChart(MultiLineChart):
    """
    접속 단말기
    """
    model = LoggedInDevice
    base_term_field = 'logged_in_datetime'
    chart_class = ''
    sub_chart_class = 'col-8'
    sub_table_class = 'col-4'
    description_class = 'col-12'
    description_data = {}
    queryset = None
    count_data = {}
    type = 'pie'
    colors_apple = ('#e55', '#d55', '#c55', '#b55', '#a55', '#955', '#855', '#755', '#655', '#555', '#455', '#355', '#255')
    colors_samsung = ('#55e', '#55d', '#55c', '#55b', '#55a', '#559', '#558', '#557', '#556', '#555', '#554', '#553', '#552')
    colors_etc = ('#5e5', '#5d5', '#5c5', '#5b5', '#5a5', '#595', '#585', '#575', '#565', '#555', '#545', '#535', '#525')

    def get_queryset(self, model=None, term_field=None):
        qs = super(DeviceChart, self).get_queryset(model=model, term_field=term_field)
        qs = qs.values('device_info__model', 'device_info__manufacturer')\
            .annotate(count=Count('device_info__model')).order_by('-count')
        return qs

    def handle_labels(self):
        self.labels = []
        if self.queryset is None:
            self.count_data = OrderedDict()
            self.description_data = {
                'Apple': [],
                'samsung': [],
                'etc': []
            }
            self.queryset = [c for c in self.get_queryset() if c]
            for q in self.queryset:
                if q['device_info__model']:
                    if q['device_info__manufacturer'] in self.count_data:
                        self.count_data[q['device_info__manufacturer']] += q['count']
                    else:
                        self.count_data[q['device_info__manufacturer']] = q['count']
                    if q['device_info__manufacturer'] in self.description_data:
                        self.description_data[q['device_info__manufacturer']].append((q['device_info__model'], q['count']))
                    else:
                        self.description_data['etc'].append((q['device_info__manufacturer'] + ' ' + q['device_info__model'], q['count']))

    def handle_data(self):
        # 데이터 정리
        self.datasets = []
        apple_cnt = 0
        samsung_cnt = 0
        etc_cnt = 0
        for label, cnt in self.count_data.items():
            if label.lower().startswith('apple'):
                color = self.colors_apple[apple_cnt] if apple_cnt < len(self.colors_apple) else self.colors_apple[-1]
                apple_cnt += 1
            elif label.lower().startswith('samsung'):
                color = self.colors_samsung[samsung_cnt] if samsung_cnt < len(self.colors_samsung) else self.colors_samsung[-1]
                samsung_cnt += 1
            else:
                color = self.colors_etc[etc_cnt] if etc_cnt < len(self.colors_etc) else self.colors_etc[-1]
                etc_cnt += 1

            self.datasets.append(self.make_dataset(
                label=label,
                data=[cnt],
                one_color=color,
                type='pie'
            ))

    def get_description(self):
        html = '<div class="jumbotron"><div class="row"><div class="col-4">%s</div><div class="col-4">%s</div><div class="col-4">%s</div></div></div>'
        table_1 = '<h5 class="text-center">Apple</h5><table class="table table-description table-striped"><tbody>%s</tbody></table>'
        table_2 = '<h5 class="text-center">Samsung</h5><table class="table table-description table-striped"><tbody>%s</tbody></table>'
        table_3 = '<h5 class="text-center">기타</h5><table class="table table-description table-striped"><tbody>%s</tbody></table>'
        row = '<tr><td>%s</td><th>%s</th></tr>%%s'
        for item in self.description_data['Apple']:
            table_1 = table_1 % row % (item[1], item[0])
        for item in self.description_data['samsung']:
            table_2 = table_2 % row % (item[1], item[0])
        for item in self.description_data['etc']:
            table_3 = table_3 % row % (item[1], item[0])
        return html % (table_1 % '', table_2 % '', table_3 % '')


class AppChart(MultiLineChart):
    """
    앱 버젼
    """
    model = LoggedInDevice
    base_term_field = 'logged_in_datetime'
    chart_class = ''
    sub_chart_class = 'col-8'
    sub_table_class = 'col-4'
    queryset = None
    count_data = {}
    type = 'pie'
    colors = ('#e5e', '#d5d', '#c5c', '#b5b', '#a5a', '#959', '#858', '#757', '#656', '#555', '#454', '#353', '#252')

    def get_queryset(self, model=None, term_field=None):
        qs = super(AppChart, self).get_queryset(model=model, term_field=term_field)
        qs = qs.order_by('-app_info__versionCode') \
            .values('app_info__versionNumber') \
            .annotate(count=Count('app_info__versionNumber'))
        return qs

    def handle_labels(self):
        self.labels = []
        self.count_data = OrderedDict()
        if self.queryset is None:
            self.queryset = [c for c in self.get_queryset() if c]
            for q in self.queryset:
                if q['app_info__versionNumber'] in self.count_data:
                    self.count_data[q['app_info__versionNumber']] += q['count']
                else:
                    self.count_data[q['app_info__versionNumber']] = q['count']

    def handle_data(self):
        # 데이터 정리
        self.datasets = []
        i = 0
        for label, cnt in self.count_data.items():
            self.datasets.append(self.make_dataset(
                label=label,
                data=[cnt],
                one_color=self.colors[i] if i < len(self.colors) else self.colors[-1],
                type='pie'
            ))
            i += 1


class MissionDailyChart(MultiLineChart):
    """
    미션 건수 차트
    """
    model = Mission
    base_term_field = 'requested_datetime'
    MISSION_STATUS_COLORS = {
        # 'total': '#d80073',
        # 'done_requested': '#6a00ff',
        # 'failed': '#76608a',
        # 'applied': '#1ba1e2',
        # 'not_applied': '#825a2c',
        # 'bidding': '#0050ef',
        # 'waiting_assignee': '#f472d0',
        'in_action': '#f0a30a',
        'done': '#008a00',
        'admin_canceled': '#642c28',
        'user_canceled': '#ff702a',
        'timeout_canceled': '#ad4d52',
        'won_and_canceled': '#e51400',
        'done_and_canceled': '#a92f26',
        'mission_deactivated': '#555555',
        'unknown': '#999999',
        'requested': '#fea',
    }
    chart_class = 'col-12'
    # table_class = 'col-12'
    sub_chart_class = 'col-6 mt-5'
    sub_table_class = 'col-6'
    # description_class = 'col-6'

    def get_context(self):
        context = super(MissionDailyChart, self).get_context()
        if len(self.labels) == 1:
            context['sub_chart_class'] = ''
            context['sub_table_class'] = 'col-12'
        return context

    def handle_data(self):
        # 쿼리
        all_requested_qs = self.get_queryset().values('requested_datetime__date') \
            .annotate(requested_count=Count('requested_datetime__date')) \
            .order_by('requested_datetime__date') \
            .values_list('requested_datetime__date', 'requested_count')
        qs = self.get_queryset().values('requested_datetime__date', 'saved_state') \
            .annotate(state_count=Count('saved_state'))\
            .order_by('requested_datetime__date')\
            .values_list('requested_datetime__date', 'saved_state', 'state_count')

        # 데이터 채워넣기
        label_cnt = len(self.labels)
        pre_data = self.get_initialized_data_dict(
            label_cnt + 1,
            'bidding', 'done', 'done_and_canceled', 'admin_canceled', 'user_canceled', 'timeout_canceled',
            'won_and_canceled', 'bid_and_canceled', 'in_action', 'done_requested', 'failed', 'applied', 'not_applied',
            'mission_deactivated', 'waiting_assignee', 'unknown', 'requested'
        )

        # 데이터 정리
        self.datasets = []
        base_type = 'bar' if label_cnt == 1 else 'line'
        state_labels = dict(MISSION_STATUS)
        state_labels.update({'requested': '전체 요청'})

        for state, color in self.MISSION_STATUS_COLORS.items():
            # 쿼리 데이터 업데이트
            if state == 'requested':
                for r in all_requested_qs:
                    i = self.labels.index(r[0].strftime('%m-%d'))
                    pre_data['requested'][i] = r[1]
            else:
                for r in qs:
                    i = self.labels.index(r[0].strftime('%m-%d'))
                    pre_data[r[1]][i] = r[2]

            # 데이터셋에 추가
            self.datasets.append(self.make_dataset(
                label=state_labels[state],
                data=pre_data[state],
                one_color=color,
                type='bar' if state == 'requested' else base_type
            ))

    def get_sub_chart_data(self):
        sub_chart_data = super(MissionDailyChart, self).get_sub_chart_data()
        sub_chart_data['labels'] = sub_chart_data['labels'][:-1]
        sub_chart_data['datasets'][0]['data'] = sub_chart_data['datasets'][0]['data'][:-1]
        return sub_chart_data


class FirstDoneMissionDailyChart(MultiLineChart):
    """
    첫 완료미션 건수 차트
    """
    model = Bid
    base_term_field = '_done_datetime'
    chart_class = 'col-12'
    sub_chart_class = 'col-6'
    sub_table_class = 'col-6'

    def get_context(self):
        context = super(FirstDoneMissionDailyChart, self).get_context()
        if len(self.labels) == 1:
            context['sub_chart_class'] = ''
            context['sub_table_class'] = 'col-12'
        return context

    def get_entries(self):
        qs = self.get_queryset().filter(saved_state__code='done', mission_id__isnull=False)
        return {
            'first_done_count': {
                'label': '최초 완료 미션',
                'color': '#f0a30a',
                'query': qs.values('_done_datetime__date') \
                    .annotate(done_count=Count('_done_datetime__date')) \
                    .order_by('_done_datetime__date') \
                    .values_list('_done_datetime__date', 'done_count')
            },
            'not_first_count': {
                'label': '다회째 완료 미션',
                'color': '#c09300',
                'query': qs.filter(mission__user__missions__bids__saved_state__code='done', mission__user__missions__bids___done_datetime__gt=F('_done_datetime')) \
                    .values('_done_datetime__date') \
                    .annotate(not_first_count=Count('_done_datetime__date', distinct=True)) \
                    .values_list('_done_datetime__date', 'not_first_count'),
            }
        }

    def handle_data(self):
        super(FirstDoneMissionDailyChart, self).handle_data()
        self.datasets[0]['data'] = [x - y for x, y in zip(self.datasets[0]['data'], self.datasets[1]['data'])]


class BidDailyChart(MultiLineChart):
    """
    입찰 건수 차트
    """
    model = Bid
    base_term_field = 'applied_datetime'
    MISSION_STATUS_COLORS = {
        # 'total': '#d80073',
        'done_requested': '#6a00ff',
        'failed': '#76608a',
        'applied': '#1ba1e2',
        'not_applied': '#825a2c',
        'bidding': '#0050ef',
        'waiting_assignee': '#f472d0',
        'mission_deactivated': '#a20025',
        'in_action': '#f0a30a',
        'done': '#008a00',
        'admin_canceled': '#642c28',
        'user_canceled': '#ff702a',
        'timeout_canceled': '#ad4d52',
        'won_and_canceled': '#e51400',
        'done_and_canceled': '#a92f26',
        'unknown': '#999999',
        'bidded': '#aef',
    }
    chart_class = 'col-12'
    # table_class = 'col-12'
    sub_chart_class = 'col-6 mt-5'
    sub_table_class = 'col-6'
    # description_class = 'col-6'

    def get_context(self):
        context = super(BidDailyChart, self).get_context()
        if len(self.labels) == 1:
            context['sub_chart_class'] = ''
            context['sub_table_class'] = 'col-12'
        return context

    def handle_data(self):
        # 쿼리
        all_bidded_qs = self.get_queryset().values('applied_datetime__date') \
            .annotate(bidded_count=Count('applied_datetime__date')) \
            .order_by('applied_datetime__date') \
            .values_list('applied_datetime__date', 'bidded_count')
        qs = self.get_queryset().values('applied_datetime__date', 'saved_state')\
            .annotate(state_count=Count('saved_state'))\
            .order_by('applied_datetime__date')\
            .values_list('applied_datetime__date', 'saved_state', 'state_count')

        # 데이터 채워넣기
        label_cnt = len(self.labels)
        pre_data = self.get_initialized_data_dict(
            label_cnt,
            'bidding', 'done', 'done_and_canceled', 'admin_canceled', 'user_canceled', 'timeout_canceled',
            'won_and_canceled', 'bid_and_canceled', 'in_action', 'done_requested', 'failed', 'applied', 'not_applied',
            'mission_deactivated', 'waiting_assignee', 'unknown', 'bidded'
        )

        # 데이터 정리
        self.datasets = []
        base_type = 'bar' if label_cnt == 1 else 'line'
        state_labels = dict(MISSION_STATUS)
        state_labels.update({'bidded': '전체 입찰'})

        for state, color in self.MISSION_STATUS_COLORS.items():
            # 쿼리 데이터 업데이트
            if state == 'bidded':
                for r in all_bidded_qs:
                    i = self.labels.index(r[0].strftime('%m-%d'))
                    pre_data['bidded'][i] = r[1]
            else:
                for r in qs:
                    i = self.labels.index(r[0].strftime('%m-%d'))
                    pre_data[r[1]][i] = r[2]

            # 데이터셋에 추가
            self.datasets.append(self.make_dataset(
                label=state_labels[state],
                data=pre_data[state],
                one_color=color,
                type = 'bar' if state == 'bidded' else base_type
            ))

    def get_sub_chart_data(self):
        sub_chart_data = super(BidDailyChart, self).get_sub_chart_data()
        sub_chart_data['labels'] = sub_chart_data['labels'][:-1]
        sub_chart_data['datasets'][0]['data'] = sub_chart_data['datasets'][0]['data'][:-1]
        return sub_chart_data


class MissionBidCountDailyChart(MultiLineChart):
    """
    입철수 별 미션 건수
    """
    model = Mission
    base_term_field = 'requested_datetime'
    chart_class = ''
    sub_chart_class = 'col-8'
    sub_table_class = 'col-4'
    queryset = None
    count_data = {}
    type = 'pie'

    def get_queryset(self, model=None, term_field=None):
        qs = super(MissionBidCountDailyChart, self).get_queryset(model=model, term_field=term_field)
        return qs.annotate(bid_count=Count('bids__applied_datetime')) \
                    .values_list('bid_count', flat=True)

    def handle_labels(self):
        self.labels = []
        self.queryset = self.get_queryset()
        count_data = {}
        for cnt in self.queryset:
            if cnt not in count_data:
                count_data[cnt] = 1
            else:
                count_data[cnt] += 1
        self.count_data = OrderedDict()
        for cnt in sorted(count_data.keys()):
            self.count_data[cnt] = count_data[cnt]
            self.labels.append('%s회' % cnt)

    def handle_data(self):
        # 데이터 정리
        self.datasets = []
        for label, cnt in self.count_data.items():
            self.datasets.append(self.make_dataset(
                label='%s회' % label,
                data=[cnt],
                one_color=self._get_count_label_color(label),
                type='pie'
            ))

    def _get_count_label_color(self, count_label):
        colors = ('#f5f5f5', '#eee', '#ddd', '#ccc', '#bbb', '#aaa', '#999', '#888', '#777', '#666', '#555', '#444', '#333', '#222', '#111', '#000')
        return colors[count_label] if count_label < 16 else colors[-1]


class BiddingMissionCanceledDetailDailyChart(MultiLineChart):
    """
    매칭전 미션 취소 사유 차트
    """
    model = Mission
    chart_class = 'col-12'
    sub_table_class = 'col-12'
    base_term_field = 'canceled_datetime'
    type = 'pie'
    options = 'null'

    def get_queryset(self, model=None, term_field=None):
        qs = super(BiddingMissionCanceledDetailDailyChart, self).get_queryset(model, term_field)
        qs = qs.exclude(canceled_detail='')
        return qs.values('canceled_detail').annotate(detail_count=Count('canceled_detail'))\
            .order_by('-detail_count').values_list('canceled_detail', 'detail_count')

    def handle_labels(self):
        self.labels = []
        self.count_data = []
        self.sub_table_count_data = []

        timeout_cnt = super(BiddingMissionCanceledDetailDailyChart, self).get_queryset(term_field='bid_limit_datetime') \
                      .filter(saved_state='timeout_canceled').count()
        last = 99999999

        for label, cnt in self.get_queryset():
            if last > timeout_cnt >= cnt:
                self.labels.append('시간초과 자동취소')
                self.count_data.append(timeout_cnt)
            last = cnt

            if cnt > 1:
                self.labels.append(label)
                self.count_data.append(cnt)
            else:
                if self.labels[-1] != '기타':
                    self.labels.append('기타')
                    self.count_data.append(0)
                self.count_data[-1] += cnt
                self.sub_table_count_data.append((label, cnt))

        # 취소사유가 아예 없는 경우 표시가 아예 없는 것에 대한 방어코드
        if not self.labels and timeout_cnt:
            self.labels.append('시간초과 자동취소')
            self.count_data.append(timeout_cnt)

    def handle_data(self):
        self.datasets = []
        colors = ['#ff2100', '#e51400', '#d50700', '#c50000', '#b50000', '#a50000', '#950000', '#850000',
                  '#750000', '#650000', '#550000',]
        if len(self.count_data) > len(colors):
            colors += [colors[-1]] * (len(self.count_data) - len(colors))
        if self.labels and self.labels[-1] == '기타':
            colors = colors[:len(self.count_data)-1] + ['#aaaaaa']
        kwargs = {
            'label': self.labels,
            'data': self.count_data,
            'backgroundColor': colors
        }
        self.datasets.append(self.make_dataset(**kwargs))

    def get_sub_table_data(self):
        return {
            'title': '기타 사유' if self.sub_table_count_data else '',
            'data': self.sub_table_count_data
        }


class InActionMissionCanceledDetailDailyChart(MultiLineChart):
    """
    수행중 미션 취소 사유 차트
    """
    model = Interaction
    chart_class = 'col-12'
    sub_table_class = 'col-12'
    base_term_field = 'accepted_datetime'
    type = 'pie'
    options = 'null'

    def get_queryset(self, model=None, term_field=None):
        qs = super(InActionMissionCanceledDetailDailyChart, self).get_queryset(model, term_field)
        qs = qs.filter(interaction_type=1).exclude(detail='')
        return qs.values('detail').annotate(detail_count=Count('detail'))\
            .order_by('-detail_count').values_list('detail', 'detail_count')

    def handle_labels(self):
        self.labels = []
        self.count_data = []
        self.sub_table_count_data = []

        for label, cnt in self.get_queryset():
            if cnt > 1:
                self.labels.append(label)
                self.count_data.append(cnt)
            else:
                if not self.labels or self.labels[-1] != '기타':
                    self.labels.append('기타')
                    self.count_data.append(0)
                self.count_data[-1] += cnt
                self.sub_table_count_data.append((label, cnt))

    def handle_data(self):
        self.datasets = []
        colors = ['#ff2100', '#e51400', '#d50700', '#c50000', '#b50000', '#a50000', '#950000', '#850000',
                  '#750000', '#650000', '#550000',]
        if len(self.count_data) > len(colors):
            colors += [colors[-1]] * (len(self.count_data) - len(colors))
        if self.labels and self.labels[-1] == '기타':
            colors = colors[:len(self.count_data)-1] + ['#aaaaaa']
        kwargs = {
            'label': self.labels,
            'data': self.count_data,
            'backgroundColor': colors
        }
        self.datasets.append(self.make_dataset(**kwargs))

    def get_sub_table_data(self):
        return {
            'title': '기타 사유' if self.sub_table_count_data else '',
            'data': self.sub_table_count_data
        }


class MissionCanceledUserDailyChart(MultiLineChart):
    """
    수행중 미션 취소 주체 차트
    """
    model = Interaction
    base_term_field = 'accepted_datetime'
    chart_class = 'col-12'

    def get_queryset(self, model=None, term_field=None):
        qs = super(MissionCanceledUserDailyChart, self).get_queryset(model, term_field)
        # return qs.filter(done_datetime__isnull=True, won_datetime__isnull=False, _canceled_datetime__isnull=False)
        return qs.filter(interaction_type=1)

    def get_entries(self):
        return {
            'by_customer': {
                'label': '고객',
                'color': '#ffcb18',
                'query': self.get_queryset().filter(created_user_id=F('bid__mission__user_id')) \
                    .values('accepted_datetime__date') \
                    .annotate(canceled_count=Count('accepted_datetime__date')) \
                    .order_by('accepted_datetime__date') \
                    .values_list('accepted_datetime__date', 'canceled_count')
            },
            'by_helper': {
                'label': '헬퍼',
                'color': '#0d5aa7',
                'query': self.get_queryset().filter(created_user_id=F('bid__helper__user_id')) \
                    .values('accepted_datetime__date') \
                    .annotate(canceled_count=Count('accepted_datetime__date')) \
                    .order_by('accepted_datetime__date') \
                    .values_list('accepted_datetime__date', 'canceled_count')
            },
            'by_admin': {
                'label': '관리자',
                'color': '#008a00',
                'query': Bid.objects.filter(_done_datetime__isnull=True, won_datetime__isnull=False,
                                            _canceled_by_admin=True, _canceled_datetime__range=(self.start, self.end)) \
                    .values('_canceled_datetime__date') \
                    .annotate(canceled_count=Count('_canceled_datetime__date')) \
                    .order_by('_canceled_datetime__date') \
                    .values_list('_canceled_datetime__date', 'canceled_count')
            },
        }


class ReviewDailyChart(MultiLineChart):
    """
    리뷰 건수 차트
    """
    model = Review
    chart_class = 'col-12'

    def get_entries(self):
        entries = {
            'customer_review': {
                'label': '고객 리뷰',
                'color': '#ffcb18',
                'type': 'line',
                'query': self.get_queryset().filter(_is_created_user_helper=True)
                    .values('created_datetime__date') \
                    .annotate(review_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'review_count')
            },
            'helper_review': {
                'label': '헬퍼 리뷰',
                'color': '#0d5aa7',
                'type': 'line',
                'query': self.get_queryset().filter(_is_created_user_helper=False)
                    .values('created_datetime__date') \
                    .annotate(review_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'review_count')
            },
            'review': {
                'label': '전체 리뷰',
                'color': '#afa',
                'type': 'bar',
                'query': self.get_queryset().values('created_datetime__date') \
                    .annotate(review_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'review_count')
            },
        }
        if len(self.labels) == 1:
            entries.pop('review')
            entries['customer_review']['type'] = 'bar'
            entries['helper_review']['type'] = 'bar'
        return entries


class ReportChart(MultiLineChart):
    """
    신고내용 차트
    """
    model = Report
    chart_class = 'col-12'
    sub_table_class = 'col-12'
    type = 'pie'
    options = 'null'

    def get_queryset(self, model=None, term_field=None):
        qs = super(ReportChart, self).get_queryset(model, term_field)
        return qs.values('content').annotate(content_count=Count('content'))\
            .order_by('-content_count').values_list('content', 'content_count')

    def handle_labels(self):
        self.labels = ['불법미션(대리처방, 문서 위조 등)', '부적절한 언어(욕설, 성희롱)', '허위미션(홍보,낚시, 도배 등)', '기타']

    def handle_data(self):
        self.datasets = []
        data = [0] * 4
        # self.etc = []
        for label, cnt in self.get_queryset():
            if label in self.labels:
                data[self.labels.index(label)] += cnt
            else:
                data[-1] += cnt
                # self.etc.append(label)
        kwargs = {
            'label': self.labels,
            'data': data,
            'backgroundColor': ['#e51400', '#ff702a', '#ad4d52', '#642c28']
        }
        self.datasets.append(self.make_dataset(**kwargs))

    def get_sub_table_data(self):
        return {
            'title': add_comma(sum(self.datasets[0]['data'])),
            # 'data': self.etc
            'data': []
        }


class PaymentDailyChart(MultiLineChart):
    """
    결제내역 차트
    """
    model = Payment
    chart_class = 'col-12'
    sub_chart_class = 'col-6'
    sub_table_class = 'col-6'

    def get_context(self):
        context = super(PaymentDailyChart, self).get_context()
        if len(self.labels) == 1:
            context['sub_chart_class'] = ''
            context['sub_table_class'] = 'col-12'
        return context

    def get_entries(self):
        return {
            'succeeded': {
                'label': '전액 카드 결제',
                'color': '#0050ef',
                'query': self.get_queryset().filter(pay_method__in=('Card', 'CARD'), is_succeeded=True, amount__gt=0).exclude(point__amount__lt=0)
                    .values('created_datetime__date') \
                    .annotate(paid_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'paid_count')
            },
            'card_point': {
                'label': '카드 + 포인트 결제',
                'color': '#f0a30a',
                'query': self.get_queryset().filter(pay_method__in=('Card', 'CARD'), is_succeeded=True, amount__gt=0, point__amount__lt=0)
                    .values('created_datetime__date') \
                    .annotate(paid_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'paid_count')
            },
            'point_only': {
                'label': '전액 포인트 결제',
                'color': '#555555',
                'query': self.get_queryset().filter(pay_method__in=('Card', 'POINT'), is_succeeded=True, amount=0, authenticated_no='')
                    .values('created_datetime__date') \
                    .annotate(paid_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'paid_count')
            },
            'canceled': {
                'label': '결제 취소',
                'color': '#e51400',
                'query': self.get_queryset().filter(pay_method='Refund', is_succeeded=True, amount__lt=0)
                    .values('created_datetime__date') \
                    .annotate(canceled_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'canceled_count')
            },
        }

    def get_sub_table_data(self):
        rtn = super(PaymentDailyChart, self).get_sub_table_data()
        # rtn['title'] = int(rtn['title']) - self.data['datasets'][-1]
        data = self._sub_chart_data['datasets'][0]['data']
        rtn['title'] = self.unit_prefix + add_comma(sum(data[:-1]) - data[-1])
        return rtn


class PaymentSumDailyChart(PaymentDailyChart):
    """
    결제 금액 차트
    """
    unit_prefix = '￦'
    sub_chart_class = ''
    sub_table_class = 'col-12'

    def get_entries(self):
        return {
            'income': {
                'label': '순결제',
                'color': '#008a00',
                'query': self.get_queryset().filter(is_succeeded=True).exclude(amount=0)
                    .values('created_datetime__date') \
                    .annotate(paid=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'paid')
            },
            'succeeded': {
                'label': '전액 카드 결제',
                'color': '#0050ef',
                'query': self.get_queryset().filter(pay_method__in=('Card', 'CARD'), is_succeeded=True, amount__gt=0).exclude(point__amount__lt=0)
                    .values('created_datetime__date') \
                    .annotate(paid=Sum('bid__amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'paid')
            },
            'card_point': {
                'label': '카드 + 포인트 결제',
                'color': '#f0a30a',
                'query': self.get_queryset().filter(pay_method__in=('Card', 'CARD'), is_succeeded=True, amount__gt=0, point__amount__lt=0)
                    .values('created_datetime__date') \
                    .annotate(paid=Sum('bid__amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'paid')
            },
            'point_only': {
                'label': '전액 포인트 결제',
                'color': '#555555',
                'query': self.get_queryset().filter(pay_method__in=('Card', 'POINT'), is_succeeded=True, amount=0, authenticated_no='')
                    .values('created_datetime__date') \
                    .annotate(paid=Sum('bid__amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'paid')
            },
            'canceled': {
                'label': '결제 취소',
                'color': '#e51400',
                'query': self.get_queryset().filter(pay_method='Refund', is_succeeded=True, amount__lt=0)
                    .values('created_datetime__date') \
                    .annotate(canceled=Sum('bid__amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'canceled')
            },
        }

    def get_sub_table_data(self):
        rtn = super(PaymentDailyChart, self).get_sub_table_data()
        rtn['title'] = self.unit_prefix + add_comma(self._sub_chart_data['datasets'][0]['data'][0])
        return rtn


class VoucherDailyChart(MultiLineChart):
    """
    포인트 상품권 차트
    """
    model = PointVoucher
    chart_class = 'col-12'
    sub_chart_class = 'col-6'
    sub_table_class = 'col-6'

    def get_entries(self):
        return {
            'created': {
                'label': '발급',
                'color': '#0050ef',
                'query': self.get_queryset().filter(created_datetime__isnull=False)
                    .values('created_datetime__date') \
                    .annotate(created_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'created_count')
            },
            'used': {
                'label': '사용',
                'color': '#e51400',
                'query': self.get_queryset(term_field='used_datetime').filter(used_datetime__isnull=False)
                    .values('created_datetime__date') \
                    .annotate(used_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'used_count')
            },
        }

    def get_sub_table_data(self):
        rtn = super(VoucherDailyChart, self).get_sub_table_data()
        rtn['title'] = ''
        return rtn


class PointSumDailyChart(MultiLineChart):
    """
    포인트 금액 차트
    """
    model = Point
    unit_prefix = '￦'
    chart_class = 'col-12'
    sub_table_class = 'col-12'

    def get_entries(self):
        return {
            'income': {
                'label': '순증감',
                'color': '#008a00',
                'query': self.get_queryset()
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'recommend_reward': {
                'label': '가입시 추천인 입력 리워드',
                'color': '#aa9933',
                'query': self.get_queryset().filter(memo__icontains='가입시 추천인 입력')
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'recommend_first_done_reward': {
                'label': '추천 가입자 첫 미션완료 리워드',
                'color': '#aacc00',
                'query': self.get_queryset().filter(memo__icontains='[친구초대] 첫 미션완료')
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'recommend_done_reward': {
                'label': '추천 가입자 미션완료 리워드',
                'color': '#00ccaa',
                'query': self.get_queryset().filter(memo__icontains='[친구초대] 미션완료')
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'mission_reward': {
                'label': '미션 완료 리워드',
                'color': '#0050ef',
                'query': self.get_queryset().filter(bid__id__isnull=False)
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'review_reward': {
                'label': '리뷰 작성 리워드',
                'color': '#f0a30a',
                'query': self.get_queryset().filter(review__id__isnull=False)
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'voucher': {
                'label': '포인트 상품권',
                'color': '#e51400',
                'query': self.get_queryset().filter(voucher__id__isnull=False)
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'payment': {
                'label': '포인트 차감 결제',
                'color': '#642c28',
                'query': self.get_queryset().filter(payment__id__isnull=False)
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'unknown_plus': {
                'label': '직접 지급',
                'color': '#555555',
                'query': self.get_queryset().filter(amount__gt=0, voucher__id__isnull=True, payment__id__isnull=True,
                                                    bid__id__isnull=True, review__id__isnull=True)
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'unknown_minus': {
                'label': '직접 차감',
                'color': '#999999',
                'query': self.get_queryset().filter(amount__lt=0, voucher__id__isnull=True, payment__id__isnull=True,
                                                    bid__id__isnull=True, review__id__isnull=True)
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
        }

    def get_sub_table_data(self):
        rtn = super(PointSumDailyChart, self).get_sub_table_data()
        rtn['title'] = self.unit_prefix + add_comma(self._sub_chart_data['datasets'][0]['data'][0])
        return rtn


class CashSumDailyChart(MultiLineChart):
    """
    캐쉬 금액 차트
    """
    model = Cash
    unit_prefix = '￦'
    chart_class = 'col-12'
    sub_table_class = 'col-12'

    def get_entries(self):
        return {
            'income': {
                'label': '순증감',
                'color': '#008a00',
                'query': self.get_queryset()
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'recommend_first_done_reward': {
                'label': '추천 가입자 첫 미션완료 리워드',
                'color': '#aacc00',
                'query': self.get_queryset().filter(memo__icontains='[친구초대] 첫 미션완료')
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'recommend_done_reward': {
                'label': '추천 가입자 미션완료 리워드',
                'color': '#00ccaa',
                'query': self.get_queryset().filter(memo__icontains='[친구초대] 미션완료')
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'mission_reward': {
                'label': '미션 수행비',
                'color': '#0050ef',
                'query': self.get_queryset().filter(bid__id__isnull=False)
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'review_reward': {
                'label': '리뷰 작성 리워드',
                'color': '#f0a30a',
                'query': self.get_queryset().filter(review__id__isnull=False)
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'withdraw': {
                'label': '인출',
                'color': '#e51400',
                'query': self.get_queryset().filter(withdraw__id__isnull=False)
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'unknown_plus': {
                'label': '직접 지급',
                'color': '#555555',
                'query': self.get_queryset().filter(amount__gt=0, withdraw__id__isnull=True,
                                                    bid__id__isnull=True, review__id__isnull=True)
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
            'unknown_minus': {
                'label': '직접 차감',
                'color': '#999999',
                'query': self.get_queryset().filter(amount__lt=0, withdraw__id__isnull=True,
                                                    bid__id__isnull=True, review__id__isnull=True)
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
        }

    def get_sub_table_data(self):
        rtn = super(CashSumDailyChart, self).get_sub_table_data()
        rtn['title'] = self.unit_prefix + add_comma(self._sub_chart_data['datasets'][0]['data'][0])
        return rtn


class RecommendedUserDailyChart(MultiLineChart):
    """
    추천 회원 차트
    """
    model = User
    chart_class = 'col-12'
    # table_class = 'col-12'
    # sub_chart_class = 'col-6 mt-5'
    sub_table_class = 'col-12'
    # description_class = 'col-6'

    def get_entries(self):
        return {
            'recommended_by_user': {
                'label': '추천 가입 회원',
                'color': '#996600',
                'query': self.get_queryset().filter(recommended_user__isnull=False) \
                    .values('created_datetime__date') \
                    .annotate(user_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'user_count')
            },
            'recommended_by_partner': {
                'label': '협력사 가입 회원',
                'color': '#ccaa00',
                'query': self.get_queryset().filter(recommended_partner__isnull=False) \
                    .values('created_datetime__date') \
                    .annotate(user_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'user_count')
            },
            'recommend_not_matched': {
                'label': '추천인 비매칭 가입 회원',
                'color': '#e51400',
                'query': self.get_queryset().filter(recommended_user__isnull=False, recommended_partner__isnull=False) \
                    .exclude(_recommended_by='') \
                    .values('created_datetime__date') \
                    .annotate(user_count=Count('created_datetime__date')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'user_count')
            },
        }


class RecommendedUserMissionDailyChart(MissionDailyChart):
    """
    추천 미션 건수 차트
    """
    def get_queryset(self, model=None, term_field=None):
        qs = super(RecommendedUserMissionDailyChart, self).get_queryset(model, term_field)
        return qs.filter(Q(user__recommended_user__isnull=False) | Q(user__recommended_partner__isnull=False))


class RecommendedPaymentDailyChart(PaymentDailyChart):
    """
    추천 결제내역 차트
    """
    def get_queryset(self, model=None, term_field=None):
        qs = super(RecommendedPaymentDailyChart, self).get_queryset(model, term_field)
        return qs.filter(Q(bid__mission__user__recommended_user__isnull=False)
                         | Q(bid__mission__user__recommended_partner__isnull=False))


class RecommendedPaymentSumDailyChart(PaymentSumDailyChart):
    """
    추천 결제금액 차트
    """
    def get_queryset(self, model=None, term_field=None):
        qs = super(RecommendedPaymentSumDailyChart, self).get_queryset(model, term_field)
        return qs.filter(Q(bid__mission__user__recommended_user__isnull=False)
                         | Q(bid__mission__user__recommended_partner__isnull=False))


class UserActionDashboard(ChartDashboard):
    """
    사용자 활동 대시보드
    """
    item_layout_class = 'col-2 mt-3'

    def get_entries(self):
        joined = User.objects.filter(
            created_datetime__gte=self.start,
            created_datetime__lt=self.end + timezone.timedelta(days=1)
        )
        withdrew = User.objects.filter(
            withdrew_datetime__gte=self.start,
            withdrew_datetime__lt=self.end + timezone.timedelta(days=1)
        )
        blocked = ServiceBlock.objects.filter(
            start_datetime__gte=self.start,
            start_datetime__lt=self.end + timezone.timedelta(days=1)
        )
        unblocked = ServiceBlock.objects.filter(
            end_datetime__gte=self.start,
            end_datetime__lt=self.end + timezone.timedelta(days=1)
        )
        push_requested = Notification.objects.filter(
            created_datetime__gte=self.start,
            created_datetime__lt=self.end + timezone.timedelta(days=1)
        ).exclude(result__requested__isnull=True).exclude(result__requested=[])\
            .values_list('result__requested', flat=True)
        push_read = Notification.objects.filter(
            created_datetime__gte=self.start,
            created_datetime__lt=self.end + timezone.timedelta(days=1)
        ).exclude(result__read__isnull=True).exclude(result__read=[]).values_list('result__read', flat=True)
        push_action = Notification.objects.filter(
            created_datetime__gte=self.start,
            created_datetime__lt=self.end + timezone.timedelta(days=1)
        ).exclude(result__did_action__isnull=True).exclude(result__did_action=[]) \
            .values_list('result__did_action', flat=True)
        logged_in_devices = LoggedInDevice.objects.get_logged_in()
        logged_in_users = logged_in_devices.values('user').distinct('user')
        return [
            {
                'title': '가입한 유져',
                'value': add_comma(joined.count())
            },
            {
                'title': '탈퇴한 유져',
                'value': add_comma(withdrew.count())
            },
            {
                'title': '이용 정지된 유져',
                'value': add_comma(blocked.count())
            },
            {
                'title': '이용 정지 해제된 유져',
                'value': add_comma(unblocked.count())
            },
            {
                'title': '푸시 요청',
                'value': add_comma(sum([len(p) for p in push_requested]))
            },
            {
                'title': '푸시 읽음',
                'value': add_comma(sum([len(p) for p in push_read]))
            },
            {
                'title': '푸시 누름',
                'value': add_comma(sum([len(p) for p in push_action]))
            },
            {
                'title': '로그인 중인 디바이스',
                'value': add_comma(logged_in_devices.count())
            },
            {
                'title': '로그인 중인 유져',
                'value': add_comma(logged_in_users.count())
            },
        ]


class MissionActionDashboard(ChartDashboard):
    """
    미션 전환 대시보드
    """
    item_layout_class = 'col-2 mt-3'
    # template_name = 'admin/charts/dashboard-row.html'

    def get_percent_str(self, denominator, numerator):
        return ('%.2f%%' % (numerator * 100 / denominator)) if denominator else '-'

    def get_entries(self):
        requested = Mission.objects.filter(created_datetime__gte=self.start, created_datetime__lt=self.end + timezone.timedelta(days=1),
                                           requested_datetime__isnull=False)
        bidded = requested.filter(bids__applied_datetime__isnull=False).distinct('id')
        checked = bidded.filter(bids__customer_checked_datetime__isnull=False).distinct('id')
        pay_tried = bidded.filter(bids__payment__id__isnull=False).distinct('id')
        paid = bidded.filter(bids__payment__is_succeeded=True).distinct('id')
        user_canceled = bidded.filter(saved_state='user_canceled')
        timeout_canceled = bidded.filter(saved_state='timeout_canceled')
        done = paid.filter(saved_state='done')
        in_action = paid.filter(saved_state='in_action')
        won_and_canceled = paid.filter(saved_state='won_and_canceled')
        done_and_canceled = paid.filter(saved_state='done_and_canceled')

        reviewed = done.filter(bids__reviews__created_datetime__isnull=False).distinct('id')
        good_reviewed_count = 0
        bad_reviewed_count = 0
        for r in Review.objects.filter(_is_created_user_helper=False, bid__mission__in=reviewed):
            if sum(r.stars) > 5:
                good_reviewed_count += 1
            else:
                bad_reviewed_count += 1

        return [
            {
                'title': '미션 요청',
                'value': add_comma(requested.count())
            },
            [
                {
                    'title': '입찰한 미션',
                    'value': add_comma(bidded.count()),
                    'percent': self.get_percent_str(requested.count(), bidded.count())
                },
                {
                    'layout_class': 'mt-3 text-danger',
                    'title': '미입찰',
                    'value': add_comma(requested.count() - bidded.count()),
                    'percent': self.get_percent_str(requested.count(), requested.count() - bidded.count())
                },
            ],
            [
                {
                    'title': '입찰 확인',
                    'value': add_comma(checked.count()),
                    'percent': self.get_percent_str(bidded.count(), checked.count())
                },
                {
                    'layout_class': 'mt-3 text-danger',
                    'title': '미확인',
                    'value': add_comma(bidded.count() - checked.count()),
                    'percent': self.get_percent_str(bidded.count(), bidded.count() - checked.count())
                },
            ],
            [
                {
                    'title': '결제 시도',
                    'value': add_comma(pay_tried.count()),
                    'percent': self.get_percent_str(bidded.count(), pay_tried.count()) + ' (입찰한 미션 대비)'
                },
                {
                    'layout_class': 'mt-3 text-success',
                    'title': '결제 성공',
                    'value': add_comma(paid.count()),
                    'percent': self.get_percent_str(bidded.count(), paid.count()) + ' (입찰한 미션 대비)'
                },
                {
                    'layout_class': 'mt-3 text-danger',
                    'title': '미션 취소',
                    'value': add_comma(user_canceled.count()),
                    'percent': self.get_percent_str(bidded.count(), user_canceled.count()) + ' (입찰한 미션 대비)'
                },
                {
                    'layout_class': 'mt-3 text-danger',
                    'title': '시간 초과',
                    'value': add_comma(timeout_canceled.count()),
                    'percent': self.get_percent_str(bidded.count(), timeout_canceled.count()) + ' (입찰한 미션 대비)'
                },
            ],
            [
                {
                    'title': '수행완료',
                    'value': add_comma(done.count()),
                    'percent': self.get_percent_str(paid.count(), done.count())
                },
                {
                    'layout_class': 'mt-3 text-info',
                    'title': '수행중',
                    'value': add_comma(in_action.count()),
                    'percent': self.get_percent_str(paid.count(), in_action.count())
                },
                {
                    'layout_class': 'mt-3 text-danger',
                    'title': '수행중 취소',
                    'value': add_comma(won_and_canceled.count()),
                    'percent': self.get_percent_str(paid.count(), won_and_canceled.count())
                },
                {
                    'layout_class': 'mt-3 text-danger',
                    'title': '수행완료 후 취소',
                    'value': add_comma(done_and_canceled.count()),
                    'percent': self.get_percent_str(paid.count(), done_and_canceled.count())
                },
            ],
            [
                {
                    'title': '고객 긍정적 리뷰',
                    'value': add_comma(good_reviewed_count),
                    'percent': self.get_percent_str(done.count(), good_reviewed_count)
                },
                {
                    'layout_class': 'mt-3 text-warning',
                    'title': '고객 부정적 리뷰',
                    'value': add_comma(bad_reviewed_count),
                    'percent': self.get_percent_str(done.count(), bad_reviewed_count)
                },
                {
                    'layout_class': 'mt-3 text-danger',
                    'title': '리뷰 미작성',
                    'value': add_comma(done.count() - bad_reviewed_count - good_reviewed_count),
                    'percent': self.get_percent_str(done.count(), done.count() - bad_reviewed_count - good_reviewed_count)
                },
            ],
        ]


class PaymentDashboard(ChartDashboard):
    """
    결제 대시보드
    """
    item_layout_class = 'col-2 mt-3'

    def get_entries(self):
        paid = Payment.objects.filter(
            created_datetime__gte=self.start,
            created_datetime__lt=self.end + timezone.timedelta(days=1),
            is_succeeded=True)
        paid_amount = sum(paid.values_list('amount', flat=True))
        paid_count = paid.get_paid().count()
        point_paid_amount = sum([p for p in paid.values_list('point__amount', flat=True) if p is not None])
        coupon_discount_amount = paid.get_discounted_amount()
        coupon_discount_count = paid.get_coupon_used().count()
        mission_done = Bid.objects.filter(won_datetime__gte=self.start,
                                          won_datetime__lt=self.end + timezone.timedelta(days=1),
                                          ).done()
        mission_amount_avg = int(statistics.mean(mission_done.values_list('amount', flat=True))) if mission_done.exists() else 0
        return [
            {
                'layout_class': 'col-2 mt-3 text-success',
                'title': '순결제액',
                'value': '￦' + add_comma(int(paid_amount))
            },
            {
                'layout_class': 'col-2 mt-3 text-warning',
                'title': '포인트 결제액',
                'value': '￦' + add_comma(int(-point_paid_amount))
            },
            {
                'layout_class': 'col-2 mt-3 text-danger',
                'title': '쿠폰 할인액',
                'value': '￦' + add_comma(int(coupon_discount_amount))
            },
            {
                'title': '평균 미션단가',
                'value': '￦' + add_comma(mission_amount_avg)
            },
            {
                'title': '평균 순결제액',
                'value': '￦' + add_comma(int(paid_amount / paid_count) if paid_count else 0)
            },
            {
                'layout_class': 'col-2 mt-3 text-danger',
                'title': '평균 쿠폰 할인액',
                'value': '￦' + add_comma(int(coupon_discount_amount / coupon_discount_count) if coupon_discount_count else 0)
            },
        ]


class FinanceEntries(ChartDataBase):
    def get_entries(self):
        return {
            'card': {
                'label': '카드결제액',
                'color': '#008a00',
                'query': self.get_queryset(model=Payment).get_paid()
                    .values('created_datetime__date') \
                    .annotate(paid=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'paid')
            },
            'point': {
                'label': '비대면바우처 포인트 충전액',
                'color': '#f0ad4e',
                'query': self.get_queryset(model=Point).filter(voucher__id__isnull=True, payment__id__isnull=True,
                                                               bid__id__isnull=True, review__id__isnull=True,
                                                               added_type__in=[11, 12])
                    .values('created_datetime__date') \
                    .annotate(point=Sum('amount')) \
                    .order_by('created_datetime__date') \
                    .values_list('created_datetime__date', 'point')
            },
        }


class FinanceDashboard(FinanceEntries, ChartDashboard):
    """
    손익계산 대시보드
    """
    item_layout_class = ''
    template_name = 'admin/charts/dashboard-row.html'

    def get_entries(self):
        entries = super(FinanceDashboard, self).get_entries()
        card_sales = sum(entries['card']['query'].values_list('paid', flat=True))
        point_with_vat_sales = sum(entries['point']['query'].filter(added_type=11).values_list('point', flat=True))
        point_without_vat_sales = sum(entries['point']['query'].filter(added_type=12).values_list('point', flat=True))
        point_sales = point_without_vat_sales + point_with_vat_sales
        card_vat = round(card_sales / 110)
        point_vat = round(point_with_vat_sales / 11)
        card_fee = round(card_sales * 0.025)
        sms_fee = round(self.get_queryset(model=Notification).filter(send_method='sms', done_datetime__isnull=False).count() * 9.5)
        kakao_fee = round(self.get_queryset(model=Notification).filter(send_method='kakao', done_datetime__isnull=False).count() * 7.2)
        service_fee = round(sum(self.get_queryset(model=Payment).get_paid().values_list('bid__amount', flat=True)) * 0.9)
        total_sales = card_sales + point_sales - card_vat - point_vat
        total_fee = sms_fee + kakao_fee + card_fee + service_fee
        total_profit = total_sales - total_fee

        return [
            [
                {
                    'layout_class': 'col-3 mt-3 text-secondary offset-3',
                    'title': '카드결제총액',
                    'value': '￦' + add_comma(card_sales)
                },
                {
                    'layout_class': 'col-3 mt-3 text-secondary',
                    'title': '비대면바우처 포인트 충전액',
                    'value': '￦' + add_comma(point_with_vat_sales + point_without_vat_sales)
                },
                {
                    'layout_class': 'col-3 mt-3 text-dark',
                    'title': '결제합계액',
                    'value': '￦' + add_comma(card_sales + point_sales)
                },
            ],
            [
                {
                    'layout_class': 'col-3 mt-3 text-secondary offset-3',
                    'title': '카드매출 부가세',
                    'value': '￦' + add_comma(card_vat)
                },
                {
                    'layout_class': 'col-3 mt-3 text-secondary',
                    'title': '비대면바우처 부가세',
                    'value': '￦' + add_comma(point_vat)
                },
                {
                    'layout_class': 'col-3 mt-3 text-danger',
                    'title': '총부가세',
                    'value': '￦' + add_comma(card_vat + point_vat)
                },
            ],
            [
                {
                    'layout_class': 'col-3 mt-3 text-white bg-dark rounded offset-9',
                    'title': '총매출액',
                    'value': '￦' + add_comma(total_sales)
                },
            ],
            [
                {
                    'layout_class': 'col-3 mt-3 text-secondary',
                    'title': 'SMS 발송비',
                    'value': '￦' + add_comma(sms_fee)
                },
                {
                    'layout_class': 'col-3 mt-3 text-secondary',
                    'title': '카카오 알림톡 발송비',
                    'value': '￦' + add_comma(kakao_fee)
                },
                {
                    'layout_class': 'col-3 mt-3 text-secondary',
                    'title': '카드수수료',
                    'value': '￦' + add_comma(card_fee)
                },
                {
                    'layout_class': 'col-3 mt-3 text-secondary',
                    'title': '헬퍼 수행비 발생액',
                    'value': '￦' + add_comma(service_fee)
                },
            ],
            [
                {
                    'layout_class': 'col-3 mt-3 text-white bg-warning rounded offset-9',
                    'title': '비용합계',
                    'value': '￦' + add_comma(total_fee)
                },
            ],
            [
                {
                    'layout_class': 'col-3 mt-3 text-white rounded offset-9 bg-%s' % ('primary' if total_profit > 0 else 'danger'),
                    'title': '손익',
                    'value': '￦' + add_comma(total_profit)
                },
            ]
        ]


class AdditionalDataDashboard(ChartDashboard):
    """
    참고지표 대시보드
    """
    item_layout_class = ''
    template_name = 'admin/charts/dashboard-row.html'

    def get_entries(self):
        paid = self.get_queryset(model=Payment).get_paid()
        mission_amount = sum(paid.values_list('bid__amount', flat=True))
        point_paid = -sum(paid.exclude(point__isnull=True).values_list('point__amount', flat=True))
        coupon_discount_amount = paid.get_discounted_amount()
        staff_used = -sum(paid.exclude(point__isnull=True).filter(bid__mission__user__is_staff=True).values_list('point__amount', flat=True))

        cashes = Cash.objects.filter(
            created_datetime__lt=self.end + timezone.timedelta(days=1),
            helper__user__is_active=True, helper__user___is_service_blocked=False,
            helper__user__withdrew_datetime__isnull=True,
            helper__accepted_datetime__isnull=False, helper__is_active=True
        ).order_by('helper_id', '-id').distinct('helper_id').values_list('balance', flat=True)
        cash_balance = sum(cashes)
        cash_withdrawable = sum([c for c in cashes if c >= 10000])
        cash_withdrew = sum(Withdraw.objects.filter(
            done_datetime__gte=self.start,
            done_datetime__lt=self.end + timezone.timedelta(days=1),
        ).values_list('amount', flat=True))

        point_balance = sum(Point.objects.filter(
            created_datetime__lt=self.end + timezone.timedelta(days=1),
            user__is_active=True, user___is_service_blocked=False, user__withdrew_datetime__isnull=True,
        ).order_by('user_id', '-id').distinct('user_id').values_list('balance', flat=True))
        untact_voucher_users = Point.objects.filter(voucher__id__isnull=True, payment__id__isnull=True,
                                                    bid__id__isnull=True, review__id__isnull=True,
                                                    added_type=11).order_by('user_id').distinct('user_id').values_list('user', flat=True)
        untact_voucher_balance = sum(Point.objects.filter(
            created_datetime__lt=self.end + timezone.timedelta(days=1),
            user_id__in=untact_voucher_users
        ).order_by('user_id', '-id').distinct('user_id').values_list('balance', flat=True))

        return [
            [
                {
                    'layout_class': 'col-4 mt-3 text-secondary',
                    'title': '미션금액',
                    'value': '￦' + add_comma(mission_amount)
                },
                {
                    'layout_class': 'col-4 mt-3 text-secondary',
                    'title': '포인트 사용액',
                    'value': '￦' + add_comma(point_paid)
                },
                {
                    'layout_class': 'col-4 mt-3 text-secondary',
                    'title': '쿠폰 할인액',
                    'value': '￦' + add_comma(coupon_discount_amount)
                },
            ],
            [
                {
                    'layout_class': 'col-4 mt-3 text-secondary',
                    'title': '기말 미인출 캐시잔액',
                    'value': '￦' + add_comma(cash_balance)
                },
                {
                    'layout_class': 'col-4 mt-3 text-secondary',
                    'title': '기말 인출가능 캐시잔액',
                    'value': '￦' + add_comma(cash_withdrawable)
                },
                {
                    'layout_class': 'col-4 mt-3 text-secondary',
                    'title': '기간내 캐시인출액',
                    'value': '￦' + add_comma(cash_withdrew)
                },
            ],
            [
                {
                    'layout_class': 'col-4 mt-3 text-secondary',
                    'title': '기말 미사용 포인트잔액',
                    'value': '￦' + add_comma(point_balance)
                },
                {
                    'layout_class': 'col-4 mt-3 text-secondary',
                    'title': '기말 미사용 비대면바우처 잔액',
                    'value': '￦' + add_comma(untact_voucher_balance)
                },
                {
                    'layout_class': 'col-4 mt-3 text-secondary',
                    'title': '임직원 포인트 사용액',
                    'value': '￦' + add_comma(staff_used)
                },
            ]
        ]

    def get_context(self):
        context = super(AdditionalDataDashboard, self).get_context()
        context['description'] = 'ㅇㅇㅇㅇㅇ'
        return context


class SalesDailyChart(FinanceEntries, MultiLineChart):
    """
    매출 차트
    """
    unit_prefix = '￦'
    chart_class = 'col-12'
    sub_chart_class = 'col-6'
    sub_table_class = 'col-6'

    def get_context(self):
        context = super(SalesDailyChart, self).get_context()
        if len(self.labels) == 1:
            context['sub_chart_class'] = ''
            context['sub_table_class'] = 'col-12'
        return context


def cache_chart(chart_class, start_date, end_date):
    cache_key = '%s%s%s' % (chart_class.__class__.__name__, start_date, end_date)
    cached = chart_class(start_date, end_date).render()
    cache.set(cache_key, cached, 4000)
    return cached


@register.simple_tag(takes_context=True)
def chart(context, chart_class_name, force_cache_reset=False):
    chart_class = eval(chart_class_name)
    if issubclass(chart_class, ChartDataBase):
        return chart_class(context['start_date'], context['end_date']).render()
    else:
        return ''

    # cache_key = '%s%s%s' % (chart_class_name, context['start_date'], context['end_date'])
    # try:
    #     cached = cache.get(cache_key)
    # except:
    #     cached = ''
    # if not cached or force_cache_reset:
    #     chart_class = eval(chart_class_name)
    #     if issubclass(chart_class, ChartDataBase):
    #         cached = cache_chart(chart_class, context['start_date'], context['end_date'])
    #     else:
    #         cached = ''
    # return cached
