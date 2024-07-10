from typing import cast

from sensai.util import logging

from penai.llm.conversation import Conversation, MessageBuilder
from penai.llm.llm_model import RegisteredLLM
from penai.registries.projects import SavedPenpotProject
from penai.render import WebDriverSVGRenderer

if __name__ == "__main__":
    logging.configure()

    page_svg = SavedPenpotProject.INTERACTIVE_MUSIC_APP.load_page_svg_with_viewboxes(
        "Interactive music app"
    )

    shape = page_svg.get_shape_by_name("ic_equalizer_48px-1")
    svg = shape.to_svg()
    svg.strip_penpot_tags()

    with WebDriverSVGRenderer.create_chrome_renderer() as renderer:
        renderer = cast(WebDriverSVGRenderer, renderer)
        image = renderer.render_svg(svg)

    conversation = Conversation(RegisteredLLM.GPT4O)

    response = conversation.query_text(
        MessageBuilder(
            f"Here's an SVG:\n```\n{svg.to_string()}\n```\n"
            "Describe the image that would be generated from it (not going into the specifics of the SVG source code)."
            "The image is given below. Consider both the SVG itself and the rendering in your response."
            "Think step by step and be concise.\n"
        )
        .with_image(image)
        .build_human_message()
    )
