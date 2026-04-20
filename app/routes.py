from flask import Blueprint, current_app, jsonify, request

from app.services.browser_service import open_target_homepage

main_blueprint = Blueprint("main", __name__)


@main_blueprint.route("/", methods=["GET"])
def health_check():
    return jsonify(
        {
            "message": "Job Application Orchestrator API is running.",
            "next_step": "POST /navigate with payload {'target': 'asako' | 'portaljob'}",
        }
    )


@main_blueprint.route("/navigate", methods=["POST"])
def navigate():
    payload = request.get_json(silent=True) or {}
    target = payload.get("target")
    if not isinstance(target, str) or not target.strip():
        result = {
            "success": False,
            "error": "Payload must include a non-empty string field: target.",
        }
        current_app.logger.info(
            "Navigate response target=%s status_code=%s payload=%s",
            target,
            400,
            result,
        )
        return jsonify(result), 400

    result = open_target_homepage(target=target)
    status_code = 200 if result.get("success") else 400
    current_app.logger.info(
        "Navigate response target=%s status_code=%s payload=%s",
        target,
        status_code,
        result,
    )
    return jsonify(result), status_code
