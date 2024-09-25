from collections import defaultdict
from html import escape
from pathlib import Path
from textwrap import dedent

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from penai.utils.misc import get_resource_dir

label_by_message_type: dict[type[BaseMessage], str] = defaultdict(lambda: "📝 Message")
label_by_message_type.update(
    {
        AIMessage: "🤖 AI Message",
        HumanMessage: "👤 Human Message",
        SystemMessage: "🖥️ System Message",
    }
)

default_stylesheet_path = get_resource_dir() / "styles/prompt_visualizer.css"


class PromptVisualizer:
    def __init__(self, stylesheet_path: str | Path | None = default_stylesheet_path):
        if stylesheet_path is not None:
            self.stylesheet = (
                "<style>\n" + Path(stylesheet_path).read_text() + "\n</style>"
            )
        else:
            self.stylesheet = ""

    def _handle_human_section(self, section: dict[str, any]) -> str:
        assert isinstance(section, dict) and "type" in section

        match section["type"]:
            case "text":
                return escape(section["text"]).replace("\n", "<br>")
            case "image_url":
                return f"<img src='{section['image_url']['url']}' />"
            case _:
                raise ValueError(f"Unsupported message section type: {section['type']}")

    def _handle_ai_section(self, section: str) -> str:
        assert isinstance(section, str)
        return escape(section).replace("\n", "<br>")

    def _visualize_message(self, message: BaseMessage) -> str:
        label = label_by_message_type[type(message)]

        sections = []

        if isinstance(message, AIMessage):
            sections = [self._handle_ai_section(message.content)]
        elif isinstance(message, HumanMessage):
            sections = [
                self._handle_human_section(section) for section in message.content
            ]
        elif isinstance(message, SystemMessage):
            sections = [self._handle_human_section(message.content)]
        else:
            raise ValueError(f"Unsupported message type: {type(message)}")

        paragraphs = (f"<p>{section}</p>" for section in sections)

        return f"<h2>{label}</h2>\n\n" + "\n".join(paragraphs)

    def _build_html(self, content: str) -> str:
        return dedent(f"""
            <!DOCTYPE html>
            <html>
                <head>
                    {self.stylesheet}
                </head>
                <body>
                    {content}
                </body>
            </html>
        """)

    def message_to_html(self, message: BaseMessage) -> str:
        return self._build_html(self._visualize_message(message))

    def messages_to_html(self, messages: list[BaseMessage]) -> str:
        return self._build_html(
            "</br>".join(self._visualize_message(message) for message in messages)
        )

    def _display(self, messages: BaseMessage | list[BaseMessage]) -> None:
        try:
            from IPython.core.display import HTML, display
        except ImportError as e:
            raise ImportError("This method requires IPython to be installed.") from e

        if isinstance(messages, list):
            html = self.messages_to_html(messages)
        elif isinstance(messages, BaseMessage):
            html = self.message_to_html(messages)
        else:
            raise ValueError("Unsupported message type")

        display(HTML(html))

    def display_message(self, message: BaseMessage) -> None:
        self._display(message)

    def display_messages(self, messages: list[BaseMessage]) -> None:
        self._display(messages)
