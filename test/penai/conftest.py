from pathlib import Path

from penai.types import PathLike
import pytest


def existing_path(path: PathLike) -> Path:
    path = Path(path)
    assert path.exists()
    return path


@pytest.fixture(scope="session")
def example_svg_path() -> Path:
    return existing_path("test/fixtures/example.svg")


@pytest.fixture(scope="session")
def example_png() -> Path:
    return existing_path("test/fixtures/example.png")
