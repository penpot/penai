import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from penai.svg import PenpotPageSVG, PenpotShapeElement


@pytest.fixture()
def penpot_page_svg(page_example_svg_path: str) -> PenpotPageSVG:
    return PenpotPageSVG.from_file(page_example_svg_path)


@pytest.fixture()
def penpot_shape_el(penpot_page_svg: PenpotPageSVG) -> PenpotShapeElement:
    return penpot_page_svg.get_shape_elements_at_depth(1)[0]


class TestPenpotPage:
    @staticmethod
    def test_shapes_loaded(penpot_page_svg: PenpotPageSVG) -> None:
        assert penpot_page_svg.max_shape_depth > 1

    @staticmethod
    def test_printing_no_exception(penpot_page_svg: PenpotPageSVG) -> None:
        penpot_page_svg.pprint_hierarchy()

    @staticmethod
    def test_parent_child_shapes_basics(penpot_page_svg: PenpotPageSVG) -> None:
        root_shape_els = penpot_page_svg.get_shape_elements_at_depth(0)
        leaves_subset = penpot_page_svg.get_shape_elements_at_depth(
            penpot_page_svg.max_shape_depth,
        )
        for root in root_shape_els:
            assert root.get_parent_shape() is None
            for child in root.get_direct_children_shapes():
                assert child.get_parent_shape() == root
        for leaf in leaves_subset:
            assert not leaf.get_all_children_shapes()
            assert not leaf.get_direct_children_shapes()
            assert leaf.get_parent_shape() is not None
            assert leaf in leaf.get_parent_shape().get_all_children_shapes()

    @staticmethod
    def test_penpot_page_svg_bbox_derivation(
        penpot_page_svg: PenpotPageSVG,
        chrom_web_driver: WebDriver,
    ) -> None:
        penpot_page_svg.retrieve_and_set_view_boxes_for_shape_elements(chrom_web_driver)
        shapes = penpot_page_svg.penpot_shape_elements

        for shape in shapes:
            bbox = shape.get_default_view_box()

            assert bbox is not None

            # BBoxes can (probably) be of zero size but not of negative dimensions
            assert bbox.width >= 0
            assert bbox.height >= 0

    # a small integration test
    @staticmethod
    def test_individual_vs_page_based_viewbox(
        penpot_page_svg: PenpotPageSVG,
        penpot_shape_el: PenpotShapeElement,
        chrom_web_driver: WebDriver,
    ) -> None:
        with pytest.raises(ValueError):
            # bbox not set yet, retrieving causes error
            penpot_shape_el.get_default_view_box()

        # computing viewbox individually for the shape by rendering
        original_shape_bbox = penpot_shape_el.get_default_view_box(chrom_web_driver)

        # computing viewbox for all shapes in the page
        penpot_page_svg.retrieve_and_set_view_boxes_for_shape_elements(chrom_web_driver, show_progress=False)
        shape_from_page = penpot_page_svg.get_shape_by_id(penpot_shape_el.shape_id)

        # shape elements should be equal
        assert penpot_shape_el == shape_from_page
        # explicitly checking viewboxes that were retrieved in different ways
        assert penpot_shape_el.get_default_view_box() == original_shape_bbox

        assert penpot_shape_el.to_svg().get_view_box() == original_shape_bbox
