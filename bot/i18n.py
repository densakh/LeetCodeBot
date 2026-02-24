import json
import os


class I18n:
    _cache: dict[str, dict] = {}

    def __init__(self, locale: str = "ru"):
        self.locale = locale
        if locale not in self._cache:
            path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "locales", f"{locale}.json"
            )
            with open(path, "r", encoding="utf-8") as f:
                self._cache[locale] = json.load(f)
        self._data = self._cache[locale]

    def get(self, key: str, **kwargs) -> str:
        parts = key.split(".")
        value = self._data
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return key
        if isinstance(value, str) and kwargs:
            return value.format(**kwargs)
        return value if isinstance(value, str) else key
