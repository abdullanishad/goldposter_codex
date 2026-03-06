import logging
import os
from io import BytesIO
from typing import Any, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from storage import storage

SUPPORTED_EXTENSIONS: Tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp")
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "static", "templates")
FONTS_DIR = os.path.join(PROJECT_ROOT, "static", "fonts")
TEXT_FIELD_KEYS = (
    "todays_date",
    "price_1g",
    "price_8g",
    "address",
    "whatsapp_number",
    "social_handle",
)
DEFAULT_FONT_COLOR = (255, 255, 255)
DEFAULT_MAX_FONT_SIZE = 60
DEFAULT_MIN_FONT_SIZE = 10
FONT_SIZE_STEP = 2
ADDRESS_LINE_SPACING = 10
DEFAULT_FONT_FILENAME = "default.ttf"
LOGGER = logging.getLogger(__name__)


def load_template(template_name: str) -> Image.Image:
    if not template_name or not str(template_name).strip():
        raise ValueError("template_name is required")

    selected_name = os.path.basename(str(template_name).strip())

    try:
        template_bytes = storage.get_file_bytes(selected_name)
        return Image.open(template_bytes).convert("RGBA")
    except Exception:
        template_path = os.path.join(TEMPLATES_DIR, selected_name)
        if not os.path.isfile(template_path):
            raise FileNotFoundError(f"Template not found in R2 or local templates: {selected_name}")
        return Image.open(template_path).convert("RGBA")


def load_font(area: dict[str, Any], size: int) -> ImageFont.ImageFont:
    font_name = str(area.get("font_family", DEFAULT_FONT_FILENAME) or DEFAULT_FONT_FILENAME).strip()
    font_name = os.path.basename(font_name) if font_name else DEFAULT_FONT_FILENAME
    font_path = os.path.join(FONTS_DIR, font_name)

    if not os.path.exists(font_path):
        fallback_path = os.path.join(FONTS_DIR, DEFAULT_FONT_FILENAME)
        LOGGER.warning("Configured font file not found: %s. Falling back to %s.", font_path, fallback_path)
        font_path = fallback_path

    try:
        return ImageFont.truetype(font_path, size=size)
    except OSError:
        LOGGER.warning("Unable to load TrueType font at %s. Falling back to PIL default font.", font_path)
        return ImageFont.load_default()


def _load_logo_image(logo_path: str) -> Image.Image:
    try:
        logo_bytes = storage.get_file_bytes(logo_path)
        return Image.open(logo_bytes).convert("RGBA")
    except Exception as exc:
        raise FileNotFoundError(f"Logo could not be fetched from R2: {logo_path}") from exc


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


def _to_font_color(raw_color: object) -> tuple[int, int, int]:
    if not isinstance(raw_color, (list, tuple)) or len(raw_color) < 3:
        return DEFAULT_FONT_COLOR
    rgb: list[int] = []
    for value in raw_color[:3]:
        if not isinstance(value, (int, float)):
            return DEFAULT_FONT_COLOR
        rgb.append(max(0, min(255, int(value))))
    return (rgb[0], rgb[1], rgb[2])


def _to_font_size(raw_size: object, default_size: int) -> int:
    if isinstance(raw_size, (int, float)) and raw_size > 0:
        return int(raw_size)
    return default_size


def _get_text_style(area: object) -> dict[str, Any]:
    if not isinstance(area, dict):
        return {
            "font_family": DEFAULT_FONT_FILENAME,
            "font_color": DEFAULT_FONT_COLOR,
            "max_font_size": DEFAULT_MAX_FONT_SIZE,
            "min_font_size": DEFAULT_MIN_FONT_SIZE,
            "alignment": "center",
        }

    max_font_size = _to_font_size(area.get("max_font_size"), DEFAULT_MAX_FONT_SIZE)
    min_font_size = _to_font_size(area.get("min_font_size"), DEFAULT_MIN_FONT_SIZE)
    if min_font_size > max_font_size:
        min_font_size = max_font_size

    raw_family = area.get("font_family")
    font_family = (
        str(raw_family).strip() if isinstance(raw_family, str) and raw_family.strip() else DEFAULT_FONT_FILENAME
    )

    return {
        "font_family": font_family,
        "font_color": _to_font_color(area.get("font_color")),
        "max_font_size": max_font_size,
        "min_font_size": min_font_size,
        "alignment": (
            str(area.get("alignment", "center")).strip().lower()
            if str(area.get("alignment", "center")).strip().lower() in {"left", "center", "right"}
            else "center"
        ),
    }


