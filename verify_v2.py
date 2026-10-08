"""V2.0 核心流程端到端验证脚本

使用 Flask test_client 模拟完整业务链路，覆盖 16 条测试用例（TEST-01~16）。
直接运行：python verify_v2.py
"""
import os
import sys
import tempfile

# 用临时数据库，避免污染本地 db.sqlite3
_tmp_db = os.path.join(tempfile.gettempdir(), 'campus_v2_verify.sqlite3')
if os.path.exists(_tmp_db):
    os.remove(_tmp_db)
os.environ['VERIFY_DB'] = _tmp_db

import config as config_mod
config_mod.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///' + _tmp_db

import app as appmod
from extensions import db
from models import (
    AccountStatus, Activity, Registration, RegistrationStatus, User,
)
from werkzeug.security import generate_password_hash

app = appmod.app
client = app.test_client()

RESULTS = []


def check(tid, desc, cond, detail=''):
    RESULTS.append((tid, desc, bool(cond), detail))
    mark = 'PASS' if cond else 'FAIL'
    print(f'[{mark}] {tid} {desc} {detail}')


def make_user(account, name, role, status='approved', acc_status='active'):
    with app.app_context():
        existing = User.query.filter_by(account=account).first()
        if existing:
            return existing.id
        u = User(account=account, name=name, role=role, status=status,
                 account_status=acc_status,
                 password_hash=generate_password_hash('pw123456', method='pbkdf2:sha256'))
        db.session.add(u)
        db.session.commit()
        return u.id


def login(account, password='pw123456'):
    return client.post('/login', data={'account': account, 'password': password},
                       follow_redirects=True)


def logout():
    client.get('/logout')


