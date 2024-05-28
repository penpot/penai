import pytest

from penai.loading import load_from_directory
from penai.registries import SavedPenpotDesign


@pytest.mark.parametrize('project_directory', [project.get_path() for project in SavedPenpotDesign])
def test_load_project_directory(project_directory):
    project = load_from_directory(project_directory)

    # We very naively assume that all projects have at least one file and page
    assert len(project.files) > 0

    file = next(iter(project.files.values()))

    assert len(file.pages) > 0
