import json
import requests
import time
import logging

import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging, db, firestore
from firebase_admin._messaging_utils import Aps, APNSPayload, APNSConfig, AndroidConfig, AndroidNotification

from django.conf import settings
from django.utils import timezone

from common.utils import SingletonOptimizedMeta
from accounts.models import User, LoggedInDevice


class FirebaseAdmin(metaclass=SingletonOptimizedMeta):
    """
    파이어베이스 초기화
    """
    def __init__(self):
        self.cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_FILE)
        self.app = firebase_admin.initialize_app(self.cred, settings.FIREBASE_OPTIONS, settings.FIREBASE_APP)


firebase = FirebaseAdmin()

logger = logging.getLogger('django')


class SMSHandler(metaclass=SingletonOptimizedMeta):
    """
    sms 처리기
    """
    api_key = None
    default_sender = None
    headers = {}
    must_send = True

    def __init__(self):
        self.api_key = settings.SMS_API_KEY
        self.default_sender = settings.SMS_SENDER_NUMBER
        self.headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'sejongApiKey': settings.SMS_API_KEY,
        }
        self.must_send = getattr(settings, 'SMS_SEND', True)

    def send(self, receiver_number, content, obj_id, sender_number=''):
        """sms 전송"""
        if not self.must_send:
            return {}
        payload = {
            'callback': sender_number or self.default_sender,
            'contents': content,
            'receiverTelNo': receiver_number,
            'userKey': obj_id,
        }
        response = requests.post(settings.SMS_SEND_URL, headers=self.headers, params=payload)
        result = json.loads(response.text)
        if 'sendCode' in result:
            result.pop('sendCode')
        return result

    def check(self, obj_id):
        """sms 전송결과 확인"""
        payload = {
            'sendCode': obj_id
        }
        response = requests.get(settings.SMS_RESULT_URL, headers=self.headers, params=payload)
        result = json.loads(response.text)
        if 'sendCode' in result:
            result.pop('sendCode')
        return result


class KakaoHandler(metaclass=SingletonOptimizedMeta):
    """
    카카오 알림톡 처리기
    """
    api_key = None
    default_id = None
    default_sender = None
    headers = {}
    must_send = True

    def __init__(self):
        self.api_key = settings.SMS_API_KEY
        self.default_id = settings.KAKAO_PLUS_ID
        self.default_sender = settings.KAKAO_SENDER_KEY
        self.headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'sejongApiKey': settings.SMS_API_KEY,
        }
        self.must_send = getattr(settings, 'KAKAO_SEND', True)

    def send(self, receiver_number, template_code, title, content, obj_id, sender_number=''):
        """알림톡 전송"""
        if not self.must_send:
            return {}
        payload = {
            'plusFriendId': self.default_id,
            'senderKey': self.default_sender,
            'templateCode': template_code,
            'title': title,
            'contents': content,
            'receiverTelNo': receiver_number,
            'userKey': obj_id,
        }
        response = requests.post(settings.KAKAO_SEND_URL, headers=self.headers, params=payload)
        result = json.loads(response.text)
        if 'sendCode' in result:
            result.pop('sendCode')
        return result

    def check(self, obj_id):
        """알림톡 전송결과 확인"""
        payload = {
            'sendCode': obj_id
        }
        response = requests.get(settings.SMS_RESULT_URL, headers=self.headers, params=payload)
        result = json.loads(response.text)
        if 'sendCode' in result:
            result.pop('sendCode')
        return result


