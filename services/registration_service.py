"""状态机与候补队列服务 - V2.0 后端核心

关键规则（与实验报告第八章对应）：
- 关键规则一：状态迁移唯一入口。所有状态变化都必须经过 transition()，
  由它集中校验「当前状态是否允许迁移到目标状态」，杜绝各接口各写一份判断。
- 关键规则二：名额判定复用。直接报名、审核通过、候补补位共用 occupy_slot()。
- 关键规则三：序号不落库。候补序号按 waitlist_at 升序在查询时计算。
- 关键规则四：事务边界。取消→释放→补位三步在同一事务内完成，失败整体回滚。
- 关键规则五：审核与名额解耦。审核接口只判资格；名额判定在审核通过之后单独执行。
"""
from datetime import datetime

from extensions import db
from models import (
    Activity, Registration, RegistrationLog, RegistrationStatus,
)


# ------------------------------------------------------------------
# 关键规则一：允许的状态迁移表
# ------------------------------------------------------------------
ALLOWED_TRANSITIONS = {
    # from -> {允许的 to 集合}
    None: {RegistrationStatus.PENDING, RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLIST},
    RegistrationStatus.PENDING: {RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLIST, RegistrationStatus.REJECTED},
    RegistrationStatus.CONFIRMED: {RegistrationStatus.CANCELLED},
    RegistrationStatus.WAITLIST: {RegistrationStatus.CONFIRMED, RegistrationStatus.CANCELLED},
    RegistrationStatus.REJECTED: set(),   # 终态，可重新提交（新建记录）
    RegistrationStatus.CANCELLED: set(),  # 终态，可重新提交（新建记录）
}

# 占用「正式名额」的状态（关键规则二复用）
_OCCUPY_STATES = RegistrationStatus.OCCUPY


class TransitionError(Exception):
    """非法状态迁移"""


def transition(reg, to_status, reason=None, operator_id=None, commit=True, is_new=False):
    """状态迁移唯一入口

    :param reg: Registration 实例
    :param to_status: 目标状态
    :param reason: 备注/拒绝原因
    :param operator_id: 操作者 id（审核时为教师，补位时为系统 None）
    :param is_new: 新建记录的首次落态（此时不校验 from 状态）
    :raises TransitionError: 当前状态不允许迁移到目标状态
    """
    if to_status not in RegistrationStatus.ALL:
        raise TransitionError(f'未知目标状态: {to_status}')

    from_status = None if is_new else reg.status
    allowed = ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise TransitionError(f'不允许的状态迁移: {from_status} -> {to_status}')

    reg.status = to_status
    # 进入候补时打上时间戳（FIFO 排序依据）
    if to_status == RegistrationStatus.WAITLIST:
        reg.waitlist_at = datetime.now()
    # 审核拒绝时记录原因
    if to_status == RegistrationStatus.REJECTED:
        reg.reject_reason = reason or None

    log = RegistrationLog(
        activity_id=reg.activity_id,
        student_id=reg.student_id,
        operator_id=operator_id,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        created_at=datetime.now(),
    )
    db.session.add(log)
    if commit:
        db.session.commit()
    return reg


# ------------------------------------------------------------------
# 关键规则二：名额占用判定（所有入口复用同一函数）
# ------------------------------------------------------------------
def occupy_slot(activity):
    """判断活动当前是否还有「正式名额」可占用"""
    return activity.confirmed_count < activity.capacity


# ------------------------------------------------------------------
# 候补队列
# ------------------------------------------------------------------
def waitlist_queue(activity_id):
    """返回候补队列（按进入候补时间升序 = FIFO）"""
    return Registration.query.filter_by(
        activity_id=activity_id, status=RegistrationStatus.WAITLIST
    ).order_by(Registration.waitlist_at.asc(), Registration.id.asc()).all()


def waitlist_position(reg):
    """候补序号（从 1 开始），非候补返回 None"""
    return reg.waitlist_no


