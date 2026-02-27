import os
from datetime import datetime
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

SUPPORTED_EXTENSIONS: Tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp")
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "static", "templates")
GENERATED_DIR = os.path.join(PROJECT_ROOT, "static", "generated")


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
    """
    Load and return a specific poster template from static/templates.

    Returns:
        PIL.Image.Image: The opened template image.

    Raises:
        FileNotFoundError: If the templates directory or selected file does not exist.
        ValueError: If no supported image files are found, or template_name is invalid.
    """
    if not template_name or not str(template_name).strip():
        raise ValueError("template_name is required")

    template_files = _get_template_files()
    allowed_names = {os.path.basename(path) for path in template_files}
    selected_name = os.path.basename(str(template_name).strip())

    if selected_name not in allowed_names:
        raise FileNotFoundError(f"Template not found: {selected_name}")

    return Image.open(os.path.join(TEMPLATES_DIR, selected_name))


def _load_font(size: int) -> ImageFont.ImageFont:
    """Load a clean TrueType font with fallback to PIL default."""
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


def _centered_text_x(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    text_width = right - left
    return max(0, (width - text_width) // 2)


def _resolve_logo_path(logo_path: str) -> str:
    if os.path.isabs(logo_path):
        return logo_path
    return os.path.join(PROJECT_ROOT, logo_path)


def generate_poster(
    shop_name: str,
    gold_price: str,
    template_name: str,
    logo_path: Optional[str] = None,
) -> str:
    """
    Generate a jewellery poster using a selected template and save it to static/generated.

    Args:
        shop_name: Shop display name.
        gold_price: Gold price text to show in the center.
        template_name: Template file name from static/templates.
        logo_path: Optional absolute or project-relative logo file path.

    Returns:
        Absolute path to the generated poster image.
    """
    if not shop_name or not str(shop_name).strip():
        raise ValueError("shop_name is required")
    if not gold_price or not str(gold_price).strip():
        raise ValueError("gold_price is required")
    if not template_name or not str(template_name).strip():
        raise ValueError("template_name is required")

    base_image = load_template(template_name).convert("RGBA")
    width, height = base_image.size
    min_dim = min(width, height)

    # Subtle dark overlay improves readability across bright template areas.
    overlay_alpha = max(50, min(95, int(min_dim * 0.08)))
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, overlay_alpha))
    base_image = Image.alpha_composite(base_image, overlay)
    draw = ImageDraw.Draw(base_image)

    raw_price = str(gold_price).strip()
    numeric_candidate = "".join(ch for ch in raw_price if ch.isdigit() or ch == ".")
    price_text = raw_price
    if numeric_candidate:
        try:
            price_value = float(numeric_candidate)
            if price_value.is_integer():
                price_text = f"₹ {int(price_value):,} / gram"
            else:
                price_text = f"₹ {price_value:,.2f} / gram"
        except ValueError:
            price_text = f"₹ {raw_price} / gram" if "/ gram" not in raw_price.lower() else raw_price
    elif "/ gram" not in raw_price.lower():
        price_text = f"₹ {raw_price} / gram"

    shop_text = str(shop_name).strip()
    price_font = _load_font(max(48, min_dim // 11))
    shop_font = _load_font(max(30, min_dim // 24))
    price_shadow_offset = max(2, min_dim // 270)
    shop_shadow_offset = max(1, min_dim // 320)
    line_gap = max(18, min_dim // 30)
    vertical_padding = max(56, int(height * 0.12))

    price_bbox = draw.textbbox((0, 0), price_text, font=price_font)
    shop_bbox = draw.textbbox((0, 0), shop_text, font=shop_font)
    price_width = price_bbox[2] - price_bbox[0]
    price_height = price_bbox[3] - price_bbox[1]
    shop_width = shop_bbox[2] - shop_bbox[0]
    shop_height = shop_bbox[3] - shop_bbox[1]
    block_height = price_height + line_gap + shop_height
    block_top = max(vertical_padding, (height - block_height) // 2)

    price_x = int((width - price_width) / 2 - price_bbox[0])
    shop_x = int((width - shop_width) / 2 - shop_bbox[0])
    price_y = int(block_top - price_bbox[1])
    shop_y = int(block_top + price_height + line_gap - shop_bbox[1])

    draw.text(
        (price_x + price_shadow_offset, price_y + price_shadow_offset),
        price_text,
        font=price_font,
        fill=(0, 0, 0, 170),
    )
    draw.text(
        (price_x, price_y),
        price_text,
        font=price_font,
        fill=(248, 232, 194, 255),
        stroke_width=max(1, min_dim // 500),
        stroke_fill=(60, 45, 20, 200),
    )
    draw.text(
        (shop_x + shop_shadow_offset, shop_y + shop_shadow_offset),
        shop_text,
        font=shop_font,
        fill=(0, 0, 0, 140),
    )
    draw.text(
        (shop_x, shop_y),
        shop_text,
        font=shop_font,
        fill=(255, 255, 255, 245),
    )

    if logo_path:
        resolved_logo_path = _resolve_logo_path(logo_path)
        if not os.path.isfile(resolved_logo_path):
            raise FileNotFoundError(f"Logo file not found: {resolved_logo_path}")

        logo_image = Image.open(resolved_logo_path).convert("RGBA")
        max_logo_width = max(90, int(width * 0.18))
        max_logo_height = max(90, int(height * 0.18))
        logo_image.thumbnail((max_logo_width, max_logo_height), Image.Resampling.LANCZOS)

        margin = max(24, int(min_dim * 0.04))
        logo_x = width - logo_image.width - margin
        logo_y = margin
        base_image.paste(logo_image, (logo_x, logo_y), logo_image)

    os.makedirs(GENERATED_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = os.path.join(GENERATED_DIR, f"poster_{timestamp}.png")
    base_image.save(output_path, format="PNG")
    return output_path
