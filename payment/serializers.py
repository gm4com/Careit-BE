import dateutil.parser
import logging

from rest_framework import serializers
from rest_framework.fields import empty

from common.exceptions import Errors
from accounts.serializers import ProfileCodeSerializer
from base.models import BannedWord
from missions.serializers import BidSerializer
from .models import Billing, Payment, Cash, Point, Withdraw, PointVoucher, Coupon


logger = logging.getLogger('payment')


class PointSerializer(serializers.ModelSerializer):
    """
    포인트 시리얼라이져
    """
    detail = serializers.CharField(source='detail_memo', read_only=True, required=False)

    class Meta:
        model = Point
        fields = ('amount', 'balance', 'detail', 'created_datetime')
        order_by = ('-id')
        extra_kwargs = {
            'balance': {'read_only': True},
            'created_datetime': {'read_only': True},
        }


class PointVoucherSerializer(serializers.ModelSerializer):
    """
    포인트 상품권 시리얼라이져
    """
    point = PointSerializer(read_only=True, required=False)

    class Meta:
        model = PointVoucher
        fields = ('code', 'point', 'expire_date', 'created_datetime', 'used_datetime')
        order_by = ('-created_datetime')
        extra_kwargs = {
            'code': {'read_only': True},
            'expire_date': {'read_only': True},
            'created_datetime': {'read_only': True},
            'used_datetime': {'read_only': True},
        }


class CouponSerializer(serializers.ModelSerializer):
    """
    쿠폰 시리얼라이져
    """
    name = serializers.CharField(read_only=True)
    discount = serializers.CharField(read_only=True)
    condition = serializers.CharField(read_only=True)
    calculated_discount = serializers.SerializerMethodField(method_name='get_calculated_discount')

    class Meta:
        model = Coupon
        fields = ('id', 'name', 'discount', 'condition', 'expire_date', 'used_datetime', 'calculated_discount')
        order_by = 'expire_date'
        extra_kwargs = {
            'expire_date': {'read_only': True},
            'used_datetime': {'read_only': True},
        }

    def __init__(self, instance=None, data=empty, **kwargs):
        self.bid = kwargs.pop('bid') if 'bid' in kwargs else None
        super(CouponSerializer, self).__init__(instance=instance, data=data, **kwargs)

    def get_calculated_discount(self, instance):
        return instance.calculate_discount(self.bid) if self.bid else 0


class CouponRegisterSerializer(serializers.Serializer):
    """
    쿠폰 등록 시리얼라이져
    """
    code = serializers.CharField(label='코드')


class CashSerializer(serializers.ModelSerializer):
    """
    캐쉬 시리얼라이져
    """
    detail = serializers.CharField(source='detail_memo', read_only=True, required=False)

    class Meta:
        model = Cash
        fields = ('amount', 'balance', 'detail', 'created_datetime')
        order_by = ('-id')


class WithdrawSerializer(serializers.ModelSerializer):
    """
    인출신청 시리얼라이져
    """
    state = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = Withdraw
        fields = ('amount', 'requested_datetime', 'failed_datetime', 'done_datetime', 'state')
        order_by = ('-id')
        extra_kwargs = {
            'requested_datetime': {'read_only': True},
            'failed_datetime': {'read_only': True},
            'done_datetime': {'read_only': True},
        }


class PaymentSerializer(serializers.ModelSerializer):
    """
    결제 시리얼라이져
    """
    point = PointSerializer(required=False)

    class Meta:
        model = Payment
        fields = ('bid', 'point', 'pay_method', 'amount', 'result', 'is_succeeded')
        order_by = ('-id')

    def create(self, validated_data):
        point = validated_data.pop('point')
        obj = Payment(**validated_data)

        # lock 해제
        obj.bid.unlock()
        logger.info('[Payment] [bid id %s] unlocked' % obj.bid_id)

        # 전액 포인트 여부 검사
        if point['amount'] != obj.bid.amount:
            raise Errors.insufficient_balance

        # 포인트 사용 처리
        if point and point['amount'] and obj.is_succeeded and not obj.use_point(point['amount']):
            logger.info('[Payment] [bid id %s (%s)] insufficient point balance' % (obj.bid_id, obj.bid._mission.code))
            raise Errors.insufficient_balance

        logger.info('[Payment] [bid id %s (%s)] create payment with validated data...' % (obj.bid_id, obj.bid._mission.code))
        logger.info(validated_data)

        obj.save()
        logger.info('[Payment] [payment id %s] saved' % obj.id)
        if obj.is_succeeded:
            logger.info('[Payment] [payment id %s] succeeded' % obj.id)
            if obj.bid.win_single():
                logger.info('[Payment] [payment id %s] [bid id %s (%s)] 낙찰처리 성공' % (obj.id, obj.bid_id, obj.bid._mission.code))
            else:
                logger.info('[Payment] [payment id %s] [bid id %s (%s)] 낙찰처리 실패' % (obj.id, obj.bid_id, obj.bid._mission.code))
        else:
            logger.info('[Payment] [payment id %s] failed' % obj.id)
            raise Errors.payment_not_completed
        return obj


class GeneralPaymentSerializer(serializers.ModelSerializer):
    """
    일반결제 시리얼라이져
    """
    class Meta:
        model = Payment
        fields = ('bid', 'coupon')

    def create(self, validated_data):
        # 일반결제 기본 정보 설정
        validated_data['pay_method'] = 'CARD'
        validated_data['amount'] = validated_data['bid'].amount
        validated_data['is_succeeded'] = False

        return Payment.objects.create(**validated_data)
        # return super(GeneralPaymentSerializer, self).create(validated_data)


class BillingRegisterSerializer(serializers.Serializer):
    """
    빌링 등록 시리얼라이져
    """
    cardNo = serializers.CharField(label='카드번호', max_length=20, min_length=15)
    expd = serializers.CharField(label='유효기간', max_length=4, min_length=4)
    customerName = serializers.CharField(label='구매자명', max_length=30, min_length=2, required=False)
    birthDay = serializers.CharField(label='생년월일 (또는 사업자번호)', max_length=13, min_length=6)
    passwd = serializers.CharField(label='비밀번호 앞 두자리', max_length=2)
    authType = serializers.CharField(label='인증타입', max_length=1, default='0', required=False)


class BillingRegisteredSerializer(serializers.ModelSerializer):
    """
    빌링 등록정보 시리얼라이져
    """
    card_no = serializers.SerializerMethodField()

    class Meta:
        model = Billing
        fields = ('id', 'card_company_no', 'card_name', 'card_no', 'created_datetime')

    def get_card_no(self, obj):
        return obj.card_no[-4:]

class BillingPaymentSerializer(serializers.ModelSerializer):
    """
    빌링 결제 시리얼라이져
    """
    class Meta:
        model = Payment
        fields = ('bid',)

