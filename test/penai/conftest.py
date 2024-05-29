from pathlib import Path

import pytest
from pytest import MonkeyPatch

from penai.config import top_level_directory
from penai.types import PathLike


@pytest.fixture(autouse=True)
def from_top_level_dir(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(top_level_directory)


def existing_path(path: PathLike) -> Path:
    path = Path(path)
    if not path.is_absolute():
        path = Path(top_level_directory) / path
    assert path.exists() or path.is_dir()
    return path


@pytest.fixture(scope="session")
def resources_path() -> Path:
    return existing_path("test/resources")


@pytest.fixture(scope="session")
def example_svg_path(resources_path: Path) -> Path:
    return resources_path / "example.svg"


@pytest.fixture(scope="session")
def example_png_path(resources_path: Path) -> Path:
    return resources_path / "example.png"


@pytest.fixture(scope="session")
def page_example_svg_path(resources_path: Path) -> Path:
    return resources_path / "page_example.svg"
