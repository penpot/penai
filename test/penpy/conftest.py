from pathlib import Path

import pytest


def example_file(path):
    path = Path(path)
    assert path.exists()
    return path


@pytest.fixture()
def example_svg_path():
    return example_file('test/fixtures/example.svg')


@pytest.fixture()
def example_png():
    return example_file('test/fixtures/example.png')
