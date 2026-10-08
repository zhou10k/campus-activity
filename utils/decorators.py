"""权限装饰器 - V2.0 平台级数据权限加固

V1.0 的 require_role 只做「角色级」校验（页面入口可见性），
V2.0 在此基础上补充「数据级」校验：
- 学生仅能操作本人的报名数据（不能改/看他人报名、不能看完整名单）
- 教师仅能维护本人负责的活动（不能审核/编辑/查看他人活动）

越权时返回 403 错误（接口级拦截），而非仅隐藏入口。
"""
from functools import wraps

from flask import abort, flash, redirect, session, url_for


def require_login(view_func):
    """要求登录装饰器 - 检查 session 中的登录状态"""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login'))
        return view_func(*args, **kwargs)
    return wrapper


def require_role(role):
    """要求角色装饰器（角色级） - 检查 session 中用户角色
    使用方式: @require_role('admin')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not session.get('user_id'):
                flash('请先登录', 'warning')
                return redirect(url_for('auth.login'))
            if session.get('role') != role:
                flash(f'该操作需要{role}权限', 'danger')
                return redirect(url_for('activity.list_activities'))
            return view_func(*args, **kwargs)
        return wrapper
    return decorator


def require_teacher_owns_activity(get_activity, activity_kwarg='activity_id'):
    """数据级校验：教师只能操作本人负责的活动

    :param get_activity: 由 activity_id 取 Activity 的函数
    :param activity_kwarg: 视图函数中承载活动 id 的关键字参数名
    越权时 abort(403)。
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            activity_id = kwargs.get(activity_kwarg)
            activity = get_activity(activity_id)
            if activity is None:
                abort(404)
            # 仅本人活动可操作
            if activity.teacher_id != session.get('user_id'):
                abort(403)
            return view_func(*args, **kwargs)
        return wrapper
    return decorator


def require_student_owns_registration(get_registration, reg_kwarg='reg_id'):
    """数据级校验：学生只能操作本人的报名记录（不能替他人操作报名）

    越权时 abort(403)。
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            reg_id = kwargs.get(reg_kwarg)
            reg = get_registration(reg_id)
            if reg is None:
                abort(404)
            if reg.student_id != session.get('user_id'):
                abort(403)
            return view_func(*args, **kwargs)
        return wrapper
    return decorator
