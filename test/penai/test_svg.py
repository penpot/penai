import pytest
from selenium.webdriver.remote.webdriver import WebDriver

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
        roots = list(penpot_page_svg.iter_shape_elements_at_depth(0))
        leaves_subset = list(penpot_page_svg.iter_shape_elements_at_depth(penpot_page_svg.max_shape_depth))
        for root in roots:
            assert root.get_parent_shape() is None
            for child in root.get_direct_children_shapes():
                assert child.get_parent_shape() == root
        for leaf in leaves_subset:
            assert not list(leaf.iter_all_children_shapes())
            assert not leaf.get_direct_children_shapes()
            assert leaf.get_parent_shape() is not None

            if (parent_shape := leaf.get_parent_shape()):
                assert leaf in list(parent_shape.iter_all_children_shapes())


class TestPenpotPageSVG:
    @staticmethod
    def test_penpot_page_svg_bbox_derivation(
        penpot_page_svg: PenpotPageSVG,
        chrom_web_driver: WebDriver,
    ) -> None:
        shapes = list(penpot_page_svg.iter_all_shape_elements())

        # Should be None before deriving
        for shape in shapes:
            assert shape.bounding_box is None

        penpot_page_svg.derive_bounding_boxes(chrom_web_driver)

        for shape in shapes:
            bbox = shape.bounding_box

            assert bbox is not None

            # BBoxes can (probably) be of zero size but not of negative dimensions
            assert bbox.width >= 0
            assert bbox.height >= 0
