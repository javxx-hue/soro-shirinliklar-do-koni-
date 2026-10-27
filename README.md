# Telegram Business AI Assistant (Powered by Google Gemini)

A personal AI assistant for Telegram Business accounts powered by **Google Gemini** (`gemini-2.5-flash` or `gemini-2.5-pro`). The bot connects to your Telegram account via the official Telegram Business "Chatbots" feature and replies to incoming messages in your personal tone and style using details provided in `profile.md`.

Authentication is handled cleanly via Google AI Studio (`GEMINI_API_KEY`).

---

## What It Does

- Connects to Telegram Business using Telegram's built-in **Chatbots** management.
- **No code allowlists:** Telegram completely dictates which chats the bot can see (*Settings → Telegram Business → Chatbots*).
- **Default Preview Mode:** Runs safely in `AUTO_SEND=false` by default, generating responses and printing formatted previews in the logs (`previews.jsonl`) without actually sending messages to chats.
- Generates natural, context-aware replies matching your writing style, tone, and active language (Uzbek, Russian, English).
- Strict safety filters: ignores bot messages, blocks unauthorized commitments regarding money, meetings, and sensitive data, and respects owner takeover (silence when you reply yourself).

---

## Behaviour Overview

| Event / Scenario | Behaviour |
|---|---|
| **Foreign Account Connection** | Connection update is logged with a warning; Gemini is never invoked. |
| **Chat Filtering** | Telegram's *Business → Chatbots* settings govern chat visibility. No chat allowlist in code. |
| **Owner Messages** | Recorded into history as `[You]`; triggers takeover silence timer (`OWNER_TAKEOVER_MINUTES`). Never replied to. |
| **Bot Messages** | Messages with `sender_business_bot` or `from_user.is_bot` are silently ignored. |
| **Duplicates** | Message IDs tracked across restarts via `seen.json`; duplicates are skipped immediately before any async call. |
| **Service Messages** | Unsupported non-text updates (joins, pins) are skipped without error. Media (stickers, voice, photos) receive descriptive tags. |
| **Owner Commands** | `/pause`, `/resume`, `/status` work only in direct private chat with the owner. |
| **`/start` Command** | Owner receives comprehensive onboarding instructions in Uzbek. Other users receive a brief disclaimer stating the bot is private. |
| **Quota / Rate Limit (429)** | Pauses generation for `LIMIT_COOLDOWN_MINUTES`; notifies owner if auto-send is active. |
| **Timeout / Auth Errors** | Gracefully caught and logged; never sends error messages to conversation partners. |
| **`[SKIP]` Token** | If Gemini determines no response is needed (e.g. casual acknowledgment), it outputs `[SKIP]` and nothing is sent. |
| **Auto-Send Verification** | Fresh connection rights (`can_reply`) and active owner status are re-checked with Telegram right before sending. |

---

## Deploy to Railway

1. **Obtain Google Gemini API Key:**
   - Go to [aistudio.google.com](https://aistudio.google.com/) and click **Get API key**.
   - Create and copy your key. (Free Tier is included and sufficient for daily messaging).
2. **Create Telegram Bot:**
   - Open [@BotFather](https://t.me/BotFather) on Telegram and create a new bot (`/newbot`).
   - Enable Business Mode: `/mybots` → Select your bot → *Bot Settings* → *Business Mode* → *Turn on*.
   - Find your Telegram numeric user ID using [@userinfobot](https://t.me/userinfobot).
3. **Push to Private GitHub Repository:**
   - Create a **private** GitHub repository (since `profile.md` contains personal background).
   - Push your code to `main`.
4. **Deploy on Railway:**
   - Go to [Railway](https://railway.com) and click **New Project** → **Deploy from GitHub repo** → Select your repository.
5. **Set Environment Variables:**
   - In Railway, navigate to **Service** → **Variables** → **Raw Editor** and paste:
     ```env
     TELEGRAM_BOT_TOKEN=<your_bot_token>
     OWNER_ID=<your_numeric_user_id>
     GEMINI_API_KEY=AIzaSy...
     GEMINI_MODEL=gemini-2.5-flash
     AUTO_SEND=false
     ```
6. **Attach Persistent Volume:**
   - On the Railway canvas, right click (or press `Cmd+K` / `Ctrl+K`) → **Volume**.
   - Select your service and set the Mount Path to exactly:
     ```
     /app/data
     ```
   - Click **Deploy**. *(Without this volume, message history, pauses, and rate limit states reset on every redeployment).*
7. **Check Logs:**
   - Verify deployment logs:
     ```
     Bot @... is running!
     Mode: PREVIEW (replies only logged, not sent)
     Gemini model: gemini-2.5-flash
     Gemini auth: API key from environment variables
     ```
8. **Connect Telegram Business Account:**
   - Start your bot in Telegram by sending `/start`.
   - In Telegram: *Settings → Telegram Business → Chatbots* (requires Telegram Premium).
   - Add your bot username, choose which chats it should access, and enable **Reply to messages**.
   - Logs will confirm: `Business connection <id>: user=<id> enabled=True can_reply=True`.
9. **Review Previews & Enable Auto-Send:**
   - Observe incoming messages in Railway logs. Each proposed response appears as `--- [PREVIEW, not sent] ---`.
   - Once satisfied with the replies, update Railway variable `AUTO_SEND=true` and redeploy.

---

## Local Development & Testing

1. **Virtual Environment & Dependencies:**
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
2. **Setup Local Environment:**
   ```bash
   cp .env.example .env
   chmod 600 .env
   ```
   Add your `GEMINI_API_KEY` to `.env`.
3. **Diagnostic Checks:**
   ```bash
   # Test Gemini API connectivity
   python bot.py --check-gemini

   # Test a single message response
   python bot.py --try "Salom, qalaysiz?"
   python bot.py --try "Привет, как дела?"
   python bot.py --try "Hi, how are you doing?"
   ```
4. **Run Offline Test Suite:**
   ```bash
   pytest -v
   ```

---

## CLI Options & Exit Codes

- `python bot.py`: Run bot using `.env`.
- `python bot.py --settings-from-env`: Run bot in container mode (wipes secrets from environment memory).
- `python bot.py --check-gemini`: Verify Gemini API connectivity (exit 0 on success, exit 1 on failure).
- `python bot.py --try "<text>"`: Generate a test reply without connecting to Telegram.

**Exit Codes:**
- `0`: Success / Clean shutdown.
- `1`: Diagnostic check failure.
- `2`: Configuration error or Telegram authentication failure.
