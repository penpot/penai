import os
from pathlib import Path
from typing import Literal

from sensai.util import logging
from termcolor import colored
from tqdm import tqdm

from penai.config import get_config, pull_from_remote, top_level_directory
from penai.llm.llm_model import RegisteredLLM
from penai.registries.projects import ShapeCollection, ShapeForExperimentation
from penai.variations.svg_variations import SVGVariationsGenerator


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


def main(
    shapes_for_exp: list[ShapeForExperimentation] | None = None,
    num_variations: int = 5,
    max_shapes: int | None = None,
    report_output_dir: str = os.path.join(top_level_directory, "reports"),
    refactoring_llm: RegisteredLLM = RegisteredLLM.CLAUDE_3_5_SONNET,
    variations_llm: RegisteredLLM = RegisteredLLM.CLAUDE_3_5_SONNET,
    force_pull_global_llm_cache: bool = False,
    include_revisions: bool = False,
    num_refactoring_steps: Literal[0, 1, 2, 3] = 2,
) -> None:
    logging.configure(level=logging.INFO)

    c = get_config()

    if not c.is_using_local_llm_cache() and force_pull_global_llm_cache:
        pull_from_remote(c.llm_responses_cache_path, force=True)

    if shapes_for_exp is None:
        shapes_for_exp = ShapeCollection.get_shapes()

    if max_shapes is None:
        max_shapes = len(shapes_for_exp)

    num_shapes_for_experiments = min(max_shapes, len(shapes_for_exp))

    shape_name_to_persistence_dir_and_semantics = {}

    for i, shape_for_exp in enumerate(
        tqdm(
            shapes_for_exp,
            total=num_shapes_for_experiments,
            desc="Shape: ",
        )
    ):
        if i >= max_shapes:
            break
        shape = shape_for_exp.get_shape()
        metadata = shape_for_exp.metadata
        semantics = metadata.to_semantics_string()
        variation_logic = metadata.variation_logic
        revision_prompt = metadata.revision_prompt

        var_gen = SVGVariationsGenerator(
            shape=shape, semantics=semantics, svg_refactoring_model=refactoring_llm,
            svg_variations_model=variations_llm, num_refactoring_steps=num_refactoring_steps
        )
        shape_name_to_persistence_dir_and_semantics[shape.name] = (
            var_gen.persistence_dir,
            semantics,
        )

        print_green(
            f"Creating {num_variations} variations for shape {shape.name} with metadata semantics: {semantics}",
        )
        variations = var_gen.create_variations(num_variations=num_variations, variation_logic=variation_logic)
        if include_revisions:
            print_green(
                f"Revising the {num_variations} variations for shape {shape.name} with metadata semantics: {semantics}"
            )
            var_gen.revise_variations(variations, revision_prompt=revision_prompt)

    html_content = generate_html_content(shape_name_to_persistence_dir_and_semantics)
    html_file_path = (
        Path(report_output_dir).absolute() / logging.datetime_tag() / "variations_viewer.html"
    )
    os.makedirs(html_file_path.parent, exist_ok=True)
    print_blue(f"Saving the HTML content to {html_file_path}")
    with open(html_file_path, "w") as f:
        f.write(html_content)


if __name__ == "__main__":
    main(
        [ShapeCollection.ma_group_6_compass],
        num_variations=3, num_refactoring_steps=2
    )
