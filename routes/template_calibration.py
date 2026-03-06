import os
from typing import Callable

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from services.template_config_store import TemplateConfigStore


ALLOWED_TEMPLATE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_FONT_EXTENSIONS = {".ttf"}
AREA_KEYS = ("x", "y", "width", "height")
ALIGNMENT_OPTIONS = {"left", "center", "right"}
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
    fonts_dir = os.path.join(os.path.dirname(templates_dir), "fonts")

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

    def _list_available_fonts() -> list[str]:
        if not os.path.isdir(fonts_dir):
            return []
        fonts = [
            filename
            for filename in os.listdir(fonts_dir)
            if os.path.isfile(os.path.join(fonts_dir, filename))
            and os.path.splitext(filename)[1].lower() in ALLOWED_FONT_EXTENSIONS
        ]
        return sorted(fonts, key=str.lower)

    def _validate_styling(field_name: str, value: object) -> tuple[bool, dict[str, object] | None, str | None]:
        if field_name == "logo_area":
            return True, {}, None
        if not isinstance(value, dict):
            return False, None, f"{field_name} must be an object."

        style: dict[str, object] = {}
        font_family = value.get("font_family")
        if isinstance(font_family, str) and font_family.strip():
            style["font_family"] = font_family.strip()
        else:
            style["font_family"] = ""

        raw_color = value.get("font_color")
        if raw_color is None:
            style["font_color"] = [255, 255, 255]
        elif isinstance(raw_color, (list, tuple)) and len(raw_color) >= 3 and all(
            isinstance(part, (int, float)) for part in raw_color[:3]
        ):
            style["font_color"] = [max(0, min(255, int(raw_color[0]))), max(0, min(255, int(raw_color[1]))), max(0, min(255, int(raw_color[2])))]
        else:
            return False, None, f"{field_name}.font_color must be an RGB array."

        font_size_raw = value.get("font_size")
        if isinstance(font_size_raw, (int, float)) and int(font_size_raw) > 0:
            font_size = int(font_size_raw)
        else:
            max_from_payload = value.get("max_font_size", 60)
            if isinstance(max_from_payload, (int, float)) and int(max_from_payload) > 0:
                font_size = int(max_from_payload)
            else:
                font_size = 60

        style["font_size"] = font_size

        font_weight = str(value.get("font_weight", "700")).strip()
        if font_weight not in {"400", "500", "600", "700", "800", "normal", "bold"}:
            font_weight = "700"
        style["font_weight"] = font_weight

        max_font_size_raw = value.get("max_font_size", font_size)
        min_font_size_raw = value.get("min_font_size", font_size)
        if not isinstance(max_font_size_raw, (int, float)) or int(max_font_size_raw) <= 0:
            return False, None, f"{field_name}.max_font_size must be a positive number."
        if not isinstance(min_font_size_raw, (int, float)) or int(min_font_size_raw) <= 0:
            return False, None, f"{field_name}.min_font_size must be a positive number."

        max_font_size = int(max_font_size_raw)
        min_font_size = int(min_font_size_raw)
        if min_font_size > max_font_size:
            min_font_size = max_font_size
        style["max_font_size"] = max_font_size
        style["min_font_size"] = min_font_size

        alignment = str(value.get("alignment", "center")).strip().lower()
        if alignment not in ALIGNMENT_OPTIONS:
            return False, None, f"{field_name}.alignment must be left, center, or right."
        style["alignment"] = alignment

        return True, style, None

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
            available_fonts=_list_available_fonts(),
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

        validated_areas: dict[str, dict[str, object]] = {}
        for field in FIELD_KEYS:
            valid, area, error = _validate_area(field, payload.get(field))
            if not valid:
                return jsonify({"error": error}), 400
            style_valid, style, style_error = _validate_styling(field, payload.get(field))
            if not style_valid:
                return jsonify({"error": style_error}), 400

            field_data: dict[str, object] = {}
            field_data.update(area or {})
            field_data.update(style or {})
            validated_areas[field] = field_data

        config_store.save_template_areas(template_name=template_name, areas=validated_areas)
        return jsonify({"message": "Template areas saved.", "template_name": template_name})

    return calibration_bp
