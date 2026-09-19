"""权限装饰器"""
from functools import wraps

from flask import flash, redirect, session, url_for


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
    """要求角色装饰器 - 检查 session 中用户角色
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