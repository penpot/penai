import base64

from IPython.display import IFrame


class IFrameFromSrc(IFrame):
    def __init__(self, html_content: str, width: int = 800, height: int = 600):
        encoded_content = base64.b64encode(html_content.encode()).decode()
        data_uri = f"data:text/html;base64,{encoded_content}"
        super().__init__(data_uri, width, height)
