import json
from functools import cache
from pathlib import Path

import requests
import requests_cache

from penai.types import PathLike


def read_json(path: PathLike) -> dict:
    """Read a JSON file from the given path."""
    return json.loads(Path(path).read_text())


@cache
def get_cached_requests_session(cache_name: str) -> requests.Session:
    """Get a requests session with a cache."""
    return requests_cache.CachedSession(cache_name)
