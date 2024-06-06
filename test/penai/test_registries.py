from penai.registries.projects import SavedPenpotProject


class TestPenpotProjectRegistry:

    @staticmethod
    def test_can_be_loaded(example_project: SavedPenpotProject) -> None:
        loaded_project = example_project.load(pull=True)
        assert len(loaded_project.files) > 0
