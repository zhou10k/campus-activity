# 校园活动管理系统 V1.0

> 三人行小组 · 基于工程意图的软件迭代开发

## 项目简介

校园活动管理系统（V1.0）是一个面向高校师生的轻量级 Web 应用，用于解决校园活动信息分散、报名统计困难的问题。系统支持学生浏览/报名活动、教师发布活动、管理员审核教师账号等核心业务。

**V1.0 功能列表**

- 三类角色注册与登录（学生 / 教师 / 管理员）
- 教师账号审核流程（防止身份冒用）
- 活动发布、列表浏览、详情查看
- 学生报名与取消报名
- 名额上限与报名截止时间自动控制

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

- 6 个测试用例（TEST-01 ~ TEST-06）已覆盖核心需求
- 2 个已修复 BUG（BUG-01：account 唯一性；BUG-02：报名截止时间校验）的回归验证通过
- 启动 `python app.py` 后可手动逐条执行测试

## 版本计划

- **V1.0（当前）**：注册 / 登录 / 审核 / 活动 / 报名基础闭环
- **V1.1（计划）**：邮件 / 短信通知
- **V1.2（计划）**：评论与评分、活动签到二维码

## 项目结构

```
campus-activity/
├── app.py                  # 应用入口
├── config.py               # 配置
├── models.py               # 数据模型
├── extensions.py           # SQLAlchemy 实例
├── blueprints/
│   ├── __init__.py
│   ├── auth.py             # 注册 / 登录
│   ├── activity.py         # 活动模块
│   ├── registration.py     # 报名模块
│   └── admin.py            # 审核模块
├── templates/
│   ├── base.html
│   ├── auth/
│   ├── activity/
│   ├── admin/
│   └── registration/
├── static/
│   ├── css/style.css
│   └── js/main.js
├── utils/
│   ├── __init__.py
│   └── decorators.py       # 权限装饰器
├── requirements.txt
└── .gitignore
```

## 团队分工

| 成员 | 职责 |
|------|------|
| 吴煦 | 后端开发 / Git 管理 |
| 侯斌 | 前端页面开发 |
| 周乐祺 | 需求分析 / 测试 / 文档 |

---

校园活动管理系统 V1.0 · 三人行小组