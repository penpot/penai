import io
from typing import Any, Self
from uuid import UUID

import requests
from transit.reader import Reader
from transit.transit_types import Keyword, TaggedValue, frozendict

from penai.config import get_config

SERVER_URL_DEFAULT = "https://design.penpot.app"


class PenpotClient:
    """Client for interaction with the Penpot backend."""

    def __init__(self, user_email: str, user_password: str, server_url: str = SERVER_URL_DEFAULT):
        self.server_url = server_url
        login_response = self._login(user_email, user_password)
        self.auth_token = login_response.cookies["auth-token"]

    @classmethod
    def create_default(cls) -> Self:
        cfg = get_config()
        return cls(cfg.penpot_user, cfg.penpot_password)

    def _login(self, email: str, password: str) -> requests.Response:
        url = f"{self.server_url}/api/rpc/command/login-with-password"
        json = {
            "~:email": email,
            "~:password": password,
        }
        headers = {
            "Content-Type": "application/transit+json",
        }
        return requests.post(url=url, headers=headers, json=json)

    def _read_transit_dict(self, response: requests.Response) -> dict:
        reader = Reader("json")
        return reader.read(io.StringIO(response.text))

    def get_file(self, project_id: str, file_id: str) -> dict:
        url = f"{self.server_url}/api/rpc/command/get-file"
        params = {
            "id": file_id,
            "project-id": project_id,
            "features": [
                "layout/grid",
                "styles/v2",
                "fdata/pointer-map",
                "fdata/objects-map",
                "components/v2",
                "fdata/shape-data-type",
            ],
        }
        cookies = {
            "auth-token": self.auth_token,
        }
        resp = requests.get(url=url, params=params, cookies=cookies)
        return self._read_transit_dict(resp)

    def _get_file_fragment(self, file_id: str, fragment_id: str) -> dict:
        url = f"{self.server_url}/api/rpc/command/get-file-fragment"
        params = {
            "file-id": file_id,
            "fragment-id": fragment_id,
        }
        cookies = {
            "auth-token": self.auth_token,
        }
        resp = requests.get(url=url, params=params, cookies=cookies)
        return self._read_transit_dict(resp)

    def get_page(self, project_id: str, file_id: str, page_id: str) -> dict:
        data = self.get_file(project_id, file_id)
        pages_index = data[Keyword("data")][Keyword("pages-index")]
        page = pages_index[UUID(page_id)]
        if Keyword("objects") not in page:
            raise NotImplementedError("Retrieval of missing page fragments not implemented")
            # TODO implement retrieval if necessary
            # Code to be adapted for this:
            # fragment_id = v["~#penpot/pointer"][0]
            # fragment = self._get_file_fragment(file_id, fragment_id[2:])
            # data["~:data"]["~:pages-index"][k] = fragment["~:content"]
        return page

    def get_shape(self, project_id: str, file_id: str, page_id: str, shape_id: str) -> dict:
        page = self.get_page(project_id, file_id, page_id)
        objects = page[Keyword("objects")]
        return objects[UUID(shape_id)]


def transit_to_py(obj: Any) -> Any:
    """Recursively converts the given transit representation to more primitive Python types.

    :param obj: the object the convert
    :return: the simplified representation
    """
    if isinstance(obj, TaggedValue):
        return {obj.tag: transit_to_py(obj.rep)}
    elif isinstance(obj, frozendict):
        return {transit_to_py(k): transit_to_py(v) for k, v in obj.items()}
    elif isinstance(obj, Keyword):
        return obj.name
    elif isinstance(obj, tuple):
        return tuple(transit_to_py(x) for x in obj)
    elif isinstance(obj, UUID):
        return obj.hex
    else:
        return obj
