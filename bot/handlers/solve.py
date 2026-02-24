import asyncio
import json
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from ai.claude import ClaudeClient, AIError
from bot.i18n import I18n
from bot.keyboards import (
    LangCallback,
    SolveActionCallback,
    ResultActionCallback,
    CheckAgainCallback,
    LocaleCallback,
    language_keyboard,
    locale_keyboard,
    solve_review_keyboard,
    result_accepted_keyboard,
    result_wrong_keyboard,
    result_tle_keyboard,
    check_again_keyboard,
)
from bot.messages import (
    fmt_problem,
    fmt_code,
    fmt_accepted,
    fmt_wrong_answer,
    fmt_tle,
    fmt_runtime_error,
    md_code_to_html,
    split_message,
)
from config import COOKIE_INSTRUCTION_RU, COOKIE_INSTRUCTION_EN
from db.sessions import (
    get_active_session,
    update_session,
    cancel_session,
    skip_session,
    complete_session,
    check_session_timeout,
    create_session,
)
from db.users import (
    get_user,
    get_solved_slugs,
    add_solved_problem,
    update_adaptive_difficulty,
    update_cookies,
)
from leetcode.client import LeetCodeClient, CookieExpiredError, LeetCodeUnavailableError
from leetcode.models import Problem

logger = logging.getLogger(__name__)

router = Router()



class SolvingStates(StatesGroup):
    SHOW = State()
    LANG = State()
    APPROACH = State()
    REVIEW = State()
    EDIT = State()
    SUBMIT = State()
    RESULT = State()


class CookieExpiredStates(StatesGroup):
    SESSION = State()
    CSRF = State()


async def start_solving(message: Message, state: FSMContext, problem: Problem, i18n: I18n, db_path: str):
    user = await get_user(db_path, message.from_user.id)
    lang = user.get("preferred_lang", "python3") if user else "python3"

    text = fmt_problem(problem, i18n, lang_slug=lang)
    parts = split_message(text)
    for part in parts:
        await message.answer(part, parse_mode="HTML", disable_web_page_preview=True)

    for url in problem.image_urls:
        try:
            await message.answer_photo(url)
        except Exception as e:
            logger.warning("Failed to send image %s: %s", url, e)

    await state.update_data(
        problem_slug=problem.title_slug,
        problem_id=problem.question_id,
        problem_title=problem.title,
        problem_content=problem.content,
        problem_difficulty=problem.difficulty,
        problem_snippets=json.dumps(
            [{"lang": s.lang, "lang_slug": s.lang_slug, "code": s.code} for s in problem.code_snippets]
        ),
        language=lang,
    )

    session = await get_active_session(db_path, message.from_user.id)
    if session:
        await update_session(db_path, session["id"], language=lang)

    await message.answer(i18n.get("solve.describe_approach"))
    await state.set_state(SolvingStates.APPROACH)


@router.callback_query(SolvingStates.LANG, LangCallback.filter())
async def on_solve_lang(callback: CallbackQuery, callback_data: LangCallback, state: FSMContext, i18n: I18n, db_path: str):
    lang = callback_data.lang
    await state.update_data(language=lang)

    session = await get_active_session(db_path, callback.from_user.id)
    if session:
        await update_session(db_path, session["id"], language=lang)

    await callback.message.edit_text(i18n.get("solve.describe_approach"))
    await state.set_state(SolvingStates.APPROACH)
    await callback.answer()


