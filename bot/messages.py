import re

from bot.i18n import I18n
from leetcode.models import Problem, SubmissionResult


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def md_to_html(text: str) -> str:
    # Extract code blocks first to protect them from other transformations
    code_blocks: list[str] = []

    def _save_code_block(m):
        lang = m.group(1) or ""
        code = m.group(2)
        if lang:
            block = f'<pre><code class="language-{lang}">{escape_html(code)}</code></pre>'
        else:
            block = f'<pre>{escape_html(code)}</pre>'
        code_blocks.append(block)
        return f"\x00CODEBLOCK{len(code_blocks) - 1}\x00"

    text = re.sub(r'```(\w*)\n?(.*?)```', _save_code_block, text, flags=re.DOTALL)

    # Escape HTML in remaining text (outside code blocks)
    parts = re.split(r'(\x00CODEBLOCK\d+\x00)', text)
    for i, part in enumerate(parts):
        if not part.startswith('\x00CODEBLOCK'):
            parts[i] = escape_html(part)
    text = ''.join(parts)

    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)

    # Italic: *text* or _text_ (but not inside words with underscores)
    text = re.sub(r'(?<!\w)\*([^*]+?)\*(?!\w)', r'<i>\1</i>', text)
    text = re.sub(r'(?<!\w)_([^_]+?)_(?!\w)', r'<i>\1</i>', text)

    # Inline code: `text`
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Strikethrough: ~~text~~
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)

    # Headers: ## text -> bold
    text = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)

    # Restore code blocks
    for i, block in enumerate(code_blocks):
        text = text.replace(f'\x00CODEBLOCK{i}\x00', block)

    return text


# Keep old name as alias
md_code_to_html = md_to_html


def split_message(text: str, limit: int = 4096) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        split_at = text.rfind('\n', 0, limit)
        if split_at == -1:
            split_at = limit
        parts.append(text[:split_at])
        text = text[split_at:].lstrip('\n')
    return parts


def fmt_problem(problem: Problem, i18n: I18n, lang_slug: str | None = None) -> str:
    diff_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(problem.difficulty, "")
    tags = ", ".join(problem.topic_tags) if problem.topic_tags else ""
    header = (
        f"<b>#{problem.frontend_id}. {escape_html(problem.title)}</b> {diff_emoji}\n"
        f"<code>/problem {problem.title_slug}</code>\n"
        f"<a href='https://leetcode.com/problems/{problem.title_slug}/'>LeetCode</a>"
    )
    if tags:
        header += f"\n{escape_html(tags)}"
    header += f"\n\n{problem.content}"

    if lang_slug and problem.code_snippets:
        snippet = next((s for s in problem.code_snippets if s.lang_slug == lang_slug), None)
        if snippet:
            header += f"\n\n<pre><code class=\"language-{snippet.lang_slug}\">{escape_html(snippet.code)}</code></pre>"

    return header


def fmt_code(code: str, language: str) -> str:
    return f'<pre><code class="language-{language}">{escape_html(code)}</code></pre>'


def fmt_accepted(result: SubmissionResult, i18n: I18n) -> str:
    return i18n.get(
        "solve.accepted",
        runtime=result.runtime_display,
        runtime_percentile=f"{result.runtime_percentile:.1f}",
        memory=result.memory_display,
        memory_percentile=f"{result.memory_percentile:.1f}",
    )


def fmt_wrong_answer(result: SubmissionResult, i18n: I18n) -> str:
    return i18n.get(
        "solve.wrong_answer",
        correct=str(result.total_correct),
        total=str(result.total_testcases),
        expected=escape_html(result.expected_output),
        output=escape_html(result.code_output),
    )


def fmt_tle(result: SubmissionResult, i18n: I18n) -> str:
    return i18n.get(
        "solve.tle",
        correct=str(result.total_correct),
        total=str(result.total_testcases),
    )


def fmt_runtime_error(result: SubmissionResult, i18n: I18n) -> str:
    return i18n.get(
        "solve.runtime_error",
        correct=str(result.total_correct),
        total=str(result.total_testcases),
    )


def fmt_compile_error(result: SubmissionResult, i18n: I18n) -> str:
    return i18n.get(
        "solve.compile_error",
        error=escape_html(result.compile_error or "Unknown error"),
    )


def fmt_memory_limit(result: SubmissionResult, i18n: I18n) -> str:
    return i18n.get(
        "solve.memory_limit",
        correct=str(result.total_correct),
        total=str(result.total_testcases),
    )


def fmt_unknown_result(result: SubmissionResult, i18n: I18n) -> str:
    return i18n.get(
        "solve.unknown_result",
        status_code=str(result.status_code),
        correct=str(result.total_correct),
        total=str(result.total_testcases),
    )


def fmt_stats(stats: dict, i18n: I18n) -> str:
    bd = stats["by_difficulty"]
    topics_str = ", ".join(stats["favorite_topics"]) if stats["favorite_topics"] else "—"
    return (
        i18n.get("stats.header") + "\n\n"
        + i18n.get("stats.total_solved", total=str(stats["total"])) + "\n"
        + i18n.get("stats.by_difficulty", easy=str(bd["Easy"]), medium=str(bd["Medium"]), hard=str(bd["Hard"])) + "\n"
        + i18n.get("stats.streak", streak=str(stats["streak"])) + "\n"
        + i18n.get("stats.favorite_topics", topics=topics_str)
    )


def fmt_settings(user: dict, i18n: I18n) -> str:
    import json
    topics_raw = user.get("topics", "[]")
    try:
        topics = json.loads(topics_raw) if topics_raw else []
    except (json.JSONDecodeError, TypeError):
        topics = []
    topics_str = ", ".join(topics) if topics else "—"

    lang_map = {"python3": "Python", "kotlin": "Kotlin", "java": "Java", "cpp": "C++"}
    lang_display = lang_map.get(user.get("preferred_lang", ""), user.get("preferred_lang", "—"))

    return i18n.get(
        "settings.menu",
        locale=user.get("locale", "ru"),
        language=lang_display,
        difficulty=user.get("difficulty", "—"),
        topics=topics_str,
    )
