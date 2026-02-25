import asyncio
import logging
import random

import httpx

from leetcode.html_converter import convert_problem_html
from leetcode.playwright_submit import PlaywrightSubmitter
from leetcode.models import CodeSnippet, Problem, SubmissionResult

try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
from leetcode.queries import (
    GLOBAL_DATA_QUERY,
    PROBLEMSET_QUESTION_LIST_QUERY,
    QUESTION_DATA_QUERY,
    QUESTION_OF_TODAY_QUERY,
    SUBMISSION_DETAILS_QUERY,
)

logger = logging.getLogger(__name__)


class LeetCodeError(Exception):
    pass


class CookieExpiredError(LeetCodeError):
    pass


class LeetCodeUnavailableError(LeetCodeError):
    pass


class LeetCodeClient:
    BASE_URL = "https://leetcode.com"

    def __init__(self, session_cookie: str, csrf_token: str, locale: str = "ru"):
        self.locale = locale
        self._session_cookie = session_cookie
        self._csrf_token = csrf_token
        self._submitter: PlaywrightSubmitter | None = None
        cookies = f"LEETCODE_SESSION={session_cookie}; csrftoken={csrf_token}"
        self._client = httpx.AsyncClient(
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "x-csrftoken": csrf_token,
                "Referer": "https://leetcode.com/",
                "Cookie": cookies,
            },
            timeout=30.0,
            trust_env=False,
        )

    async def _graphql(self, query: str, variables: dict | None = None) -> dict:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        delays = [1, 2, 4]
        last_exc = None

        for attempt in range(3):
            try:
                resp = await self._client.post(
                    f"{self.BASE_URL}/graphql", json=payload
                )

                if resp.status_code == 403:
                    raise CookieExpiredError("LeetCode cookies expired")

                if resp.status_code == 400:
                    logger.error("LeetCode 400 Bad Request. Payload: %s, Response: %s", payload, resp.text)
                    raise LeetCodeError(f"Bad request: {resp.text}")

                if resp.status_code == 429 or resp.status_code >= 500:
                    if attempt < 2:
                        await asyncio.sleep(delays[attempt])
                        continue
                    raise LeetCodeUnavailableError(
                        f"LeetCode returned {resp.status_code}"
                    )

                resp.raise_for_status()
                data = resp.json()

                if "errors" in data:
                    raise LeetCodeError(str(data["errors"]))

                return data["data"]

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
                if attempt < 2:
                    await asyncio.sleep(delays[attempt])
                    continue
                raise LeetCodeUnavailableError(str(e)) from e
            except (CookieExpiredError, LeetCodeError):
                raise
            except Exception as e:
                last_exc = e
                if attempt < 2:
                    await asyncio.sleep(delays[attempt])
                    continue
                raise LeetCodeUnavailableError(str(e)) from e

        raise LeetCodeUnavailableError(str(last_exc))

    async def validate_cookies(self) -> bool:
        try:
            data = await self._graphql(GLOBAL_DATA_QUERY)
            return data["userStatus"]["isSignedIn"]
        except CookieExpiredError:
            return False

    async def get_user_profile(self) -> str:
        data = await self._graphql(GLOBAL_DATA_QUERY)
        return data["userStatus"]["username"]

    async def get_daily_problem(self) -> Problem:
        data = await self._graphql(QUESTION_OF_TODAY_QUERY)
        q = data["activeDailyCodingChallengeQuestion"]["question"]
        converted = convert_problem_html(q.get("content", ""), self.locale)
        return Problem(
            question_id=q["questionId"],
            frontend_id=q["questionFrontendId"],
            title=q["title"],
            title_slug=q["titleSlug"],
            difficulty=q["difficulty"],
            content=converted.text,
            topic_tags=[t["name"] for t in q.get("topicTags", [])],
            code_snippets=[
                CodeSnippet(lang=s["lang"], lang_slug=s["langSlug"], code=s["code"])
                for s in q.get("codeSnippets", [])
            ],
            image_urls=converted.image_urls,
        )

    async def get_problem_detail(self, title_slug: str) -> Problem:
        data = await self._graphql(
            QUESTION_DATA_QUERY, {"titleSlug": title_slug}
        )
        q = data["question"]
        converted = convert_problem_html(q.get("content", ""), self.locale)
        return Problem(
            question_id=q["questionId"],
            frontend_id=q["questionFrontendId"],
            title=q["title"],
            title_slug=q["titleSlug"],
            difficulty=q["difficulty"],
            content=converted.text,
            topic_tags=[t["name"] for t in q.get("topicTags", [])],
            code_snippets=[
                CodeSnippet(lang=s["lang"], lang_slug=s["langSlug"], code=s["code"])
                for s in q.get("codeSnippets", [])
            ],
            image_urls=converted.image_urls,
            sample_test_case=q.get("sampleTestCase", ""),
        )

    async def get_random_problem(
        self,
        difficulty: str | None,
        topics: list[str],
        skip_slugs: list[str],
    ) -> Problem | None:
        filters: dict = {}
        if difficulty:
            filters["difficulty"] = difficulty.upper()

        # LeetCode tags filter is AND — pick one random topic per attempt
        shuffled_topics = list(topics) if topics else []
        random.shuffle(shuffled_topics)

        for _ in range(5):
            if shuffled_topics:
                filters["tags"] = [shuffled_topics[_ % len(shuffled_topics)]]

            data = await self._graphql(
                PROBLEMSET_QUESTION_LIST_QUERY,
                {
                    "categorySlug": "algorithms",
                    "limit": 1,
                    "skip": 0,
                    "filters": filters,
                },
            )
            total = data["problemsetQuestionList"]["total"]
            if total == 0:
                continue

            offset = random.randint(0, total - 1)
            data = await self._graphql(
                PROBLEMSET_QUESTION_LIST_QUERY,
                {
                    "categorySlug": "algorithms",
                    "limit": 1,
                    "skip": offset,
                    "filters": filters,
                },
            )
            questions = data["problemsetQuestionList"]["questions"]
            if not questions:
                continue

            q = questions[0]
            if q["titleSlug"] in skip_slugs:
                continue
            if q.get("paidOnly"):
                continue

            return await self.get_problem_detail(q["titleSlug"])

        return None

    async def _ensure_submitter(self) -> PlaywrightSubmitter:
        if self._submitter is None:
            self._submitter = PlaywrightSubmitter(
                self._session_cookie, self._csrf_token
            )
            await self._submitter.start()
        return self._submitter

    async def _submit_curl_cffi(
        self, slug: str, lang: str, code: str, question_id: str
    ) -> int | None:
        """Try submit via curl_cffi with Firefox TLS fingerprint. Returns submission_id or None."""
        if not HAS_CURL_CFFI:
            return None

        submit_url = f"{self.BASE_URL}/problems/{slug}/submit/"
        problem_url = f"{self.BASE_URL}/problems/{slug}/"

        try:
            async with CurlAsyncSession(impersonate="firefox136") as session:
                resp = await session.post(
                    submit_url,
                    json={
                        "lang": lang,
                        "question_id": question_id,
                        "typed_code": code,
                    },
                    headers={
                        "x-csrftoken": self._csrf_token,
                        "Referer": problem_url,
                    },
                    cookies={
                        "LEETCODE_SESSION": self._session_cookie,
                        "csrftoken": self._csrf_token,
                    },
                )
                if resp.status_code == 200:
                    body = resp.json()
                    submission_id = body.get("submission_id")
                    if submission_id:
                        logger.info("Submit OK via curl_cffi, submission_id=%s", submission_id)
                        return int(submission_id)
                logger.info("curl_cffi submit failed (status=%d), falling back to Playwright", resp.status_code)
                return None
        except Exception as e:
            logger.warning("curl_cffi submit error: %s, falling back to Playwright", e)
            return None

    async def submit_solution(
        self, slug: str, lang: str, code: str, question_id: str
    ) -> int:
        # Try curl_cffi first (fast, no browser)
        result = await self._submit_curl_cffi(slug, lang, code, question_id)
        if result is not None:
            return result

        # Fallback to Playwright
        submitter = await self._ensure_submitter()
        delays = [2, 4]

        for attempt in range(2):
            try:
                return await submitter.submit(slug, lang, code, question_id)
            except CookieExpiredError:
                raise
            except LeetCodeError:
                if attempt == 0:
                    logger.warning("Playwright submit failed, retrying in %ds", delays[attempt])
                    await asyncio.sleep(delays[attempt])
                    continue
                raise

        raise LeetCodeUnavailableError("Submit failed after retries")

    async def check_submission(self, submission_id: int) -> SubmissionResult:
        data = await self._graphql(
            SUBMISSION_DETAILS_QUERY, {"submissionId": submission_id}
        )
        details = data["submissionDetails"]

        if details is None:
            return SubmissionResult(status_code=0, is_pending=True)

        status_code = details.get("statusCode")
        if status_code is None:
            return SubmissionResult(status_code=0, is_pending=True)

        return SubmissionResult(
            status_code=int(status_code),
            runtime_display=details.get("runtimeDisplay", ""),
            runtime_percentile=float(details.get("runtimePercentile") or 0),
            memory_display=details.get("memoryDisplay", ""),
            memory_percentile=float(details.get("memoryPercentile") or 0),
            total_correct=int(details.get("totalCorrect") or 0),
            total_testcases=int(details.get("totalTestcases") or 0),
            expected_output=details.get("expectedOutput", ""),
            code_output=details.get("codeOutput", ""),
            compile_error=details.get("compileError", ""),
            runtime_error=details.get("runtimeError", ""),
        )

    async def close(self) -> None:
        if self._submitter:
            await self._submitter.close()
            self._submitter = None
        await self._client.aclose()
