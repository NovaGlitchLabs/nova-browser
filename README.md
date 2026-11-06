# ✦ Nova Browser

*by [NovaGlitchLabs](https://github.com/NovaGlitchLabs)*

A fun, very customizable web browser for Windows, written in Python (PyQt6 + Qt WebEngine, the same engine as Chrome).
It has a games hub, a hub for following sports and anime, offline voice control, mouse gestures, Game Mode and a lot more.

> **Hobby project.** Nova Browser is a side project. It isn't meant to replace Chrome, Edge or Firefox for banking or anything
> sensitive. Security fixes come from the PyQt6-WebEngine package, so keep it up to date (`pip install -U PyQt6-WebEngine`).

<!-- Add your own screenshots to docs/screenshots/ and uncomment these lines:
![Start page](docs/screenshots/start-page.png)
![Games hub](docs/screenshots/games.png)
![Following hub](docs/screenshots/following.png)
-->

## ✨ Features

**Browsing**
- Tabs, private tabs, split view, floating always-on-top tabs, reader mode, screenshots, save as PDF
- ⌘ Command palette (Ctrl+K) that finds every command, tab, bookmark and game
- Built-in 🛡 ad & tracker blocker, dark mode for any website, focus mode, screen time
- 🧠 Tab manager (Shift+Esc): memory use per tab, sleep, wake or close tabs, plus a live memory meter

**Make it yours**
- 🎨 260+ options: style packs, live wallpapers (constellation, matrix rain, aurora, synthwave, your own video…), start page widgets, tab shapes, fonts
- 🏆 XP, levels and 32 badges that unlock exclusive style packs

**🎮 Games hub**
- 12 free games built in (Snake, Starfall Blocks, 2048, Brick Breaker, Space Rocks, Four in a Row, …), working offline
- Link the games you own (Steam & Epic auto-detect, Steam library import) for patch notes and one-click launch
- Free games of the week, and 💸 a deals wishlist with price-drop alerts across Steam, Epic, GOG, Humble and more

**📣 Following hub**
- Follow teams and leagues (live scores and alerts), YouTube channels, subreddits, any website, news topics
- 📺 Anime tracker: new-episode alerts, countdowns, and a button that jumps to your next episode on Crunchyroll
- You choose everything you follow, and every item and alert has its own on/off switch

**Power features**
- 🕹 Game Mode: when a game starts it sleeps tabs, mutes and pauses media and holds alerts, then switches off when you're done
- 🖱 Mouse gestures: hold right-click and draw (← back, ↓→ close tab, ↑↓ reload, … all changeable)
- 🎯 Zapper (Alt+Z): click annoying popups and banners to hide them on that site for good
- 📌 Sidebar apps: Discord, YouTube Music, WhatsApp and your own sites beside your tabs (Alt+B)
- 🎤 Voice control: push-to-talk (Ctrl+Shift+Space) or a "hey browser" wake word. It runs **offline**, so your voice never leaves your PC
- ❓ Built-in welcome tour and searchable help page (F1)

## 🚀 Install & run

You need **Windows 10/11** and **Python 3.10 or newer** ([python.org](https://www.python.org/downloads/); tick "Add Python to PATH").

```bat
git clone https://github.com/NovaGlitchLabs/nova-browser.git
cd nova-browser
pip install -r requirements.txt
```

Or skip Python entirely: download the installer from [Releases](https://github.com/NovaGlitchLabs/nova-browser/releases).
Windows may show "Windows protected your PC" because the app isn't signed with a paid certificate. Click **More info → Run anyway**.

Then double-click **`start_nova_browser.bat`** (opens with no console window), or run `pythonw nova_browser.pyw`.

The first time, a short welcome tour shows you around. Press **F1** any time for help.

### Make a real app (.exe) and installer
1. Double-click **`build_app.bat`**. It installs the build tools and creates `dist\Nova Browser\Nova Browser.exe`.
2. Optional: open `nova_browser_installer.iss` in [Inno Setup](https://jrsoftware.org/isinfo.php) and press Compile to get `NovaBrowserSetup.exe`.

### Voice control (optional)
Press the 🎤 button. A one-time setup installs two small add-ons (`vosk`, `sounddevice`) and downloads a free English
speech model (40 MB, or a more accurate 128 MB one). After that it works offline.

## 📁 Where your stuff is kept
Everything (settings, bookmarks, history, the things you follow, XP) is stored on your PC in `%USERPROFILE%\.nova_browser`.
Nothing is uploaded anywhere. Your optional Steam Web API key is stored there too, and it's only sent to Steam.

## 🌐 Data sources
The hubs use free public data. These sources can change or stop working at any time, and Nova Browser isn't affiliated with any of them:
ESPN's public (unofficial) scores & news feeds · YouTube & Reddit RSS feeds · Google News RSS · Steam store/news API ·
Epic Games free-games feed · [AniList](https://anilist.co) · [CheapShark](https://www.cheapshark.com) ·
speech recognition by [Vosk](https://alphacephei.com/vosk/).

## ✦ Nova integration (optional)
Nova Browser was made alongside **Nova**, a personal desktop assistant. It works fully **without** her.
If you run your own Jarvis-style assistant, see [`nova-integration/`](nova-integration/) for the two code sections that connect it
(side panel, page summaries, voice control). Turn Nova features off in 🎨 Customize → Nova.

## 📂 Files
| File | What it is |
|---|---|
| `nova_browser.pyw` | The browser |
| `nova_hub.py` | 🎮 Games and 📣 Following hubs, XP & badges |
| `nova_extras.py` | Game Mode, tab manager, gestures, zapper, sidebar apps, voice control |
| `start_nova_browser.bat` | Starts it with no console window |
| `build_app.bat`, `nova_browser_installer.iss` | Build the .exe and the installer |

Keep `nova_browser.pyw`, `nova_hub.py` and `nova_extras.py` in the same folder.

## 📝 License
[MIT](LICENSE): free to use, change and share.
