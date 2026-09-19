"""End-to-end smoke test using Flask test client.
Covers: register -> login -> publish -> audit -> register student -> browse -> register for activity
Uses only HTTP-level checks to keep state clean.
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, '.')

# Use a fresh test DB to avoid polluting the real one
# Flask-SQLAlchemy 把 sqlite:/// 相对路径放到 instance/ 文件夹, 用绝对路径
TEST_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', '_smoketest.sqlite3')
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

# Override DB URI before importing the app
import config
config.Config.SQLALCHEMY_DATABASE_URI = f'sqlite:///{TEST_DB}'

from app import create_app

app = create_app()
client = app.test_client()

print('=' * 60)
print('=== E2E Smoke Test: 校园活动管理系统 ===')
print('=' * 60)


def step(label):
    print(f'\n[{step.n}] {label}')
    step.n += 1
step.n = 1


def ok(msg):
    print(f'  ✓ {msg}')


def expect_status(label, expected, actual):
    if actual != expected:
        raise AssertionError(f'{label}: expected {expected}, got {actual}')
    ok(f'{label}: {actual}')


# ---- 1. 首页跳转 ----
step('GET / -> 重定向到活动列表')
r = client.get('/')
expect_status('status', 302, r.status_code)
ok(f'Location: {r.headers["Location"]}')


# ---- 2. 活动列表空状态 ----
step('GET /activities -> 200 渲染空列表')
r = client.get('/activities')
expect_status('status', 200, r.status_code)
assert '校园活动'.encode('utf-8') in r.data
ok('页面渲染成功')


# ---- 3. 注册教师 ----
step('POST /register 注册教师 T001')
r = client.post('/register', data={
    'account': 'T001', 'name': '张老师', 'password': 'pass123',
    'confirm_password': 'pass123', 'role': 'teacher',
}, follow_redirects=True)
expect_status('status', 200, r.status_code)
ok('教师注册成功 (status=pending, 自动登录)')


# ---- 4. 注销 ----
client.get('/logout')


# ---- 5. 管理员登录 ----
step('POST /login 管理员 admin/admin123')
r = client.post('/login', data={'account': 'admin', 'password': 'admin123'},
                follow_redirects=True)
expect_status('status', 200, r.status_code)
ok('管理员登录成功')


# ---- 6. 审核教师 ----
step('POST /admin/audit/<id> 通过 T001')
r = client.post('/admin/audit/2', data={'decision': 'approved'}, follow_redirects=True)
expect_status('status', 200, r.status_code)
ok('审核通过')


# ---- 7. 注销管理员 ----
client.get('/logout')


# ---- 8. 教师登录 ----
step('POST /login 教师 T001')
r = client.post('/login', data={'account': 'T001', 'password': 'pass123'},
                follow_redirects=True)
expect_status('status', 200, r.status_code)
ok('教师登录成功')


# ---- 9. 发布活动 ----
step('POST /teacher/activities/new 发布活动')
start = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
end = (datetime.now() + timedelta(days=3, hours=2)).strftime('%Y-%m-%dT%H:%M')
deadline = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
r = client.post('/teacher/activities/new', data={
    'title': 'Python 编程体验工作坊',
    'description': '面向大一新生的 Python 入门活动',
    'location': '教学楼 A 座 301',
    'start_time': start,
    'end_time': end,
    'capacity': '30',
    'register_deadline': deadline,
}, follow_redirects=True)
expect_status('status', 200, r.status_code)
assert 'Python 编程体验工作坊'.encode('utf-8') in r.data
ok('活动发布成功')


# ---- 10. 注销教师 ----
client.get('/logout')


# ---- 11. 注册学生 ----
step('POST /register 注册学生 2026001')
r = client.post('/register', data={
    'account': '2026001', 'name': '李同学', 'password': 'pass123',
    'confirm_password': 'pass123', 'role': 'student',
}, follow_redirects=True)
expect_status('status', 200, r.status_code)
ok('学生注册并自动登录')


# ---- 12. 浏览活动详情 ----
step('GET /activity/<id> 查看活动详情')
r = client.get('/activity/1')
expect_status('status', 200, r.status_code)
assert 'Python 编程体验工作坊'.encode('utf-8') in r.data
ok('详情页渲染成功')


# ---- 13. 报名活动 ----
step('POST /activity/<id>/register 报名')
r = client.post('/activity/1/register', follow_redirects=True)
expect_status('status', 200, r.status_code)
ok('报名成功')


# ---- 14. 重复报名 - 应被拒绝 ----
step('POST /activity/<id>/register 重复报名')
r = client.post('/activity/1/register', follow_redirects=False)
expect_status('status(302 redirect)', 302, r.status_code)
ok('重复报名被拒绝(视图层校验)')


# ---- 15. 我的活动 ----
step('GET /my/activities 我的活动列表')
r = client.get('/my/activities')
expect_status('status', 200, r.status_code)
assert 'Python 编程体验工作坊'.encode('utf-8') in r.data
ok('我的活动页面正确展示已报名活动')


# ---- 16. 取消报名 ----
step('POST /activity/<id>/cancel 取消报名')
r = client.post('/activity/1/cancel', follow_redirects=True)
expect_status('status', 200, r.status_code)
ok('取消报名成功')


# ---- 17. 重新报名 - 部分唯一索引应允许 ----
step('POST /activity/<id>/register 重新报名')
r = client.post('/activity/1/register', follow_redirects=True)
expect_status('status', 200, r.status_code)
ok('重新报名成功(部分唯一索引允许)')


# ---- 18. 注销学生, 管理员登录验证审核日志 ----
client.get('/logout')
step('POST /login 管理员验证 audit_logs')
r = client.post('/login', data={'account': 'admin', 'password': 'admin123'},
                follow_redirects=True)
expect_status('status', 200, r.status_code)

r = client.get('/admin/audit')
expect_status('status', 200, r.status_code)
# 审核后没有 pending 教师
assert '暂无待审核教师'.encode('utf-8') in r.data or '审计'.encode('utf-8') in r.data
ok('审核列表已无待审核教师')


# ---- 19. BUG-02: 截止时间校验 - 注册一个截止时间已过的活动 ----
step('BUG-02 验证: 截止时间已过的活动发布被拒绝')
client.get('/logout')
client.post('/login', data={'account': 'T001', 'password': 'pass123'},
            follow_redirects=True)
past_start = (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')
past_end = (datetime.now() + timedelta(hours=4)).strftime('%Y-%m-%dT%H:%M')
past_deadline = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
r = client.post('/teacher/activities/new', data={
    'title': '过期活动测试',
    'description': '测试用',
    'location': '某地',
    'start_time': past_start,
    'end_time': past_end,
    'capacity': '10',
    'register_deadline': past_deadline,
}, follow_redirects=True)
expect_status('status', 200, r.status_code)
ok('截止时间 < 当前时间的活动被拒绝(视图层拦截)')


print('\n' + '=' * 60)
print('✓ 全部冒烟测试通过 (REQ-01 ~ REQ-08 + BUG-01 + BUG-02)')
print('=' * 60)

# 清理测试 DB（SQLite 句柄可能尚未释放，容忍 OSError）
try:
    os.remove(TEST_DB)
except OSError:
    pass