class PushHandler(metaclass=SingletonOptimizedMeta):
    """
    push 처리기
    """
    slice_count = 500

    def __init__(self, apns=None, android=None):
        self.app = firebase.app
        self.apns = apns or APNSConfig(headers={'apns-priority': '5'}, payload=APNSPayload(aps=Aps(sound='notification.caf')))
        self.android = android or AndroidConfig(notification=AndroidNotification(
            sound='notification', channel_id='notification', priority='high'
        ))

    def send_by_obj(self, obj):
        """알림 오브젝트를 통해 전송 ;; condition은 적용하지 않음"""
        code_and_tokens = obj.code_and_tokens
        if not code_and_tokens:
            logger.error('[PushHandler] 대상 유져가 없음')
            # raise ValueError('No target users.')
            return self._initialize_response()

        # 중복제거 방어코드 추가
        code_and_tokens = list(set(code_and_tokens))

        notification = messaging.Notification(title=obj.subject, body=obj.content)
        response = self._initialize_response(len(obj.code_and_tokens))
        i = 0
        while code_and_tokens[i: i + self.slice_count]:
            sliced_code_and_tokens = code_and_tokens[i: i + self.slice_count]
            sliced_tokens = [ct[1] for ct in sliced_code_and_tokens]
            message = messaging.MulticastMessage(
                tokens=sliced_tokens,
                notification=notification,
                apns=self.apns,
                android=self.android,
                data=obj.data
            )
            try:
                result = messaging.send_multicast(message, app=self.app)
            except:
                logger.info('multiple push failed : ("%s", "%s", %s)' % (notification.title, notification.body, obj.data))
            else:
                result_ids = []
                unregistered = []
                sender_id_mismatch = []
                for r, ct in zip(result.responses, sliced_code_and_tokens):
                    if r.success:
                        result_ids.append(ct[0])
                    else:
                        try:
                            j = r.exception.http_response.json()
                            result_ids.append(list(ct) + list([e['errorCode'] for e in j['error']['details']]))
                        except:
                            result_ids.append(None)
                        else:
                            if 'UNREGISTERED' in result_ids[-1]:
                                unregistered.append(ct)
                            if 'SENDER_ID_MISMATCH' in result_ids[-1]:
                                sender_id_mismatch.append(ct)
                response = self._add_response(
                    response,
                    failure_count=result.failure_count,
                    success_count=result.success_count,
                    data=result_ids,
                    unregistered=unregistered,
                    sender_id_mismatch=sender_id_mismatch
                )
            i += self.slice_count

        self.handle_unregistered([u[1] for u in response['unregistered']])
        self.handle_sender_id_mismatch([m[1] for m in response['sender_id_mismatch']])

        # 푸시 요청된 회원코드 저장
        data = response.pop('data')
        response['data'] = []
        codes = []
        for requested in data:
            if type(requested) == str:
                codes.append(requested)
            else:
                response['data'].append(requested)
        response['requested'] = list(set(codes))
        return response

    def no_send_by_obj(self, obj):
        if not obj.target_users and not obj.code_and_tokens:
            logger.error('[PushHandler] 대상 유져가 없음')
            # raise ValueError('No target users.')
            return self._initialize_response()

        response = self._initialize_response(len(obj.code_and_tokens))

        # 요청된 회원코드 저장
        codes= []
        for code, _ in obj.code_and_tokens:
            codes.append(code)
        response['requested'] = list(set(codes))
        return response


    def send(self, title, content, data, tokens=list(), condition=''):
        """전송"""
        notification = messaging.Notification(title=title, body=content)
        if not tokens and not condition:
            logger.error('[PushHandler] 토큰 또는 조건이 없음')
            raise ValueError('No tokens and condition.')

        if condition:
            return self._send_condition(condition, notification, data)

        request_count = len(tokens)

        if request_count is 1:
            return self._send_single(tokens[0], notification, data)
        else:
            return self._send_multi(tokens, notification, data)

    def _send_single(self, token, notification, data):
        response = self._initialize_response(1)
        message = messaging.Message(
            token=token,
            notification=notification,
            apns=self.apns,
            data=data
        )
        try:
            result = messaging.send(message, app=self.app)
        except:
            logger.info('single push failed : ("%s", "%s", %s)' % (notification.title, notification.body, data))
            result = None
        return self._add_response(response, data=[result] if result else [])

    def _send_multi(self, tokens, notification, data):
        response = self._initialize_response(len(tokens))
        i = 0
        while tokens[i: i + self.slice_count]:
            sliced_tokens = tokens[i: i + self.slice_count]
            message = messaging.MulticastMessage(
                tokens=sliced_tokens,
                notification=notification,
                apns=self.apns,
                android=self.android,
                data=data
            )
            try:
                result = messaging.send_multicast(message, app=self.app)
            except:
                logger.info('multiple push failed : ("%s", "%s", %s)' % (notification.title, notification.body, data))
            else:
                result_ids = []
                unregistered = []
                sender_id_mismatch = []
                for r, t in zip(result.responses, sliced_tokens):
                    if r.success:
                        # result_ids.append(r.message_id)
                        result_ids.append(t)
                    else:
                        try:
                            j = r.exception.http_response.json()
                            result_ids.append([e['errorCode'] for e in j['error']['details']])
                        except:
                            result_ids.append(None)
                        else:
                            if 'UNREGISTERED' in result_ids[-1]:
                                unregistered.append(t)
                            if 'SENDER_ID_MISMATCH' in result_ids[-1]:
                                sender_id_mismatch.append(t)
                response = self._add_response(
                    response,
                    failure_count=result.failure_count,
                    success_count=result.success_count,
                    data=result_ids,
                    unregistered=unregistered,
                    sender_id_mismatch=sender_id_mismatch
                )
            i += self.slice_count

        self.handle_unregistered(response['unregistered'])
        self.handle_sender_id_mismatch(response['sender_id_mismatch'])
        return response

    def handle_unregistered(self, unregistered):
        for device in LoggedInDevice.objects.get_by_tokens(unregistered):
            device.logout()
            logger.warning('%s <%s> 로그아웃 처리 (푸시 시도했으나, 등록 토큰 유효하지 않음)' % (str(device.user), str(device)))

    def handle_sender_id_mismatch(self, sender_id_mismatch):
        for device in LoggedInDevice.objects.get_by_tokens(sender_id_mismatch):
            device.logout()
            logger.warning('%s <%s> 로그아웃 처리 (푸시 시도했으나, 등록 토큰 발신자와 매치되지 않음)' % (str(device.user), str(device)))

    def _send_condition(self, condition, notification, data):
        message = messaging.Message(
            condition=condition,
            notification=notification,
            apns=self.apns,
            android=self.android,
            data=data
        )
        return messaging.send(message, app=firebase.app)

    def _initialize_response(self, request_count=0):
        return {
            'request_count': request_count,
            'failure_count': 0,
            'success_count': 0,
            'unregistered': [],
            'sender_id_mismatch': [],
            'data': [],
            'read': [],
            'did_action': [],
        }

    def _add_response(self, response, request_count=0, failure_count=0, success_count=0, data=list(),
                      unregistered=list(), sender_id_mismatch=list(), **kwargs):
        response['request_count'] += request_count
        response['failure_count'] += failure_count
        response['success_count'] += success_count
        response['unregistered'] += unregistered
        response['sender_id_mismatch'] += sender_id_mismatch
        response['data'] += data
        response.update(kwargs)
        return response


