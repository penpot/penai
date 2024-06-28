import re
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import sensai.util.io as sensai_io


class ResultWriter(sensai_io.ResultWriter):
    def write_text_file(
        self,
        filename_suffix: str,
        content: str,
        extension_to_add: str | None = None,
        content_description: str = "text file",
    ) -> str:
        p = self.path(filename_suffix, extension_to_add=extension_to_add)
        if self.enabled:
            self.log.info(f"Saving {content_description} to {p}")
            with open(p, "w") as f:
                f.write(content)
        return p


def fn_compatible(name: str) -> str:
    """Returns a filename-compatible version of the given name.

    :param name: the name
    :return: a string that can be used as a filename/directory name
    """
    name = name.replace("/", "")
    name = re.sub(r"\s+", " ", name)
    return name


@contextmanager
def temp_file_for_content(
    content: str | bytes,
    extension: str,
    delete: bool = False,
) -> Generator[Path, Any, Any]:
    """Create a temporary file for a given file content."""
    if extension and not extension.startswith("."):
        raise ValueError("Extension should start with a dot")

    if isinstance(content, str):
        mode = "w"
    else:
        assert isinstance(content, bytes)
        mode = "wb"

    # Note: (just for the curious, not actually needed to know)
    # buffering=0 is very important if you want to yield inside
    # Since we don't use the delete option here (we delete manually below)
    # we yield outside of this context
    # The code below is essentially equivalent to `with open()...write`
    with NamedTemporaryFile(prefix="penai_", suffix=extension, mode=mode, delete=False) as file:
        file.write(content)
        file.flush()

        path = Path(file.name)
    yield path

    if delete:
        path.unlink()
