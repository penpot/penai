import random
from collections.abc import Callable, Iterable
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from penai.models import PenpotFile, PenpotPage, PenpotProject
from penai.registries.projects import SavedPenpotProject
from penai.render import BaseSVGRenderer
from penai.svg import PenpotPageSVG, PenpotShapeElement


@pytest.fixture()
def penpot_page_svg(page_example_svg_path: str) -> PenpotPageSVG:
    return PenpotPageSVG.from_file(page_example_svg_path)


@pytest.fixture()
def penpot_shape_el(penpot_page_svg: PenpotPageSVG) -> PenpotShapeElement:
    return penpot_page_svg.get_shape_elements_at_depth(1)[0]


class TestPenpotPage:
    RENDER_WIDTH = 1024

    def test_shapes_loaded(self, penpot_page_svg: PenpotPageSVG) -> None:
        assert penpot_page_svg.max_shape_depth > 1

    def test_printing_no_exception(self, penpot_page_svg: PenpotPageSVG) -> None:
        penpot_page_svg.pprint_hierarchy()

    def test_parent_child_shapes_basics(self, penpot_page_svg: PenpotPageSVG) -> None:
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

    def test_penpot_page_svg_bbox_derivation(
        self,
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
    def test_individual_vs_page_based_viewbox(
        self,
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
        penpot_page_svg.retrieve_and_set_view_boxes_for_shape_elements(
            chrom_web_driver,
            show_progress=False,
        )
        shape_from_page = penpot_page_svg.get_shape_by_id(penpot_shape_el.shape_id)

        # shape elements should be equal
        assert penpot_shape_el == shape_from_page
        # explicitly checking viewboxes that were retrieved in different ways
        assert penpot_shape_el.get_default_view_box() == original_shape_bbox

        assert penpot_shape_el.to_svg().get_view_box() == original_shape_bbox

    def _gen_page_diffs(
        self,
        project: PenpotProject,
        renderer: BaseSVGRenderer,
        hook: Callable[[PenpotFile, PenpotPage], bool | None],
    ) -> Iterable[tuple[np.ndarray, np.ndarray]]:
        for file in project.files.values():
            for page in file.pages.values():
                shapes_before = list(page.svg.penpot_shape_elements)

                img_before = renderer.render_svg(page.svg, width=self.RENDER_WIDTH).image

                if hook(file, page) is False:
                    continue

                shapes_after = list(page.svg.penpot_shape_elements)

                assert len(shapes_before) >= len(shapes_after)

                img_after = renderer.render_svg(page.svg, width=self.RENDER_WIDTH).image

                img_before_arr = np.array(img_before) / 255.0
                img_after_arr = np.array(img_after) / 255.0

                yield img_before_arr, img_after_arr

    def _save_diff_fig(self, img_before: np.ndarray, img_after: np.ndarray, save_path: Path) -> None:
        fig, (before_ax, after_ax, diff_ax) = plt.subplots(1, 3, figsize=(40, 10))

        before_ax.imshow(img_before)
        before_ax.set_title("Before")

        after_ax.imshow(img_after)
        after_ax.set_title("After")

        diff = abs(img_before - img_after)

        diff_ax.imshow(diff)
        diff_ax.set_title("Diff")

        fig.savefig(save_path, bbox_inches="tight", dpi=400)

    def test_removing_shapes_without_content(
        self,
        example_project: SavedPenpotProject,
        resvg_renderer: BaseSVGRenderer,  # We specifically use the resvg renderer as the Chrome renderer might be non-deterministic
        log_dir: Path,
    ) -> None:
        renderer = resvg_renderer

        def hook(file: PenpotFile, page: PenpotPage) -> None:
            shapes_before = list(page.svg.penpot_shape_elements)

            page.svg.remove_elements_with_no_visible_content()

            shapes_after = list(page.svg.penpot_shape_elements)

            assert len(shapes_before) >= len(shapes_after)

        # TODO: this adds a relatively large overhead to the tests.
        # We should consider reducing the number of files or pages we test on.
        for img_before, img_after in self._gen_page_diffs(
            example_project.load(),
            renderer,
            hook,
        ):
            if not np.allclose(img_before, img_after, atol=0.02):
                self._save_diff_fig(
                    img_before,
                    img_after,
                    save_path := (
                        log_dir / f"removing_shapes_without_content_{example_project.name}.png"
                    ),
                )

                diff = abs(img_before - img_after)

                raise AssertionError(
                    f"Images do not match. Max diff of {np.max(diff)} between the two versions. Saved to file://{save_path} for visual inspection.",
                )

    def test_removal_of_visible_elements_test(
        self,
        example_project: SavedPenpotProject,
        resvg_renderer: BaseSVGRenderer,  # We specifically use the resvg renderer as the Chrome renderer might be non-deterministic
        log_dir: Path,
    ) -> None:
        renderer = resvg_renderer

        def hook(file: PenpotFile, page: PenpotPage) -> bool | None:
            try:
                # Choose a random visible top-level shape to remove
                top_level_shapes = page.svg.get_shape_elements_at_depth(0)
                visible_shape = random.choice(
                    [shape for shape in top_level_shapes if shape.check_for_visible_content()],
                )
            except IndexError:
                return False

            page.svg.remove_shape(visible_shape.shape_id)
            return None

        for img_before, img_after in self._gen_page_diffs(
            example_project.load(),
            renderer,
            hook,
        ):
            if np.allclose(img_before, img_after, atol=0.02):
                self._save_diff_fig(
                    img_before,
                    img_after,
                    save_path := log_dir / f"removing_visible_element_{example_project.name}.png",
                )

                diff = abs(img_before - img_after)

                raise AssertionError(
                    f"Images do match while they shouldn't. Max diff of {np.max(diff)} between the two versions. Saved to file://{save_path} for visual inspection.",
                )
