"""报名蓝图 - V2.0 报名 / 取消（含自动补位） / 我的活动

对应 R-S1（报名状态可见）、R-S4（取消与释放）、R-T4/T6/T7（候补与补位）
"""
from datetime import datetime

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, session, url_for
)

from extensions import db
from models import Activity, ActivityStatus, Registration, RegistrationStatus
from services.registration_service import (
    TransitionError, cancel_registration, submit_registration,
)
from utils.decorators import require_role

registration_bp = Blueprint('registration', __name__)


def _get_activity_or_404(activity_id):
    activity = Activity.query.get(activity_id)
    if not activity:
        abort(404)
    return activity


@registration_bp.route('/activity/<int:activity_id>/register', methods=['POST'])
@require_role('student')
def register(activity_id):
    """学生报名 - V2.0 走审核分流 + 名额分流"""
    activity = _get_activity_or_404(activity_id)

    # 已下架 / 未发布 的活动不可报名
    if activity.status != ActivityStatus.PUBLISHED:
        flash('该活动当前不可报名', 'warning')
        return redirect(url_for('activity.detail', activity_id=activity_id))

    # 报名截止时间校验
    now = datetime.now()
    if activity.register_deadline and now >= activity.register_deadline:
        flash('报名已截止', 'warning')
        return redirect(url_for('activity.detail', activity_id=activity_id))

    try:
        reg, msg = submit_registration(activity, session['user_id'])
    except TransitionError as e:
        db.session.rollback()
        flash(f'报名失败：{e}', 'danger')
        return redirect(url_for('activity.detail', activity_id=activity_id))

    flash(msg, 'success')
    return render_template('registration/success.html', activity=activity, reg=reg)


@registration_bp.route('/activity/<int:activity_id>/cancel', methods=['POST'])
@require_role('student')
def cancel(activity_id):
    """取消报名 - 正式参加者释放名额并自动补位；候补者退出队列"""
    activity = _get_activity_or_404(activity_id)

    reg = Registration.query.filter(
        Registration.activity_id == activity_id,
        Registration.student_id == session['user_id'],
        Registration.status.in_((RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLIST)),
    ).first()
    if not reg:
        flash('您没有可取消的报名记录', 'warning')
        return redirect(url_for('activity.detail', activity_id=activity_id))

    try:
        _, msg = cancel_registration(reg, activity)
    except TransitionError as e:
        db.session.rollback()
        flash(f'取消失败：{e}', 'danger')
        return redirect(url_for('activity.detail', activity_id=activity_id))

    flash(msg, 'info')
    return redirect(url_for('activity.detail', activity_id=activity_id))


@registration_bp.route('/my/activities')
@require_role('student')
def my_activities():
    """我的活动 - V2.0 四态展示（待审核 / 正式参加 / 候补中 / 未通过）"""
    regs = Registration.query.filter(
        Registration.student_id == session['user_id'],
        Registration.status.in_((
            RegistrationStatus.PENDING,
            RegistrationStatus.CONFIRMED,
            RegistrationStatus.WAITLIST,
            RegistrationStatus.REJECTED,
        )),
    ).order_by(Registration.registered_at.desc()).all()
    return render_template('registration/my_activities.html', registrations=regs)


@registration_bp.route('/my/registration/<int:reg_id>/cancel', methods=['POST'])
@require_role('student')
def cancel_mine(reg_id):
    """按记录 id 取消本人的报名（数据级权限：仅本人可操作）"""
    reg = Registration.query.get(reg_id)
    if not reg:
        abort(404)
    # 数据级越权拦截：不能替他人操作报名
    if reg.student_id != session['user_id']:
        abort(403)

    activity = _get_activity_or_404(reg.activity_id)
    try:
        _, msg = cancel_registration(reg, activity)
    except TransitionError as e:
        db.session.rollback()
        flash(f'取消失败：{e}', 'danger')
        return redirect(url_for('registration.my_activities'))

    flash(msg, 'info')
    return redirect(url_for('registration.my_activities'))
