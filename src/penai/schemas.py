from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel

from penai.types import PathLike, ValidUUID
from penai.utils import read_json


class PenpotPageIndexItemSchema(BaseModel):
    name: str


class PenpotFileDetailsSchema(BaseModel):
    features: list[str]
    libraries: list[Any]
    hasDeletedComponents: bool
    hasComponents: bool
    name: str
    pagesIndex: dict[ValidUUID, PenpotPageIndexItemSchema]
    exportType: str
    pages: list[ValidUUID]
    hasMedia: bool
    shared: bool
    version: int
    hasTypographies: bool
    hasColors: bool


class PenpotProjectManifestSchema(BaseModel):
    teamId: ValidUUID
    fileId: ValidUUID
    """The main/default file id. The `files` dict will always contain at least this key"""
    files: dict[ValidUUID, PenpotFileDetailsSchema]

    @classmethod
    def from_project_dir(cls, project_dir: PathLike) -> Self:
        return cls.from_manifest_file(Path(project_dir) / "manifest.json")

    @classmethod
    def from_manifest_file(cls, manifest_file: PathLike) -> Self:
        return cls(**read_json(manifest_file))
