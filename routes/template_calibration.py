import os
from typing import Callable

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from services.template_config_store import TemplateConfigStore


ALLOWED_TEMPLATE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
AREA_KEYS = ("x", "y", "width", "height")
FIELD_KEYS = (
    "todays_date",
    "price_1g",
    "price_8g",
    "logo_area",
    "address",
    "whatsapp_number",
    "social_handle",
)


def create_template_calibration_blueprint(
    admin_required: Callable,
    list_template_names: Callable,
    templates_dir: str,
    config_path: str,
) -> Blueprint:
    calibration_bp = Blueprint("template_calibration", __name__)
    config_store = TemplateConfigStore(config_path)

    def _is_allowed(filename: str) -> bool:
        extension = os.path.splitext(filename)[1].lower()
        return extension in ALLOWED_TEMPLATE_EXTENSIONS

    def _validate_area(field_name: str, value: object) -> tuple[bool, dict[str, float] | None, str | None]:
        if not isinstance(value, dict):
            return False, None, f"{field_name} must be an object with x, y, width, height."

        area: dict[str, float] = {}
        for key in AREA_KEYS:
            if key not in value:
                return False, None, f"{field_name}.{key} is required."
            raw_number = value[key]
            if not isinstance(raw_number, (int, float)):
                return False, None, f"{field_name}.{key} must be numeric."
            area[key] = float(raw_number)

        if area["width"] <= 0 or area["height"] <= 0:
            return False, None, f"{field_name} width and height must be greater than 0."
        if area["x"] < 0 or area["y"] < 0:
            return False, None, f"{field_name} x and y must be >= 0."
        if area["x"] + area["width"] > 1 or area["y"] + area["height"] > 1:
            return False, None, f"{field_name} must stay inside image bounds."

        return True, area, None

    @calibration_bp.route("/admin/template-calibration", methods=["GET"])
    @admin_required
    def calibration_page():
        selected_template = request.args.get("template", "").strip()
        templates = list_template_names()
        existing_config = config_store.load()

        if not selected_template and templates:
            selected_template = templates[0]

        selected_template = os.path.basename(selected_template)
        if selected_template and selected_template not in templates:
            selected_template = ""

        selected_areas = existing_config.get(selected_template) if selected_template else None
        return render_template(
            "calibrate.html",
            templates=templates,
            selected_template=selected_template,
            selected_areas=selected_areas,
        )

    @calibration_bp.route("/admin/template-calibration/upload", methods=["POST"])
    @admin_required
    def upload_template():
        template_file = request.files.get("template_image")
        if not template_file or not template_file.filename:
            flash("Please choose a template image.", "danger")
            return redirect(url_for("template_calibration.calibration_page"))

        filename = secure_filename(template_file.filename)
        if not _is_allowed(filename):
            flash("Template must be PNG, JPG, or JPEG.", "danger")
            return redirect(url_for("template_calibration.calibration_page"))

        os.makedirs(templates_dir, exist_ok=True)
        save_path = os.path.join(templates_dir, filename)
        template_file.save(save_path)

        flash("Template uploaded successfully.", "success")
        return redirect(url_for("template_calibration.calibration_page", template=filename))

    @calibration_bp.route("/admin/template-calibration/save", methods=["POST"])
    @admin_required
    def save_template_coordinates():
        payload = request.get_json(silent=True) or {}
        template_name = os.path.basename(str(payload.get("template_name", "")).strip())
        templates = set(list_template_names())

        if not template_name or template_name not in templates:
            return jsonify({"error": "Invalid template name."}), 400

        validated_areas: dict[str, dict[str, float]] = {}
        for field in FIELD_KEYS:
            valid, area, error = _validate_area(field, payload.get(field))
            if not valid:
                return jsonify({"error": error}), 400
            validated_areas[field] = area

        config_store.save_template_areas(template_name=template_name, areas=validated_areas)
        return jsonify({"message": "Template areas saved.", "template_name": template_name})

    return calibration_bp
