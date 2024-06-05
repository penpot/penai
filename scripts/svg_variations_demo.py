from penai.registries.projects import SavedPenpotProject
from penai.registries.web_drivers import RegisteredWebDriver
from penai.variations.svg_variations import SVGVariationsGenerator

if __name__ == '__main__':
    saved_penpot_project = SavedPenpotProject.INTERACTIVE_MUSIC_APP#
    penpot_project = saved_penpot_project.load(pull=True)
    main_file = penpot_project.get_main_file()
    page = main_file.get_page_by_name("Interactive music app")
    page.svg.retrieve_and_set_view_boxes_for_shape_elements(RegisteredWebDriver.CHROME)
    shape = page.svg.get_shape_by_name("ic_equalizer_48px-1")

    var_gen = SVGVariationsGenerator(shape=shape, semantics="equalizer")