@router.message(SolvingStates.APPROACH)
async def on_approach(message: Message, state: FSMContext, i18n: I18n, db_path: str, services: dict):
    text = message.text.strip()
    data = await state.get_data()
    ai_client: ClaudeClient = services["ai_client"]

    try:
        status_msg = await message.answer(i18n.get("solve.generating"))
        locale = data.get("locale", i18n.locale)
        current_code = data.get("current_code")
        lang = data.get("language", "python3")

        # Find starter code snippet for the user's language
        starter_code = ""
        snippets_raw = data.get("problem_snippets", "[]")
        try:
            snippets = json.loads(snippets_raw)
            snippet = next((s for s in snippets if s["lang_slug"] == lang), None)
            if snippet:
                starter_code = snippet["code"]
        except (json.JSONDecodeError, TypeError):
            pass

        ai_response = await ai_client.process_approach(
            problem=data["problem_content"],
            user_message=text,
            language=lang,
            starter_code=starter_code,
            current_code=current_code,
            locale=locale,
        )

        await status_msg.delete()

        if ai_response.is_code:
            code = ai_response.content
            await state.update_data(current_code=code, user_approach=text)

            session = await get_active_session(db_path, message.from_user.id)
            if session:
                await update_session(
                    db_path, session["id"],
                    user_approach=text,
                    current_code=code,
                )

            code_text = fmt_code(code, lang)
            for part in split_message(code_text):
                await message.answer(part, parse_mode="HTML")

            review_label = "Что делаем?" if i18n.locale == "ru" else "What next?"
            await message.answer(
                review_label,
                reply_markup=solve_review_keyboard(i18n),
            )
            await state.set_state(SolvingStates.REVIEW)
        else:
            # AI returned text (hint, explanation, clarification)
            response_html = md_code_to_html(ai_response.content)
            for part in split_message(response_html):
                await message.answer(part, parse_mode="HTML")
            # Stay in APPROACH

    except AIError:
        await message.answer(i18n.get("errors.ai_unavailable"))


@router.callback_query(SolvingStates.REVIEW, SolveActionCallback.filter())
async def on_solve_action(callback: CallbackQuery, callback_data: SolveActionCallback, state: FSMContext, i18n: I18n, db_path: str, services: dict):
    action = callback_data.action
    data = await state.get_data()
    ai_client: ClaudeClient = services["ai_client"]
    lc_client: LeetCodeClient = services["lc_client"]

    if action == "submit":
        await callback.message.edit_text(i18n.get("solve.submitting"))
        await state.set_state(SolvingStates.SUBMIT)

        try:
            submission_id = await lc_client.submit_solution(
                slug=data["problem_slug"],
                lang=data.get("language", "python3"),
                code=data["current_code"],
                question_id=data["problem_id"],
            )
            await state.update_data(submission_id=submission_id)
            await _poll_submission(callback.message, state, i18n, db_path, lc_client, submission_id)
        except CookieExpiredError:
            await _handle_cookie_expired(callback.message, state, i18n)
        except LeetCodeUnavailableError:
            await callback.message.answer(i18n.get("errors.leetcode_unavailable"))
            await state.set_state(SolvingStates.REVIEW)

    elif action == "edit":
        await callback.message.edit_text(i18n.get("solve.revision"))
        await state.set_state(SolvingStates.EDIT)

    elif action == "explain":
        try:
            locale = data.get("locale", i18n.locale)
            explanation = await ai_client.explain_code(
                code=data["current_code"],
                language=data.get("language", "python3"),
                locale=locale,
            )
            explanation_html = md_code_to_html(explanation)
            for part in split_message(explanation_html):
                await callback.message.answer(part, parse_mode="HTML")
        except AIError:
            await callback.message.answer(i18n.get("errors.ai_unavailable"))
        # Stay in REVIEW

    await callback.answer()