# class FirebaseRealtimeChatHandler(metaclass=SingletonOptimizedMeta):
#     """
#     애니톡 처리기 - 실시간데이터베이스
#     """
#     default_reference = '/anytalk'
#     _reference = '/anytalk'
#
#     def __init__(self):
#         self.cred = credentials.Certificate('web/conf/googleserviceaccount.json')
#         self.app = firebase_admin.initialize_app(self.cred, settings.FIREBASE_OPTIONS)
#
#     def get(self, ref):
#         if ref.startswith('/'):
#             self._reference = ref
#         else:
#             self._reference = self.default_reference + '/' + ref
#         return db.reference(self._reference, self.app).get()
#
#     def get_rooms(self, bid_id=None):
#         """채팅방 목록 가져오기"""
#         ref = 'room'
#         if bid_id:
#             ref += '/' + str(bid_id)
#         return self.get(ref)
#
#     def get_chats(self, bid_id):
#         """bid 기준 대화내용 가져오기"""
#         ref = 'message'
#         if bid_id:
#             ref += '/' + str(bid_id)
#         return self.get(ref)
#
#     def get_chats_display(self, bid_id):
#         users = {}
#         lines = []
#         chats = self.get_chats(bid_id)
#         if chats:
#             for row in chats.values():
#                 user_code = row.pop('user_code')
#                 if user_code in users:
#                     user = users[user_code]
#                 else:
#                     user = User.objects.get(code=user_code)
#                 sent_datetime = timezone.datetime.fromtimestamp(row.pop('timestamp') / 1000)
#                 row.update({'user': user, 'sent_datetime': sent_datetime})
#                 lines.append(row)
#         return lines


