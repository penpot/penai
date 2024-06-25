import json
import logging
import random
from functools import cache
from pathlib import Path

import requests
import requests_cache
from cssutils import CSSParser

from penai.types import PathLike, RGBColor


def read_json(path: PathLike) -> dict:
    """Read a JSON file from the given path."""
    return json.loads(Path(path).read_text())


@cache
def get_css_parser() -> CSSParser:
    """Get a CSS parser with the default settings."""
    return CSSParser(loglevel=logging.CRITICAL)


@cache
def get_cached_requests_session(cache_name: str = "cache") -> requests.Session:
    """Get a requests session with a cache."""
    return requests_cache.CachedSession(cache_name)


def random_rgb_color() -> RGBColor:
    """Generates a random RGB color in hex."""
    rgb = tuple(random.randint(0, 255) for _ in range(3))
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
