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

    def save_template_areas(self, template_name: str, areas: dict[str, dict[str, float]]) -> None:
        data = self.load()
        normalized: dict[str, dict[str, float]] = {}
        for field, area in areas.items():
            normalized[field] = {
                "x": float(area["x"]),
                "y": float(area["y"]),
                "width": float(area["width"]),
                "height": float(area["height"]),
            }

        data[template_name] = normalized
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2)
