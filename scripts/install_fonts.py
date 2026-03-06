#!/usr/bin/env python3
"""Download popular Google Fonts (Regular + Bold) into static/fonts."""

from __future__ import annotations

from pathlib import Path
from typing import Any


REPO_API_BASE = "https://api.github.com/repos/google/fonts/contents"
REQUEST_TIMEOUT = 30
FONT_VARIANTS = ("Regular", "Bold")
FONT_FAMILIES = (
    "Poppins",
    "Montserrat",
    "PlayfairDisplay",
    "Cinzel",
    "Lora",
    "Merriweather",
    "Cormorant",
    "LibreBaskerville",
    "Roboto",
    "OpenSans",
    "Raleway",
    "Inter",
    "Nunito",
    "PTSerif",
    "Quicksand",
    "Oswald",
    "BebasNeue",
    "SourceSansPro",
    "WorkSans",
    "JosefinSans",
)


def _slug(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _repo_candidates(font_family: str) -> list[str]:
    slug = _slug(font_family)
    return [f"ofl/{slug}", f"apache/{slug}", f"ufl/{slug}"]


def _get_json(session: Any, url: str) -> list[dict[str, Any]] | None:
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, list):
        return payload
    return None


def _pick_font_entry(entries: list[dict[str, Any]], family: str, variant: str) -> dict[str, Any] | None:
    ttf_entries = [
        entry
        for entry in entries
        if entry.get("type") == "file"
        and str(entry.get("name", "")).lower().endswith(".ttf")
        and isinstance(entry.get("download_url"), str)
    ]
    if not ttf_entries:
        return None

    family_lower = family.lower()
    regular_exact = {
        f"{family_lower}-regular.ttf",
        f"{family_lower}regular.ttf",
        f"{family_lower}[wght].ttf",
        f"{family_lower}[opsz,wght].ttf",
    }
    bold_exact = {
        f"{family_lower}-bold.ttf",
        f"{family_lower}bold.ttf",
    }

    def entry_name(entry: dict[str, Any]) -> str:
        return str(entry.get("name", "")).lower()

    non_italic = [e for e in ttf_entries if "italic" not in entry_name(e)]
    if variant == "Regular":
        for entry in non_italic:
            if entry_name(entry) in regular_exact:
                return entry
        for entry in non_italic:
            name = entry_name(entry)
            if "regular" in name:
                return entry
        if non_italic:
            return sorted(non_italic, key=entry_name)[0]
    else:
        for entry in non_italic:
            if entry_name(entry) in bold_exact:
                return entry
        for entry in non_italic:
            if "bold" in entry_name(entry):
                return entry
        # Fallback to a variable/non-italic font if dedicated Bold is unavailable.
        if non_italic:
            return sorted(non_italic, key=entry_name)[0]
    return None


def _download_file(session: Any, source_url: str, destination: Path) -> None:
    response = session.get(source_url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    destination.write_bytes(response.content)


def install_fonts() -> int:
    try:
        import requests
    except ModuleNotFoundError:
        print("requests is not installed. Install dependencies first: pip install -r requirements.txt")
        return 2

    project_root = Path(__file__).resolve().parents[1]
    fonts_dir = project_root / "static" / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0
    failed = 0

    with requests.Session() as session:
        session.headers.update({"User-Agent": "goldposter-font-installer/1.0"})

        for family in FONT_FAMILIES:
            family_entries: list[dict[str, Any]] | None = None
            for repo_dir in _repo_candidates(family):
                listing_url = f"{REPO_API_BASE}/{repo_dir}"
                try:
                    family_entries = _get_json(session, listing_url)
                except requests.RequestException as exc:
                    print(f"[error] listing failed for {family} at {repo_dir}: {exc}")
                    family_entries = None
                if family_entries:
                    break

            if not family_entries:
                print(f"[warn] could not locate {family} in google/fonts repository")
                failed += len(FONT_VARIANTS)
                continue

            for variant in FONT_VARIANTS:
                destination = fonts_dir / f"{family}-{variant}.ttf"
                if destination.exists():
                    print(f"[skip] {destination.name} already exists")
                    skipped += 1
                    continue

                entry = _pick_font_entry(family_entries, family, variant)
                if not entry:
                    print(f"[warn] no {variant} .ttf found for {family}")
                    failed += 1
                    continue

                source_url = str(entry["download_url"])
                try:
                    _download_file(session, source_url, destination)
                    print(f"[ok] {destination.name} <- {source_url}")
                    downloaded += 1
                except requests.RequestException as exc:
                    print(f"[error] download failed for {destination.name}: {exc}")
                    failed += 1

    print(
        "\nSummary:",
        f"downloaded={downloaded}",
        f"skipped={skipped}",
        f"failed={failed}",
        f"target_dir={fonts_dir}",
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(install_fonts())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130) from None
