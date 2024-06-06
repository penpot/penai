from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pytest
from pytest import FixtureRequest, MonkeyPatch
from selenium.webdriver.remote.webdriver import WebDriver

from penai.config import top_level_directory
from penai.registries.projects import SavedPenpotProject
from penai.render import BaseSVGRenderer, WebDriverSVGRenderer
from penai.types import PathLike
from penai.utils.web_drivers import create_chrome_web_driver


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


@pytest.fixture(scope="session")
def log_dir() -> Path:
    log_dir_root = existing_path("test/log")
    session_log_dir = log_dir_root / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_log_dir.mkdir(parents=True)
    return session_log_dir


@pytest.fixture(scope="session")
def chrom_web_driver() -> Generator[WebDriver, Any, Any]:
    with create_chrome_web_driver() as driver:
        yield driver


@pytest.fixture(scope="session")
def chrome_svg_renderer(chrom_web_driver: WebDriver) -> Iterable[BaseSVGRenderer]:
    return WebDriverSVGRenderer(chrom_web_driver)


@pytest.fixture(params=[
    SavedPenpotProject.AVATAAARS,
    SavedPenpotProject.BLACK_AND_WHITE_MOBILE_TEMPLATES,
    SavedPenpotProject.MATERIAL_DESIGN_3,
])
def example_project(request: FixtureRequest) -> SavedPenpotProject:
    return request.param