@router.message(SolvingStates.EDIT)
async def on_edit(message: Message, state: FSMContext, i18n: I18n, db_path: str, services: dict):
    text = message.text.strip()
    data = await state.get_data()
    ai_client: ClaudeClient = services["ai_client"]

    try:
        status_msg = await message.answer(i18n.get("solve.generating"))
        locale = data.get("locale", i18n.locale)
        lang = data.get("language", "python3")

        starter_code = ""
        snippets_raw = data.get("problem_snippets", "[]")
        try:
            snippets = json.loads(snippets_raw)
            snippet = next((s for s in snippets if s["lang_slug"] == lang), None)
            if snippet:
                starter_code = snippet["code"]
        except (json.JSONDecodeError, TypeError):
            pass

        ai_response = await ai_client.process_approach(
            problem=data["problem_content"],
            user_message=text,
            language=lang,
            starter_code=starter_code,
            current_code=data.get("current_code"),
            locale=locale,
        )

        await status_msg.delete()

        if ai_response.is_code:
            code = ai_response.content
            await state.update_data(current_code=code)

            session = await get_active_session(db_path, message.from_user.id)
            if session:
                iteration = session.get("iteration", 0) + 1
                await update_session(
                    db_path, session["id"],
                    current_code=code,
                    iteration=iteration,
                )

            code_text = fmt_code(code, lang)
            for part in split_message(code_text):
                await message.answer(part, parse_mode="HTML")

            review_label = "Что делаем?" if i18n.locale == "ru" else "What next?"
            await message.answer(
                review_label,
                reply_markup=solve_review_keyboard(i18n),
            )
            await state.set_state(SolvingStates.REVIEW)
        else:
            response_html = md_code_to_html(ai_response.content)
            for part in split_message(response_html):
                await message.answer(part, parse_mode="HTML")
            # Stay in EDIT

    except AIError:
        await message.answer(i18n.get("errors.ai_unavailable"))


async def _poll_submission(
    message: Message,
    state: FSMContext,
    i18n: I18n,
    db_path: str,
    lc_client: LeetCodeClient,
    submission_id: int,
):
    for _ in range(10):
        await asyncio.sleep(2)
        try:
            result = await lc_client.check_submission(submission_id)
        except CookieExpiredError:
            await _handle_cookie_expired(message, state, i18n)
            return
        except LeetCodeUnavailableError:
            continue

        if result.is_pending:
            continue

        data = await state.get_data()
        telegram_id = message.chat.id

        if result.status_code == 10:  # Accepted
            await message.answer(
                fmt_accepted(result, i18n),
                reply_markup=result_accepted_keyboard(i18n),
                parse_mode="HTML",
            )
            session = await get_active_session(db_path, telegram_id)
            if session:
                await complete_session(db_path, session["id"])
                await add_solved_problem(
                    db_path, telegram_id,
                    problem_slug=data["problem_slug"],
                    problem_id=int(data["problem_id"]),
                    difficulty=data.get("problem_difficulty", ""),
                    result="accepted",
                    attempts=session.get("iteration", 0) + 1,
                )
            await update_adaptive_difficulty(db_path, telegram_id, accepted=True)
            await state.set_state(SolvingStates.RESULT)
            await state.update_data(last_result_code=10, submission_result={
                "expected": result.expected_output,
                "output": result.code_output,
                "runtime_percentile": f"{result.runtime_percentile:.1f}",
                "memory_percentile": f"{result.memory_percentile:.1f}",
            })

        elif result.status_code == 11:  # Wrong Answer
            await message.answer(
                fmt_wrong_answer(result, i18n),
                reply_markup=result_wrong_keyboard(i18n),
                parse_mode="HTML",
            )
            await update_adaptive_difficulty(db_path, telegram_id, accepted=False)
            await state.set_state(SolvingStates.RESULT)
            await state.update_data(last_result_code=11, submission_result={
                "expected": result.expected_output,
                "output": result.code_output,
            })

        elif result.status_code == 14:  # TLE
            await message.answer(
                fmt_tle(result, i18n),
                reply_markup=result_tle_keyboard(i18n),
                parse_mode="HTML",
            )
            await update_adaptive_difficulty(db_path, telegram_id, accepted=False)
            await state.set_state(SolvingStates.RESULT)
            await state.update_data(last_result_code=14)

        elif result.status_code == 15:  # Runtime Error
            await message.answer(
                fmt_runtime_error(result, i18n),
                reply_markup=result_tle_keyboard(i18n),
                parse_mode="HTML",
            )
            await update_adaptive_difficulty(db_path, telegram_id, accepted=False)
            await state.set_state(SolvingStates.RESULT)
            await state.update_data(last_result_code=15)

        return

    # Timeout - result not ready after 10 attempts
    await message.answer(
        i18n.get("solve.timeout_polling"),
        reply_markup=check_again_keyboard(i18n),
    )


