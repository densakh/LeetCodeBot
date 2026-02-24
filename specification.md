# ТЗ: LeetCode Telegram Bot

## Общее описание

Персональный Telegram-бот для решения задач LeetCode без написания кода вручную. Пользователь описывает алгоритм на естественном языке, ИИ генерирует реализацию, бот отправляет её на проверку и возвращает результат.

---

## Стек

- Python 3.11+
- aiogram 3
- httpx (async)
- Anthropic Claude API
- SQLite + aiosqlite
- APScheduler
- python-dotenv
- beautifulsoup4 + lxml

---

## Структура проекта

```
leetcode-bot/
├── bot/
│   ├── handlers/
│   │   ├── start.py        # онбординг
│   │   ├── solve.py        # основной флоу решения
│   │   ├── daily.py        # /daily
│   │   ├── stats.py        # /stats
│   │   └── settings.py     # /settings
│   ├── keyboards.py        # все инлайн клавиатуры
│   ├── messages.py         # все шаблоны сообщений
│   ├── middlewares.py      # проверка ALLOWED_TELEGRAM_ID
│   ├── i18n.py             # загрузка и доступ к локализации
│   └── scheduler.py        # напоминания об обновлении куки
│
├── locales/
│   ├── ru.json
│   └── en.json
│
├── leetcode/
│   ├── client.py           # GraphQL запросы к leetcode.com
│   ├── queries.py          # все GraphQL query/mutation строки
│   ├── models.py           # датаклассы: Problem, Submission, TestResult
│   └── html_converter.py   # конвертация HTML условий в Telegram HTML
│
├── ai/
│   ├── base.py             # абстрактный базовый класс
│   ├── claude.py           # реализация под Claude
│   └── prompts.py          # системные промпты
│
├── db/
│   ├── database.py         # инициализация, соединение
│   ├── users.py            # CRUD пользователей
│   └── sessions.py         # CRUD сессий решения
│
├── config.py               # env переменные + инструкция по куки
├── main.py
├── requirements.txt        # генерируется через pip freeze после установки
├── .env.example            # шаблон переменных окружения
├── deploy.sh               # скрипт деплоя
└── README.md
```

---

## Переменные окружения

`.env.example` — шаблон, из которого `deploy.sh` создаёт `.env`:

```bash
BOT_TOKEN=                  # токен Telegram бота
ANTHROPIC_API_KEY=          # ключ Claude API
ALLOWED_TELEGRAM_ID=        # твой telegram_id, только он получит доступ
LOG_LEVEL=INFO              # уровень логирования (DEBUG / INFO / WARNING)
```

`.env` создаётся с правами `600`. Middleware проверяет `ALLOWED_TELEGRAM_ID` на каждый апдейт — все остальные игнорируются.

---

## Функциональные требования

### Онбординг `/start`

При первом запуске бот последовательно запрашивает:

1. Язык интерфейса — кнопки: 🇷🇺 Русский, 🇬🇧 English. По умолчанию русский
2. `LEETCODE_SESSION` cookie — пользователь вставляет текстом
3. `csrftoken` cookie — пользователь вставляет текстом
4. Валидация куки — бот делает GraphQL запрос `globalData` к LeetCode. Если возвращается username — куки валидны, username сохраняется в `users.lc_username`. Если 403 — просит повторить с шага 2
5. Язык решений — инлайн кнопки: Python, Kotlin, Java, C++
6. Сложность — инлайн кнопки: Easy, Medium, Hard, Адаптивная
7. Темы — мультиселект с кнопками, минимум 1 тема обязательна: Arrays, Strings, Linked List, Trees, Graphs, DP, Backtracking, Binary Search, Greedy, Hash Table, Stack/Queue, Math

После онбординга все данные сохраняются в БД.

**Повторный `/start`**: если пользователь уже прошёл онбординг — бот отвечает: "Ты уже настроен! Используй /settings для изменения настроек, /daily или /random для задач." Онбординг не перезапускается.

---

### Команды

**`/daily`**
Получает задачу дня с LeetCode. Показывает название, сложность, условие, примеры. Запускает флоу решения.

**`/random`**
Выбирает случайную задачу с учётом фильтров пользователя (темы + сложность). Использует GraphQL API LeetCode (`problemsetQuestionList`) с серверной фильтрацией по difficulty и tags. Запрашивает `totalNum` из ответа и выбирает случайный offset. Исключает уже решённые задачи по локальной БД `solved_problems` (задачи, решённые вне бота, не исключаются). Если все задачи по фильтрам исчерпаны — сообщение `errors.no_problems_available` с предложением расширить фильтры в `/settings`. Запускает флоу решения.

**`/settings`**
Показывает текущие настройки. Позволяет изменить язык интерфейса, язык решений, сложность, темы, обновить куки. Переиспользует те же хендлеры и клавиатуры что и онбординг.

**`/stats`**
Показывает статистику: сколько задач решено, разбивка по сложностям, streak (дней подряд по UTC), любимые темы. Streak считается по UTC-дням из `solved_problems.solved_at`.

