import base64
import io
from typing import Any
from urllib.parse import urlparse

import requests
from lxml import etree
from PIL import Image


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


def image_from_bytes(image_bytes: bytes | bytearray) -> Image.Image:
    """Create an image from a bytes or bytearray object."""
    return Image.open(io.BytesIO(image_bytes))


def url_to_data_uri(image_url: str) -> str:
    """Convert an image URL to a data URI."""
    response = requests.get(image_url)
    response.raise_for_status()

    if not (content_type := response.headers.get("content-type")):
        raise ValueError("No content type found in response headers")

    image_data = base64.b64encode(response.content).decode("utf-8")

    return f"data:{content_type};base64,{image_data}"


def validate_uri(x: Any) -> bool:
    """Validate a given URI."""
    try:
        result = urlparse(x)
        return all([result.scheme, result.netloc])
    except AttributeError:
        return False
