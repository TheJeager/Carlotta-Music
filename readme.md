<div align="center">

<img src="https://i.ibb.co/n8cwC0KR/photo-2026-04-17-20-43-57.jpg" width="320" alt="Carlotta Music banner" />

# 🎵 Carlotta Music

### Elegant Telegram Voice Chat Music Bot

A feature-rich Telegram music bot for voice chats, built with **Python**, **Kurigram**, **PyTgCalls**, and **MongoDB**.

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.13%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img alt="Kurigram" src="https://img.shields.io/badge/Kurigram-2.2.26-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" />
  <img alt="PyTgCalls" src="https://img.shields.io/badge/PyTgCalls-Streaming-26A5E4?style=for-the-badge" />
  <img alt="MongoDB" src="https://img.shields.io/badge/MongoDB-Database-47A248?style=for-the-badge&logo=mongodb&logoColor=white" />
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

<p>
  <img alt="FFmpeg" src="https://img.shields.io/badge/FFmpeg-Required-007808?style=flat-square&logo=ffmpeg&logoColor=white" />
  <img alt="Platform" src="https://img.shields.io/badge/Platform-Linux-informational?style=flat-square" />
  <img alt="License" src="https://img.shields.io/badge/Status-Public%20Repo-orange?style=flat-square" />
</p>

</div>

---

## 📌 Table of Contents

