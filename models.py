"""数据模型定义"""
from datetime import datetime
from sqlalchemy import Index, text

from extensions import db


class User(db.Model):
    """用户表 - 学生/教师/管理员"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(50), unique=True, nullable=False)  # 学号或工号
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student / teacher / admin
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending / approved / rejected
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
    status = db.Column(db.String(20), default='published', nullable=False)  # draft / published / closed / cancelled
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    registrations = db.relationship(
        'Registration', backref='activity', lazy='select',
        cascade='all, delete-orphan'
    )

    @property
    def registered_count(self):
        """已报名人数"""
        return Registration.query.filter_by(
            activity_id=self.id, status='registered'
        ).count()

    def __repr__(self):
        return f'<Activity {self.id}: {self.title}>'


class Registration(db.Model):
    """报名记录表"""
    __tablename__ = 'registrations'

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='registered', nullable=False)  # registered / cancelled
    registered_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # 部分唯一索引：同一活动同一学生只能有一条"已报名"记录（取消后允许重新报名）
    __table_args__ = (
        Index(
            'idx_registration_active',
            'activity_id', 'student_id',
            unique=True,
            sqlite_where=text("status='registered'"),
        ),
    )

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