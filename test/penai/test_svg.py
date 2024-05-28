import pytest

from penai.svg import PenpotPageSVG


@pytest.fixture(scope="module")
def penpot_page_svg(page_example_svg_path: str) -> PenpotPageSVG:
    return PenpotPageSVG.from_file(page_example_svg_path)


class TestPenpotShape:
    @staticmethod
    def test_shapes_loaded(penpot_page_svg: PenpotPageSVG) -> None:
        assert penpot_page_svg.max_shape_depth > 1

    @staticmethod
    def test_printing_no_exception(penpot_page_svg: PenpotPageSVG) -> None:
        penpot_page_svg.pprint_hierarchy()

    @staticmethod
    def test_parent_child_shapes_basics(penpot_page_svg: PenpotPageSVG) -> None:
        roots = penpot_page_svg.get_shape_elements_at_depth(0)
        leaves_subset = penpot_page_svg.get_shape_elements_at_depth(penpot_page_svg.max_shape_depth)
        for root in roots:
            assert root.get_parent_shape() is None
            for child in root.get_direct_children_shapes():
                assert child.get_parent_shape() == root
        for leaf in leaves_subset:
            assert not leaf.get_all_children_shapes()
            assert not leaf.get_direct_children_shapes()
            assert leaf.get_parent_shape() is not None
            assert leaf in leaf.get_parent_shape().get_all_children_shapes()
