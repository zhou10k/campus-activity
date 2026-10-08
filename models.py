"""数据模型定义 - V2.0

V2.0 相对 V1.0 的核心变化：
- registrations：由两态（registered / cancelled）扩展为五态状态机
  （pending / confirmed / waitlist / rejected / cancelled），并新增
  waitlist_at 承载「进入候补时间」，作为 FIFO 候补序号的排序依据。
- activities：新增 eligibility（资格条件说明）与 require_review（是否需要审核）两个活动级属性。
- users：新增 account_status（账号能否登录），与原有 status（教师能否发布活动）严格区分。
"""
from datetime import datetime
from sqlalchemy import Index, text

from extensions import db


# ------------------------------------------------------------------
# 状态常量（状态迁移唯一入口的取值来源）
# ------------------------------------------------------------------
class RegistrationStatus:
    PENDING = 'pending'        # 待审核（活动开启审核时，提交后的初始状态）
    CONFIRMED = 'confirmed'    # 正式参加（已占名额）
    WAITLIST = 'waitlist'      # 候补中（名额已满，排队等待）
    REJECTED = 'rejected'      # 未通过（审核拒绝）
    CANCELLED = 'cancelled'    # 已取消（主动退出，非终态可重新提交）

    ALL = (PENDING, CONFIRMED, WAITLIST, REJECTED, CANCELLED)
    # 占用「正式名额」的状态集合
    OCCUPY = (CONFIRMED,)
    # 占用「候补位」的状态集合
    QUEUE = (WAITLIST,)


class ActivityStatus:
    DRAFT = 'draft'
    PUBLISHED = 'published'
    CLOSED = 'closed'
    CANCELLED = 'cancelled'
    DELISTED = 'delisted'      # V2.0 新增：管理员下架处置


class AccountStatus:
    ACTIVE = 'active'          # 账号可用
    DISABLED = 'disabled'      # 账号停用（不可登录）


class TeacherAuditStatus:
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'


class User(db.Model):
    """用户表 - 学生/教师/管理员"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(50), unique=True, nullable=False)  # 学号或工号
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student / teacher / admin
    # 教师审核状态：能否发布活动（V1.0 已有）
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending / approved / rejected
    # V2.0 新增：账号状态，表示「账号能否登录」，与上面的教师审核状态语义不同，不可合并
    account_status = db.Column(db.String(20), default='active', nullable=False)  # active / disabled
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # 反向关系
    activities = db.relationship(
        'Activity', backref='teacher', lazy='select',
        foreign_keys='Activity.teacher_id'
    )
    registrations = db.relationship(
        'Registration', backref='student', lazy='select',
        foreign_keys='Registration.student_id'
    )

    def is_admin(self):
        return self.role == 'admin'

    def is_teacher(self):
        return self.role == 'teacher'

    def is_student(self):
        return self.role == 'student'

    def can_login(self):
        """账号层面是否允许登录（与教师审核状态无关）"""
        return self.account_status == AccountStatus.ACTIVE

    def __repr__(self):
        return f'<User {self.account} ({self.role})>'


class Activity(db.Model):
    """活动表"""
    __tablename__ = 'activities'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    capacity = db.Column(db.Integer, nullable=False)
    register_deadline = db.Column(db.DateTime)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='published', nullable=False)  # draft / published / closed / cancelled / delisted
    # V2.0 新增：活动级资格条件与审核开关（默认关闭，保持与 V1.0 行为一致）
    eligibility = db.Column(db.String(200))  # 资格条件说明，如「限计算机学院大二以上」
    require_review = db.Column(db.Boolean, default=False, nullable=False)  # 是否需要教师审核
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    registrations = db.relationship(
        'Registration', backref='activity', lazy='select',
        cascade='all, delete-orphan'
    )

    @property
    def confirmed_count(self):
        """已确定（正式参加）人数"""
        return Registration.query.filter_by(
            activity_id=self.id, status=RegistrationStatus.CONFIRMED
        ).count()

    @property
    def registered_count(self):
        """兼容 V1.0 命名：等同于已确定人数"""
        return self.confirmed_count

    @property
    def waitlist_count(self):
        """候补人数"""
        return Registration.query.filter_by(
            activity_id=self.id, status=RegistrationStatus.WAITLIST
        ).count()

    @property
    def remaining(self):
        """剩余名额"""
        return max(self.capacity - self.confirmed_count, 0)

    def is_full(self):
        return self.confirmed_count >= self.capacity

    def __repr__(self):
        return f'<Activity {self.id}: {self.title}>'


class Registration(db.Model):
    """报名记录表 - V2.0 五态状态机"""
    __tablename__ = 'registrations'

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # pending / confirmed / waitlist / rejected / cancelled
    status = db.Column(db.String(20), default='confirmed', nullable=False)
    # 状态进入时间（V1.0 字段名 registered_at 保留，语义扩展为「记录创建时间」）
    registered_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    # V2.0 新增：进入候补队列的时间，作为 FIFO 序号的排序依据（序号本身不落库）
    waitlist_at = db.Column(db.DateTime)
    # V2.0 新增：审核拒绝时记录的原因
    reject_reason = db.Column(db.Text)

    # 部分唯一索引：同一活动同一学生只能有一条「未终结」记录
    # 未终结 = pending / confirmed / waitlist（cancelled / rejected 后可重新提交）
    __table_args__ = (
        Index(
            'idx_registration_active',
            'activity_id', 'student_id',
            unique=True,
            sqlite_where=text("status IN ('pending','confirmed','waitlist')"),
        ),
    )

    @property
    def waitlist_no(self):
        """候补序号 - 按进入候补时间升序在查询时计算，不落库

        序号从 1 开始；非候补状态返回 None。
        时间相同的极端情况以 id 升序作为次级排序，保证 FIFO 稳定。
        """
        if self.status != RegistrationStatus.WAITLIST or not self.waitlist_at:
            return None
        # 排在前面：更早进入候补，或同一时刻但 id 更小
        earlier = Registration.query.filter(
            Registration.activity_id == self.activity_id,
            Registration.status == RegistrationStatus.WAITLIST,
            db.or_(
                Registration.waitlist_at < self.waitlist_at,
                db.and_(
                    Registration.waitlist_at == self.waitlist_at,
                    Registration.id < self.id,
                ),
            ),
        ).count()
        return earlier + 1

    def __repr__(self):
        return f'<Registration activity={self.activity_id} student={self.student_id} status={self.status}>'


class AuditLog(db.Model):
    """教师审核日志表"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    decision = db.Column(db.String(20), nullable=False)  # approved / rejected
    reason = db.Column(db.Text)
    decided_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    teacher = db.relationship('User', foreign_keys=[teacher_id])
    admin = db.relationship('User', foreign_keys=[admin_id])

    def __repr__(self):
        return f'<AuditLog teacher={self.teacher_id} decision={self.decision}>'


class RegistrationLog(db.Model):
    """报名/审核/补位操作日志表（V2.0 新增，便于追溯状态流转）"""
    __tablename__ = 'registration_logs'

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    from_status = db.Column(db.String(20))
    to_status = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    def __repr__(self):
        return f'<RegistrationLog {self.from_status}->{self.to_status}>'
