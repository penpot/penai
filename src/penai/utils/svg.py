import base64
import io
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import urlparse

import requests
from PIL import Image
from lxml import etree


def trim_namespace_from_tree(node: etree.Element, namespace: str) -> None:
    """Strip all elements belonging to a specific namespace from an XML tree.

    Useful for debugging, reverse engineering or testing purposes.
    """
    children = list(node)

    for child in children:
        if child.prefix and child.prefix == namespace:
            node.remove(child)
        else:
            trim_namespace_from_tree(child, namespace)


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


@contextmanager
def temp_file_for_content(content: str | bytes, extension: str, delete: bool = False) -> Generator[Path, Any, Any]:
    """Create a temporary file for a given file content."""
    if extension and not extension.startswith("."):
        raise ValueError("Extension should start with a dot")

    if isinstance(content, str):
        mode = "w"
    else:
        assert isinstance(content, bytes)
        mode = "wb"

    # Note: (just for the curious, not actually needed to know)
    # buffering=0 is very important if you want to yield inside
    # Since we don't use the delete option here (we delete manually below)
    # we yield outside of this context
    # The code below is essentially equivalet to wit open()..write
    with NamedTemporaryFile(prefix="penai_", suffix=extension, mode=mode, delete=False, buffering=0) as file:
        file.write(content)
        path = Path(file.name)
    yield path

    if delete:
        path.unlink()
