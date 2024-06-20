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
    return name.replace("/", "")
