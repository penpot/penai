import collections
import os
from enum import Enum

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from penai.config import get_config, top_level_directory
from penai.variations.svg_variations import SVGVariationsGenerator

cfg = get_config()


class WebServer:
    def __init__(self) -> None:
        svg_variations_directory = os.path.join(cfg.results_dir(), "svg_variations")
        self.svg_variations_dir = svg_variations_directory
        self.app = FastAPI()
        self.templates = Jinja2Templates(
            directory=os.path.join(top_level_directory, "resources", "jinja_templates")
        )

        self.app.mount("/results", StaticFiles(directory=cfg.results_dir()), name="results")
        self.app.mount(
            "/static",
            StaticFiles(directory=os.path.join(top_level_directory, "resources", "static_html")),
            name="results",
        )

        self.app.get("/")(self.index)
        self.app.get("/svg_variations")(self.variations_index)
        self.app.get("/svg_variation_transfer")(self.variation_transfer_index)

    class VariationMode(Enum):
        VARIATION_TRANSFER = "variation_transfer"
        VARIATIONS = "variation"

    def _load_svg_variations(self, mode: VariationMode) -> dict[str, dict[str, list[str]]]:
        html_files: dict[str, dict[str, list[str]]] = collections.defaultdict(
            lambda: collections.defaultdict(list)
        )

        for root, _dirs, files in os.walk(self.svg_variations_dir):
            is_variation_transfer = (
                SVGVariationsGenerator.FILENAME_VARIATION_TRANSFER_EXAMPLE_PRESENTED in files
            )
            match mode:
                case self.VariationMode.VARIATION_TRANSFER:
                    is_relevant_folder = is_variation_transfer
                case self.VariationMode.VARIATIONS:
                    is_relevant_folder = not is_variation_transfer
                case _:
                    raise ValueError
            if not is_relevant_folder:
                continue

            for file in files:
                if file.endswith((".html", ".md")):
                    rel_dir = os.path.relpath(root, self.svg_variations_dir).replace(
                        os.path.sep, "/"
                    )
                    shape_name = rel_dir.split("/")[0]
                    sub_dir = rel_dir[len(shape_name) + 1 :]
                    html_files[shape_name][sub_dir].append(file)

        sorted_html_files = {}
        for key, value in sorted(html_files.items()):
            sorted_html_files[key] = dict(sorted(value.items(), reverse=True))
        return sorted_html_files

    async def index(self, request: Request) -> HTMLResponse:
        return self.templates.TemplateResponse("index.html", {"request": request})

    async def variations_index(self, request: Request) -> HTMLResponse:
        html_files = self._load_svg_variations(self.VariationMode.VARIATIONS)
        return self.templates.TemplateResponse(
            "svg_variations_index.html",
            {"request": request, "html_files": html_files, "title": "SVG Variations"},
        )

    async def variation_transfer_index(self, request: Request) -> HTMLResponse:
        html_files = self._load_svg_variations(self.VariationMode.VARIATION_TRANSFER)
        return self.templates.TemplateResponse(
            "svg_variations_index.html",
            {
                "request": request,
                "html_files": html_files,
                "title": "SVG Variation Transfer",
            },
        )

    def run(self, port: int = 8000) -> None:
        import uvicorn

        uvicorn.run(self.app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    WebServer().run()
