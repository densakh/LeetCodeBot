import json
import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.i18n import I18n
from db.sessions import get_active_session, cancel_session, create_session, check_session_timeout
from db.users import get_user, get_solved_slugs
from leetcode.client import LeetCodeClient, CookieExpiredError, LeetCodeUnavailableError, LeetCodeError

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("daily"))
async def cmd_daily(message: Message, state: FSMContext, i18n: I18n, db_path: str, services: dict):
    user = await get_user(db_path, message.from_user.id)
    if not user or not user.get("lc_session"):
        await message.answer(i18n.get("onboarding.already_configured").replace("!", ".").split(".")[0] + ".")
        return

    await check_session_timeout(db_path, message.from_user.id)

    session = await get_active_session(db_path, message.from_user.id)
    if session:
        await cancel_session(db_path, session["id"])

    await message.answer(i18n.get("commands.daily_loading"))

    lc_client: LeetCodeClient = services["lc_client"]
    try:
        problem = await lc_client.get_daily_problem()
        await create_session(db_path, message.from_user.id, problem.title_slug)

        from bot.handlers.solve import start_solving
        await start_solving(message, state, problem, i18n, db_path)

    except CookieExpiredError:
        from bot.handlers.solve import _handle_cookie_expired
        await _handle_cookie_expired(message, state, i18n)
    except LeetCodeUnavailableError:
        await message.answer(i18n.get("errors.leetcode_unavailable"))
    except Exception as e:
        logger.exception("Error in /daily: %s", e)
        await message.answer(i18n.get("errors.unknown"))


@router.message(Command("random"))
async def cmd_random(message: Message, state: FSMContext, i18n: I18n, db_path: str, services: dict):
    user = await get_user(db_path, message.from_user.id)
    if not user or not user.get("lc_session"):
        await message.answer(i18n.get("errors.no_active_session"))
        return

    await check_session_timeout(db_path, message.from_user.id)

    session = await get_active_session(db_path, message.from_user.id)
    if session:
        await cancel_session(db_path, session["id"])

    await message.answer(i18n.get("commands.random_loading"))

    difficulty = user.get("difficulty")
    if difficulty == "Adaptive":
        difficulty = user.get("current_difficulty", "Easy")

    topics = json.loads(user.get("topics", "[]")) if user.get("topics") else []
    skip_slugs = await get_solved_slugs(db_path, message.from_user.id)

    lc_client: LeetCodeClient = services["lc_client"]
    logger.info("Random filters: difficulty=%s, topics=%s, skip_slugs=%d", difficulty, topics, len(skip_slugs))
    try:
        problem = await lc_client.get_random_problem(difficulty, topics, skip_slugs)
        if problem is None:
            await message.answer(i18n.get("errors.no_problems_available"))
            return

        await create_session(db_path, message.from_user.id, problem.title_slug)

        from bot.handlers.solve import start_solving
        await start_solving(message, state, problem, i18n, db_path)

    except CookieExpiredError:
        from bot.handlers.solve import _handle_cookie_expired
        await _handle_cookie_expired(message, state, i18n)
    except LeetCodeUnavailableError:
        await message.answer(i18n.get("errors.leetcode_unavailable"))
    except Exception as e:
        logger.exception("Error in /random: %s", e)
        await message.answer(i18n.get("errors.unknown"))


@router.message(Command("problem"))
async def cmd_problem(message: Message, state: FSMContext, command: CommandObject, i18n: I18n, db_path: str, services: dict):
    user = await get_user(db_path, message.from_user.id)
    if not user or not user.get("lc_session"):
        await message.answer(i18n.get("errors.no_active_session"))
        return

    slug = command.args
    if not slug:
        usage = "/problem <slug>\n\nExample: <code>/problem two-sum</code>"
        await message.answer(usage, parse_mode="HTML")
        return

    slug = slug.strip().lower()

    await check_session_timeout(db_path, message.from_user.id)

    session = await get_active_session(db_path, message.from_user.id)
    if session:
        await cancel_session(db_path, session["id"])

    loading = "⏳ Загружаю задачу..." if i18n.locale == "ru" else "⏳ Loading problem..."
    await message.answer(loading)

    lc_client: LeetCodeClient = services["lc_client"]
    try:
        problem = await lc_client.get_problem_detail(slug)
        await create_session(db_path, message.from_user.id, problem.title_slug)

        from bot.handlers.solve import start_solving
        await start_solving(message, state, problem, i18n, db_path)

    except CookieExpiredError:
        from bot.handlers.solve import _handle_cookie_expired
        await _handle_cookie_expired(message, state, i18n)
    except LeetCodeUnavailableError:
        await message.answer(i18n.get("errors.leetcode_unavailable"))
    except (LeetCodeError, Exception) as e:
        logger.exception("Error in /problem: %s", e)
        not_found = "Задача не найдена. Проверь slug." if i18n.locale == "ru" else "Problem not found. Check the slug."
        await message.answer(not_found)
