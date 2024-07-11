from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any

from sensai.util import logging


class ShapeRenameInput(BaseModel):
    name: str
    shape_svg: str


class ShapeRenameOutput(BaseModel):
    name: str


class PluginBackendService:
    def __init__(self, port: int):
        self.port = port
        self.app = FastAPI()
        self._setup_routes()

    def _setup_routes(self):
        self.app.post("/rename_shape", response_model=ShapeRenameOutput)(self.rename_shape)

    async def rename_shape(self, shape_input: ShapeRenameInput) -> Dict[str, Any]:
        new_name = f"Renamed {shape_input.name}"
        return ShapeRenameOutput(name=new_name).dict()

    def run(self):
        import uvicorn
        uvicorn.run(self.app, host="0.0.0.0", port=self.port, use_colors=False)


def main(port: int):
    service = PluginBackendService(port)
    service.run()


if __name__ == "__main__":
    logging.run_cli(main, level=logging.INFO)  # type: ignore