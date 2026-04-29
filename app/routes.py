from flask import Blueprint, current_app, jsonify, request

from app.services.auth_service import login_user, register_user
from app.services.orchestrator_service import run_orchestration
from app.services.user_platform_config_service import upsert_user_platform_config, upsert_user_profile

main_blueprint = Blueprint("main", __name__)


@main_blueprint.route("/", methods=["GET"])
def health_check():
    return jsonify(
        {
            "message": "Job Application Orchestrator API is running.",
            "entrypoint": "POST /orchestrate",
            "description": "Automated job application flow with authentication only.",
        }
    )


@main_blueprint.route("/orchestrate", methods=["POST"])
def orchestrate():
    payload = request.get_json(silent=True) or {}
    result = run_orchestration(payload)
    status_code = 200 if result.get("success") else 400
    current_app.logger.info(
        "Orchestrate response user_id=%s platform=%s mode=%s status_code=%s payload=%s",
        payload.get("user_id"),
        payload.get("platform"),
        payload.get("mode", "auto_apply"),
        status_code,
        result,
    )
    return jsonify(result), status_code


@main_blueprint.route("/auth/register", methods=["POST"])
def auth_register():
    payload = request.get_json(silent=True) or {}
    result = register_user(payload)
    status_code = 201 if result.get("success") else 400
    return jsonify(result), status_code


@main_blueprint.route("/auth/login", methods=["POST"])
def auth_login():
    payload = request.get_json(silent=True) or {}
    result = login_user(payload)
    status_code = 200 if result.get("success") else 401
    return jsonify(result), status_code


@main_blueprint.route("/users/platform-config", methods=["POST"])
def save_user_platform_config():
    payload = request.get_json(silent=True) or {}
    result = upsert_user_platform_config(payload)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@main_blueprint.route("/users/profile", methods=["POST"])
def save_user_profile():
    payload = request.get_json(silent=True) or {}
    result = upsert_user_profile(payload)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code