**`/skip`**
Пропускает текущую задачу и сразу загружает следующую с учётом тех же фильтров (сложность + темы). Доступна только при активной сессии решения. Если вызвана вне сессии — бот отвечает локализованным сообщением `errors.no_active_session`. Пропущенные задачи не считаются решёнными, не влияют на streak и адаптивную сложность, могут выпасть повторно при `/random`.

**`/cancel`**
Отменяет текущую сессию решения, сбрасывает FSM в `IDLE`.

Отличие `/skip` от `/cancel`:

| Действие   | Текущая сессия         | Что дальше               |
|------------|------------------------|--------------------------|
| `/cancel`  | Статус → `cancelled`   | Возврат в главное меню   |
| `/skip`    | Статус → `skipped`     | Сразу новая задача       |

---

### Флоу решения задачи

```
1. Показ задачи
   → название, сложность, теги, условие, примеры
   → картинки из условия отправляются отдельными сообщениями

2. Выбор языка
   → инлайн кнопки (текущий язык выделен по умолчанию)

3. Запрос подхода
   → "Опиши своё решение"
   → если пользователь пишет "не знаю" / "подскажи" / "hint"
     → бот даёт наводящий вопрос, не алгоритм

4. Генерация кода
   → AI-клиент получает: условие задачи + подход пользователя + язык
   → реализует ТОЛЬКО описанный подход
   → бот показывает код в code block

5. Подтверждение
   → кнопки: [Сабмитить ✅] [Изменить 🔄] [Объяснить код 💬]
   → "Изменить" → пользователь описывает правки → новая генерация
   → iteration++ в сессии

6. Сабмит
   → отправка на LeetCode через GraphQL
   → polling результата (раз в 2 сек, до 10 попыток)
   → показ результата
   → если после 10 попыток результат не получен — сообщение
     "Результат ещё не готов" с кнопкой [Проверить снова 🔄],
     состояние остаётся SOLVING_SUBMIT, кнопка запускает ещё 10 попыток

7. Результат
   → Accepted: runtime, memory, percentiles
     кнопки: [Следующая 🎲] [Разбор 📖]
     "Разбор" — AI объясняет почему подход работает, временную сложность, edge cases
   → Wrong Answer: failing test case
     кнопки: [Подсказка 💡] [Пересмотреть 🔄]
     "Подсказка" — AI получает код + failing test и даёт конкретную подсказку по ошибке
   → Time Limit / Runtime Error: пояснение что пошло не так
     кнопка: [Пересмотреть 🔄]
```

---

### Обновление куки

- В `users` хранится `cookies_updated` timestamp
- APScheduler проверяет раз в день: если `cookies_updated` > 5 дней назад — присылает напоминание с инструкцией
- При любом 403 от LeetCode — немедленный запрос обновить куки, текущая сессия сохраняется и возобновляется после обновления
- Инструкция по получению куки хранится в `config.py`, показывается по запросу

---

### Адаптивная сложность

Если выбран режим "Адаптивная":
- Старт с Easy
- 3 Accepted подряд → переход на Medium
- 3 Accepted подряд на Medium → переход на Hard
- 2 WA/TLE подряд → возврат на уровень ниже (с Easy — остаёмся на Easy)
- Текущий уровень хранится в `users.current_difficulty`
- `consecutive_solved` — глобальный счётчик, не привязан к сессии
- `/cancel` и `/skip` не сбрасывают `consecutive_solved`
- WA/TLE сбрасывает `consecutive_solved` в 0 и инкрементирует `consecutive_failed`
- Accepted сбрасывает `consecutive_failed` в 0

В таблице `users` добавляется поле `consecutive_failed INTEGER DEFAULT 0`.

---

## Конвертер HTML условий задач

### Проблема

Условия задач LeetCode приходят в сыром HTML, содержащем теги, которые Telegram не поддерживает. Telegram допускает только: `<b>`, `<i>`, `<u>`, `<s>`, `<code>`, `<pre>`, `<a>`, `<blockquote>`. Всё остальное — `<p>`, `<ul>`, `<li>`, `<div>`, `<sup>`, `<sub>`, `<table>`, `<img>`, `<strong>`, `<em>` — вызовет ошибку `Bad Request: can't parse entities`.

### Типичный HTML от LeetCode

```html
<p>Given an array of integers <code>nums</code> and an integer <code>target</code>,
return <em>indices of the two numbers such that they add up to
<code>target</code></em>.</p>

<p>You may assume that each input would have
<strong>exactly one solution</strong>.</p>

<ul>
  <li>2 ≤ nums.length ≤ 10<sup>4</sup></li>
  <li>-10<sup>9</sup> ≤ nums[i] ≤ 10<sup>9</sup></li>
</ul>

<p><img src="https://assets.leetcode.com/uploads/2021/tree.jpg" /></p>

<table>
  <tr><th>Input</th><th>Output</th></tr>
  <tr><td>[2,7,11]</td><td>[0,1]</td></tr>
</table>

<pre>
Input: nums = [2,7,11,15], target = 9
Output: [0,1]
</pre>
```

