import os
from pathlib import Path


# TODO: sphinx is too dumb to render modules without at least one function
#  and I couldn't figure out how to suppress the specific warning
#  Remove once the module is less empty
def dummy() -> None:
    """Dummy function to make sphinx happy."""


PathLike = str | Path | os.PathLike[str]