class FirebaseHandler:
    """
    Firestore 처리기
    """
    ref = None

    def __init__(self):
        self.firebase = firebase
        self.db = firestore.client(self.firebase.app)

    def get_document(self, id):
        return self.ref.document(str(id))
    #
    # def get(self, id):
    #     return self.get_document(id).get().to_dict()

    def set(self, id, kwargs, is_update=True):
        document = self.get_document(id)
        document.set(kwargs, merge=is_update)

    def update(self, id, kwargs):
        document = self.get_document(id)
        try:
            document.update(kwargs)
            return True
        except:
            return False


class FirebaseFirestoreChatHandler(FirebaseHandler):
    """
    애니톡 처리기 - Firestore
    """
    users = {}

    def __init__(self):
        super(FirebaseFirestoreChatHandler, self).__init__()
        self.ref = self.db.collection('anytalk_room')

    def get(self, bid_id):
        document = self.get_document(bid_id)
        return {
            'info': document.get().to_dict(),
            'chat': [self._handle_message(m.to_dict()) for m in list(document.collection('messages').order_by('timestamp').get())]
        }

    def open(self, bid):
        mission = bid._mission
        if mission.is_web:
            return None
        kwargs = {
            'users': [
                {
                    'user_code': mission.user.code,
                    'user_type': 'user',
                    'unread_message_count': 0,
                    'user_name': mission.user.username,
                }, {
                    'user_code': bid.helper.user.code,
                    'user_type': 'helper',
                    'unread_message_count': 0,
                    'user_name': bid.helper.user.username,
                    'profile_photo': bid.helper.profile_image_url,
                }
            ],
            'timestamp': firestore.firestore.SERVER_TIMESTAMP,
            'last_message': '미션매칭 성공',
            'mission_id': mission.id,
            'mission_content': mission.content,
            'mission_area': mission.final_address_area_id,
            'mission_type': mission.mission_type_id,
            'mission_code': mission.code,
            'active_due': bid.active_due.timestamp(),
            'contain_user_ids': [mission.user.code, bid.helper.user.code],
            'files': [],
            'is_end': False,
            'is_multi': mission.is_multi
        }
        data = self.get(bid.id)
        if data['info']:
            if 'is_end' in data['info'] and data['info']['is_end'] == True:
                self.reopen(bid.id)
                return True
        else:
            self.set(bid.id, kwargs)
            return True
        return False

    def close(self, bid_id):
        self.update(bid_id, {'is_end': True})

    def reopen(self, bid_id):
        self.update(bid_id, {'is_end': False})

    def _handle_message(self, msg_dict):
        # user
        user_code = msg_dict.pop('user_code')
        if user_code not in self.users:
            try:
                self.users[user_code] = User.objects.get(code=user_code)
            except:
                self.users[user_code] = user_code

        # datetime
        sent_datetime = msg_dict.pop('timestamp')
        if type(sent_datetime) is int:
            sent_datetime = timezone.datetime.fromtimestamp(sent_datetime / 1000)

        msg_dict.update({'user': self.users[user_code], 'sent_datetime': sent_datetime})
        return msg_dict
