import pytest

from penai.registries import SavedPenpotProject

projects_to_test = [
    SavedPenpotProject.AVATAAARS,
    SavedPenpotProject.BLACK_AND_WHITE_MOBILE_TEMPLATES,
    SavedPenpotProject.MATERIAL_DESIGN_3,
]


class TestPenpotProjectRegistry:

    @staticmethod
    @pytest.mark.parametrize("project", projects_to_test)
    def test_can_be_loaded(project: SavedPenpotProject) -> None:
        loaded_project = project.load(pull=True)
        assert len(loaded_project.files) > 0
