"""用户认证蓝图 - 注册 / 登录 / 登出 (REQ-01, REQ-02)"""
from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for
)
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册 - 学生自动通过, 教师待审核 (REQ-01)"""
    if request.method == 'POST':
        account = (request.form.get('account') or '').strip()
        name = (request.form.get('name') or '').strip()
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm_password') or ''
        role = request.form.get('role') or ''

        errors = []
        if not account:
            errors.append('学号/工号不能为空')
        if not name:
            errors.append('姓名不能为空')
        if not password:
            errors.append('密码不能为空')
        if password != confirm:
            errors.append('两次输入的密码不一致')
        if role not in ('student', 'teacher'):
            errors.append('请选择正确的角色')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template(
                'auth/register.html',
                errors=errors,
                account=account, name=name, role=role,
            )

        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        # 学生注册后直接通过, 教师注册后待审核
        status = 'approved' if role == 'student' else 'pending'

        user = User(
            account=account,
            password_hash=password_hash,
            name=name,
            role=role,
            status=status,
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            # account 唯一索引兜底捕获
            flash('该学号/工号已被注册', 'danger')
            return render_template(
                'auth/register.html',
                errors=['该学号/工号已被注册'],
                account=account, name=name, role=role,
            )

        # 注册成功直接建立会话
        session.clear()
        session['user_id'] = user.id
        session['role'] = user.role
        session['name'] = user.name

        if role == 'teacher':
            flash('注册成功,您的教师账号正在等待管理员审核,审核通过后方可发布活动', 'success')
        else:
            flash('注册成功,已自动登录', 'success')
        return redirect(url_for('activity.list_activities'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录 (REQ-02)"""
    if request.method == 'POST':
        account = (request.form.get('account') or '').strip()
        password = request.form.get('password') or ''

        user = User.query.filter_by(account=account).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('账号或密码错误', 'danger')
            return render_template('auth/login.html', account=account)

        # V2.0：账号状态校验（账号能否登录，与教师审核状态无关）
        if not user.can_login():
            flash('该账号已被停用，请联系管理员', 'danger')
            return render_template('auth/login.html', account=account)

        # 教师登录时的审核状态校验
        if user.role == 'teacher':
            if user.status == 'pending':
                flash('您的账号正在审核中,请耐心等待', 'warning')
                return render_template('auth/login.html', account=account)
            if user.status == 'rejected':
                flash('您的账号审核未通过,请联系管理员', 'danger')
                return render_template('auth/login.html', account=account)

        session.clear()
        session['user_id'] = user.id
        session['role'] = user.role
        session['name'] = user.name
        flash('登录成功', 'success')
        return redirect(url_for('activity.list_activities'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    """登出"""
    session.clear()
    flash('已登出', 'info')
    return redirect(url_for('auth.login'))