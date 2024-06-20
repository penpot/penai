from calendar import c
import os
from pathlib import Path
from jsonargparse import CLI
from regex import W
from sensai.util import logging

from penai.registries.projects import SavedPenpotProject
from penai.variations.svg_variations import SVGVariationsGenerator
from tqdm import tqdm
from termcolor import colored


def generate_html_content(
    shape_name_to_persistence_dir_and_semantics: dict[str, tuple[Path, str]]
) -> str:
    """Generate HTML content from the list of directories and file paths."""
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Variations Viewer</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
            }}
            .directory {{
                margin-bottom: 30px;
            }}
            .file {{
                margin-bottom: 20px;
            }}
            iframe {{
                width: 100%;
                height: 500px;
                border: 1px solid #ccc;
            }}
        </style>
    </head>
    <body>
    <h1>Variations:</h1>
    {content}
    </body>
    </html>
    """

    def get_variations_template(
        shape_name: str, semantics: str, variations_path: str, revised_variations_path: str
    ) -> str:
        return f"""
        <div>
            <h2>Shape: {shape_name}</h2>
            <span>Semantics string: {semantics} </span>
            
            <h3>Variations</h3>
            <iframe src="{variations_path}" title="Variations"></iframe>
            
            <h3>Revised Variations</h3>
            <iframe src="{revised_variations_path}" title="Variations"></iframe>
        </div>
        """

    content = ""
    for shape_name, (
        persistence_dir,
        semantics,
    ) in shape_name_to_persistence_dir_and_semantics.items():
        variations_path = str(persistence_dir / "variations.html")
        revised_variations_path = str(persistence_dir / "revised_variations.html")
        content += get_variations_template(
            shape_name, semantics, variations_path, revised_variations_path
        )
    return html_template.format(content=content)


def print_green(text: str) -> None:
    print(colored(text, "green"))


def print_blue(text: str) -> None: 
    print(colored(text, "blue"))


def main(num_variations: int = 2, max_shapes: int = 2, report_output_dir: str = "reports") -> None:
    logging.configure(level=logging.INFO)

    num_shapes_for_experiments = min(
        max_shapes, SavedPenpotProject.get_num_all_selected_shapes_for_experiments()
    )

    shape_name_to_persistence_dir_and_semantics = {}

    for i, (shape, metadata) in enumerate(
        tqdm(
            SavedPenpotProject.get_all_selected_shapes_for_experiments(),
            total=num_shapes_for_experiments,
            desc="Shape: ",
        )
    ):
        if i >= max_shapes:
            break
        semantics = metadata.to_semantics_string()
        var_gen = SVGVariationsGenerator(shape=shape, semantics=semantics)
        shape_name_to_persistence_dir_and_semantics[shape.name] = (
            var_gen.persistence_dir,
            semantics,
        )

        print_green(
            f"Creating {num_variations} variations for shape {shape.name} with metadata semantics: {semantics}",
        )
        variations = var_gen.create_variations(num_variations=num_variations)
        print_green(
            f"Revising the {num_variations} variations for shape {shape.name} with metadata semantics: {semantics}"
        )
        var_gen.revise_variations(variations)

    html_content = generate_html_content(shape_name_to_persistence_dir_and_semantics)
    html_file_path = (
        Path(report_output_dir).absolute() / logging.datetime_tag() / "variations_viewer.html"
    )
    os.makedirs(html_file_path.parent, exist_ok=True)
    print_blue(f"Saving the HTML content to {html_file_path}")
    with open(html_file_path, "w") as f:
        f.write(html_content)


if __name__ == "__main__":
    CLI(main)
