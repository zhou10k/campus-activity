"""教师审核蓝图 - V2.0 新增

对应 R-T9（审核分流）、R-T10（审核本人活动申请）、R-T2/T3（名额看板）
- 教师仅能审核/查看本人负责活动的申请（数据级权限）
- 审核工作台：列出待审核申请，可通过或拒绝（拒绝需填原因）
- 名额看板：实时显示已确定人数、剩余名额、候补人数
"""
from flask import (
    Blueprint, abort, flash, redirect, render_template, request, session, url_for
)

from extensions import db
from models import (
    Activity, ActivityStatus, Registration, RegistrationStatus, User,
)
from services.registration_service import TransitionError, review_registration
from utils.decorators import require_role

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')


def _get_own_activity_or_403(activity_id):
    """数据级校验：仅本人活动，越权返回 403"""
    activity = Activity.query.get(activity_id)
    if not activity:
        abort(404)
    if activity.teacher_id != session.get('user_id'):
        abort(403)
    return activity


@teacher_bp.route('/activities')
@require_role('teacher')
def my_activities():
    """我发布的活动（含名额看板数据）"""
    activities = Activity.query.filter_by(teacher_id=session['user_id']) \
        .order_by(Activity.created_at.desc()).all()
    return render_template('teacher/activities.html', activities=activities)


@teacher_bp.route('/activity/<int:activity_id>/review')
@require_role('teacher')
def review_workbench(activity_id):
    """审核工作台 - 仅本人活动，仅显示待审核申请"""
    activity = _get_own_activity_or_403(activity_id)

    pending = Registration.query.filter_by(
        activity_id=activity_id, status=RegistrationStatus.PENDING
    ).order_by(Registration.registered_at.asc()).all()

    confirmed = Registration.query.filter_by(
        activity_id=activity_id, status=RegistrationStatus.CONFIRMED
    ).order_by(Registration.registered_at.asc()).all()

    waitlist = Registration.query.filter_by(
        activity_id=activity_id, status=RegistrationStatus.WAITLIST
    ).order_by(Registration.waitlist_at.asc()).all()

    return render_template(
        'teacher/review.html',
        activity=activity,
        pending=pending,
        confirmed=confirmed,
        waitlist=waitlist,
    )


@teacher_bp.route('/activity/<int:activity_id>/review/<int:reg_id>', methods=['POST'])
@require_role('teacher')
def review_decide(activity_id, reg_id):
    """审核决定 - 通过或拒绝（拒绝需填原因）"""
    activity = _get_own_activity_or_403(activity_id)

    reg = Registration.query.get(reg_id)
    if not reg or reg.activity_id != activity_id:
        abort(404)

    decision = request.form.get('decision')
    reason = (request.form.get('reason') or '').strip()

    if decision not in ('approve', 'reject'):
        flash('审核结果不合法', 'danger')
        return redirect(url_for('teacher.review_workbench', activity_id=activity_id))

    if decision == 'reject' and not reason:
        flash('拒绝时必须填写原因', 'danger')
        return redirect(url_for('teacher.review_workbench', activity_id=activity_id))

    try:
        _, msg = review_registration(
            reg, activity,
            approve=(decision == 'approve'),
            teacher_id=session['user_id'],
            reason=reason or None,
        )
    except TransitionError as e:
        db.session.rollback()
        flash(f'审核失败：{e}', 'danger')
        return redirect(url_for('teacher.review_workbench', activity_id=activity_id))

    flash(msg, 'success')
    return redirect(url_for('teacher.review_workbench', activity_id=activity_id))


@teacher_bp.route('/activity/<int:activity_id>/roster')
@require_role('teacher')
def roster(activity_id):
    """报名名单 - 仅本人活动，含正式名单与候补队列"""
    activity = _get_own_activity_or_403(activity_id)

    confirmed = Registration.query.filter_by(
        activity_id=activity_id, status=RegistrationStatus.CONFIRMED
    ).order_by(Registration.registered_at.asc()).all()
    waitlist = Registration.query.filter_by(
        activity_id=activity_id, status=RegistrationStatus.WAITLIST
    ).order_by(Registration.waitlist_at.asc()).all()

    return render_template(
        'teacher/roster.html',
        activity=activity,
        confirmed=confirmed,
        waitlist=waitlist,
    )
