from penai.client import PenpotClient


def test_authentication_successful() -> None:
    client = PenpotClient.create_default()
    assert client.session.cookies, "Authentication to penpot server failed, check your config!"
