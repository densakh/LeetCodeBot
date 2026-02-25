# LeetCode Telegram Bot

Personal Telegram bot for solving LeetCode problems without writing code manually. Describe your algorithm in natural language, AI generates the implementation, and the bot submits it for verification.

## Requirements

- Python 3.11+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Anthropic API Key
- LeetCode account

## Getting LeetCode Cookies

The bot needs your LeetCode session cookies to interact with the platform.

### Step-by-step:

1. Open [leetcode.com](https://leetcode.com) in your browser and log in
2. Open Developer Tools (press `F12` or `Cmd+Option+I` on Mac)
3. Go to the **Application** tab (Chrome) or **Storage** tab (Firefox)
4. In the left sidebar, expand **Cookies** and click on `https://leetcode.com`
5. Find and copy the value of `LEETCODE_SESSION`
6. Find and copy the value of `csrftoken`

> Cookies are valid for approximately 2 weeks. The bot will remind you when they need updating.

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd leetcode-bot
```

### 2. Fill in environment variables

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` and fill in:

```
BOT_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
ALLOWED_TELEGRAM_ID=your_telegram_user_id
LOG_LEVEL=INFO
```

To find your Telegram ID, message [@userinfobot](https://t.me/userinfobot).

### 3. Quick Start (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

The bot will initialize the database automatically and start polling.

### 4. Deploy (systemd)

For a permanent setup on a server (e.g. Orange Pi):

```bash
chmod +x deploy.sh
./deploy.sh
```

The deploy script will:
- Check Python version
- Create a virtual environment
- Install dependencies + patchright Chromium
- Install Xvfb (for headless Cloudflare bypass)
- Initialize the database
- Create and start a systemd service (via `xvfb-run`)

### 5. Transfer to another machine (without git)

```bash
rsync -av --exclude={'.venv','data','logs','__pycache__','*.pyc','.env','.idea','.git'} ./ user@target:/path/to/leetcode-bot/
```

On the target machine:

```bash
cd /path/to/leetcode-bot
cp .env.example .env && chmod 600 .env
# fill in .env
./deploy.sh
```

> `data/` is excluded — it will be recreated on first launch. Copy it separately to keep history.

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Initial setup (language, cookies, preferences) |
| `/daily` | Get the LeetCode daily challenge |
| `/random` | Get a random problem matching your filters |
| `/stats` | View your solving statistics |
| `/settings` | Change language, difficulty, topics, or cookies |
| `/skip` | Skip current problem and load a new one |
| `/cancel` | Cancel current solving session |

## How It Works

1. Start the bot with `/start` and complete the setup
2. Use `/daily` or `/random` to get a problem
3. Describe your approach in natural language
4. Review the AI-generated code
5. Submit to LeetCode and see the results
6. Get hints or revise your approach if needed

## Service Management

```bash
# Check status
sudo systemctl status leetcode-bot

# Restart
sudo systemctl restart leetcode-bot

# Stop
sudo systemctl stop leetcode-bot

# View logs
journalctl -u leetcode-bot -f

# Application logs
tail -f logs/bot.log
```

## Project Structure

```
leetcode-bot/
├── bot/
│   ├── handlers/
│   │   ├── start.py        # onboarding
│   │   ├── solve.py         # main solving flow
│   │   ├── daily.py         # /daily and /random
│   │   ├── stats.py         # /stats
│   │   └── settings.py      # /settings
│   ├── keyboards.py         # inline keyboards
│   ├── messages.py          # message formatters
│   ├── middlewares.py       # access control
│   ├── i18n.py              # localization
│   └── scheduler.py         # cookie reminders
├── locales/
│   ├── ru.json
│   └── en.json
├── leetcode/
│   ├── client.py            # LeetCode API client
│   ├── playwright_submit.py # Cloudflare bypass via patchright
│   ├── queries.py           # GraphQL queries
│   ├── models.py            # data models
│   └── html_converter.py    # HTML to Telegram format
├── ai/
│   ├── base.py              # abstract AI client
│   ├── claude.py            # Claude implementation
│   └── prompts.py           # system prompts
├── db/
│   ├── database.py          # DB initialization
│   ├── users.py             # user CRUD
│   └── sessions.py          # session CRUD
├── config.py
├── main.py
├── requirements.txt
├── .env.example
├── deploy.sh
└── README.md
```
