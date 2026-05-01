from flask import Blueprint, current_app, jsonify, request

from app.services.auth_service import login_user, register_user
from app.services.orchestrator_service import run_orchestration
from app.services.auto_apply_scheduler import run_auto_apply_now
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
        "Orchestrate response user_id=%s platform=%s mode=%s status_code=%s success=%s",
        payload.get("user_id"),
        payload.get("platform"),
        payload.get("mode", "auto_apply"),
        status_code,
        bool(result.get("success")),
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


@main_blueprint.route("/scheduler/run-now", methods=["POST"])
def run_scheduler_now():
    summary = run_auto_apply_now()
    current_app.logger.info(
        "Scheduler run-now executions=%s successes=%s failures=%s",
        summary.get("executions", 0),
        summary.get("successes", 0),
        summary.get("failures", 0),
    )
    return (
        jsonify(
            {
                "success": True,
                "mode": "auto_apply",
                "scope": "all_users",
                "summary": summary,
            }
        ),
        200,
    )
