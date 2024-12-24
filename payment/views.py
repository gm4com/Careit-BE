import json
import dateutil.parser
import logging
import hashlib
import datetime

import requests

from django.views.generic import CreateView
from django.http import HttpResponse, QueryDict
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import redirect

from rest_framework import mixins, response, parsers
from rest_framework.decorators import action
from drf_yasg.utils import swagger_auto_schema, no_body

from common.views import swagger_auto_boolean_schema
from common.exceptions import Errors
from common.admin import log_with_reason
from base.views import BaseModelViewSet
from accounts import permissions
from missions.models import Bid
from .models import Billing, Payment, PointVoucher, Coupon, Cash, Point, Withdraw
from .utils import PaymentAPI, BillingAPI
from .serializers import (
    PaymentSerializer,
    BillingRegisterSerializer, BillingRegisteredSerializer, BillingPaymentSerializer, GeneralPaymentSerializer,
    PointVoucherSerializer, CouponSerializer, CouponRegisterSerializer,
    CashSerializer, PointSerializer, WithdrawSerializer
)


logger = logging.getLogger('payment')


class PointViewSet(mixins.ListModelMixin,
                   BaseModelViewSet):
    """
    포인트 API endpoint
    """
    model = Point
    serializer_class = PointSerializer
    permission_classes = (permissions.IsValidUser,)

    def get_queryset(self):
        return super(PointViewSet, self).get_queryset().filter(user_id=self.request.user.id)\
            .exclude(amount=0).order_by('-id')


class PointVoucherViewSet(mixins.ListModelMixin,
                    mixins.UpdateModelMixin,
                    BaseModelViewSet):
    """
    포인트 상품권 API endpoint
    """
    model = PointVoucher
    serializer_class = PointVoucherSerializer
    permission_classes = (permissions.IsValidUser,)
    http_method_names = ('get', 'put')
    lookup_url_kwarg = 'code'

    def get_queryset(self):
        qs = super(PointVoucherViewSet, self).get_queryset().filter(user_id=self.request.user.id)
        if self.action == 'usable':
            qs = qs.usable_set()
        return qs.order_by('-id')

    @action(detail=False, methods=['get'])
    def usable(self, request, *args, **kwargs):
        """사용가능 포인트 상품권 목록"""
        return super(PointVoucherViewSet, self).list(request, *args, **kwargs)

    @swagger_auto_schema(responses={404: Errors.not_found.as_p(), 406: Errors.not_usable.as_p()})
    def update(self, request, *args, **kwargs):
        """포인트 상품권 사용"""
        obj = self.get_queryset().get_usable(self.kwargs.get('code'), self.request.user)
        if obj is None:
            raise Errors.voucher_not_found
        if obj is False:
            raise Errors.voucher_not_usable
        obj = obj.use(self.request.user)
        return response.Response(data=self.serializer_class(instance=obj).data)


