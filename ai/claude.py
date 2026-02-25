import json as json_module
import logging
import re

from anthropic import AsyncAnthropic

from ai.base import BaseAIClient
from ai.prompts import (
    APPROACH_PROMPT,
    EXPLAIN_CODE_PROMPT,
    EXPLAIN_SOLUTION_PROMPT,
    HINT_WITH_CODE_PROMPT,
    IMPROVE_PROMPT,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

LOCALE_NAMES = {"ru": "Russian", "en": "English"}


class AIError(Exception):
    pass


class AIResponse:
    """Structured response from AI: either code or text."""
    def __init__(self, response_type: str, content: str):
        self.type = response_type  # "code" or "text"
        self.content = content

    @property
    def is_code(self) -> bool:
        return self.type == "code"


class ClaudeClient(BaseAIClient):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    def _locale_instruction(self, locale: str) -> str:
        name = LOCALE_NAMES.get(locale, "Russian")
        return f"Respond in {name}."

    def _strip_code_fences(self, text: str) -> str:
        text = text.strip()
        text = re.sub(r'^```\w*\n', '', text)
        text = re.sub(r'\n```$', '', text)
        return text.strip()

    async def _ask(
        self, prompt: str, max_tokens: int, system: str = SYSTEM_PROMPT,
        temperature: float = 1.0,
    ) -> str:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error("Claude API error: %s", e)
            reason = "overloaded" if "529" in str(e) or "overload" in str(e).lower() else str(e)
            raise AIError(reason) from e

    def _parse_ai_response(self, raw: str) -> AIResponse:
        """Parse JSON response from AI into AIResponse."""
        raw = self._strip_code_fences(raw).strip()
        try:
            data = json_module.loads(raw)
            resp_type = data.get("type", "text")
            content = data.get("content", "")
            if resp_type == "code":
                content = self._strip_code_fences(content)
            return AIResponse(resp_type, content)
        except (json_module.JSONDecodeError, AttributeError):
            # Fallback: if AI didn't return valid JSON, treat as text
            logger.warning("AI returned non-JSON response, treating as text")
            return AIResponse("text", raw)

    async def process_approach(
        self,
        problem: str,
        user_message: str,
        language: str,
        starter_code: str = "",
        current_code: str | None = None,
        locale: str = "ru",
    ) -> AIResponse:
        context = ""
        if current_code:
            context = f"Current code:\n```{language}\n{current_code}\n```\n\n"

        prompt = APPROACH_PROMPT.format(
            problem=problem,
            user_message=user_message,
            language=language,
            starter_code=starter_code,
            context=context,
            locale_instruction=self._locale_instruction(locale),
        )

        raw = await self._ask(prompt, max_tokens=4096)
        return self._parse_ai_response(raw)

    async def get_hint(
        self,
        problem: str,
        language: str,
        locale: str = "ru",
        current_code: str | None = None,
        failing_test: dict | None = None,
    ) -> str:
        prompt = HINT_WITH_CODE_PROMPT.format(
            problem=problem,
            language=language,
            current_code=current_code or "",
            input=failing_test.get("input", "") if failing_test else "",
            expected=failing_test.get("expected", "") if failing_test else "",
            output=failing_test.get("output", "") if failing_test else "",
            locale_instruction=self._locale_instruction(locale),
        )
        return await self._ask(prompt, max_tokens=2048)

    async def explain_code(
        self,
        code: str,
        language: str,
        locale: str = "ru",
    ) -> str:
        prompt = EXPLAIN_CODE_PROMPT.format(
            code=code,
            language=language,
            locale_instruction=self._locale_instruction(locale),
        )
        return await self._ask(prompt, max_tokens=2048)

    async def explain_solution(
        self,
        problem: str,
        code: str,
        language: str,
        locale: str = "ru",
    ) -> str:
        prompt = EXPLAIN_SOLUTION_PROMPT.format(
            problem=problem,
            code=code,
            language=language,
            locale_instruction=self._locale_instruction(locale),
        )
        return await self._ask(prompt, max_tokens=2048)

    async def suggest_improvement(
        self,
        problem: str,
        code: str,
        language: str,
        runtime_percentile: str = "",
        memory_percentile: str = "",
        locale: str = "ru",
    ) -> str:
        prompt = IMPROVE_PROMPT.format(
            problem=problem,
            code=code,
            language=language,
            runtime_percentile=runtime_percentile,
            memory_percentile=memory_percentile,
            locale_instruction=self._locale_instruction(locale),
        )
        return await self._ask(prompt, max_tokens=2048)