### Модуль `leetcode/html_converter.py`

Зависимость: `beautifulsoup4` + `lxml`.

Функция `convert_problem_html(raw_html: str) -> ConvertedProblem`:

```python
@dataclass
class ConvertedProblem:
    text: str            # условие в Telegram HTML
    image_urls: list[str] # URL картинок для отправки отдельными сообщениями
```

### Правила конвертации

| HTML от LeetCode          | Telegram HTML                          |
|---------------------------|----------------------------------------|
| `<p>текст</p>`           | `текст\n\n`                            |
| `<strong>`, `<b>`        | `<b>текст</b>`                         |
| `<em>`, `<i>`            | `<i>текст</i>`                         |
| `<code>`                 | `<code>текст</code>`                   |
| `<pre>`                  | `<pre>текст</pre>`                     |
| `<a href="...">`         | `<a href="...">текст</a>`             |
| `<ul>/<li>`              | `• текст\n` (символ `•`, не тег)       |
| `<ol>/<li>`              | `1. текст\n` (с инкрементом)           |
| `<sup>`                  | Unicode суперскрипт (см. маппинг ниже) |
| `<sub>`                  | Unicode сабскрипт                      |
| `<table>`                | моноширинный текст в `<pre>`           |
| `<img src="url">`        | URL сохраняется в `image_urls`         |
| `<br>`, `<br/>`          | `\n`                                   |
| `<div>`                  | `\n` + inner text                      |
| `<blockquote>`           | `<blockquote>текст</blockquote>`       |
| Любой другой тег         | inner text (тег удаляется)             |

### Маппинг суперскриптов и сабскриптов

```python
SUPERSCRIPT_MAP = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
    'n': 'ⁿ', 'i': 'ⁱ',
}

SUBSCRIPT_MAP = {
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
    '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
    '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
}
```

Символы без маппинга остаются как есть.

### Конвертация таблиц

Таблицы форматируются моноширинным текстом с выравниванием по колонкам:

```
Вход из LeetCode:
<table>
  <tr><th>Input</th><th>Output</th></tr>
  <tr><td>[2,7,11]</td><td>[0,1]</td></tr>
  <tr><td>[3,2,4]</td><td>[1,2]</td></tr>
</table>

Результат в Telegram:
<pre>
Input     Output
[2,7,11]  [0,1]
[3,2,4]   [1,2]
</pre>
```

Ширина каждой колонки — максимальная длина значения в этой колонке + 2 символа padding.

### Обработка картинок

Картинки нельзя встроить в текстовое сообщение Telegram. Стратегия:

1. Все `<img src="...">` извлекаются в `image_urls`
2. В тексте вместо картинки вставляется `[📎 изображение]` / `[📎 image]` (локализовано)
3. После отправки текста условия бот отправляет каждую картинку отдельным сообщением через `send_photo(url)`
4. LeetCode хостит картинки на публичном CDN (`assets.leetcode.com`) — прямые URL работают

### Постобработка

После конвертации:
- Удаляются множественные пустые строки (3+ `\n` → 2 `\n`)
- Удаляются пробелы в начале/конце
- Спецсимволы HTML (`&amp;`, `&lt;`, `&gt;`, `&nbsp;`, `&quot;`) декодируются, затем динамический контент экранируется через `escape_html()`

### Важно

Конвертер вызывается в `leetcode/client.py` сразу при получении задачи. Хендлеры работают только с уже конвертированным `ConvertedProblem`, никогда с сырым HTML.

---

## Диаграмма состояний FSM

### Состояния

```
IDLE                    — нет активной сессии
ONBOARDING_LOCALE       — выбор языка интерфейса
ONBOARDING_SESSION      — ввод LEETCODE_SESSION cookie
ONBOARDING_CSRF         — ввод csrftoken cookie
ONBOARDING_LANG         — выбор языка решений
ONBOARDING_DIFFICULTY   — выбор сложности
ONBOARDING_TOPICS       — выбор тем

SOLVING_SHOW            — условие задачи показано
SOLVING_LANG            — выбор языка для этой задачи
SOLVING_APPROACH        — ожидание описания подхода
SOLVING_REVIEW          — код сгенерирован, ожидание действия
SOLVING_EDIT            — ожидание описания правок
SOLVING_SUBMIT          — отправка на LeetCode, polling
SOLVING_RESULT          — результат показан, ожидание действия

SETTINGS_MENU           — меню настроек
SETTINGS_COOKIES        — обновление куки (SESSION)
SETTINGS_CSRF           — обновление куки (CSRF)

COOKIE_EXPIRED          — куки невалидны, сессия приостановлена
COOKIE_EXPIRED_CSRF     — ввод CSRF после обновления SESSION
```