class CouponViewSet(mixins.ListModelMixin,
                    mixins.CreateModelMixin,
                    BaseModelViewSet):
    """
    쿠폰 API endpoint
    """
    model = Coupon
    serializer_class = CouponSerializer
    permission_classes = (permissions.IsValidUser,)
    http_method_names = ('get', 'post')

    def get_serializer_class(self):
        if self.action == 'create':
            return CouponRegisterSerializer
        return super(CouponViewSet, self).get_serializer_class()

    def get_queryset(self):
        qs = super(CouponViewSet, self).get_queryset().filter(user_id=self.request.user.id)
        if self.action in ('usable', 'usable_count'):
            qs = qs.usable_set()
        return qs.order_by('-id')

    @action(detail=False, methods=['get'])
    def usable(self, request, *args, **kwargs):
        """사용가능 쿠폰 목록"""
        return super(CouponViewSet, self).list(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def usable_count(self, request, *args, **kwargs):
        """사용가능 쿠폰 카운터"""
        return response.Response({'count': self.get_queryset().count()})

    # @swagger_auto_schema(responses={404: Errors.not_found.as_p(), 406: Errors.not_usable.as_p()})
    # def update(self, request, *args, **kwargs):
    #     """쿠폰 사용"""
    #     obj = self.get_queryset().get_usable(self.kwargs.get('code'), self.request.user)
    #     if obj is None:
    #         raise Errors.voucher_not_found
    #     if obj is False:
    #         raise Errors.voucher_not_usable
    #     obj = obj.use(self.request.user)
    #     return response.Response(data=self.serializer_class(instance=obj).data)

    def create(self, request, *args, **kwargs):
        """쿠폰 등록"""
        registered = Coupon.objects.register(request.data['code'], request.user)
        if registered:
            return response.Response(data=CouponSerializer(instance=registered[0]).data)
        if registered is False:
            raise Errors.coupon_not_usable
        raise Errors.coupon_not_found


class CouponBidViewSet(mixins.ListModelMixin,
                       BaseModelViewSet):
    """
    쿠폰 API endpoint
    """
    model = Coupon
    serializer_class = CouponSerializer
    permission_classes = (permissions.IsValidUser,)

    def dispatch(self, request, *args, **kwargs):
        self.bid = Bid.objects.get(id=kwargs['bid_id'])
        return super(CouponBidViewSet, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super(CouponBidViewSet, self).get_queryset().get_usable(self.request.user)

    def list(self, request, *args, **kwargs):
        """결제할 금액에 따른 사용가능 쿠폰 목록"""
        return response.Response(data=self.serializer_class(instance=self.get_queryset(), many=True, bid=self.bid).data)


class CashViewSet(mixins.ListModelMixin,
                  BaseModelViewSet):
    """
    캐쉬 API endpoint
    """
    model = Cash
    serializer_class = CashSerializer
    permission_classes = (permissions.IsHelper,)

    def get_queryset(self):
        return super(CashViewSet, self).get_queryset().filter(helper__user_id=self.request.user.id)\
            .exclude(amount=0).order_by('-id')


class WithdrawViewSet(mixins.ListModelMixin,
                      mixins.CreateModelMixin,
                      BaseModelViewSet):
    """
    캐쉬 인출 신청 API endpoint
    """
    model = Withdraw
    serializer_class = WithdrawSerializer
    permission_classes = (permissions.IsHelper,)

    def get_queryset(self):
        qs = super(WithdrawViewSet, self).get_queryset().filter(helper__user_id=self.request.user.id).order_by('-id')
        if self.action == 'list':
            qs = qs.filter(failed_datetime__isnull=True, done_datetime__isnull=True)
        return qs

    def create(self, request, *args, **kwargs):
        if datetime.datetime.now().weekday() != 1:
            raise Errors.not_tuesday
        if 'amount' not in request.data or not request.data['amount']:
            raise Errors.invalid_amount
        if not request.user.is_helper:
            raise Errors.permission_denied
        if self.get_queryset().requested_set().exists():
            raise Errors.duplicated_request
        if request.user.helper.cash_balance < max(10000, request.data['amount']):
            raise Errors.insufficient_balance
        request.data.update({'helper_id': request.user.helper.id})
        obj = self.model.objects.create(**request.data)
        log_with_reason(request.user, obj, 'added', str(request.user.helper.bank_account or ''))
        return response.Response(data=self.serializer_class(instance=obj).data)


def commit_transaction(url, obj):
    """트랜잭션 실행"""
    result = requests.post(url, data={
        'P_MID': settings.PAYMENT_INI_MID,
        'P_TID': obj.payment_id
    })
    if result.status_code < 300:
        obj.result = dict([arr.split('=') for arr in result.text.split('&')])
        query = QueryDict(result.text)
        obj.authenticated_no = query.get('P_AUTH_NO', ''),
        authenticated_datetime_string = query.get('P_AUTH_DT', '')
        if authenticated_datetime_string:
            obj.authenticated_datetime = dateutil.parser.parse(authenticated_datetime_string)
        if query.get('P_STATUS', '') == '00':
            obj.is_succeeded = True
        else:
            obj.is_succeeded = False
        obj.save()
        return obj
    return None


@method_decorator(csrf_exempt, name='dispatch')
class ExternalPaymentView(CreateView):
    """
    외부미션 결제 트랜잭션 뷰
    """
    model = Payment
    template_name = 'payment/external.html'
    fields = '__all__'

    def post(self, request, *args, **kwargs):
        result = {'payment_result': False}
        error_msg = ''

        # 입찰 가져오기
        bid_id = kwargs.get('bid_id', None)
        if bid_id:
            try:
                bid = Bid.objects.get(id=bid_id)
            except:
                # raise Errors.not_found
                error_msg = '[트랜잭션 오류] 결제정보가 없습니다.'
            else:
                if bid.is_paid:
                    # raise Errors.already_paid
                    error_msg = '이미 결제가 되었습니다.'
        else:
            # raise Errors.permission_denied
            error_msg = '[트랜잭션 오류] 권한이 없습니다.'

        if error_msg:
            try:
                self.unlock(bid)
            except:
                pass
            result.update({'error_msg': error_msg})
            return self.return_result(result)

        # 트랜잭션 실행 요청
        if 'P_STATUS' in request.POST and request.POST.get('P_STATUS', '') == '00':
            try:
                obj = self.model(
                    bid=bid, pay_method='Card',
                    payment_id=request.POST.get('P_TID', ''),
                    amount=request.POST.get('P_AMT', ''),
                )
                point = int(request.POST.get('P_NOTI', 0) or 0)
            except:
                logger.info('[Payment] [bid id %s (%s)] failed\n%s' % (bid.id, bid._mission.code, request.POST))
                raise Errors.payment_not_completed
            else:
                # 포인트 사용가능 상태 검사
                if point:
                    if bid.mission.user.points.get_balance() < point:
                        self.unlock(bid)
                        result.update({'error_msg': '포인트가 부족합니다.'})
                        logger.info('[Payment] [payment id %s] failed\n포인트가 부족합니다.' % obj.id)
                        return self.return_result(result)

                # 트랜잭션 실행
                obj = commit_transaction(request.POST.get('P_REQ_URL', ''), obj)
                if obj is None:
                    self.unlock(bid)
                    logger.info('[Payment] [payment id %s] failed\n%s' % (obj.id, obj.result['P_RMESG1']))
                    result.update({'error_msg': obj.result['P_RMESG1']})
                    return self.return_result(result)

                if obj.is_succeeded:
                    if point:
                        obj.use_point(point)
                    logger.info('[Payment] [payment id %s] succeeded' % obj.id)
                    result['payment_result'] = True

                    # 해당 입찰을 낙찰 처리
                    if bid.win_single():
                        logger.info('[Payment] [payment id %s] [bid id %s (%s)] 낙찰처리 성공' % (obj.id, bid.id, bid._mission.code))
                    else:
                        logger.info('[Payment] [payment id %s] [bid id %s (%s)] 낙찰처리 실패' % (obj.id, bid.id, bid._mission.code))
                else:
                    logger.info('[Payment] [payment id %s] failed\n%s' % (obj.id, obj.result['P_RMESG1']))
                    result.update({'error_msg': obj.result['P_RMESG1']})
        else:
            error_msg = request.POST.get('P_RMESG1', '')
            logger.info('[Payment] [bid id %s (%s)] failed\n%s' % (bid.id, bid._mission.code, error_msg))
            result.update({'error_msg': error_msg})
        self.unlock(bid)
        return self.return_result(result)

    def unlock(self, bid):
        # lock 해제
        bid.unlock()
        logger.info('[Payment] [bid id %s (%s)] unlocked' % (bid.id, bid._mission.code))

    def return_result(self, result):
        return HttpResponse("""
                <script>
                    opener.postMessage(%s, '*');
                </script>
                """ % json.dumps(result))

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


@method_decorator(csrf_exempt, name='dispatch')
class TransactionView(ExternalPaymentView):
    """
    결제 트랜잭션 뷰
    """
    template_name = 'payment/transaction.html'

    def return_result(self, result):
        return HttpResponse("""
                <script>
                    setTimeout(()=>{
                        if(typeof(cordova_iab) === 'undefined') { var cordova_iab = window.webkit.messageHandlers.cordova_iab;}
                        cordova_iab.postMessage(JSON.stringify(%s));
                    },100);
                </script>
                """ % json.dumps(result))


class PaymentViewSet(mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.CreateModelMixin,
                     BaseModelViewSet):
    """
    결제 API endpoint
    """
    model = Payment
    serializer_class = PaymentSerializer
    permission_classes = (permissions.IsValidUser,)

    def get_queryset(self):
        return super(PaymentViewSet, self).get_queryset().filter(bid__mission__user_id=self.request.user.id)

    def create(self, request, *args, **kwargs):
        logger.info('[결제결과 저장요청] %s' % request.get_full_path())
        logger.info(request.data)
        return super(PaymentViewSet, self).create(request, *args, **kwargs)


class GeneralPaymentViewSet(mixins.CreateModelMixin,
                            mixins.RetrieveModelMixin,
                            mixins.DestroyModelMixin,
                            BaseModelViewSet):
    """
    일반 결제 API endpoint
    """
    model = Payment
    serializer_class = GeneralPaymentSerializer

    def get_permissions(self):
        if self.action in ('retrieve', 'close', 'create'):
            self.permission_classes = (permissions.AllowAny,)
        return super(GeneralPaymentViewSet, self).get_permissions()

    def create(self, request, *args, **kwargs):
        logger.info('[U%s] [결제 요청] %s' % (request.user.code, request.get_full_path()))

        # 결제 됐는지 확인
        try:
            bid = Bid.objects.get(id=request.data['bid'])
        except:
            raise Errors.fields_invalid
        if bid.is_paid:
            raise Errors.already_paid

        # 쿠폰 유효성 체크
        if 'coupon' in request.data:
            try:
                coupon = Coupon.objects.get(id=request.data['coupon'])
            except:
                raise Errors.coupon_not_found
            if not coupon.is_usable:
                raise Errors.coupon_not_usable
            if coupon.calculate_discount(bid) == 0:
                raise Errors.coupon_not_usable

        # 포인트 잔액이 결제 가능한지 체크
        point_amount = int(request.data.pop('point_amount') or 0) if 'point_amount' in request.data else 0
        if request.user.points.get_balance() < point_amount:
            raise Errors.insufficient_balance

        # 웹 결제인지 체크
        is_web = request.data.pop('is_web') if 'is_web' in request.data else False

        # 데이터 체크
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            raise Errors.fields_invalid
            # return self.return_error('결제에 필요한 데이터가 전달되지 않았습니다.')

        # 오브젝트 저장 후 포인트 금액만큼 결제액 조정
        obj = serializer.save()
        obj.amount -= point_amount

        # 쿠폰이 있는 경우 결제액 조정
        if obj.coupon:
            obj.amount -= obj.coupon.calculate_discount(bid)

        if is_web:
            obj.result['is_web'] = is_web
        obj.save()

        # todo: lock 확인 후 락

        if obj.amount > 0:
            # 포인트로 전액 결제되지 않은 경우 카드결제 시도
            logger.info('[U%s] [결제 READY] %s' % (request.user.code, obj.amount))
            obj.result['point_to_pay'] = point_amount  # 나중에 처리를 위해 남겨두는게 현명할지는 판단 필요
            pay = PaymentAPI()
            ready_result = pay.request_ready(obj)
            if ready_result:
                obj.payment_id, obj.result['ready_next_url'] = ready_result
                obj.save()
                return response.Response({'next_url': obj.result['ready_next_url']})
                # return redirect(obj.result['ready_next_url'])
            else:
                self.unlock(obj.bid)
                raise Errors.payment_not_completed
                # return self.return_error('결제 요청단계에서 오류가 발생했습니다.', obj)

        else:
            # 포인트로 전액 결제된 경우 결제 성공 처리
            if obj.use_point(point_amount):
                obj.pay_method = 'POINT'

                # 쿠폰 사용 처리
                if obj.coupon:
                    obj.coupon.use()

                obj.is_succeeded = True
                obj.save()

                # 해당 입찰을 낙찰 처리
                if self.__win(obj):
                    self.unlock(obj.bid)
                    return response.Response({'pay_method': 'POINT', 'amount': point_amount, 'result': True})
                else:
                    self.unlock(obj.bid)
                    return response.Response({'pay_method': 'POINT', 'amount': point_amount, 'result': False})
        self.unlock(obj.bid)
        raise Errors.payment_not_completed

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.bid.is_paid:
            return self.return_error('이미 결제가 된 미션입니다.', obj)
        obj.result['approval'] = {
            'aid': request.GET.get('aid'),
            'authToken': request.GET.get('authToken'),
            'merchantData': request.GET.get('merchantData'),
            'payType': request.GET.get('payType'),
        }
        logger.info('[미션 %s] [결제 AUTH] %s' % (obj.bid.mission.code, obj.result['approval']))
        pay = PaymentAPI()
        auth_result = pay.request_auth(obj)
        if auth_result:
            obj.authenticated_no, obj.authenticated_datetime, obj.result['auth_result'] = auth_result

            # 쿠폰 사용 처리
            if obj.coupon:
                obj.coupon.use()

            obj.is_succeeded = True
            obj.save()
            if obj.result['point_to_pay']:
                obj.use_point(obj.result['point_to_pay'], restrict=False)
            logger.info('[Payment] [미션 %s] 결제완료' % obj.bid.mission.code)

            # 해당 입찰을 낙찰 처리
            if self.__win(obj):
                return self.return_success(obj)
            else:
                return self.return_error('미션 낙찰처리가 정상적으로 완료되지 않았습니다. 고객센터로 문의바랍니다.', obj)

        logger.info('[Payment] [미션 %s] 결제실패 - 트랜잭션 승인되지 않음' % obj.bid.mission.code)
        return self.return_error('결제 트랜잭션이 실행되지 못했습니다.', obj)

    @action(methods=['get'], detail=True)
    def close(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.result['close'] = kwargs.get('aid')
        logger.info('[미션 %s] [결제 CLOSE] %s' % (obj.bid.mission.code, obj.result['close']))
        return self.return_error('사용자가 결제를 중단했습니다.')

    def destroy(self, request, *args, **kwargs):
        pass

    def __win(self, obj):
        if obj.bid.win_single():
            logger.info('[Payment] [payment id %s] [bid id %s (%s)] 낙찰처리 성공' % (obj.id, obj.bid_id, obj.bid._mission.code))
            return True
        else:
            logger.info('[Payment] [payment id %s] [bid id %s (%s)] 낙찰처리 실패' % (obj.id, obj.bid_id, obj.bid._mission.code))
            return False

    def unlock(self, bid):
        # lock 해제
        bid.unlock()
        logger.info('[Payment] [bid id %s (%s)] unlocked' % (bid.id, bid._mission.code))

    def make_response(self, result, is_web=False):
        if is_web:
            return HttpResponse("""
                <script>
                    opener.postMessage(%s, '*');
                </script>
                """ % json.dumps(result))
        else:
            return HttpResponse("""
                <script>
                    setTimeout(()=>{
                        if(typeof(cordova_iab) === 'undefined') { cordova_iab = window.webkit.messageHandlers.cordova_iab;}
                        cordova_iab.postMessage(JSON.stringify(%s));
                    },1000);
                </script>
                """ % json.dumps(result))

    def return_error(self, msg, obj=None):
        if obj and obj.bid:
            self.unlock(obj.bid)
        result = {
            'payment_result': False,
            'error_msg': msg
        }
        is_web = True if obj and 'is_web' in obj.result and obj.result['is_web'] else False
        response = self.make_response(result, is_web)
        self.write_log(self.request, response, logging.WARNING)
        return response

    def return_success(self, obj):
        if obj.bid:
            self.unlock(obj.bid)
        result = {
            'payment_result': True
        }
        is_web = True if obj and 'is_web' in obj.result and obj.result['is_web'] else False
        response = self.make_response(result, is_web)
        self.write_log(self.request, response)
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        if self.action == 'create':
            return super(GeneralPaymentViewSet, self).finalize_response(request, response, *args, **kwargs)
        return response


class BillingPaymentViewSet(mixins.CreateModelMixin,
                            mixins.ListModelMixin,
                            mixins.DestroyModelMixin,
                            BaseModelViewSet):
    """
    빌링 결제 API endpoint
    """
    model = Billing

    def get_queryset(self):
        return super(BillingPaymentViewSet, self).get_queryset().filter(user=self.request.user,
                                                                        canceled_datetime__isnull=True)

    def get_serializer_class(self):
        if self.action == 'create':
            return BillingRegisterSerializer
        if self.action == 'pay':
            return GeneralPaymentSerializer
        return BillingRegisteredSerializer

    def create(self, request, *args, **kwargs):
        # 데이터 체크
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            raise Errors.fields_invalid

        # 빌링 등록 요청
        pay = BillingAPI()
        obj = pay.request_register(request.user.billings.create(), serializer.data)
        return response.Response(data=BillingRegisteredSerializer(instance=obj).data)

    def destroy(self, request, *args, **kwargs):
        # 권한 체크
        obj = self.get_object()
        if request.user != obj.user:
            raise Errors.permission_denied

        # 빌링 등록해지 요청
        pay = BillingAPI()
        if pay.request_unregister(obj):
            return response.Response({'result': True})

    @action(methods=['post'], detail=True)
    def pay(self, request, *args, **kwargs):
        logger.info('[U%s] [빌링 결제 요청] %s' % (request.user.code, request.get_full_path()))

        # 결제 됐는지 확인
        try:
            bid = Bid.objects.get(id=request.data['bid'])
        except:
            raise Errors.fields_invalid
        if bid.is_paid:
            raise Errors.already_paid

        # 쿠폰 유효성 체크
        if 'coupon' in request.data:
            try:
                coupon = Coupon.objects.get(id=request.data['coupon'])
            except:
                raise Errors.coupon_not_found
            if not coupon.is_usable:
                raise Errors.coupon_not_usable
            if coupon.calculate_discount(bid) == 0:
                raise Errors.coupon_not_usable

        # 포인트 잔액이 결제 가능한지 체크
        point_amount = int(request.data.pop('point_amount')) if 'point_amount' in request.data else 0
        if request.user.points.get_balance() < point_amount:
            raise Errors.insufficient_balance

        # 데이터 체크
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            raise Errors.fields_invalid

        # 결제 오브젝트 저장
        obj = serializer.save()

        # 쿠폰이 있는 경우 결제액 조정
        if obj.coupon:
            obj.amount -= obj.coupon.calculate_discount(bid)

        # 포인트 금액만큼 결제액 조정
        obj.billing = self.get_object()
        obj.amount -= point_amount
        obj.save()

        # 미션과 빌링 유져 확인
        if obj.bid.mission.user != obj.billing.user:
            raise Errors.permission_denied

        # todo: lock 확인 후 락

        if obj.amount > 0:
            # 포인트로 전액 결제되지 않는 경우 카드결제 시도
            pay = BillingAPI()
            obj = pay.request_pay(obj)

            if obj:
                # 포인트 처리
                if point_amount:
                    obj.use_point(point_amount, restrict=False)

                # 쿠폰 사용 처리
                if obj.coupon:
                    obj.coupon.use()

                # 해당 입찰을 낙찰 처리
                if self.__win(obj):
                    self.unlock(obj.bid)
                    return response.Response({'pay_method': 'CARD', 'amount': obj.amount, 'result': True})
                else:
                    self.unlock(obj.bid)
                    raise Errors.billing_failed('미션 낙찰처리가 정상적으로 완료되지 않았습니다. 고객센터로 문의바랍니다.')
            else:
                self.unlock(obj.bid)
                raise Errors.billing_failed('결제처리가 정상적으로 완료되지 않았습니다.')

        else:
            # 포인트로 전액 결제된 경우 결제 성공 처리
            if obj.use_point(point_amount):
                obj.pay_method = 'POINT'

                # 쿠폰 사용 처리
                if obj.coupon:
                    obj.coupon.use()

                obj.billing = None
                obj.is_succeeded = True
                obj.save()

                # 해당 입찰을 낙찰 처리
                if self.__win(obj):
                    self.unlock(obj.bid)
                    return response.Response({'pay_method': 'POINT', 'amount': point_amount, 'result': True})
                else:
                    self.unlock(obj.bid)
                    return response.Response({'pay_method': 'POINT', 'amount': point_amount, 'result': False})
        self.unlock(obj.bid)
        raise Errors.payment_not_completed

    def __win(self, obj):
        if obj.bid.win_single():
            logger.info('[Payment] [payment id %s] [bid id %s (%s)] 낙찰처리 성공' % (obj.id, obj.bid_id, obj.bid._mission.code))
            return True
        else:
            logger.info('[Payment] [payment id %s] [bid id %s (%s)] 낙찰처리 실패' % (obj.id, obj.bid_id, obj.bid._mission.code))
            return False

    def unlock(self, bid):
        # lock 해제
        bid.unlock()
        logger.info('[Payment] [bid id %s (%s)] unlocked' % (bid.id, bid._mission.code))

    def finalize_response(self, request, response, *args, **kwargs):
        return super(BillingPaymentViewSet, self).finalize_response(request, response, *args, **kwargs)
