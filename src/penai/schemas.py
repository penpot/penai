from typing import Any
from uuid import UUID

from pydantic import BaseModel, RootModel


class PenpotPageIndexItemSchema(BaseModel):
    name: str


class PenpotFileDetailsSchema(BaseModel):
    features: list[str]
    libraries: list[Any]
    hasDeletedComponents: bool
    hasComponents: bool
    name: str
    pagesIndex: dict[UUID, PenpotPageIndexItemSchema]
    exportType: str
    pages: list[UUID]
    hasMedia: bool
    shared: bool
    version: int
    hasTypographies: bool
    hasColors: bool


class PenpotFilesSchema(RootModel):
    root: dict[UUID, PenpotFileDetailsSchema]


class PenpotProjectManifestSchema(BaseModel):
    teamId: UUID
    fileId: UUID
    files: PenpotFilesSchema
