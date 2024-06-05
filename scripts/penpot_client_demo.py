from pprint import pprint

from penai.client import PenpotClient, transit_to_py
from penai.registries.projects import SavedPenpotProject

if __name__ == '__main__':
    saved_penpot_project = SavedPenpotProject.INTERACTIVE_MUSIC_APP
    penpot_project = saved_penpot_project.load(pull=True)
    main_file = penpot_project.get_main_file()
    page = main_file.get_page_by_name("Interactive music app")
    shape = page.svg.get_shape_by_name("ic_equalizer_48px-1")

    client = PenpotClient.create_default()
    result = client.get_shape_recursive_py(
        project_id=saved_penpot_project.get_project_id(),
        file_id=main_file.id,
        page_id=page.id,
        shape_id=shape.id
    )
    pprint(result)
