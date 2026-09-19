"""报名蓝图 - 报名 / 取消报名 / 我的活动 (REQ-05, REQ-08)"""
from datetime import datetime

from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for
)
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Activity, Registration
from utils.decorators import require_role

registration_bp = Blueprint('registration', __name__)


@registration_bp.route('/activity/<int:activity_id>/register', methods=['POST'])
@require_role('student')
def register(activity_id):
    """学生报名 (REQ-08)
    校验顺序(严格): 活动存在 -> 已发布 -> 未重复报名 -> 未截止 -> 未满员
    """
    # a) 活动是否存在
    activity = Activity.query.get(activity_id)
    if not activity:
        flash('活动不存在', 'danger')
        return redirect(url_for('activity.list_activities'))

    # b) 活动状态
    if activity.status != 'published':
        flash('该活动当前不可报名', 'warning')
        return redirect(url_for('activity.detail', activity_id=activity_id))

    student_id = session['user_id']

    # c) 重复报名校验 - 视图层先查(更好的用户体验)
    existing = Registration.query.filter_by(
        activity_id=activity_id,
        student_id=student_id,
        status='registered',
    ).first()
    if existing:
        flash('您已报名本活动', 'warning')
        return redirect(url_for('activity.detail', activity_id=activity_id))

    # d) 报名截止时间校验 (BUG-02 修复点)
    now = datetime.now()
    if activity.register_deadline and now >= activity.register_deadline:
        flash('报名已截止', 'warning')
        return redirect(url_for('activity.detail', activity_id=activity_id))

    # e) 名额校验
    registered_count = Registration.query.filter_by(
        activity_id=activity_id, status='registered'
    ).count()
    if registered_count >= activity.capacity:
        flash('本活动名额已满,请关注其他活动', 'warning')
        return redirect(url_for('activity.detail', activity_id=activity_id))

    # 全部通过 - 创建报名记录
    reg = Registration(
        activity_id=activity_id,
        student_id=student_id,
        status='registered',
        registered_at=now,
    )
    db.session.add(reg)
    try:
        db.session.commit()
    except IntegrityError:
        # UNIQUE 部分索引兜底
        db.session.rollback()
        flash('您已报名本活动', 'warning')
        return redirect(url_for('activity.detail', activity_id=activity_id))

    flash('报名成功', 'success')
    return render_template(
        'registration/success.html',
        activity=activity,
    )


@registration_bp.route('/activity/<int:activity_id>/cancel', methods=['POST'])
@require_role('student')
def cancel(activity_id):
    """取消报名"""
    reg = Registration.query.filter_by(
        activity_id=activity_id,
        student_id=session['user_id'],
        status='registered',
    ).first()
    if not reg:
        flash('您未报名此活动', 'warning')
        return redirect(url_for('activity.detail', activity_id=activity_id))

    reg.status = 'cancelled'
    db.session.commit()
    flash('已取消报名', 'info')
    return redirect(url_for('activity.detail', activity_id=activity_id))


@registration_bp.route('/my/activities')
@require_role('student')
def my_activities():
    """我的活动 - 所有当前已报名"""
    regs = Registration.query.filter_by(
        student_id=session['user_id'],
        status='registered',
    ).order_by(Registration.registered_at.desc()).all()
    return render_template('registration/my_activities.html', registrations=regs)