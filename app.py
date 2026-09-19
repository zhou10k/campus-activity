"""应用入口"""
from flask import Flask, redirect, url_for
from werkzeug.security import generate_password_hash

from config import Config
from extensions import db


def create_app():
    """工厂函数 - 创建 Flask 应用实例"""
    app = Flask(__name__)
    app.config.from_object(Config)

    # 初始化扩展
    db.init_app(app)

    # 注册蓝图
    from blueprints.auth import auth_bp
    from blueprints.admin import admin_bp
    from blueprints.activity import activity_bp
    from blueprints.registration import registration_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(activity_bp)
    app.register_blueprint(registration_bp)

    # 根路径跳转
    @app.route('/')
    def index():
        return redirect(url_for('activity.list_activities'))

    # 首次启动建表 + 创建初始管理员
    with app.app_context():
        import models  # noqa: F401 - 确保模型被注册到 SQLAlchemy metadata
        db.create_all()
        _ensure_initial_admin()

    return app


def _ensure_initial_admin():
    """首次启动时检查是否已存在管理员账号, 若不存在则创建 admin/admin123"""
    from models import User

    admin = User.query.filter_by(role='admin').first()
    if admin:
        return
    user = User(
        account='admin',
        password_hash=generate_password_hash('admin123', method='pbkdf2:sha256'),
        name='系统管理员',
        role='admin',
        status='approved',
    )
    db.session.add(user)
    db.session.commit()
    print('[INFO] 已创建初始管理员账号: admin / admin123')


# 顶层 app 供 flask run / python app.py 使用
app = create_app()


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)