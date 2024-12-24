import os
import itertools
import functools
import hashlib
import random
import json
import re
import tempfile
import threading
from uuid import uuid4

import openpyxl

from Crypto.PublicKey import RSA
from Crypto import Random
import requests

from django.utils import timezone
from django.core.files.storage import FileSystemStorage
from django.conf import settings


"""
데코레이터
"""


class cached_property(object):
    def __init__(self, function):
        self.function = function
        functools.update_wrapper(self, function)

    def __get__(self, obj, type_):
        if obj is None:
            return self
        val = self.function(obj)
        obj.__dict__[self.function.__name__] = val
        return val


def parametrized(dec):
    """데코레이터에 파라미터 입력하는 데코레이터"""

    def layer(*args, **kwargs):
        def repl(f):
            return dec(f, *args, **kwargs)

        return repl

    return layer


@parametrized
def types(function, *types):
    """타입 제한 데코레이터"""

    def rep(*args, **kwargs):
        for a, t, n in zip(args, types, itertools.count()):
            if type(a) is not t:
                raise TypeError('Value %d has not type %s. %s instead' % (n, t, type(a)))
        return function(*args, **kwargs)

    return rep


"""
공통 함수
"""


@types(int)
def add_comma(num):
    if type(num) == str and not num.isdigit():
        return num
    if not num:
        return '0'
    return '{:20,}'.format(num).strip()


def list_to_concat_string(obj):
    if type(obj) is list:
        return ''.join([list_to_concat_string(o) for o in obj])
    return str(obj)



class SingletonOptimizedMeta(type):
    _instances = {}
    __lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls.__lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super(SingletonOptimizedMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class CachedProperties(metaclass=SingletonOptimizedMeta):
    """
    사이트 글로벌로 적용될 캐쉬 설정값
    """
    _data = {}

    def __getattr__(self, key):
        if key not in self._data:
            self._data[key] = None
        return self._data[key]

    def __setattr__(self, key, value):
        self._data[key] = value

    def __iter__(self):
        return self._data.__iter__()


class UploadFileHandler:
    """
    업로드 파일 핸들러
    """
    instance = None
    file_obj = None
    _filename = ''
    auto_filename = True
    ext = ''
    parent_id = ''
    ts = ''
    digest = ''

    def __init__(self, instance, file_obj, filename=''):
        self.instance = instance
        self.file_obj = file_obj
        self.ext = file_obj.name.split('.')[-1]
        if filename:
            self._filename = filename
            self.auto_filename = False
        else:
            self._filename = str(instance.pk) if instance.pk else uuid4().hex

    def with_parent(self, parent_id):
        self.parent_id = str(getattr(self.instance, parent_id, '')) or ''
        return self

    def with_timestamp(self):
        self.ts = str(timezone.now().timestamp())
        return self

    def with_digest(self):
        self.digest = get_file_digest(self.instance.attach.file.name)
        return self

    @property
    def filename(self):
        if self.auto_filename:
            names = [i for i in [self.parent_id, self._filename, self.ts, self.digest, self.ext] if i]
        else:
            names = [self._filename, self.ext]
        return os.path.join(self.instance._meta.model.__name__.lower(), '.'.join(names))

    def save(self, to=''):
        fs = FileSystemStorage()
        saved = fs.save(self.filename, self.file_obj)
        if to:
            setattr(self.instance, to, saved)
            self.instance.save()
        return saved


def get_md5_hash(content, buffer=65536):
    """텍스트를 md5 해싱해서 다이제스트 뽑기"""
    # todo: InMemoryUploadedFile 이외에도 django.core.files.uploadedfile의 다른 클래스에 대한 대응 고려할 것.
    hasher = hashlib.md5()
    if content.__class__.__name__ is 'InMemoryUploadedFile':
        content.open('rb')
        for chunk in iter(lambda: content.read(buffer), b''):
            hasher.update(chunk)
    elif type(content) is str:
        hasher.update(content.encode('utf-8'))
    return hasher.hexdigest()


def get_file_digest(filepath, buffer=65536):
    """파일을 md5 해싱해서 다이제스트 뽑기"""
    if not os.path.isfile(filepath):
        return None
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(buffer), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


@types(int)
def get_random_digit(n):
    # random.randint(10**(n-1), 10**n - 1)
    return ''.join(random.sample([chr(n) for n in range(48, 58)], n))


@types(int, int, str, str)
def stars(cnt, all=5, starred='★', blank='☆'):
    return starred * cnt + blank * (all - cnt)


def get_external_ip():
    try:
        return requests.get('https://checkip.amazonaws.com').text.strip()
    except:
        return None


def send_fcm_notification(ids, title, body):
    """fcm 푸시 알림 보내기"""
    headers = {
        'Authorization': 'key=%s' % settings.FCM_SERVER_KEY,
        'Content-Type': 'application/json; UTF-8',
    }
    content = {
        'registration_ids': ids,
        'notification': {
            'title': title,
            'body': body
        }
    }
    requests.post(settings.FCM_URL, data=json.dumps(content), headers=headers)


class PushMessageHandler:
    """
    FCM 이용한 푸시 매세지
    """
    def __init__(self):
        pass


class SlackWebhook:
    """
    슬랙 웹훅
    """
    url = None

    def __init__(self, ch=None):
        self.urls = getattr(settings, 'SLACK_WEBHOOK_URLS', [])
        if ch:
            self.channel(ch)

    def channel(self, ch):
        if ch in self.urls:
            self.url = self.urls[ch]
            return self
        raise KeyError('Channel is wrong or missing.')

    def send(self, message_body):
        requests.post(self.url, data=json.dumps(message_body))
        return self

    def text(self, msg):
        return self.send({'text': msg})

    def script_msg(self, title, msg='', result=[]):
        payload = {
            'text': title,
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': '*%s*' % title,
                    }
                },
            ],
            'attachments': []
        }

        if msg:
            payload['blocks'].append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': msg,
                }
            })

        for r in result:
            color = '#ff0000' if r['code'] else '#777777'
            contents = ''.join(r['contents']) if type(r['contents']) is list else r['contents']
            contents = contents if contents else 'Error' if r['code'] else 'OK'
            payload['attachments'].append({
                'color': color,
                'blocks': [
                    {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': '*%s*' % r['title'],
                        }
                    },
                    {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': contents,
                        }
                    },
                ]
            })

        return self.send(payload)

    def section_msg(self, title, msgs=[]):
        if type(title) in (list, tuple):
            title_md = '\n'.join(['*%s*' % t for t in title])
            title = '\n'.join(title)
        else:
            title_md = '*%s*' % title
        payload = {
            'text': title,
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': title_md,
                    }
                },
            ],
            'attachments': []
        }

        for msg in msgs:
            color = msg['color'] if 'color' in msg else '#777777'
            contents = ''.join(msg['contents']) if type(msg['contents']) is list else msg['contents']
            blocks = []
            if 'title' in msg:
                blocks.append({
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': '*%s*' % msg['title'],
                        }
                    })
            if contents:
                blocks.append({
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': contents,
                    }
                })
            payload['attachments'].append({
                'color': color,
                'blocks': blocks
            })

        return self.send(payload)


