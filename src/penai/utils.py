import base64
import io
import json
from pathlib import Path
from urllib.parse import urlparse

import requests
from lxml import etree
from PIL import Image

from penai.svg import SVG
from penai.types import PathLike


def read_json(path: PathLike) -> dict:
    """Read a JSON file from the given path."""
    return json.loads(Path(path).read_text())


def strip_penpot_from_tree(node: etree.Element) -> None:
    """Strip all Penpot-specific nodes from a given SVG DOM.

    Useful for debugging, reverse engineering or testing purposes.
    """
    children = list(node)

    for child in children:
        if child.prefix and child.prefix == "penpot":
            node.remove(child)
        else:
            strip_penpot_from_tree(child)


def strip_penpot_from_svg(svg: SVG) -> None:
    """Strip all Penpot-specific nodes from a given SVG object.

    Useful for debugging, reverse engineering or testing purposes.
    """
    strip_penpot_from_tree(svg.dom.getroot())


def image_from_bytes(image_bytes: bytes | bytearray) -> Image.Image:
    """Create an image from a bytes or bytearray object."""
    return Image.open(io.BytesIO(image_bytes))


def url_to_data_uri(image_url):
    """Convert an image URL to a data URI."""
    response = requests.get(image_url)
    response.raise_for_status()

    if not (content_type := response.headers.get('content-type')):
        raise ValueError('No content type found in response headers')

    image_data = base64.b64encode(response.content).decode('utf-8')

    return f"data:{content_type};base64,{image_data}"


def validate_uri(x):
    """Validate a given URI."""
    try:
        result = urlparse(x)
        return all([result.scheme, result.netloc])
    except AttributeError:
        return False
