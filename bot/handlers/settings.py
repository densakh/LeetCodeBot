import json
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from bot.i18n import I18n
from bot.keyboards import (
    LocaleCallback,
    LangCallback,
    DifficultyCallback,
    TopicCallback,
    SettingsCallback,
    locale_keyboard,
    language_keyboard,
    difficulty_keyboard,
    topics_keyboard,
    settings_menu_keyboard,
    TOPIC_SLUGS,
)
from bot.messages import fmt_settings
from config import COOKIE_INSTRUCTION_RU, COOKIE_INSTRUCTION_EN
from db.users import get_user, update_user, update_cookies
from leetcode.client import LeetCodeClient, CookieExpiredError

logger = logging.getLogger(__name__)

router = Router()


class SettingsStates(StatesGroup):
    MENU = State()
    COOKIES = State()
    CSRF = State()


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext, i18n: I18n, db_path: str):
    user = await get_user(db_path, message.from_user.id)
    if not user:
        await message.answer(i18n.get("errors.not_configured"))
        return

    # Save current state if in solving flow
    current_state = await state.get_state()
    if current_state and "Solving" in str(current_state):
        data = await state.get_data()
        await state.update_data(
            suspended_state=current_state,
            suspended_problem=data.get("problem_slug"),
            suspended_code=data.get("current_code"),
        )

    text = fmt_settings(user, i18n)
    await message.answer(text, reply_markup=settings_menu_keyboard(i18n), parse_mode="HTML")
    await state.set_state(SettingsStates.MENU)


@router.callback_query(SettingsStates.MENU, SettingsCallback.filter())
async def on_settings(callback: CallbackQuery, callback_data: SettingsCallback, state: FSMContext, i18n: I18n, db_path: str):
    setting = callback_data.setting

    if setting == "locale":
        await callback.message.edit_text(
            i18n.get("settings.locale"),
            reply_markup=locale_keyboard(),
        )

    elif setting == "language":
        await callback.message.edit_text(
            i18n.get("settings.language"),
            reply_markup=language_keyboard(i18n),
        )

    elif setting == "difficulty":
        await callback.message.edit_text(
            i18n.get("settings.difficulty"),
            reply_markup=difficulty_keyboard(i18n),
        )

    elif setting == "topics":
        user = await get_user(db_path, callback.from_user.id)
        current_topics = []
        if user and user.get("topics"):
            try:
                topic_slugs = json.loads(user["topics"])
                slug_to_name = {v: k for k, v in TOPIC_SLUGS.items()}
                current_topics = [slug_to_name.get(s, s) for s in topic_slugs]
            except (json.JSONDecodeError, TypeError):
                pass
        await state.update_data(selected_topics=current_topics)
        await callback.message.edit_text(
            i18n.get("settings.topics"),
            reply_markup=topics_keyboard(i18n, current_topics),
        )

    elif setting == "cookies":
        locale_val = i18n.locale
        cookie_instruction = COOKIE_INSTRUCTION_RU if locale_val == "ru" else COOKIE_INSTRUCTION_EN
        await callback.message.edit_text(
            i18n.get("settings.cookies") + "\n\n" + cookie_instruction,
        )
        await state.set_state(SettingsStates.COOKIES)

    elif setting == "back":
        data = await state.get_data()
        suspended_state = data.get("suspended_state")
        if suspended_state:
            await state.set_state(suspended_state)
            await callback.message.edit_text(i18n.get("solve.describe_approach"))
        else:
            await state.clear()
            await callback.message.edit_text("OK")

    await callback.answer()


# Settings locale callback - reuse from onboarding
@router.callback_query(SettingsStates.MENU, LocaleCallback.filter())
async def on_settings_locale(callback: CallbackQuery, callback_data: LocaleCallback, state: FSMContext, db_path: str):
    locale = callback_data.locale
    await update_user(db_path, callback.from_user.id, locale=locale)
    i18n = I18n(locale)
    await callback.message.edit_text(i18n.get("settings.updated"))

    user = await get_user(db_path, callback.from_user.id)
    text = fmt_settings(user, i18n)
    await callback.message.answer(text, reply_markup=settings_menu_keyboard(i18n), parse_mode="HTML")
    await callback.answer()


