import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString, Tag

SUPERSCRIPT_MAP = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
    'n': 'ⁿ', 'i': 'ⁱ',
}

SUBSCRIPT_MAP = {
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
    '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
    '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
}


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class ConvertedProblem:
    text: str
    image_urls: list[str] = field(default_factory=list)


def convert_problem_html(raw_html: str, locale: str = "ru") -> ConvertedProblem:
    if not raw_html:
        return ConvertedProblem(text="", image_urls=[])

    soup = BeautifulSoup(raw_html, "lxml")
    image_urls: list[str] = []
    placeholder = "[📎 изображение]" if locale == "ru" else "[📎 image]"

    def convert_node(node) -> str:
        if isinstance(node, NavigableString):
            text = str(node)
            return escape_html(text)

        if not isinstance(node, Tag):
            return ""

        tag = node.name.lower()

        if tag == "img":
            src = node.get("src", "")
            if src:
                image_urls.append(src)
            return placeholder

        children_text = "".join(convert_node(child) for child in node.children)

        if tag == "p":
            return children_text + "\n\n"
        elif tag in ("strong", "b"):
            return f"<b>{children_text}</b>"
        elif tag in ("em", "i"):
            return f"<i>{children_text}</i>"
        elif tag == "code":
            if node.parent and node.parent.name == "pre":
                return children_text
            return f"<code>{children_text}</code>"
        elif tag == "pre":
            return f"<pre>{children_text}</pre>\n\n"
        elif tag == "a":
            href = node.get("href", "")
            return f'<a href="{href}">{children_text}</a>'
        elif tag == "ul":
            return children_text + "\n"
        elif tag == "ol":
            result = ""
            counter = 1
            for child in node.children:
                if isinstance(child, Tag) and child.name == "li":
                    li_text = "".join(convert_node(c) for c in child.children).strip()
                    result += f"{counter}. {li_text}\n"
                    counter += 1
            return result + "\n"
        elif tag == "li":
            if node.parent and node.parent.name == "ol":
                return ""
            return f"• {children_text.strip()}\n"
        elif tag == "sup":
            raw_text = node.get_text()
            return "".join(SUPERSCRIPT_MAP.get(c, c) for c in raw_text)
        elif tag == "sub":
            raw_text = node.get_text()
            return "".join(SUBSCRIPT_MAP.get(c, c) for c in raw_text)
        elif tag == "table":
            return _convert_table(node) + "\n\n"
        elif tag == "br":
            return "\n"
        elif tag == "div":
            return "\n" + children_text
        elif tag == "blockquote":
            return f"<blockquote>{children_text}</blockquote>"
        elif tag in ("html", "body", "[document]", "span"):
            return children_text
        else:
            return children_text

    result = convert_node(soup)
    return ConvertedProblem(
        text=_postprocess(result),
        image_urls=image_urls,
    )


def _convert_table(table: Tag) -> str:
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = []
        for cell in tr.find_all(["th", "td"]):
            cells.append(cell.get_text().strip())
        if cells:
            rows.append(cells)

    if not rows:
        return ""

    num_cols = max(len(row) for row in rows)
    col_widths = [0] * num_cols
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    lines = []
    for row in rows:
        parts = []
        for i in range(num_cols):
            cell = row[i] if i < len(row) else ""
            parts.append(cell.ljust(col_widths[i] + 2))
        lines.append("".join(parts).rstrip())

    return "<pre>" + escape_html("\n".join(lines)) + "</pre>"


def _postprocess(text: str) -> str:
    # Collapse excessive newlines and strip
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text
