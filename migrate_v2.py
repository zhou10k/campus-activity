"""V2.0 存量数据迁移脚本

在 V1.0 数据库（db.sqlite3）上执行，完成：
1. users 表新增 account_status 列（默认 active）
2. activities 表新增 eligibility / require_review 列（默认 NULL / 0）
3. registrations 表新增 waitlist_at / reject_reason 列
4. registrations.status 的存量取值迁移：registered -> confirmed
5. 重建 registrations 上的部分唯一索引（覆盖新三态）

用法：
    python migrate_v2.py

脚本幂等：重复执行不会报错（列已存在则跳过）。
"""
import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'db.sqlite3')


def _column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def main():
    if not os.path.exists(DB_PATH):
        print(f'[SKIP] 未找到数据库 {DB_PATH}，无需迁移（首次启动将直接按 V2.0 建表）')
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1) users.account_status
    if not _column_exists(cur, 'users', 'account_status'):
        cur.execute("ALTER TABLE users ADD COLUMN account_status VARCHAR(20) DEFAULT 'active' NOT NULL")
        print('[OK] users.account_status 已新增')
    else:
        print('[SKIP] users.account_status 已存在')

    # 2) activities.eligibility / require_review
    if not _column_exists(cur, 'activities', 'eligibility'):
        cur.execute("ALTER TABLE activities ADD COLUMN eligibility VARCHAR(200)")
        print('[OK] activities.eligibility 已新增')
    else:
        print('[SKIP] activities.eligibility 已存在')

    if not _column_exists(cur, 'activities', 'require_review'):
        cur.execute("ALTER TABLE activities ADD COLUMN require_review BOOLEAN DEFAULT 0 NOT NULL")
        print('[OK] activities.require_review 已新增')
    else:
        print('[SKIP] activities.require_review 已存在')

    # 3) registrations.waitlist_at / reject_reason
    if not _column_exists(cur, 'registrations', 'waitlist_at'):
        cur.execute("ALTER TABLE registrations ADD COLUMN waitlist_at DATETIME")
        print('[OK] registrations.waitlist_at 已新增')
    else:
        print('[SKIP] registrations.waitlist_at 已存在')

    if not _column_exists(cur, 'registrations', 'reject_reason'):
        cur.execute("ALTER TABLE registrations ADD COLUMN reject_reason TEXT")
        print('[OK] registrations.reject_reason 已新增')
    else:
        print('[SKIP] registrations.reject_reason 已存在')

    # 4) 状态取值迁移：registered -> confirmed（存量语义保持：已占名额）
    cur.execute("UPDATE registrations SET status='confirmed' WHERE status='registered'")
    migrated = cur.rowcount
    print(f'[OK] registrations 状态迁移 registered -> confirmed，共 {migrated} 条')

    # 5) 重建部分唯一索引（覆盖 pending / confirmed / waitlist）
    cur.execute("DROP INDEX IF EXISTS idx_registration_active")
    cur.execute(
        "CREATE UNIQUE INDEX idx_registration_active "
        "ON registrations (activity_id, student_id) "
        "WHERE status IN ('pending','confirmed','waitlist')"
    )
    print('[OK] 部分唯一索引 idx_registration_active 已重建')

    conn.commit()
    conn.close()
    print('[DONE] V2.0 数据迁移完成')


if __name__ == '__main__':
    main()
