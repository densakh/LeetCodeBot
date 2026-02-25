import asyncio
import json
import logging

from patchright.async_api import async_playwright, Browser, BrowserContext, Playwright

logger = logging.getLogger(__name__)

LEETCODE_URL = "https://leetcode.com"


class PlaywrightSubmitter:
    """Handles LeetCode submit via patchright to bypass Cloudflare."""

    def __init__(self, session_cookie: str, csrf_token: str):
        self._session_cookie = session_cookie
        self._csrf_token = csrf_token
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=False,
        )
        self._context = await self._create_context()
        logger.info("Patchright browser started")

    async def _create_context(self) -> BrowserContext:
        context = await self._browser.new_context(
            locale="en-US",
            viewport={"width": 1920, "height": 1080},
        )
        await context.add_cookies([
            {
                "name": "LEETCODE_SESSION",
                "value": self._session_cookie,
                "domain": ".leetcode.com",
                "path": "/",
            },
            {
                "name": "csrftoken",
                "value": self._csrf_token,
                "domain": ".leetcode.com",
                "path": "/",
            },
        ])
        return context

    async def update_cookies(self, session_cookie: str, csrf_token: str) -> None:
        self._session_cookie = session_cookie
        self._csrf_token = csrf_token
        if self._context:
            await self._context.close()
        self._context = await self._create_context()
        logger.info("Patchright cookies updated")

    async def submit(
        self, slug: str, lang: str, code: str, question_id: str
    ) -> int:
        """Navigate to problem page first (establishes TLS state), then POST submit."""
        page = await self._context.new_page()
        try:
            return await self._do_submit(page, slug, lang, code, question_id)
        finally:
            await page.close()

    async def _do_submit(
        self, page, slug: str, lang: str, code: str, question_id: str
    ) -> int:
        problem_url = f"{LEETCODE_URL}/problems/{slug}/"
        submit_url = f"{LEETCODE_URL}/problems/{slug}/submit/"

        # If cf_clearance exists from a previous submit, try direct POST
        if await self._has_cf_clearance():
            csrf = await self._get_csrf_from_cookies()
            resp = await page.request.post(
                submit_url,
                headers={
                    "Content-Type": "application/json",
                    "x-csrftoken": csrf,
                    "Referer": problem_url,
                },
                data=json.dumps({
                    "lang": lang,
                    "question_id": question_id,
                    "typed_code": code,
                }),
            )
            if resp.ok:
                body = await resp.json()
                submission_id = body.get("submission_id")
                if submission_id:
                    logger.info("Submit OK via direct POST, submission_id=%s", submission_id)
                    return int(submission_id)
            logger.info("Direct POST failed (status=%d), will navigate", resp.status)

        # Navigate to the problem page — establishes browser TLS state with Cloudflare
        # Retry navigation: first attempt often gets ERR_EMPTY_RESPONSE,
        # but retries can succeed after Cloudflare warms up to the browser
        for nav_attempt in range(3):
            logger.info("Navigating to %s (attempt %d)", problem_url, nav_attempt)
            try:
                await page.goto(problem_url, wait_until="domcontentloaded", timeout=15000)
                logger.info("Navigation succeeded")
                break
            except Exception as e:
                logger.warning("page.goto attempt %d raised: %s", nav_attempt, e)
                await asyncio.sleep(5)

        # Try to solve Turnstile if present
        await self._solve_turnstile(page)

        # POST submit after navigation
        csrf = await self._get_csrf_from_cookies()
        resp = await page.request.post(
            submit_url,
            headers={
                "Content-Type": "application/json",
                "x-csrftoken": csrf,
                "Referer": problem_url,
            },
            data=json.dumps({
                "lang": lang,
                "question_id": question_id,
                "typed_code": code,
            }),
        )

        logger.info("POST after navigation: status=%d", resp.status)

        if resp.status == 403:
            body_text = await resp.text()
            logger.error("Submit 403 after navigation: %s", body_text[:500])
            from leetcode.client import CookieExpiredError
            raise CookieExpiredError("LeetCode cookies expired (Playwright submit)")

        if resp.status == 429 or resp.status >= 500:
            from leetcode.client import LeetCodeUnavailableError
            raise LeetCodeUnavailableError(
                f"Playwright submit returned {resp.status}"
            )

        body = await resp.json()
        submission_id = body.get("submission_id")
        if not submission_id:
            from leetcode.client import LeetCodeError
            raise LeetCodeError(f"No submission_id in response: {body}")

        logger.info("Submit OK via Playwright, submission_id=%s", submission_id)
        return int(submission_id)

    async def _solve_turnstile(self, page) -> None:
        """Find and click the Cloudflare Turnstile checkbox, then wait for cf_clearance."""
        await asyncio.sleep(2)

        # Check if Turnstile iframe exists at all
        iframe_found = False
        try:
            iframe = page.locator("iframe[src*='challenges.cloudflare.com']")
            iframe_found = await iframe.count() > 0
        except Exception:
            pass

        if not iframe_found:
            logger.info("No Turnstile iframe found, skipping challenge")
            return

        # Try to click the checkbox inside the iframe
        clicked = False
        for attempt in range(5):
            try:
                turnstile_frame = page.frame_locator(
                    "iframe[src*='challenges.cloudflare.com']"
                )
                checkbox = turnstile_frame.locator(
                    "label.cb-lb, input[type='checkbox'], .mark"
                )
                if await checkbox.count() > 0:
                    await checkbox.first.click()
                    logger.info("Clicked Turnstile checkbox (attempt %d)", attempt)
                    clicked = True
                    break
            except Exception as e:
                logger.debug("Turnstile click attempt %d: %s", attempt, e)
            await asyncio.sleep(1)

        if not clicked:
            # Fallback: click iframe by coordinates
            try:
                box = await iframe.first.bounding_box()
                if box:
                    await page.mouse.click(
                        box["x"] + 30,
                        box["y"] + box["height"] / 2,
                    )
                    logger.info("Clicked Turnstile iframe via coordinates")
                    clicked = True
            except Exception as e:
                logger.debug("Turnstile iframe click fallback: %s", e)

        if not clicked:
            logger.warning("Could not click Turnstile checkbox")
            return

        # Wait for cf_clearance only if we actually clicked something
        for i in range(10):
            if await self._has_cf_clearance():
                logger.info("cf_clearance obtained (%ds)", i * 2)
                return
            await asyncio.sleep(2)

        logger.warning("cf_clearance not found after click, trying submit anyway")

    async def _has_cf_clearance(self) -> bool:
        cookies = await self._context.cookies(LEETCODE_URL)
        return any(c["name"] == "cf_clearance" for c in cookies)

    async def _get_csrf_from_cookies(self) -> str:
        cookies = await self._context.cookies(LEETCODE_URL)
        for c in cookies:
            if c["name"] == "csrftoken":
                return c["value"]
        return self._csrf_token

    async def close(self) -> None:
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._pw:
            await self._pw.stop()
            self._pw = None
        logger.info("Patchright browser closed")
