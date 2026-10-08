# 校园活动管理系统 V2.0

> 三人行小组 · 基于工程意图的软件迭代开发

## 项目简介

校园活动管理系统（V2.0）是一个面向高校师生的轻量级 Web 应用，用于解决校园活动信息分散、报名统计困难的问题。V2.0 在 V1.0「发布—浏览—报名」静态主线的基础上，补齐了「满员—候补—取消—补位」的动态闭环，并对权限与审核做了加固。

**V1.0 功能列表**

- 三类角色注册与登录（学生 / 教师 / 管理员）
- 教师账号审核流程（防止身份冒用）
- 活动发布、列表浏览、详情查看
- 学生报名与取消报名
- 名额上限与报名截止时间自动控制

**V2.0 新增功能**

- 报名状态机：`pending / confirmed / waitlist / rejected / cancelled` 五态，学生端四态可视
- 候补队列：满员自动进入候补，FIFO 排队，序号查询时计算（不落库）
- 取消—释放—自动补位：正式人员取消后名额释放，候补队首自动补位（同一事务）
- 审核分流：活动级审核开关，教师审核通过后再判名额（审核通过 ≠ 正式参加）
- 资格条件：活动级资格说明公开
- 平台级权限加固：学生仅操作本人报名、教师仅维护本人活动，越权返回 403
- 管理员处置：平台活动全量查看与下架处置（不影响名单与候补）、账号停用/恢复
- 前端增强：活动搜索筛选、名额看板、审核工作台

## 技术栈

- 后端框架：Flask
- ORM：Flask-SQLAlchemy
- 数据库：SQLite（本地文件 `db.sqlite3`）
- 模板引擎：Jinja2
- 密码哈希：werkzeug.security（PBKDF2-SHA256）

## 快速开始

### 环境要求

- Python 3.10+

### 安装与启动

```bash
# 1. 克隆仓库
git clone <仓库地址>
cd campus-activity

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用
python app.py
```

访问地址：<http://127.0.0.1:5000/>

首次启动会自动建表并创建初始管理员账号 `admin / admin123`。

## 默认账号清单

| 角色 | 账号 | 密码 | 说明 |
|------|------|------|------|
| 管理员 | admin | admin123 | 初始管理员，可审核教师账号 |
| 学生 | 2026001 | （注册时设定） | 测试用学生账号 |
| 教师 | T001 | （注册后需审核） | 测试用教师账号，需管理员审核通过后方可发布活动 |

## 系统架构

三层架构：表现层（HTML / CSS / JS） + 业务层（Flask 蓝图） + 数据层（SQLite / SQLAlchemy）

### 模块划分

| 蓝图 | 职责 |
|------|------|
| `auth` | 注册 / 登录 / 登出 |
| `admin` | 教师审核 |
| `activity` | 活动列表 / 详情 / 发布 |
| `registration` | 报名 / 取消 / 我的活动 |

### 数据表

- `users` — 用户（学生 / 教师 / 管理员）
- `activities` — 活动
- `registrations` — 报名记录（含部分唯一索引）
- `audit_logs` — 教师审核日志

## 核心业务流程

以「学生查看活动并报名」为例的 5 步 HTTP 请求链路：

1. 登录 — `POST /login`
2. 查看活动列表 — `GET /activities`
3. 查看活动详情 — `GET /activity/<id>`
4. 报名 — `POST /activity/<id>/register`
5. 查看我的活动 — `GET /my/activities`

## 接口说明

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET, POST | `/register` | 注册 | 未登录 |
| GET, POST | `/login` | 登录 | 未登录 |
| GET | `/logout` | 登出 | 已登录 |
| GET | `/activities` | 活动列表（分页） | 公开 |
| GET | `/activity/<id>` | 活动详情 | 公开 |
| POST | `/activity/<id>/register` | 学生报名 | 学生 |
| POST | `/activity/<id>/cancel` | 取消报名 | 学生 |
| GET | `/my/activities` | 我的活动 | 学生 |
| GET, POST | `/teacher/activities/new` | 发布活动 | 已审核教师 |
| GET | `/teacher/activities` | 我的发布 | 教师 |
| GET | `/admin/audit` | 待审核教师列表 | 管理员 |
| POST | `/admin/audit/<teacher_id>` | 审核操作 | 管理员 |

## 测试说明

- V1.0 的 6 个测试用例（TEST-01 ~ TEST-06）已覆盖基础需求
- V2.0 新增至 16 个测试用例（TEST-01 ~ TEST-16），覆盖审核分流、候补补位、权限越权拦截、管理员处置等新规则，并保留 V1.0 回归项
- 一键运行：`python verify_v2.py`（使用临时库，不污染本地数据）
- 2 个历史 BUG（BUG-01：account 唯一性；BUG-02：报名截止时间校验）的回归验证通过

## 数据迁移

V1.0 → V2.0 存量数据迁移：`python migrate_v2.py`

- `registrations.status` 的 `registered` 映射为 `confirmed`
- 新增列（`users.account_status`、`activities.eligibility/require_review`、`registrations.waitlist_at/reject_reason`）均给出默认值
- 重建部分唯一索引以覆盖新的未终结三态

## 版本计划

- **V1.0**：注册 / 登录 / 审核 / 活动 / 报名基础闭环
- **V2.0（当前）**：报名状态机、候补队列与自动补位、审核分流、权限加固、管理员处置
- **V2.1（计划）**：邮件 / 短信通知
- **V2.2（计划）**：评论与评分、活动签到二维码

## 项目结构

```
campus-activity/
├── app.py                  # 应用入口
├── config.py               # 配置
├── models.py               # 数据模型（五态报名状态机）
├── extensions.py           # SQLAlchemy 实例
├── migrate_v2.py           # V2.0 存量数据迁移脚本
├── verify_v2.py            # V2.0 端到端验证脚本（16 条用例）
├── blueprints/
│   ├── __init__.py
│   ├── auth.py             # 注册 / 登录
│   ├── activity.py         # 活动模块
│   ├── registration.py     # 报名 / 取消 / 我的活动
│   ├── teacher.py          # 审核工作台 / 名单（V2.0 新增）
│   └── admin.py            # 账号审核 / 活动处置（V2.0 扩展）
├── services/
│   ├── __init__.py
│   └── registration_service.py  # 状态机 / 候补队列 / 补位事务（V2.0 新增）
├── templates/
│   ├── base.html
│   ├── auth/
│   ├── activity/
│   ├── teacher/            # 审核工作台 / 名单（V2.0 新增）
│   ├── admin/
│   └── registration/
├── static/
│   ├── css/style.css
│   └── js/main.js
├── utils/
│   ├── __init__.py
│   └── decorators.py       # 角色级 + 数据级权限装饰器
├── requirements.txt
└── .gitignore
```

## 团队分工

| 成员 | 职责 |
|------|------|
| 侯斌 | V2.0 主要迭代开发（后端核心 / 前端页面 / 接口联调） |
| 吴煦 | 项目管理 / 后端协同 / Git 分支管理与合并 |
| 周乐祺 | 需求分析 / 测试 / 文档 |

---

校园活动管理系统 V2.0 · 三人行小组