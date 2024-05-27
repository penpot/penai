from typing import Any

from pydantic import BaseModel, RootModel

from penai.types import ValidUUID


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


class PenpotFilesSchema(RootModel):
    root: dict[ValidUUID, PenpotFileDetailsSchema]


class PenpotProjectManifestSchema(BaseModel):
    teamId: ValidUUID
    fileId: ValidUUID
    files: PenpotFilesSchema
