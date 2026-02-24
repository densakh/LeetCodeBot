import json
import logging

from aiogram import Router, F
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
    locale_keyboard,
    language_keyboard,
    difficulty_keyboard,
    topics_keyboard,
    TOPICS_LIST,
    TOPIC_SLUGS,
)

from db.users import create_user, get_user, update_user, update_cookies
from leetcode.client import LeetCodeClient, CookieExpiredError

logger = logging.getLogger(__name__)

router = Router()


class OnboardingStates(StatesGroup):
    LOCALE = State()
    SESSION = State()
    CSRF = State()
    LANG = State()
    DIFFICULTY = State()
    TOPICS = State()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, i18n: I18n, db_path: str):
    user = await get_user(db_path, message.from_user.id)
    if user and user.get("lc_session"):
        await message.answer(i18n.get("onboarding.already_configured"))
        return

    await create_user(db_path, message.from_user.id)
    await message.answer(
        i18n.get("onboarding.welcome") + "\n\n" + i18n.get("onboarding.choose_locale"),
        reply_markup=locale_keyboard(),
    )
    await state.set_state(OnboardingStates.LOCALE)


@router.callback_query(OnboardingStates.LOCALE, LocaleCallback.filter())
async def on_locale(callback: CallbackQuery, callback_data: LocaleCallback, state: FSMContext, db_path: str):
    locale = callback_data.locale
    await update_user(db_path, callback.from_user.id, locale=locale)
    i18n = I18n(locale)
    await state.update_data(locale=locale)

    await callback.message.edit_text(
        i18n.get("onboarding.enter_session"),
    )
    await state.set_state(OnboardingStates.SESSION)
    await callback.answer()


@router.message(OnboardingStates.SESSION)
async def on_session(message: Message, state: FSMContext, i18n: I18n):
    session_cookie = message.text.strip()
    await state.update_data(lc_session=session_cookie)
    await message.answer(i18n.get("onboarding.enter_csrf"))
    await state.set_state(OnboardingStates.CSRF)


@router.message(OnboardingStates.CSRF)
async def on_csrf(message: Message, state: FSMContext, i18n: I18n, db_path: str, services: dict):
    csrf_token = message.text.strip()
    data = await state.get_data()
    session_cookie = data["lc_session"]
    locale = data.get("locale", "ru")

    client = LeetCodeClient(session_cookie, csrf_token, locale)
    try:
        valid = await client.validate_cookies()
        if not valid:
            await client.close()
            await message.answer(i18n.get("onboarding.invalid_cookies"))
            await state.set_state(OnboardingStates.SESSION)
            await message.answer(i18n.get("onboarding.enter_session"))
            return

        username = await client.get_user_profile()
        await update_cookies(db_path, message.from_user.id, session_cookie, csrf_token)
        await update_user(db_path, message.from_user.id, lc_username=username)

        # Update shared lc_client
        old_client = services.get("lc_client")
        if old_client:
            await old_client.close()
        services["lc_client"] = client

        await message.answer(
            i18n.get("onboarding.cookies_valid", username=username)
        )
        await message.answer(
            i18n.get("onboarding.choose_lang"),
            reply_markup=language_keyboard(i18n),
        )
        await state.set_state(OnboardingStates.LANG)
    except CookieExpiredError:
        await client.close()
        await message.answer(i18n.get("onboarding.invalid_cookies"))
        await message.answer(i18n.get("onboarding.enter_session"))
        await state.set_state(OnboardingStates.SESSION)


@router.callback_query(OnboardingStates.LANG, LangCallback.filter())
async def on_lang(callback: CallbackQuery, callback_data: LangCallback, state: FSMContext, i18n: I18n, db_path: str):
    await update_user(db_path, callback.from_user.id, preferred_lang=callback_data.lang)
    await callback.message.edit_text(
        i18n.get("onboarding.choose_difficulty"),
        reply_markup=difficulty_keyboard(i18n),
    )
    await state.set_state(OnboardingStates.DIFFICULTY)
    await callback.answer()


@router.callback_query(OnboardingStates.DIFFICULTY, DifficultyCallback.filter())
async def on_difficulty(callback: CallbackQuery, callback_data: DifficultyCallback, state: FSMContext, i18n: I18n, db_path: str):
    difficulty = callback_data.difficulty
    fields = {"difficulty": difficulty}
    if difficulty == "Adaptive":
        fields["current_difficulty"] = "Easy"
    await update_user(db_path, callback.from_user.id, **fields)

    await state.update_data(selected_topics=[])
    await callback.message.edit_text(
        i18n.get("onboarding.choose_topics"),
        reply_markup=topics_keyboard(i18n, []),
    )
    await state.set_state(OnboardingStates.TOPICS)
    await callback.answer()


@router.callback_query(OnboardingStates.TOPICS, TopicCallback.filter())
async def on_topic(callback: CallbackQuery, callback_data: TopicCallback, state: FSMContext, i18n: I18n, db_path: str):
    data = await state.get_data()
    selected = data.get("selected_topics", [])

    if callback_data.action == "done":
        if not selected:
            await callback.answer("Выбери хотя бы одну тему" if i18n.locale == "ru" else "Select at least one topic")
            return

        topic_slugs = [TOPIC_SLUGS.get(t, t.lower()) for t in selected]
        await update_user(db_path, callback.from_user.id, topics=topic_slugs)

        await callback.message.edit_text(i18n.get("onboarding.done"))
        await state.clear()
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
