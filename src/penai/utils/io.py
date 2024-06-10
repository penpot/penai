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
