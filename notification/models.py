import threading
import time
import socket
import json
from logging import getLogger

import requests

from harupy.text import String
from harupy.shell import cmd

from django.apps import apps
from django.db import models
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField
from django.contrib import messages
from django.utils import timezone
from django.utils.formats import localize
from django.utils.functional import cached_property
from django.template.loader import render_to_string
from django.forms import ValidationError

from common.utils import CachedProperties
from base.models import Area
from accounts.serializers import SimpleProfileSerializer
from notification.utils import SMSHandler, KakaoHandler, PushHandler


sms = SMSHandler()
kakao = KakaoHandler()
push = PushHandler()
logger = getLogger('django')
anyman = CachedProperties()


MESSAGE_METHODS = (
    ('push', 'Push'),
    ('sms', 'SMS'),
    ('email', 'Email'),
    ('kakao', '카카오'),
)

CONDITIONS = (
    ('joined', '회원가입 즉시'),
    ('joined_remind_72', '회원가입 후 72시간동안 미션 없음'),
    ('first_mission_done', '첫 미션 완료'),
    ('coupon_expire_remind_5d', '쿠폰 만료 5일전'),
    ('coupon_expire_remind_10d', '쿠폰 만료 10일전'),
    ('2nd_mission_done_in_peoriod', '기간내에 미션 2회 완료'),

    # 앱
    ('test', '** [APP] 어드민 발송 테스트'),
    ('helper_accepted', '** [APP] 헬퍼신청 승인'),
    ('helper_rejected', '** [APP] 헬퍼신청 반려'),
    ('reviewed_from_helper', '** [APP] 헬퍼로부터 리뷰를 받음'),
    ('reviewed_from_customer', '** [APP] 고객으로부터 리뷰를 받음'),
    # ('mission_requested', '** [APP] 미션 발생'),
    ('mission_bidded', '** [APP] 헬퍼가 미션에 입찰함'),
    ('assigned_mission_bidded', '** [APP] 지정헬퍼가 미션에 입찰함'),
    ('assigned_mission_requested', '** [APP] 지정헬퍼에게 미션이 요청됨'),
    ('assigned_mission_canceled', '** [APP] 지정헬퍼에게 요청된 미션이 취소됨'),
    ('select_helper_before_timeout', '** [APP] 입찰시간 종료가 임박함'),
    ('bidded_mission_canceled', '** [APP] 입찰한 미션이 취소됨'),
    # ('bidded_mission_failed', '** [APP] 입찰한 미션에 패찰'),
    ('bidded_mission_matched', '** [APP] 입찰한 미션에 낙찰'),
    ('mission_timeout_canceled', '** [APP] 미션이 시간초과로 자동취소 (입찰자 없음)'),
    ('mission_timeout_canceled_with_bidding', '** [APP] 미션이 시간초과로 자동취소 (입찰자 있음)'),
    ('rewarded_helper_recommend_done_first', '** [APP] 헬퍼가 초대한 친구가 첫 미션을 완료함'),
    ('rewarded_customer_recommend_done_first', '** [APP] 고객이 초대한 친구가 첫 미션을 완료함'),
    ('rewarded_helper_recommend_done', '** [APP] 헬퍼가 초대한 친구가 미션을 완료함'),
    ('rewarded_customer_recommend_done', '** [APP] 고객이 초대한 친구가 미션을 완료함'),
    ('cancel_interaction_requested_by_helper', '** [APP] 헬퍼가 미션 취소 요청함'),
    ('cancel_interaction_requested_by_customer', '** [APP] 고객이 미션 취소 요청함'),
    ('due_interaction_requested_by_helper', '** [APP] 헬퍼가 미션일시 변경 요청함'),
    ('due_interaction_requested_by_customer', '** [APP] 고객이 미션일시 변경 요청함'),
    ('done_interaction_requested_by_helper', '** [APP] 헬퍼가 미션 완료 요청함'),
    ('done_interaction_requested_by_customer', '** [APP] 고객이 미션 완료 요청함'),
    ('cancel_interaction_canceled_by_helper', '** [APP] 헬퍼가 미션 취소 요청 취소함'),
    ('cancel_interaction_canceled_by_customer', '** [APP] 고객이 미션 취소 요청 취소함'),
    ('due_interaction_canceled_by_helper', '** [APP] 헬퍼가 미션일시 변경 요청 취소함'),
    ('due_interaction_canceled_by_customer', '** [APP] 고객이 미션일시 변경 요청 취소함'),
    ('done_interaction_canceled_by_helper', '** [APP] 헬퍼가 미션 완료 요청 취소함'),
    ('done_interaction_canceled_by_customer', '** [APP] 고객이 미션 완료 요청 취소함'),
    ('cancel_interaction_rejected_by_helper', '** [APP] 헬퍼가 취소요청 거부함'),
    ('cancel_interaction_rejected_by_customer', '** [APP] 고객이 취소요청 거부함'),
    ('due_interaction_rejected_by_helper', '** [APP] 헬퍼가 미션일시 변경 요청 거부함'),
    ('due_interaction_rejected_by_customer', '** [APP] 고객이 미션일시 변경 요청 거부함'),
    ('done_interaction_rejected_by_helper', '** [APP] 헬퍼가 미션 완료 요청 거부함'),
    ('done_interaction_rejected_by_customer', '** [APP] 고객이 미션 완료 요청 거부함'),
    ('cancel_interaction_accepted_by_helper', '** [APP] 헬퍼가 미션 취소 요청 수락함'),
    ('cancel_interaction_accepted_by_customer', '** [APP] 고객이 미션 취소 요청 수락함'),
    ('due_interaction_accepted_by_helper', '** [APP] 헬퍼가 미션일시 변경 요청 수락함'),
    ('due_interaction_accepted_by_customer', '** [APP] 고객이 미션일시 변경 요청 수락함'),
    ('done_interaction_accepted_by_helper', '** [APP] 헬퍼가 미션 완료 요청 수락함'),
    ('done_interaction_accepted_by_customer', '** [APP] 고객이 미션 완료 요청 수락함'),

    # 웹 미션
    ('web_requested', '** [WEB] 견적 요청 완료'),
    ('web_bidded', '** [WEB] 헬퍼가 미션에 입찰함'),
    ('web_select_helper_before_timeout', '** [WEB] 입찰시간 종료가 임박함'),
    ('web_mission_timeout_canceled', '** [WEB] 미션이 시간초과로 자동취소 (입찰자 없음)'),
    ('web_mission_timeout_canceled_with_bidding', '** [WEB] 미션이 시간초과로 자동취소 (입찰자 있음)'),
    ('web_cancel_interaction_requested_by_helper', '** [WEB] 헬퍼가 미션 취소 요청함'),
    ('web_due_interaction_requested_by_helper', '** [WEB] 헬퍼가 미션일시 변경 요청함'),
    ('web_done_interaction_requested_by_helper', '** [WEB] 헬퍼가 미션 완료 요청함'),
    ('web_cancel_interaction_canceled_by_helper', '** [WEB] 헬퍼가 미션 취소 요청 취소함'),
    ('web_due_interaction_canceled_by_helper', '** [WEB] 헬퍼가 미션일시 변경 요청 취소함'),
    ('web_done_interaction_canceled_by_helper', '** [WEB] 헬퍼가 미션 완료 요청 취소함'),
    ('web_cancel_interaction_rejected_by_helper', '** [WEB] 헬퍼가 취소요청 거부함'),
    ('web_due_interaction_rejected_by_helper', '** [WEB] 헬퍼가 미션일시 변경 요청 거부함'),
    ('web_done_interaction_rejected_by_helper', '** [WEB] 헬퍼가 미션 완료 요청 거부함'),
    ('web_cancel_interaction_accepted_by_helper', '** [WEB] 헬퍼가 미션 취소 요청 수락함'),
    ('web_due_interaction_accepted_by_helper', '** [WEB] 헬퍼가 미션일시 변경 요청 수락함'),
    ('web_done_interaction_accepted_by_helper', '** [WEB] 헬퍼가 미션 완료 요청 수락함'),

    # 시스템 알림
    ('regular_point_balance', '** [SYSTEM] 포인트 잔액 정기 안내'),
    # ('', ''),
)

