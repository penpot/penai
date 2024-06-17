import json
import os
import textwrap
from copy import deepcopy

from lxml import etree

from penai.config import top_level_directory
from penai.hierarchy_generation.inference import HierarchyElement
from penai.svg import BoundingBox, PenpotShapeElement
from penai.types import PathLike

color_by_hierarchy_level = [
    "#984447",
    "#a38f9e",
    "#add9f4",
    "#7aa3c8",
    "#6188b2",
    "#476c9b",
    "#468c98",
    "#2b5059",
    "#101419",
]


class InteractiveSVGHierarchyVisualizer:
    def __init__(self, hierarchy_element: HierarchyElement, shape: PenpotShapeElement) -> None:
        # augment hierarchy
        self._inject_hierarchy_visualization(hierarchy_element)
        self.hierarchy_element = hierarchy_element

        # create SVG with interactive elements
        svg = shape.to_svg()
        self._inject_stylesheet(svg.dom.getroot())
        self.svg = svg

    def _bbox_to_svg_attribs(self, bbox: BoundingBox) -> dict[str, str]:
        return {
            "x": str(bbox.x),
            "y": str(bbox.y),
            "width": str(bbox.width),
            "height": str(bbox.height),
        }

    @staticmethod
    def hierarchy_highlight_element_id(hierarchy_element: HierarchyElement) -> str:
        return f"hierarchy_hl_{id(hierarchy_element)}"

    def _inject_shape_visualization(self, hierarchy_element: HierarchyElement) -> None:
        root = hierarchy_element.shape.get_containing_g_element()

        interactive_group = etree.SubElement(
            root,
            "g",
            attrib={
                "class": "interactive",
                "id": self.hierarchy_highlight_element_id(hierarchy_element),
            },
        )

        hover_group = etree.SubElement(interactive_group, "g")
        ghost_group = etree.SubElement(interactive_group, "g", attrib={"pointer-events": "none"})

        hierarchy_level = 0

        while hierarchy_element is not None:
            bbox = hierarchy_element.bbox.with_margin(10)
            bbox_group = ghost_group if hierarchy_level else hover_group

            etree.SubElement(
                bbox_group,
                "rect",
                attrib={
                    **bbox.to_svg_attribs(),
                    "fill": "#ffffff30",
                    "stroke": color_by_hierarchy_level[hierarchy_level],
                    "stroke-width": "3",
                    "opacity": "0.5",
                },
            )

            if not hierarchy_level:
                label = etree.SubElement(
                    ghost_group,
                    "text",
                    attrib=dict(
                        x=str(bbox.x),
                        y=str(bbox.y - 10),
                        style="fill: black;",
                    ),
                )
                label.text = hierarchy_element.description

                label_bg = deepcopy(label)
                label_bg.attrib["style"] = "stroke:white; stroke-width:0.8em;"
                ghost_group.insert(0, label_bg)

            hierarchy_element = hierarchy_element.parent
            hierarchy_level += 1

    def _inject_stylesheet(self, svg_root: etree.Element) -> None:
        style = etree.Element("style")
        style.text = textwrap.dedent(
            """
        .interactive {
            opacity: 0;
        }

        .interactive:hover {
            opacity: 100%;
        }
        """,
        )
        svg_root.insert(0, style)

    def _inject_hierarchy_visualization(self, hierarchy: HierarchyElement) -> None:
        for hierarchy_element in hierarchy.flatten():
            if hierarchy_element is None:
                continue

            self._inject_shape_visualization(hierarchy_element)

    def write_svg(self, path: PathLike) -> None:
        self.svg.to_file(path)


class InteractiveHTMLHierarchyVisualizer:
    def __init__(
        self,
        svg_path: str,
        hierarchy_element: HierarchyElement,
        title="Hierarchy Inspection",
    ):
        with open(os.path.join(top_level_directory, "resources", "hierarchy.html")) as f:
            html_content = f.read()
        jstree_data_dict = self._create_jstree_data_dict(hierarchy_element)
        self.html_content = (
            html_content.replace("$$title", title)
            .replace("$$svgFile", svg_path)
            .replace("$$hierarchyData", json.dumps(jstree_data_dict))
        )

    def _create_jstree_data_dict(self, hierarchy_element: HierarchyElement) -> dict:
        item_dict = {
            "text": hierarchy_element.description,
            "data": {
                "id": InteractiveSVGHierarchyVisualizer.hierarchy_highlight_element_id(
                    hierarchy_element,
                ),
            },
        }
        if hierarchy_element.children:
            item_dict["children"] = [
                self._create_jstree_data_dict(child) for child in hierarchy_element.children
            ]
        return item_dict

    def write_html(self, path: PathLike) -> None:
        with open(path, "w") as f:
            f.write(self.html_content)