def _fit_text_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_height: int,
    area: dict[str, Any],
) -> tuple[ImageFont.ImageFont, tuple[int, int, int, int]]:
    max_size = _to_font_size(area.get("max_font_size"), DEFAULT_MAX_FONT_SIZE)
    min_size = _to_font_size(area.get("min_font_size"), DEFAULT_MIN_FONT_SIZE)
    if min_size > max_size:
        min_size = max_size

    font_size = max_size
    while font_size >= min_size:
        font = load_font(area, font_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        if text_width <= max_width and text_height <= max_height:
            return font, bbox
        font_size -= FONT_SIZE_STEP

    font = load_font(area, min_size)
    return font, draw.textbbox((0, 0), text, font=font)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    area_px: tuple[int, int, int, int],
    style: dict[str, Any],
    shadow_alpha: int = 120,
) -> None:
    x, y, width, height = area_px
    font, bbox = _fit_text_font(
        draw=draw,
        text=text,
        max_width=max(1, width - 6),
        max_height=max(1, height - 4),
        area=style,
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    if style["alignment"] == "left":
        text_x = int(x - bbox[0])
    elif style["alignment"] == "right":
        text_x = int(x + width - text_width - bbox[0])
    else:
        text_x = int(x + ((width - text_width) / 2) - bbox[0])
    text_y = int(y + ((height - text_height) / 2) - bbox[1])

    draw.text((text_x + 2, text_y + 2), text, font=font, fill=(0, 0, 0, shadow_alpha))
    draw.text((text_x, text_y), text, font=font, fill=style["font_color"])


def _format_price(raw_price: str) -> str:
    raw = str(raw_price).strip()
    if not raw:
        return ""

    numeric_candidate = "".join(ch for ch in raw if ch.isdigit() or ch == ".")
    if numeric_candidate:
        try:
            price_value = float(numeric_candidate)
            if price_value.is_integer():
                return f" {int(price_value):,}"
            return f" {price_value:,.2f}"
        except ValueError:
            return raw
    return raw


def wrap_text_to_two_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]

        if line_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                lines.append(word)
                current_line = ""

        if len(lines) == 1:
            continue

    if current_line:
        lines.append(current_line)

    return lines[:2]


def _draw_wrapped_address(
    draw: ImageDraw.ImageDraw,
    text: str,
    area_px: tuple[int, int, int, int],
    style: dict[str, Any],
    shadow_alpha: int = 120,
    line_spacing: int = ADDRESS_LINE_SPACING,
) -> None:
    x, y, width, height = area_px
    clean_text = str(text).strip()
    if not clean_text:
        return

    best_font: ImageFont.ImageFont | None = None
    best_lines: list[str] = []
    best_total_height = 0

    max_size = _to_font_size(style.get("max_font_size"), DEFAULT_MAX_FONT_SIZE)
    min_size = _to_font_size(style.get("min_font_size"), DEFAULT_MIN_FONT_SIZE)
    if min_size > max_size:
        min_size = max_size

    font_size = max_size
    while font_size >= min_size:
        font = load_font(style, font_size)
        lines = wrap_text_to_two_lines(draw, clean_text, font, max(1, width - 6))
        if not lines:
            font_size -= FONT_SIZE_STEP
            continue

        total_height = 0
        widest_line = 0

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            widest_line = max(widest_line, line_width)
            total_height += line_height

        total_height += line_spacing * (len(lines) - 1)

        if widest_line <= width and total_height <= height:
            best_font = font
            best_lines = lines
            best_total_height = total_height
            break
        font_size -= FONT_SIZE_STEP

    if best_font is None:
        best_font = load_font(style, min_size)
        best_lines = wrap_text_to_two_lines(draw, clean_text, best_font, max(1, width - 6))
        if not best_lines:
            return

        best_total_height = 0
        for line in best_lines:
            bbox = draw.textbbox((0, 0), line, font=best_font)
            best_total_height += bbox[3] - bbox[1]
        best_total_height += line_spacing * (len(best_lines) - 1)

    current_y = y + max(0, (height - best_total_height) // 2)

    for line in best_lines:
        bbox = draw.textbbox((0, 0), line, font=best_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        if style["alignment"] == "left":
            text_x = x - bbox[0]
        elif style["alignment"] == "right":
            text_x = x + width - text_width - bbox[0]
        else:
            text_x = x + max(0, (width - text_width) // 2) - bbox[0]

        text_y = current_y - bbox[1]
        draw.text((text_x + 2, text_y + 2), line, font=best_font, fill=(0, 0, 0, shadow_alpha))
        draw.text((text_x, text_y), line, font=best_font, fill=style["font_color"])

        current_y += text_height + line_spacing


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
) -> BytesIO:
    if not template_name or not str(template_name).strip():
        raise ValueError("template_name is required")
    if template_data is None:
        raise ValueError("Template not found in configuration")

    selected_template = os.path.basename(str(template_name).strip())

    areas: dict[str, tuple[int, int, int, int]] = {}
    text_styles: dict[str, dict[str, Any]] = {}
    base_image = load_template(selected_template)
    draw = ImageDraw.Draw(base_image)
    img_width, img_height = base_image.size

    for field in TEXT_FIELD_KEYS:
        area_config = template_data.get(field)
        areas[field] = _area_to_pixels(
            _validate_area(field, area_config),
            img_width,
            img_height,
        )
        text_styles[field] = _get_text_style(area_config)

    areas["logo_area"] = _area_to_pixels(
        _validate_area("logo_area", template_data.get("logo_area")),
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
        if field == "address":
            continue
        value = text_values[field]
        if not value:
            continue
        _draw_centered_text(draw, value, areas[field], text_styles[field])

    _draw_wrapped_address(
        draw=draw,
        text=text_values["address"],
        area_px=areas["address"],
        style=text_styles["address"],
    )

    if logo_path:
        logo_image = _load_logo_image(logo_path)
        logo_x, logo_y, logo_width, logo_height = areas["logo_area"]
        logo_image = logo_image.resize((int(logo_width), int(logo_height)), Image.Resampling.LANCZOS)
        base_image.paste(logo_image, (int(logo_x), int(logo_y)), logo_image)

    img_io = BytesIO()
    base_image.save(img_io, "PNG")
    img_io.seek(0)
    return img_io
