"""活动蓝图 - 列表 / 详情 / 发布 (REQ-04, REQ-06, REQ-07)"""
from datetime import datetime

from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for
)

from extensions import db
from models import Activity, Registration, User
from utils.decorators import require_login, require_role

activity_bp = Blueprint('activity', __name__)


@activity_bp.route('/activities')
def list_activities():
    """活动列表 - 仅展示已发布 (REQ-06)"""
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get('per_page', 10))
    except ValueError:
        per_page = 10

    pagination = Activity.query.filter_by(status='published') \
        .order_by(Activity.start_time.asc()) \
        .paginate(page=page, per_page=per_page, error_out=False)

    return render_template('activity/list.html', pagination=pagination)


@activity_bp.route('/activity/<int:activity_id>')
def detail(activity_id):
    """活动详情 (REQ-07)"""
    activity = Activity.query.get(activity_id)
    if not activity or activity.status == 'cancelled':
        flash('活动不存在或已取消', 'warning')
        return redirect(url_for('activity.list_activities'))

    teacher_name = activity.teacher.name if activity.teacher else '未知'
    registered_count = Registration.query.filter_by(
        activity_id=activity_id, status='registered'
    ).count()

    # 当前学生是否已报名
    is_registered = False
    if session.get('role') == 'student' and session.get('user_id'):
        is_registered = Registration.query.filter_by(
            activity_id=activity_id,
            student_id=session['user_id'],
            status='registered',
        ).first() is not None

    return render_template(
        'activity/detail.html',
        activity=activity,
        teacher_name=teacher_name,
        registered_count=registered_count,
        is_registered=is_registered,
    )


@activity_bp.route('/teacher/activities/new', methods=['GET', 'POST'])
@require_role('teacher')
def new_activity():
    """发布活动 (REQ-04) - 仅审核通过的教师可访问"""
    current_user = User.query.get(session['user_id'])

    # 权限联动: 教师必须审核通过才能发布活动
    if current_user.status != 'approved':
        if current_user.status == 'pending':
            flash('您的账号尚未通过审核,暂无法发布活动', 'warning')
        else:
            flash('您的账号审核未通过,请联系管理员', 'danger')
        return redirect(url_for('activity.list_activities'))

    if request.method == 'POST':
        errors = []
        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip()
        location = (request.form.get('location') or '').strip()
        start_str = request.form.get('start_time') or ''
        end_str = request.form.get('end_time') or ''
        capacity_str = request.form.get('capacity') or ''
        deadline_str = request.form.get('register_deadline') or ''

        # 必填字段校验
        if not title:
            errors.append('活动标题不能为空')
        if not location:
            errors.append('活动地点不能为空')
        if not start_str:
            errors.append('开始时间不能为空')
        if not end_str:
            errors.append('结束时间不能为空')
        if not capacity_str:
            errors.append('名额上限不能为空')
        if not deadline_str:
            errors.append('报名截止时间不能为空')

        # 容量与时间解析
        capacity = None
        if capacity_str:
            try:
                capacity = int(capacity_str)
                if capacity <= 0:
                    errors.append('名额上限必须为正整数')
            except ValueError:
                errors.append('名额上限必须为整数')

        start_time = end_time = register_deadline = None
        try:
            if start_str:
                start_time = datetime.strptime(start_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            errors.append('开始时间格式不正确')
        try:
            if end_str:
                end_time = datetime.strptime(end_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            errors.append('结束时间格式不正确')
        try:
            if deadline_str:
                register_deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            errors.append('报名截止时间格式不正确')

        # 时间关系校验
        if start_time and end_time and start_time >= end_time:
            errors.append('开始时间必须早于结束时间')
        now = datetime.now()
        if register_deadline and register_deadline < now:
            errors.append('报名截止时间不能早于当前时间')
        if register_deadline and start_time and register_deadline > start_time:
            errors.append('报名截止时间不能晚于活动开始时间')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template(
                'activity/new.html',
                errors=errors,
                form=request.form,
            )

        activity = Activity(
            title=title,
            description=description,
            location=location,
            start_time=start_time,
            end_time=end_time,
            capacity=capacity,
            register_deadline=register_deadline,
            teacher_id=current_user.id,
            status='published',
        )
        db.session.add(activity)
        db.session.commit()

        flash('活动发布成功', 'success')
        return redirect(url_for('activity.detail', activity_id=activity.id))

    return render_template('activity/new.html', errors=None, form=None)


@activity_bp.route('/teacher/activities')
@require_role('teacher')
def my_activities():
    """我发布的活动列表"""
    activities = Activity.query.filter_by(teacher_id=session['user_id']) \
        .order_by(Activity.created_at.desc()).all()
    return render_template('activity/my_activities.html', activities=activities)