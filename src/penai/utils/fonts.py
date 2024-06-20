import cssutils

from penai.constants import PENPOT_FONT_MAPPING
from penai.errors import FontFetchError
from penai.utils.misc import get_cached_requests_session


def get_css_for_google_font(font_family: str, font_weight: str | None = None) -> str:
    """Return the CSS for a given Google Font."""
    font_query = font_family

    if font_weight:
        font_query += f":{font_weight}"

    session = get_cached_requests_session("google-fonts")

    rsp = session.get(
        "https://fonts.googleapis.com/css",
        params={"family": font_query},
    )

    if rsp.status_code != 200:
        raise FontFetchError(f"Failed to fetch font: {rsp.status_code}")

    return rsp.text


def replace_font_families(css: str, mapping: dict[str, str]) -> str:
    """Replace font families in a CSS stylesheet given as string."""
    sheet = cssutils.parseString(css)

    for rule in sheet:
        if isinstance(rule, cssutils.css.CSSFontFaceRule):
            for property in rule.style:
                font_family = property.value.strip('"')
                if property.name == "font-family" and font_family in mapping:
                    property.value = f'"{mapping[font_family]}"'

    return sheet.cssText.decode("utf-8")


def get_css_for_penpot_font(font_family: str, font_weight: str | None = None) -> str:
    """Return the CSS for a given font family as in Penpot.

    This will take care of handling naming differences between Google Fonts names and
    some Penpot-specific legacy font names.
    """
    original_font_family = font_family

    if font_family in PENPOT_FONT_MAPPING:
        font_family = PENPOT_FONT_MAPPING[font_family]

    css = get_css_for_google_font(font_family, font_weight)

    if font_family != original_font_family:
        css = replace_font_families(css, {font_family: original_font_family})

    return css
