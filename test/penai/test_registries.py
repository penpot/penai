import pytest

from penai.registries.projects import SavedPenpotProject


class TestPenpotProjectRegistry:
    @staticmethod
    @pytest.mark.skip(reason="may fail due to a upstream bug in accrs")
    def test_can_be_loaded(example_project: SavedPenpotProject) -> None:
        loaded_project = example_project.load(pull=True)
        assert len(loaded_project.files) > 0