@router.callback_query(SettingsStates.MENU, LangCallback.filter())
async def on_settings_lang(callback: CallbackQuery, callback_data: LangCallback, state: FSMContext, i18n: I18n, db_path: str):
    await update_user(db_path, callback.from_user.id, preferred_lang=callback_data.lang)
    await callback.message.edit_text(i18n.get("settings.updated"))

    user = await get_user(db_path, callback.from_user.id)
    text = fmt_settings(user, i18n)
    await callback.message.answer(text, reply_markup=settings_menu_keyboard(i18n), parse_mode="HTML")
    await callback.answer()


@router.callback_query(SettingsStates.MENU, DifficultyCallback.filter())
async def on_settings_difficulty(callback: CallbackQuery, callback_data: DifficultyCallback, state: FSMContext, i18n: I18n, db_path: str):
    difficulty = callback_data.difficulty
    fields = {"difficulty": difficulty}
    if difficulty == "Adaptive":
        fields["current_difficulty"] = "Easy"
    await update_user(db_path, callback.from_user.id, **fields)
    await callback.message.edit_text(i18n.get("settings.updated"))

    user = await get_user(db_path, callback.from_user.id)
    text = fmt_settings(user, i18n)
    await callback.message.answer(text, reply_markup=settings_menu_keyboard(i18n), parse_mode="HTML")
    await callback.answer()


@router.callback_query(SettingsStates.MENU, TopicCallback.filter())
async def on_settings_topic(callback: CallbackQuery, callback_data: TopicCallback, state: FSMContext, i18n: I18n, db_path: str):
    data = await state.get_data()
    selected = data.get("selected_topics", [])

    if callback_data.action == "done":
        if not selected:
            await callback.answer(
                "Выбери хотя бы одну тему" if i18n.locale == "ru" else "Select at least one topic"
            )
            return

        topic_slugs = [TOPIC_SLUGS.get(t, t.lower()) for t in selected]
        await update_user(db_path, callback.from_user.id, topics=topic_slugs)
        await callback.message.edit_text(i18n.get("settings.updated"))

        user = await get_user(db_path, callback.from_user.id)
        text = fmt_settings(user, i18n)
        await callback.message.answer(text, reply_markup=settings_menu_keyboard(i18n), parse_mode="HTML")
        await callback.answer()
        return

    topic = callback_data.topic
    if topic in selected:
        selected.remove(topic)
    else:
        selected.append(topic)

    await state.update_data(selected_topics=selected)
    await callback.message.edit_reply_markup(
        reply_markup=topics_keyboard(i18n, selected),
    )
    await callback.answer()


@router.message(SettingsStates.COOKIES)
async def on_settings_cookies(message: Message, state: FSMContext, i18n: I18n):
    session_cookie = message.text.strip()
    await state.update_data(new_lc_session=session_cookie)
    await message.answer(i18n.get("onboarding.enter_csrf"))
    await state.set_state(SettingsStates.CSRF)


@router.message(SettingsStates.CSRF)
async def on_settings_csrf(message: Message, state: FSMContext, i18n: I18n, db_path: str, services: dict):
    csrf_token = message.text.strip()
    data = await state.get_data()
    session_cookie = data["new_lc_session"]

    client = LeetCodeClient(session_cookie, csrf_token, i18n.locale)
    try:
        valid = await client.validate_cookies()
        if not valid:
            await message.answer(i18n.get("onboarding.invalid_cookies"))
            await state.set_state(SettingsStates.COOKIES)
            return

        username = await client.get_user_profile()
        await update_cookies(db_path, message.from_user.id, session_cookie, csrf_token)
        await update_user(db_path, message.from_user.id, lc_username=username)

        # Update shared lc_client
        old_client = services.get("lc_client")
        if old_client:
            await old_client.close()
        services["lc_client"] = client

        await message.answer(i18n.get("onboarding.cookies_valid", username=username))

        user = await get_user(db_path, message.from_user.id)
        text = fmt_settings(user, i18n)
        await message.answer(text, reply_markup=settings_menu_keyboard(i18n), parse_mode="HTML")
        await state.set_state(SettingsStates.MENU)
    except CookieExpiredError:
        await client.close()
        await message.answer(i18n.get("onboarding.invalid_cookies"))
        await state.set_state(SettingsStates.COOKIES)
