import socket
from collections import OrderedDict

import requests
from bs4 import BeautifulSoup

from django.apps import apps
from django.conf import settings

from common.utils import SingletonOptimizedMeta


class KeywordWarning(metaclass=SingletonOptimizedMeta):
    """
    위험 키워드 체크
    """
    def __init__(self):
        try:  # 마이그레이션 오류 방지
            self.refresh()
        except:
            pass

    def refresh(self):
        self.warnings = {}
        self.words = {}
        model = apps.get_model('missions', 'DangerousKeyword')
        for obj in model.objects.all().prefetch_related('warning'):
            self.words[obj.text] = obj.warning_id
            if obj.warning_id not in self.warnings:
                self.warnings.update({obj.warning_id: obj.warning.description})

    def check(self, text):
        result = []
        for word, id in self.words.items():
            if word in text:
                result.append(self.warnings[id])
        return result


class KCTPacket(dict):
    """
    KCT 패킷
    """
    SIZE = 127
    COMPANY_ID = None
    _string = ''

    def __init__(self, string='', **kwargs):
        super(KCTPacket, self).__init__(**kwargs)
        if string and kwargs:
            raise ValueError('문자열이나 키/값 중 한가지만 입력해야 합니다.')
        self.COMPANY_ID = settings.KCT_COMPANY_ID
        # self.COMPANY_ID = 'anyman25'
        if string:
            if type(string) is bytes:
                string = string.decode()
            self._string = string
            self._from_packet_string()
        if kwargs:
            self.update(kwargs)

    def __str__(self):
        return self._to_packet_string()

    def __dict__(self):
        return self

    def __bytes__(self):
        return str(self).encode()

    def _get_default_packet_string(self):
        return OrderedDict((
            ('stx', '#'),
            ('packet_id', ' ' * 4),
            ('company_id', self.COMPANY_ID),
            ('system_id', ' ' * 3),
            ('sequence', ' ' * 10),
            ('result', ' ' * 2),
            ('method', '1'),
            ('safety_number', ' ' * 12),
            ('phone_number_1', ' ' * 12),
            ('phone_number_2', ' ' * 12),
            ('phone_number_3', ' ' * 12),
            ('_safety_number', ' ' * 12),
            ('_phone_number_1', ' ' * 12),
            ('_phone_number_2', ' ' * 12),
            ('_phone_number_3', ' ' * 12),
            ('use_flag', '1'),
            ('etx', '$'),
        ))

    def _to_packet_string(self):
        data = self._get_default_packet_string()
        packet_string = ''
        for key, val in data.items():
            if key in self:
                new_val = str(self[key])
                additional_length = len(val) - len(new_val)
                if additional_length < 0:
                    raise ValueError
                val = new_val + ' ' * additional_length
            packet_string += val
        if len(packet_string) != self.SIZE:
            raise ValueError('패킷 사이즈가 맞지않음')
        return packet_string

    def _from_packet_string(self):
        if len(self._string) != self.SIZE:
            raise ValueError('패킷 사이즈가 맞지않음')
        offset = 0
        data = self._get_default_packet_string()
        for key, val in data.items():
            length = len(val)
            data[key] = self._string[offset:offset + length].strip()
            offset += length
        self.update({key: val for key, val in data.items() if val})


class KCTSafetyNumber(metaclass=SingletonOptimizedMeta):
    """
    KCT 안심번호 핸들러
    """
    RESULT_CODES = {
        '00': '성공',
        '01': '패킷 길이 에러',
        '02': '정의되지않은 패킷 번호',
        '03': '사업자코드 에러',
        '04': '번호 할당 후 전송 요청',
        '05': '050 번호 prefix 맞지않음',
        '06': '050 번호 길이 맞지 않음',
        '07': '전화번호 형식이 맞지 않음',
        '08': '구분자 에러',
        '09': '번호 사용상태 오류 (Invalid Use Flag)',
        '10': '고객사 외부연동방식이 설정값과 다름',
        '11': '등록, 수정, 삭제 오류(DB오류)',
        '12': '지정되지 않은 050 번호',
        '13': '허용 TPS 초과',
        '14': '등록된 IP정보가 아닌 곳에서 로그인 요청',
    }
    sock = None
    _host = ''
    _port = ''
    fail_silently = True

    def __init__(self):
        self._host = settings.KCT_CONNECT_HOST
        self._port = settings.KCT_CONNECT_PORT
        # self._host = '112.140.147.113'
        # self._port = 60001

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self._host, self._port))

    def disconnect(self):
        self.sock.close()
        self.sock = None

    def get_error(self, result_code):
        if result_code in self.RESULT_CODES:
            return IOError(self.RESULT_CODES[result_code])
        return IOError('알 수 없는 오류 : %s' % result_code)

    def request(self, packet):
        if not self.sock:
            self.connect()
        connected = False
        tried = 0
        while connected is False:
            try:
                self.sock.sendall(bytes(packet))
            except BrokenPipeError:
                self.connect()
            else:
                connected = True
            if tried > 2:
                raise IOError('연결할 수 없음')
            tried += 1
        return self.get_response()

    def get_response(self):
        response = KCTPacket(self.sock.recv(KCTPacket.SIZE))
        if 'result' in response and response['result'] == '00':
            return response
        if not self.fail_silently:
            raise self.get_error(response['result'])
        return None

    def login(self):
        packet = KCTPacket(packet_id=2500)
        self.request(packet)

    def health_check(self):
        packet = KCTPacket(packet_id=2600)
        response = self.request(packet)
        if response:
            print('Health check OK.')

    def assign_number(self, safety_number, phone_number):
        packet = KCTPacket(packet_id=2501, safety_number=safety_number, phone_number_1=phone_number)
        return self.request(packet)

    def unassign_number(self, safety_number):
        packet = KCTPacket(packet_id=2502, safety_number=safety_number)
        return self.request(packet)

    def pause_number(self, safety_number):
        packet = KCTPacket(packet_id=2503, safety_number=safety_number)
        return self.request(packet)

    def resume_number(self, safety_number):
        packet = KCTPacket(packet_id=2504, safety_number=safety_number)
        return self.request(packet)


# 0508-4896-0000
# 0508-4898-9999


""" 
from missions.utils import *
kct = KCTSafetyNumber()
kct.login()
"""


class IkeaProductCrawler:
    """
    이케아 제품 크롤러
    """
    def _search(self, url):
        res = requests.get(url)
        soup = BeautifulSoup(res.text, 'html.parser')
        try:
            product_name = soup.select_one('div[class*=range-revamp-header-section__title--small]').get_text()
            category_name = soup.select_one('span[class*=range-revamp-header-section__description-text]').get_text()
            price = soup.select_one('span[class=range-revamp-price__integer]').get_text()
            image = soup.select_one('img[class=range-revamp-aspect-ratio-image__image]').attrs['src']
            product_detail = soup.select_one('span[class*=range-revamp-header-section__description-measurement]')
        except:
            return {}
        product_detail = product_detail.get_text() if product_detail else ''

        return {
            'product_name': '%s %s' % (product_name, product_detail),
            'title': '%s %s %s' % (product_name, category_name, product_detail),
            'category_name': category_name,
            'price': price,
            'img': image,
        }

    def search(self, code):
        url = 'https://www.ikea.com/kr/ko/products/%s/%s-compact-fragment.html' % (code[-3:], code)
        result = self._search(url)
        if not result:
            url = 'https://www.ikea.com/kr/ko/products/%s/s%s-compact-fragment.html' % (code[-3:], code)
            result = self._search(url)
        if result:
            result.update({'itemId': code})
        return result


