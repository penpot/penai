import os
from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator

PathLike = str | Path | os.PathLike[str]


def ensure_valid_uuid_str(value: str) -> str:
    """Ensures that a string is a valid UUID string, returning the input if it is or raising an error otherwise."""
    try:
        return str(UUID(value))
    except ValueError as e:
        raise ValueError("Invalid UUID") from e


ValidUUID = Annotated[str, AfterValidator(ensure_valid_uuid_str)]
