import os
from typing import Dict, Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import collections

from starlette.responses import HTMLResponse

from penai.config import get_config, top_level_directory

cfg = get_config()


class WebServer:
    def __init__(self) -> None:
        svg_variations_directory = os.path.join(cfg.results_dir(), "svg_variations")
        self.base_directory = svg_variations_directory
        self.app = FastAPI()
        self.templates = Jinja2Templates(directory=os.path.join(top_level_directory, "resources", "jinja_templates"))
        self.app.mount("/static", StaticFiles(directory=svg_variations_directory), name="static")

        # register routes
        self.app.get("/")(self.index)
        self.app.get("/view/{filepath:path}")(self.view_file)

    def _load_svg_variations(self) -> Dict[str, Dict[str, list[str]]]:
        html_files: Dict[str, Dict[str, list[str]]] = collections.defaultdict(lambda: collections.defaultdict(list))
        for root, dirs, files in os.walk(self.base_directory):
            for file in files:
                if file.endswith('.html'):
                    rel_dir = os.path.relpath(root, self.base_directory).replace(os.path.sep, "/")
                    shape_name = rel_dir.split("/")[0]
                    sub_dir = rel_dir[len(shape_name) + 1:]
                    html_files[shape_name][sub_dir].append(file)
        return html_files

    async def index(self, request: Request) -> HTMLResponse:
        html_files = self._load_svg_variations()
        return self.templates.TemplateResponse("svg_variations_index.html", {"request": request, "html_files": html_files})

    async def view_file(self, filepath: str) -> FileResponse:
        filepath = filepath.replace("/", os.path.sep)
        full_path = os.path.join(self.base_directory, filepath)
        return FileResponse(full_path)

    def run(self, port: int = 8000) -> None:
        import uvicorn
        uvicorn.run(self.app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    WebServer().run()
