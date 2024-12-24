import json
import dateutil.parser
import logging
import hashlib

import requests

from django.conf import settings
from django.utils import timezone

from common.exceptions import Errors


logger = logging.getLogger('payment')


class PaymentAPI:
    """
    결제 API 연동
    """
    # url_by_client = 'nextAppUrl'
    url_by_client = 'nextMobileUrl'

    def request_ready(self, obj):
        url = settings.SPC_PAYMENT_API_URL + '/v1/payment/ready'
        payload = self.get_payload(obj)
        response = requests.post(url, payload)
        rtn = None
        if response.status_code < 300:
            result = response.json()
            if result['resultCode'] == '200':
                try:
                    rtn = (result['data']['aid'], result['data'][self.url_by_client])
                except:
                    obj.result['ready_error'] = result
                    obj.save()
            else:
                obj.result['ready_error'] = result
                obj.save()
        return rtn

    def request_auth(self, obj):
        url = settings.SPC_PAYMENT_API_URL + '/v1/payment/pay'
        payload = self.get_payload(obj)
        response = requests.post(url, payload)
        rtn = None
        if response.status_code < 300:
            result = response.json()
            if result['resultCode'] == '200':
                try:
                    applNo = result['data'].pop('applNo')
                    tranDate = result['data'].pop('tranDate')
                    tranTime = result['data'].pop('tranTime')
                    tranDatetime = timezone.datetime.strptime(tranDate + tranTime, '%y%m%d%H%M%S')
                    rtn = (applNo, tranDatetime, result['data'])
                except:
                    obj.result['auth_error'] = result
                    obj.save()
            else:
                obj.result['auth_error'] = result
                obj.save()
        else:
            # 망취소
            requests.post(settings.SPC_PAYMENT_API_URL + '/v1/payment/net-cancel', payload)
        return rtn

    def request_cancel(self, obj):
        url = settings.SPC_BILLING_API_URL + '/v1/api/payments/payment/cancel'
        payload = self.get_payload(obj, is_cancel=True)
        response = requests.post(url, payload)
        rtn = None
        if response.status_code < 300:
            result = response.json()
            if result['resultCode'] == '200':
                try:
                    tranDate = result['data'].pop('tranDate')
                    tranTime = result['data'].pop('tranTime')
                    tranDatetime = timezone.datetime.strptime(tranDate + tranTime, '%y%m%d%H%M%S')
                    rtn = (tranDatetime, result['data'])
                except:
                    obj.result['cancel_error'] = result
                    obj.save()
            else:
                obj.result['cancel_error'] = result
                obj.save()
        return rtn

    def get_payload(self, obj, is_cancel=False):
        mbrNo = settings.SPC_PAYMENT_API_MID
        mbrRefNo = obj.bid.mission.code + '-' + str(obj.bid_id)  # 가맹점 주문번호를 입찰 id로 입력
        amount = str(obj.amount)

        payload = {
            'version': '1.0',
            'mbrNo': mbrNo,
            'mbrRefNo': mbrRefNo,
            'paymethod': 'CARD',
            'amount': amount,
            'taxAmt': round(obj.amount / 110),
            'timestamp': str(timezone.now().timestamp()),
        }
        if is_cancel:
            # cancel 요청
            if 'auth_result' in obj.result and 'refNo' in obj.result['auth_result'] and obj.authenticated_datetime:
                payload.update({
                    'orgRefNo': obj.result['auth_result']['refNo'],
                    'orgTranDate': obj.authenticated_datetime.date().strftime('%y%m%d'),
                })
                if 'auth_result' in obj.result and 'payType' in obj.result['auth_result'] and \
                        obj.result['auth_result']['payType']:
                    payload.update({'payType': obj.result['auth_result']['payType']})
        else:
            if obj.payment_id:
                # auth 요청
                payload.update({
                    'aid': obj.result['approval']['aid'],
                    'authToken': obj.result['approval']['authToken'],
                    'payType': obj.result['approval']['payType'],
                })
            else:
                # ready 요청
                payload.update({
                    'goodsName': '미션요청',
                    'goodsCode': obj.bid.mission.code,  # 상품명을 미션코드로 입력
                    'approvalUrl': '%s/%s/' % (settings.SPC_PAYMENT_CALLBACK_URL, obj.id),
                    'closeUrl': '%s/%s/close/' % (settings.SPC_PAYMENT_CALLBACK_URL, obj.id),
                    'customerName': obj.bid.mission.user.username,
                    'customerEmail': obj.bid.mission.user.email,
                })
        signature = '|'.join([mbrNo, mbrRefNo, amount, settings.SPC_PAYMENT_API_KEY, payload['timestamp']])
        payload.update({'signature': hashlib.sha256(signature.encode('utf-8')).hexdigest()})
        return payload


