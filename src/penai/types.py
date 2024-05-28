import os
from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator

PathLike = str | Path | os.PathLike[str]

def _validate_uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except ValueError as e:
        raise ValueError("Invalid UUID") from e

ValidUUID = Annotated[str, AfterValidator(_validate_uuid)]
