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

    def _visualize_message(self, message: BaseMessage) -> str:
        label = label_by_message_type[type(message)]

        sections = []

        for section in message.content:
            assert isinstance(section, dict) and "type" in section

            match section["type"]:
                case "text":
                    sections.append(escape(section["text"]).replace("\n", "<br>"))
                case "image_url":
                    sections.append(f"<img src='{section['image_url']['url']}' />")
                case _:
                    raise ValueError(
                        f"Unsupported message section type: {section['type']}"
                    )

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

    def visualize_message(self, message: BaseMessage) -> str:
        return self._build_html(self._visualize_message(message))

    def visualize_messages(self, messages: list[BaseMessage]) -> str:
        return self._build_html(
            "</br>".join(self._visualize_message(message) for message in messages)
        )
