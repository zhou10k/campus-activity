"""管理蓝图 - 教师账号审核 + V2.0 活动下架处置与账号停用

对应 R-A1（账号停用/恢复）、R-A2（查看平台全部活动）、R-A3（下架处置）、R-A4（不越界）
"""
from datetime import datetime

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, session, url_for
)

from extensions import db
from models import (
    AccountStatus, Activity, ActivityStatus, AuditLog, Registration, User,
)
from utils.decorators import require_role

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ------------------------------------------------------------------
# 教师账号审核（V1.0 已有）
# ------------------------------------------------------------------
@admin_bp.route('/audit', methods=['GET'])
@require_role('admin')
def audit_list():
    """待审核教师列表"""
    pending_teachers = User.query.filter_by(
        role='teacher', status='pending'
    ).order_by(User.created_at.asc()).all()
    return render_template('admin/audit.html', teachers=pending_teachers)


@admin_bp.route('/audit/<int:teacher_id>', methods=['POST'])
@require_role('admin')
def audit_decide(teacher_id):
    """审核操作 - 通过或拒绝"""
    decision = request.form.get('decision')
    reason = (request.form.get('reason') or '').strip()

    if decision not in ('approved', 'rejected'):
        flash('审核结果不合法', 'danger')
        return redirect(url_for('admin.audit_list'))

    teacher = User.query.get(teacher_id)
    if not teacher or teacher.role != 'teacher' or teacher.status != 'pending':
        flash('目标教师不存在或不在待审核状态', 'danger')
        return redirect(url_for('admin.audit_list'))

    teacher.status = decision
    log = AuditLog(
        teacher_id=teacher.id,
        admin_id=session['user_id'],
        decision=decision,
        reason=reason or None,
        decided_at=datetime.now(),
    )
    db.session.add(log)
    db.session.commit()

    flash('审核完成', 'success')
    return redirect(url_for('admin.audit_list'))


# ------------------------------------------------------------------
# V2.0 新增：账号停用 / 恢复（R-A1）
# ------------------------------------------------------------------
@admin_bp.route('/users')
@require_role('admin')
def user_list():
    """用户管理 - 账号状态一览"""
    users = User.query.filter(User.role != 'admin') \
        .order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@require_role('admin')
def toggle_account(user_id):
    """停用 / 恢复账号（仅影响账号能否登录，不改教师审核状态）"""
    user = User.query.get(user_id)
    if not user or user.role == 'admin':
        flash('目标用户不存在或不可操作', 'danger')
        return redirect(url_for('admin.user_list'))

    if user.account_status == AccountStatus.ACTIVE:
        user.account_status = AccountStatus.DISABLED
        flash(f'已停用账号 {user.account}', 'info')
    else:
        user.account_status = AccountStatus.ACTIVE
        flash(f'已恢复账号 {user.account}', 'success')
    db.session.commit()
    return redirect(url_for('admin.user_list'))


# ------------------------------------------------------------------
# V2.0 新增：平台活动全量查看与下架处置（R-A2、R-A3、R-A4）
# ------------------------------------------------------------------
@admin_bp.route('/activities')
@require_role('admin')
def activity_list():
    """平台全部活动（含其他教师的活动） - R-A2"""
    activities = Activity.query.order_by(Activity.created_at.desc()).all()
    return render_template('admin/activities.html', activities=activities)


@admin_bp.route('/activity/<int:activity_id>/delist', methods=['POST'])
@require_role('admin')
def delist_activity(activity_id):
    """下架处置 - R-A3

    仅改变活动状态为 delisted（学生端不可见且不可报名），
    不改变该活动的报名名单与候补队列（R-A4：不越界）。
    """
    activity = Activity.query.get(activity_id)
    if not activity:
        abort(404)

    if activity.status == ActivityStatus.DELISTED:
        flash('该活动已是下架状态', 'warning')
        return redirect(url_for('admin.activity_list'))

    reason = (request.form.get('reason') or '').strip()
    activity.status = ActivityStatus.DELISTED
    db.session.commit()

    note = f'（原因：{reason}）' if reason else ''
    flash(f'活动「{activity.title}」已下架{note}，报名名单与候补队列保持不变', 'info')
    return redirect(url_for('admin.activity_list'))


@admin_bp.route('/activity/<int:activity_id>/restore', methods=['POST'])
@require_role('admin')
def restore_activity(activity_id):
    """恢复上架（将误下架的活动重新发布）"""
    activity = Activity.query.get(activity_id)
    if not activity:
        abort(404)
    if activity.status != ActivityStatus.DELISTED:
        flash('该活动当前不是下架状态', 'warning')
        return redirect(url_for('admin.activity_list'))

    activity.status = ActivityStatus.PUBLISHED
    db.session.commit()
    flash(f'活动「{activity.title}」已恢复上架', 'success')
    return redirect(url_for('admin.activity_list'))