- [🌟 Preview](#-preview)
- [✨ Highlights](#-highlights)
- [🏗️ Architecture Flow](#️-architecture-flow)
- [🗂️ Project Structure](#️-project-structure)
- [🙏 Credits](#-credits)
- [🚀 Quick Start](#-quick-start)
- [🔐 Environment Configuration](#-environment-configuration)
- [▶️ Run Methods](#️-run-methods)
- [🐳 Docker Deployment](#-docker-deployment)
- [🧩 Command Map](#-command-map)
- [💾 Persistence & Data](#-persistence--data)
- [🛠️ Troubleshooting](#️-troubleshooting)
- [🔒 Security Checklist](#-security-checklist)
- [🧪 Developer Notes](#-developer-notes)

---

## 🌟 Preview

### Welcome Experience

- Branded startup image and clean command responses.
- Fast feedback for play/search/ping actions.
- Structured controls for playback, queue, and quality tuning.

### What You Can Expect

- Stable group voice playback.
- Multi-session assistant handling.
- Configurable autoplay, loop, and queue behavior.

---

## ✨ Highlights

- 🎙️ **Voice Chat Streaming** with PyTgCalls.
- 🤖 **Multi-Client Startup** (bot + up to 3 assistants).
- 📚 **Smart Queue System** for each chat.
- 🔁 **Autoplay** using related-track discovery.
- 🎚️ **Quality Profiles** (best / balanced / performance).
- 📡 **RTMP Streaming Support** (set, play, stop, inspect).
- 🌍 **Multi-language Ready** via locale files.
- 🧠 **MongoDB Persistence** for settings, auth, and state.
- 🧩 **Plugin-based Design** for easy extension.

---

## 🏗️ Architecture Flow

```text
User Command
   ↓
Pyrogram Handler (Plugin)
   ↓
Queue / Resolver / YouTube Layer
   ↓
PyTgCalls Stream Engine
   ↓
Telegram Group Voice Chat
```

Startup sequence:

1. `python3 -m carlotta` boots `carlotta/__main__.py`.
2. Initializes MongoDB, bot client, assistants, and call engine.
3. Dynamically loads plugins from `carlotta/plugins`.
4. Serves commands with shared runtime objects from `carlotta/__init__.py`.

---

## 🗂️ Project Structure

```text
.
├── carlotta/
│   ├── __main__.py
│   ├── __init__.py
│   ├── core/
│   ├── helpers/
│   ├── locales/
│   ├── plugins/
│   └── cookies/
├── config.py
├── requirements.txt
├── Dockerfile
├── Procfile
└── start
```

---

## ⚙️ Requirements

| Component | Minimum |
|---|---|
| Python | 3.13+ |
| FFmpeg | Installed on host/container |
| Database | MongoDB URI |
| Telegram | API_ID, API_HASH, BOT_TOKEN |
| Assistant Session | SESSION1 (required) |

Install Python packages:

```bash
pip install -r requirements.txt
```

---

## 🚀 Quick Start

### 1) Clone project

```bash
git clone https://github.com/TheJeager/Carlotta-Music
cd Carlotta-Music
```

### 2) Install FFmpeg (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

### 3) Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4) Configure `.env`

Create `.env` in root (uses `python-dotenv`).

### 5) Start bot

```bash
bash start
```

_or_

```bash
python3 -m carlotta
```

---

## 🔐 Environment Configuration

Runtime config is managed in `config.py` via class `Config`.

### Required variables

- `API_ID`
- `API_HASH`
- `BOT_TOKEN`
- `MONGO_URL`
- `LOGGER_ID`
- `OWNER_ID`
- `SESSION1`

### Optional variables

- `SESSION2`, `SESSION3`
- `DURATION_LIMIT`, `QUEUE_LIMIT`, `PLAYLIST_LIMIT`
- `SUPPORT_CHANNEL`, `SUPPORT_CHAT`
- `AUTO_LEAVE`, `AUTO_END`, `THUMB_GEN`, `VIDEO_PLAY`
- `LANG_CODE`
- `COOKIES_URL`
- `DEFAULT_THUMB`, `PING_IMG`, `START_IMG`

### Sample `.env`

```env
API_ID=123456
API_HASH=your_api_hash
BOT_TOKEN=123456789:your_bot_token
MONGO_URL=mongodb+srv://user:pass@cluster.example.mongodb.net/?retryWrites=true&w=majority
LOGGER_ID=-1001234567890
OWNER_ID=123456789
SESSION1=your_pyrogram_session_string
```

> ⚠️ Never commit real tokens, sessions, or credentials.

---

## ▶️ Run Methods

### Standard

```bash
bash start
```

### Module mode

```bash
python3 -m carlotta
```

### Procfile

```procfile
worker: bash start
```

---

## 🐳 Docker Deployment

```bash
docker build -t Carlotta-Music .
docker run --rm --env-file .env Carlotta-Music 
```

The image installs FFmpeg, Deno, and the pinned Python dependencies, then starts the bot with `python -m carlotta`.

---

## 🧩 Command Map

### Playback
`/play` `/playforce` `/vplay` `/vplayforce`

### Queue
`/queue` `/playing`

### Controls
`/pause` `/resume` `/skip` `/next` `/stop` `/end` `/seek` `/seekback` `/loop`

### Quality & mode
`/quality` `/streammode` `/playmode` `/settings`

### Playlist
`/playlist` `/addpl` `/delpl`

### Admin & auth
`/auth` `/unauth` `/authlist` `/admincache` `/reload`

### Bot info
`/start` `/help` `/ping` `/alive` `/stats`

### Sudo / owner
`/addsudo` `/delsudo` `/rmsudo` `/listsudo` `/sudolist` `/broadcast` `/restart` `/logs` `/logger`

### Eval
`/eval` `/exec`

### Blacklist
`/blacklist` `/unblacklist` `/whitelist`

### Voice activity
`/ac` `/activevc`

### Language
`/lang` `/language`

### Autoplay
`/autoplay`

> Some commands are admin-only, owner-only, or group-only.

---

## 💾 Persistence & Data

MongoDB usage includes:

- Authorized user records
- Assistant assignment per chat
- Blacklist and whitelist data
- Language and per-chat preferences
- Queue and playlist metadata
- Autoplay + stream mode toggles

At startup, database connectivity is verified before full bot service is enabled.

---

## 🛠️ Troubleshooting

- **Startup logger errors**
  - Ensure bot can post in `LOGGER_ID` chat.
  - Ensure bot has admin permissions.

- **Assistant client fails**
  - Regenerate `SESSION1/2/3`.
  - Check session validity and account status.

- **No music in VC**
  - Confirm voice chat is active.
  - Ensure assistant can join/speak.
  - Verify FFmpeg installation.

- **Autoplay/download problems**
  - Check external API/cookies settings.
  - Check server connectivity.

- **MongoDB failures**
  - Validate `MONGO_URL`.
  - Ensure network/IP allows DB access.

---

## 🔒 Security Checklist

- [ ] Keep `.env`, Telegram session files, and cookie files out of version control.
- [ ] Rotate leaked tokens immediately.
- [ ] Restrict owner/sudo access.
- [ ] Keep `/eval` and `/exec` restricted to the configured owner; these commands execute arbitrary Python code.
- [ ] Restrict broadcast and sudo commands to trusted accounts.
- [ ] Use managed secrets in production.

---

## 🧪 Developer Notes

- Entrypoint: `carlotta/__main__.py`
- Runtime globals: `carlotta/__init__.py`
- Plugin autoload: `carlotta/plugins/__init__.py`
- Extend features by adding a plugin under `carlotta/plugins/`

Recommended future improvements:

- Remove hardcoded sensitive defaults from `config.py`
- Document assistant session generation flow in detail

---
## 🙏 Credits
Special thanks to [AnonymousX1025](https://github.com/AnonymousX1025) for the original inspiration.

Original project: [AnonXMusic](https://github.com/AnonymousX1025/AnonXMusic)