CONDITION_PUSH_DATA = {
    # page
    # 헬퍼가 받는경우 BID_* ,
    # 고객이 받는경우 MISSION_*

    'test': {'page': 'TEST'},
    'helper_accepted': {'page': 'HOME_HELPER', 'type': 'state'},
    'helper_rejected': {'page': 'HOME_HELPER', 'type': 'state'},
    'reviewed_from_helper': {'page': 'MYPAGE_REVIEW_RECEIVED/user'},
    'reviewed_from_customer': {'page': 'MYPAGE_REVIEW_RECEIVED/helper'},
    'mission_requested': {'page': 'HOME_HELPER', 'type': 'added_mission'},
    'mission_bidded': {'page': 'MISSION_BIDDING_DETAIL', 'obj_id': None},
    'assigned_mission_bidded': {'page': 'MISSION_BIDDING_DETAIL', 'type': 'added_mission', 'obj_id': None},
    'assigned_mission_requested': {'page': 'BID_UNBIDDEN_DETAIL', 'type': 'added_mission', 'obj_id': None},
    'select_helper_before_timeout': {'page': 'MISSION_BIDDING_DETAIL', 'obj_id': None},
    'bidded_mission_canceled': {'page': 'BID_ARCHIVE/cancel'},
    'bidded_mission_matched': {'page': 'BID_INACTION_DETAIL', 'obj_id': None},
    'mission_timeout_canceled': {'page': 'MISSION_ARCHIVE_DETAIL', 'type': 'interaction', 'obj_id': None},
    'mission_timeout_canceled_with_bidding': {'page': 'MISSION_ARCHIVE_DETAIL', 'type': 'interaction', 'obj_id': None},
    'rewarded_helper_recommend_done_first': {'page': 'MYPAGE_HISTORY_CASH', 'type': 'reward'},
    'rewarded_customer_recommend_done_first': {'page': 'MYPAGE_HISTORY_POINT', 'type': 'reward'},
    'rewarded_helper_recommend_done': {'page': 'MYPAGE_HISTORY_CASH', 'type': 'reward'},
    'rewarded_customer_recommend_done': {'page': 'MYPAGE_HISTORY_POINT', 'type': 'reward'},

    # 요청
    'cancel_interaction_requested_by_helper': {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'cancel_interaction_requested_by_customer': {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'due_interaction_requested_by_helper': {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'due_interaction_requested_by_customer': {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'done_interaction_requested_by_helper': {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'done_interaction_requested_by_customer': {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},

    # 취소
    'cancel_interaction_canceled_by_helper': {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'cancel_interaction_canceled_by_customer': {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'due_interaction_canceled_by_helper': {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'due_interaction_canceled_by_customer': {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'done_interaction_canceled_by_helper': {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'done_interaction_canceled_by_customer': {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},

    # 거절
    'cancel_interaction_rejected_by_helper': {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'cancel_interaction_rejected_by_customer': {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'due_interaction_rejected_by_helper': {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'due_interaction_rejected_by_customer': {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'done_interaction_rejected_by_helper': {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'done_interaction_rejected_by_customer': {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},

    # 수락
    'cancel_interaction_accepted_by_helper': {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'cancel_interaction_accepted_by_customer': {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'due_interaction_accepted_by_helper': {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'due_interaction_accepted_by_customer': {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None},
    'done_interaction_accepted_by_helper': {'page': 'MISSION_ARCHIVE_DETAIL', 'type': 'interaction', 'obj_id': None},
    'done_interaction_accepted_by_customer': {'page': 'BID_ARCHIVE_DETAIL', 'type': 'interaction', 'obj_id': None},

    # System
    'regular_point_balance': {'page': 'MYPAGE_HISTORY_POINT', 'type': 'reward'},

}

NOTIFICATION_STATUS = {
    'read': '수신확인',
    'done': '발송완료',
    'retried': '재시도',
    'failed': '발송실패',
    'requested': '발송요청',
    'created': '작성됨',
}


# todo: 삭제 예정
SMS_PRESETS = {
    'external_requested': '[애니맨] 견적 요청이 완료되었습니다.\n\n{}',
    'external_bidded': '[애니맨] 견적한 헬퍼를 확인해주세요. 견적한 헬퍼 : {}명\n\n{}',
    'web_requested': '[애니맨] 견적 요청이 완료되었습니다.\n\n{}',
    'web_bidded': '[애니맨] 견적한 헬퍼를 확인해주세요. 견적한 헬퍼 : {}명\n\n{}',
    'select_helper_before_timeout': '[애니맨] 입찰 시간이 곧 종료됩니다.\n견적한 헬퍼 : {}명\n헬퍼를 선택하지 않으면 자동 취소됩니다.\n\n{}',
    'mission_timeout_canceled': '요청하신 미션은 입찰 시간 초과로 종료되었습니다.',
    'mission_timeout_canceled_with_bidding': '입찰 시간 내에 헬퍼를 선택하지 않아 입찰이 종료되었습니다.',

    'cancel_interaction_requested_by_helper': '[애니맨] 진행중인 미션에 취소요청이 왔습니다.\n\n{}',
    'due_interaction_requested_by_helper': '[애니맨] 진행중인 미션의 수행 날짜/시간에 변경 요청이 왔습니다.\n\n{}',
    'done_interaction_requested_by_helper': '[애니맨] 진행중인 미션의 완료확정을 진행해주세요.\n\n{}',
    'cancel_interaction_canceled_by_helper': '[애니맨] 미션취소 요청이 취소되었습니다.\n\n{}',
    'due_interaction_canceled_by_helper': '[애니맨] 미션의 수행 날짜시간 변경이 취소되었습니다.\n\n{}',
    'done_interaction_canceled_by_helper': '[애니맨] 미션의 완료 요청이 취소되었습니다.\n\n{}',
    'cancel_interaction_rejected_by_helper': '[애니맨] 미션취소 요청이 거절되었습니다.\n\n{}',
    'due_interaction_rejected_by_helper': '[애니맨] 미션의 수행 날짜/시간 변경이 거절되었습니다.\n\n{}',
    'done_interaction_rejected_by_helper': '[애니맨] 미션의 완료요청이 거절되었습니다.\n\n{}',
    'cancel_interaction_accepted_by_helper': '[애니맨] 미션이 취소되었습니다.\n\n{}',
    'due_interaction_accepted_by_helper': '[애니맨] 미션의 수행 날짜/시간이 변경되었습니다.\n\n{}',
    'done_interaction_accepted_by_helper': '[애니맨] 미션이 완료 처리되었습니다.\n\n{}',
}


# todo: 삭제 예정
PUSH_PRESETS = {
    'test': ('[푸쉬 테스트] 안녕하세요. 애니맨입니다.', {'page': 'TEST'}),
    'helper_accepted': ('{} 님, 애니맨 헬퍼가 되셨습니다. 다양한 미션을 수행해보세요.', {'page': 'HOME_HELPER', 'type': 'state'}),
    'helper_rejected': ('헬퍼신청 승인이 거부되었습니다. 사유를 확인해주세요.', {'page': 'HOME_HELPER', 'type': 'state'}),
    'reviewed_from_helper': ('{} 헬퍼님이 회원님에게 리뷰를 남겼습니다.', {'page': 'MYPAGE_REVIEW_RECEIVED/user'}),
    'reviewed_from_customer': ('{} 고객님이 회원님에게 리뷰를 남겼습니다.', {'page': 'MYPAGE_REVIEW_RECEIVED/helper'}),
    'mission_requested': ('{} 미션 발생! {}', {'page': 'HOME_HELPER', 'type': 'added_mission'}),
    'mission_bidded': ('요청하신 미션에 입찰한 헬퍼를 확인해주세요. 입찰한 헬퍼 : {}명', {'page': 'MISSION_BIDDING_DETAIL', 'obj_id': None }),
    'assigned_mission_bidded': ('{} 헬퍼님이 미션에 입찰했습니다. 견적을 확인하고 진행여부를 결정해주세요.', {'page': 'MISSION_BIDDING_DETAIL', 'type': 'added_mission', 'obj_id': None }),
    'assigned_mission_requested': ('{} 님이 회원님에게 미션을 요청했습니다. ', {'page': 'BID_UNBIDDEN_DETAIL', 'type': 'added_mission', 'obj_id': None }),
    'assigned_mission_canceled': ('{} 님이 회원님에게 요청한 미션이 취소되었습니다.', {}),
    'select_helper_before_timeout': ('입찰 시간이 곧 종료됩니다. 헬퍼를 선택하지 않으면 자동 취소됩니다.', {'page': 'MISSION_BIDDING_DETAIL', 'obj_id': None }),
    'bidded_mission_canceled': ('입찰하신 "{}" 미션이 취소되었습니다.', {'page': 'BID_ARCHIVE/cancel'}),
    'bidded_mission_failed': ('입찰하신 "{}" 미션이 종료되었습니다.', {}),
    'bidded_mission_matched': ('[매칭 성공] "{}" 미션을 진행해주세요.', {'page': 'BID_INACTION_DETAIL', 'obj_id': None }),
    'mission_timeout_canceled': ('요청하신 미션은 입찰 시간 초과로 종료되었습니다. 다시 요청할까요?', {'page': 'MISSION_ARCHIVE_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'mission_timeout_canceled_with_bidding': ('입찰 시간 내에 헬퍼를 선택하지 않아 입찰이 종료되었습니다. 다시 요청할까요?', {'page': 'MISSION_ARCHIVE_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'rewarded_helper_recommend_done_first': ('친구의 첫 요청 미션이 완료되어 {} 캐시 적립', {'page': 'MYPAGE_HISTORY_CASH', 'type': 'reward'}),
    'rewarded_customer_recommend_done_first': ('친구의 요청 미션이 완료되어 {} 포인트 적립', {'page': 'MYPAGE_HISTORY_POINT', 'type': 'reward'}),
    'rewarded_helper_recommend_done': ('친구의 요청 미션이 완료되어 {} 캐시 적립', {'page': 'MYPAGE_HISTORY_CASH', 'type': 'reward'}),
    'rewarded_customer_recommend_done': ('친구의 요청 미션이 완료되어 {} 포인트 적립', {'page': 'MYPAGE_HISTORY_POINT', 'type': 'reward'}),

    # 헬퍼가 받는경우 BID_* ,
    # 고객이 받는경우 MISSION_*

    # 요청
    'cancel_interaction_requested_by_helper': (
    '"{}" 미션에 취소요청이 왔습니다.', {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'cancel_interaction_requested_by_customer': (
    '"{}" 미션에 취소요청이 왔습니다.', {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'due_interaction_requested_by_helper': (
    '"{}" 미션의 수행 날짜/시간에 변경 요청이 왔습니다.', {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'due_interaction_requested_by_customer': (
    '"{}" 미션의 수행 날짜/시간에 변경 요청이 왔습니다.', {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'done_interaction_requested_by_helper': (
    '"{}" 미션의 완료확정을 진행해주세요.', {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'done_interaction_requested_by_customer': (
    '"{}" 미션의 완료확정을 진행해주세요.', {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),

    # 취소
    'cancel_interaction_canceled_by_helper': (
    '"{}" 미션취소 요청이 취소되었습니다.', {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'cancel_interaction_canceled_by_customer': (
    '"{}" 미션취소 요청이 취소되었습니다.', {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'due_interaction_canceled_by_helper': (
    '"{}" 미션의 수행 날짜/시간 변경이 취소되었습니다.', {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'due_interaction_canceled_by_customer': (
    '"{}" 미션의 수행 날짜/시간 변경이 취소되었습니다.', {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'done_interaction_canceled_by_helper': (
    '"{}" 미션의 완료요청이 취소되었습니다.', {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'done_interaction_canceled_by_customer': (
    '"{}" 미션의 완료요청이 취소되었습니다.', {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),

    # 거절
    'cancel_interaction_rejected_by_helper': (
    '"{}" 미션취소 요청이 거절되었습니다.', {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'cancel_interaction_rejected_by_customer': (
    '"{}" 미션취소 요청이 거절되었습니다.', {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'due_interaction_rejected_by_helper': (
    '"{}" 미션의 수행 날짜/시간 변경이 거절되었습니다.', {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'due_interaction_rejected_by_customer': (
    '"{}" 미션의 수행 날짜/시간 변경이 거절되었습니다.', {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'done_interaction_rejected_by_helper': (
    '"{}" 미션의 완료요청이 거절되었습니다.', {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'done_interaction_rejected_by_customer': (
    '"{}" 미션의 완료요청이 거절되었습니다.', {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),

    # 수락
    'cancel_interaction_accepted_by_helper': (
    '"{}" 미션이 취소되었습니다.', {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'cancel_interaction_accepted_by_customer': (
    '"{}" 미션이 취소되었습니다.', {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'due_interaction_accepted_by_helper': (
    '"{}" 미션의 수행 날짜/시간이 변경되었습니다.', {'page': 'MISSION_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'due_interaction_accepted_by_customer': (
    '"{}" 미션의 수행 날짜/시간이 변경되었습니다.', {'page': 'BID_INACTION_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'done_interaction_accepted_by_helper': (
    '"{}" 미션이 완료 처리되었습니다. 리뷰를 작성하면 추가 포인트가 지급됩니다.', {'page': 'MISSION_ARCHIVE_DETAIL', 'type': 'interaction', 'obj_id': None}),
    'done_interaction_accepted_by_customer': (
    '"{}" 미션이 완료 처리되었습니다. 리뷰를 작성하면 추가 캐시가 지급됩니다.', {'page': 'BID_ARCHIVE_DETAIL', 'type': 'interaction', 'obj_id': None}),
}


EMAIL_PRESETS = {
    'password_reset_requested': '[애니맨] 계정에 비밀번호 재설정이 요청되었습니다.'
}


def sms_result_check_worker(obj):
    """sms 결과확인 수행 워커"""
    i = 0
    if obj.result and 'code' in obj.result and obj.result['code'] == '200':
        while not ('data' in obj.result and 'resultCode' in obj.result['data'] and obj.result['data']['resultCode']):
            time.sleep(settings.SMS_RESULT_DELAY)
            obj.check_result()
            i += 1
            if i > 10:
                break


def push_worker(obj):
    """push 수행 워커"""
    obj.send()


class QueueRegisterer:
    """
    릴레이 서버 큐 등록
    """
    sock = None
    _host = ''
    _port = ''

    def __init__(self):
        self._host = settings.PUSH_QUEUE_HOST
        self._port = settings.PUSH_QUEUE_PORT

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self._host, self._port))

    def disconnect(self):
        self.sock.close()
        self.sock = None

    def request(self, msg):
        if not self.sock:
            self.connect()

        try:
            self.sock.sendall(str(msg).encode())
            result = True
        except:
            result = False
        self.disconnect()
        return result

    def __request(self, msg):
        if not self.sock:
            self.connect()

        retry_count = 0
        while retry_count < 2:
            try:
                self.sock.sendall(str(msg).encode())
            except:
                self.disconnect()
                self.connect()
                retry_count += 1
            else:
                return True
        return False

    def push(self, obj_id):
        return self.request('PUSH:%s' % str(obj_id))


class NotificationManager(models.Manager):
    """
    알림 매니져
    """
    def __init__(self):
        self.user_model = get_user_model()
        super(NotificationManager, self).__init__()

    def get_by_usercode(self, code, days=30, limit=0, exclude_read=False, send_method='push'):
        qs = self.get_queryset().filter(receiver_user__code=code, send_method=send_method).order_by('-requested_datetime')
        if days:
            qs = qs.filter(requested_datetime__gte=(timezone.now() - timezone.timedelta(days=days)))
        if exclude_read:
            qs = qs.exclude(result__read__contains=code)
        if limit:
            return qs[:limit]
        return qs

    def _get_by_usercode(self, code, days=30, limit=0, exclude_read=False):
        qs = self.get_queryset().filter(send_method='push', result__requested__contains=code) \
             .exclude(receiver_areas__id__isnull=False) \
             .exclude(receiver_groups__code='online_helper') \
             .order_by('-requested_datetime')
        if days:
            qs = qs.filter(requested_datetime__gte=(timezone.now() - timezone.timedelta(days=days)))
        if exclude_read:
            qs = qs.exclude(result__read__contains=code)
        if limit:
            return qs[:limit]
        return qs

    def not_requested(self, send_method=None):
        qs = self.filter(requested_datetime__isnull=True)
        if send_method:
            qs = qs.filter(send_method=send_method)
        return qs

    def kakao(self, receiver, template_code, title, content, sender=None, tasker=None):
        kwargs = {
            'send_method': 'kakao',
            'data_type': template_code,
            'subject': title,
            'content': content,
            'tasker': tasker,
        }
        if isinstance(receiver, self.user_model):
            kwargs.update({'receiver_user': receiver})
            if receiver.mobile:
                kwargs.update({'receiver_identifier': str(receiver.mobile)})
            else:
                raise ValueError('해당 회원은 인증된 휴대폰 번호가 없습니다.')
        elif str(receiver).isdigit():
            kwargs.update({'receiver_identifier': receiver})
        if sender and isinstance(sender, self.user_model):
            kwargs.update({'created_user': sender})
        obj = self.create(**kwargs)
        return obj.send_or_relay()

    def sms(self, receiver, content, sender=None, tasker=None):
        kwargs = {
            'send_method': 'sms',
            'content': content,
            'tasker': tasker,
        }
        if isinstance(receiver, self.user_model):
            kwargs.update({'receiver_user': receiver})
            if receiver.mobile:
                kwargs.update({'receiver_identifier': str(receiver.mobile)})
            else:
                raise ValueError('해당 회원은 인증된 휴대폰 번호가 없습니다.')
        elif str(receiver).isdigit():
            kwargs.update({'receiver_identifier': receiver})
        if sender and isinstance(sender, self.user_model):
            kwargs.update({'created_user': sender})
        obj = self.create(**kwargs)
        # obj.send()
        # worker = threading.Thread(target=sms_result_check_worker, args=(obj,))
        # worker.start()
        return obj.send_or_relay()

    def sms_preset(self, receiver, preset, args=[], sender=None):
        content = SMS_PRESETS[preset].format(*args)
        return self.sms(receiver, content, sender)

    def push(self, receiver, title, content, data={}, sender=None, tasker=None, lazy=False, send=True):
        kwargs = {
            'send_method': 'push',
            'subject': title,
            'content': content,
            'tasker': tasker,
        }
        for k, v in data.items():
            kwargs['data_'+k] = v

        if sender:
            kwargs.update({'created_user': sender})
        if isinstance(receiver, self.user_model):
            # 회원 1명인 경우
            kwargs.update({'receiver_user': receiver})
            if not lazy and not receiver.push_tokens:
                logger.error('[Push] [receiver %s] 해당 회원은 로그인된 기기의 푸쉬 토큰 정보가 없습니다.' % receiver)
                raise LookupError('해당 회원은 로그인된 기기의 푸쉬 토큰 정보가 없습니다.')
        else:
            if not hasattr(receiver, '__iter__'):
                logger.error('[Push] [receiver %s] 수신자 정보를 올바르게 입력하세요.' % receiver)
                raise ValueError('수신자 정보를 올바르게 입력하세요.')
        obj = self.create(**kwargs)
        if not obj.receiver_user and hasattr(receiver, '__iter__'):
            if type(receiver[0]) is int:
                # 지역 id의 list인 경우
                obj.receiver_areas.add(*receiver)
            elif isinstance(receiver[0], self.user_model):
                code_and_tokens = []
                for r in receiver:
                    for t in r.push_tokens:
                        code_and_tokens.append((r.code, t))
                obj.receiver_identifier = json.dumps(code_and_tokens)
                # obj.receiver_identifier = ','.join([','.join(r.push_tokens) for r in receiver if r.push_tokens])
            elif isinstance(receiver[0], ReceiverGroup):
                obj.receiver_groups.add(*receiver)
            elif isinstance(receiver, str):
                try:
                    group = ReceiverGroup.objects.get(code=receiver)
                except:
                    raise ValueError('수신자 정보를 올바르게 입력하세요.')
                obj.receiver_groups.add(group)
            else:
                obj.receiver_identifier = ','.join(receiver)
        obj.save()

        # 전송요청
        obj.check_requested_count()
        # obj.send()
        # todo: celery 고려할 것
        # worker = threading.Thread(target=push_worker, args=obj, daemon=False)
        # worker.start()

        if send:
            obj.send_or_relay(lazy=lazy)
        else:
            obj.send(commit=False)
        return obj

    def push_preset(self, receiver, preset, args=[], kwargs={}, request=None, sender=None, title='애니맨 알림', lazy=False):
        content = PUSH_PRESETS[preset][0].format(*args)
        data = PUSH_PRESETS[preset][1]
        data.update(kwargs)
        try:
            result = self.push(receiver, title, content, data, sender, lazy=lazy)
        except:
            if request:
                receiver_string = String(receiver)
                receiver_string = receiver_string[:50] + '...' if len(receiver_string) > 50 else receiver_string
                messages.error(request, '%s에게 푸쉬 알림을 보낼 수 없습니다.' % receiver_string)
            result = None
            logger.error('[Push] Cannot push messages "%s". Requested to %s %s' % (preset, receiver, type(receiver)))
        else:
            if request:
                messages.success(request, '푸쉬 알림을 전송했습니다.')
        return result

    def no_send_push(self, receiver, title='애니맨 알림', content='', data={}, request=None):
        try:
            result = self.push(receiver, title, content, data, sender=request.user, send=False)
        except:
            messages.success(request, '알림 목록 추가에 실패했습니다.')
            return None
        messages.success(request, '알림 목록에 추가했습니다.')
        return result

    def email(self, receiver, title, plaintext, html=None, sender=None, tasker=None):
        kwargs = {
            'send_method': 'email',
            'subject': title,
            'content': plaintext,
            'tasker': tasker,
        }
        if html:
            kwargs.update({'data': html})  # todo: html 메세지 사용이 필요한 시점에 반드시 수정할 것.
        if isinstance(receiver, self.user_model):
            kwargs.update({'receiver_user': receiver})
            if receiver.email:
                kwargs.update({'receiver_identifier': str(receiver.email)})
            else:
                raise ValueError('해당 회원은 이메일 주소가 없습니다.')
        else:
            kwargs.update({'receiver_identifier': receiver})
        if sender and isinstance(sender, self.user_model):
            kwargs.update({'created_user': sender})
        obj = self.create(**kwargs)
        obj.send()

    def email_preset(self, receiver, preset, context=None, request=None):
        title = EMAIL_PRESETS[preset].format(**(context or {}))
        html = render_to_string('notification/email/%s.html' % preset, context)
        plaintext = render_to_string('notification/email/%s.txt' % preset, context)
        try:
            result = self.email(receiver, title, plaintext, html)
        except:
            if request:
                messages.error(request, '%s에게 이메일을 보낼 수 없습니다.' % String(receiver))
            result = None
        else:
            if request:
                messages.success(request, '%s에게 이메일을 전송했습니다.' % String(receiver))
        return result


class ReceiverGroupQueryset(models.QuerySet):
    """
    수신그룹 쿼리셋
    """
    def get_query_dict(self):
        query_dict = {}
        for q in self.values_list('query', flat=True):
            query_dict.update(q)
        return query_dict

    def get_group_users(self, return_token=False):
        users = get_user_model().objects.get_active_users()
        query = self.get_query_dict()
        new_query = {}
        for k, v in query.items():
            if type(v) == str and v.endswith(')') and '(' in v:
                new_query.update({k: eval(v)})
            elif k == 'QUERYSET' and hasattr(users, v):
                get_new_users = getattr(users, v)
                users = get_new_users()
            else:
                new_query.update({k: v})
        users = users.filter(**new_query)
        if not return_token:
            return users
        return users.get_push_tokens()


class ReceiverGroup(models.Model):
    """
    수신그룹 모델
    """
    title = models.CharField('제목', unique=True, max_length=20)
    code = models.SlugField('슬러그', unique=True, max_length=20)
    query = JSONField('쿼리', default=dict)

    objects = ReceiverGroupQueryset.as_manager()

    class Meta:
        verbose_name = '수신그룹'
        verbose_name_plural = '수신그룹'

    def __str__(self):
        return self.title


class Notification(models.Model):
    """
    알림 모델
    """
    send_method = models.CharField('메세지 타입', max_length=5, choices=MESSAGE_METHODS)
    receiver_groups = models.ManyToManyField(ReceiverGroup, verbose_name='수신그룹', related_name='notifications',
                                           blank=True)
    receiver_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='수신회원', null=True, blank=True,
                                      related_name='received_notifications', on_delete=models.CASCADE,
                                      help_text='회원이 선택된 경우 수신 식별자보다 우선 적용됩니다.')
    receiver_areas = models.ManyToManyField(Area, verbose_name='수신 지역', blank=True, related_name='notifications')
    subject = models.CharField('제목', max_length=100, blank=True, default='')
    content = models.TextField('내용', blank=True, default='')
    data_page = models.CharField('랜딩 페이지', max_length=50, blank=True, default='')
    data_type = models.CharField('랜딩 타입', max_length=30, blank=True, default='')
    data_obj_id = models.PositiveIntegerField('랜딩 오브젝트 ID', null=True, blank=True, default=None)
    created_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='작성회원', null=True, blank=True,
                                     related_name='created_notifications', on_delete=models.CASCADE)
    tasker = models.ForeignKey('notification.Tasker', verbose_name='태스커', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='notifications')
    created_datetime = models.DateTimeField('작성일시', auto_now_add=True)
    requested_datetime = models.DateTimeField('발송요청일시', null=True, blank=True)
    retried_datetime = models.DateTimeField('재시도일시', null=True, blank=True)
    done_datetime = models.DateTimeField('발송완료일시', null=True, blank=True)
    failed_datetime = models.DateTimeField('발송실패일시', null=True, blank=True)
    read_datetime = models.DateTimeField('수신일시', null=True, blank=True)
    receiver_identifier = models.TextField('수신 식별자', blank=True, default='')
    result = JSONField('결과', null=True, blank=True)

    objects = NotificationManager()

    class Meta:
        verbose_name = '알림'
        verbose_name_plural = '알림'

    def __str__(self):
        return '[%s] %s' % (self.send_method, self.receiver[:50] + ('...' if len(self.receiver) > 50 else ''))

    @property
    def receiver(self):
        if self.receiver_groups.exists():
            return '<' + ', '.join(self.receiver_groups.values_list('title', flat=True)) + '>'
        elif self.receiver_user:
            return str(self.receiver_user)
        if self.send_method == 'push':
            if self.receiver_areas.exists():
                return '<' + ', '.join([str(area) for area in self.receiver_areas.all()]) + '>'
            elif self.code_and_tokens:
                return ', '.join({ct[0] for ct in self.code_and_tokens})
            return '***token***'
        return self.receiver_identifier

    @property
    def sender(self):
        return self.created_user.username if self.created_user else 'Anyman'

    @property
    def data(self):
        _data = {'page': self.data_page}
        if self.data_type:
            _data.update({'type': self.data_type})
        if self.data_obj_id:
            _data.update({'obj_id': str(self.data_obj_id)})
        return _data

    @cached_property
    def target_users(self):
        """실제로 푸시를 보내지 않는 경우를 고려하여 push_allowed 확인하지 않음"""
        if self.receiver_groups.exists():
            users = self.receiver_groups.get_group_users()
            if self.created_user:
                users = users.exclude(id=self.created_user.id)
            if self.receiver_groups.count() == 1 and self.receiver_groups.last().code == 'online_helper':
                users = users.filter(helper__is_online_acceptable=True)
            return users
        elif self.receiver_areas.exists():
            # 지역
            # 지역으로 발송하는 경우는 대상이 헬퍼인 경우로 한정함.
            # 애초에 지역으로 발송한다는 것 자체가 헬퍼의 수행지역을 기반으로 발송하는 경우만 상정하고 있기에
            # 헬퍼가 아닌 사람에게 지역으로 발송하는 경우는 상정할 수 없음.
            # 또한 그러한 시도는 의도하지 않은 결과가 나오게 될 것임.
            area_ids = list(self.receiver_areas.all().values_list('id', flat=True))
            return get_user_model().objects.get_by_helper_areas(*area_ids)\
                .exclude(id=self.created_user_id).exclude(id__in=self.created_user.blocked_ids)
        else:
            if self.receiver_user:
                # 1명이지만 쿼리셋 오브젝트로 리턴
                return get_user_model().objects.filter(id=self.receiver_user.id)

        # 없지만 쿼리셋 오브젝트로 리턴
        return get_user_model().objects.none()

    @cached_property
    def tokens(self):
        if self.receiver_identifier and not self.receiver_user:
            return self.receiver_identifier.split(',')
        return self.target_users.get_push_tokens()

    @cached_property
    def code_and_tokens(self):
        if self.receiver_identifier and not self.receiver_user:
            try:
                return json.loads(self.receiver_identifier)
            except:
                return []
        # 수신회원이 특정된 경우에는 알림허용 여부를 무시하고 보냄
        only_if_allowed = False if self.receiver_user else True
        return self.target_users.get_code_and_push_tokens(only_if_allowed=only_if_allowed,
                                                          is_mission_request=self.receiver_areas.exists())

    @property
    def success_count(self):
        try:
            return self.result['request_count'] or self.check_requested_count()
        except:
            pass
        return self.check_requested_count()

    def check_requested_count(self):
        if not hasattr(self, '_requested_count'):
            only_if_allowed = False if self.receiver_user else True
            cnt = self.target_users.get_code_and_push_tokens(only_if_allowed=only_if_allowed,
                                                              is_mission_request=self.receiver_areas.exists(),
                                                              return_count=True)
            setattr(self, '_requested_count', cnt)
        return self._requested_count

    def send_worker_start(self):
        if self.send_method == 'sms':
            self.send()
            worker = threading.Thread(target=sms_result_check_worker, args=(self,))
            worker.start()
            return True
        return False

    def send_or_relay(self, lazy=False):
        if self.send_method == 'sms':
            if settings.NOTIFICATION['relay_url']:
                requests.get(settings.NOTIFICATION['relay_url'] + str(self.id) + '/')
            else:
                self.send_worker_start()
            return self

        if self.send_method == 'kakao':
            if settings.NOTIFICATION['relay_url']:
                requests.get(settings.NOTIFICATION['relay_url'] + str(self.id) + '/')
            else:
                self.send()
            return self

        if self.send_method == 'push':
            if lazy:
                if self.tasker_id:
                    # 태스커에 의한 lazy 전송의 경우 별도 스크립트로 처리
                    return self
                queue = QueueRegisterer()
                if queue.push(self.id):
                    return self

            # cmd('nohup ./venv/bin/python3 manage.py notify push %s' % obj.id)
            self.send()
            return self

        if self.send_method == 'email':
            self.send()
            return self

    def send(self, commit=True):
        if self.send_method == 'sms':
            self.result = sms.send(self.receiver_identifier, self.content, self.id)
            if self.result and 'code' in self.result and self.result['code'] == '200':
                if self.requested_datetime:
                    self.retried_datetime = timezone.now()
                else:
                    self.requested_datetime = timezone.now()
            else:
                self.failed_datetime = timezone.now()

        if self.send_method == 'push':
            # self.result = push.send(self.subject, self.content, self.data, tokens=self.tokens)
            self.result = push.send_by_obj(self) if commit else push.no_send_by_obj(self)

            if self.requested_datetime:
                self.retried_datetime = timezone.now()
            else:
                self.requested_datetime = timezone.now()

        if self.send_method == 'kakao':
            self.result = kakao.send(self.receiver_identifier, self.data_type, self.subject, self.content, self.id)
            if self.result and 'code' in self.result and self.result['code'] == '200':
                if self.requested_datetime:
                    self.retried_datetime = timezone.now()
                else:
                    self.requested_datetime = timezone.now()
            else:
                self.failed_datetime = timezone.now()

        if self.send_method == 'email':
            msg = EmailMultiAlternatives(
                self.subject,
                self.content,
                self.created_user.email if self.created_user else settings.DEFAULT_FROM_EMAIL,
                [self.receiver_identifier]
            )
            # todo: html 메세지 사용이 필요한 시점에 반드시 수정할 것.
            # if self.data:
            #     msg.attach_alternative(self.data, "text/html")
            if self.requested_datetime:
                self.retried_datetime = timezone.now()
            else:
                self.requested_datetime = timezone.now()
            result = msg.send()
            if result:
                self.result = {
                    'request_count': 1,
                    'failure_count': 0,
                    'success_count': 1,
                }
                self.done_datetime = timezone.now()
            else:
                self.result = {
                    'request_count': 1,
                    'failure_count': 1,
                    'success_count': 0,
                }
                self.failed_datetime = timezone.now()

        self.save()

    def read(self, code):
        if 'read' not in self.result:
            self.result['read'] = [code]
            self.save()
            return True
        elif code not in self.result['read']:
            self.result['read'].append(code)
            self.save()
            return True
        return False

    def did_action(self, code):
        if 'did_action' not in self.result:
            self.result['did_action'] = [code]
            if not self.read(code):
                self.save()
            return True
        elif code not in self.result['did_action']:
            self.result['did_action'].append(code)
            if not self.read(code):
                self.save()
            return True
        return False

    def check_result(self):
        if not self.result:
            return None
        if self.state in ('read', 'done', 'created'):
            return False

        if self.send_method == 'sms':
            self.result.update(sms.check(self.id))
            try:
                if self.result['code'] == '200' and self.result['data']['resultCode'] == '100':
                    self.done_datetime = timezone.now()
                else:
                    self.failed_datetime = timezone.now()
            except: pass

        if self.send_method == 'push':
            pass

        self.save()

    def get_sender_display(self):
        return self.sender
    get_sender_display.short_description = '발신자'
    get_sender_display.admin_order_field = 'created_user'

    @property
    def state(self):
        if self.read_datetime:
            return 'read'
        if self.done_datetime:
            return 'done'
        if self.requested_datetime:
            if self.retried_datetime:
                return 'retried' if self.retried_datetime > self.failed_datetime else 'failed'
            if self.failed_datetime:
                return 'failed'
            return 'requested'
        return 'created'

    @property
    def get_state_display(self):
        return NOTIFICATION_STATUS[self.state]

    @property
    def state_with_datetime(self):
        dt = getattr(self, '%s_datetime' % self.state)
        return '[%s] %s' % (self.get_state_display, localize(dt))


class TaskerQuerySet(models.QuerySet):
    """
    알림 태스커 쿼리셋
    """
    def cache_taskers(self):
        anyman.taskers = {}
        try:
            for t in self.filter(is_active=True).order_by('condition'):
                if t.condition in anyman.taskers:
                    anyman.taskers[t.condition].append(t)
                else:
                    anyman.taskers.update({t.condition: [t]})
        except:
            pass

    def get_active(self, condition=None, peoriod_only=False):
        today = timezone.now().date()
        qs = self.filter(is_active=True, start_date__lte=today, end_date__gte=today)
        if not peoriod_only:
            qs = qs | self.filter(is_active=True, start_date__isnull=True, end_date__isnull=True)
        if condition:
            qs = qs.filter(condition=condition)
        return qs

    def task(self, condition, request=None, user=None, obj=None, kwargs={}, data={}):
        # if condition in anyman.taskers:
        user = user or request.user
        notifications = []
        for t in self.get_active(condition=condition):
            notifications.append(t.send(user, obj=obj, kwargs=kwargs, additional_data=data))
        notifications = [n for n in notifications if n]
        return  notifications[0] if notifications else None

    def check_and_run_peoriod_task(self, condition, user):
        for t in self.get_active(condition, peoriod_only=True):
            if condition == '2nd_mission_done_in_peoriod':
                if user.get_mission_done_in_peoriod(t.start_date, t.end_date).count() == 2:
                    t.send(user)


class Tasker(models.Model):
    """
    알림 태스커
    """
    condition = models.CharField('조건', choices=CONDITIONS, max_length=100)
    push_title = models.CharField('푸시 제목', max_length=100, blank=True, help_text='다음 항목을 사용할 수 있습니다: ' + ', '.join(['{%s}' % f for f in SimpleProfileSerializer.Meta.fields] + ['{coupon_name} (쿠폰 만료 조건시)', '{coupon_expire} (쿠폰 만료 조건시)']))
    push_content = models.TextField('푸시 내용', blank=True, help_text='다음 항목을 사용할 수 있습니다: ' + ', '.join(['{%s}' % f for f in SimpleProfileSerializer.Meta.fields] + ['{coupon_name} (쿠폰 만료 조건시)', '{coupon_expire} (쿠폰 만료 조건시)']))
    email_title = models.CharField('이메일 제목', max_length=100, blank=True, help_text='다음 항목을 사용할 수 있습니다: ' + ', '.join(['{%s}' % f for f in SimpleProfileSerializer.Meta.fields] + ['{coupon_name} (쿠폰 만료 조건시)', '{coupon_expire} (쿠폰 만료 조건시)']))
    email_content = models.TextField('이메일 내용', blank=True, help_text='다음 항목을 사용할 수 있습니다: ' + ', '.join(['{%s}' % f for f in SimpleProfileSerializer.Meta.fields] + ['{coupon_name} (쿠폰 만료 조건시)', '{coupon_expire} (쿠폰 만료 조건시)']))
    kakao_template_code = models.CharField('카카오 알림톡 템플릿 코드', blank=True, max_length=30)
    kakao_content = models.TextField('카카오 알림톡 내용', blank=True, help_text='다음 항목을 사용할 수 있습니다: ' + ', '.join(['{%s}' % f for f in SimpleProfileSerializer.Meta.fields] + ['{coupon_name} (쿠폰 만료 조건시)', '{coupon_expire} (쿠폰 만료 조건시)']))
    sms_content = models.TextField('SMS 내용', blank=True, help_text='다음 항목을 사용할 수 있습니다: ' + ', '.join(['{%s}' % f for f in SimpleProfileSerializer.Meta.fields] + ['{coupon_name} (쿠폰 만료 조건시)', '{coupon_expire} (쿠폰 만료 조건시)']))
    auto_issue_coupon = models.ForeignKey('payment.CouponTemplate', verbose_name='자동발급 쿠폰', null=True, blank=True,
                                          on_delete=models.SET_NULL, related_name='taskers')
    start_date = models.DateField('활성화 시작일', blank=True, null=True)
    end_date = models.DateField('활성화 종료일', blank=True, null=True)
    is_active = models.BooleanField('활성화', blank=True, default=True)
    is_lazy = models.BooleanField('lazy process', blank=True, default=False)

    objects = TaskerQuerySet.as_manager()

    class Meta:
        verbose_name = '알림 태스커'
        verbose_name_plural = '알림 태스커'

    def __str__(self):
        return '%s [%s]' % (self.get_condition_display(), '/'.join(self.send_methods))

    def save(self, *args, **kwargs):
        if bool(self.start_date) != bool(self.end_date):
            raise ValidationError('활성화 시작일과 종료일은 둘 다 입력하거나 둘다 입력하지 않아야 함.')
        if self.start_date and self.start_date > self.end_date:
            raise ValidationError('활성화 시작일이 종료일보다 빨라야 함.')

        # if self.is_active:
        #     same_conditions = Tasker.objects.filter(condition=self.condition, is_active=True).exclude(id=self.id)
        #     if same_conditions.exists():
        #         same_conditions.update(is_active=False)
        saved = super(Tasker, self).save(*args, **kwargs)
        Tasker.objects.cache_taskers()
        return saved

    @property
    def send_methods(self):
        rtn = []
        if self.push_title and self.push_content:
            rtn.append('push')
        if self.kakao_template_code and self.kakao_content:
            rtn.append('kakao')
        if self.email_title and self.email_content:
            rtn.append('email')
        if self.sms_content:
            rtn.append('sms')
        return rtn

    @property
    def last_notification(self):
        return self.notifications.last()

    def get_condition_display(self):
        return dict(CONDITIONS)[self.condition]

    def render(self, user, kwargs={}):
        try:
            data = SimpleProfileSerializer(user).data
            setattr(self, 'push_title_rendered', self.push_title.format(**data, **kwargs))
            setattr(self, 'push_content_rendered', self.push_content.format(**data, **kwargs))
            setattr(self, 'email_title_rendered', self.email_title.format(**data, **kwargs))
            setattr(self, 'email_content_rendered', self.email_content.format(**data, **kwargs))
            setattr(self, 'kakao_content_rendered', self.kakao_content.format(**data, **kwargs))
            setattr(self, 'sms_content_rendered', self.sms_content.format(**data, **kwargs))
        except:
            return False
        return True

    def send(self, user, obj=None, kwargs={}, additional_data={}):
        if not self.render(user, kwargs):
            return False
        if self.auto_issue_coupon:
            self.auto_issue_coupon.issue([user], tasker=self)
        rtn = None
        for send_method in self.send_methods:
            send = getattr(self, 'send_%s' % send_method, None)
            if send and callable(send):
                rtn = send(user, additional_data)
        return rtn

    def send_push(self, user, additional_data={}):
        data = {}
        if self.condition in CONDITION_PUSH_DATA:
            data.update(CONDITION_PUSH_DATA[self.condition])
        if self.auto_issue_coupon:
            data['page'] = 'MYPAGE_HISTORY_COUPON'
        data.update(additional_data)
        try:
            return Notification.objects.push(
                user,
                self.push_title_rendered,
                self.push_content_rendered,
                data=data,
                tasker=self,
                lazy=self.is_lazy
            )
        except:
            return None

    def send_kakao(self, user, additional_data={}):
        try:
            return Notification.objects.kakao(
                user,
                self.kakao_template_code,
                self.condition,
                self.kakao_content_rendered,
                tasker=self
            )
        except:
            return None

    def send_sms(self, user, additional_data={}):
        try:
            return Notification.objects.sms(
                user,
                self.sms_content_rendered,
                tasker=self
            )
        except:
            return None

    def send_email(self, user, additional_data={}):
        try:
            return Notification.objects.email(
                user,
                self.email_title_rendered,
                self.email_content_rendered,
                tasker=self
            )
        except:
            return None
