from django.core.management.base import BaseCommand

from accounts.models import User
from notification.models import Tasker


class Command(BaseCommand):
    """
    기본 태스커 초기화
    """

    def handle(self, *args, **options):
        data = {
            'test': {
                'push_title': '애니맨 테스트',
                'push_content': '[푸쉬 테스트] {username}님, 안녕하세요. 애니맨입니다. 이 메세지는 테스트 메세지입니다.',
            },
            'helper_accepted': {
                'push_title': '{username} 헬퍼님, 반가워요!',
                'push_content': '애니맨 헬퍼가 되셨습니다.\n미션 목록에서 수행할 미션을 찾아서 입찰해보세요!',
                'email_title': '{username} 헬퍼님 반갑습니다!',
                'email_content': '안녕하세요! 애니맨입니다.\n\n헬퍼로 승인되셨습니다.\n\n이제부터 수행할 수 있는 미션을 찾아볼까요?',
                'sms_content': '{username} 님, 애니맨 헬퍼가 되셨습니다. 다양한 미션을 수행해보세요.'
            },
            'helper_rejected': {
                'push_title': '{username} 님, 헬퍼신청 승인이 거부되었습니다.',
                'push_content': '다음의 내용을 다시 확인해서 신청해주세요.\n{reason}',
            },
            'reviewed_from_helper': {
                'push_title': '리뷰 등록',
                'push_content': '{sender} 헬퍼님이 {username}님에게 리뷰를 남겼습니다.\n{stars}',
            },
            'reviewed_from_customer': {
                'push_title': '리뷰 등록',
                'push_content': '{sender} 고객님이 {username}님에게 리뷰를 남겼습니다.\n{stars}',
            },

            #    'mission_requested': {
            #        'push_title': '{} 미션 발생! {}',
            #        'push_content': '',
            #    },

            'mission_bidded': {
                'push_title': '헬퍼 입찰',
                'push_content': '헬퍼님이 입찰했어요! 요청에 입찰한 헬퍼를 확인해주세요.\n입찰한 헬퍼 : {count}명',
            },
            'assigned_mission_bidded': {
                'push_title': '지정헬퍼 입찰',
                'push_content': '지정하신 {sender} 헬퍼님이 입찰했어요! 견적을 확인하고 진행여부를 결정해주세요.',
            },
            'assigned_mission_requested': {
                'push_title': '지정 미션 도착',
                'push_content': '{sender} 님이 회원님에게 미션을 요청했습니다.\n지금 바로 요청내용을 확인 후 입찰해주세요.',
            },
            'assigned_mission_canceled': {
                'push_title': '미션 취소',
                'push_content': '{sender} 님이 회원님에게 요청한 미션이 취소되었습니다.',
            },
            'bidded_mission_canceled': {
                'push_title': '미션 취소',
                'push_content': '입찰하신 "{mission}" 미션이 취소되었습니다.',
            },
            'select_helper_before_timeout': {
                'push_title': '헬퍼를 선택해주세요',
                'push_content': '입찰 시간이 곧 종료됩니다. 입찰중인 {count}명의 헬퍼 중에서 낙찰자를 선택해주세요. 선택하지 않으시면 의뢰하신 서비스는 자동으로 취소됩니다.',
            },

            #    'bidded_mission_failed': {
            #        'push_title': '입찰하신 "{}" 미션이 종료되었습니다.',
            #        'push_content': '',
            #    },

            'bidded_mission_matched': {
                'push_title': '매칭 성공',
                'push_content': '"{mission}" 미션이 매칭되었습니다. 미션을 진행해주세요.',
            },
            'mission_timeout_canceled': {
                'push_title': '입찰시간 초과',
                'push_content': '요청하신 미션은 입찰 시간 초과로 종료되었습니다. 다시 요청할까요?',
            },
            'mission_timeout_canceled_with_bidding': {
                'push_title': '입찰시간 초과',
                'push_content': '입찰 시간 내에 헬퍼를 선택하지 않으셨습니다. 입찰은 자동으로 종료되었습니다. 다시 요청할까요?',
            },
            'rewarded_helper_recommend_done_first': {
                'push_title': '캐시 적립',
                'push_content': '친구의 첫 요청 미션이 완료되어 {amount} 캐시가 적립되었습니다.',
            },
            'rewarded_customer_recommend_done_first': {
                'push_title': '포인트 적립',
                'push_content': '친구의 첫 요청 미션이 완료되어 {amount} 포인트가 적립되었습니다.',
            },
            'rewarded_helper_recommend_done': {
                'push_title': '캐시 적립',
                'push_content': '친구의 요청 미션이 완료되어 {amount} 캐시가 적립되었습니다.',
            },
            'rewarded_customer_recommend_done': {
                'push_title': '포인트 적립',
                'push_content': '친구의 요청 미션이 완료되어 {amount} 포인트가 적립되었습니다.',
            },

            'cancel_interaction_requested_by_helper': {
                'push_title': '취소 요청',
                'push_content': '{sender} 헬퍼님이 "{mission}" 미션의 취소를 요청했습니다.',
            },
            'cancel_interaction_requested_by_customer': {
                'push_title': '취소 요청',
                'push_content': '{sender} 고객님이 "{mission}" 미션의 취소를 요청했습니다.',
            },
            'due_interaction_requested_by_helper': {
                'push_title': '수행일시 변경 요청',
                'push_content': '{sender} 헬퍼님이 "{mission}" 미션의 수행 날짜/시간의 변경을 요청했습니다.',
            },
            'due_interaction_requested_by_customer': {
                'push_title': '수행일시 변경 요청',
                'push_content': '{sender} 고객님이 "{mission}" 미션의 수행 날짜/시간의 변경을 요청했습니다.',
            },
            'done_interaction_requested_by_helper': {
                'push_title': '수행완료 요청',
                'push_content': '{sender} 헬퍼님이 "{mission}" 미션의 수행완료를 요청했습니다.',
            },
            'done_interaction_requested_by_customer': {
                'push_title': '수행완료 요청',
                'push_content': '{sender} 고객님이 "{mission}" 미션의 수행완료를 요청했습니다.',
            },
            'cancel_interaction_canceled_by_helper': {
                'push_title': '취소 요청의 취소',
                'push_content': '{sender} 헬퍼님이 "{mission}" 미션 취소 요청을 취소했습니다. (계속 진행됩니다)',
            },
            'cancel_interaction_canceled_by_customer': {
                'push_title': '취소 요청의 취소',
                'push_content': '{sender} 고객님이 "{mission}" 미션 취소 요청을 취소했습니다. (계속 진행됩니다)',
            },
            'due_interaction_canceled_by_helper': {
                'push_title': '수행일시 변경의 취소',
                'push_content': '{sender} 헬퍼님이 "{mission}" 미션의 수행 날짜/시간 변경을 취소했니다.',
            },
            'due_interaction_canceled_by_customer': {
                'push_title': '수행일시 변경의 취소',
                'push_content': '{sender} 고객님이 "{mission}" 미션의 수행 날짜/시간 변경을 취소했니다.',
            },
            'done_interaction_canceled_by_helper': {
                'push_title': '수행완료 요청 취소',
                'push_content': '{sender} 헬퍼님이 "{mission}" 미션의 완료요청을 취소했습니다.',
            },
            'done_interaction_canceled_by_customer': {
                'push_title': '수행완료 요청 취소',
                'push_content': '{sender} 고객님이 "{mission}" 미션의 완료요청을 취소했습니다.',
            },
            'cancel_interaction_rejected_by_helper': {
                'push_title': '취소 요청 거절',
                'push_content': '{sender} 헬퍼님이 "{mission}" 미션취소 요청을 거절했습니다.',
            },
            'cancel_interaction_rejected_by_customer': {
                'push_title': '취소 요청 거절',
                'push_content': '{sender} 고객님이 "{mission}" 미션취소 요청을 거절했습니다.',
            },
            'due_interaction_rejected_by_helper': {
                'push_title': '수행일시 변경 거절',
                'push_content': '{sender} 헬퍼님이 "{mission}" 미션의 수행 날짜/시간 변경을 거절했습니다.',
            },
            'due_interaction_rejected_by_customer': {
                'push_title': '수행일시 변경 거절',
                'push_content': '{sender} 고객님이 "{mission}" 미션의 수행 날짜/시간 변경을 거절했습니다.',
            },
            'done_interaction_rejected_by_helper': {
                'push_title': '수행완료 요청 거절',
                'push_content': '{sender} 헬퍼님이 "{mission}" 미션의 완료요청을 거절했습니다.',
            },
            'done_interaction_rejected_by_customer': {
                'push_title': '수행완료 요청 거절',
                'push_content': '{sender} 고객님이 "{mission}" 미션의 완료요청을 거절했습니다.',
            },
            'cancel_interaction_accepted_by_helper': {
                'push_title': '취소 요청 수락',
                'push_content': '"{mission}" 미션이 취소되었습니다.',
            },
            'cancel_interaction_accepted_by_customer': {
                'push_title': '취소 요청 수락',
                'push_content': '"{mission}" 미션이 취소되었습니다.',
            },
            'due_interaction_accepted_by_helper': {
                'push_title': '수행일시 변경 수락',
                'push_content': '"{mission}" 미션의 수행 날짜/시간이 변경되었습니다.',
            },
            'due_interaction_accepted_by_customer': {
                'push_title': '수행일시 변경 수락',
                'push_content': '"{mission}" 미션의 수행 날짜/시간이 변경되었습니다.',
            },
            'done_interaction_accepted_by_helper': {
                'push_title': '수행완료',
                'push_content': '"{mission}" 미션이 완료 처리되었습니다. 리뷰를 작성하면 추가 포인트가 지급됩니다.',
            },
            'done_interaction_accepted_by_customer': {
                'push_title': '수행완료',
                'push_content': '"{mission}" 미션이 완료 처리되었습니다. 리뷰를 작성하면 추가 캐시가 지급됩니다.',
            },

            # web
            'web_requested': {
                'sms_content': '[애니맨] 견적 요청이 완료되었습니다.\n\n{url}',
            },
            'web_bidded': {
                'sms_content': '[애니맨] 견적한 헬퍼를 확인해주세요. 견적한 헬퍼 : {count}명\n\n{url}',
            },
            'web_select_helper_before_timeout': {
                'sms_content': '[애니맨] 입찰 시간이 곧 종료됩니다.\n입찰중인 {count}명의 헬퍼 중에서 낙찰자를 선택해주세요\n헬퍼를 선택하지 않으시면 의뢰하신 서비스는 자동으로 취소됩니다.\n\n{url}',
            },
            'web_mission_timeout_canceled': {
                'sms_content': '[애니맨] 요청하신 미션은 입찰 시간 초과로 종료되었습니다.',
            },
            'web_mission_timeout_canceled_with_bidding': {
                'sms_content': '[애니맨] 입찰 시간 내에 헬퍼를 선택하지 않으셨습니다. 입찰은 자동으로 종료되었습니다.',
            },
            'web_cancel_interaction_requested_by_helper': {
                'sms_content': '[애니맨] 진행중인 "{mission}" 미션에 취소요청이 왔습니다.\n\n{url}',
            },
            'web_due_interaction_requested_by_helper': {
                'sms_content': '[애니맨] "{mission}" 미션의 수행 날짜/시간에 변경 요청이 왔습니다.\n\n{url}',
            },
            'web_done_interaction_requested_by_helper': {
                'sms_content': '[애니맨] "{mission}" 미션의 완료확정을 진행해주세요.\n\n{url}',
            },
            'web_cancel_interaction_canceled_by_helper': {
                'sms_content': '[애니맨] "{mission}" 미션취소 요청이 취소되었습니다.\n\n{url}',
            },
            'web_due_interaction_canceled_by_helper': {
                'sms_content': '[애니맨] "{mission}" 미션의 수행 날짜/시간 변경이 취소되었습니다.\n\n{url}',
            },
            'web_done_interaction_canceled_by_helper': {
                'sms_content': '[애니맨] "{mission}" 미션의 완료요청이 취소되었습니다.\n\n{url}',
            },
            'web_cancel_interaction_rejected_by_helper': {
                'sms_content': '[애니맨] "{mission}" 미션취소 요청이 거절되었습니다.\n\n{url}',
            },
            'web_due_interaction_rejected_by_helper': {
                'sms_content': '[애니맨] "{mission}" 미션의 수행 날짜/시간 변경이 거절되었습니다.\n\n{url}',
            },
            'web_done_interaction_rejected_by_helper': {
                'sms_content': '[애니맨] "{mission}" 미션의 완료요청이 거절되었습니다.\n\n{url}',
            },
            'web_cancel_interaction_accepted_by_helper': {
                'sms_content': '[애니맨] "{mission}" 미션이 취소되었습니다.\n\n{url}',
            },
            'web_due_interaction_accepted_by_helper': {
                'sms_content': '[애니맨] "{mission}" 미션의 수행 날짜/시간이 변경되었습니다.\n\n{url}',
            },
            'web_done_interaction_accepted_by_helper': {
                'sms_content': '[애니맨] "{mission}" 미션이 완료 처리되었습니다.\n\n{url}',
            },

            # System
            'regular_point_balance': {
                'push_title': '미사용 포인트 잔액 안내',
                'push_content': '{username} 님, 현재 사용하지 않은 포인트 잔액이 {balance}원 있습니다. 서비스 의뢰 시 언제든지 사용할 수 있습니다. 감사합니다.',
            },

        }

        conditions = Tasker.objects.values_list('condition', flat=True)
        for condition, item in data.items():
            if condition not in conditions:
                Tasker.objects.create(condition=condition, **item)
