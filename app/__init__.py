import os

from flask import Flask
from flask_cors import CORS

from app.routes import main_blueprint
from app.services.auto_apply_scheduler import start_auto_apply_scheduler
from app.services.mongo_service import ensure_mongo_indexes


def _get_cors_origins() -> list[str]:
    raw_origins = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(
        app,
        resources={r"/*": {"origins": _get_cors_origins()}},
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    ensure_mongo_indexes()
    app.register_blueprint(main_blueprint)
    start_auto_apply_scheduler()
    return app
