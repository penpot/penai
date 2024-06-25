from sensai.util import logging

from penai.llm.llm_model import RegisteredLLM
from penai.registries.variation_transfer_tasks import VariationTransferTasks, VariationTransferTask
from penai.variations.svg_variations import SVGVariationsGenerator


def run_variation_transfer(
        tasks: list[VariationTransferTask] | None = None,
        model: RegisteredLLM = RegisteredLLM.CLAUDE_3_5_SONNET) -> None:
    if tasks is None:
        tasks = VariationTransferTasks.items()
    for task in tasks:
        for shape_ref in task.shapes:
            var_gen = SVGVariationsGenerator(shape_ref.load_shape(), model=model)
            example_variations = task.shape_variation_template.to_svg_variations()
            var_gen.create_variations_from_example(example_variations)


if __name__ == '__main__':
    logging.configure(level=logging.INFO)
    run_variation_transfer()