@router.callback_query(SolvingStates.SUBMIT, CheckAgainCallback.filter())
async def on_check_again(callback: CallbackQuery, state: FSMContext, i18n: I18n, db_path: str, services: dict):
    data = await state.get_data()
    submission_id = data.get("submission_id")
    lc_client: LeetCodeClient = services["lc_client"]

    await callback.message.edit_text(i18n.get("solve.submitting"))
    await _poll_submission(callback.message, state, i18n, db_path, lc_client, submission_id)
    await callback.answer()


@router.callback_query(SolvingStates.RESULT, ResultActionCallback.filter())
async def on_result_action(callback: CallbackQuery, callback_data: ResultActionCallback, state: FSMContext, i18n: I18n, db_path: str, services: dict):
    action = callback_data.action
    data = await state.get_data()
    ai_client: ClaudeClient = services["ai_client"]
    lc_client: LeetCodeClient = services["lc_client"]

    if action == "next":
        user = await get_user(db_path, callback.from_user.id)
        if not user:
            return

        difficulty = user.get("difficulty")
        if difficulty == "Adaptive":
            difficulty = user.get("current_difficulty", "Easy")

        topics = json.loads(user.get("topics", "[]")) if user.get("topics") else []
        skip_slugs = await get_solved_slugs(db_path, callback.from_user.id)

        try:
            problem = await lc_client.get_random_problem(difficulty, topics, skip_slugs)
            if problem is None:
                await callback.message.answer(i18n.get("errors.no_problems_available"))
                await callback.answer()
                return

            session = await get_active_session(db_path, callback.from_user.id)
            if session:
                await cancel_session(db_path, session["id"])

            await create_session(db_path, callback.from_user.id, problem.title_slug)
            await start_solving(callback.message, state, problem, i18n, db_path)
        except CookieExpiredError:
            await _handle_cookie_expired(callback.message, state, i18n)
        except LeetCodeUnavailableError:
            await callback.message.answer(i18n.get("errors.leetcode_unavailable"))

    elif action == "review":
        try:
            locale = data.get("locale", i18n.locale)
            explanation = await ai_client.explain_solution(
                problem=data["problem_content"],
                code=data["current_code"],
                language=data.get("language", "python3"),
                locale=locale,
            )
            explanation_html = md_code_to_html(explanation)
            for part in split_message(explanation_html):
                await callback.message.answer(part, parse_mode="HTML")
        except AIError:
            await callback.message.answer(i18n.get("errors.ai_unavailable"))

    elif action == "hint":
        try:
            locale = data.get("locale", i18n.locale)
            submission_result = data.get("submission_result", {})
            hint = await ai_client.get_hint(
                problem=data["problem_content"],
                language=data.get("language", "python3"),
                locale=locale,
                current_code=data.get("current_code"),
                failing_test=submission_result if submission_result else None,
            )
            hint_html = md_code_to_html(hint)
            for part in split_message(hint_html):
                await callback.message.answer(part, parse_mode="HTML")
        except AIError:
            await callback.message.answer(i18n.get("errors.ai_unavailable"))

    elif action == "improve":
        try:
            locale = data.get("locale", i18n.locale)
            submission_result = data.get("submission_result", {})
            suggestion = await ai_client.suggest_improvement(
                problem=data["problem_content"],
                code=data["current_code"],
                language=data.get("language", "python3"),
                runtime_percentile=submission_result.get("runtime_percentile", ""),
                memory_percentile=submission_result.get("memory_percentile", ""),
                locale=locale,
            )
            suggestion_html = md_code_to_html(suggestion)
            for part in split_message(suggestion_html):
                await callback.message.answer(part, parse_mode="HTML")
            # Stay in RESULT — user clicks "Revise" when ready to implement
        except AIError:
            await callback.message.answer(i18n.get("errors.ai_unavailable"))

    elif action == "revise":
        await callback.message.answer(i18n.get("solve.describe_approach"))
        await state.set_state(SolvingStates.APPROACH)

    await callback.answer()


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, i18n: I18n, db_path: str):
    session = await get_active_session(db_path, message.from_user.id)
    if session:
        await cancel_session(db_path, session["id"])
    await state.clear()
    await message.answer(i18n.get("commands.cancel"))