# ------------------------------------------------------------------
# 报名主流程（关键规则五：审核与名额解耦）
# ------------------------------------------------------------------
def submit_registration(activity, student_id):
    """提交报名

    两处分流：
    - 审核分流：活动开启 require_review 时，先进入 pending 待审核；
      否则直接进入名额分流。
    - 名额分流：无论是否经过审核，最终按「当时剩余名额」决定
      是 confirmed 还是 waitlist。

    :return: (Registration, str message)
    """
    now = datetime.now()

    # 已存在未终结记录 -> 不允许重复提交
    existing = Registration.query.filter(
        Registration.activity_id == activity.id,
        Registration.student_id == student_id,
        Registration.status.in_((
            RegistrationStatus.PENDING,
            RegistrationStatus.CONFIRMED,
            RegistrationStatus.WAITLIST,
        )),
    ).first()
    if existing:
        return existing, '您已提交过本活动的报名'

    reg = Registration(
        activity_id=activity.id,
        student_id=student_id,
        status=RegistrationStatus.PENDING,  # 占位，随即由 transition 落定
        registered_at=now,
    )
    db.session.add(reg)

    # 审核分流：开启审核先进入 pending
    if activity.require_review:
        transition(reg, RegistrationStatus.PENDING, commit=False, is_new=True)
        db.session.commit()
        return reg, '报名已提交，等待教师审核'

    # 名额分流（复用 occupy_slot）
    if occupy_slot(activity):
        transition(reg, RegistrationStatus.CONFIRMED, commit=False, is_new=True)
        db.session.commit()
        return reg, '报名成功，已确定为正式参加'
    else:
        transition(reg, RegistrationStatus.WAITLIST, commit=False, is_new=True)
        db.session.commit()
        return reg, '名额已满，已进入候补队列'


# ------------------------------------------------------------------
# 教师审核（关键规则五：只判资格，不判名额）
# ------------------------------------------------------------------
def review_registration(reg, activity, approve, teacher_id, reason=None):
    """教师审核本人活动的报名申请

    - approve=True：先判资格（此处即审核），通过后单独执行名额判定。
    - approve=False：直接置为 rejected 并记录原因。

    :raises TransitionError: 状态不允许审核
    """
    if reg.status != RegistrationStatus.PENDING:
        raise TransitionError('仅「待审核」的申请可以审核')

    if not approve:
        transition(reg, RegistrationStatus.REJECTED, reason=reason,
                   operator_id=teacher_id, commit=False)
        db.session.commit()
        return reg, '已拒绝该申请'

    # 审核通过 -> 再判名额（审核通过 ≠ 正式参加）
    if occupy_slot(activity):
        transition(reg, RegistrationStatus.CONFIRMED, operator_id=teacher_id, commit=False)
        msg = '审核通过，已确定为正式参加'
    else:
        transition(reg, RegistrationStatus.WAITLIST, operator_id=teacher_id, commit=False)
        msg = '审核通过，但名额已满，已进入候补队列'
    db.session.commit()
    return reg, msg


# ------------------------------------------------------------------
# 取消 -> 释放 -> 自动补位（关键规则四：同一事务）
# ------------------------------------------------------------------
def cancel_registration(reg, activity):
    """取消报名并触发自动补位

    两种情况：
    - 取消的是「正式参加」：释放一个名额，候补队首自动补位。
    - 取消的是「候补中」：从队列移除，后续候补序号自然前移（序号查询时计算）。
    """
    try:
        if reg.status == RegistrationStatus.CONFIRMED:
            transition(reg, RegistrationStatus.CANCELLED, commit=False)
            # 释放名额 -> 队首补位（同一事务，失败整体回滚）
            queue = waitlist_queue(activity.id)
            if queue:
                head = queue[0]
                transition(head, RegistrationStatus.CONFIRMED, commit=False)
                db.session.commit()
                return reg, f'已取消报名，候补第 1 位已自动补位为正式参加'
            db.session.commit()
            return reg, '已取消报名，名额已释放'

        elif reg.status == RegistrationStatus.WAITLIST:
            transition(reg, RegistrationStatus.CANCELLED, commit=False)
            db.session.commit()
            return reg, '已退出候补队列'

        else:
            raise TransitionError('当前状态无法取消')
    except Exception:
        db.session.rollback()
        raise
