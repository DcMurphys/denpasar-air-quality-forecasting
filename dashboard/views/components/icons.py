"""Material Symbols icons inside custom HTML (the font is already loaded by Streamlit)."""

from html import escape


def icon_html(name: str, color: str, size: str = "1.1rem") -> str:
    """A decorative icon; hidden from screen readers because a text label always follows."""
    style = (
        "font-family:'Material Symbols Rounded';font-weight:normal;font-style:normal;"
        f"font-size:{size};line-height:1;color:{color};vertical-align:-0.2em;"
        "font-feature-settings:'liga';-webkit-font-feature-settings:'liga';user-select:none;"
    )
    return f'<span aria-hidden="true" style="{style}">{escape(name)}</span>'
