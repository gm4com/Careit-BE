from common_ref import *
import accounts.models as acnt
import anyman_migration.models as any_mig

# anyman 2.0 tb key
ps_user_keys = (
    'password', 'last_login', 'created_datetime', 'username', 'date_of_birth', 'gender',
    'withdrew_datetime',
    '_is_service_blocked', 'email')

ps_mobile_phone_keys = ('number',)
ps_service_block_keys = ('start_datetime', 'end_datetime',)
ps_helper_keys = ('push_not_allowed_from', 'push_not_allowed_to', 'introduction',)

ps_mission_keys = ('anycode', 'end_datetime',)


def helper_mig():
    # anyman 1.0 헬퍼기준 멤버 데이터
    ms_helper_rs = select_sql_file('helper_main', **conn_dict_main_na)

    for ms_helper in ms_helper_rs:
        # 0. ms <-> ps sql 전처리
        ms_helper['gender'] = yn2tf(ms_helper['gender'])
        ms_helper['_is_service_blocked'] = yn2tf(ms_helper['_is_service_blocked'])

        ms_helper['created_datetime'] = dt_timezone(ms_helper['created_datetime'])
        ms_helper['withdrew_datetime'] = dt_timezone(ms_helper['withdrew_datetime'])
        ms_helper['last_login'] = dt_timezone(ms_helper['last_login'])
        ms_helper['start_datetime'] = dt_timezone(ms_helper['start_datetime'])
        ms_helper['end_datetime'] = dt_timezone(ms_helper['end_datetime'])

        # 1. User Insert
        try:
            ps_user, created = acnt.User.objects.get_or_create(**slice_dict(ms_helper, ps_user_keys))
        except:
            pass

        if created:  # TODO 임시 email = user code
            ps_user.email = ps_user.code
            ps_user.save()

        # 2. MobilePhone Insert
        ps_mobile_phone = {'user': ps_user, **slice_dict(ms_helper, ps_mobile_phone_keys)}
        if ps_mobile_phone['number'] is None:
            ps_mobile_phone['number'] = ''
        print(ps_mobile_phone)

        try:
            mobile_phone = acnt.MobilePhone(**ps_mobile_phone)
            mobile_phone.save()
        except:
            pass

        # 3. ServiceBlock Insert
        if ms_helper['start_datetime'] is not None:
            # if ms_helper['_is_service_blocked']:

            ps_service_block = {'user': ps_user, **slice_dict(ms_helper, ps_service_block_keys)}
            # print('ps_service_block', ps_service_block)
            try:
                service_block = acnt.ServiceBlock(**ps_service_block)
                service_block.save()
                service_block.start_datetime = ms_helper['start_datetime']
                service_block.save()
            except:
                pass

        # 4. Helper 관련모델 Insert
        if ms_helper['helper_grade'] == '20':  # 정식헬퍼인 경우만 헬퍼로 Insert
            # 4-1. Helper Insert
            ps_helper = {'user': ps_user, **slice_dict(ms_helper, ps_helper_keys)}
            # print('ps_helper', ps_helper)
            helper = acnt.Helper(**ps_helper)
            helper.save()

            # 4-2. Helper 관련모델 Insert
            if ms_helper['bank_code'] in BANK_CODES_CONV.keys() and ms_helper['bank_code'] is not None:
                ps_bank_account = {'helper': helper, 'bank_code': BANK_CODES_CONV[ms_helper['bank_code']],
                                   'number': number_only(ms_helper['bank_number'])[:15], 'name': ms_helper['bank_name']}
                try:
                    bank_account = acnt.BankAccount(**ps_bank_account)
                    bank_account.save()
                except:
                    pass

            # 4-3. UID Insert
            ps_h_uid = {'user': ps_user, 'h_uid': ms_helper['h_uid']}
            print(ps_h_uid)
            try:
                user_asis, created = any_mig.HelperAsIs.objects.get_or_create(**ps_h_uid)
            except:
                pass


def user_mig():
    # anyman 1.0 헬퍼기준 멤버 데이터
    ms_member = select_sql_file('user_main', **conn_dict_main_na)

    for ms_m in ms_member:
        # 0. ms <-> ps sql 전처리
        ms_m['gender'] = yn2tf(ms_m['gender'])
        ms_m['_is_service_blocked'] = yn2tf(ms_m['_is_service_blocked'])
        ms_m['created_datetime'] = dt_timezone(ms_m['created_datetime'])
        ms_m['withdrew_datetime'] = dt_timezone(ms_m['withdrew_datetime'])
        ms_m['last_login'] = dt_timezone(ms_m['last_login'])
        ms_m['start_datetime'] = dt_timezone(ms_m['start_datetime'])
        ms_m['end_datetime'] = dt_timezone(ms_m['end_datetime'])

        # 1. User Insert
        ps_user, created = acnt.User.objects.get_or_create(**slice_dict(ms_m, ps_user_keys))
        # print(ps_user)

        # TODO 임시. email = user_code
        if created:
            ps_user.email = ps_user.code
            ps_user.save()

        # 2. MobilePhone Insert

        ps_mobile_phone = {'user': ps_user, **slice_dict(ms_m, ps_mobile_phone_keys)}
        # print(ps_mobile_phone)
        try:
            mobile_phone, created = acnt.MobilePhone.objects.get_or_create(**ps_mobile_phone)
        except:
            pass

        # mobile_phone.save()

        # 3. UID Insert
        ps_uid = {'user': ps_user, 'uid': ms_m['uid']}
        print(ps_uid)
        try:
            user_asis, created = any_mig.UserAsIs.objects.get_or_create(**ps_uid)
        except:
            pass
        # user_asis.save()

        # ServiceBlock Insert
        if ms_m['start_datetime'] is not None:
            # if ms_m['_is_service_blocked']:
            ps_service_block = {'user': ps_user, **slice_dict(ms_m, ps_service_block_keys)}
            # print('ps_service_block', ps_service_block)
            service_block = acnt.ServiceBlock(**ps_service_block)
            service_block.save()
            service_block.start_datetime = ms_m['start_datetime']
            service_block.save()


if __name__ == '__main__':
    helper_mig()
    user_mig()
