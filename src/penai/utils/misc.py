import json
import logging
import random
from functools import cache
from pathlib import Path

from cssutils import CSSParser

from penai.types import PathLike


def read_json(path: PathLike) -> dict:
    """Read a JSON file from the given path."""
    return json.loads(Path(path).read_text())


@cache
def get_css_parser() -> CSSParser:
    """Get a CSS parser with the default settings."""
    return CSSParser(loglevel=logging.CRITICAL)


def random_rgb_color():
    """Generates a random RGB color in hex."""
    rgb = tuple(random.randint(0, 255) for _ in range(3))
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