### Диаграмма переходов

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              ОНБОРДИНГ                                  │
│                                                                         │
│  /start ──▶ ONBOARDING_LOCALE                                          │
│                  │                                                       │
│                  │ кнопка RU/EN                                          │
│                  ▼                                                       │
│             ONBOARDING_SESSION                                          │
│                  │                                                       │
│                  │ текст (cookie)                                        │
│                  ▼                                                       │
│             ONBOARDING_CSRF                                             │
│                  │                                                       │
│                  │ текст (cookie)                                        │
│                  ├── валидация OK ──▶ ONBOARDING_LANG                   │
│                  └── 403 ──▶ ONBOARDING_SESSION (повтор)                │
│                                          │                               │
│                                          │ кнопка языка                  │
│                                          ▼                               │
│                                    ONBOARDING_DIFFICULTY                 │
│                                          │                               │
│                                          │ кнопка сложности              │
│                                          ▼                               │
│                                    ONBOARDING_TOPICS                    │
│                                          │                               │
│                                          │ кнопка "Готово" (≥1 тема)     │
│                                          ▼                               │
│                                        IDLE                             │
└─────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                           ФЛОУ РЕШЕНИЯ                                  │
│                                                                         │
│  /daily, /random ──▶ SOLVING_SHOW                                      │
│                          │                                               │
│                          │ (автоматически)                               │
│                          ▼                                               │
│                     SOLVING_LANG                                        │
│                          │                                               │
│                          │ кнопка языка                                  │
│                          ▼                                               │
│                     SOLVING_APPROACH                                    │
│                          │                                               │
│                          ├── текст подхода ──▶ [AI генерация]           │
│                          │                          │                    │
│                          │                          ▼                    │
│                          │                     SOLVING_REVIEW            │
│                          │                          │                    │
│                          │              ┌───────────┼───────────┐        │
│                          │              │           │           │        │
│                          │          [Сабмит ✅] [Изменить 🔄] [Объяснить 💬]
│                          │              │           │           │        │
│                          │              │           │       AI ответ,    │
│                          │              │           │       остаёмся в   │
│                          │              │           │       SOLVING_REVIEW
│                          │              │           ▼                    │
│                          │              │     SOLVING_EDIT               │
│                          │              │           │                    │
│                          │              │           │ текст правок       │
│                          │              │           │                    │
│                          │              │           ▼                    │
│                          │              │     [AI генерация]             │
│                          │              │     iteration++                │
│                          │              │           │                    │
│                          │              │           └──▶ SOLVING_REVIEW  │
│                          │              ▼                                │
│                          │        SOLVING_SUBMIT                        │
│                          │              │                                │
│                          │              │ polling (2s × 10)              │
│                          │              ▼                                │
│                          │        SOLVING_RESULT                        │
│                          │              │                                │
│                          │    ┌─────────┼──────────────┐                │
│                          │    │         │              │                 │
│                          │ Accepted   WA/TLE      Timeout               │
│                          │    │         │          polling               │
│                          │    │         │              │                 │
│                          │    │         │        [Проверить снова🔄]     │
│                          │    │         │        остаёмся в              │
│                          │    │         │        SOLVING_SUBMIT          │
│                          │    │         │                                │
│                          │ [Следующая🎲] [Подсказка💡]                  │
│                          │ [Разбор 📖] [Пересмотреть🔄]                │
│                          │    │         │              │                 │
│                          │    │    ┌────┘              │                 │
│                          │    │    │                   │                 │
│                          │    │  [Подсказка💡]──▶ AI hint,              │
│                          │    │    │           остаёмся в               │
│                          │    │    │           SOLVING_RESULT            │
│                          │    │    │                                     │
│                          │    │  [Пересмотреть🔄]──▶ SOLVING_APPROACH   │
│                          │    │                                         │
│                          │    ├── [Следующая 🎲] ──▶ SOLVING_SHOW      │
│                          │    │                      (новая задача)      │
│                          │    └── [Разбор 📖] ──▶ AI объяснение,       │
│                          │                        остаёмся в            │
│                          │                        SOLVING_RESULT        │
│                          │                                              │
│                          └── "не знаю"/"hint" ──▶ AI hint,             │
│                                                   остаёмся в            │
│                                                   SOLVING_APPROACH      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                     ГЛОБАЛЬНЫЕ ПЕРЕХОДЫ                                 │
│                                                                         │
│  Из ЛЮБОГО состояния кроме ONBOARDING_*:                               │
│                                                                         │
│    /cancel ──▶ IDLE                                                    │
│        сессия → cancelled                                               │
│                                                                         │
│    /skip ──▶ SOLVING_SHOW (новая задача)                               │
│        сессия → skipped                                                 │
│        (только если есть активная сессия, иначе ошибка)                 │
│                                                                         │
│    /settings ──▶ SETTINGS_MENU                                         │
│        (если есть активная сессия — сохраняется, возобновится)          │
│                                                                         │
│    /daily, /random ──▶ SOLVING_SHOW                                    │
│        (если есть активная сессия — отменяется)                         │
│                                                                         │
│    /stats ──▶ показ статистики ──▶ остаёмся в текущем состоянии        │
│        (не меняет FSM)                                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                    ПРОТУХШИЕ КУКИ (403)                                  │
│                                                                         │
│  403 из ЛЮБОГО SOLVING_* состояния:                                    │
│                                                                         │
│    текущее состояние ──▶ COOKIE_EXPIRED                                │
│        (сессия сохраняется в БД, статус остаётся active)               │
│                                                                         │
│    COOKIE_EXPIRED                                                       │
│        │                                                                │
│        │ текст (LEETCODE_SESSION)                                       │
│        ▼                                                                │
│    COOKIE_EXPIRED_CSRF                                                  │
│        │                                                                │
│        │ текст (csrftoken)                                              │
│        ├── валидация OK ──▶ возврат в сохранённое состояние            │
│        │                    (повтор последнего действия)                │
│        └── 403 ──▶ COOKIE_EXPIRED (повтор)                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                          НАСТРОЙКИ                                      │
│                                                                         │
│  /settings ──▶ SETTINGS_MENU                                           │
│                    │                                                    │
│        ┌───────────┼────────────┬────────────┬──────────┐              │
│        │           │            │            │          │               │
│   [Язык UI]  [Язык кода]  [Сложность]   [Темы]   [Куки]              │
│        │           │            │            │          │               │
│        │     переиспользуют хендлеры         │    SETTINGS_COOKIES     │
│        │     онбординга, по завершении       │          │               │
│        │     возврат в SETTINGS_MENU         │          │ текст         │
│        │           │            │            │          ▼               │
│        └───────────┴────────────┴────────────┘   SETTINGS_CSRF        │
│                                                        │               │
│                                                        │ текст         │
│                                                        ├── OK ──▶ SETTINGS_MENU
│                                                        └── 403 ──▶ SETTINGS_COOKIES
│                                                                        │
│  [Назад] из SETTINGS_MENU:                                             │
│        ├── была активная сессия ──▶ возврат в сохранённое состояние    │
│        └── не было сессии ──▶ IDLE                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Хранение состояния при прерываниях