class ServerScript:
    """
    서버 스크립트 실행
    """
    venv = 'source venv/bin/activate'

    def _run_os_script(self, cmd, exclude=''):
        """ run os command """
        tmp = tempfile.NamedTemporaryFile(dir='/tmp')
        try:
            cmd_rtn_code = os.system('%s &> %s' % (cmd, tmp.name))
            cmd_stdout = open(tmp.name, 'r').readlines()
        except:
            cmd_rtn_code = -1
            cmd_stdout = []
        tmp.close()

        if exclude:
            cmd_stdout = [s for s in cmd_stdout if not re.findall(exclude, s)]

        return {
            'code': cmd_rtn_code,
            'contents': cmd_stdout,
        }

    def deploy(self, view_on_console=False):
        commands = (
            {
                'title': 'Pull from github',
                'cmd': '%s; git pull' % self.venv,
                'msg_exclude': r'^warning\:\s',
            },
            {
                'title': 'Upgrade pip',
                'cmd': '%s; pip install --upgrade pip' % self.venv,
                'msg_exclude': r'^(Requirement\salready\s)|(WARNING\:\s)',
            },
            {
                'title': 'Install pip packages',
                'cmd': '%s; pip install -r requirements.txt' % self.venv,
                'msg_exclude': r'^(Requirement\salready\ssatisfied)|(WARNING\:\s)',
            },
            {
                'title': 'DB migrations',
                'cmd': '%s; python3 manage.py migrate --no-input' % self.venv,
                'msg_exclude': r'^(Operations\sto\sperform)|(Apply\sall\smigrations)|(Running\smigrations)|(No\smigrations\sto\sapply)'
            },
            {
                'title': 'Collect static files',
                'cmd': '%s; python3 manage.py collectstatic --no-input' % self.venv,
                'msg_exclude': r'^0\sstatic\sfiles\scopied'
            },
            {
                'title': 'Reload wsgi',
                'cmd': 'touch web/wsgi.py',
                'msg_exclude': '',
            },
        )
        rtn = []
        for command in commands:
            result = self._run_os_script(command['cmd'], command['msg_exclude'])
            result['title'] = command['title']
            rtn.append(result)
            if view_on_console:
                self.console(result)
        return rtn

    def console(self, result):
        print('[{code}] {title}'.format(**result))
        print('\n'.join(result['contents']))



