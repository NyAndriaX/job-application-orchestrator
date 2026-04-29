from flask import Flask

from app.routes import main_blueprint
from app.services.mongo_service import ensure_mongo_indexes


def create_app() -> Flask:
    app = Flask(__name__)
    ensure_mongo_indexes()
    app.register_blueprint(main_blueprint)
    return app
