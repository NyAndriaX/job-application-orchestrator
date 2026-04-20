from flask import Blueprint, jsonify

from app.services.browser_service import open_asako_homepage

main_blueprint = Blueprint("main", __name__)


@main_blueprint.route("/", methods=["GET"])
def health_check():
    return jsonify(
        {
            "message": "Job Application Orchestrator API is running.",
            "next_step": "POST /navigate/asako to open https://asako.mg/",
        }
    )


@main_blueprint.route("/navigate/asako", methods=["POST"])
def navigate_asako():
    result = open_asako_homepage()
    status_code = 200 if result.get("success") else 504
    return jsonify(result), status_code