class BillingAPI:
    """
    빌링 결제 api
    """
    def request_register(self, obj, data):
        logger.info('[U%s] [빌링 등록 요청]' % obj.user.code)

        url = settings.SPC_BILLING_API_URL + '/v1/api/payments/payment/card-auto/auth'
        payload = self.get_payload(obj, data)
        res = requests.post(url, payload)
        if res.status_code < 300:
            result = res.json()
            if result['resultCode'] == '200':
                try:
                    # 빌링 등록정보 저장
                    obj.billkey = result['data']['billkey']
                    obj.ref_no = result['data']['refNo']
                    obj.card_company_no = result['data']['cardCompanyNo']
                    obj.card_name = result['data']['cardName']
                    obj.card_no = result['data']['cardNo']
                    obj.customer_name = result['data']['custommerName']
                    obj.customer_tel_no = result['data']['custommerTelNo']
                except:
                    logger.error('[U%s] [빌링 등록 응답오류] %s' % (obj.user.code, result))
                    obj.delete()
                    raise Errors.billing_not_completed
                else:
                    obj.save()
            else:
                logger.error('[U%s] [빌링 등록 오류] %s (%s)' % (obj.user.code, result['resultMessage'], result['developerMessage']))
                obj.delete()
                raise Errors.billing_failed('%s (%s)' % (result['resultMessage'], (result['resultCode'] if 'resultCode' in result else '')))

            # 결과 리턴
            logger.info('[U%s] [빌링 등록 성공] %s (%s)' % (obj.user.code, obj.id, obj))
            return obj

        logger.error('[U%s] [빌링 등록 응답오류] (%s) %s' % (obj.user.code, res.status_code, res.content))
        obj.delete()
        raise Errors.billing_not_completed

    def request_unregister(self, obj):
        logger.info('[U%s] [빌링 등록해지 요청] %s (%s)' % (obj.user.code, obj.id, obj))

        url = settings.SPC_BILLING_API_URL + '/v1/api/payments/payment/card-auto/auth-cancel'
        canceled_datetime = timezone.now()
        payload = self.get_payload(obj, {
            'timestamp': str(canceled_datetime.timestamp()),
            'clientType': 'MERCHANT',
            'billkey': obj.billkey
        })
        res = requests.post(url, payload)
        if res.status_code < 300:
            result = res.json()
            if result['resultCode'] == '200':
                try:
                    # 빌링 등록해지정보 저장
                    obj.canceled_datetime = canceled_datetime
                except:
                    logger.error('[U%s] [빌링 등록해지 응답오류] %s' % (obj.user.code, result))
                    raise Errors.billing_not_completed
                else:
                    obj.save()
            else:
                logger.error('[U%s] [빌링 등록해지 오류] %s (%s)' % (obj.user.code, result['resultMessage'], result['developerMessage']))
                raise Errors.billing_failed(result['resultMessage'])

            # 결과 리턴
            logger.info('[U%s] [빌링 해지 성공] %s (%s)' % (obj.user.code, obj.id, obj))
            return True

        logger.error('[U%s] [빌링 등록해지 응답오류] (%s) %s' % (obj.user.code, res.status_code, res.content))
        raise Errors.billing_not_completed

    def request_pay(self, obj):
        logger.info('[U%s] [빌링 결제 요청] %s' % (obj.billing.user.code, obj.id))

        url = settings.SPC_BILLING_API_URL + '/v1/api/payments/payment/card-auto/trans'
        payload = self.get_payment_payload(obj)
        res = requests.post(url, payload)
        if res.status_code < 300:
            result = res.json()
            if result['resultCode'] == '200':
                try:
                    # 빌링 결제정보 저장
                    obj.authenticated_no = result['data'].pop('applNo')
                    obj.payment_id = result['data'].pop('refNo')
                    tranDate = result['data'].pop('tranDate')
                    obj.authenticated_datetime = timezone.datetime.strptime(tranDate, '%y%m%d')
                    obj.result['billing_result'] = result['data']
                except:
                    logger.error('[U%s] [빌링 결제 응답오류] %s' % (obj.billing.user.code, result))
                    raise Errors.billing_failed('결제처리가 정상적으로 완료되지 않았습니다.')
                else:
                    obj.is_succeeded = True
                    obj.save()
            else:
                logger.error('[U%s] [빌링 결제 오류] %s (%s)' % (obj.billing.user.code, result['resultMessage'], result['developerMessage']))
                raise Errors.billing_failed(result['resultMessage'])

            # 결과 리턴
            logger.info('[U%s] [빌링 결제 성공] %s (%s)' % (obj.billing.user.code, obj.id, obj))
            return obj

        logger.error('[U%s] [빌링 등록해지 응답오류] (%s) %s' % (obj.billing.user.code, res.status_code, res.content))
        raise Errors.billing_not_completed

    def request_cancel(self, obj):
        logger.info('[U%s] [빌링 결제취소 요청] %s' % (obj.billing.user.code, obj.id))

        url = settings.SPC_BILLING_API_URL + '/v1/api/payments/payment/card/cancel'
        payload = self.get_payment_payload(obj, is_cancel=True)
        response = requests.post(url, payload)
        rtn = None
        if response.status_code < 300:
            result = response.json()
            if result['resultCode'] == '200':
                try:
                    tranDate = result['data'].pop('tranDate')
                    tranTime = result['data'].pop('tranTime')
                    tranDatetime = timezone.datetime.strptime(tranDate + tranTime, '%y%m%d%H%M%S')
                    rtn = (tranDatetime, result['data'])
                except:
                    obj.result['cancel_error'] = result
                    obj.save()
            else:
                obj.result['cancel_error'] = result
                obj.save()
        return rtn

    def get_payload(self, obj, data={}):
        mbrNo = settings.SPC_BILLING_API_MID
        mbrRefNo = obj.mbrRefNo

        payload = {
            'mbrNo': mbrNo,
            'mbrRefNo': mbrRefNo,
            'customerId': 'U%s' % obj.user.code,
            'customerName': obj.user.username,
            'customerTelNo': obj.user.mobile,
            'clientType': 'Online',
            'timestamp': str(obj.created_datetime.timestamp()),
        }
        payload.update(data)
        signature = '|'.join([mbrNo, mbrRefNo, '0', settings.SPC_BILLING_API_KEY, payload['timestamp']])
        payload.update({'signature': hashlib.sha256(signature.encode('utf-8')).hexdigest()})
        return payload

    def get_payment_payload(self, obj, is_cancel=False):
        mbrNo = settings.SPC_BILLING_API_MID
        mbrRefNo = obj.bid.mission.code + '-' + str(obj.bid_id)  # 가맹점 주문번호를 입찰 id로 입력

        payload = {
            'mbrNo': mbrNo,
            'mbrRefNo': mbrRefNo,
            'amount': str(obj.amount),
            'taxAmt': round(obj.amount / 110),
            'clientType': 'MERCHANT'
        }
        if is_cancel:
            payload.update({
                'orgRefNo': obj.payment_id,
                'orgTranDate': obj.authenticated_datetime.date().strftime('%y%m%d'),
                'timestamp': str(timezone.now().timestamp())
            })
        else:
            payload.update({
                'goodsName': '미션요청',
                'billkey': obj.billing.billkey,
                'customerName': obj.billing.user.username,
                'timestamp': str(obj.created_datetime.timestamp())
            })

        signature = '|'.join([mbrNo, mbrRefNo, payload['amount'], settings.SPC_BILLING_API_KEY, payload['timestamp']])
        payload.update({'signature': hashlib.sha256(signature.encode('utf-8')).hexdigest()})
        return payload