def new_activity(teacher_account, title, capacity, require_review=False, deadline_future=True):
    """以教师身份发布活动，返回 activity_id"""
    login(teacher_account)
    from datetime import datetime, timedelta
    now = datetime.now()
    start = (now + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
    end = (now + timedelta(days=3, hours=2)).strftime('%Y-%m-%dT%H:%M')
    deadline = (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
    data = {
        'title': title, 'description': 'desc', 'location': 'A101',
        'start_time': start, 'end_time': end, 'capacity': str(capacity),
        'register_deadline': deadline,
    }
    if require_review:
        data['require_review'] = 'on'
    client.post('/teacher/activities/new', data=data, follow_redirects=True)
    logout()
    with app.app_context():
        a = Activity.query.filter_by(title=title).order_by(Activity.id.desc()).first()
        return a.id if a else None


def register(account, activity_id):
    login(account)
    r = client.post(f'/activity/{activity_id}/register', follow_redirects=True)
    logout()
    return r


def reg_status(activity_id, student_account):
    with app.app_context():
        u = User.query.filter_by(account=student_account).first()
        r = Registration.query.filter_by(activity_id=activity_id, student_id=u.id).order_by(Registration.id.desc()).first()
        return r.status if r else None


def main():
    # 建初始数据（admin 已由 app 首次启动自动创建）
    make_user('T001', '教师张', 'teacher')          # 已审核教师
    make_user('T002', '教师李', 'teacher')          # 另一位教师
    for i in range(1, 8):
        make_user(f'2026{i:03d}', f'学生{i}', 'student')

    # TEST-01 活动发布（含审核开关）
    a1 = new_activity('T001', '开放日A', capacity=2, require_review=False)
    check('TEST-01', '教师发布活动成功', a1 is not None, f'activity_id={a1}')

    # TEST-02 无审核开关：未满员直接 confirmed
    register('2026001', a1)
    check('TEST-02', '有名额时报名直接成为正式参加',
          reg_status(a1, '2026001') == RegistrationStatus.CONFIRMED,
          f"status={reg_status(a1, '2026001')}")

    # TEST-03 满员后报名进入候补
    register('2026002', a1)  # 第 2 个名额，满
    register('2026003', a1)  # 应进入候补
    check('TEST-03', '名额满后新报名进入候补队列',
          reg_status(a1, '2026003') == RegistrationStatus.WAITLIST,
          f"status={reg_status(a1, '2026003')}")

    # TEST-04 候补序号 FIFO
    register('2026004', a1)
    register('2026005', a1)
    with app.app_context():
        u3 = User.query.filter_by(account='2026003').first()
        u4 = User.query.filter_by(account='2026004').first()
        r3 = Registration.query.filter_by(activity_id=a1, student_id=u3.id, status='waitlist').first()
        r4 = Registration.query.filter_by(activity_id=a1, student_id=u4.id, status='waitlist').first()
        no3, no4 = r3.waitlist_no, r4.waitlist_no
    check('TEST-04', '候补序号按进入时间升序（FIFO）', no3 == 1 and no4 == 2, f'no3={no3}, no4={no4}')

    # TEST-05 取消 -> 释放 -> 队首自动补位
    login('2026001'); client.post(f'/activity/{a1}/cancel', follow_redirects=True); logout()
    check('TEST-05', '正式人员取消后名额释放且候补队首自动补位',
          reg_status(a1, '2026001') == RegistrationStatus.CANCELLED
          and reg_status(a1, '2026003') == RegistrationStatus.CONFIRMED,
          f"取消者={reg_status(a1, '2026001')}, 队首={reg_status(a1, '2026003')}")

    # TEST-06 候补者退出队列
    login('2026004'); client.post(f'/activity/{a1}/cancel', follow_redirects=True); logout()
    check('TEST-06', '候补人员可主动退出队列',
          reg_status(a1, '2026004') == RegistrationStatus.CANCELLED,
          f"status={reg_status(a1, '2026004')}")

    # TEST-07 审核通过 ≠ 正式参加（审核开关 + 满员场景）
    a2 = new_activity('T001', '开放日B', capacity=1, require_review=True)
    register('2026005', a2)  # 开启审核，先 pending
    check('TEST-07', '开启审核的活动报名后进入待审核',
          reg_status(a2, '2026005') == RegistrationStatus.PENDING,
          f"status={reg_status(a2, '2026005')}")

    # 教师审核通过 -> 有名额 -> confirmed
    with app.app_context():
        u5 = User.query.filter_by(account='2026005').first()
        r5 = Registration.query.filter_by(activity_id=a2, student_id=u5.id).first()
        r5_id = r5.id
    login('T001')
    client.post(f'/teacher/activity/{a2}/review/{r5_id}', data={'decision': 'approve'}, follow_redirects=True)
    logout()
    check('TEST-08', '审核通过后有名额转为正式参加',
          reg_status(a2, '2026005') == RegistrationStatus.CONFIRMED,
          f"status={reg_status(a2, '2026005')}")

    # TEST-09 审核通过但名额已满 -> 候补
    register('2026006', a2)  # capacity=1 已满
    with app.app_context():
        u6 = User.query.filter_by(account='2026006').first()
        r6 = Registration.query.filter_by(activity_id=a2, student_id=u6.id).first()
        r6_id = r6.id
    login('T001')
    client.post(f'/teacher/activity/{a2}/review/{r6_id}', data={'decision': 'approve'}, follow_redirects=True)
    logout()
    check('TEST-09', '审核通过但名额已满 -> 进入候补（审核通过≠正式参加）',
          reg_status(a2, '2026006') == RegistrationStatus.WAITLIST,
          f"status={reg_status(a2, '2026006')}")

    # TEST-10 审核拒绝需填原因
    a3 = new_activity('T001', '开放日C', capacity=3, require_review=True)
    register('2026007', a3)
    with app.app_context():
        u7 = User.query.filter_by(account='2026007').first()
        r7 = Registration.query.filter_by(activity_id=a3, student_id=u7.id).first()
        r7_id = r7.id
    login('T001')
    client.post(f'/teacher/activity/{a3}/review/{r7_id}', data={'decision': 'reject', 'reason': ''}, follow_redirects=True)
    st_after_empty = reg_status(a3, '2026007')
    client.post(f'/teacher/activity/{a3}/review/{r7_id}', data={'decision': 'reject', 'reason': '条件不符'}, follow_redirects=True)
    st_after = reg_status(a3, '2026007')
    logout()
    check('TEST-10', '拒绝必须填原因；填写后置为未通过',
          st_after_empty == RegistrationStatus.PENDING and st_after == RegistrationStatus.REJECTED,
          f'空原因后={st_after_empty}, 填原因后={st_after}')

    # TEST-11 教师越权审核他人活动（数据级拦截）
    login('T002')  # 教师李 尝试审核 教师张 的活动 a3
    resp = client.get(f'/teacher/activity/{a3}/review')
    codes = resp.status_code
    logout()
    check('TEST-11', '教师不能审核他人活动（返回 403）', codes == 403, f'status_code={codes}')

    # TEST-12 学生不能替他人取消报名（数据级拦截）
    with app.app_context():
        u2 = User.query.filter_by(account='2026002').first()
        r2 = Registration.query.filter_by(activity_id=a1, student_id=u2.id).first()
        r2_id = r2.id
    login('2026007')  # 非本人
    resp = client.post(f'/my/registration/{r2_id}/cancel', follow_redirects=False)
    code = resp.status_code
    logout()
    check('TEST-12', '学生不能替他人操作报名（返回 403）', code == 403, f'status_code={code}')

    # TEST-13 管理员下架活动（不改名单/候补）
    with app.app_context():
        before_confirmed = Registration.query.filter_by(activity_id=a1, status='confirmed').count()
        before_waitlist = Registration.query.filter_by(activity_id=a1, status='waitlist').count()
    login('admin', 'admin123')
    client.post(f'/admin/activity/{a1}/delist', data={'reason': '信息错误'}, follow_redirects=True)
    logout()
    with app.app_context():
        a1_now = Activity.query.get(a1)
        after_confirmed = Registration.query.filter_by(activity_id=a1, status='confirmed').count()
        after_waitlist = Registration.query.filter_by(activity_id=a1, status='waitlist').count()
    check('TEST-13', '管理员下架活动且不影响名单与候补',
          a1_now.status == 'delisted' and before_confirmed == after_confirmed and before_waitlist == after_waitlist,
          f"status={a1_now.status}, 名单 {before_confirmed}->{after_confirmed}, 候补 {before_waitlist}->{after_waitlist}")

    # TEST-14 下架活动对学生不可见不可报名
    login('2026007')
    resp = client.get(f'/activity/{a1}', follow_redirects=True)
    invisible = '活动不存在或已下架'.encode('utf-8') in resp.data
    resp2 = client.post(f'/activity/{a1}/register', follow_redirects=True)
    st = reg_status(a1, '2026007')
    logout()
    check('TEST-14', '下架活动学生不可见且不可报名',
          invisible and st in (None, RegistrationStatus.REJECTED),
          f'invisible={invisible}, reg_status={st}')

    # TEST-15 账号停用后不可登录
    login('admin', 'admin123')
    with app.app_context():
        u1 = User.query.filter_by(account='2026001').first()
        uid = u1.id
    client.post(f'/admin/users/{uid}/toggle', follow_redirects=True)
    logout()
    r = client.post('/login', data={'account': '2026001', 'password': 'pw123456'}, follow_redirects=True)
    disabled_blocked = '已被停用'.encode('utf-8') in r.data
    check('TEST-15', '管理员停用账号后该账号无法登录', disabled_blocked, f'blocked={disabled_blocked}')

    # TEST-16 V1.0 核心回归：重复报名被拦截
    a4 = new_activity('T001', '回归活动D', capacity=5, require_review=False)
    register('2026002', a4)
    register('2026002', a4)  # 重复
    with app.app_context():
        u2 = User.query.filter_by(account='2026002').first()
        cnt = Registration.query.filter(
            Registration.activity_id == a4, Registration.student_id == u2.id,
            Registration.status.in_(('pending', 'confirmed', 'waitlist')),
        ).count()
    check('TEST-16', 'V1.0 回归：同一学生不可重复报名', cnt == 1, f'active_records={cnt}')

    # 汇总
    print('\n' + '=' * 60)
    total = len(RESULTS)
    passed = sum(1 for _, _, ok, _ in RESULTS if ok)
    print(f'测试结果：{passed}/{total} 通过')
    failed = [r for r in RESULTS if not r[2]]
    if failed:
        print('失败项：')
        for tid, desc, _, detail in failed:
            print(f'  - {tid} {desc} {detail}')
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
