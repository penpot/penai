import os
from typing import Any

from penai.config import top_level_directory


class HierarchyHTMLVisualisation:
    def __init__(self, svg_path: str, hierarchy: Any, title="Hierarchy Inspection"):
        with open(os.path.join(top_level_directory, "resources", "hierarchy.html"), "r") as f:
            html_content = f.read()
        self.html_content = html_content.replace("$$title", title).replace("$$svgFile", svg_path)
