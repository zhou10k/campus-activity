"""管理蓝图 - 教师账号审核 (REQ-03)"""
from datetime import datetime

from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for
)

from extensions import db
from models import AuditLog, User
from utils.decorators import require_role

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


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