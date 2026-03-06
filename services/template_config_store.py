import json
import os
from typing import Any, Dict


class TemplateConfigStore:
    """Persists template calibration data in template_config.json."""

    def __init__(self, config_path: str) -> None:
        self.config_path = config_path

    def load(self) -> Dict[str, Dict[str, Any]]:
        if not os.path.isfile(self.config_path):
            return {}

        try:
            with open(self.config_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except (json.JSONDecodeError, OSError):
            return {}

        return data if isinstance(data, dict) else {}

    def save_template_areas(self, template_name: str, areas: dict[str, dict[str, Any]]) -> None:
        data = self.load()
        existing_template = data.get(template_name, {})
        normalized: dict[str, Any] = {}
        for field, area in areas.items():
            merged_field_data: dict[str, Any] = {}
            if isinstance(existing_template, dict):
                existing_field = existing_template.get(field)
                if isinstance(existing_field, dict):
                    merged_field_data.update(existing_field)

            merged_field_data.update({
                "x": float(area["x"]),
                "y": float(area["y"]),
                "width": float(area["width"]),
                "height": float(area["height"]),
            })
            for style_key in ("font_family", "font_color", "max_font_size", "min_font_size", "alignment", "font_size", "font_weight"):
                if style_key in area:
                    merged_field_data[style_key] = area[style_key]
            normalized[field] = merged_field_data

        if isinstance(existing_template, dict):
            existing_category = existing_template.get("category")
            if isinstance(existing_category, str) and existing_category.strip():
                normalized["category"] = existing_category.strip()

        data[template_name] = normalized
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2)