class RSACrypt:
    """
    RSA 암호화
    """
    key = None
    publickey = None

    def __init__(self, private_pem='', public_pem=''):
        Random.atfork()
        if private_pem and os.path.exists(private_pem):
            self.key = self.get_key_from_pem(private_pem)
            self.publickey = self.key.publickey()
        if public_pem and os.path.exists(public_pem):
            self.publickey = self.get_key_from_pem(public_pem)

    def _export_pem(self, filename, key):
        fp = open(filename, 'wb+')
        fp.write(key.exportKey('PEM'))
        fp.close()
        return key

    def make_private_pem(self, filename, bits=1024):
        return self._export_pem(filename, RSA.generate(bits))

    def make_public_pem(self, filename):
        if not self.key:
            raise ValueError('No private key.')
        return self._export_pem(filename, self.key.publickey())

    def get_key_from_pem(self, filename):
        fp = open(filename, 'r')
        key = RSA.importKey(fp.read())
        fp.close()
        return key

    def set_key(self, key):
        self.key = RSA.importKey(key)

    def encrypt(self, text):
        if not self.publickey:
            raise ValueError('No key file.')
        return self.publickey.encrypt(text.encode('utf-8'), 32)[0]

    def decrypt(self, text):
        if not self.key:
            raise ValueError('No private key.')
        return self.key.decrypt(text).decode('utf-8')


class BaseExcelImportConverter:
    """
    엑셀 가져오기 기본 클래스
    """
    sheet_order = 0
    row_converter = None
    field_converter = None
    post_save = None
    workbook = None
    worksheet = None
    columns = ()
    model = None
    data_start_row = 2
    data_end_row = None
    data_start_col = 1
    data_end_col = None

    def __init__(self, filename, *args, **kwargs):
        if not self.model:
            raise ValueError('No model')
        self.load(filename)
        self.args = args
        self.kwargs = kwargs

    def load(self, filename):
        self.workbook = openpyxl.load_workbook(filename)
        self.set_sheet(0)

    def set_sheet(self, sheet_order, start_row=None, end_row=None, start_col=None, end_col=None):
        self.worksheet = self.workbook[self.workbook.sheetnames[sheet_order]]
        self.sheet_order = sheet_order
        self.data_start_row = start_row or self.data_start_row
        self.data_end_row = end_row or self.data_end_row
        self.data_start_col = start_col or self.data_start_col
        self.data_end_col = end_col or self.data_end_col
        self.row_converter = getattr(self, 'convert_sheet_%s_row' % self.sheet_order, self.convert_sheet_0_row)
        self.field_converter = getattr(self, 'convert_sheet_%s_fields' % self.sheet_order)
        self.post_save = getattr(self, 'post_save_sheet_%s' % self.sheet_order, self.post_save_sheet_0)

    def raw_print(self, row):
        if type(row) is int:
            row = list(self.worksheet)[row-1]
        print([cell.value for cell in row])

    def print(self):
        for row in list(self.worksheet)[self.data_start_row-1:self.data_end_row]:
            print(self.row_converter(row))

    def get_data_from_sheet(self, sheet_order=0, start_row=None, end_row=None, start_col=None, end_col=None):
        self.set_sheet(sheet_order, start_row, end_row, start_col, end_col)
        data = []
        for row in list(self.worksheet)[self.data_start_row-1:self.data_end_row]:
            data.append(self.row_converter(row))
        return data

    def make_objects(self, save=True):
        ids = list()
        data = list()
        for row in list(self.worksheet)[self.data_start_row-1:self.data_end_row]:
            obj = self.row_converter(row, to_object=True)
            if not obj:
                print('*** Failed ***')
                self.raw_print(row)
                print()
                continue
            if save:
                obj.save()
                self.post_save(obj)
                ids.append(obj.id)
                print('등록 성공 :', obj.id)
                print('*** Succeeded ***')
                self.raw_print(row)
                print()
            else:
                data.append(obj)
        return ids or data

    def dict_to_obj(self, dict_data, save=False):
        obj = self.model(**dict_data)
        if save:
            obj.save()
        return obj

    def convert_sheet_0_row(self, row, to_object=False):
        row_data = dict()
        i = self.data_start_col - 1
        for key in self.columns[self.sheet_order]:
            # 값 처리
            try:
                value = row[i].value
            except:
                value = None

            # 값 추가처리 메쏘드가 있는 경우 처리기
            handler = getattr(self, 'set_field_' + key, None)
            if callable(handler):
                value = handler(value)

            row_data.update({key: value})

            i += 1
            if self.data_end_col and i >= self.data_end_col:
                break

        # 필드 변환 처리
        if self.field_converter:
            row_data = self.field_converter(row_data)

        # 모델 오브젝트 또는 딕셔너리에 값 할당
        if to_object:
            row_data = self.dict_to_obj(row_data)
        return row_data

    def set_field_empty(self, dict_data, value):
        return dict_data

    def post_save_sheet_0(self, obj):
        pass
