# LeetCode Telegram Bot

Telegram-bot that helps you practice algorithmic thinking on LeetCode problems — without writing code by hand.

You get a problem, describe your approach in plain text, and the bot generates code from your description, submits it to LeetCode, and shows the result. If something is wrong — ask for a hint, revise your approach, and try again.

The idea: focus on understanding algorithms and data structures, not on syntax and typos.

## Features

- **Problem selection** — daily challenge, random by filters, or specific problem by slug
- **Natural language solving** — describe your algorithm in words, AI turns it into code
- **Iterative workflow** — edit, explain, submit, get hints, revise, repeat
- **Hints on wrong answers** — AI analyzes the failing test case and gives a targeted hint
- **Solution review** — after acceptance, get complexity analysis and optimization suggestions
- **Theory reference** — request educational material on relevant data structures and algorithms
- **Adaptive difficulty** — automatically adjusts difficulty based on your results
- **Statistics** — track solved problems, streaks, and top topics
- **Bilingual** — full Russian and English support
- **Languages** — Python, Java, Kotlin, C++

## How It Works

1. **Setup** — choose interface language, enter LeetCode cookies, pick solution language, difficulty, and topics of interest
2. **Get a problem** — use `/daily`, `/random`, or `/problem <slug>`
3. **Read and think** — the bot shows the problem statement, examples, and starter code
4. **Describe your approach** — explain your algorithm in plain text (or ask for theory first)
5. **Review generated code** — the bot shows the code; you can edit it, ask for an explanation, or submit
6. **Submit and iterate** — the bot submits to LeetCode and shows the verdict:
   - **Accepted** — see runtime/memory stats, request a review or optimization suggestions, then move to the next problem
   - **Wrong answer** — see expected vs actual output, ask for a hint, revise your approach
   - **TLE / Error** — revise and try a different approach
7. **Track progress** — `/stats` shows your solve count, difficulty breakdown, streak, and top topics

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Initial setup |
| `/daily` | Daily challenge |
| `/random` | Random problem matching your filters |
| `/problem <slug>` | Specific problem (e.g. `/problem two-sum`) |
| `/stats` | Solving statistics |
| `/settings` | Change language, difficulty, topics, or cookies |
| `/skip` | Skip current problem |
| `/cancel` | Cancel current session |

## Requirements

- Python 3.11+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Anthropic API Key
- LeetCode account

## Setup

### 1. Clone and configure

```bash
git clone <repo-url>
cd leetcode-bot
cp .env.example .env
chmod 600 .env
```

Edit `.env`:

```
BOT_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
ALLOWED_TELEGRAM_ID=your_telegram_user_id
```

To find your Telegram ID, message [@userinfobot](https://t.me/userinfobot).

### 2. Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### 3. Deploy (systemd)

```bash
chmod +x deploy.sh
./deploy.sh
```

The script creates a virtual environment, installs dependencies, and sets up a systemd service.

## Getting LeetCode Cookies

The bot needs your LeetCode session cookies to fetch problems and submit solutions.

1. Open [leetcode.com](https://leetcode.com) and log in
2. Open DevTools (`F12`) → **Application** → **Cookies** → `https://leetcode.com`
3. Copy `LEETCODE_SESSION` and `csrftoken` values

The bot will ask for these during setup. Cookies expire roughly every 2 weeks — the bot will ask you to refresh them when needed.

## Service Management

```bash
sudo systemctl status leetcode-bot
sudo systemctl restart leetcode-bot
journalctl -u leetcode-bot -f
```

## Project Structure

```
leetcode-bot/
├── bot/
│   ├── handlers/
│   │   ├── start.py          # onboarding
│   │   ├── solve.py          # main solving flow
│   │   ├── daily.py          # /daily, /random, /problem
│   │   ├── stats.py          # /stats
│   │   └── settings.py       # /settings
│   ├── keyboards.py          # inline keyboards
│   ├── messages.py           # message formatters
│   ├── middlewares.py        # access control
│   └── i18n.py               # localization
├── locales/
│   ├── ru.json
│   └── en.json
├── leetcode/
│   ├── client.py             # LeetCode API client
│   ├── queries.py            # GraphQL queries
│   ├── models.py             # data models
│   └── html_converter.py     # HTML → Telegram format
├── ai/
│   ├── base.py               # abstract AI client
│   ├── claude.py             # Claude implementation
│   └── prompts.py            # system prompts
├── db/
│   ├── database.py           # DB init
│   ├── users.py              # user CRUD
│   └── sessions.py           # session CRUD
├── config.py
├── main.py
├── requirements.txt
├── .env.example
├── deploy.sh
└── README.md
```
