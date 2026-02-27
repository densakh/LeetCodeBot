from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.i18n import I18n


class LocaleCallback(CallbackData, prefix="locale"):
    locale: str


class LangCallback(CallbackData, prefix="lang"):
    lang: str


class DifficultyCallback(CallbackData, prefix="diff"):
    difficulty: str


class TopicCallback(CallbackData, prefix="topic"):
    topic: str
    action: str


class SolveActionCallback(CallbackData, prefix="solve"):
    action: str


class ResultActionCallback(CallbackData, prefix="result"):
    action: str


class SettingsCallback(CallbackData, prefix="settings"):
    setting: str


class CheckAgainCallback(CallbackData, prefix="check"):
    pass


class TheoryCallback(CallbackData, prefix="theory"):
    pass


TOPICS_LIST = [
    "Arrays", "Strings", "Linked List", "Trees", "Graphs", "DP",
    "Backtracking", "Binary Search", "Greedy", "Hash Table", "Stack/Queue", "Math",
]

TOPIC_SLUGS = {
    "Arrays": "array",
    "Strings": "string",
    "Linked List": "linked-list",
    "Trees": "tree",
    "Graphs": "graph",
    "DP": "dynamic-programming",
    "Backtracking": "backtracking",
    "Binary Search": "binary-search",
    "Greedy": "greedy",
    "Hash Table": "hash-table",
    "Stack/Queue": "stack",
    "Math": "math",
}

LANGUAGES = [
    ("Python", "python3"),
    ("Kotlin", "kotlin"),
    ("Java", "java"),
    ("C++", "cpp"),
]


def locale_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🇷🇺 Русский",
                callback_data=LocaleCallback(locale="ru").pack(),
            ),
            InlineKeyboardButton(
                text="🇬🇧 English",
                callback_data=LocaleCallback(locale="en").pack(),
            ),
        ]
    ])


def language_keyboard(i18n: I18n) -> InlineKeyboardMarkup:
    buttons = []
    for name, slug in LANGUAGES:
        buttons.append(
            InlineKeyboardButton(
                text=name,
                callback_data=LangCallback(lang=slug).pack(),
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def difficulty_keyboard(i18n: I18n) -> InlineKeyboardMarkup:
    difficulties = [
        ("Easy", "Easy"),
        ("Medium", "Medium"),
        ("Hard", "Hard"),
        ("Adaptive", "Adaptive"),
    ]
    buttons = []
    for label, value in difficulties:
        buttons.append(
            InlineKeyboardButton(
                text=label,
                callback_data=DifficultyCallback(difficulty=value).pack(),
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def topics_keyboard(i18n: I18n, selected: list[str] | None = None) -> InlineKeyboardMarkup:
    selected = selected or []
    rows = []
    for topic in TOPICS_LIST:
        check = "✅ " if topic in selected else ""
        rows.append([
            InlineKeyboardButton(
                text=f"{check}{topic}",
                callback_data=TopicCallback(topic=topic, action="toggle").pack(),
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text=i18n.get("buttons.done"),
            callback_data=TopicCallback(topic="_done", action="done").pack(),
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def solve_review_keyboard(i18n: I18n) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=i18n.get("buttons.submit"),
                callback_data=SolveActionCallback(action="submit").pack(),
            ),
            InlineKeyboardButton(
                text=i18n.get("buttons.edit"),
                callback_data=SolveActionCallback(action="edit").pack(),
            ),
            InlineKeyboardButton(
                text=i18n.get("buttons.explain"),
                callback_data=SolveActionCallback(action="explain").pack(),
            ),
        ]
    ])


def result_accepted_keyboard(i18n: I18n) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=i18n.get("buttons.next"),
                callback_data=ResultActionCallback(action="next").pack(),
            ),
            InlineKeyboardButton(
                text=i18n.get("buttons.review"),
                callback_data=ResultActionCallback(action="review").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=i18n.get("buttons.improve"),
                callback_data=ResultActionCallback(action="improve").pack(),
            ),
            InlineKeyboardButton(
                text=i18n.get("buttons.revise"),
                callback_data=ResultActionCallback(action="revise").pack(),
            ),
        ]
    ])


def result_wrong_keyboard(i18n: I18n) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=i18n.get("buttons.hint"),
                callback_data=ResultActionCallback(action="hint").pack(),
            ),
            InlineKeyboardButton(
                text=i18n.get("buttons.revise"),
                callback_data=ResultActionCallback(action="revise").pack(),
            ),
        ]
    ])


def result_tle_keyboard(i18n: I18n) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=i18n.get("buttons.revise"),
                callback_data=ResultActionCallback(action="revise").pack(),
            ),
        ]
    ])


def check_again_keyboard(i18n: I18n) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=i18n.get("buttons.check_again"),
                callback_data=CheckAgainCallback().pack(),
            ),
        ]
    ])


def theory_keyboard(i18n: I18n) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=i18n.get("buttons.theory"),
                callback_data=TheoryCallback().pack(),
            ),
        ]
    ])


def settings_menu_keyboard(i18n: I18n) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🌐 " + i18n.get("settings.locale"),
                callback_data=SettingsCallback(setting="locale").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="💻 " + i18n.get("settings.language"),
                callback_data=SettingsCallback(setting="language").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="📊 " + i18n.get("settings.difficulty"),
                callback_data=SettingsCallback(setting="difficulty").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="📋 " + i18n.get("settings.topics"),
                callback_data=SettingsCallback(setting="topics").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🍪 Cookies",
                callback_data=SettingsCallback(setting="cookies").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=i18n.get("buttons.back"),
                callback_data=SettingsCallback(setting="back").pack(),
            ),
        ],
    ])
