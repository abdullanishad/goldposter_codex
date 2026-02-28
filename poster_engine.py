import os
from datetime import datetime
from typing import Any, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

SUPPORTED_EXTENSIONS: Tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp")
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "static", "templates")
GENERATED_DIR = os.path.join(PROJECT_ROOT, "static", "generated")
TEXT_FIELD_KEYS = (
    "todays_date",
    "price_1g",
    "price_8g",
    "address",
    "whatsapp_number",
    "social_handle",
)


def _get_template_files() -> list[str]:
    if not os.path.isdir(TEMPLATES_DIR):
        raise FileNotFoundError(f"Template directory not found: {TEMPLATES_DIR}")

    template_files = [
        os.path.join(TEMPLATES_DIR, filename)
        for filename in os.listdir(TEMPLATES_DIR)
        if filename.lower().endswith(SUPPORTED_EXTENSIONS)
        and os.path.isfile(os.path.join(TEMPLATES_DIR, filename))
    ]

    if not template_files:
        raise ValueError(f"No template images found in: {TEMPLATES_DIR}")

    return template_files


def load_template(template_name: str) -> Image.Image:
    if not template_name or not str(template_name).strip():
        raise ValueError("template_name is required")

    template_files = _get_template_files()
    allowed_names = {os.path.basename(path) for path in template_files}
    selected_name = os.path.basename(str(template_name).strip())

    if selected_name not in allowed_names:
        raise FileNotFoundError(f"Template not found: {selected_name}")

    return Image.open(os.path.join(TEMPLATES_DIR, selected_name))


def _load_font(size: int) -> ImageFont.ImageFont:
    candidate_fonts = [
        "DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "arialbd.ttf",
    ]
    for font_path in candidate_fonts:
        try:
            return ImageFont.truetype(font_path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _resolve_logo_path(logo_path: str) -> str:
    if os.path.isabs(logo_path):
        return logo_path
    return os.path.join(PROJECT_ROOT, logo_path)


def _validate_area(name: str, area: object) -> dict[str, float]:
    if not isinstance(area, dict):
        raise ValueError(f"Template not found in configuration: missing {name}")

    parsed: dict[str, float] = {}
    for key in ("x", "y", "width", "height"):
        if key not in area or not isinstance(area[key], (int, float)):
            raise ValueError(f"Template not found in configuration: invalid {name}.{key}")
        parsed[key] = float(area[key])

    if parsed["width"] <= 0 or parsed["height"] <= 0:
        raise ValueError(f"Template not found in configuration: invalid {name} size")
    if parsed["x"] < 0 or parsed["y"] < 0:
        raise ValueError(f"Template not found in configuration: invalid {name} position")
    if parsed["x"] + parsed["width"] > 1 or parsed["y"] + parsed["height"] > 1:
        raise ValueError(f"Template not found in configuration: {name} out of bounds")

    return parsed


def _area_to_pixels(area: dict[str, float], img_width: int, img_height: int) -> tuple[int, int, int, int]:
    x = int(img_width * area["x"])
    y = int(img_height * area["y"])
    width = int(img_width * area["width"])
    height = int(img_height * area["height"])

    width = max(1, min(width, img_width))
    height = max(1, min(height, img_height))
    x = max(0, min(x, img_width - width))
    y = max(0, min(y, img_height - height))

    return x, y, width, height


def _fit_text_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_height: int,
    start_size: int = 160,
    min_size: int = 10,
) -> tuple[ImageFont.ImageFont, tuple[int, int, int, int]]:
    for size in range(start_size, min_size - 1, -1):
        font = _load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        if text_width <= max_width and text_height <= max_height:
            return font, bbox

    font = _load_font(min_size)
    return font, draw.textbbox((0, 0), text, font=font)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    area_px: tuple[int, int, int, int],
    color: tuple[int, int, int] = (255, 255, 255),
    shadow_alpha: int = 120,
) -> None:
    x, y, width, height = area_px
    font, bbox = _fit_text_font(
        draw=draw,
        text=text,
        max_width=max(1, width - 6),
        max_height=max(1, height - 4),
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = int(x + ((width - text_width) / 2) - bbox[0])
    text_y = int(y + ((height - text_height) / 2) - bbox[1])

    draw.text((text_x + 2, text_y + 2), text, font=font, fill=(0, 0, 0, shadow_alpha))
    draw.text((text_x, text_y), text, font=font, fill=color)


def _format_price(raw_price: str) -> str:
    raw = str(raw_price).strip()
    if not raw:
        return ""

    numeric_candidate = "".join(ch for ch in raw if ch.isdigit() or ch == ".")
    if numeric_candidate:
        try:
            price_value = float(numeric_candidate)
            if price_value.is_integer():
                return f"₹ {int(price_value):,}"
            return f"₹ {price_value:,.2f}"
        except ValueError:
            return raw
    return raw


def generate_poster(
    template_name: str,
    template_data: dict[str, Any],
    todays_date: str,
    price_1g: str,
    price_8g: str,
    address: str,
    whatsapp_number: str,
    social_handle: str,
    logo_path: Optional[str] = None,
) -> str:
    if not template_name or not str(template_name).strip():
        raise ValueError("template_name is required")
    if template_data is None:
        raise ValueError("Template not found in configuration")

    selected_template = os.path.basename(str(template_name).strip())

    areas: dict[str, tuple[int, int, int, int]] = {}
    base_image = load_template(selected_template).convert("RGBA")
    draw = ImageDraw.Draw(base_image)
    img_width, img_height = base_image.size

    for field in (*TEXT_FIELD_KEYS, "logo_area"):
        areas[field] = _area_to_pixels(
            _validate_area(field, template_data.get(field)),
            img_width,
            img_height,
        )

    text_values = {
        "todays_date": str(todays_date).strip(),
        "price_1g": _format_price(price_1g),
        "price_8g": _format_price(price_8g),
        "address": str(address).strip(),
        "whatsapp_number": str(whatsapp_number).strip(),
        "social_handle": str(social_handle).strip(),
    }

    for field in TEXT_FIELD_KEYS:
        value = text_values[field]
        if not value:
            continue
        _draw_centered_text(draw, value, areas[field])

    if logo_path:
        resolved_logo_path = _resolve_logo_path(logo_path)
        if not os.path.isfile(resolved_logo_path):
            raise FileNotFoundError(f"Logo file not found: {resolved_logo_path}")

        logo_image = Image.open(resolved_logo_path).convert("RGBA")
        logo_x, logo_y, logo_width, logo_height = areas["logo_area"]
        logo_image = logo_image.resize((int(logo_width), int(logo_height)), Image.Resampling.LANCZOS)
        base_image.paste(logo_image, (int(logo_x), int(logo_y)), logo_image)

    os.makedirs(GENERATED_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = os.path.join(GENERATED_DIR, f"poster_{timestamp}.png")
    base_image.save(output_path, format="PNG")
    return output_path
