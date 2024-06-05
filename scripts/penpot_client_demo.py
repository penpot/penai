from penai.client import PenpotClient
from penai.registries.projects import SavedPenpotProject

if __name__ == '__main__':
    penpot_project = SavedPenpotProject.INTERACTIVE_MUSIC_APP.load(pull=True)
    project_id = "15586d98-a20a-8145-8004-69dd979da070"

    main_file = penpot_project.get_main_file()
    page = main_file.get_page_by_name("Interactive music app")
    shape = page.svg.get_shape_by_name("ic_equalizer_48px-1")

    client = PenpotClient.create_default()
    result = client.get_shape(
        project_id=project_id,
        file_id=main_file.id,
        page_id=page.id,
        shape_id=shape.id
    )
