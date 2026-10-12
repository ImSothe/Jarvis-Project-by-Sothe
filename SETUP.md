# Set up your own Jarvis

A step-by-step guide to running your own copy of **Jarvis Project by Sothe**, with all of its features, on Windows. It is ordered so you get a working assistant first (only one free key) and then switch on the extras one by one.

> **Time:** about 15 minutes for the core assistant; each optional integration adds 5-10 minutes.
> **Cost:** nothing. Everything below uses free tiers. The only paid thing you might already have is Spotify Premium, which Spotify requires to control playback through its API.

## Contents

1. [What you need first](#1-what-you-need-first)
2. [Install](#2-install)
3. [Add your AI key](#3-add-your-ai-key-the-only-required-step)
4. [Enable the Jarvis tools](#4-enable-the-jarvis-tools-required)
5. [First launch](#5-first-launch)
6. [Turn on voice](#6-turn-on-voice)
7. [Optional integrations](#7-optional-integrations)
   - [Approved apps (`open_app`)](#approved-apps-open_app)
   - [Spotify](#spotify)
   - [Gmail and Google Calendar](#gmail-and-google-calendar)
   - [Weather](#weather)
   - [Instagram](#instagram)
   - [Viral videos (YouTube + video analysis)](#viral-videos-youtube--video-analysis)
   - [X (Twitter) analytics](#x-twitter-analytics)
   - [OBS Studio](#obs-studio)
   - [PC control and installing programs](#pc-control-and-installing-programs)
   - [Make it yours (persona and the author-specific tools)](#make-it-yours-persona-and-the-author-specific-tools)
8. [Where everything lives](#8-where-everything-lives)
9. [Check that it works](#9-check-that-it-works)
10. [Troubleshooting](#10-troubleshooting)
11. [Keeping your keys safe](#11-keeping-your-keys-safe)

---

## 1. What you need first

| Requirement | Why | How to get it |
|---|---|---|
| **Windows 10/11** | The PC, Spotify, OBS and `winget` tools are Windows-only | - |
| **Git** | To clone the repo | `winget install Git.Git` |
| **Python 3.10-3.13** | Backend | `winget install Python.Python.3.12` |
| **uv** | Python package manager | `winget install astral-sh.uv` |
| **Node.js 18+** | Web interface | `winget install OpenJS.NodeJS.LTS` |
| **A free Gemini API key** | The AI brain, speech and voice | <https://aistudio.google.com/apikey> |

Needed only for specific features:

| Feature | Requirement |
|---|---|
| Spotify | Spotify **desktop app** installed from spotify.com, and a **Premium** account |
| Video analysis | `ffmpeg` (`winget install Gyan.FFmpeg`) |
| OBS control | OBS Studio 28 or newer |

Open a new PowerShell window after installing anything so the commands are on your PATH.

## 2. Install

```powershell
git clone https://github.com/ImSothe/Jarvis-Project-by-Sothe.git
cd Jarvis-Project-by-Sothe

# Backend: creates the .venv folder and installs everything, including the desktop extras
uv sync --extra desktop

# Web interface
cd frontend
npm install
cd ..
```

The launch scripts expect the virtual environment at `.\.venv`, which `uv sync` creates. A few small Windows-only packages (the app window, OBS, audio control, media sessions, `yt-dlp`) are installed automatically the first time you run `start-jarvis.ps1`.

## 3. Add your AI key (the only required step)

1. Copy the template:

   ```powershell
   copy .env.example .env
   ```

2. Open `.env` and paste your key:

   ```
   GEMINI_API_KEY=your_key_here
   ```

That is all the core assistant needs. Jarvis uses this one key for the language model, for understanding your voice and for speaking back.

> **Important:** Jarvis reads `.env` only when you start it through `start-jarvis.ps1`, `jarvis-terminal.ps1` or the Jarvis app shortcut (which calls `start-jarvis.ps1`). Do not start the server any other way, or it will not see your keys. If you edit `.env`, **restart Jarvis**.

`.env` is listed in `.gitignore`, so it will never be committed.

## 4. Enable the Jarvis tools (required)

Out of the box, the agent is only allowed to use three tools: `think`, `calculator` and `web_search`. **None of the Jarvis features (Spotify, PC control, Google, Instagram...) work until you enable them.** The repo ships a ready-made list:

```powershell
mkdir $env:USERPROFILE\.openjarvis -Force
copy config.example.toml $env:USERPROFILE\.openjarvis\config.toml
```

If you already have a `config.toml` there, copy only the `[tools]`, `[speech]` and `[system_prompt]` blocks into it.

Open the file and read the comments. It enables 26 tools, grouped by purpose; delete a line to switch a tool off. Two tools are **deliberately left out** because they can act on their own: `gmail_send_email` (sends mail from your account) and `shell_exec` (runs commands on your PC). Add them only if you accept that risk. `get_weather` and `optimizer_info` are commented out as optional.

## 5. First launch

```powershell
.\start-jarvis.ps1
```

This installs the missing small packages, starts the server and the interface, and opens Jarvis in your browser. The first launch takes a few minutes.

To use Jarvis as a **proper desktop app** instead of a browser tab, create the shortcut once:

```powershell
.\make-jarvis-shortcut.ps1
```

It adds a **Jarvis** shortcut to your desktop and Start menu (you can pin it to the taskbar). From then on, open Jarvis from that shortcut. The app starts the server for you, connects the microphone by itself and releases the microphone when you close the window.

Closing the window leaves the server running in the background (so a restart is instant). To stop everything, end the `jarvis.exe` and `python.exe` processes from the Jarvis folder in Task Manager.

> Jarvis does **not** start with Windows. If you want that, put a shortcut to `.venv\Scripts\pythonw.exe "<repo>\jarvis_app.pyw"` in your Startup folder (`Win+R`, then `shell:startup`).

## 6. Turn on voice

1. In Jarvis, open **Settings** and turn on **Speech-to-Text** and **Text-to-Speech**. Turn on **Wake word** too if you want the browser to listen for "Jarvis" outside a call.
2. Allow the microphone when asked. The desktop app allows it automatically.
3. Say **"Jarvis, ..."**. Only sentences that **start with "Jarvis"** are answered; everything else is ignored.

The first time you speak, the local Whisper models used by the privacy filter are downloaded (about 150 MB for the fast one and about 460 MB for the accurate one). This happens once.

**Choosing Jarvis's voice.** It is the `[speech]` block of `~/.openjarvis/config.toml` (`C:\Users\<you>\.openjarvis\config.toml`):

```toml
[speech]
tts_backend = "gemini_tts"   # free with your Gemini key
voice_id = "Kore"            # Gemini voice names: Kore, Algenib, Puck, Charon, Fenrir...
voice_speed = 1.0
```

Other backends: `kokoro` is a fully local voice (install the `voice` extra with `uv sync --extra desktop --extra voice` and `espeak-ng`). `edge_tts` is supported, but it relies on an unofficial Microsoft endpoint that can reject connections (it returned a 403 error when this guide was tested), so prefer `gemini_tts`.

You can steer the Gemini voice's acting with an optional line in `.env`, for example `GEMINI_TTS_STYLE=Speak in a calm, low voice`. Restart Jarvis after changing the voice.

**Advanced switches.** Two behaviors are stored in the app's browser storage. To change them, enable the developer tools once by setting a Windows environment variable and restarting the app:

```powershell
setx JARVIS_DEBUG 1
```

Then press `F12` in the Jarvis window, open **Console** and run one of these:

| Command | Effect |
|---|---|
| `localStorage.setItem('jarvis.autoConnect','false')` | Do not connect the microphone on launch (you get a "tap core to connect" button) |
| `localStorage.setItem('jarvis.requireName','false')` | Answer everything you say, without needing the word "Jarvis" |

## 7. Optional integrations

Each section is independent. Skip what you do not need; the tools you do not configure simply report that they are not connected.

### Approved apps (`open_app`)

For safety, Jarvis can only open programs you list in `~/.openjarvis/apps.json`. Create the file; names are what you say out loud:

```json
{
  "chrome": {
    "path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "accepts_url": true,
    "aliases": ["browser", "google"]
  },
  "vscode": {
    "path": "C:\\Users\\YOU\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"
  },
  "my game": {
    "uri": "steam://rungameid/730"
  },
  "spotify search": {
    "uri_template": "spotify:search:{q}"
  }
}
```

| Key | Meaning |
|---|---|
| `path` | Full path to the `.exe` |
| `args` | Optional list of command-line arguments |
| `accepts_url` | `true` lets Jarvis open a web address in that program (browsers) |
| `aliases` | Other names you might say |
| `uri` | A fixed launcher link. Only `steam:`, `com.epicgames.launcher:` and `spotify:` links are allowed |
| `uri_template` | Like `uri`, with `{q}` replaced by a short search text |

The same list decides what `close_app` and `running_apps` (in `pc_control`) can see and close.

### Spotify

Needs a **Premium** account and the Spotify **desktop app** (installed from spotify.com).

1. Go to <https://developer.spotify.com/dashboard> and **Create app**.
2. Add this exact **Redirect URI**: `http://127.0.0.1:8888/callback`
3. Under **User Management**, add the email of your Spotify account.
4. Copy the **Client ID** and **Client secret** into `.env`:

   ```
   OPENJARVIS_SPOTIFY_CLIENT_ID=...
   OPENJARVIS_SPOTIFY_CLIENT_SECRET=...
   ```

5. Restart Jarvis, then authorize once:

   ```powershell
   .\jarvis-terminal.ps1 connect spotify
   ```

   Your browser opens; log in and accept. Jarvis stores the tokens in `~/.openjarvis/connectors/spotify.json` and refreshes them by itself.

Try: *"Jarvis, play [your favorite artist]"*. If Spotify is closed, Jarvis starts it minimized (it does not take focus from your game), pauses a YouTube video that was playing, and plays on your PC.

The first time, Jarvis also builds a list of the artists you listen to (from your liked songs and recent plays) so it spells names correctly. You can add names by hand, one per line, in `~/.openjarvis/music_vocab_extra.txt`.

### Gmail and Google Calendar

1. Open <https://console.cloud.google.com/> and create a project.
2. **APIs & Services > Library**: enable the **Gmail API** and the **Google Calendar API**.
3. **APIs & Services > OAuth consent screen**: choose *External*, fill the basics, and add **your own Google account as a Test user**.
4. **APIs & Services > Credentials > Create credentials > OAuth client ID**, application type **Desktop app**. Copy the Client ID and Client secret.
5. Authorize once:

   ```powershell
   .\jarvis-terminal.ps1 connect gmail
   ```

   Paste the Client ID and Client secret when asked; the browser opens to approve. The same approval also covers Calendar, Drive, Contacts and Tasks.

Try: *"Jarvis, what is on my calendar today?"*, *"read my unread emails"*, *"schedule a meeting tomorrow at 5 with a Meet link"*.

### Weather

1. Create a free account at <https://openweathermap.org/api> and copy your API key.
2. Add it to `.env`:

   ```
   OPENWEATHERMAP_API_KEY=...
   ```

New OpenWeatherMap keys can take a couple of hours to activate.

### Instagram

Needs an Instagram **professional** account (Business or Creator).

1. Create an app at <https://developers.facebook.com/> and add the **Instagram API with Instagram Login** product.
2. Add your Instagram account as a tester and generate a **long-lived access token** (it lasts about 60 days).
3. Add it to `.env`:

   ```
   INSTAGRAM_ACCESS_TOKEN=...
   INSTAGRAM_USER_ID=...        # optional; defaults to the account that owns the token
   ```

The token expires, so renew it about every two months.

### Viral videos (YouTube + video analysis)

1. In <https://console.cloud.google.com/> (the same project works), enable **YouTube Data API v3** and create an **API key** under Credentials.
2. Add it to `.env`:

   ```
   YOUTUBE_API_KEY=...
   ```

3. Install `ffmpeg` so videos can be analyzed: `winget install Gyan.FFmpeg`. If Jarvis cannot find it, set `FFMPEG_PATH` in `.env` to the full path of `ffmpeg.exe`.

Try: *"Jarvis, find viral videos about [topic]"* and then *"analyze the first one"*. Analysis works on public videos up to 3 minutes (YouTube, Instagram Reels, TikTok, X) and uses your same Gemini key.

### X (Twitter) analytics

This uses files you export yourself, so there is no paid API.

1. In X, open **Analytics** and export your posts as CSV (or request your data archive).
2. Put the files in `~/.openjarvis/x_exports/`.
3. Ask: *"Jarvis, summarize my X exports"* or *"which were my best posts by impressions?"*.

The analytics CSV has impressions; the data archive only has likes and retweets.

### OBS Studio

Needs OBS 28 or newer, which includes the WebSocket server.

1. In OBS, open **Tools > WebSocket Server Settings** and tick **Enable WebSocket server** (default port 4455).
2. If you set a password, nothing else is needed: Jarvis reads OBS's own config file.

Try: *"Jarvis, start recording"*, *"switch to the gaming scene"*, *"mute my mic"*. Going **live** only happens when you explicitly ask for it.

### PC control and installing programs

Nothing to configure.
- `pc_control` handles volume, mute, lock, screenshots (saved in `Pictures\Jarvis`), system status, closing approved apps, and sleep/shutdown/restart (the last three always need your explicit confirmation).
- `install_app` uses `winget` (included in Windows 11 and recent Windows 10). It shows you the match and asks before installing anything.

### Make it yours (persona and the author-specific tools)

- **Personality and memory.** Create `SOUL.md` (who Jarvis is and how it talks), `USER.md` (facts about you) and `MEMORY.md` (things to remember) in `~/.openjarvis/`. They are added to the assistant's instructions automatically. A long `SOUL.md` is cut in the middle unless you raise `soul_max_chars` in the `[system_prompt]` block of `config.toml` (the example file already sets 24000).
- **Author-specific text.** Several tool descriptions refer to the original author (for example "Sothe's PC"). Replace those texts in `src/openjarvis/tools/` with your own name if you like; it only affects wording.
- **`optimizer_info` and `content_memory`.** `optimizer_info` reads the data of the author's own Windows optimizer, from the folder in `SOTHE_OPTIMIZER_DIR`. Unless you have a project with the same file layout, ignore it, or adapt it to read your own product's data. `content_memory` works for anyone: it is a local library of ideas and scripts.

## 8. Where everything lives

| What | Where |
|---|---|
| Your keys | `<repo>\.env` (never committed) |
| Settings and data | `C:\Users\<you>\.openjarvis\` |
| Main config | `~\.openjarvis\config.toml` |
| Approved apps | `~\.openjarvis\apps.json` |
| Google / Spotify login tokens | `~\.openjarvis\connectors\*.json` |
| X exports | `~\.openjarvis\x_exports\` |
| Persona files | `~\.openjarvis\SOUL.md`, `USER.md`, `MEMORY.md` |
| Artist list | `~\.openjarvis\music_vocab.json` (auto), `music_vocab_extra.txt` (yours) |
| Server log | `~\.openjarvis\server.log` |
| App log | `%LOCALAPPDATA%\Jarvis\app.log` |

All the optional keys in one place (`.env`):

```
GEMINI_API_KEY=                       # required
OPENJARVIS_SPOTIFY_CLIENT_ID=         # Spotify
OPENJARVIS_SPOTIFY_CLIENT_SECRET=     # Spotify
OPENWEATHERMAP_API_KEY=               # weather
INSTAGRAM_ACCESS_TOKEN=               # Instagram
INSTAGRAM_USER_ID=                    # Instagram (optional)
YOUTUBE_API_KEY=                      # viral videos
GEMINI_TTS_STYLE=                     # voice acting direction (optional)
FFMPEG_PATH=                          # only if ffmpeg is not found
SOTHE_OPTIMIZER_DIR=                  # only for optimizer_info
JARVIS_ENGINES=                       # engines checked at startup. Default: cloud,nim (see below)
```

`JARVIS_ENGINES` keeps startup fast: every local AI engine that is not installed (Ollama, vLLM, LM Studio...) costs about 4 seconds of timeout each time Jarvis starts. The launcher defaults it to `cloud,nim`, which is what you need with a Gemini key. **If you run a local engine, set it in `.env`**, for example `JARVIS_ENGINES=ollama,cloud`.

## 9. Check that it works

Try these in order. Each one proves a different piece:

| Say | Proves |
|---|---|
| *"Jarvis, what is two plus two?"* | AI key, voice in, voice out |
| *"Jarvis, set the volume to 30"* | PC control |
| *"Jarvis, open [an app from your apps.json]"* | Approved apps |
| *"Jarvis, play [artist]"* | Spotify, music vocabulary, focus-safe launch |
| *"Jarvis, what is on my calendar today?"* | Google connection |
| *(say something without "Jarvis")* | The privacy filter: it should be ignored |

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| Jarvis says it cannot do something (play music, open apps, read email...) | The tool is not enabled. Check the `[tools] enabled` list in `~\.openjarvis\config.toml` (step 4) and restart |
| "GEMINI_API_KEY is empty" in the console | Check `.env` is in the repo root, has no quotes problems, and restart Jarvis |
| Jarvis does not answer, or says too many requests | You hit the free-tier limit of Gemini. Wait for the quota to reset |
| Microphone does not work | Windows Settings > Privacy > Microphone: allow desktop apps. Close other apps that hold the mic |
| It ignores "Jarvis" | Speak closer to the mic, or set `jarvis.requireName` to `false` (see above) |
| First answer is slow | The Whisper models are being downloaded or loaded; it is a one-time delay per launch |
| Spotify says "No active device" | Open the Spotify desktop app once and log in. The Microsoft Store version is not detected as reliably as the installer from spotify.com |
| Spotify says it needs Premium | Playback control through the API requires a Premium account |
| Spotify "403" error | Add your account under **User Management** in the Spotify dashboard, then run `connect spotify` again |
| Google says "access blocked" | Add your account as a **Test user** on the OAuth consent screen |
| Instagram stops working after ~2 months | The token expired; generate a new one |
| Video analysis fails | Install `ffmpeg` and make sure it is on PATH, or set `FFMPEG_PATH` |
| Tools or wrong behavior after pulling an update | Run `uv sync --extra desktop` again and restart Jarvis |
| Something else | Check `~\.openjarvis\server.log` and `%LOCALAPPDATA%\Jarvis\app.log` |

To turn off the token-saving tool router (for debugging), set `JARVIS_ROUTE_TOOLS=0` in `.env`.

## 11. Keeping your keys safe

- Never commit `.env` or anything in `~/.openjarvis/connectors/`. The repository's `.gitignore` already excludes `.env`.
- If you fork this repo and make it public, check before pushing:

  ```powershell
  git status          # .env must NOT appear
  git log --all -S"<a few characters of your key>" --oneline   # should print nothing
  ```

- If a key ever leaks, **revoke it** in the provider's dashboard and create a new one. Deleting the commit is not enough.
- Prefer a Gemini key with a spending cap or the free tier only.
