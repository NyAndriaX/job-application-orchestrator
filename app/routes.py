from flask import Blueprint, current_app, jsonify, request

from app.services.auth_service import login_user, register_user
from app.services.orchestrator_service import run_orchestration
from app.services.auto_apply_scheduler import get_scheduler_status, run_auto_apply_now
from app.services.user_platform_config_service import upsert_user_platform_config, upsert_user_profile
from app.services.mongo_service import (
    get_job_applications_collection,
    get_scheduler_tasks_collection,
    get_users_collection,
)

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


@main_blueprint.route("/users/platform-config", methods=["GET"])
def get_user_platform_config():
    user_id = request.args.get("user_id", "").strip()
    platform = request.args.get("platform", "").strip().lower()
    if not user_id:
        return jsonify({"success": False, "error": "user_id query param is required."}), 400

    users = get_users_collection()
    user_doc = users.find_one({"user_id": user_id}, {"_id": 0, "platform_configs": 1})
    if not user_doc:
        return jsonify({"success": False, "error": "User not found for this user_id."}), 404

    platform_configs = user_doc.get("platform_configs") or {}
    if not isinstance(platform_configs, dict):
        platform_configs = {}

    if platform:
        return jsonify(
            {
                "success": True,
                "user_id": user_id,
                "platform": platform,
                "config": platform_configs.get(platform) or {},
            }
        ), 200

    return jsonify({"success": True, "user_id": user_id, "platform_configs": platform_configs}), 200


@main_blueprint.route("/users/profile", methods=["POST"])
def save_user_profile():
    payload = request.get_json(silent=True) or {}
    result = upsert_user_profile(payload)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@main_blueprint.route("/users/profile", methods=["GET"])
def get_user_profile():
    user_id = request.args.get("user_id", "").strip()
    if not user_id:
        return jsonify({"success": False, "error": "user_id query param is required."}), 400

    users = get_users_collection()
    user_doc = users.find_one({"user_id": user_id}, {"_id": 0, "user_id": 1, "profile": 1})
    if not user_doc:
        return jsonify({"success": False, "error": "User not found for this user_id."}), 404

    profile = user_doc.get("profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    return jsonify({"success": True, "user_id": user_id, "profile": profile}), 200


@main_blueprint.route("/jobs", methods=["GET"])
def list_job_applications():
    user_id = request.args.get("user_id", "").strip()
    platform = request.args.get("platform", "").strip()
    status = request.args.get("status", "").strip()
    limit = min(int(request.args.get("limit", 100)), 500)

    if not user_id:
        return jsonify({"success": False, "error": "user_id query param is required."}), 400

    query = {"user_id": user_id}
    if platform:
        query["platform"] = platform
    if status:
        query["status"] = status

    collection = get_job_applications_collection()
    cursor = collection.find(query, {"_id": 0}).sort("applied_at", -1).limit(limit)
    jobs = list(cursor)
    return jsonify({"success": True, "total": len(jobs), "jobs": jobs}), 200


@main_blueprint.route("/scheduler/status", methods=["GET"])
def scheduler_status():
    return jsonify({"success": True, **get_scheduler_status()}), 200


@main_blueprint.route("/scheduler/tasks", methods=["GET"])
def list_scheduler_tasks():
    limit = min(int(request.args.get("limit", 20)), 100)
    collection = get_scheduler_tasks_collection()
    cursor = collection.find({}, {"_id": 0}).sort("started_at", -1).limit(limit)
    tasks = list(cursor)
    return jsonify({"success": True, "total": len(tasks), "tasks": tasks}), 200


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
