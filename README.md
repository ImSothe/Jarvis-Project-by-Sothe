# Jarvis Project by Sothe

A voice-driven personal AI assistant for **Windows** that controls your PC, your music and your social-media analytics, and runs **for free with a single AI key**.

You say *"Jarvis, play Quevedo"* and it opens Spotify and plays it. You say *"Jarvis, turn the volume down"*, *"what's on my calendar today?"* or *"analyze this reel"* and it does it.

Under the hood it is an **AI agent with tools**: a language model (Gemini) decides which tool to use from what you ask, runs it on your machine, and tells you the result.

> **Want your own?** Follow the step-by-step guide in **[SETUP.md](SETUP.md)**: where to put each key, which tools to enable and how to connect Spotify, Google, Instagram and the rest.

> **Credit where it is due.** This project is built on top of the open-source [OpenJarvis](https://github.com/open-jarvis/OpenJarvis) framework (Stanford and contributors, Apache 2.0), which provides the engine, most of the code and most of the git history. My own work is the Windows personal-assistant layer described in [What I added](#what-i-added). See [Origin and credits](#origin-and-credits) for the exact split.

---

## Table of contents

1. [Key features at a glance](#key-features-at-a-glance)
2. [Free: one AI key is all you need](#free-one-ai-key-is-all-you-need)
3. [Origin and credits](#origin-and-credits)
4. [What came with OpenJarvis](#what-came-with-openjarvis)
5. [What was added for Gemini, calls and Google (TenMM2)](#what-was-added-for-gemini-calls-and-google-tenmm2)
6. [What I added](#what-i-added)
7. [Everything Jarvis can do (tool reference)](#everything-jarvis-can-do-tool-reference)
8. [How it works](#how-it-works)
9. [Installation](#installation)
10. [Configuration](#configuration)
11. [Usage](#usage)
12. [Security and privacy](#security-and-privacy)
13. [Limitations](#limitations)
14. [Project structure](#project-structure)
15. [License](#license)

---

## Key features at a glance

- **Hands-free voice**: continuous call mode with real silence detection, a full-screen HUD, interruption by voice (barge-in) and a wake word ("Jarvis").
- **Windows desktop app**: its own window, icon and taskbar identity, single instance, connects by itself on launch.
- **Privacy filter for speech**: a local Whisper model checks that a sentence starts with "Jarvis" *before* any audio is sent to the cloud.
- **Music**: play any artist, track, album or playlist on Spotify, control playback, like songs, and pause the YouTube video that is playing, without minimizing your game.
- **PC control**: volume, lock, screenshots, system status, close apps, sleep/shutdown/restart (with confirmation), OBS, installing programs with `winget`, launching apps and games.
- **Google**: read, search and send Gmail; read, search and create Calendar events with Google Meet links.
- **Content and social**: Instagram insights, X (Twitter) analytics from exported files, viral-video discovery and analysis, and a local content library.
- **Token saver**: a tool router cuts the tool definitions sent on each request from about 13,000 tokens to about 1,800.
- **Smarter music recognition**: learns the artists you listen to so names like *Quevedo* are transcribed and searched correctly.
- **Free to run**: only one free AI key is required.

## Free: one AI key is all you need

This Jarvis was built and tested on the **free tier** of everything. Wherever the original project would use a paid service or its own infrastructure, it has been replaced by a free alternative, so **you only need one free AI key** ([Gemini, from Google AI Studio](https://aistudio.google.com/apikey)) for the core assistant to work.

| Piece | Paid alternative | What Jarvis uses (free) |
|---|---|---|
| Language model | OpenAI, Anthropic... | **Gemini** (free tier) |
| Speech-to-text | Per-minute paid APIs | Gemini, plus a **local Whisper** (`faster-whisper`) for the privacy filter |
| Jarvis's voice | Paid TTS | **Gemini TTS**, or **Kokoro** (fully local) |
| Web search | Tavily, You.com, Serply | **DuckDuckGo**, no key |
| Video analysis | Paid video APIs | `yt-dlp` + the same Gemini key |
| X (Twitter) analytics | The X API (paid) | **Files you export yourself**, no API |
| Instagram and YouTube | - | Official free APIs (optional keys) |
| Gmail and Calendar | - | Google OAuth, free |

On top of that, token usage was reduced so the free quota lasts (see [Token saver](#token-saver-tool-router)).

Honest caveats:
- Gemini's free tier has **usage limits**. If you exceed them, the AI stops answering until the quota resets. Check Google's terms about data use on the free tier.
- Controlling **Spotify** playback through its API requires a **Premium** account. That is a Spotify requirement, not a project one.
- A few optional integrations need their own free key (weather, YouTube, Instagram, Spotify app credentials). They are all optional.

## Origin and credits

This repository is the result of three layers of work, and it matters to say who did which:

1. **[OpenJarvis](https://github.com/open-jarvis/OpenJarvis)** (Stanford and contributors, Apache 2.0): the framework. It is the foundation and the vast majority of the code and commit history. **This is not my work.**
2. **[@TenMM2](https://github.com/TenMM2)**: an adaptation for a final-year project, with Gemini as the engine, the Gmail and Calendar tools (including Google Meet links), the glowing-core interface, hands-free call mode with live silence detection, the wake word, and the full-screen voice screen with barge-in.
3. **Sothe** ([@ImSothe](https://github.com/ImSothe)): the Windows personal-assistant layer in [What I added](#what-i-added).

The full git history is preserved so every contributor keeps their authorship.

## What came with OpenJarvis

OpenJarvis is a modular, open-source framework for personal AI assistants. From the structure of its code, it provides:

- **Agents**: tool-using orchestrator, ReAct, deep research, proactive agent, morning digest, scheduled agents and more.
- **50+ tools**: run code and shell commands, read and write files, git, database queries, browser, web search, calculator, PDF, images, memory and a knowledge base.
- **Connectors**: Gmail, Google Calendar, Drive, Contacts and Tasks, Notion, Obsidian, Slack, Outlook, Strava, Oura, Spotify (read), RSS news and others.
- **30+ channels** to talk to the assistant: Telegram, Discord, WhatsApp, Slack, Signal, Matrix, email, SMS, webchat...
- **Model engines**: Ollama, cloud providers, LiteLLM, NVIDIA NIM and local models.
- **Speech**: speech-to-text and text-to-speech with several providers (local Whisper, Kokoro, Deepgram, Cartesia, OpenAI...).
- **Platform**: task scheduler, MCP support, a security and tool-permission system, telemetry, evaluations, a desktop shell and a React frontend.
- **Persona files**: `SOUL.md`, `MEMORY.md` and `USER.md` in `~/.openjarvis` shape the assistant's personality and memory.

## What was added for Gemini, calls and Google (TenMM2)

- Gemini as the default engine, with native audio for both understanding speech and speaking.
- **Glowing-core interface** and a **full-screen voice HUD** with two color themes (blue and amber).
- **Hands-free call mode**: continuous listening with live silence detection that adapts to background noise, plus a manual fallback (press Space to send now).
- **Barge-in**: you can interrupt Jarvis while it is speaking.
- A browser-based **wake word** ("Jarvis") with no API cost.
- **Gmail and Calendar tools** (see the reference below), including creating events with a Google Meet link.
- A cloud-model picker and fixes for audio playback and error reporting in call mode.

## What I added

### Windows desktop app
- Jarvis opens as **its own app window** (WebView2) with an icon, a single instance, a startup splash and a taskbar identity, not as a browser tab.
- It **does not freeze** when the window is covered or minimized.
- It **connects by itself** on launch, with no button to press, and **the microphone is released when you close the window**.
- Launch from a shortcut, from a hidden background script or from the terminal.
- It does **not** start with Windows unless you set that up yourself.

### Hands-free voice
- **Tolerant wake word**: understands "Jarvis" even when the recognizer writes *yarvis*, *jarbis* or *harvis*.
- **Local privacy and cost filter**: before any audio goes to the cloud, a local Whisper checks that the sentence starts with "Jarvis". If not (the TV, a video, another person), the audio **never leaves your PC**. It runs in two passes (a fast model first, a more accurate one as a fallback) and fails open: if the local model is unavailable, nothing is blocked.
- **Music vocabulary**: learns the artists you listen to (from your liked songs and recent plays) so the speech recognizer spells names like *Quevedo* correctly, and mangled queries such as "Ponquevedos" or "pon que veo" are corrected before searching.
- Saying only "Jarvis" and pausing makes it wait for your request instead of ignoring it.
- It filters out echo of its own voice and ignores noise transcripts.

### Token saver (tool router)
- Every request used to carry all ~67 tool definitions (about 13,000 tokens). Now it sends a small core set plus the tools matching the topic of your request, and the model can load more with a `more_tools` call. A request like *"play Quevedo"* drops from about 13,400 to about 1,800 tokens of tool definitions.
- Disable it with `JARVIS_ROUTE_TOOLS=0`.
- Costly background automations (a daily video-analysis job) are **not part of this repository**. Video analysis stays available whenever you ask for it.

### Spotify
- Plays artists, tracks, albums and playlists found by search, using **text-similarity matching** so a famous but unrelated result does not win.
- Plays your Liked Songs (shuffled or in order), pauses, resumes, skips, changes volume, toggles shuffle, shows what is playing, and saves songs to Liked Songs.
- Starts Spotify **minimized and without stealing focus**, so it does not pull you out of a fullscreen game.
- **Pauses the video** playing in your browser (YouTube...) through Windows media sessions before the music starts.
- Refreshes its own login token and always plays on your PC, never on a speaker or TV in another room.

### PC and app control
See the [tool reference](#everything-jarvis-can-do-tool-reference) for every action.

### Content and social media
Instagram insights, X analytics from exports, viral-video discovery and analysis, a local content library, and a tool that reads a product's real data so the assistant never invents facts about it.

### Quality
New automated tests for the tool router, the speech privacy filter, the music vocabulary, `site_trust` and `x_analytics`.

## Everything Jarvis can do (tool reference)

### Music and media
| Tool | What it does |
|---|---|
| `spotify_play` | Play an artist, track, album or playlist found by search, your Liked Songs, or resume playback. Starts Spotify if it is closed. |
| `spotify_control` | Pause, resume, next, previous, volume (0-100), shuffle, what's playing now, and like a song (the one playing or one found by name). |
| `media_control` | Windows media keys: play/pause, next, previous, stop, volume up/down, mute. Works with any player. |

### PC control
| Tool | What it does |
|---|---|
| `pc_control` | `get_volume`, `set_volume`, `mute`, `unmute`, `lock`, `show_desktop`, `screenshot` (saved to Pictures/Jarvis), `system_status` (CPU, RAM, disk, GPU, uptime, heaviest programs), `running_apps`, `close_app`, and `sleep` / `shutdown` / `restart` / `cancel_shutdown`, which **require explicit confirmation**. |
| `open_app` | Opens desktop apps, games and websites from an **approved list you define**. Browsers can open a URL. |
| `obs_control` | Launch OBS, check its status, start/stop recording, start/stop streaming (only when explicitly asked), list and switch scenes, mute/unmute a microphone. |
| `install_app` | Search, install and check programs with `winget`. Always shows the match first and **asks before installing**. |

### Google
| Tool | What it does |
|---|---|
| `gmail_search_emails` | Search mail with Gmail's own query syntax. |
| `gmail_list_unread` | List unread messages, optionally by label. |
| `gmail_get_thread` | Read a whole conversation. |
| `gmail_send_email` | Compose and send an email (with CC). |
| `calendar_get_events_today` | Today's events. |
| `calendar_search_events` | Search events by keyword. |
| `calendar_next_meeting` | The next upcoming meeting. |
| `calendar_create_event` | Create an event, optionally with a Google Meet link and attendees. |

### Content and social
| Tool | What it does |
|---|---|
| `instagram_account_overview` | Username, followers, following and post count. Read-only. |
| `instagram_recent_posts` | Latest posts and Reels with caption, date, likes and comments. |
| `instagram_post_insights` | Reach, views, likes, comments, shares, saves and interactions for one post. |
| `x_analytics` | Summary and best posts by impressions, engagement, likes, retweets, replies and clicks, from files exported from X. No paid API. |
| `find_viral_videos` | Finds recent short YouTube videos performing far above normal, ranked by views per day (YouTube Data API). |
| `analyze_video` | Studies a public short video (YouTube/Shorts, Instagram Reel, TikTok, X): stats, caption, opening hook, transcript and a description of sampled frames. Used to explain why it works and adapt its *structure*, never to copy its wording. |
| `content_memory` | A local library of ideas, scripts, published posts with metrics and lessons. Add, list, search, update and remove. Nothing leaves the PC. |

### Shopping, weather and knowledge
| Tool | What it does |
|---|---|
| `check_site_trust` | Free trust signals for an online shop: domain age, valid HTTPS certificate, HTTP-to-HTTPS redirect, risky TLDs. A signal, not a verdict. |
| `get_weather` | Current weather and forecast for any city (OpenWeatherMap key required). |
| `optimizer_info` | Reads the real data of a product (tweaks, profiles, features, anti-cheat notes, reversibility) so answers are never made up. |
| `web_search` | Web search through DuckDuckGo by default, no key. |
| `digest_collect` | Gathers recent data from connectors into a summary for a morning digest. |

### Everything else from OpenJarvis
Shell and code execution, file read/write, git, database queries, HTTP requests, browser automation, PDF and image tools, text-to-speech, calculator, memory, knowledge graph, knowledge search and more.

## How it works

1. **You speak.** The browser records until it detects silence.
2. **Local gate.** A local Whisper checks the first seconds of the clip. If it does not start with "Jarvis", the audio is discarded on your PC.
3. **Transcription.** Only the clips that pass are transcribed by Gemini, with a hint of the artists you listen to.
4. **Tool selection.** The tool router picks the tools relevant to the request.
5. **Agent loop.** The model chooses tools, they run on your machine, and the model reads the results.
6. **Reply.** Jarvis answers with a synthesized voice, and you can interrupt it.

## Installation

Designed for **Windows 10/11**.

You need:
- [Python 3.10-3.13](https://www.python.org/) and [uv](https://docs.astral.sh/uv/) (`winget install astral-sh.uv`).
- [Node.js 18+](https://nodejs.org/) for the interface.
- A **free Gemini key**: <https://aistudio.google.com/apikey>.

```powershell
git clone https://github.com/ImSothe/Jarvis-Project-by-Sothe.git
cd Jarvis-Project-by-Sothe

# Backend (creates .venv and installs everything)
uv sync --extra desktop

# Interface
cd frontend
npm install
cd ..
```

The first time speech is used, the Whisper models are downloaded (about 150 MB for the fast one and about 460 MB for the accurate one).

## Configuration

> The short version is below. The full walkthrough, with step-by-step instructions for every integration, is in **[SETUP.md](SETUP.md)**.

1. Copy the template and add your key. **This is the only required key.**

   ```powershell
   copy .env.example .env
   ```

   ```
   GEMINI_API_KEY=your_key_here
   ```

   `.env` is in `.gitignore` and is never committed.

2. Optional, depending on what you want to use:

   | Variable | Purpose |
   |---|---|
   | `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID` | Instagram stats (professional account) |
   | `YOUTUBE_API_KEY` | Viral-video search (free YouTube Data API key) |
   | `OPENJARVIS_SPOTIFY_CLIENT_ID`, `OPENJARVIS_SPOTIFY_CLIENT_SECRET` | Spotify control (free app in Spotify for Developers) |
   | `OPENWEATHERMAP_API_KEY` | Weather (free OpenWeatherMap key) |
   | `SOTHE_OPTIMIZER_DIR` | Folder read by `optimizer_info` |

3. **Enable the tools.** Out of the box the agent can only use `think`, `calculator` and `web_search`. Copy the ready-made list that turns on all the Jarvis features:

   ```powershell
   mkdir $env:USERPROFILE\.openjarvis -Force
   copy config.example.toml $env:USERPROFILE\.openjarvis\config.toml
   ```

4. For Gmail, Calendar or Spotify, authorize your account once:

   ```powershell
   .\jarvis-terminal.ps1 connect gmail
   .\jarvis-terminal.ps1 connect spotify
   ```

5. The instructions and tools are written for **a single user** (the author). If you use it yourself, adapt the texts in `src/openjarvis/tools/` and your approved-apps list in `~/.openjarvis/apps.json`.

## Usage

```powershell
.\start-jarvis.ps1          # starts the server and the interface
.\make-jarvis-shortcut.ps1  # creates the "Jarvis" shortcut on the desktop and Start menu
```

Open the app and say, for example:

- *"Jarvis, play Quevedo."*
- *"Jarvis, set the volume to 40."*
- *"Jarvis, open Discord."*
- *"Jarvis, what do I have on my calendar today?"*
- *"Jarvis, analyze this reel."*

Sentences that do **not** start with "Jarvis" are ignored.

Two advanced switches (disable auto-connect, answer without the wake word) are explained in [SETUP.md](SETUP.md#6-turn-on-voice).

## Security and privacy

- Keys live in `.env` (ignored by git). Google and Spotify tokens are stored in your user folder (`~/.openjarvis/connectors`), outside the repository.
- Sensitive actions (shutdown, restart, installing programs, going live on a stream) **require explicit confirmation**.
- Only apps on the **approved list** can be launched.
- The microphone is only open while the Jarvis window is open.
- The local filter avoids sending audio that is not addressed to Jarvis to the cloud.
- Before this repository was published, the working tree and the entire git history were checked for API keys and personal data.

## Limitations

- The PC, Spotify, OBS and `winget` tools are **Windows-only**.
- Voice relies on Gemini cloud services, which have usage limits on the free tier.
- The tool router is keyword-based: when it misses, the model can load more tools with `more_tools` at the cost of one extra turn.
- The local filter can ignore a "Jarvis" spoken in a very noisy room or far from the microphone.
- Part of the test suite inherited from OpenJarvis fails on Windows for reasons unrelated to this project.

## Project structure

| Path | Contents |
|---|---|
| `SETUP.md` | Step-by-step guide to configure your own Jarvis |
| `config.example.toml` | Example config that enables all the tools (copy to `~/.openjarvis/config.toml`) |
| `jarvis_app.pyw` | Desktop app (WebView2 window) |
| `start-jarvis.ps1`, `make-jarvis-shortcut.ps1` | Launch scripts and shortcuts |
| `src/openjarvis/tools/` | Tools (`spotify_control`, `open_app`, `pc_control`, `obs_control`, `install_app`, `instagram`, `x_analytics`, `site_trust`, `music_vocab`...) |
| `src/openjarvis/agents/tool_router.py` | Tool router |
| `src/openjarvis/speech/name_gate.py` | Local "Jarvis" filter |
| `frontend/` | Web interface (React) |
| `tests/` | Tests |

## License

Distributed under the **Apache 2.0** license (see [LICENSE](LICENSE)), the same as OpenJarvis. The copyright and attribution notices of the original project and its contributors are preserved.