@router.message(Command("skip"))
async def cmd_skip(message: Message, state: FSMContext, i18n: I18n, db_path: str, services: dict):
    session = await get_active_session(db_path, message.from_user.id)
    if not session:
        await message.answer(i18n.get("errors.no_active_session"))
        return

    await skip_session(db_path, session["id"])
    await message.answer(i18n.get("commands.skip"))

    lc_client: LeetCodeClient = services["lc_client"]
    user = await get_user(db_path, message.from_user.id)
    if not user:
        return

    difficulty = user.get("difficulty")
    if difficulty == "Adaptive":
        difficulty = user.get("current_difficulty", "Easy")

    topics = json.loads(user.get("topics", "[]")) if user.get("topics") else []
    skip_slugs = await get_solved_slugs(db_path, message.from_user.id)

    try:
        problem = await lc_client.get_random_problem(difficulty, topics, skip_slugs)
        if problem is None:
            await message.answer(i18n.get("errors.no_problems_available"))
            return

        await create_session(db_path, message.from_user.id, problem.title_slug)
        await start_solving(message, state, problem, i18n, db_path)
    except CookieExpiredError:
        await _handle_cookie_expired(message, state, i18n)
    except LeetCodeUnavailableError:
        await message.answer(i18n.get("errors.leetcode_unavailable"))


async def _handle_cookie_expired(message: Message, state: FSMContext, i18n: I18n):
    current_state = await state.get_state()
    data = await state.get_data()
    await state.update_data(
        suspended_state=current_state,
        suspended_problem=data.get("problem_slug"),
        suspended_code=data.get("current_code"),
    )

    await message.answer(i18n.get("cookie.expired"))
    locale = data.get("locale", i18n.locale)
    cookie_instruction = COOKIE_INSTRUCTION_RU if locale == "ru" else COOKIE_INSTRUCTION_EN
    await message.answer(cookie_instruction, parse_mode="HTML")
    await state.set_state(CookieExpiredStates.SESSION)


@router.message(CookieExpiredStates.SESSION)
async def on_cookie_session(message: Message, state: FSMContext, i18n: I18n):
    session_cookie = message.text.strip()
    await state.update_data(new_lc_session=session_cookie)
    await message.answer(i18n.get("onboarding.enter_csrf"))
    await state.set_state(CookieExpiredStates.CSRF)


@router.message(CookieExpiredStates.CSRF)
async def on_cookie_csrf(message: Message, state: FSMContext, i18n: I18n, db_path: str, services: dict):
    csrf_token = message.text.strip()
    data = await state.get_data()
    session_cookie = data["new_lc_session"]
    locale = data.get("locale", i18n.locale)

    client = LeetCodeClient(session_cookie, csrf_token, locale)
    try:
        valid = await client.validate_cookies()
        if not valid:
            await message.answer(i18n.get("onboarding.invalid_cookies"))
            await state.set_state(CookieExpiredStates.SESSION)
            return

        username = await client.get_user_profile()
        await update_cookies(db_path, message.from_user.id, session_cookie, csrf_token)

        # Update shared lc_client
        old_client = services.get("lc_client")
        if old_client:
            await old_client.close()
        services["lc_client"] = client

        await message.answer(
            i18n.get("onboarding.cookies_valid", username=username)
        )

        # Restore suspended state
        suspended_state = data.get("suspended_state")
        if suspended_state:
            await state.set_state(suspended_state)
            await message.answer(i18n.get("solve.describe_approach"))
        else:
            await state.clear()

    except CookieExpiredError:
        await message.answer(i18n.get("onboarding.invalid_cookies"))
        await state.set_state(CookieExpiredStates.SESSION)
