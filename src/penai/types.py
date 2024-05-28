import os
from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator

PathLike = str | Path | os.PathLike[str]


def validate_uuid(value: str) -> str:
    """Validate whether a string is a valid UUID string."""
    try:
        return str(UUID(value))
    except ValueError as e:
        raise ValueError("Invalid UUID") from e


ValidUUID = Annotated[str, AfterValidator(validate_uuid)]