При переходе в `COOKIE_EXPIRED` или `SETTINGS_MENU` из активной сессии:

```python
# Сохраняем в FSM data
data["suspended_state"] = current_state   # например "SOLVING_REVIEW"
data["suspended_problem"] = problem_slug
data["suspended_code"] = current_code
```

При возврате — восстанавливаем состояние и повторяем последнее действие:
- Из `SOLVING_SUBMIT` — повторный сабмит
- Из `SOLVING_APPROACH` — повторный запрос подхода
- Из `SOLVING_REVIEW` — повторный показ кода с кнопками

### Таймаут состояний

Если пользователь не взаимодействует с ботом:
- Через **30 минут** в любом `SOLVING_*` состоянии — сессия автоматически не отменяется, но при следующем сообщении бот напоминает о текущей задаче
- Через **24 часа** — сессия переводится в `cancelled`, FSM сбрасывается в `IDLE`
- Таймаут реализуется через проверку `solve_sessions.started_at` при входе в хендлер, не через отдельный scheduler

---

## Обработка ошибок

Бот никогда не падает молча. При любой ошибке пользователь видит внятное сообщение:

- **LeetCode недоступен / таймаут** — локализованная строка `errors.leetcode_unavailable`
- **403 от LeetCode** — немедленный запрос обновить куки
- **429 / rate limit от LeetCode** — retry с exponential backoff (1s, 2s, 4s, макс 3 попытки) в `leetcode/client.py`. При исчерпании — `errors.leetcode_unavailable`
- **Claude API ошибка / rate limit** — локализованная строка `errors.ai_unavailable`
- **Неизвестная ошибка** — локализованная строка `errors.unknown` + логирование полного traceback

Все ошибки логируются. Исключения не всплывают в хендлеры — оборачиваются на уровне `leetcode/client.py` и `ai/claude.py`.

---

## LeetCode API

У LeetCode нет официальной документации API. Эндпоинты получены реверс-инжинирингом сетевых запросов и проверены community-проектами.

### Общее

- **GraphQL endpoint:** `POST https://leetcode.com/graphql`
- **REST submit endpoint:** `POST https://leetcode.com/problems/{titleSlug}/submit/`
- **Submission check:** `GET https://leetcode.com/submissions/detail/{id}/check/`

**Обязательные заголовки для всех запросов:**

```
Content-Type: application/json
x-csrftoken: <значение из cookie csrftoken>
Referer: https://leetcode.com/
Cookie: LEETCODE_SESSION=<...>; csrftoken=<...>
```

### GraphQL запросы

**1. Валидация куки / получение username**

```graphql
query globalData {
  userStatus {
    isSignedIn
    username
  }
}
```

Переменные: нет. Если `isSignedIn == true` — куки валидны, `username` сохраняется в БД.

**2. Задача дня**

```graphql
query questionOfToday {
  activeDailyCodingChallengeQuestion {
    date
    link
    question {
      questionId
      questionFrontendId
      title
      titleSlug
      difficulty
      content
      topicTags { name slug }
      codeSnippets { lang langSlug code }
    }
  }
}
```

Переменные: нет.

**3. Список задач с фильтрами (для `/random`)**

