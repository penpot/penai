from typing import cast

from penai.llm.conversation import Conversation, HumanMessageBuilder
from penai.llm.llm_model import RegisteredLLM
from penai.registries.projects import SavedPenpotProject
from penai.registries.web_drivers import RegisteredWebDriver

from penai.render import WebDriverSVGRenderer

if __name__ == '__main__':
    saved_penpot_project = SavedPenpotProject.INTERACTIVE_MUSIC_APP
    penpot_project = saved_penpot_project.load(pull=True)
    main_file = penpot_project.get_main_file()
    page = main_file.get_page_by_name("Interactive music app")
    page.svg.retrieve_and_set_view_boxes_for_shape_elements(RegisteredWebDriver.CHROME)

    shape = page.svg.get_shape_by_name("ic_equalizer_48px-1")
    svg = shape.to_svg()
    svg.strip_penpot_tags()

    with WebDriverSVGRenderer.create_chrome_renderer() as renderer:
        renderer = cast(WebDriverSVGRenderer, renderer)
        image = renderer.render_svg(svg)

    conversation = Conversation(RegisteredLLM.GPT4O)

    response = conversation.query_text(
            HumanMessageBuilder(
                    f"Here's an SVG:\n```\n{svg.to_string()}\n```\n"
                    "Describe the image that would be generated from it (not going into the specifics of the SVG source code)."
                    "The image is given below. Consider both the SVG itself and the rendering in your response."
                    "Think step by step and be concise.\n")
                .with_image(image)
                .build())
