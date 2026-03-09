"""
Font management: download Montserrat from Google Fonts on first run.
Cached in assets/fonts/ — persists across restarts.
"""

import os
import urllib.request
from pathlib import Path

from logger_setup import log

FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"

_MONTSERRAT_BASE = (
    "https://github.com/google/fonts/raw/main/ofl/montserrat/static/"
)
_REQUIRED = {
    "Montserrat-Bold.ttf":     _MONTSERRAT_BASE + "Montserrat-Bold.ttf",
    "Montserrat-SemiBold.ttf": _MONTSERRAT_BASE + "Montserrat-SemiBold.ttf",
    "Montserrat-Regular.ttf":  _MONTSERRAT_BASE + "Montserrat-Regular.ttf",
    "Montserrat-Light.ttf":    _MONTSERRAT_BASE + "Montserrat-Light.ttf",
}

# System fallbacks (Ubuntu) if download fails
_SYSTEM_BOLD = [
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
_SYSTEM_REG = [
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def ensure_fonts() -> None:
    """Download Montserrat fonts if not cached. Called once at bot startup."""
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in _REQUIRED.items():
        path = FONTS_DIR / name
        if not path.exists():
            try:
                log.info("Downloading font %s ...", name)
                urllib.request.urlretrieve(url, str(path))
                log.info("Font downloaded: %s", name)
            except Exception as exc:
                log.warning("Failed to download %s: %s — will use system fallback", name, exc)


def get_font(variant: str, size: int):
    """
    Load a Montserrat variant. Falls back to system fonts if unavailable.
    variant: 'Bold' | 'SemiBold' | 'Regular' | 'Light'
    """
    from PIL import ImageFont

    path = FONTS_DIR / f"Montserrat-{variant}.ttf"
    if path.exists():
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            pass

    # System fallbacks
    fallbacks = _SYSTEM_BOLD if variant in ("Bold", "SemiBold") else _SYSTEM_REG
    for fb in fallbacks:
        try:
            return ImageFont.truetype(fb, size)
        except (OSError, IOError):
            continue

    return ImageFont.load_default()
