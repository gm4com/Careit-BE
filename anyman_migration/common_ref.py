import pymssql
import datetime
from django.utils import timezone

conn_dict_main = {'host': 'localhost', 'user': 'sa', 'password': 'anyman11@'}
conn_dict_main_na = {**conn_dict_main, 'database': 'na52791588'}

BANK_CODES_CONV = {
    'KDB산업은행': 2,
    'IBK기업은행': 3,
    '국민은행': 4,
    '외환은행': 5,
    '수협중앙회': 7,
    '농협(중앙회)': 11,
    '농협(단위농협)': 12,
    '우리은행': 20,
    'SC제일은행': 23,
    '한국씨티은행': 27,
    '대구은행': 31,
    '부산은행': 32,
    '광주은행': 34,
    '제주은행': 35,
    '전북은행': 37,
    '경남은행': 39,
    'KEB하나은행': 81,
    '신한은행': 88,
    '새마을금고': 45,
    '신협중앙회': 48,
    '상호저축은행': 50,
    'HSBC은행': 54,
    '도이치은행': 55,
    '케이뱅크': 89,
    '카카오뱅크': 90,

    '농협': 11,
    '기업은행': 3,
    '국민': 4,
    '신한': 88,
    '하나은행': 81,
    '기업': 3,
    '우리': 20,

}


def yn2tf(yn):
    if yn == 'Y':
        rt = True
    elif yn == 'N':
        rt = False
    else:
        rt = None
    return rt


def number_only(s):
    import re
    if s is None:
        rt_s = None
    else:
        rt_s = re.findall("\d+", s)[0]
    return rt_s


def number_only2(s):
    if s is None:
        rt_s = None
    else:
        rt_s = int(filter(str.isdigit, s))
    return rt_s


def slice_dict(d, key_list):
    od = {}
    for k in key_list:
        od = {k: d[k], **od}
    return od


def dt_timezone(dtm):
    if dtm is None:
        dt_rt = None
    else:
        dt_rt = timezone.make_aware(dtm)
    return dt_rt


def select(inq_sql, **conn_dict):
    db_conn = pymssql.connect(**conn_dict)
    try:
        with db_conn.cursor(as_dict=True) as db_curs:
            db_curs.execute(inq_sql)
            # fet_rows = (tuple((dsc[0] for dsc in db_curs.description)),)
            # fet_rows =  db_curs.fetchall()
            fet_rows = tuple(db_curs.fetchall())
    finally:
        db_conn.close()
    return tuple(fet_rows)


def cud(exe_sql, **conn_dict):
    db_conn = pymssql.connect(**conn_dict)
    db_conn.autocommit(True)
    try:
        with db_conn.cursor() as db_curs:
            exe_return = db_curs.execute(exe_sql)
    except Exception as e:
        db_conn.rollback()
        exe_return = e
    finally:
        db_conn.autocommit(False)
        db_conn.close()
    return exe_return


def select_sql_file(exe_sql_nm, **conn_dict):
    exe_sql_dir = "mig_sql/"
    # print('%s%s%s' % (exe_sql_dir, exe_sql_nm, '.sql'))
    with open('%s%s%s' % (exe_sql_dir, exe_sql_nm, '.sql')) as f:
        return select(f.read(), **conn_dict)


def cud_sql_file(exe_sql_nm, **conn_dict):
    exe_sql_dir = "mig_sql/"
    # print('%s%s%s' % (exe_sql_dir, exe_sql_nm, '.sql'))
    with open('%s%s%s' % (exe_sql_dir, exe_sql_nm, '.sql')) as f:
        return cud(f.read(), **conn_dict)


def cud_sql_file_list(exe_sql_nm_list, **conn_dict):
    r_list = []
    for exe_sql_nm in exe_sql_nm_list:
        r_list = [*r_list, (exe_sql_nm, cud_sql_file(exe_sql_nm, **conn_dict))]
    return r_list


if __name__ == '__main__':
    # print(t)
    print(*select_sql_file('helper_main', **conn_dict_main_na), sep="\n")
    # p_list = [chr(i) for i in range(ord('a'), ord('z') + 1)] + [chr(i) for i in range(ord('0'), ord('9') + 1)]
    #
    # nCnt = 1
    # # for p1 in p_list:
    # #     for p2 in p_list:
    # #
    # exe_sql = ""
    # v = []
    # for p1 in p_list:
    #     for p2 in p_list:
    #         for p3 in p_list:
    #             for p4 in p_list:
    #                 v = tuple([str(nCnt), p1 + p2 + p3 + p4])
    #                 if nCnt % 500 == 0:
    #                     print(nCnt)
    #                     exe_sql = "INSERT INTO uid_rel values" + exe_sql + "('%s','%s')," % v
    #                     cud(exe_sql[:-1], **conn_dict_main_na)
    #                     exe_sql = ""
    #                 else:
    #                     exe_sql = exe_sql + "('%s','%s')," % v
    #
    #                 nCnt = nCnt + 1
    #                 if nCnt > 500000:
    #                     break
    #             if nCnt > 500000:
    #                 break
    #         if nCnt > 500000:
    #             break
    #     if nCnt > 500000:
    #         break
    # exe_sql = "INSERT INTO uid_rel values" + exe_sql + "('%s','%s')," % v
    # cud(exe_sql[:-1], **conn_dict_main_na)
    #
    # # exe_sql = "INSERT INTO uid_rel values" + "('%s','%s')," * 1296 % tuple(v)
    # # print(exe_sql)
    # # cud(exe_sql[:-1], **conn_dict_main_na)
    # #
    # #
    # # nCnt += 1
    # # print(nCnt, p1 + p2 + p3 + p4)
    # # if nCnt >= 1000:
    # #             break
