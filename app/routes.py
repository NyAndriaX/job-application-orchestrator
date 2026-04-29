from flask import Blueprint, current_app, jsonify, request

from app.services.orchestrator_service import run_orchestration

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
        "Orchestrate response platform=%s mode=%s status_code=%s payload=%s",
        payload.get("platform"),
        payload.get("mode", "auto_apply"),
        status_code,
        result,
    )
    return jsonify(result), status_code