```graphql
query problemsetQuestionList(
  $categorySlug: String,
  $limit: Int,
  $skip: Int,
  $filters: QuestionListFilterInput
) {
  problemsetQuestionList: questionList(
    categorySlug: $categorySlug
    limit: $limit
    skip: $skip
    filters: $filters
  ) {
    total: totalNum
    questions: data {
      questionId
      questionFrontendId
      title
      titleSlug
      difficulty
      status
      topicTags { name slug }
      paidOnly: isPaidOnly
    }
  }
}
```

Переменные:
```json
{
  "categorySlug": "algorithms",
  "limit": 1,
  "skip": <random 0..total-1>,
  "filters": {
    "difficulty": "MEDIUM",
    "tags": ["array", "dynamic-programming"]
  }
}
```

Для `/random`: первый запрос с `limit: 0` чтобы получить `total`, затем запрос с `limit: 1, skip: random(0, total-1)`.

**4. Детали задачи**

```graphql
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    questionFrontendId
    title
    titleSlug
    content
    difficulty
    topicTags { name slug }
    codeSnippets { lang langSlug code }
    sampleTestCase
  }
}
```

Переменные: `{"titleSlug": "two-sum"}`.

Поле `content` — сырой HTML, который передаётся в `html_converter.py`. Поле `codeSnippets` содержит шаблоны кода для каждого языка.

**5. Проверка результата сабмита**

```graphql
query submissionDetails($submissionId: Int!) {
  submissionDetails(submissionId: $submissionId) {
    statusCode
    runtimeDisplay
    runtimePercentile
    memoryDisplay
    memoryPercentile
    totalCorrect
    totalTestcases
    inputFormatted
    expectedOutput
    codeOutput
  }
}
```

Переменные: `{"submissionId": 123456789}`.

`statusCode`: 10 = Accepted, 11 = Wrong Answer, 14 = Time Limit Exceeded, 15 = Runtime Error. Если `state != "SUCCESS"` — сабмит ещё обрабатывается, нужно повторить запрос.

### REST эндпоинт

**Отправка решения** — единственная операция через REST, не GraphQL:

```
POST https://leetcode.com/problems/{titleSlug}/submit/

Body:
{
  "lang": "python3",
  "question_id": "1",
  "typed_code": "class Solution: ..."
}

Response:
{
  "submission_id": 123456789
}
```

Маппинг языков для поля `lang`: `python3`, `kotlin`, `java`, `cpp`.

После получения `submission_id` — polling через GraphQL запрос `submissionDetails` каждые 2 секунды, до 10 попыток.

### Источники

