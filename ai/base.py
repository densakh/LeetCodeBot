from abc import ABC, abstractmethod


class BaseAIClient(ABC):

    @abstractmethod
    async def process_approach(
        self,
        problem: str,
        user_message: str,
        language: str,
        starter_code: str = "",
        current_code: str | None = None,
        locale: str = "ru",
    ):
        """Process user message: return code or text response."""
        ...

    @abstractmethod
    async def get_hint(
        self,
        problem: str,
        language: str,
        locale: str = "ru",
        current_code: str | None = None,
        failing_test: dict | None = None,
    ) -> str:
        """Return a hint about what went wrong after WA."""
        ...

    @abstractmethod
    async def get_theory(
        self,
        problem: str,
        topic_tags: list[str],
        locale: str = "ru",
    ) -> str:
        """Return a theory reference based on problem and its topic tags."""
        ...

    @abstractmethod
    async def explain_code(
        self,
        code: str,
        language: str,
        locale: str = "ru",
    ) -> str:
        """Explain what the generated code does."""
        ...

    @abstractmethod
    async def explain_solution(
        self,
        problem: str,
        code: str,
        language: str,
        locale: str = "ru",
    ) -> str:
        """Post-Accepted review: why the approach works, time complexity, edge cases."""
        ...
