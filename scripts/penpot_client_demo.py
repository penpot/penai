from penai.client import PenpotClient

if __name__ == '__main__':
    client = PenpotClient.create_default()
    shape = client.get_shape(
        project_id="15586d98-a20a-8145-8004-69dd979da070",
        file_id="cdedfc7e-d457-80ce-8004-6b19bad0cffe",
        page_id="cdedfc7e-d457-80ce-8004-6b19bb6ff2c8",
        shape_id="cdedfc7e-d457-80ce-8004-6b19c3a99be9"
    )