Документация собрана по community-проектам:
- [leetcode-graphql-queries](https://github.com/akarsh1995/leetcode-graphql-queries) — коллекция GraphQL запросов
- [python-leetcode](https://github.com/fspv/python-leetcode) — Python-клиент (автогенерация Swagger)
- [leetcode-cli DeepWiki](https://deepwiki.com/wklee610/leetcode-cli/5.3-api-endpoints-and-data-flow) — описание эндпоинтов и data flow
- [leetcode-query (npm)](https://www.npmjs.com/package/leetcode-query) — JS-клиент с GraphQL

---

## Интерфейс LeetCode-клиента

`leetcode/client.py` предоставляет следующие методы. Конкретные GraphQL query/mutation хранятся в `leetcode/queries.py`:

```python
class LeetCodeClient:
    async def validate_cookies(self) -> bool
        """GraphQL globalData. True если isSignedIn == true."""

    async def get_user_profile(self) -> str
        """GraphQL globalData → userStatus.username."""

    async def get_daily_problem(self) -> Problem
        """GraphQL questionOfToday → Problem."""

    async def get_problem_detail(self, title_slug: str) -> Problem
        """GraphQL questionData → Problem с content и codeSnippets."""

    async def get_random_problem(
        self,
        difficulty: str | None,
        topics: list[str],
        skip_slugs: list[str]
    ) -> Problem | None
        """GraphQL problemsetQuestionList с серверной фильтрацией.
        Два запроса: total → random offset. None если задач нет."""

    async def submit_solution(self, slug: str, lang: str, code: str, question_id: str) -> int
        """REST POST /problems/{slug}/submit/ → submission_id."""

    async def check_submission(self, submission_id: int) -> SubmissionResult
        """GraphQL submissionDetails → результат."""
```

Все методы оборачивают исключения внутри — хендлеры получают либо результат, либо типизированную ошибку. Retry с exponential backoff для 429/5xx встроен в клиент.

---

## Абстракция AI-клиента

Все обращения к ИИ идут через абстрактный интерфейс `BaseAIClient` из `ai/base.py`. Конкретная реализация подключается через `config.py`. Хендлеры работают только с интерфейсом, не зная о конкретном провайдере. Все методы принимают `locale` для генерации ответов на языке пользователя.

```python
# ai/base.py
from abc import ABC, abstractmethod

class BaseAIClient(ABC):

    @abstractmethod
    async def generate_code(
        self,
        problem: str,
        approach: str,
        language: str,
        locale: str = "ru",
        current_code: str | None = None
    ) -> str:
        """Генерирует код по описанию подхода пользователя"""
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
        """Возвращает наводящий вопрос, не решение.
        Если current_code и failing_test переданы (после WA) — подсказка конкретная.
        Если None (из SOLVING_APPROACH) — подсказка общая."""
        ...

    @abstractmethod
    async def explain_code(
        self,
        code: str,
        language: str,
        locale: str = "ru",
    ) -> str:
        """Объясняет что делает сгенерированный код (кнопка 'Объяснить' в SOLVING_REVIEW)"""
        ...

    @abstractmethod
    async def explain_solution(
        self,
        problem: str,
        code: str,
        language: str,
        locale: str = "ru",
    ) -> str:
        """Разбор после Accepted: почему подход работает, временная сложность, edge cases
        (кнопка 'Разбор' в SOLVING_RESULT)"""
        ...
```

`ClaudeClient` в `ai/claude.py` наследует `BaseAIClient` и реализует все четыре метода через Anthropic API. Промпты хранятся в `ai/prompts.py` отдельно от логики клиента. В промпты подставляется `locale` через `"Respond in {locale_name}."`.

---

## Ограничения AI-клиента

Системный промпт запрещает:
- Предлагать алгоритм если пользователь не описал подход
- Оптимизировать код без явного запроса
- Менять структуру алгоритма при правках — только точечные изменения по запросу

---

## Локализация

### Принцип
Все строки бота хранятся в файлах локализации. В коде нет хардкоженных текстов. Язык интерфейса выбирается при онбординге и хранится в `users.locale`.

### Структура файлов

```json
{
  "onboarding": {
    "welcome": "Привет! Давай настроим бота.",
    "enter_session": "Введи <code>LEETCODE_SESSION</code> cookie.",
    "enter_csrf": "Введи <code>csrftoken</code> cookie.",
    "invalid_cookies": "❌ Куки невалидны, попробуй ещё раз.",
    "choose_lang": "Выбери язык решений:",
    "choose_difficulty": "Выбери сложность:",
    "choose_topics": "Выбери темы (минимум одна):",
    "done": "✅ Всё настроено! Попробуй /daily или /random."
  },
  "solve": {
    "describe_approach": "Опиши своё решение:",
    "generating": "Генерирую код...",
    "submit_confirm": "Отправить на проверку?",
    "submitting": "Отправляю... ⏳"
  },
  "commands": {
    "skip": "⏭ Задача пропущена. Загружаю следующую..."
  },
  "errors": {
    "leetcode_unavailable": "LeetCode не отвечает, попробуй позже.",
    "ai_unavailable": "ИИ временно недоступен, попробуй через минуту.",
    "no_active_session": "Нет активной задачи. Попробуй /daily или /random.",
    "unknown": "Что-то пошло не так."
  }
}
```

### Модуль `bot/i18n.py`

```python
class I18n:
    def __init__(self, locale: str):
        self._data = self._load(locale)

    def get(self, key: str) -> str:
        """Получить строку по dot-notation ключу: 'onboarding.welcome'"""
        ...
```

В хендлерах и `messages.py` все тексты получаются через `i18n.get(key)`. Никаких строк напрямую в коде.

### Полнота файлов локализации

Полная структура JSON в спеке не приводится — она будет расти вместе с кодом. Правило: **при реализации каждого хендлера сразу добавлять ключи в оба файла** (`ru.json`, `en.json`). Структура JSON повторяет dot-notation ключи, используемые в коде.

---

## Форматирование сообщений

### Общее правило
Все сообщения отправляются с `parse_mode="HTML"`. Markdown не использовать нигде.

### Почему HTML а не MarkdownV2
MarkdownV2 требует экранирования `_ * [ ] ( ) ~ > # + - = | { } . !` — эти символы часто встречаются в условиях задач, именах переменных и коде. Один неэкранированный символ роняет всё сообщение. HTML этой проблемы не имеет.

### Допустимые теги
```html
<b>жирный</b>
<i>курсив</i>
<code>инлайн код</code>
<pre>блок кода</pre>
<pre><code class="language-python">блок с подсветкой</code></pre>
<a href="url">ссылка</a>
```

### Экранирование динамического контента
Любой текст извне (условие задачи, код от AI, ввод пользователя) перед вставкой в HTML прогоняется через:

```python
def escape_html(text: str) -> str:
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;"))
```

Статичные строки бота экранировать не нужно — они хранятся в `locales/*.json` и не содержат спецсимволов HTML.

### Конвертация кода от AI
AI возвращает код в markdown-блоках. Перед отправкой конвертируем в HTML:

```python
import re

def md_code_to_html(text: str) -> str:
    # блоки с языком
    text = re.sub(
        r'```(\w+)\n(.*?)```',
        lambda m: f'<pre><code class="language-{m.group(1)}">{escape_html(m.group(2))}</code></pre>',
        text, flags=re.DOTALL
    )
    # блоки без языка
    text = re.sub(
        r'```\n?(.*?)```',
        lambda m: f'<pre>{escape_html(m.group(1))}</pre>',
        text, flags=re.DOTALL
    )
    # инлайн код
    text = re.sub(
        r'`([^`]+)`',
        lambda m: f'<code>{escape_html(m.group(1))}</code>',
        text
    )
    return text
```

### Лимит длины сообщения
Telegram ограничивает сообщение 4096 символами. Все длинные сообщения отправляются через:

```python
def split_message(text: str, limit: int = 4096) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        split_at = text.rfind('\n', 0, limit)
        if split_at == -1:
            split_at = limit
        parts.append(text[:split_at])
        text = text[split_at:].lstrip('\n')
    return parts
```

### Шаблоны сообщений
Все тексты бота — в `bot/messages.py` как функции-форматтеры. Никаких HTML-строк прямо в хендлерах:

```python
def fmt_problem(title, difficulty, slug, content) -> str:
    diff_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(difficulty, "")
    return (
        f"<b>{escape_html(title)}</b> {diff_emoji}\n"
        f"<a href='https://leetcode.com/problems/{slug}/'>Открыть на LeetCode</a>\n\n"
        f"{content}"  # уже safe HTML из конвертера, escape_html НЕ применяется
    )

def fmt_accepted(runtime, runtime_pct, memory, memory_pct) -> str:
    return (
        f"✅ <b>Accepted!</b>\n\n"
        f"⏱ Runtime: <code>{runtime}ms</code> (beats {runtime_pct}%)\n"
        f"💾 Memory: <code>{memory}MB</code> (beats {memory_pct}%)"
    )

def fmt_wrong_answer(input_, expected, got) -> str:
    return (
        f"❌ <b>Wrong Answer</b>\n\n"
        f"Input: <code>{escape_html(str(input_))}</code>\n"
        f"Expected: <code>{escape_html(str(expected))}</code>\n"
        f"Got: <code>{escape_html(str(got))}</code>"
    )
```

---

## Нефункциональные требования

- Деплой на Orange Pi Zero 3, локально, без внешнего хостинга
- Бот только для одного пользователя — доступ ограничен по `ALLOWED_TELEGRAM_ID`
- `.env` с правами `600`
- Все запросы к LeetCode асинхронные
- Логирование:
  - Путь: `logs/bot.log` (относительно корня проекта)
  - Ротация: `RotatingFileHandler`, 5 MB, 3 файла
  - Уровень: `INFO` (переключается через env-переменную `LOG_LEVEL`)
  - Формат: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

---

## БД

```sql
users (
    telegram_id        INTEGER PRIMARY KEY,
    lc_session         TEXT,
    lc_csrf            TEXT,
    lc_username        TEXT,
    preferred_lang     TEXT,
    difficulty         TEXT,
    current_difficulty TEXT,
    topics             TEXT,           -- json array
    locale             TEXT DEFAULT 'ru',
    cookies_updated    TIMESTAMP,
    consecutive_solved INTEGER DEFAULT 0,
    consecutive_failed INTEGER DEFAULT 0,
    created_at         TIMESTAMP
)

solved_problems (
    id              INTEGER PRIMARY KEY,
    telegram_id     INTEGER,
    problem_slug    TEXT,
    problem_id      INTEGER,
    difficulty      TEXT,
    result          TEXT,              -- accepted / wa / tle
    attempts        INTEGER,
    solved_at       TIMESTAMP
)

solve_sessions (
    id              INTEGER PRIMARY KEY,
    telegram_id     INTEGER,
    problem_slug    TEXT,
    language        TEXT,
    user_approach   TEXT,
    current_code    TEXT,
    iteration       INTEGER DEFAULT 0,
    status          TEXT,              -- active / completed / cancelled / skipped
    started_at      TIMESTAMP
)
```

---

## Деплой

### Скрипт `deploy.sh`

Запускается один раз на чистой системе:

```
1. Проверяет наличие Python 3.11+
2. Создаёт виртуальное окружение venv
3. Устанавливает зависимости из requirements.txt
4. Создаёт .env из .env.example если .env не существует
5. Выставляет права 600 на .env
6. Инициализирует БД (создаёт таблицы)
7. Создаёт и регистрирует systemd сервис
8. Включает автозапуск
9. Запускает сервис
10. Выводит статус
```

### systemd сервис `leetcode-bot.service`

```ini
[Unit]
Description=LeetCode Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/leetcode-bot
ExecStart=/path/to/leetcode-bot/venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`Restart=on-failure` — автоперезапуск при падении. `After=network.target` — ждёт сети перед стартом.

### Управление после деплоя

```bash
sudo systemctl status leetcode-bot
sudo systemctl restart leetcode-bot
sudo systemctl stop leetcode-bot
journalctl -u leetcode-bot -f
```

---

## README

Должен содержать:
- Как получить `LEETCODE_SESSION` и `csrftoken` из браузера (пошаговая инструкция)
- Как заполнить `.env`
- Как запустить `deploy.sh`
- Команды управления сервисом