import json
import logging
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
