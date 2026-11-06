"""
nova_hub.py - the 🎮 Games hub and 📣 Following hub for Nova Browser.

Keep this file in the same folder as nova_browser.pyw (build_app.bat picks it up automatically).
Everything you follow is your own choice: nothing is followed until you pick it, and every hub,
item and alert can be switched on or off.

Free data sources (no accounts needed):
  ESPN public scores/news feeds, YouTube channel feeds, Reddit feeds, any website's RSS/Atom feed,
  Google News topic feeds, Steam news + store search, Epic Games free-games list,
  AniList (anime episodes), CheapShark (game prices across stores).

Also here: XP, levels and badges (all stored only on this PC).
"""
import os
import sys
import re
import json
import time
import html
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QUrl, QFile, QIODevice, QByteArray
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")
ESPN = "https://site.api.espn.com/apis/site/v2/sports/"
MAX_BYTES = 6 * 1024 * 1024

# key, name, ESPN path, emoji, has teams to follow
LEAGUES = [
    ("nfl", "NFL", "football/nfl", "🏈", True),
    ("nba", "NBA", "basketball/nba", "🏀", True),
    ("mlb", "MLB", "baseball/mlb", "⚾", True),
    ("nhl", "NHL", "hockey/nhl", "🏒", True),
    ("wnba", "WNBA", "basketball/wnba", "🏀", True),
    ("college-football", "College Football", "football/college-football", "🏈", True),
    ("mens-college-basketball", "Men's College Basketball", "basketball/mens-college-basketball", "🏀", True),
    ("womens-college-basketball", "Women's College Basketball", "basketball/womens-college-basketball", "🏀", True),
    ("mls", "MLS", "soccer/usa.1", "⚽", True),
    ("nwsl", "NWSL", "soccer/usa.nwsl", "⚽", True),
    ("epl", "Premier League", "soccer/eng.1", "⚽", True),
    ("laliga", "La Liga", "soccer/esp.1", "⚽", True),
    ("seriea", "Serie A", "soccer/ita.1", "⚽", True),
    ("bundesliga", "Bundesliga", "soccer/ger.1", "⚽", True),
    ("ligue1", "Ligue 1", "soccer/fra.1", "⚽", True),
    ("ucl", "Champions League", "soccer/uefa.champions", "⚽", True),
    ("ligamx", "Liga MX", "soccer/mex.1", "⚽", True),
    ("f1", "Formula 1", "racing/f1", "🏎️", False),
    ("ufc", "UFC", "mma/ufc", "🥊", False),
    ("pga", "PGA Tour", "golf/pga", "⛳", False),
    ("atp", "ATP Tennis", "tennis/atp", "🎾", False),
    ("wta", "WTA Tennis", "tennis/wta", "🎾", False),
]
LEAGUE = {k: {"key": k, "name": n, "path": p, "emoji": e, "teams": t} for k, n, p, e, t in LEAGUES}

KIND_ICON = {"team": "🏟", "league": "🏆", "youtube": "▶️", "reddit": "👽", "rss": "📰", "topic": "🔎", "anime": "📺"}
SOURCE_SUGGESTIONS = ["@ESPN", "@NBA", "@NFL", "@MLB", "@NHL", "@F1", "@houseofhighlights",
                      "r/nba", "r/nfl", "r/soccer", "r/baseball", "r/hockey", "r/formula1", "r/gaming", "r/pcgaming"]
WEB_GAME_SITES = [
    ("Lichess", "https://lichess.org", "♟️", "Free, ad-free chess against players or the computer."),
    ("Poki", "https://poki.com", "🕹️", "Hundreds of free games that run right in the browser."),
    ("CrazyGames", "https://www.crazygames.com", "🎯", "Big library of free browser games."),
    ("itch.io web games", "https://itch.io/games/platform-web", "🧪", "Indie games you can play in the browser."),
    ("Armor Games", "https://armorgames.com", "🛡️", "Classic free web games."),
    ("Newgrounds", "https://www.newgrounds.com/games", "🔥", "Indie and classic web games."),
    ("Slither.io", "https://slither.io", "🐍", "Multiplayer snake battles."),
    ("Krunker", "https://krunker.io", "🔫", "Fast browser shooter."),
    ("Shell Shockers", "https://shellshock.io", "🥚", "Egg-themed multiplayer shooter."),
    ("Wordle", "https://www.nytimes.com/games/wordle", "🟩", "The daily five-letter word puzzle."),
]

STEAM_SKIP = re.compile(r"redistributable|proton|steam linux runtime|steamvr|steamworks|dedicated server|\bsdk\b|soundtrack",
                        re.I)


# ============================================================================== helpers
def now():
    return time.time()


def parse_time(s):
    """ISO 8601 / RFC 822 / epoch -> epoch seconds (0 if unknown)."""
    if s is None or s == "":
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}", s):
            s2 = s.replace("Z", "+00:00")
            s2 = re.sub(r"\.(\d{1,6})\d*", lambda m: "." + m.group(1).ljust(6, "0"), s2)
            dt = datetime.fromisoformat(s2)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        return parsedate_to_datetime(s).timestamp()
    except Exception:
        return 0.0


def clean_text(s, limit=240, bbcode=False):
    """Plain text from HTML (and Steam's [b]BBCode[/b] when bbcode=True), shortened."""
    s = str(s or "")
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    if bbcode:
        s = re.sub(r"\[/?[a-zA-Z0-9*]+(=[^\]]*)?\]", " ", s)
    s = html.unescape(s)
    s = re.sub(r"https?://\S+", " ", s) if len(s) > 400 else s
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= limit else s[:limit - 1].rsplit(" ", 1)[0] + "…"


def safe_url(u):
    u = str(u or "").strip()
    return u if re.match(r"^https?://", u, re.I) else ""


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:80] or "x"


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def child_text(node, *names):
    for c in node:
        if local(c.tag) in names:
            return (c.text or "").strip()
    return ""


# ============================================================================== feed parsing (RSS + Atom)
def parse_feed(data):
    """RSS 2.0 / RDF / Atom bytes or text -> {"title", "link", "items": [...]}."""
    if isinstance(data, str):
        data = data.encode("utf-8", "replace")
    root = ET.fromstring(data)
    kind = local(root.tag).lower()
    items, title, link = [], "", ""
    if kind == "feed":                                          # Atom (YouTube, Reddit, many blogs)
        title = child_text(root, "title")
        for c in root:
            if local(c.tag) == "link" and c.get("rel", "alternate") == "alternate":
                link = c.get("href", "")
        entries = [c for c in root if local(c.tag) == "entry"]
        for e in entries:
            url, img, vid = "", "", ""
            for c in e:
                n = local(c.tag)
                if n == "link" and (c.get("rel", "alternate") == "alternate") and not url:
                    url = c.get("href", "")
                elif n == "videoId":
                    vid = (c.text or "").strip()
            for d in e.iter():
                if local(d.tag) == "thumbnail" and d.get("url"):
                    img = d.get("url")
                    break
            if vid and not img:
                img = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
            summary = child_text(e, "summary") or child_text(e, "content")
            if not summary:
                for d in e.iter():
                    if local(d.tag) == "description" and d.text:
                        summary = d.text
                        break
            if not img:
                m = re.search(r'<img[^>]+src="([^"]+)"', summary or "")
                img = html.unescape(m.group(1)) if m else ""
            items.append({"id": child_text(e, "id") or url, "title": clean_text(child_text(e, "title"), 200),
                          "url": url, "time": parse_time(child_text(e, "published") or child_text(e, "updated")),
                          "summary": clean_text(summary), "image": safe_url(img)})
    else:                                                       # RSS 2.0 / RDF
        chan = None
        for c in root.iter():
            if local(c.tag) == "channel":
                chan = c
                break
        if chan is not None:
            title = child_text(chan, "title")
            link = child_text(chan, "link")
        for it in root.iter():
            if local(it.tag) != "item":
                continue
            url = child_text(it, "link") or child_text(it, "guid")
            img = ""
            for d in it.iter():
                n = local(d.tag)
                if n in ("thumbnail", "content") and d.get("url") and (n == "thumbnail" or (d.get("medium") == "image"
                                                                                           or "image" in (d.get("type") or ""))):
                    img = d.get("url")
                    break
                if n == "enclosure" and "image" in (d.get("type") or ""):
                    img = d.get("url")
                    break
            desc = child_text(it, "description") or child_text(it, "encoded")
            if not img:
                m = re.search(r'<img[^>]+src="([^"]+)"', desc or "")
                img = html.unescape(m.group(1)) if m else ""
            items.append({"id": child_text(it, "guid") or url, "title": clean_text(child_text(it, "title"), 200),
                          "url": url, "time": parse_time(child_text(it, "pubDate") or child_text(it, "date")),
                          "summary": clean_text(desc), "image": safe_url(img),
                          "source": child_text(it, "source")})
    return {"title": clean_text(title, 120), "link": link, "items": [i for i in items if i["title"] and safe_url(i["url"])]}


def find_feed_links(page_html, base):
    out = []
    for m in re.finditer(r"<link\b[^>]*>", page_html or "", re.I):
        tag = m.group(0)
        if re.search(r'type=["\']application/(rss|atom)\+xml["\']', tag, re.I):
            h = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
            if h:
                out.append(urllib.parse.urljoin(base, html.unescape(h.group(1))))
    return out


def looks_like_feed(text):
    head = (text or "")[:1500].lower()
    return "<rss" in head or "<feed" in head or "<rdf:rdf" in head


def google_news_feed(query):
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})


# ============================================================================== ESPN parsing
def _team_obj(t):
    t = t or {}
    logo = t.get("logo") or ""
    if not logo and t.get("logos"):
        logo = (t["logos"][0] or {}).get("href", "")
    return {"id": str(t.get("id", "")), "abbr": t.get("abbreviation") or "", "name": t.get("displayName") or t.get("name") or "",
            "short": t.get("shortDisplayName") or t.get("name") or "", "logo": safe_url(logo),
            "color": re.sub(r"[^0-9a-fA-F]", "", str(t.get("color") or ""))[:6]}


def _score(v):
    if isinstance(v, dict):
        return str(v.get("displayValue") or v.get("value") or "")
    return "" if v is None else str(v)


def _event_link(ev):
    for l in ev.get("links") or []:
        rel = l.get("rel") or []
        if "desktop" in rel and ("event" in rel or "summary" in rel) and safe_url(l.get("href")):
            return l["href"]
    for l in ev.get("links") or []:
        if safe_url(l.get("href")):
            return l["href"]
    return ""


def parse_espn_event(ev, league):
    """One ESPN event -> a game (two teams) or an event (race, fight card, tournament)."""
    comps = ev.get("competitions") or [{}]
    comp = comps[0] or {}
    status = comp.get("status") or ev.get("status") or {}
    stype = status.get("type") or {}
    state = stype.get("state") or ("post" if stype.get("completed") else "pre")
    g = {"id": str(ev.get("id", "")), "league": league, "name": ev.get("name") or "", "short": ev.get("shortName") or "",
         "time": parse_time(ev.get("date") or comp.get("date")), "state": state,
         "detail": stype.get("shortDetail") or stype.get("detail") or stype.get("description") or "",
         "link": _event_link(ev)}
    competitors = comp.get("competitors") or []
    sides = {c.get("homeAway"): c for c in competitors if c.get("homeAway") in ("home", "away")}
    if len(competitors) == 2 and len(sides) == 2:
        g["type"] = "game"
        for side in ("home", "away"):
            c = sides[side]
            team = _team_obj(c.get("team"))
            team["score"] = _score(c.get("score"))
            team["winner"] = bool(c.get("winner"))
            rec = c.get("records") or c.get("record") or []
            if isinstance(rec, list) and rec:
                team["record"] = (rec[0] or {}).get("summary", "")
            g[side] = team
    else:
        g["type"] = "event"
    return g


def parse_espn_scoreboard(data, league):
    out = []
    for ev in (data or {}).get("events") or []:
        try:
            out.append(parse_espn_event(ev, league))
        except Exception:
            continue
    return out


def parse_espn_teams(data):
    teams = []
    try:
        for entry in data["sports"][0]["leagues"][0]["teams"]:
            t = _team_obj(entry.get("team"))
            if t["id"] and t["name"]:
                teams.append(t)
    except (KeyError, IndexError, TypeError):
        pass
    return sorted(teams, key=lambda t: t["name"].lower())


def parse_espn_team(data, league):
    t = (data or {}).get("team") or {}
    info = {"record": "", "standing": t.get("standingSummary") or "", "next": None}
    for item in ((t.get("record") or {}).get("items") or []):
        if item.get("type") in ("total", None) or not info["record"]:
            info["record"] = item.get("summary") or info["record"]
            if item.get("type") == "total":
                break
    nxt = t.get("nextEvent") or []
    if nxt:
        try:
            info["next"] = parse_espn_event(nxt[0], league)
        except Exception:
            pass
    return info


def parse_espn_schedule_last(data, league):
    best = None
    for ev in (data or {}).get("events") or []:
        try:
            g = parse_espn_event(ev, league)
        except Exception:
            continue
        if g["state"] == "post" and g["time"] <= now() + 3600 and (best is None or g["time"] > best["time"]):
            best = g
    return best


def parse_espn_news(data, source_id, source_name, league):
    out = []
    for a in (data or {}).get("articles") or []:
        url = safe_url(((a.get("links") or {}).get("web") or {}).get("href"))
        if not url:
            continue
        img = ""
        for im in a.get("images") or []:
            if safe_url(im.get("url")):
                img = im["url"]
                break
        out.append({"id": "espn:" + str(a.get("id") or url), "title": clean_text(a.get("headline"), 200), "url": url,
                    "time": parse_time(a.get("published") or a.get("lastModified")),
                    "summary": clean_text(a.get("description")), "image": img,
                    "source_id": source_id, "source": source_name, "kind": "sports", "league": league})
    return out


# ============================================================================== Steam / Epic parsing
def steam_image(appid):
    return f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg"


def parse_steam_news(data, game):
    out = []
    for n in (((data or {}).get("appnews") or {}).get("newsitems") or []):
        url = safe_url(n.get("url"))
        if not url:
            continue
        out.append({"id": "steam:" + str(n.get("gid") or url), "title": clean_text(n.get("title"), 200), "url": url,
                    "time": float(n.get("date") or 0), "summary": clean_text(n.get("contents"), bbcode=True),
                    "label": n.get("feedlabel") or "", "game_id": game["id"], "game": game["name"],
                    "official": n.get("feedname") == "steam_community_announcements" or "patch" in (n.get("tags") or [])})
    return out


def parse_steam_search(data):
    out = []
    for it in (data or {}).get("items") or []:
        if it.get("type") not in (None, "app", "game"):
            continue
        out.append({"appid": str(it.get("id")), "name": it.get("name") or "", "image": safe_url(it.get("tiny_image"))})
    return [o for o in out if o["appid"].isdigit() and o["name"]]


def parse_epic_free(data):
    out = []
    try:
        els = data["data"]["Catalog"]["searchStore"]["elements"] or []
    except (KeyError, TypeError):
        return out
    for e in els:
        promos = e.get("promotions") or {}

        def offers(key):
            for group in promos.get(key) or []:
                for o in group.get("promotionalOffers") or []:
                    yield o
        free_now = [o for o in offers("promotionalOffers")
                    if (o.get("discountSetting") or {}).get("discountPercentage") == 0]
        price = ((e.get("price") or {}).get("totalPrice") or {})
        free_soon = [o for o in offers("upcomingPromotionalOffers")
                     if (o.get("discountSetting") or {}).get("discountPercentage") == 0]
        if free_now and price.get("discountPrice") == 0:
            offer, is_now = free_now[0], True
        elif free_soon:
            offer, is_now = free_soon[0], False
        else:
            continue
        slug_ = ""
        for m in ((e.get("catalogNs") or {}).get("mappings") or []) + (e.get("offerMappings") or []):
            if m.get("pageSlug"):
                slug_ = m["pageSlug"]
                break
        slug_ = slug_ or e.get("productSlug") or ""
        if slug_ and "[" in slug_:
            slug_ = ""
        imgs = {i.get("type"): i.get("url") for i in e.get("keyImages") or []}
        img = imgs.get("OfferImageWide") or imgs.get("DieselStoreFrontWide") or imgs.get("Thumbnail") or imgs.get("OfferImageTall") or ""
        out.append({"id": "epic:" + str(e.get("id")), "title": e.get("title") or "", "summary": clean_text(e.get("description"), 160),
                    "url": f"https://store.epicgames.com/en-US/p/{slug_}" if slug_ else "https://store.epicgames.com/en-US/free-games",
                    "image": safe_url(img), "start": parse_time(offer.get("startDate")), "end": parse_time(offer.get("endDate")),
                    "now": is_now, "worth": price.get("originalPrice") or 0})
    out.sort(key=lambda g: (not g["now"], g["start"]))
    return out


def parse_steam_owned(data):
    games = (((data or {}).get("response") or {}).get("games") or [])
    out = [{"appid": str(g.get("appid")), "name": g.get("name") or f"App {g.get('appid')}",
            "hours": round((g.get("playtime_forever") or 0) / 60, 1)} for g in games if g.get("appid")]
    return sorted(out, key=lambda g: -g["hours"])


def normalize_name(s):
    return re.sub(r"[^a-z0-9]+", "", re.sub(r"[™®©]", "", str(s).lower()))


# ============================================================================== games installed on this PC
def scan_installed_games():
    """Steam + Epic games installed on this PC. Only reads launcher files; changes nothing."""
    found, seen = [], set()
    steam_roots = []
    if sys.platform == "win32":
        try:
            import winreg
            for hive, key, val in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                   (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                                   (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        steam_roots.append(winreg.QueryValueEx(k, val)[0])
                except OSError:
                    pass
        except ImportError:
            pass
        steam_roots += [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"]
    else:
        steam_roots += [os.path.expanduser("~/.steam/steam"), os.path.expanduser("~/.local/share/Steam")]
    libraries = []
    for root in steam_roots:
        p = Path(root)
        if not (p / "steamapps").is_dir():
            continue
        libraries.append(p)
        vdf = p / "steamapps" / "libraryfolders.vdf"
        try:
            for path in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="replace")):
                libraries.append(Path(path.replace("\\\\", "\\")))
        except OSError:
            pass
    lib_seen = set()
    for lib in libraries:
        try:
            key = os.path.normcase(str(lib.resolve()))
        except OSError:
            continue
        if key in lib_seen:
            continue
        lib_seen.add(key)
        for acf in sorted((lib / "steamapps").glob("appmanifest_*.acf")):
            try:
                text = acf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            a = re.search(r'"appid"\s+"(\d+)"', text)
            n = re.search(r'"name"\s+"([^"]+)"', text)
            d_ = re.search(r'"installdir"\s+"([^"]+)"', text)
            if not a or not n or STEAM_SKIP.search(n.group(1)) or ("steam", a.group(1)) in seen:
                continue
            seen.add(("steam", a.group(1)))
            found.append({"source": "steam", "appid": a.group(1), "name": n.group(1),
                          "image": steam_image(a.group(1)), "launch": f"steam://rungameid/{a.group(1)}",
                          "dir": str(lib / "steamapps" / "common" / d_.group(1)) if d_ else ""})
    if sys.platform == "win32":
        man = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
        for item in sorted(man.glob("*.item")) if man.is_dir() else []:
            try:
                j = json.loads(item.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                continue
            name = j.get("DisplayName") or ""
            if not name or j.get("bIsApplication") is False or j.get("bIsIncompleteInstall"):
                continue
            if "addons" in [str(c).lower() for c in j.get("AppCategories") or []] and "games" not in [
                    str(c).lower() for c in j.get("AppCategories") or []]:
                continue
            ns, cid, app = j.get("CatalogNamespace", ""), j.get("CatalogItemId", ""), j.get("AppName", "")
            if ("epic", app) in seen:
                continue
            seen.add(("epic", app))
            launch = ("com.epicgames.launcher://apps/" + urllib.parse.quote(f"{ns}:{cid}:{app}", safe="")
                      + "?action=launch&silent=true") if app else ""
            found.append({"source": "epic", "appid": "", "name": name, "image": "", "launch": launch, "epic_app": app,
                          "dir": str(j.get("InstallLocation") or "")})
    return found


# ============================================================================== anime (AniList, free, no account)
ANILIST = "https://graphql.anilist.co"
ANIME_FIELDS = ("id title{romaji english} format status episodes seasonYear coverImage{large} siteUrl "
                "nextAiringEpisode{episode airingAt}")
ANIME_SEARCH_Q = "query($q:String){Page(perPage:12){media(search:$q,type:ANIME,sort:[SEARCH_MATCH]){" + ANIME_FIELDS + "}}}"
ANIME_INFO_Q = ("query($ids:[Int]){Page(perPage:50){media(id_in:$ids,type:ANIME){" + ANIME_FIELDS +
                " externalLinks{site url} streamingEpisodes{title url site}}}}")


def parse_anime_media(m):
    if not isinstance(m, dict) or not str(m.get("id", "")).isdigit():
        return None
    t = m.get("title") or {}
    title = str(t.get("english") or t.get("romaji") or "Untitled")[:120]
    romaji = str(t.get("romaji") or "")[:120]
    total = m.get("episodes") if isinstance(m.get("episodes"), int) else None
    nxt = m.get("nextAiringEpisode") or {}
    next_ep = nxt.get("episode") if isinstance(nxt.get("episode"), int) else None
    next_at = nxt.get("airingAt") if isinstance(nxt.get("airingAt"), int) else None
    status = str(m.get("status") or "")
    if next_ep:
        aired = next_ep - 1
    elif status == "FINISHED":
        aired = total or 0
    elif status == "NOT_YET_RELEASED":
        aired = 0
    else:
        aired = total
    cr = ""
    for link in m.get("externalLinks") or []:
        if isinstance(link, dict) and str(link.get("site", "")).lower() == "crunchyroll" and safe_url(link.get("url")):
            cr = safe_url(link.get("url"))
            break
    eps = {}
    for e in m.get("streamingEpisodes") or []:
        if not isinstance(e, dict) or str(e.get("site", "")).lower() != "crunchyroll":
            continue
        mm = re.match(r"\s*(?:Episode|Ep\.?)\s*(\d+)", str(e.get("title", "")), re.I)
        u = safe_url(e.get("url"))
        if mm and u:
            eps[str(int(mm.group(1)))] = u
    return {"anilist_id": str(m["id"]), "title": title, "romaji": romaji,
            "format": str(m.get("format") or "").replace("_", " "), "status": status, "total": total,
            "next_ep": next_ep, "next_at": next_at, "aired": aired,
            "year": m.get("seasonYear") if isinstance(m.get("seasonYear"), int) else None,
            "image": safe_url((m.get("coverImage") or {}).get("large")),
            "url": safe_url(m.get("siteUrl")) or f"https://anilist.co/anime/{m['id']}", "cr": cr, "cr_eps": eps}


def parse_anime_page(data):
    media = ((((data or {}) if isinstance(data, dict) else {}).get("data") or {}).get("Page") or {}).get("media") or []
    return [x for x in (parse_anime_media(m) for m in media) if x]


def anime_watch_url(info, ep):
    """Best link for episode `ep`: that episode on Crunchyroll, else the show on Crunchyroll, else a Crunchyroll search."""
    info = info or {}
    u = (info.get("cr_eps") or {}).get(str(ep))
    if u:
        return u
    if info.get("cr"):
        return info["cr"]
    return "https://www.crunchyroll.com/search?q=" + urllib.parse.quote(info.get("romaji") or info.get("title") or "")


# ============================================================================== game deals (CheapShark, free, no account)
CHEAPSHARK = "https://www.cheapshark.com/api/1.0/"
TOP_DEAL_STORES = "1,7,11,25"         # Steam, GOG, Humble, Epic


def cs_price(v):
    try:
        f = round(float(v), 2)
        return f if 0 <= f < 100000 else None
    except (TypeError, ValueError):
        return None


def deal_url(deal_id):
    did = str(deal_id or "")
    if not re.fullmatch(r"[A-Za-z0-9%+/=_.-]{1,200}", did):         # CheapShark's deal ids already come URL-encoded
        did = urllib.parse.quote(did, safe="")
    return "https://www.cheapshark.com/redirect?dealID=" + did


def parse_cs_stores(data):
    out = {}
    for st in data if isinstance(data, list) else []:
        if isinstance(st, dict) and str(st.get("storeID", "")).isdigit():
            out[str(st["storeID"])] = str(st.get("storeName") or "Store")[:40]
    return out


def parse_cs_search(data):
    out = []
    for g in data if isinstance(data, list) else []:
        if not isinstance(g, dict) or not str(g.get("gameID", "")).isdigit():
            continue
        out.append({"gid": str(g["gameID"]), "title": str(g.get("external") or "")[:120], "thumb": safe_url(g.get("thumb")),
                    "cheapest": cs_price(g.get("cheapest")), "steam": str(g.get("steamAppID") or "") if str(g.get("steamAppID") or "").isdigit() else ""})
    return out


def parse_cs_games(data, stores=None):
    """games?ids=… → {gameID: {title, thumb, best, retail, savings, store, deal, lowest}}."""
    out = {}
    stores = stores or {}
    for gid, g in (data.items() if isinstance(data, dict) else []):
        if not str(gid).isdigit() or not isinstance(g, dict):
            continue
        info = g.get("info") or {}
        deals = [d for d in g.get("deals") or [] if isinstance(d, dict) and cs_price(d.get("price")) is not None]
        deals.sort(key=lambda d: cs_price(d.get("price")))
        best = deals[0] if deals else {}
        cpe = g.get("cheapestPriceEver") or {}
        out[str(gid)] = {"title": str(info.get("title") or "")[:120], "thumb": safe_url(info.get("thumb")),
                         "steam": str(info.get("steamAppID") or "") if str(info.get("steamAppID") or "").isdigit() else "",
                         "best": cs_price(best.get("price")), "retail": cs_price(best.get("retailPrice")),
                         "savings": int(round(float(best.get("savings") or 0))) if best else 0,
                         "store": stores.get(str(best.get("storeID", "")), "a store") if best else "",
                         "deal": str(best.get("dealID") or ""), "lowest": cs_price(cpe.get("price"))}
    return out


def parse_cs_deals(data, stores=None):
    out, seen = [], set()
    stores = stores or {}
    for d in data if isinstance(data, list) else []:
        if not isinstance(d, dict) or not d.get("dealID"):
            continue
        title = str(d.get("title") or "")[:120]
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        out.append({"deal": str(d["dealID"]), "title": title, "store": stores.get(str(d.get("storeID", "")), "Store"),
                    "price": cs_price(d.get("salePrice")), "retail": cs_price(d.get("normalPrice")),
                    "savings": int(round(float(d.get("savings") or 0))), "thumb": safe_url(d.get("thumb")),
                    "gid": str(d.get("gameID") or ""), "rating": str(d.get("steamRatingText") or "")[:30],
                    "steam": str(d.get("steamAppID") or "") if str(d.get("steamAppID") or "").isdigit() else ""})
    return out[:24]


# ============================================================================== XP, levels, badges (stored only on this PC)
GAME_GOALS = {"snake": (25, False), "blocks": (3000, False), "fusion": (20000, False), "bricks": (1000, False),
              "flight": (25, False), "mines": (1, False), "memory": (16, True), "paddle": (1, False),
              "rocks": (5000, False), "four": (1, False), "dash": (1000, False), "ttt": (1, False)}


def _goal(game):
    def test(S):
        goal, low = GAME_GOALS[game]
        b = S["best"].get(game)
        return b is not None and (b <= goal if low else b >= goal) and (b > 0 or low)
    return test


BADGES = [
    ("first_game", "🕹", "Player One", "Play any built-in game.", lambda S: len(S["played"]) >= 1),
    ("arcade", "👾", "Arcade Regular", "Play 6 different built-in games.", lambda S: len(S["played"]) >= 6),
    ("all_games", "🏟", "Arcade Master", "Play all 12 built-in games.", lambda S: len(S["played"]) >= 12),
    ("snake", "🐍", "Snake Charmer", "Score 25 in Snake.", _goal("snake")),
    ("blocks", "🧩", "Line Clearer", "Score 3,000 in Starfall Blocks.", _goal("blocks")),
    ("fusion", "🔢", "Fusion Master", "Score 20,000 in Fusion 2048.", _goal("fusion")),
    ("bricks", "🧱", "Wrecking Ball", "Score 1,000 in Brick Breaker.", _goal("bricks")),
    ("flight", "🚀", "Ace Pilot", "Fly through 25 gaps in Nova Flight.", _goal("flight")),
    ("mines", "💣", "Bomb Squad", "Win a game of Mine Sweep.", _goal("mines")),
    ("memory", "🃏", "Photographic", "Finish Memory Cards in 16 moves or fewer.", _goal("memory")),
    ("paddle", "🏓", "Paddle Champ", "Win a Paddle Duel.", _goal("paddle")),
    ("rocks", "☄️", "Rock Breaker", "Score 5,000 in Space Rocks.", _goal("rocks")),
    ("four", "🔴", "Connect Master", "Beat the computer at Four in a Row.", _goal("four")),
    ("dash", "⚡", "Speed Demon", "Run 1,000 m in Neon Dash.", _goal("dash")),
    ("ttt", "❌", "Tic-Tac-Pro", "Beat the computer at Tic-Tac-Toe.", _goal("ttt")),
    ("fan", "🏟", "True Fan", "Follow a team.", lambda S: S["teams"] >= 1),
    ("superfan", "📣", "Superfan", "Follow 10 things.", lambda S: S["follows"] >= 10),
    ("otaku", "📺", "Otaku", "Track an anime.", lambda S: S["anime"] >= 1),
    ("binge", "🍿", "Binge Watcher", "Mark 25 episodes as watched.", lambda S: S["c"].get("anime_ep", 0) >= 25),
    ("collector", "🎮", "Collector", "Link a game you own.", lambda S: S["linked"] >= 1),
    ("library", "📚", "Library Card", "Link 25 games.", lambda S: S["linked"] >= 25),
    ("bargain", "💸", "Bargain Hunter", "Put a game on your deals wishlist.", lambda S: S["wished"] >= 1),
    ("zone", "🕹", "In the Zone", "Use Game Mode.", lambda S: S["c"].get("game_mode", 0) >= 1),
    ("zapper", "🎯", "Exterminator", "Zap 10 annoying things off websites.", lambda S: S["c"].get("zap", 0) >= 10),
    ("wizard", "🖱", "Wizard Hands", "Use 25 mouse gestures.", lambda S: S["c"].get("gesture", 0) >= 25),
    ("voice", "🎙", "Talk to Me", "Control the browser with your voice 10 times.", lambda S: S["c"].get("voice", 0) >= 10),
    ("multitask", "📌", "Multitasker", "Open a sidebar app.", lambda S: S["c"].get("sidebar", 0) >= 1),
    ("reader", "✦", "Speed Reader", "Have Nova summarize 5 pages.", lambda S: S["c"].get("summarize", 0) >= 5),
    ("explorer", "🧭", "Explorer", "Browse 1,000 pages.", lambda S: S["c"].get("page", 0) >= 1000),
    ("streak3", "🔥", "On a Roll", "Use the browser 3 days in a row.", lambda S: S["best_streak"] >= 3),
    ("streak7", "🔥", "Week Warrior", "Use the browser 7 days in a row.", lambda S: S["best_streak"] >= 7),
    ("streak30", "🌋", "Unstoppable", "Use the browser 30 days in a row.", lambda S: S["best_streak"] >= 30),
]
BADGE_XP = 50

# XP each thing gives, and the most you can get from it per day
XP_RULES = {"page": (1, 40, 5), "gesture": (1, 20, 1), "zap": (3, 30, 1), "voice": (2, 40, 1), "game_mode": (10, 20, 1),
            "sidebar": (2, 10, 1), "summarize": (5, 25, 1), "anime_ep": (5, 50, 1), "follow": (5, 50, 1), "link": (5, 50, 1),
            "wish": (5, 25, 1)}
GAMES_DAILY_CAP = 250

# Style packs you unlock by levelling up (only setting values the browser already knows)
REWARD_PACKS = {
    "Arcade": (2, "Neon arcade cabinet look", {
        "theme": "Custom", "custom_accent": "#00e5ff", "base_palette": "OLED Black", "wp_type": "Synthwave grid",
        "wp_color_mode": "Rainbow", "wg_style": "Neon", "tab_shape": "Slanted glow", "sp_logo_style": "Gradient",
        "ui_font": "Bahnschrift", "sp_logo_font": "Impact"}),
    "Champion": (4, "Gold-on-midnight trophy look", {
        "theme": "Custom", "custom_accent": "#ffc940", "base_palette": "Midnight", "wp_type": "Starfield",
        "wp_color_mode": "Accent", "wg_style": "Glass", "sp_logo_style": "Glow", "w_clock_style": "Big"}),
    "Vaporwave": (6, "Pink & purple retro dream", {
        "theme": "Custom", "custom_accent": "#ff71ce", "base_palette": "Plum", "wp_type": "Flowing gradient",
        "wp_color_mode": "Rainbow", "wg_style": "Glass", "sp_logo_style": "Gradient", "tab_shape": "Pill"}),
    "Legend": (8, "Deep violet nebula", {
        "theme": "Custom", "custom_accent": "#b36bff", "base_palette": "OLED Black", "wp_type": "Nebula",
        "wg_style": "Neon", "sp_logo_style": "Gradient", "tab_shape": "Slanted glow", "wp_vignette": True}),
    "Mythic": (10, "Crimson hyperspace", {
        "theme": "Custom", "custom_accent": "#ff4d8d", "base_palette": "Crimson Night", "wp_type": "Hyperspace",
        "wp_color_mode": "Rainbow", "wg_style": "Outline", "sp_logo_style": "Glow"}),
    "Nova Prime": (15, "The final form: rainbow aurora", {
        "theme": "Custom", "custom_accent": "#7cf7ff", "base_palette": "Midnight", "wp_type": "Aurora",
        "wp_color_mode": "Rainbow", "wg_style": "Glass", "sp_logo_style": "Glow", "w_clock_style": "Big"}),
}


def level_floor(level):
    """Total XP needed to reach this level (level 1 = 0, 2 = 100, 3 = 300, 4 = 600 …)."""
    return 50 * (level - 1) * level


def level_for(xp):
    lv = 1
    while level_floor(lv + 1) <= xp:
        lv += 1
    return lv


def today_str(t=None):
    return time.strftime("%Y-%m-%d", time.localtime(t if t is not None else time.time()))


def streak_of(days, today=None):
    """Consecutive days ending today (or yesterday) in a list of 'YYYY-MM-DD'."""
    have = set(days or [])
    t = time.mktime(time.strptime(today or today_str(), "%Y-%m-%d")) + 43200
    if today_str(t) not in have:
        t -= 86400
    n = 0
    while today_str(t) in have:
        n += 1
        t -= 86400
    return n


def best_streak_of(days):
    best = run = 0
    prev = None
    for d in sorted(set(days or [])):
        t = time.mktime(time.strptime(d, "%Y-%m-%d"))
        run = run + 1 if prev is not None and 80000 < t - prev < 93000 else 1
        best = max(best, run)
        prev = t
    return best


# ============================================================================== speakable lines (for Nova's voice answers)
def spoken_when(t):
    lt = time.localtime(t)
    now_lt = time.localtime()
    days = int((time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 12, 0, 0, 0, 0, -1)) -
                time.mktime((now_lt.tm_year, now_lt.tm_mon, now_lt.tm_mday, 12, 0, 0, 0, 0, -1))) // 86400)
    clock = time.strftime("%I:%M %p", lt).lstrip("0").replace(":00 ", " ")
    if days == 0:
        return "today at " + clock
    if days == 1:
        return "tomorrow at " + clock
    if days == -1:
        return "yesterday"
    if 1 < days < 7:
        return time.strftime("%A", lt) + " at " + clock
    return time.strftime("%B ", lt) + str(lt.tm_mday) + (" at " + clock if days > 0 else "")


def spoken_in(seconds):
    s = max(0, int(seconds))
    d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    if d:
        return f"{d} day{'s' if d != 1 else ''}" + (f" and {h} hour{'s' if h != 1 else ''}" if h and d < 3 else "")
    if h:
        return f"{h} hour{'s' if h != 1 else ''}" + (f" and {m} minute{'s' if m != 1 else ''}" if m else "")
    return f"{max(1, m)} minute{'s' if max(1, m) != 1 else ''}"


def team_line(name, g, tid):
    """One sentence about a game of team `tid` (from the team's point of view)."""
    if not g or g.get("type") != "game":
        return ""
    home = g["home"]["id"] == tid
    us, them = (g["home"], g["away"]) if home else (g["away"], g["home"])
    them_n = them.get("short") or them.get("name") or them.get("abbr") or "their opponent"
    if g.get("state") == "in":
        return f"The {name} are playing the {them_n} right now. It's {us.get('score')} to {them.get('score')}, {g.get('detail', '')}.".replace(", .", ".")
    if g.get("state") == "post":
        res = "beat" if us.get("winner") else ("lost to" if them.get("winner") else "played")
        a, b = us.get("score"), them.get("score")
        return f"The {name} {res} the {them_n}, {a} to {b}, {spoken_when(g.get('time', 0))}."
    return f"The {name} play the {them_n} {spoken_when(g.get('time', 0))}."


# ============================================================================== networking
class Net(QObject):
    """Small cached downloader. cb(data, error): data is text, bytes or parsed JSON."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nam = QNetworkAccessManager(self)
        self.cache = {}
        self.waiting = {}

    def post(self, url, payload, cb, ttl=0):
        self.get(url, cb, ttl, "json", {"Accept": "application/json"}, json.dumps(payload, sort_keys=True))

    def get(self, url, cb, ttl=0, mode="json", headers=None, body=None):
        key = (url, mode, body)
        hit = self.cache.get(key)
        if hit and ttl and now() - hit[0] < ttl:
            QTimer.singleShot(0, lambda: cb(hit[1], ""))
            return
        if key in self.waiting:
            self.waiting[key].append(cb)
            return
        self.waiting[key] = [cb]
        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"User-Agent", UA.encode())
        req.setRawHeader(b"Accept-Language", b"en-US,en;q=0.9")
        for k, v in (headers or {}).items():
            req.setRawHeader(k.encode(), v.encode())
        try:
            req.setTransferTimeout(20000)
        except AttributeError:
            pass
        if body is not None:
            req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
            reply = self.nam.post(req, QByteArray(body.encode("utf-8")))
        else:
            reply = self.nam.get(req)
        reply.finished.connect(lambda r=reply, k=key: self._done(k, r))

    def _done(self, key, reply):
        err = ""
        if reply.error() != QNetworkReply.NetworkError.NoError:
            err = reply.errorString() or "network error"
        raw = bytes(reply.readAll())[:MAX_BYTES]
        reply.deleteLater()
        data = None
        if not err:
            try:
                if key[1] == "json":
                    data = json.loads(raw.decode("utf-8", "replace"))
                elif key[1] == "text":
                    data = raw.decode("utf-8", "replace")
                else:
                    data = raw
                self.cache[key] = (now(), data)
            except ValueError:
                err = "unexpected answer"
        if err and key in self.cache:
            data = self.cache[key][1]          # keep showing the last good data
        for cb in self.waiting.pop(key, []):
            try:
                cb(data, err)
            except Exception as e:             # one bad callback must not break the others
                print("[hub] callback error:", e)


# ============================================================================== the hub service
WIDGET_KEYS = ("scores", "followfeed", "gamenews", "anime")
OPTION_WHITELIST = {"hub_games", "hub_follow", "games_free_week", "games_web_sites", "games_deals", "games_top_deals", "xp_on"}
GAME_IDS = {"snake", "blocks", "fusion", "bricks", "flight", "mines", "memory", "paddle", "rocks", "four", "dash", "ttt"}


class HubService(QObject):
    """Keeps everything you follow up to date and raises alerts. One per browser."""
    changed = pyqtSignal()                       # new data for hub pages / start page / badges
    notify = pyqtSignal(str, str, str, str)      # icon, title, body, url
    open_requested = pyqtSignal(str)             # open this web address in a new tab
    game_launched = pyqtSignal(object)           # a linked game was started from the hub (Game Mode)
    pack_requested = pyqtSignal(str)             # apply an unlocked reward style pack
    option_requested = pyqtSignal(str, object)   # change a browser option
    customize_requested = pyqtSignal()

    def __init__(self, data_dir, settings, net=None, parent=None):
        super().__init__(parent)
        self.dir = Path(data_dir)
        self.file = self.dir / "hub.json"
        self.settings = settings                 # callable -> current browser settings dict
        self.net = net if net is not None else Net(self)
        d = {}
        try:
            d = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        d = d if isinstance(d, dict) else {}
        self.follows = [f for f in d.get("follows", []) if isinstance(f, dict) and f.get("id")]
        self.games = [g for g in d.get("games", []) if isinstance(g, dict) and g.get("id")]
        self.seen = d.get("seen", {}) if isinstance(d.get("seen"), dict) else {}
        self.synced = set(d.get("synced", []) or [])
        self.game_states = d.get("game_states", {}) if isinstance(d.get("game_states"), dict) else {}
        self.last_open = {"follow": 0, "games": 0}
        self.last_open.update(d.get("last_open") or {})
        self.state = d.get("state") if isinstance(d.get("state"), dict) else {}
        for k, v in (("teams", {}), ("today", []), ("feed", []), ("game_news", []), ("free", []), ("errors", {}),
                     ("updated", 0), ("anime", {}), ("deals", []), ("stores", {})):
            self.state.setdefault(k, v)
        self.wishlist = [w for w in d.get("wishlist", []) if isinstance(w, dict) and w.get("id")]
        self.xp = d.get("xp") if isinstance(d.get("xp"), dict) else {}
        for k, v in (("total", 0), ("badges", {}), ("c", {}), ("best", {}), ("played", {}), ("days", []), ("day", {}),
                     ("last_game_xp", {})):
            self.xp.setdefault(k, v)
        self.touch_day()
        self.raw = {}
        self.busy = False
        self.again = False
        self.pending = 0
        self.next_full = 0.0
        self.next_live = 0.0
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(1500)
        self.save_timer.timeout.connect(self.save)
        self.timer = QTimer(self)
        self.timer.setInterval(15000)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        QTimer.singleShot(2500, self.tick)

    # ---------------------------------------------------------------- settings helpers
    def opt(self, key, default=None):
        try:
            return self.settings().get(key, default)
        except Exception:
            return default

    def follow_on(self):
        return bool(self.opt("hub_follow", True))

    def games_on(self):
        return bool(self.opt("hub_games", True))

    def find(self, item_id):
        for lst in (self.follows, self.games, self.wishlist):
            for f in lst:
                if f["id"] == item_id:
                    return f
        return None

    # ---------------------------------------------------------------- saving
    def save_soon(self):
        self.save_timer.start()

    def save(self):
        cutoff = now() - 40 * 86400
        self.seen = {k: v for k, v in self.seen.items() if v > cutoff}
        if len(self.seen) > 4000:
            self.seen = dict(sorted(self.seen.items(), key=lambda kv: kv[1])[-4000:])
        self.game_states = {k: v for k, v in self.game_states.items() if v.get("t", 0) > now() - 4 * 86400}
        self.xp["days"] = sorted(set(self.xp.get("days", [])))[-400:]
        data = {"follows": self.follows, "games": self.games, "seen": self.seen, "synced": sorted(self.synced),
                "game_states": self.game_states, "last_open": self.last_open, "state": self.state,
                "wishlist": self.wishlist, "xp": self.xp}
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self.file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, self.file)
        except OSError as e:
            print("[hub] save failed:", e)

    # ---------------------------------------------------------------- refreshing
    def live_active(self):
        t = now()
        for g in self.state.get("today", []):
            if g.get("mine") and (g.get("state") == "in" or (g.get("state") == "pre" and 0 < g.get("time", 0) - t < 20 * 60)):
                return True
        return False

    def tick(self):
        if not (self.follow_on() or self.games_on()):
            return
        t = now()
        if t >= self.next_full:
            self.refresh()
        elif self.follow_on() and self.live_active() and t >= self.next_live:
            self.refresh(live_only=True)

    def refresh(self, live_only=False, force=False):
        if self.busy:
            self.again = True
            return
        self.busy = True
        s = self.settings()
        jobs = []
        k = 0.0 if force else 1.0
        if self.follow_on():
            teams = [f for f in self.follows if f.get("kind") == "team" and f.get("on", True)]
            leagues = {f["league"] for f in teams} | {f["league"] for f in self.follows
                                                      if f.get("kind") == "league" and f.get("on", True)}
            for lg in sorted(leagues):
                if lg in LEAGUE:
                    jobs.append((("score", lg), ESPN + LEAGUE[lg]["path"] + "/scoreboard", 40 * k if live_only else 90 * k, "json"))
            if not live_only:
                for f in teams:
                    if f["league"] not in LEAGUE:
                        continue
                    base = ESPN + LEAGUE[f["league"]]["path"]
                    jobs.append((("team", f["id"]), f"{base}/teams/{f['team_id']}", 900 * k, "json"))
                    jobs.append((("sched", f["id"]), f"{base}/teams/{f['team_id']}/schedule", 1800 * k, "json"))
                    jobs.append((("news", f["id"]), f"{base}/news?team={f['team_id']}&limit=6", 900 * k, "json"))
                for f in self.follows:
                    if not f.get("on", True):
                        continue
                    if f.get("kind") == "league" and f["league"] in LEAGUE:
                        jobs.append((("news", f["id"]), ESPN + LEAGUE[f["league"]]["path"] + "/news?limit=10", 900 * k, "json"))
                    elif f.get("kind") in ("youtube", "reddit", "rss", "topic") and safe_url(f.get("feed")):
                        jobs.append((("feed", f["id"]), f["feed"], 1200 * k, "bytes"))
                ids = sorted({int(f["anilist_id"]) for f in self.follows if f.get("kind") == "anime" and f.get("on", True)
                              and str(f.get("anilist_id", "")).isdigit()})
                for i in range(0, len(ids), 50):
                    jobs.append((("anime", str(i)), ANILIST, 900 * k, "json",
                                 {"query": ANIME_INFO_Q, "variables": {"ids": ids[i:i + 50]}}))
        if self.games_on() and not live_only:
            for g in self.games:
                if not g.get("on", True):
                    continue
                if g.get("appid"):
                    url = ("https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid="
                           f"{g['appid']}&count=4&maxlength=400&format=json")
                    jobs.append((("gnews", g["id"]), url, 1800 * k, "json"))
                else:
                    q = f'"{g["name"]}" (update OR patch OR season)'
                    jobs.append((("gfeed", g["id"]), google_news_feed(q), 3600 * k, "bytes"))
            if s.get("games_free_week", True):
                jobs.append((("free", ""), "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
                                           "?locale=en-US&country=US&allowCountries=US", 6 * 3600 * k, "json"))
            if s.get("games_deals", True) and (self.wishlist or s.get("games_top_deals", True)):
                jobs.append((("cs_stores", ""), CHEAPSHARK + "stores", 86400, "json"))
                gids = [w["gid"] for w in self.wishlist if str(w.get("gid", "")).isdigit()]
                for i in range(0, len(gids), 25):
                    jobs.append((("cs_games", str(i)), CHEAPSHARK + "games?ids=" + ",".join(gids[i:i + 25]), 3600 * k, "json"))
                if s.get("games_top_deals", True):
                    jobs.append((("cs_top", ""), CHEAPSHARK + "deals?" + urllib.parse.urlencode(
                        {"storeID": TOP_DEAL_STORES, "onSale": 1, "pageSize": 30, "sortBy": "Deal Rating", "AAA": 0}),
                        3 * 3600 * k, "json"))
        self.pending = len(jobs)
        if not jobs:
            self._finish(live_only)
            return
        for job in jobs:
            key, url, ttl, mode = job[:4]
            cb = (lambda data, err, key=key, lo=live_only: self._got(key, data, err, lo))
            if len(job) > 4:
                self.net.post(url, job[4], cb, ttl=ttl)
            else:
                self.net.get(url, cb, ttl=ttl, mode=mode)

    def _got(self, key, data, err, live_only):
        self.raw[key] = (data, err)
        self.pending -= 1
        if self.pending <= 0:
            self._finish(live_only)

    def _finish(self, live_only):
        try:
            self.assemble(live_only)
        except Exception as e:
            print("[hub] assemble error:", e)
        t = now()
        if not live_only:
            self.next_full = t + max(5, int(self.opt("hub_refresh", 15) or 15)) * 60
        self.next_live = t + max(20, int(self.opt("hub_live_refresh", 60) or 60))
        self.busy = False
        self.save_soon()
        self.changed.emit()
        if self.again:
            self.again = False
            QTimer.singleShot(200, self.refresh)

    # ---------------------------------------------------------------- building the state
    def assemble(self, live_only=False):
        st = self.state
        errors = {}
        teams = [f for f in self.follows if f.get("kind") == "team"]
        boards = {}
        for (kind, k), (data, err) in self.raw.items():
            if kind == "score":
                if err and not data:
                    errors["league:" + k] = err
                boards[k] = parse_espn_scoreboard(data, k) if data else boards.get(k, [])

        team_info = dict(st.get("teams") or {})
        my_team_ids = {}
        for f in teams:
            my_team_ids.setdefault(f["league"], {})[f["team_id"]] = f
            info = dict(team_info.get(f["id"]) or {})
            if not live_only:
                data, err = self.raw.get(("team", f["id"]), (None, ""))
                if data:
                    info.update(parse_espn_team(data, f["league"]))
                elif err:
                    errors[f["id"]] = err
                data, err = self.raw.get(("sched", f["id"]), (None, ""))
                if data:
                    info["last"] = parse_espn_schedule_last(data, f["league"])
            info["today"] = None
            for g in boards.get(f["league"], []):
                if g.get("type") == "game" and f["team_id"] in (g["home"]["id"], g["away"]["id"]):
                    info["today"] = g
                    break
            team_info[f["id"]] = info
        st["teams"] = {k: v for k, v in team_info.items() if any(f["id"] == k for f in teams)}

        today = []
        followed_leagues = {f["league"] for f in self.follows if f.get("kind") == "league" and f.get("on", True)}
        for lg, games in boards.items():
            for g in games:
                mine = g.get("type") == "game" and any(
                    g[side]["id"] in my_team_ids.get(lg, {}) for side in ("home", "away"))
                if mine or lg in followed_leagues:
                    g = dict(g, mine=mine)
                    today.append(g)
        order = {"in": 0, "pre": 1, "post": 2}
        today.sort(key=lambda g: (not g.get("mine"), order.get(g["state"], 3), g["time"]))
        st["today"] = today[:120]
        self.score_alerts(today, my_team_ids)

        if not live_only:
            feed = []
            for f in self.follows:
                data, err = self.raw.get(("news", f["id"]), (None, ""))
                if f.get("kind") in ("team", "league"):
                    if data:
                        feed += parse_espn_news(data, f["id"], f.get("name", ""), f.get("league", ""))
                    elif err:
                        errors[f["id"]] = err
                data, err = self.raw.get(("feed", f["id"]), (None, ""))
                if f.get("kind") in ("youtube", "reddit", "rss", "topic"):
                    if data:
                        try:
                            parsed = parse_feed(data)
                            for it in parsed["items"][:25]:
                                it.update(source_id=f["id"], source=f.get("name", ""), kind=f["kind"])
                                it["id"] = f["id"] + "|" + str(it["id"])
                                feed.append(it)
                        except ET.ParseError:
                            errors[f["id"]] = "that feed couldn't be read"
                    elif err:
                        errors[f["id"]] = err
            feed += self.assemble_anime(errors)
            seen_urls, dedup = set(), []
            for it in sorted(feed, key=lambda i: -i.get("time", 0)):
                if it["url"] in seen_urls:
                    continue
                seen_urls.add(it["url"])
                dedup.append(it)
            st["feed"] = dedup[:400]

            gnews = []
            for g in self.games:
                data, err = self.raw.get(("gnews", g["id"]), (None, ""))
                if data:
                    gnews += parse_steam_news(data, g)
                elif err and g.get("appid"):
                    errors[g["id"]] = err
                data, err = self.raw.get(("gfeed", g["id"]), (None, ""))
                if data and not g.get("appid"):
                    try:
                        for it in parse_feed(data)["items"][:8]:
                            gnews.append({"id": g["id"] + "|" + str(it["id"]), "title": it["title"], "url": it["url"],
                                          "time": it["time"], "summary": it["summary"], "label": it.get("source") or "News",
                                          "game_id": g["id"], "game": g["name"], "official": False})
                    except ET.ParseError:
                        pass
            gnews.sort(key=lambda i: -i.get("time", 0))
            st["game_news"] = gnews[:300]
            data, err = self.raw.get(("free", ""), (None, ""))
            if data:
                st["free"] = parse_epic_free(data)
            self.assemble_deals(errors)
            self.item_alerts()
            for k_ in [k_ for k_ in self.raw if k_[0] != "score"]:
                self.raw.pop(k_, None)          # big data no longer needed once parsed
            st["errors"] = errors
        else:
            st.setdefault("errors", {}).update(errors)
        st["updated"] = now()

    # ---------------------------------------------------------------- alerts
    def alerts_on(self, kind):
        return bool(self.opt("hub_notify", True)) and bool(self.opt(kind, True))

    def score_alerts(self, games, my_team_ids):
        t = now()
        for g in games:
            if g.get("type") != "game":
                continue
            prev = (self.game_states.get(g["id"]) or {}).get("s")
            self.game_states[g["id"]] = {"s": g["state"], "t": t}
            if not prev or prev == g["state"] or not g.get("mine"):
                continue
            mine = None
            for side in ("home", "away"):
                f = my_team_ids.get(g["league"], {}).get(g[side]["id"])
                if f and f.get("on", True) and f.get("notify", True):
                    mine = (side, f)
            if not mine or not self.alerts_on("hub_notify_scores"):
                continue
            side, f = mine
            us, them = g[side], g["away" if side == "home" else "home"]
            icon = LEAGUE.get(g["league"], {}).get("emoji", "🏟")
            if g["state"] == "in" and prev == "pre":
                self.notify.emit(icon, f"{us['short'] or us['name']} game is on", f"{g['short'] or g['name']} has started.",
                                 g.get("link", ""))
            elif g["state"] == "post":
                res = "won" if us.get("winner") else ("lost" if them.get("winner") else "finished")
                self.notify.emit(icon, f"Final: {us['abbr']} {us['score']} – {them['abbr']} {them['score']}",
                                 f"The {us['short'] or us['name']} {res}.", g.get("link", ""))

    def item_alerts(self):
        t = now()
        new_feed, new_games = [], []
        sources = {f["id"]: f for f in self.follows}
        games = {g["id"]: g for g in self.games}
        new_anime = []
        for it in self.state.get("feed", []):
            sid = it.get("source_id")
            if it["id"] in self.seen:
                continue
            self.seen[it["id"]] = t
            f = sources.get(sid)
            if sid in self.synced and f and f.get("notify", True) and f.get("on", True) and t - it.get("time", 0) < 2 * 86400:
                (new_anime if it.get("kind") == "anime" else new_feed).append(it)
        if new_anime and self.alerts_on("hub_notify_anime") and self.follow_on():
            for it in new_anime[:4]:
                self.notify.emit("📺", it.get("source") or "New episode", it["title"] + " · tap to watch", it["url"])
        for it in self.state.get("game_news", []):
            gid = it.get("game_id")
            if it["id"] in self.seen:
                continue
            self.seen[it["id"]] = t
            g = games.get(gid)
            if gid in self.synced and g and g.get("notify", True) and g.get("on", True) and t - it.get("time", 0) < 3 * 86400:
                new_games.append(it)
        for it in self.state.get("free", []):
            key = "free|" + it["id"] + "|" + str(int(it.get("start", 0)))
            if key in self.seen:
                continue
            self.seen[key] = t
            if "free:epic" in self.synced and it.get("now") and self.alerts_on("hub_notify_free") and self.games_on():
                self.notify.emit("🎁", f"Free game: {it['title']}", "Free to keep on the Epic Games Store right now.", it["url"])
        self.synced |= set(sources) | set(games)
        if self.state.get("free"):
            self.synced.add("free:epic")
        if new_feed and self.alerts_on("hub_notify_news") and self.follow_on():
            if len(new_feed) > 3:
                self.notify.emit("📣", f"{len(new_feed)} new updates", "From things you follow. Open 📣 Following to see them.", "")
            else:
                for it in new_feed:
                    icon = KIND_ICON.get(it.get("kind"), "📣") if it.get("kind") != "sports" else "📰"
                    self.notify.emit(icon, it.get("source") or "New update", it["title"], it["url"])
        if new_games and self.alerts_on("hub_notify_games") and self.games_on():
            if len(new_games) > 3:
                self.notify.emit("🎮", f"{len(new_games)} game updates", "Open 🎮 Games → Updates to see them.", "")
            else:
                for it in new_games:
                    self.notify.emit("🎮", it["game"], it["title"], it["url"])

    def unread(self, hub):
        if hub == "follow":
            if not self.follow_on():
                return 0
            on = {f["id"] for f in self.follows if f.get("on", True)}
            return sum(1 for it in self.state.get("feed", []) if it.get("source_id") in on
                       and it.get("time", 0) > self.last_open.get("follow", 0) and it.get("source_id") in self.synced)
        if not self.games_on():
            return 0
        on = {g["id"] for g in self.games if g.get("on", True)}
        return sum(1 for it in self.state.get("game_news", []) if it.get("game_id") in on
                   and it.get("time", 0) > self.last_open.get("games", 0))

    # ---------------------------------------------------------------- data for pages
    def public_state(self):
        s = self.settings()
        return {"enabled": {"games": self.games_on(), "follow": self.follow_on()},
                "follows": self.follows, "games": self.games, "state": self.state, "busy": self.busy,
                "has_steam_key": bool(str(s.get("steam_api_key", "")).strip() and str(s.get("steam_id", "")).strip()),
                "widgets": {w: s.get(f"w_{w}_pos", "Hidden") for w in WIDGET_KEYS},
                "free_on": bool(s.get("games_free_week", True)), "web_on": bool(s.get("games_web_sites", True)),
                "deals_on": bool(s.get("games_deals", True)), "top_deals_on": bool(s.get("games_top_deals", True)),
                "wishlist": self.wishlist, "xp": self.xp_public(), "xp_on": self.xp_on(),
                "last_open": self.last_open, "now": now()}

    def start_data(self):
        """Compact data for the start page widgets."""
        rows = []
        for f in self.follows:
            if f.get("kind") != "team" or not f.get("on", True):
                continue
            info = (self.state.get("teams") or {}).get(f["id"]) or {}
            rows.append({"name": f.get("name", ""), "abbr": f.get("abbr", ""), "logo": f.get("logo", ""),
                         "record": info.get("record", ""), "today": info.get("today"), "next": info.get("next"),
                         "last": info.get("last"), "team_id": f.get("team_id")})
        on = {f["id"] for f in self.follows if f.get("on", True)}
        feed = [{"t": i["title"], "u": i["url"], "s": i.get("source", ""), "time": i.get("time", 0), "k": i.get("kind", "")}
                for i in self.state.get("feed", []) if i.get("source_id") in on][:20]
        gon = {g["id"] for g in self.games if g.get("on", True)}
        gnews = [{"t": i["title"], "u": i["url"], "s": i.get("game", ""), "time": i.get("time", 0)}
                 for i in self.state.get("game_news", []) if i.get("game_id") in gon][:20]
        anime = []
        for f in self.follows:
            if f.get("kind") != "anime" or not f.get("on", True):
                continue
            info = (self.state.get("anime") or {}).get(f["id"]) or {}
            aired = info.get("aired") or 0
            nxt_ep = (f.get("progress", 0) or 0) + 1
            anime.append({"t": f.get("name", ""), "img": f.get("image", ""), "next": info.get("next_ep"), "at": info.get("next_at"),
                          "new": max(0, aired - (f.get("progress", 0) or 0)), "watch": anime_watch_url(info, nxt_ep) if aired >= nxt_ep else "",
                          "status": info.get("status", "")})
        anime.sort(key=lambda a: (-a["new"], a["at"] or 10 ** 12))
        return {"teams": rows if self.follow_on() else [], "feed": feed if self.follow_on() else [],
                "gamenews": gnews if self.games_on() else [], "follow_on": self.follow_on(), "games_on": self.games_on(),
                "anime": anime if self.follow_on() else []}

    # ---------------------------------------------------------------- anime
    def assemble_anime(self, errors):
        """Updates anime info and returns 'episode is out' feed items."""
        info_all = dict(self.state.get("anime") or {})
        got_any = False
        for (kind, k), (data, err) in list(self.raw.items()):
            if kind != "anime":
                continue
            if data:
                got_any = True
                for m in parse_anime_page(data):
                    info_all["anime:" + m["anilist_id"]] = m
            elif err:
                errors["anime"] = err
        items, t = [], now()
        for f in self.follows:
            if f.get("kind") != "anime":
                continue
            info = info_all.get(f["id"])
            if not info:
                continue
            f["name"] = info["title"] or f.get("name", "")
            f["image"] = info["image"] or f.get("image", "")
            aired = info.get("aired")
            eps = f.setdefault("eps", {})
            if got_any and isinstance(aired, int):
                prev = f.get("aired_seen")
                if prev is None:
                    f["aired_seen"] = aired           # first look: nothing is "new" yet
                elif aired > prev:
                    for ep in range(max(prev + 1, aired - 2), aired + 1):
                        eps[str(ep)] = t
                    f["aired_seen"] = aired
            for ep, when_ in list(eps.items())[-6:]:
                items.append({"id": f"{f['id']}|ep{ep}", "title": f"Episode {ep} is out", "url": anime_watch_url(info, ep),
                              "time": when_, "summary": info.get("format", ""), "image": info.get("image", ""),
                              "source": f.get("name", ""), "source_id": f["id"], "kind": "anime"})
            if len(eps) > 12:
                f["eps"] = dict(sorted(eps.items(), key=lambda kv: int(kv[0]))[-12:])
        self.state["anime"] = {k: v for k, v in info_all.items() if any(f["id"] == k for f in self.follows)}
        return items

    def api_anime_search(self, a, done):
        q = str(a.get("q", "")).strip()[:80]
        if len(q) < 2:
            done([], None)
            return
        self.net.post(ANILIST, {"query": ANIME_SEARCH_Q, "variables": {"q": q}},
                      lambda data, err: done(parse_anime_page(data), None if data else (err or "search failed")), ttl=600)

    def api_follow_anime(self, a, done):
        aid = str(a.get("anilist_id", ""))
        if not aid.isdigit():
            done(None, "unknown show")
            return
        fid = "anime:" + aid
        if not self.find(fid):
            prog = a.get("progress")
            self.follows.append({"id": fid, "kind": "anime", "anilist_id": aid, "name": str(a.get("name", ""))[:120],
                                 "image": safe_url(a.get("image")), "url": safe_url(a.get("url")) or f"https://anilist.co/anime/{aid}",
                                 "progress": int(prog) if isinstance(prog, int) and 0 <= prog < 5000 else 0,
                                 "on": True, "notify": True, "added": now()})
            self.xp_event("follow")
        self.changed_soon()
        done(self.find(fid), None)

    def api_anime_progress(self, a, done):
        f = self.find(str(a.get("id", "")))
        if not f or f.get("kind") != "anime":
            done(None, "not found")
            return
        info = (self.state.get("anime") or {}).get(f["id"]) or {}
        top = info.get("aired") if isinstance(info.get("aired"), int) else (
            info.get("total") if isinstance(info.get("total"), int) else 9999)      # can't have watched what isn't out yet
        try:
            v = int(a.get("value"))
        except (TypeError, ValueError):
            done(None, "bad number")
            return
        v = max(0, min(v, top))
        gained = v - int(f.get("progress", 0) or 0)
        f["progress"] = v
        for _ in range(max(0, min(gained, 30))):
            self.xp_event("anime_ep", quiet=True)
        self.check_badges()
        self.changed_soon(refresh=False)
        done(f, None)

    # ---------------------------------------------------------------- deals
    def assemble_deals(self, errors):
        data, err = self.raw.get(("cs_stores", ""), (None, ""))
        if data:
            self.state["stores"] = parse_cs_stores(data) or self.state.get("stores", {})
        stores = self.state.get("stores") or {}
        prices = {}
        got = False
        for (kind, k), (data, err) in list(self.raw.items()):
            if kind == "cs_games":
                if data:
                    got = True
                    prices.update(parse_cs_games(data, stores))
                elif err:
                    errors["deals"] = err
        data, err = self.raw.get(("cs_top", ""), (None, ""))
        if data:
            self.state["deals"] = parse_cs_deals(data, stores)
        elif err:
            errors["top_deals"] = err
        if not got:
            return
        for w in self.wishlist:
            p = prices.get(w.get("gid"))
            if not p or p.get("best") is None:
                continue
            prev = w.get("best")
            for key_ in ("retail", "savings", "store", "deal", "lowest", "thumb"):
                if p.get(key_) not in (None, ""):
                    w[key_] = p[key_]
            w["title"] = p.get("title") or w.get("title", "")
            w["best"] = p["best"]
            w["checked"] = now()
            if prev is None or not w.get("notify", True) or not w.get("on", True):
                continue
            if not (self.alerts_on("hub_notify_deals") and self.games_on()):
                continue
            target = w.get("target")
            hit = isinstance(target, (int, float)) and p["best"] <= target and w.get("alerted") != p["best"]
            if p["best"] < prev - 0.005 or hit:
                w["alerted"] = p["best"]
                off = f" (−{p['savings']}%)" if p.get("savings") else ""
                title = ("🎯 Your price! " if hit else "Price drop: ") + w["title"]
                self.notify.emit("💸", title, f"${p['best']:.2f} at {p.get('store') or 'a store'}{off}.", deal_url(p.get("deal")))

    def api_deal_search(self, a, done):
        q = str(a.get("q", "")).strip()[:80]
        if len(q) < 2:
            done([], None)
            return
        self.net.get(CHEAPSHARK + "games?" + urllib.parse.urlencode({"title": q, "limit": 15}),
                     lambda data, err: done(parse_cs_search(data), None if data is not None else (err or "search failed")), ttl=900)

    def api_wish_add(self, a, done):
        gid = str(a.get("gid", ""))
        if not gid.isdigit():
            done(None, "unknown game")
            return
        wid = "deal:" + gid
        if not self.find(wid):
            self.wishlist.append({"id": wid, "gid": gid, "title": str(a.get("title", ""))[:120], "thumb": safe_url(a.get("thumb")),
                                  "best": None, "target": None, "on": True, "notify": True, "added": now()})
            self.xp_event("wish")
        self.changed_soon()
        done(self.find(wid), None)

    def api_wish_remove(self, a, done):
        wid = str(a.get("id", ""))
        self.wishlist = [w for w in self.wishlist if w["id"] != wid]
        self.changed_soon(refresh=False)
        done(True, None)

    def api_wish_target(self, a, done):
        w = self.find(str(a.get("id", "")))
        if not w or not w["id"].startswith("deal:"):
            done(None, "not found")
            return
        v = a.get("target")
        try:
            v = None if v in (None, "") else round(float(v), 2)
        except (TypeError, ValueError):
            done(None, "That's not a price.")
            return
        w["target"] = v if v is None or 0 <= v < 1000 else None
        w.pop("alerted", None)
        self.changed_soon(refresh=False)
        done(w, None)

    def api_open_deal(self, a, done):
        did = str(a.get("deal", ""))
        if re.fullmatch(r"[A-Za-z0-9%+/=_-]{6,200}", did):
            self.open_requested.emit(deal_url(did))
        done(True, None)

    # ---------------------------------------------------------------- XP, levels, badges
    def xp_on(self):
        return bool(self.opt("xp_on", True))

    def touch_day(self):
        if not self.xp_on():
            return
        d = today_str()
        days = self.xp.setdefault("days", [])
        if d in days:
            return
        days.append(d)
        streak = streak_of(days)
        self._add_xp(20 + 5 * min(streak - 1, 10), "day", None)
        if getattr(self, "timer", None) is not None:       # (not while the service is still starting)
            self.check_badges()

    def level(self):
        return level_for(int(self.xp.get("total", 0)))

    def _add_xp(self, n, src, cap):
        day = self.xp.setdefault("day", {})
        if day.get("date") != today_str():
            day.clear()
            day["date"] = today_str()
            day["got"] = {}
        got = day.setdefault("got", {})
        if cap is not None:
            n = max(0, min(n, cap - got.get(src, 0)))
        if n <= 0:
            return 0
        got[src] = got.get(src, 0) + n
        before = self.level()
        self.xp["total"] = int(self.xp.get("total", 0)) + n
        after = self.level()
        if after > before and getattr(self, "timer", None) is not None:
            unlocked = [name for name, (lv, _d, _s) in REWARD_PACKS.items() if before < lv <= after]
            body = ("Unlocked the “" + "”, “".join(unlocked) + "” style pack" + ("s" if len(unlocked) > 1 else "") +
                    " (🎨 Customize → ✨ Style packs).") if unlocked else f"{int(self.xp['total'])} XP so far. Keep going!"
            self.notify.emit("⭐", f"Level {after}!", body, "")
        return n

    def xp_event(self, kind, quiet=False):
        """Something XP-worthy happened (called by the browser and by the hub itself)."""
        if not self.xp_on():
            return
        c = self.xp.setdefault("c", {})
        c[kind] = c.get(kind, 0) + 1
        rule = XP_RULES.get(kind)
        if rule:
            amount, cap, every = rule
            if c[kind] % every == 0:
                self._add_xp(amount, kind, cap)
        self.touch_day()
        if not quiet:
            self.check_badges()
        self.save_soon()

    def xp_stats(self):
        days = self.xp.get("days", [])
        return {"played": self.xp.get("played", {}), "best": self.xp.get("best", {}), "c": self.xp.get("c", {}),
                "teams": sum(1 for f in self.follows if f.get("kind") == "team"),
                "follows": len(self.follows), "anime": sum(1 for f in self.follows if f.get("kind") == "anime"),
                "linked": len(self.games), "wished": len(self.wishlist),
                "streak": streak_of(days), "best_streak": best_streak_of(days)}

    def check_badges(self):
        if not self.xp_on():
            return []
        S = self.xp_stats()
        have = self.xp.setdefault("badges", {})
        new = []
        for bid, emoji, name, desc, test in BADGES:
            if bid in have:
                continue
            try:
                ok = bool(test(S))
            except Exception:
                ok = False
            if ok:
                have[bid] = now()
                new.append((emoji, name, desc))
        for emoji, name, desc in new:
            self._add_xp(BADGE_XP, "badge", None)
        if new:
            if len(new) > 2:
                self.notify.emit("🏆", f"{len(new)} badges unlocked!", ", ".join(n for _e, n, _d in new), "")
            else:
                for emoji, name, desc in new:
                    self.notify.emit("🏆", f"Badge unlocked: {emoji} {name}", f"{desc} +{BADGE_XP} XP", "")
            self.save_soon()
            self.changed.emit()
        return new

    def xp_public(self):
        total = int(self.xp.get("total", 0))
        lv = level_for(total)
        S = self.xp_stats()
        have = self.xp.get("badges", {})
        return {"total": total, "level": lv, "floor": level_floor(lv), "next": level_floor(lv + 1),
                "streak": S["streak"], "best_streak": S["best_streak"],
                "badges": [{"id": b, "emoji": e, "name": n, "desc": d, "got": have.get(b, 0)} for b, e, n, d, _t in BADGES],
                "rewards": [{"name": n, "level": lv_, "desc": d, "unlocked": lv >= lv_} for n, (lv_, d, _s) in REWARD_PACKS.items()],
                "stats": {"pages": S["c"].get("page", 0), "games": len(S["played"]),
                          "rounds": sum(S["played"].values()) if S["played"] else 0, "episodes": S["c"].get("anime_ep", 0),
                          "zaps": S["c"].get("zap", 0), "gestures": S["c"].get("gesture", 0), "voice": S["c"].get("voice", 0)},
                "best": S["best"]}

    def api_game_result(self, a, done):
        """A built-in game page reports a score, a win, or (when it opens) the best score it has saved."""
        if not self.xp_on():
            done(True, None)
            return
        game, kind = str(a.get("game", "")), str(a.get("kind", ""))
        try:
            v = float(a.get("value"))
        except (TypeError, ValueError):
            done(None, "bad value")
            return
        if game not in GAME_IDS or kind not in ("score", "win", "best") or not (0 <= v <= 10 ** 7):
            done(None, "bad result")
            return
        v = int(v) if v == int(v) else v
        low = GAME_GOALS.get(game, (0, False))[1]
        bests = self.xp.setdefault("best", {})
        old = bests.get(game)
        better = old is None or (v < old if low else v > old)
        if kind == "best":                     # what the game had saved before (no XP, just so badges count it)
            if better and (v > 0 or low):
                bests[game] = v
                self.check_badges()
                self.save_soon()
            done(True, None)
            return
        played = self.xp.setdefault("played", {})
        last = self.xp.setdefault("last_game_xp", {})
        t = now()
        xp = 0
        if kind == "win":
            bests[game] = (old or 0) + 1 if not low else bests.get(game)
            if t - last.get(game + ":win", 0) > 15:
                xp += 15
                last[game + ":win"] = t
        else:
            if better and (v > 0 or low):
                bests[game] = v
                if old is not None and t - last.get(game + ":best", 0) > 60:
                    xp += 10
                    last[game + ":best"] = t
        if t - last.get(game, 0) > 30:
            played[game] = played.get(game, 0) + 1
            xp += 3
            last[game] = t
        elif game not in played:
            played[game] = 1
        if xp:
            self._add_xp(xp, "games", GAMES_DAILY_CAP)
        self.touch_day()
        self.check_badges()
        self.save_soon()
        done({"xp": xp}, None)

    def reward_unlocked(self, name):
        return name in REWARD_PACKS and self.level() >= REWARD_PACKS[name][0]

    def api_apply_pack(self, a, done):
        name = str(a.get("name", ""))
        if not self.reward_unlocked(name):
            done(None, "Not unlocked yet.")
            return
        self.pack_requested.emit(name)
        done(True, None)

    # ---------------------------------------------------------------- what Nova can answer out loud
    def voice_summary(self):
        teams, anime, deals = [], [], []
        for f in self.follows:
            if not f.get("on", True):
                continue
            if f.get("kind") == "team":
                info = (self.state.get("teams") or {}).get(f["id"]) or {}
                short = f.get("name", "").split()[-1] if f.get("name") else f.get("abbr", "")
                g = info.get("today")
                lines = [x for x in (team_line(short, g, f.get("team_id")),
                                     team_line(short, info.get("next"), f.get("team_id")) if not g or g.get("state") == "post" else "",
                                     team_line(short, info.get("last"), f.get("team_id")) if not g else "") if x]
                if info.get("record"):
                    lines.append(f"Their record is {info['record']}.")
                teams.append({"name": f.get("name", ""), "abbr": f.get("abbr", ""), "short": short,
                              "line": " ".join(lines[:3]) or f"I don't have any games for the {short} right now."})
            elif f.get("kind") == "anime":
                info = (self.state.get("anime") or {}).get(f["id"]) or {}
                prog = int(f.get("progress", 0) or 0)
                aired = info.get("aired") or 0
                bits = []
                if aired > prog:
                    bits.append(f"Episode {prog + 1} is out and ready to watch" + (f", and {aired - prog - 1} more after it" if aired - prog > 1 else "") + ".")
                if info.get("next_ep") and info.get("next_at"):
                    bits.append(f"Episode {info['next_ep']} comes out in {spoken_in(info['next_at'] - now())}, {spoken_when(info['next_at'])}.")
                elif info.get("status") == "FINISHED":
                    bits.append("It has finished airing.")
                anime.append({"name": f.get("name", ""), "romaji": info.get("romaji", ""),
                              "line": " ".join(bits) or "I don't have a schedule for it yet."})
        for w in self.wishlist:
            if w.get("best") is not None:
                off = f", {w['savings']} percent off" if w.get("savings") else ""
                deals.append({"name": w.get("title", ""), "line": f"{w.get('title')} is ${w['best']:.2f} at {w.get('store') or 'a store'}{off}."})
        return {"teams": teams, "anime": anime, "deals": deals, "level": self.level(), "xp": int(self.xp.get("total", 0))}

    # ---------------------------------------------------------------- actions from the hub pages
    def handle(self, method, a, done):
        fn = getattr(self, "api_" + re.sub(r"[^a-z_]", "", str(method)), None)
        if fn is None:
            done(None, "unknown action")
            return
        try:
            fn(a if isinstance(a, dict) else {}, done)
        except Exception as e:
            print("[hub] action error:", method, e)
            done(None, "something went wrong")

    def changed_soon(self, refresh=True):
        self.save_soon()
        self.changed.emit()
        if refresh:
            QTimer.singleShot(300, self.refresh)

    def api_state(self, a, done):
        done(self.public_state(), None)

    def api_refresh(self, a, done):
        self.refresh(force=True)
        done(True, None)

    def api_mark_seen(self, a, done):
        hub = a.get("hub")
        if hub in ("follow", "games"):
            self.last_open[hub] = now()
            self.save_soon()
            self.changed.emit()
        done(True, None)

    def api_teams(self, a, done):
        lg = LEAGUE.get(str(a.get("league")))
        if not lg or not lg["teams"]:
            done([], None)
            return
        self.net.get(ESPN + lg["path"] + "/teams?limit=1000",
                     lambda data, err: done(parse_espn_teams(data), None if data else (err or "no teams found")),
                     ttl=86400)

    def api_follow_team(self, a, done):
        lg, tid = str(a.get("league", "")), str(a.get("team_id", ""))
        if lg not in LEAGUE or not LEAGUE[lg]["teams"] or not tid.isdigit():
            done(None, "unknown team")
            return
        fid = f"team:{lg}:{tid}"
        if not self.find(fid):
            self.xp_event("follow", quiet=True)
            self.follows.append({"id": fid, "kind": "team", "league": lg, "team_id": tid,
                                 "name": str(a.get("name", ""))[:80], "abbr": str(a.get("abbr", ""))[:8],
                                 "logo": safe_url(a.get("logo")), "color": re.sub(r"[^0-9a-fA-F]", "", str(a.get("color", "")))[:6],
                                 "on": True, "notify": True, "added": now()})
        self.changed_soon()
        done(self.find(fid), None)

    def api_follow_league(self, a, done):
        lg = str(a.get("league", ""))
        if lg not in LEAGUE:
            done(None, "unknown league")
            return
        fid = "league:" + lg
        if not self.find(fid):
            self.follows.append({"id": fid, "kind": "league", "league": lg, "name": LEAGUE[lg]["name"],
                                 "on": True, "notify": True, "added": now()})
        self.changed_soon()
        done(self.find(fid), None)

    def api_unfollow(self, a, done):
        fid = str(a.get("id", ""))
        self.follows = [f for f in self.follows if f["id"] != fid]
        self.games = [g for g in self.games if g["id"] != fid]
        self.state["feed"] = [i for i in self.state.get("feed", []) if i.get("source_id") != fid]
        self.state["game_news"] = [i for i in self.state.get("game_news", []) if i.get("game_id") != fid]
        self.state.get("teams", {}).pop(fid, None)
        self.state.get("anime", {}).pop(fid, None)
        self.synced.discard(fid)
        self.changed_soon(refresh=False)
        done(True, None)

    def api_toggle(self, a, done):
        item = self.find(str(a.get("id", "")))
        field = a.get("field")
        if not item or field not in ("on", "notify"):
            done(None, "not found")
            return
        item[field] = bool(a.get("value"))
        self.changed_soon(refresh=field == "on" and item[field])
        done(item, None)

    def api_add_source(self, a, done):
        text = str(a.get("text", "")).strip()[:500]
        if not text:
            done(None, "Type something to follow first.")
            return
        m = re.match(r"^(?:https?://)?(?:www\.|old\.)?(?:reddit\.com)?/?r/([A-Za-z0-9_]{2,30})/?", text)
        if m:
            name = m.group(1)
            self._add_follow({"id": "reddit:" + name.lower(), "kind": "reddit", "name": "r/" + name,
                              "feed": f"https://www.reddit.com/r/{name}/.rss", "url": f"https://www.reddit.com/r/{name}/"}, done)
            return
        if text.startswith("@") or re.search(r"(^|//|\.)youtube\.com/|youtu\.be/", text, re.I):
            self._add_youtube(text, done)
            return
        if re.match(r"^https?://", text, re.I) or re.match(r"^[\w-]+(\.[\w-]+)+(/\S*)?$", text):
            url = text if re.match(r"^https?://", text, re.I) else "https://" + text
            self._discover_feed(url, done)
            return
        self._add_follow({"id": "topic:" + slug(text), "kind": "topic", "name": text[:80],
                          "feed": google_news_feed(text), "url": "https://news.google.com/search?q=" + urllib.parse.quote(text)},
                         done)

    def _add_follow(self, item, done):
        old = self.find(item["id"])
        if old:
            done(old, None)
            return
        item.update(on=True, notify=True, added=now())
        self.follows.append(item)
        self.xp_event("follow")
        self.changed_soon()
        done(item, None)

    def _add_youtube(self, text, done):
        m = re.search(r"(UC[\w-]{22})", text)
        if m and "/channel/" in text:
            cid = m.group(1)
            self._add_follow({"id": "yt:" + cid, "kind": "youtube", "name": "YouTube channel",
                              "feed": f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}",
                              "url": f"https://www.youtube.com/channel/{cid}"}, done)
            self._name_from_feed("yt:" + cid)
            return
        if text.startswith("@"):
            url = "https://www.youtube.com/" + text.split()[0]
        else:
            url = text if re.match(r"^https?://", text, re.I) else "https://" + text
        if not re.match(r"^https://(www\.|m\.)?youtube\.com/", url, re.I):
            done(None, "That doesn't look like a YouTube channel address.")
            return

        def got(page, err):
            page = page or ""
            m2 = (re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', page)
                  or re.search(r'"externalId":"(UC[\w-]{22})"', page)
                  or re.search(r'<meta itemprop="identifier" content="(UC[\w-]{22})"', page))
            if not m2:
                done(None, "Couldn't find that YouTube channel" + (f" ({err})." if err else "."))
                return
            cid = m2.group(1)
            t = re.search(r'<meta property="og:title" content="([^"]+)"', page)
            name = html.unescape(t.group(1)) if t else text
            self._add_follow({"id": "yt:" + cid, "kind": "youtube", "name": name[:80],
                              "feed": f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}",
                              "url": f"https://www.youtube.com/channel/{cid}"}, done)
        self.net.get(url, got, ttl=3600, mode="text", headers={"Cookie": "CONSENT=YES+1"})

    def _name_from_feed(self, fid):
        item = self.find(fid)
        if not item:
            return

        def got(data, err):
            if data:
                try:
                    t = parse_feed(data)["title"]
                    if t and self.find(fid):
                        self.find(fid)["name"] = t[:80]
                        self.changed_soon(refresh=False)
                except ET.ParseError:
                    pass
        self.net.get(item["feed"], got, ttl=1200, mode="bytes")

    def _discover_feed(self, url, done, tries=None):
        def add(feed_url, data):
            try:
                parsed = parse_feed(data)
            except ET.ParseError:
                done(None, "That feed couldn't be read.")
                return
            host = urllib.parse.urlsplit(feed_url).hostname or feed_url
            self._add_follow({"id": "rss:" + feed_url, "kind": "rss", "name": (parsed["title"] or host)[:80],
                              "feed": feed_url, "url": safe_url(parsed.get("link")) or url}, done)

        def got(data, err):
            text = (data or b"").decode("utf-8", "replace") if isinstance(data, (bytes, bytearray)) else (data or "")
            if data and looks_like_feed(text):
                add(current, data)
                return
            nonlocal_tries = tries if tries is not None else (
                find_feed_links(text, current) + [urllib.parse.urljoin(current, p) for p in ("/feed", "/rss", "/feed.xml", "/rss.xml", "/atom.xml")])
            if not nonlocal_tries:
                done(None, "No updates feed found on that site. Tip: type the site's name to follow it as a news topic.")
                return
            self._discover_feed(nonlocal_tries[0], done, nonlocal_tries[1:])
        current = url
        self.net.get(url, got, ttl=600, mode="bytes")

    def api_search_games(self, a, done):
        q = str(a.get("q", "")).strip()[:80]
        if len(q) < 2:
            done([], None)
            return
        url = "https://store.steampowered.com/api/storesearch/?" + urllib.parse.urlencode({"term": q, "l": "english", "cc": "US"})
        self.net.get(url, lambda data, err: done(parse_steam_search(data)[:12], None if data else (err or "search failed")),
                     ttl=600)

    def _link(self, appid, name, image="", source="steam", launch="", folder=""):
        appid = str(appid or "")
        gid = f"steam:{appid}" if appid.isdigit() else f"game:{slug(name)}"
        old = self.find(gid)
        if old:
            if launch and not old.get("launch"):
                old["launch"] = launch
            if folder and not old.get("dir"):
                old["dir"] = folder
            return old
        if appid.isdigit() and not launch and source == "steam":
            launch = f"steam://rungameid/{appid}"
        item = {"id": gid, "appid": appid if appid.isdigit() else "", "name": str(name)[:100],
                "image": safe_url(image) or (steam_image(appid) if appid.isdigit() else ""),
                "source": source, "launch": launch if re.match(r"^(steam|com\.epicgames\.launcher)://", launch or "") else "",
                "dir": str(folder or "")[:400], "on": True, "notify": True, "added": now()}
        self.games.append(item)
        self.xp_event("link", quiet=True)
        return item

    def api_link_game(self, a, done):
        name = str(a.get("name", "")).strip()
        if not name:
            done(None, "missing name")
            return
        item = self._link(a.get("appid", ""), name, a.get("image", ""), "steam" if str(a.get("appid", "")).isdigit() else "manual")
        self.check_badges()
        self.changed_soon()
        done(item, None)

    def api_scan_games(self, a, done):
        found = scan_installed_games()
        linked = {g.get("appid") for g in self.games if g.get("appid")} | {normalize_name(g["name"]) for g in self.games}
        for f in found:
            f["linked"] = (f.get("appid") in linked) or (normalize_name(f["name"]) in linked)
            if f["linked"] and f.get("dir"):         # remember install folders of games linked earlier (for Game Mode)
                for g in self.games:
                    if not g.get("dir") and ((f.get("appid") and g.get("appid") == f["appid"]) or normalize_name(g["name"]) == normalize_name(f["name"])):
                        g["dir"] = f["dir"]
                        self.save_soon()
        done(found, None)

    def api_link_scanned(self, a, done):
        items = [i for i in (a.get("items") or []) if isinstance(i, dict) and i.get("name")][:200]
        todo = [len(items)]
        if not items:
            done(0, None)
            return

        def one_done():
            todo[0] -= 1
            if todo[0] <= 0:
                self.check_badges()
                self.changed_soon()
                done(len(items), None)
        for it in items:
            launch = str(it.get("launch", ""))
            folder = str(it.get("dir", ""))
            if str(it.get("appid", "")).isdigit():
                self._link(it["appid"], it["name"], it.get("image", ""), "steam", launch, folder)
                one_done()
                continue

            def matched(data, err, it=it, launch=launch, folder=folder):
                hit = None
                for r in parse_steam_search(data):
                    if normalize_name(r["name"]) == normalize_name(it["name"]):
                        hit = r
                        break
                if hit:        # same game is on Steam: use its official news, keep the Epic launcher
                    self._link(hit["appid"], it["name"], steam_image(hit["appid"]), it.get("source", "epic"), launch, folder)
                else:
                    self._link("", it["name"], "", it.get("source", "epic"), launch, folder)
                one_done()
            self.net.get("https://store.steampowered.com/api/storesearch/?" +
                         urllib.parse.urlencode({"term": it["name"], "l": "english", "cc": "US"}), matched, ttl=3600)

    def api_steam_owned(self, a, done):
        s = self.settings()
        key = str(s.get("steam_api_key", "")).strip()
        sid = str(s.get("steam_id", "")).strip()
        if not key or not sid:
            done(None, "Add your Steam Web API key and Steam ID in 🎨 Customize → Games & Following first.")
            return
        m = re.search(r"/profiles/(\d{17})", sid) or re.match(r"^(\d{17})$", sid)
        if m:
            self._owned(key, m.group(1), done)
            return
        vanity = re.search(r"/id/([^/\s]+)", sid)
        vanity = vanity.group(1) if vanity else sid

        def resolved(data, err):
            r = (data or {}).get("response") or {}
            if r.get("success") == 1 and r.get("steamid"):
                self._owned(key, r["steamid"], done)
            else:
                done(None, "Couldn't find that Steam profile. Check the Steam ID in Customize.")
        self.net.get("https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?" +
                     urllib.parse.urlencode({"key": key, "vanityurl": vanity}), resolved, ttl=0)

    def _owned(self, key, steamid, done):
        def got(data, err):
            games = parse_steam_owned(data)
            if not games:
                done(None, "No games came back. Make sure your Steam profile's game details are set to Public." +
                     (f" ({err})" if err else ""))
                return
            linked = {g.get("appid") for g in self.games}
            for g in games:
                g["linked"] = g["appid"] in linked
                g["image"] = steam_image(g["appid"])
            done(games, None)
        self.net.get("https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?" +
                     urllib.parse.urlencode({"key": key, "steamid": steamid, "include_appinfo": 1,
                                             "include_played_free_games": 1, "format": "json"}), got, ttl=600)

    def api_launch(self, a, done):
        g = self.find(str(a.get("id", "")))
        uri = (g or {}).get("launch", "")
        if not g or not re.match(r"^(steam|com\.epicgames\.launcher)://", uri):
            done(None, "This game can't be started from here.")
            return
        QDesktopServices.openUrl(QUrl(uri))
        self.game_launched.emit(dict(g))
        done(True, None)

    def api_open(self, a, done):
        url = safe_url(a.get("url"))
        if url:
            self.open_requested.emit(url)
        done(bool(url), None)

    def api_set_widget(self, a, done):
        w, pos = str(a.get("widget", "")), str(a.get("pos", ""))
        if w in WIDGET_KEYS and pos in ("Left", "Center", "Right", "Hidden"):
            self.option_requested.emit(f"w_{w}_pos", pos)
            QTimer.singleShot(50, self.changed.emit)
        done(True, None)

    def api_set_option(self, a, done):
        k = str(a.get("key", ""))
        if k in OPTION_WHITELIST:
            self.option_requested.emit(k, bool(a.get("value")))
            QTimer.singleShot(50, self.changed.emit)
            QTimer.singleShot(400, self.refresh)
        done(True, None)

    def api_customize(self, a, done):
        self.customize_requested.emit()
        done(True, None)


class HubBridge(QObject):
    """What a hub page can call (through Qt's web channel). One per page."""
    reply = pyqtSignal(str, str)
    push = pyqtSignal(str, str)

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        service.changed.connect(self._changed)

    def _changed(self):
        try:
            self.push.emit("state", json.dumps(self.service.public_state()))
        except RuntimeError:
            pass

    @pyqtSlot(str, str, str)
    def call(self, req_id, method, args_json):
        try:
            args = json.loads(args_json or "{}")
        except ValueError:
            args = {}

        def done(result, error):
            try:
                self.reply.emit(req_id, json.dumps({"ok": error is None, "result": result, "error": error}))
            except RuntimeError:
                pass            # the page was closed meanwhile
        self.service.handle(method, args, done)


def qwebchannel_js():
    """Qt's qwebchannel.js (needed by the hub pages to talk to the browser)."""
    try:
        import PyQt6.QtWebChannel  # noqa: F401  (loads the library that holds the file)
    except ImportError:
        pass
    f = QFile(":/qtwebchannel/qwebchannel.js")
    if f.open(QIODevice.OpenModeFlag.ReadOnly):
        js = bytes(f.readAll()).decode("utf-8", "replace")
        f.close()
        if "QWebChannel" in js:
            return "<script>" + js.replace("</script", "<\\/script") + "</script>"
    return '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'


# ============================================================================== built-in games (free, offline)
GAME_PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="nova-page" content="game"><title>__EMOJI__ __NAME__</title>
<style>
:root { --a:__ACCENT__; --al:__ACCENT_L__; --bg:__BG__; --card:__CARD__; --text:__TEXT__; --dim:__DIM__; }
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; overflow: hidden; }
body { background: radial-gradient(900px 500px at 50% -10%, color-mix(in srgb, var(--a) 22%, transparent), transparent), var(--bg);
       color: var(--text); font: 14px "Segoe UI", sans-serif; display: flex; flex-direction: column; user-select: none; }
header { display: flex; align-items: center; gap: 14px; padding: 10px 20px; flex-wrap: wrap; }
header a { color: var(--dim); text-decoration: none; font-size: 13px; } header a:hover { color: var(--text); }
h1 { margin: 0 6px 0 0; font-size: 20px; letter-spacing: .04em; }
.stat { background: var(--card); padding: 5px 12px; border-radius: 9px; color: var(--dim); font-size: 12px; }
.stat b { color: var(--text); font-size: 15px; margin-left: 5px; }
.b { background: var(--card); color: var(--text); border: 1px solid rgba(255,255,255,.12); border-radius: 9px; padding: 6px 12px;
     font: inherit; cursor: pointer; }
.b:hover { border-color: var(--a); } .b.primary { background: var(--a); border-color: var(--a); color: #fff; font-weight: 600; }
select.b { padding: 5px 8px; }
.help { color: var(--dim); font-size: 12px; margin-left: auto; }
#stage { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 0; padding: 8px 12px 16px; }
canvas { display: block; border-radius: 14px; background: rgba(0,0,0,.35); max-width: 100%; max-height: 100%;
         box-shadow: 0 20px 60px rgba(0,0,0,.45), 0 0 0 1px rgba(255,255,255,.06); touch-action: none; }
#ov { position: fixed; inset: 0; display: none; align-items: center; justify-content: center; flex-direction: column; gap: 12px;
      background: rgba(5,6,10,.6); text-align: center; z-index: 5; }
#ov.show { display: flex; } #ov h2 { margin: 0; font-size: 36px; } #ov p { margin: 0; color: var(--dim); font-size: 15px; }
__CSS__
</style></head>
<body>
<header><a href="../games.html">← Games</a><h1>__EMOJI__ __NAME__</h1>
<span class="stat">__SCORE_LABEL__<b id="score">0</b></span><span class="stat">__BEST_LABEL__<b id="best">–</b></span>
__EXTRA__<button class="b" id="restart">↺ New game</button><span class="help">__HELP__</span></header>
<div id="stage">__BODY__</div><div id="ov"></div>
<!--QWEBCHANNEL-->
<script>
"use strict";
var GAME_ID = "__ID__", LOWER_BETTER = __LOWER__;
var NOVA_HUB = null, seqR = 0;
function report(kind, v) {
  if (NOVA_HUB && typeof v === "number" && isFinite(v)) {
    try { NOVA_HUB.call("g" + (++seqR), "game_result", JSON.stringify({ game: GAME_ID, kind: kind, value: v })); } catch (e) {}
  }
}
try {
  if (window.qt && qt.webChannelTransport && typeof QWebChannel !== "undefined")
    new QWebChannel(qt.webChannelTransport, function (ch) { NOVA_HUB = ch.objects.nova; var b = getBest(); if (b != null) report("best", b); });
} catch (e) {}
var css = getComputedStyle(document.documentElement);
var C = { a: css.getPropertyValue("--a").trim() || "#6c8cff", al: css.getPropertyValue("--al").trim() || "#8fa6ff",
          text: css.getPropertyValue("--text").trim() || "#e6e6e6", dim: css.getPropertyValue("--dim").trim() || "#9a9ca6",
          card: css.getPropertyValue("--card").trim() || "#23252c" };
function $(id) { return document.getElementById(id); }
var Score = { v: 0, set: function (n) { this.v = n; $("score").textContent = n; }, add: function (n) { this.set(this.v + n); } };
function bestKey() { return "nova-game-" + GAME_ID + "-best"; }
function getBest() { try { var b = localStorage.getItem(bestKey()); return b == null ? null : Number(b); } catch (e) { return null; } }
function setBest(v) { try { localStorage.setItem(bestKey(), String(v)); } catch (e) {} showBest(); }
function submit(v) { var b = getBest(), nb = b == null || (LOWER_BETTER ? v < b : v > b); if (nb) setBest(v); report("score", v); return nb; }
function addWin() { setBest((getBest() || 0) + 1); report("win", 1); }
function showBest() { var b = getBest(); $("best").textContent = b == null ? "–" : (window.fmtBest ? fmtBest(b) : b); }
function overlay(title, sub, btn, cb) {
  var o = $("ov"); o.innerHTML = "<h2>" + title + "</h2>" + (sub ? "<p>" + sub + "</p>" : "") + (btn ? '<button class="b primary" id="ovb">' + btn + "</button>" : "");
  o.classList.add("show"); if (btn) { var b = $("ovb"); b.onclick = function () { hideOverlay(); if (cb) cb(); }; setTimeout(function () { b.focus(); }, 30); }
}
function hideOverlay() { $("ov").classList.remove("show"); }
function overlayOpen() { return $("ov").classList.contains("show"); }
var keys = {};
addEventListener("keydown", function (e) {
  keys[e.key] = true;
  if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", " "].indexOf(e.key) >= 0 && e.target.tagName !== "SELECT") e.preventDefault();
  if ((e.key === "Enter" || e.key === " ") && overlayOpen() && $("ovb")) { e.preventDefault(); $("ovb").click(); }
});
addEventListener("keyup", function (e) { keys[e.key] = false; });
addEventListener("blur", function () { keys = {}; });
function rand(a, b) { return a + Math.random() * (b - a); }
function ri(a, b) { return Math.floor(rand(a, b + 1)); }
function glow(x, color, blur) { x.shadowColor = color; x.shadowBlur = blur; }
function rr(x, X, Y, w, h, r) { x.beginPath(); x.moveTo(X + r, Y); x.arcTo(X + w, Y, X + w, Y + h, r); x.arcTo(X + w, Y + h, X, Y + h, r);
  x.arcTo(X, Y + h, X, Y, r); x.arcTo(X, Y, X + w, Y, r); x.closePath(); }
function canvasPoint(cv, e) { var r = cv.getBoundingClientRect(); return { x: (e.clientX - r.left) * cv.width / r.width, y: (e.clientY - r.top) * cv.height / r.height }; }
$("restart").onclick = function () { hideOverlay(); this.blur(); restart(); };
showBest();
__JS__
</script>
</body></html>
"""

GAMES = []


def game(id, name, emoji, desc, help, js, body='<canvas id="c" width="600" height="600"></canvas>', css="", extra="",
         score_label="Score", best_label="Best", lower=False):
    GAMES.append({"id": id, "name": name, "emoji": emoji, "desc": desc, "help": help, "js": js, "body": body, "css": css,
                  "extra": extra, "score_label": score_label, "best_label": best_label, "lower": lower})


# ------------------------------------------------------------------------------ Snake
game("snake", "Snake", "🐍", "Eat, grow, don't bite yourself. Gets faster as you grow.", "Arrows / WASD · P pause", r"""
var cv = $("c"), x = cv.getContext("2d"), N = 25, S = 24, snake, dir, next, food, alive, timer, speed, paused;
function place() { do { food = { x: ri(0, N - 1), y: ri(0, N - 1) }; } while (snake.some(function (s) { return s.x === food.x && s.y === food.y; })); }
function restart() {
  clearTimeout(timer); snake = [{ x: 12, y: 12 }, { x: 11, y: 12 }, { x: 10, y: 12 }]; dir = { x: 1, y: 0 }; next = dir;
  place(); alive = true; speed = 120; paused = false; Score.set(0); draw();
  overlay("🐍 Snake", "Arrow keys or WASD to steer · P to pause", "Start", loop);
}
function loop() { if (!alive) return; if (!paused) step(); draw(); timer = setTimeout(loop, speed); }
function step() {
  dir = next; var h = { x: snake[0].x + dir.x, y: snake[0].y + dir.y };
  var body = snake.slice(0, snake.length - 1);
  if (h.x < 0 || h.y < 0 || h.x >= N || h.y >= N || body.some(function (s) { return s.x === h.x && s.y === h.y; })) {
    alive = false; var nb = submit(Score.v);
    overlay("Game over", "Score " + Score.v + (nb && Score.v ? " · new best! 🏆" : ""), "Play again", restart); return;
  }
  snake.unshift(h);
  if (h.x === food.x && h.y === food.y) { Score.add(1); speed = Math.max(55, speed - 3); place(); } else snake.pop();
}
function draw() {
  x.clearRect(0, 0, 600, 600);
  x.fillStyle = "rgba(255,255,255,.025)";
  for (var i = 0; i < N; i++) for (var j = 0; j < N; j++) if ((i + j) % 2) x.fillRect(i * S, j * S, S, S);
  glow(x, "#ff5a6a", 18); x.fillStyle = "#ff5a6a"; x.beginPath(); x.arc(food.x * S + S / 2, food.y * S + S / 2, S / 2 - 4, 0, 7); x.fill();
  snake.forEach(function (s, k) {
    glow(x, C.a, k ? 6 : 16); x.fillStyle = k ? C.a : C.al; x.globalAlpha = k ? Math.max(.45, 1 - k / (snake.length + 6)) : 1;
    rr(x, s.x * S + 2, s.y * S + 2, S - 4, S - 4, 7); x.fill();
  });
  x.globalAlpha = 1; x.shadowBlur = 0;
  var hd = snake[0]; x.fillStyle = "#0b0c10";
  [[-1, -1], [1, -1]].forEach(function (o) {
    var ex = hd.x * S + S / 2 + (dir.x ? dir.x * 5 : o[0] * 5), ey = hd.y * S + S / 2 + (dir.y ? dir.y * 5 : o[0] * 5);
    if (dir.x) ey = hd.y * S + S / 2 + o[0] * 5; x.beginPath(); x.arc(ex, ey, 2.6, 0, 7); x.fill();
  });
  if (paused) { x.fillStyle = "rgba(0,0,0,.5)"; x.fillRect(0, 0, 600, 600); x.fillStyle = C.text; x.font = "bold 34px Segoe UI"; x.textAlign = "center"; x.fillText("Paused", 300, 310); }
}
addEventListener("keydown", function (e) {
  var k = e.key.toLowerCase(), d = { arrowup: [0, -1], w: [0, -1], arrowdown: [0, 1], s: [0, 1], arrowleft: [-1, 0], a: [-1, 0], arrowright: [1, 0], d: [1, 0] }[k];
  if (k === "p" && alive) { paused = !paused; draw(); }
  if (d && !(d[0] === -dir.x && d[1] === -dir.y)) next = { x: d[0], y: d[1] };
});
restart();
""")

# ------------------------------------------------------------------------------ Falling blocks
game("blocks", "Starfall Blocks", "🧩", "Stack falling blocks and clear lines. Speed rises every 10 lines.",
     "←→ move · ↑ rotate · ↓ soft drop · Space hard drop · P pause", r"""
var cv = $("c"), x = cv.getContext("2d"), W = 10, H = 20, CS = 30;
var SH = { I: [[0,0,0,0],[1,1,1,1],[0,0,0,0],[0,0,0,0]], O: [[1,1],[1,1]], T: [[0,1,0],[1,1,1],[0,0,0]], S: [[0,1,1],[1,1,0],[0,0,0]],
           Z: [[1,1,0],[0,1,1],[0,0,0]], J: [[1,0,0],[1,1,1],[0,0,0]], L: [[0,0,1],[1,1,1],[0,0,0]] };
var COL = { I: "#36c9e6", O: "#f2c94c", T: "#a46cff", S: "#2fd38a", Z: "#ff5a6a", J: "#6c8cff", L: "#ff8a4c" };
var board, cur, nextK, bag, acc, last, lines, level, over, paused, raf;
function rot(m) { return m[0].map(function (_, i) { return m.map(function (r) { return r[i]; }).reverse(); }); }
function draw7() { if (!bag.length) bag = Object.keys(SH).sort(function () { return Math.random() - .5; }); return bag.pop(); }
function hit(m, px, py) {
  for (var y = 0; y < m.length; y++) for (var i = 0; i < m[y].length; i++) if (m[y][i]) {
    var bx = px + i, by = py + y; if (bx < 0 || bx >= W || by >= H) return true; if (by >= 0 && board[by][bx]) return true; }
  return false;
}
function spawn() {
  var k = nextK; nextK = draw7(); var m = SH[k];
  cur = { k: k, m: m, x: Math.floor((W - m[0].length) / 2), y: k === "I" ? -1 : 0 };
  if (hit(cur.m, cur.x, cur.y)) { over = true; var nb = submit(Score.v); overlay("Game over", "Score " + Score.v + " · " + lines + " lines" + (nb && Score.v ? " · new best! 🏆" : ""), "Play again", restart); }
}
function restart() {
  cancelAnimationFrame(raf); board = []; for (var y = 0; y < H; y++) board.push(new Array(W).fill(0));
  bag = []; nextK = draw7(); lines = 0; level = 1; over = false; paused = false; Score.set(0); acc = 0; spawn(); draw();
  overlay("🧩 Starfall Blocks", "←→ move · ↑ rotate · ↓ soft drop · Space hard drop", "Start", function () { last = performance.now(); raf = requestAnimationFrame(frame); });
}
function speed() { return Math.max(70, 800 - (level - 1) * 75); }
function lock() {
  cur.m.forEach(function (r, y) { r.forEach(function (v, i) { if (v && cur.y + y >= 0) board[cur.y + y][cur.x + i] = cur.k; }); });
  var cleared = 0;
  for (var y = H - 1; y >= 0; y--) if (board[y].every(function (v) { return v; })) { board.splice(y, 1); board.unshift(new Array(W).fill(0)); cleared++; y++; }
  if (cleared) { Score.add([0, 100, 300, 500, 800][cleared] * level); lines += cleared; level = 1 + Math.floor(lines / 10); }
  spawn();
}
function fall() { if (!hit(cur.m, cur.x, cur.y + 1)) { cur.y++; return true; } lock(); return false; }
function frame(t) {
  if (over) return; raf = requestAnimationFrame(frame);
  var dt = Math.min(100, t - last); last = t; if (paused || overlayOpen()) { draw(); return; }
  acc += dt; if (acc >= speed()) { acc = 0; fall(); } draw();
}
function cell(px, py, k, a) {
  x.globalAlpha = a; x.fillStyle = COL[k]; glow(x, COL[k], a < 1 ? 0 : 8); rr(x, px + 1, py + 1, CS - 2, CS - 2, 5); x.fill();
  x.shadowBlur = 0; x.fillStyle = "rgba(255,255,255,.18)"; x.fillRect(px + 4, py + 3, CS - 8, 4); x.globalAlpha = 1;
}
function draw() {
  x.clearRect(0, 0, 470, 600); x.fillStyle = "rgba(0,0,0,.25)"; x.fillRect(0, 0, W * CS, H * CS);
  x.strokeStyle = "rgba(255,255,255,.04)";
  for (var i = 1; i < W; i++) { x.beginPath(); x.moveTo(i * CS, 0); x.lineTo(i * CS, H * CS); x.stroke(); }
  for (var j = 1; j < H; j++) { x.beginPath(); x.moveTo(0, j * CS); x.lineTo(W * CS, j * CS); x.stroke(); }
  board.forEach(function (r, y) { r.forEach(function (k, i) { if (k) cell(i * CS, y * CS, k, 1); }); });
  if (cur && !over) {
    var gy = cur.y; while (!hit(cur.m, cur.x, gy + 1)) gy++;
    cur.m.forEach(function (r, y) { r.forEach(function (v, i) { if (v && gy + y >= 0) cell((cur.x + i) * CS, (gy + y) * CS, cur.k, .22); }); });
    cur.m.forEach(function (r, y) { r.forEach(function (v, i) { if (v && cur.y + y >= 0) cell((cur.x + i) * CS, (cur.y + y) * CS, cur.k, 1); }); });
  }
  x.fillStyle = C.dim; x.font = "600 13px Segoe UI"; x.textAlign = "left";
  x.fillText("NEXT", 330, 34); var nm = SH[nextK];
  nm.forEach(function (r, y) { r.forEach(function (v, i) { if (v) cell(330 + i * CS, 50 + y * CS, nextK, 1); }); });
  [["LEVEL", level], ["LINES", lines]].forEach(function (p, n) {
    x.fillStyle = C.dim; x.font = "600 13px Segoe UI"; x.fillText(p[0], 330, 210 + n * 70);
    x.fillStyle = C.text; x.font = "300 30px Segoe UI"; x.fillText(p[1], 330, 244 + n * 70); });
  if (paused) { x.fillStyle = "rgba(0,0,0,.55)"; x.fillRect(0, 0, W * CS, H * CS); x.fillStyle = C.text; x.font = "bold 30px Segoe UI"; x.textAlign = "center"; x.fillText("Paused", 150, 300); }
}
addEventListener("keydown", function (e) {
  if (over || overlayOpen() || !cur) return; var k = e.key.toLowerCase();
  if (k === "p") { paused = !paused; return; } if (paused) return;
  if (k === "arrowleft" || k === "a") { if (!hit(cur.m, cur.x - 1, cur.y)) cur.x--; }
  else if (k === "arrowright" || k === "d") { if (!hit(cur.m, cur.x + 1, cur.y)) cur.x++; }
  else if (k === "arrowdown" || k === "s") { if (fall()) Score.add(1); acc = 0; }
  else if (k === "arrowup" || k === "w" || k === "x") {
    var m = rot(cur.m); for (var kick of [0, -1, 1, -2, 2]) if (!hit(m, cur.x + kick, cur.y)) { cur.m = m; cur.x += kick; break; }
  } else if (k === " ") { var n = 0; while (!hit(cur.m, cur.x, cur.y + 1)) { cur.y++; n++; } Score.add(n * 2); lock(); acc = 0; }
  draw();
});
restart();
""", body='<canvas id="c" width="470" height="600"></canvas>')

# ------------------------------------------------------------------------------ 2048
game("fusion", "Fusion 2048", "🔢", "Slide and merge matching tiles. Can you reach 2048?", "Arrows / WASD / swipe", r"""
var bd = $("board"), g, won, done;
function empty() { var e = []; for (var y = 0; y < 4; y++) for (var i = 0; i < 4; i++) if (!g[y][i]) e.push([y, i]); return e; }
function add() { var e = empty(); if (!e.length) return; var p = e[ri(0, e.length - 1)]; g[p[0]][p[1]] = Math.random() < .9 ? 2 : 4; return p; }
function restart() { g = [[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]; won = false; done = false; Score.set(0); add(); add(); draw(); hideOverlay(); }
function color(v) {
  if (!v) return "rgba(255,255,255,.05)"; var n = Math.log2(v);
  return "hsl(" + ((230 - n * 22 + 360) % 360) + "," + (55 + n * 3) + "%," + Math.max(30, 62 - n * 2.5) + "%)";
}
function draw(fresh) {
  bd.innerHTML = "";
  g.forEach(function (r, y) { r.forEach(function (v, i) {
    var c = document.createElement("div"); c.className = "cell" + (fresh && fresh[0] === y && fresh[1] === i ? " pop" : ""); c.textContent = v || "";
    c.style.background = color(v); if (v >= 128) c.style.boxShadow = "0 0 " + Math.min(30, Math.log2(v) * 2.5) + "px " + color(v);
    if (v >= 1024) c.style.fontSize = "calc(var(--s) * .27)"; else if (v >= 128) c.style.fontSize = "calc(var(--s) * .31)";
    bd.appendChild(c); }); });
}
function slide(row) {
  var a = row.filter(function (v) { return v; }), out = [];
  for (var i = 0; i < a.length; i++) { if (a[i] === a[i + 1]) { out.push(a[i] * 2); Score.add(a[i] * 2); if (a[i] * 2 === 2048 && !won) won = "new"; i++; } else out.push(a[i]); }
  while (out.length < 4) out.push(0); return out;
}
function move(d) {
  if (done || overlayOpen()) return; var before = JSON.stringify(g);
  for (var k = 0; k < 4; k++) {
    var line = [];
    for (var j = 0; j < 4; j++) line.push(d === "l" ? g[k][j] : d === "r" ? g[k][3 - j] : d === "u" ? g[j][k] : g[3 - j][k]);
    line = slide(line);
    for (j = 0; j < 4; j++) { if (d === "l") g[k][j] = line[j]; else if (d === "r") g[k][3 - j] = line[j]; else if (d === "u") g[j][k] = line[j]; else g[3 - j][k] = line[j]; }
  }
  if (JSON.stringify(g) === before) return;
  var p = add(); draw(p); submit(Score.v);
  if (won === "new") { won = true; overlay("2048! 🎉", "You made it. Keep going for a higher score?", "Keep going"); return; }
  if (!canMove()) { done = true; overlay("No more moves", "Score " + Score.v, "Play again", restart); }
}
function canMove() {
  if (empty().length) return true;
  for (var y = 0; y < 4; y++) for (var i = 0; i < 4; i++) { if (i < 3 && g[y][i] === g[y][i + 1]) return true; if (y < 3 && g[y][i] === g[y + 1][i]) return true; }
  return false;
}
addEventListener("keydown", function (e) {
  var d = { arrowleft: "l", a: "l", arrowright: "r", d: "r", arrowup: "u", w: "u", arrowdown: "d", s: "d" }[e.key.toLowerCase()]; if (d) move(d);
});
var t0 = null;
bd.addEventListener("pointerdown", function (e) { t0 = { x: e.clientX, y: e.clientY }; });
addEventListener("pointerup", function (e) {
  if (!t0) return; var dx = e.clientX - t0.x, dy = e.clientY - t0.y; t0 = null;
  if (Math.max(Math.abs(dx), Math.abs(dy)) < 30) return; move(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "r" : "l") : (dy > 0 ? "d" : "u"));
});
restart();
""", body='<div id="board"></div>', css="""
#board { display: grid; grid-template-columns: repeat(4, var(--s)); gap: 12px; padding: 12px; background: rgba(0,0,0,.3); border-radius: 18px;
         --s: min(112px, 17vmin); box-shadow: 0 20px 60px rgba(0,0,0,.45), 0 0 0 1px rgba(255,255,255,.06); touch-action: none; }
.cell { width: var(--s); height: var(--s); border-radius: 11px; display: grid; place-items: center; font-weight: 800;
        font-size: calc(var(--s) * .38); color: #fff; text-shadow: 0 2px 6px rgba(0,0,0,.35); }
.cell.pop { animation: pop .18s ease; } @keyframes pop { from { transform: scale(.4); opacity: .3; } }
""")

# ------------------------------------------------------------------------------ Brick breaker
game("bricks", "Brick Breaker", "🧱", "Bounce the ball, smash every brick. 3 lives.", "Mouse / ←→ move · Click / Space launch", r"""
var cv = $("c"), x = cv.getContext("2d"), WD = 760, HT = 540, pad, ball, bricks, lives, level, raf, over, last;
function makeBricks() {
  bricks = []; var rows = Math.min(8, 4 + level), cols = 11, bw = 62, bh = 22, gap = 4, ox = (WD - cols * (bw + gap) + gap) / 2;
  for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++)
    bricks.push({ x: ox + c * (bw + gap), y: 60 + r * (bh + gap), w: bw, h: bh, hp: (level > 2 && r < 2) ? 2 : 1, hue: (r * 34 + level * 40) % 360 });
}
function resetBall() { ball = { x: pad.x + pad.w / 2, y: pad.y - 10, vx: 0, vy: 0, r: 8, stuck: true }; }
function restart() {
  cancelAnimationFrame(raf); pad = { x: WD / 2 - 60, y: HT - 36, w: 120, h: 14 }; lives = 3; level = 1; over = false; Score.set(0);
  makeBricks(); resetBall(); last = performance.now(); raf = requestAnimationFrame(frame);
  overlay("🧱 Brick Breaker", "Move with the mouse or ←→ · click or Space to launch", "Start");
}
function launch() { if (ball.stuck && !overlayOpen()) { var sp = 6 + level * .6; ball.vx = rand(-2, 2); ball.vy = -sp; ball.stuck = false; } }
function frame(t) {
  raf = requestAnimationFrame(frame); var dt = Math.min(2.5, (t - last) / 16.67); last = t;
  if (!over && !overlayOpen()) update(dt); draw();
}
function update(dt) {
  if (keys.ArrowLeft || keys.a) pad.x -= 9 * dt; if (keys.ArrowRight || keys.d) pad.x += 9 * dt;
  pad.x = Math.max(0, Math.min(WD - pad.w, pad.x));
  if (ball.stuck) { ball.x = pad.x + pad.w / 2; ball.y = pad.y - ball.r - 1; return; }
  var steps = 4;
  for (var s = 0; s < steps; s++) {
    ball.x += ball.vx * dt / steps; ball.y += ball.vy * dt / steps;
    if (ball.x < ball.r) { ball.x = ball.r; ball.vx = Math.abs(ball.vx); } if (ball.x > WD - ball.r) { ball.x = WD - ball.r; ball.vx = -Math.abs(ball.vx); }
    if (ball.y < ball.r) { ball.y = ball.r; ball.vy = Math.abs(ball.vy); }
    if (ball.vy > 0 && ball.y + ball.r >= pad.y && ball.y + ball.r <= pad.y + pad.h + 8 && ball.x >= pad.x - 6 && ball.x <= pad.x + pad.w + 6) {
      var hitPos = (ball.x - (pad.x + pad.w / 2)) / (pad.w / 2), sp = Math.hypot(ball.vx, ball.vy);
      var ang = hitPos * 1.05; ball.vx = sp * Math.sin(ang); ball.vy = -Math.abs(sp * Math.cos(ang)); ball.y = pad.y - ball.r;
    }
    for (var i = 0; i < bricks.length; i++) {
      var b = bricks[i];
      if (ball.x + ball.r < b.x || ball.x - ball.r > b.x + b.w || ball.y + ball.r < b.y || ball.y - ball.r > b.y + b.h) continue;
      var ox = Math.min(ball.x + ball.r - b.x, b.x + b.w - (ball.x - ball.r)), oy = Math.min(ball.y + ball.r - b.y, b.y + b.h - (ball.y - ball.r));
      if (ox < oy) ball.vx = -ball.vx; else ball.vy = -ball.vy;
      b.hp--; if (b.hp <= 0) { bricks.splice(i, 1); Score.add(10 * level); var sp2 = Math.hypot(ball.vx, ball.vy); if (sp2 < 13) { ball.vx *= 1.01; ball.vy *= 1.01; } }
      break;
    }
  }
  if (ball.y > HT + 20) {
    lives--; if (lives <= 0) { over = true; var nb = submit(Score.v); overlay("Game over", "Score " + Score.v + (nb && Score.v ? " · new best! 🏆" : ""), "Play again", restart); }
    else resetBall();
  }
  if (!bricks.length) { level++; makeBricks(); resetBall(); overlay("Level " + level, "Faster ball, tougher bricks.", "Go"); }
}
function draw() {
  x.clearRect(0, 0, WD, HT);
  bricks.forEach(function (b) { var c = "hsl(" + b.hue + ",80%," + (b.hp > 1 ? 45 : 62) + "%)"; glow(x, c, 10); x.fillStyle = c; rr(x, b.x, b.y, b.w, b.h, 5); x.fill();
    if (b.hp > 1) { x.shadowBlur = 0; x.strokeStyle = "rgba(255,255,255,.6)"; x.lineWidth = 2; x.stroke(); } });
  glow(x, C.a, 16); x.fillStyle = C.a; rr(x, pad.x, pad.y, pad.w, pad.h, 7); x.fill();
  glow(x, "#fff", 14); x.fillStyle = "#fff"; x.beginPath(); x.arc(ball.x, ball.y, ball.r, 0, 7); x.fill(); x.shadowBlur = 0;
  x.fillStyle = C.dim; x.font = "600 14px Segoe UI"; x.textAlign = "left"; x.fillText("Level " + level, 14, 28);
  x.textAlign = "right"; x.fillText("❤".repeat(Math.max(0, lives)), WD - 14, 28);
}
cv.addEventListener("mousemove", function (e) { pad.x = canvasPoint(cv, e).x - pad.w / 2; });
cv.addEventListener("click", launch);
addEventListener("keydown", function (e) { if (e.key === " ") launch(); });
restart();
""", body='<canvas id="c" width="760" height="540"></canvas>')

# ------------------------------------------------------------------------------ Flappy-style
game("flight", "Nova Flight", "🚀", "Tap to fly through the gaps. One touch and it's over.", "Click / Space / ↑ to fly", r"""
var cv = $("c"), x = cv.getContext("2d"), WD = 480, HT = 640, p, pipes, stars, t, raf, last, state;
function restart() {
  cancelAnimationFrame(raf); p = { y: HT / 2, vy: 0 }; pipes = []; t = 0; state = "ready"; Score.set(0);
  stars = []; for (var i = 0; i < 70; i++) stars.push({ x: rand(0, WD), y: rand(0, HT), s: rand(.2, 1.2) });
  last = performance.now(); raf = requestAnimationFrame(frame);
}
function flap() { if (overlayOpen()) return; if (state === "dead") return; if (state === "ready") state = "play"; p.vy = -7.6; }
function frame(now) {
  raf = requestAnimationFrame(frame); var dt = Math.min(2.5, (now - last) / 16.67); last = now;
  stars.forEach(function (s) { s.x -= s.s * dt; if (s.x < 0) { s.x = WD; s.y = rand(0, HT); } });
  if (state === "play") {
    t += dt; p.vy += .42 * dt; p.y += p.vy * dt; var sp = 2.7 + Math.min(2, Score.v * .04);
    if (!pipes.length || pipes[pipes.length - 1].x < WD - 230) { var gap = Math.max(140, 180 - Score.v * 1.2); pipes.push({ x: WD + 40, top: rand(70, HT - 70 - gap), gap: gap, done: false }); }
    pipes.forEach(function (q) { q.x -= sp * dt; if (!q.done && q.x + 60 < 110) { q.done = true; Score.add(1); } });
    pipes = pipes.filter(function (q) { return q.x > -80; });
    var hit = p.y > HT - 14 || p.y < 14 || pipes.some(function (q) { return 110 + 14 > q.x && 110 - 14 < q.x + 60 && (p.y - 13 < q.top || p.y + 13 > q.top + q.gap); });
    if (hit) { state = "dead"; var nb = submit(Score.v); overlay("Crashed!", "Score " + Score.v + (nb && Score.v ? " · new best! 🏆" : ""), "Fly again", restart); }
  } else if (state === "ready") { p.y = HT / 2 + Math.sin(now / 300) * 10; }
  draw(now);
}
function draw(now) {
  x.clearRect(0, 0, WD, HT);
  stars.forEach(function (s) { x.fillStyle = "rgba(255,255,255," + (s.s * .6) + ")"; x.fillRect(s.x, s.y, s.s * 2, s.s * 2); });
  pipes.forEach(function (q) {
    var gr = x.createLinearGradient(q.x, 0, q.x + 60, 0); gr.addColorStop(0, C.a); gr.addColorStop(1, C.al);
    glow(x, C.a, 18); x.fillStyle = gr; rr(x, q.x, -20, 60, q.top + 20, 10); x.fill(); rr(x, q.x, q.top + q.gap, 60, HT - q.top - q.gap + 20, 10); x.fill();
  });
  x.shadowBlur = 0; x.save(); x.translate(110, p.y); x.rotate(Math.max(-.5, Math.min(1.2, p.vy / 10)));
  glow(x, "#ff8a4c", 20); x.fillStyle = "#ff8a4c"; x.beginPath(); x.moveTo(-16, -6); x.lineTo(-28 - Math.random() * 10, 0); x.lineTo(-16, 6); x.fill();
  glow(x, "#fff", 12); x.fillStyle = "#f4f6ff"; x.beginPath(); x.moveTo(18, 0); x.lineTo(-14, -12); x.lineTo(-10, 0); x.lineTo(-14, 12); x.closePath(); x.fill();
  x.fillStyle = C.a; x.beginPath(); x.arc(2, 0, 4, 0, 7); x.fill(); x.restore(); x.shadowBlur = 0;
  x.fillStyle = "#fff"; x.font = "bold 46px Segoe UI"; x.textAlign = "center"; if (state !== "ready") x.fillText(Score.v, WD / 2, 80);
  if (state === "ready") { x.font = "600 18px Segoe UI"; x.fillStyle = C.text; x.fillText("Click or press Space to fly", WD / 2, HT / 2 + 90); }
}
cv.addEventListener("pointerdown", flap);
addEventListener("keydown", function (e) { if ((e.key === " " || e.key === "ArrowUp" || e.key === "w") && !e.repeat) flap(); });
restart();
""", body='<canvas id="c" width="480" height="640"></canvas>')

# ------------------------------------------------------------------------------ Minesweeper
game("mines", "Mine Sweep", "💣", "Clear the field without hitting a mine. First click is always safe.", "Click reveal · Right-click flag", r"""
var LEVELS = { Easy: [9, 9, 10], Medium: [16, 16, 40], Hard: [16, 30, 99] };
var grid = $("grid"), sel = $("level"), R, Cc, M, cells, first, over, flags, timer, secs, opened;
function fmtBest(v) { return v + " won"; }
function bestTime() { try { return localStorage.getItem("nova-game-mines-time-" + sel.value); } catch (e) { return null; } }
function restart() {
  clearInterval(timer); var L = LEVELS[sel.value]; R = L[0]; Cc = L[1]; M = L[2]; first = true; over = false; flags = 0; secs = 0; opened = 0;
  cells = []; for (var i = 0; i < R * Cc; i++) cells.push({ m: false, n: 0, open: false, flag: false });
  grid.style.gridTemplateColumns = "repeat(" + Cc + ", var(--cs))"; grid.style.setProperty("--cs", Math.min(34, Math.floor(Math.min(innerWidth - 60, 1100) / Cc), Math.floor((innerHeight - 140) / R)) + "px");
  Score.set(0); $("mleft").textContent = M; var bt = bestTime(); $("btime").textContent = bt ? bt + "s" : "–"; draw(); hideOverlay();
}
function nb(i) { var r = Math.floor(i / Cc), c = i % Cc, o = []; for (var dr = -1; dr <= 1; dr++) for (var dc = -1; dc <= 1; dc++) {
  if (!dr && !dc) continue; var rr2 = r + dr, cc = c + dc; if (rr2 >= 0 && rr2 < R && cc >= 0 && cc < Cc) o.push(rr2 * Cc + cc); } return o; }
function plant(safe) {
  var no = nb(safe).concat([safe]), placed = 0;
  while (placed < M) { var i = ri(0, R * Cc - 1); if (cells[i].m || no.indexOf(i) >= 0) continue; cells[i].m = true; placed++; }
  cells.forEach(function (c, i) { c.n = nb(i).filter(function (j) { return cells[j].m; }).length; });
}
function open(i) {
  var c = cells[i]; if (c.open || c.flag) return; c.open = true; opened++;
  if (c.m) { lose(i); return; } if (!c.n) nb(i).forEach(open);
}
function lose(i) {
  over = true; clearInterval(timer); cells.forEach(function (c) { if (c.m) c.open = true; }); draw(i);
  overlay("💥 Boom", "You hit a mine after " + secs + "s.", "Try again", restart);
}
function checkWin() {
  if (!over && opened === R * Cc - M) {
    over = true; clearInterval(timer); cells.forEach(function (c) { if (c.m) c.flag = true; }); draw(); addWin();
    var bt = bestTime(), nbst = !bt || secs < Number(bt); if (nbst) try { localStorage.setItem("nova-game-mines-time-" + sel.value, String(secs)); } catch (e) {}
    $("btime").textContent = (nbst ? secs : bt) + "s";
    overlay("Cleared! 🎉", sel.value + " in " + secs + "s" + (nbst ? " · new best time! 🏆" : ""), "Play again", restart);
  }
}
function click(i) {
  if (over || overlayOpen()) return;
  if (first) { first = false; plant(i); timer = setInterval(function () { secs++; Score.set(secs); }, 1000); }
  var c = cells[i];
  if (c.open && c.n) { var f = nb(i).filter(function (j) { return cells[j].flag; }).length; if (f === c.n) nb(i).forEach(open); }
  else open(i);
  if (!over) { draw(); checkWin(); }
}
function flag(i) { if (over || first || cells[i].open) return; cells[i].flag = !cells[i].flag; flags += cells[i].flag ? 1 : -1; $("mleft").textContent = M - flags; draw(); }
var NC = ["", "#6c8cff", "#2fd38a", "#ff5a6a", "#a46cff", "#ff8a4c", "#36c9e6", "#e6e6e6", "#9a9ca6"];
function draw(boom) {
  grid.innerHTML = "";
  cells.forEach(function (c, i) {
    var d = document.createElement("div"); d.className = "mc" + (c.open ? " open" : "") + (i === boom ? " boom" : ""); d.dataset.i = i;
    if (c.open) { if (c.m) d.textContent = "💣"; else if (c.n) { d.textContent = c.n; d.style.color = NC[c.n]; } }
    else if (c.flag) d.textContent = "🚩";
    grid.appendChild(d);
  });
}
grid.addEventListener("click", function (e) { var t = e.target.closest(".mc"); if (t) click(+t.dataset.i); });
grid.addEventListener("contextmenu", function (e) { e.preventDefault(); var t = e.target.closest(".mc"); if (t) flag(+t.dataset.i); });
sel.addEventListener("change", function () { restart(); sel.blur(); });
restart();
""", body='<div id="grid"></div>', score_label="Time", best_label="Wins", extra=(
    '<select class="b" id="level"><option>Easy</option><option selected>Medium</option><option>Hard</option></select>'
    '<span class="stat">Mines<b id="mleft">0</b></span><span class="stat">Best time<b id="btime">–</b></span>'), css="""
#grid { display: grid; gap: 3px; padding: 10px; background: rgba(0,0,0,.3); border-radius: 14px; box-shadow: 0 20px 60px rgba(0,0,0,.45); }
.mc { width: var(--cs); height: var(--cs); border-radius: 5px; background: color-mix(in srgb, var(--a) 30%, #2a2d38); display: grid; place-items: center;
      font-weight: 800; font-size: calc(var(--cs) * .5); cursor: pointer; transition: background .1s; }
.mc:hover { background: color-mix(in srgb, var(--a) 45%, #2a2d38); }
.mc.open { background: rgba(255,255,255,.06); cursor: default; } .mc.boom { background: #ff5a6a; }
""")

# ------------------------------------------------------------------------------ Memory
game("memory", "Memory Cards", "🃏", "Flip cards and find all the pairs in as few moves as you can.", "Click two cards", r"""
var grid = $("grid"), EMO = ["🚀", "🌙", "🪐", "⭐", "☄️", "🛸", "👾", "🌌", "🔭", "🌠", "🌍", "☀️"], deck, open, lock, moves, found;
function restart() {
  var pick = EMO.slice().sort(function () { return Math.random() - .5; }).slice(0, 8);
  deck = pick.concat(pick).sort(function () { return Math.random() - .5; }).map(function (e) { return { e: e, up: false, done: false }; });
  open = []; lock = false; moves = 0; found = 0; Score.set(0); draw(); hideOverlay();
}
function draw() {
  grid.innerHTML = "";
  deck.forEach(function (c, i) {
    var d = document.createElement("div"); d.className = "card2" + (c.up || c.done ? " up" : "") + (c.done ? " done" : ""); d.dataset.i = i;
    d.innerHTML = '<div class="face back">✦</div><div class="face front">' + c.e + "</div>"; grid.appendChild(d);
  });
}
grid.addEventListener("click", function (e) {
  var t = e.target.closest(".card2"); if (!t || lock) return; var c = deck[+t.dataset.i]; if (c.up || c.done) return;
  c.up = true; open.push(c); t.classList.add("up");
  if (open.length === 2) {
    moves++; Score.set(moves); lock = true;
    setTimeout(function () {
      if (open[0].e === open[1].e) { open[0].done = open[1].done = true; found++; } else { open[0].up = open[1].up = false; }
      open = []; lock = false; draw();
      if (found === 8) { var nb = submit(moves); overlay("All pairs found! 🎉", moves + " moves" + (nb ? " · new best! 🏆" : ""), "Play again", restart); }
    }, 650);
  }
});
restart();
""", body='<div id="grid"></div>', score_label="Moves", best_label="Fewest moves", lower=True, css="""
#grid { display: grid; grid-template-columns: repeat(4, var(--s)); gap: 14px; --s: min(118px, 18vmin); perspective: 900px; }
.card2 { width: var(--s); height: var(--s); position: relative; cursor: pointer; transform-style: preserve-3d; transition: transform .35s; }
.card2.up { transform: rotateY(180deg); }
.face { position: absolute; inset: 0; border-radius: 14px; display: grid; place-items: center; backface-visibility: hidden; }
.back { background: linear-gradient(135deg, var(--a), color-mix(in srgb, var(--a) 40%, #000)); color: rgba(255,255,255,.75); font-size: calc(var(--s) * .3);
        box-shadow: 0 10px 24px rgba(0,0,0,.35); }
.front { background: var(--card); transform: rotateY(180deg); font-size: calc(var(--s) * .48); box-shadow: 0 0 0 1px rgba(255,255,255,.08); }
.card2.done .front { box-shadow: 0 0 0 2px var(--a), 0 0 22px color-mix(in srgb, var(--a) 50%, transparent); }
""")

# ------------------------------------------------------------------------------ Pong
game("paddle", "Paddle Duel", "🏓", "Classic paddle tennis against the computer. First to 7 wins.", "Mouse / W S / ↑↓", r"""
var cv = $("c"), x = cv.getContext("2d"), WD = 800, HT = 500, P, A, ball, you, cpu, raf, last, over, serveT;
function restart() {
  cancelAnimationFrame(raf); P = { y: HT / 2 - 45, h: 90 }; A = { y: HT / 2 - 45, h: 90 }; you = 0; cpu = 0; over = false; Score.set("0 – 0");
  serve(1); last = performance.now(); raf = requestAnimationFrame(frame); overlay("🏓 Paddle Duel", "First to 7 wins · move with the mouse, W/S or ↑↓", "Serve");
}
function serve(dir) { ball = { x: WD / 2, y: HT / 2, vx: 0, vy: 0, r: 9 }; serveT = 45; ball.dir = dir; }
function frame(t) { raf = requestAnimationFrame(frame); var dt = Math.min(2.5, (t - last) / 16.67); last = t; if (!over && !overlayOpen()) update(dt); draw(); }
function update(dt) {
  if (keys.w || keys.ArrowUp) P.y -= 8 * dt; if (keys.s || keys.ArrowDown) P.y += 8 * dt; P.y = Math.max(0, Math.min(HT - P.h, P.y));
  var target = ball.vx > 0 ? ball.y - A.h / 2 + Math.sin(performance.now() / 300) * 18 : HT / 2 - A.h / 2;
  var maxS = 5.2 + Math.min(3, (you + cpu) * .25); A.y += Math.max(-maxS, Math.min(maxS, (target - A.y) * .09)) * dt; A.y = Math.max(0, Math.min(HT - A.h, A.y));
  if (serveT > 0) { serveT -= dt; if (serveT <= 0) { ball.vx = 6 * ball.dir; ball.vy = rand(-3, 3); } return; }
  ball.x += ball.vx * dt; ball.y += ball.vy * dt;
  if (ball.y < ball.r || ball.y > HT - ball.r) { ball.vy = -ball.vy; ball.y = Math.max(ball.r, Math.min(HT - ball.r, ball.y)); }
  [[30, P], [WD - 44, A]].forEach(function (pp) {
    var px = pp[0], pd = pp[1];
    if (ball.x + ball.r > px && ball.x - ball.r < px + 14 && ball.y > pd.y - 6 && ball.y < pd.y + pd.h + 6) {
      var rel = (ball.y - (pd.y + pd.h / 2)) / (pd.h / 2), sp = Math.min(15, Math.hypot(ball.vx, ball.vy) * 1.06);
      var dir = px < WD / 2 ? 1 : -1; ball.vx = dir * sp * Math.cos(rel * .9); ball.vy = sp * Math.sin(rel * .9); ball.x = px < WD / 2 ? px + 14 + ball.r : px - ball.r;
    }
  });
  if (ball.x < -20) { cpu++; point(1); } else if (ball.x > WD + 20) { you++; point(-1); }
}
function point(dir) {
  Score.set(you + " – " + cpu);
  if (you >= 7 || cpu >= 7) { over = true; if (you > cpu) addWin();
    overlay(you > cpu ? "You win! 🏆" : "CPU wins", you + " – " + cpu, "Play again", restart); } else serve(dir);
}
function draw() {
  x.clearRect(0, 0, WD, HT); x.setLineDash([10, 14]); x.strokeStyle = "rgba(255,255,255,.12)"; x.lineWidth = 3;
  x.beginPath(); x.moveTo(WD / 2, 0); x.lineTo(WD / 2, HT); x.stroke(); x.setLineDash([]);
  x.fillStyle = "rgba(255,255,255,.08)"; x.font = "bold 90px Segoe UI"; x.textAlign = "center"; x.fillText(you, WD / 2 - 110, 110); x.fillText(cpu, WD / 2 + 110, 110);
  glow(x, C.a, 18); x.fillStyle = C.a; rr(x, 30, P.y, 14, P.h, 7); x.fill();
  glow(x, "#ff6fae", 18); x.fillStyle = "#ff6fae"; rr(x, WD - 44, A.y, 14, A.h, 7); x.fill();
  glow(x, "#fff", 14); x.fillStyle = "#fff"; x.beginPath(); x.arc(ball.x, ball.y, ball.r, 0, 7); x.fill(); x.shadowBlur = 0;
}
cv.addEventListener("mousemove", function (e) { P.y = canvasPoint(cv, e).y - P.h / 2; });
restart();
""", body='<canvas id="c" width="800" height="500"></canvas>', score_label="You – CPU", best_label="Wins")

# ------------------------------------------------------------------------------ Asteroids-style
game("rocks", "Space Rocks", "☄️", "Blast the space rocks before they hit your ship.", "←→ turn · ↑ thrust · Space shoot", r"""
var cv = $("c"), x = cv.getContext("2d"), WD = 820, HT = 560, ship, bullets, rocks, parts, lives, level, raf, last, over, cool, inv;
function rock(px, py, size) {
  var r = [0, 15, 28, 48][size], pts = []; for (var i = 0; i < 11; i++) pts.push(r * rand(.72, 1.15));
  var a = rand(0, 6.28), sp = rand(.6, 1.6) * (4 - size) * .55 + level * .12;
  return { x: px, y: py, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, r: r, size: size, pts: pts, rot: rand(-.02, .02), ang: 0 };
}
function wave() { rocks = []; for (var i = 0; i < 3 + level; i++) { var px, py; do { px = rand(0, WD); py = rand(0, HT); } while (Math.hypot(px - WD / 2, py - HT / 2) < 160); rocks.push(rock(px, py, 3)); } }
function newShip() { ship = { x: WD / 2, y: HT / 2, a: -Math.PI / 2, vx: 0, vy: 0 }; inv = 120; }
function restart() {
  cancelAnimationFrame(raf); lives = 3; level = 1; over = false; bullets = []; parts = []; cool = 0; Score.set(0); newShip(); wave();
  last = performance.now(); raf = requestAnimationFrame(frame); overlay("☄️ Space Rocks", "←→ turn · ↑ thrust · Space shoot", "Launch");
}
function wrap(o) { if (o.x < -50) o.x += WD + 100; if (o.x > WD + 50) o.x -= WD + 100; if (o.y < -50) o.y += HT + 100; if (o.y > HT + 50) o.y -= HT + 100; }
function boom(px, py, n, col) { for (var i = 0; i < n; i++) { var a = rand(0, 6.28), s = rand(.5, 4); parts.push({ x: px, y: py, vx: Math.cos(a) * s, vy: Math.sin(a) * s, life: rand(20, 45), c: col }); } }
function frame(t) { raf = requestAnimationFrame(frame); var dt = Math.min(2.5, (t - last) / 16.67); last = t; if (!over && !overlayOpen()) update(dt); draw(); }
function update(dt) {
  if (ship) {
    if (keys.ArrowLeft || keys.a) ship.a -= .075 * dt; if (keys.ArrowRight || keys.d) ship.a += .075 * dt;
    ship.thrust = keys.ArrowUp || keys.w;
    if (ship.thrust) { ship.vx += Math.cos(ship.a) * .16 * dt; ship.vy += Math.sin(ship.a) * .16 * dt; }
    ship.vx *= Math.pow(.99, dt); ship.vy *= Math.pow(.99, dt); ship.x += ship.vx * dt; ship.y += ship.vy * dt; wrap(ship);
    cool -= dt; if (keys[" "] && cool <= 0 && bullets.length < 7) { cool = 9; bullets.push({ x: ship.x + Math.cos(ship.a) * 16, y: ship.y + Math.sin(ship.a) * 16,
      vx: Math.cos(ship.a) * 9 + ship.vx, vy: Math.sin(ship.a) * 9 + ship.vy, life: 60 }); }
    if (inv > 0) inv -= dt;
  }
  bullets.forEach(function (b) { b.x += b.vx * dt; b.y += b.vy * dt; b.life -= dt; wrap(b); }); bullets = bullets.filter(function (b) { return b.life > 0; });
  rocks.forEach(function (r) { r.x += r.vx * dt; r.y += r.vy * dt; r.ang += r.rot * dt; wrap(r); });
  parts.forEach(function (p) { p.x += p.vx * dt; p.y += p.vy * dt; p.life -= dt; }); parts = parts.filter(function (p) { return p.life > 0; });
  for (var i = rocks.length - 1; i >= 0; i--) {
    var r = rocks[i];
    for (var j = bullets.length - 1; j >= 0; j--) {
      if (Math.hypot(bullets[j].x - r.x, bullets[j].y - r.y) < r.r) {
        bullets.splice(j, 1); rocks.splice(i, 1); Score.add([0, 100, 50, 20][r.size]); boom(r.x, r.y, 10 + r.size * 4, C.al);
        if (r.size > 1) { rocks.push(rock(r.x, r.y, r.size - 1)); rocks.push(rock(r.x, r.y, r.size - 1)); }
        break;
      }
    }
  }
  if (ship && inv <= 0) for (var k = 0; k < rocks.length; k++) if (Math.hypot(ship.x - rocks[k].x, ship.y - rocks[k].y) < rocks[k].r + 11) {
    boom(ship.x, ship.y, 40, "#ff8a4c"); lives--; ship = null;
    if (lives <= 0) { over = true; var nb = submit(Score.v); setTimeout(function () { overlay("Ship destroyed", "Score " + Score.v + (nb && Score.v ? " · new best! 🏆" : ""), "Play again", restart); }, 700); }
    else setTimeout(newShip, 1100); break;
  }
  if (!rocks.length) { level++; wave(); }
}
function draw() {
  x.clearRect(0, 0, WD, HT); x.lineWidth = 2;
  rocks.forEach(function (r) { x.save(); x.translate(r.x, r.y); x.rotate(r.ang); glow(x, C.a, 10); x.strokeStyle = C.al; x.fillStyle = "rgba(108,140,255,.08)";
    x.beginPath(); r.pts.forEach(function (d, i) { var a = i / r.pts.length * 6.283; x[i ? "lineTo" : "moveTo"](Math.cos(a) * d, Math.sin(a) * d); }); x.closePath(); x.fill(); x.stroke(); x.restore(); });
  bullets.forEach(function (b) { glow(x, "#fff", 10); x.fillStyle = "#fff"; x.beginPath(); x.arc(b.x, b.y, 2.5, 0, 7); x.fill(); });
  parts.forEach(function (p) { x.globalAlpha = Math.min(1, p.life / 30); x.fillStyle = p.c; x.fillRect(p.x, p.y, 2.5, 2.5); }); x.globalAlpha = 1;
  if (ship && !(inv > 0 && Math.floor(inv / 6) % 2)) {
    x.save(); x.translate(ship.x, ship.y); x.rotate(ship.a); glow(x, "#fff", 14); x.strokeStyle = "#fff";
    x.beginPath(); x.moveTo(16, 0); x.lineTo(-11, -10); x.lineTo(-6, 0); x.lineTo(-11, 10); x.closePath(); x.stroke();
    if (ship.thrust) { glow(x, "#ff8a4c", 14); x.strokeStyle = "#ff8a4c"; x.beginPath(); x.moveTo(-8, -5); x.lineTo(-18 - Math.random() * 8, 0); x.lineTo(-8, 5); x.stroke(); }
    x.restore();
  }
  x.shadowBlur = 0; x.fillStyle = C.dim; x.font = "600 14px Segoe UI"; x.textAlign = "left"; x.fillText("Wave " + level, 14, 26);
  x.textAlign = "right"; x.fillText("🚀".repeat(Math.max(0, lives)), WD - 14, 26);
}
restart();
""", body='<canvas id="c" width="820" height="560"></canvas>')

# ------------------------------------------------------------------------------ Four in a row
game("four", "Four in a Row", "🔴", "Drop discs and connect four before the computer does.", "Click a column", r"""
var cv = $("c"), x = cv.getContext("2d"), COLS = 7, ROWS = 6, CS = 86, OX = 15, OY = 70, b, turn, over, hover, depth, anim;
var sel = $("diff");
function restart() { b = []; for (var r = 0; r < ROWS; r++) b.push(new Array(COLS).fill(0)); turn = 1; over = false; hover = -1; anim = null; depth = { Easy: 2, Normal: 4, Hard: 6 }[sel.value]; hideOverlay(); draw(); }
function drop(bd, c, p) { for (var r = ROWS - 1; r >= 0; r--) if (!bd[r][c]) { bd[r][c] = p; return r; } return -1; }
function win(bd, p) {
  for (var r = 0; r < ROWS; r++) for (var c = 0; c < COLS; c++) {
    if (bd[r][c] !== p) continue;
    if (c + 3 < COLS && bd[r][c + 1] === p && bd[r][c + 2] === p && bd[r][c + 3] === p) return [[r, c], [r, c + 1], [r, c + 2], [r, c + 3]];
    if (r + 3 < ROWS && bd[r + 1][c] === p && bd[r + 2][c] === p && bd[r + 3][c] === p) return [[r, c], [r + 1, c], [r + 2, c], [r + 3, c]];
    if (r + 3 < ROWS && c + 3 < COLS && bd[r + 1][c + 1] === p && bd[r + 2][c + 2] === p && bd[r + 3][c + 3] === p) return [[r, c], [r + 1, c + 1], [r + 2, c + 2], [r + 3, c + 3]];
    if (r - 3 >= 0 && c + 3 < COLS && bd[r - 1][c + 1] === p && bd[r - 2][c + 2] === p && bd[r - 3][c + 3] === p) return [[r, c], [r - 1, c + 1], [r - 2, c + 2], [r - 3, c + 3]];
  }
  return null;
}
function full(bd) { return bd[0].every(function (v) { return v; }); }
function scoreWin(w, p) { var me = 0, op = 0, e = 0; w.forEach(function (v) { if (v === p) me++; else if (v) op++; else e++; });
  if (me === 4) return 1000; if (me === 3 && e === 1) return 6; if (me === 2 && e === 2) return 2; if (op === 3 && e === 1) return -5; return 0; }
function evalB(bd, p) {
  var s = 0; for (var r = 0; r < ROWS; r++) if (bd[r][3] === p) s += 3;
  for (r = 0; r < ROWS; r++) for (var c = 0; c < COLS; c++) {
    if (c + 3 < COLS) s += scoreWin([bd[r][c], bd[r][c + 1], bd[r][c + 2], bd[r][c + 3]], p);
    if (r + 3 < ROWS) s += scoreWin([bd[r][c], bd[r + 1][c], bd[r + 2][c], bd[r + 3][c]], p);
    if (r + 3 < ROWS && c + 3 < COLS) s += scoreWin([bd[r][c], bd[r + 1][c + 1], bd[r + 2][c + 2], bd[r + 3][c + 3]], p);
    if (r - 3 >= 0 && c + 3 < COLS) s += scoreWin([bd[r][c], bd[r - 1][c + 1], bd[r - 2][c + 2], bd[r - 3][c + 3]], p);
  }
  return s;
}
var ORDER = [3, 2, 4, 1, 5, 0, 6];
function mm(bd, d, a, bt, maxP) {
  if (win(bd, 2)) return [null, 100000 + d]; if (win(bd, 1)) return [null, -100000 - d]; if (full(bd) || d === 0) return [null, evalB(bd, 2) - evalB(bd, 1)];
  var best = null, val = maxP ? -Infinity : Infinity;
  for (var k = 0; k < 7; k++) { var c = ORDER[k]; if (bd[0][c]) continue; var r = drop(bd, c, maxP ? 2 : 1), v = mm(bd, d - 1, a, bt, !maxP)[1]; bd[r][c] = 0;
    if (maxP ? v > val : v < val) { val = v; best = c; } if (maxP) a = Math.max(a, val); else bt = Math.min(bt, val); if (a >= bt) break; }
  return [best, val];
}
function play(c, p, then) {
  if (b[0][c]) return; var r = drop(b, c, p); b[r][c] = 0; anim = { c: c, r: r, p: p, y: OY - CS / 2, then: then };
  (function step() { anim.y += 26; if (anim.y >= OY + r * CS + CS / 2) { b[r][c] = p; var t = anim.then; anim = null; draw(); t(); return; } draw(); requestAnimationFrame(step); })();
}
function check(p) {
  var w = win(b, p); if (w) { over = true; draw(w); if (p === 1) { addWin(); Score.set("You won"); }
    setTimeout(function () { overlay(p === 1 ? "You win! 🏆" : "Computer wins", p === 1 ? "Four in a row!" : "Better luck next time.", "Play again", restart); }, 700); return true; }
  if (full(b)) { over = true; overlay("Draw", "The board is full.", "Play again", restart); return true; }
  return false;
}
cv.addEventListener("mousemove", function (e) { var c = Math.floor((canvasPoint(cv, e).x - OX) / CS); hover = c >= 0 && c < COLS ? c : -1; if (!anim) draw(); });
cv.addEventListener("mouseleave", function () { hover = -1; if (!anim) draw(); });
cv.addEventListener("click", function (e) {
  if (over || anim || turn !== 1 || overlayOpen()) return; var c = Math.floor((canvasPoint(cv, e).x - OX) / CS); if (c < 0 || c >= COLS || b[0][c]) return;
  turn = 2; play(c, 1, function () {
    if (check(1)) return;
    setTimeout(function () { var mv = mm(b.map(function (r) { return r.slice(); }), depth, -Infinity, Infinity, true)[0];
      if (mv == null) mv = ORDER.filter(function (k) { return !b[0][k]; })[0];
      if (sel.value === "Easy" && Math.random() < .25) { var free = ORDER.filter(function (k) { return !b[0][k]; }); mv = free[ri(0, free.length - 1)]; }
      play(mv, 2, function () { if (!check(2)) turn = 1; }); }, 120);
  });
});
function disc(cx, cy, p, a) { var col = p === 1 ? C.a : "#ff6fae"; x.globalAlpha = a; glow(x, col, 14); x.fillStyle = col; x.beginPath(); x.arc(cx, cy, CS / 2 - 8, 0, 7); x.fill();
  x.shadowBlur = 0; x.fillStyle = "rgba(255,255,255,.18)"; x.beginPath(); x.arc(cx - 8, cy - 9, CS / 6, 0, 7); x.fill(); x.globalAlpha = 1; }
function draw(w) {
  x.clearRect(0, 0, cv.width, cv.height);
  if (hover >= 0 && turn === 1 && !over && !anim) disc(OX + hover * CS + CS / 2, OY - CS / 2 + 4, 1, .55);
  x.fillStyle = "rgba(20,24,40,.9)"; rr(x, OX - 6, OY - 6, COLS * CS + 12, ROWS * CS + 12, 18); x.fill();
  for (var r = 0; r < ROWS; r++) for (var c = 0; c < COLS; c++) {
    var cx = OX + c * CS + CS / 2, cy = OY + r * CS + CS / 2;
    if (b[r][c]) disc(cx, cy, b[r][c], 1); else { x.fillStyle = "rgba(0,0,0,.45)"; x.beginPath(); x.arc(cx, cy, CS / 2 - 8, 0, 7); x.fill(); }
  }
  if (anim) disc(OX + anim.c * CS + CS / 2, anim.y, anim.p, 1);
  if (w) w.forEach(function (p) { x.strokeStyle = "#fff"; x.lineWidth = 4; x.beginPath(); x.arc(OX + p[1] * CS + CS / 2, OY + p[0] * CS + CS / 2, CS / 2 - 6, 0, 7); x.stroke(); });
}
sel.addEventListener("change", function () { restart(); sel.blur(); });
restart();
""", body='<canvas id="c" width="632" height="600"></canvas>', score_label="Status", best_label="Wins",
     extra='<select class="b" id="diff"><option>Easy</option><option selected>Normal</option><option>Hard</option></select>')

# ------------------------------------------------------------------------------ Endless runner
game("dash", "Neon Dash", "⚡", "Jump the obstacles in an endless neon run. How far can you go?", "Space / ↑ / Click jump (hold = higher)", r"""
var cv = $("c"), x = cv.getContext("2d"), WD = 900, HT = 360, GY = 300, p, obs, dist, sp, raf, last, state, gridOff, nextGap;
function restart() {
  cancelAnimationFrame(raf); p = { y: GY - 34, vy: 0, h: 34, w: 34, ground: true, coyote: 0, rot: 0 }; obs = []; dist = 0; sp = 7; gridOff = 0; nextGap = 60; state = "ready";
  Score.set(0); last = performance.now(); raf = requestAnimationFrame(frame);
}
function jump() { if (overlayOpen() || state === "dead") return; if (state === "ready") state = "play"; if (p.ground || p.coyote > 0) { p.vy = -13.2; p.ground = false; p.coyote = 0; } }
function frame(t) {
  raf = requestAnimationFrame(frame); var dt = Math.min(2.5, (t - last) / 16.67); last = t;
  if (state === "play") {
    sp = 7 + Math.min(9, dist / 900); dist += sp * dt; Score.set(Math.floor(dist / 10)); gridOff = (gridOff + sp * dt) % 60;
    var hold = keys[" "] || keys.ArrowUp || keys.w || mouseDown;
    p.vy += (hold && p.vy < 0 ? .55 : 1.05) * dt; p.y += p.vy * dt;
    if (p.y >= GY - p.h) { p.y = GY - p.h; p.vy = 0; if (!p.ground) p.rot = Math.round(p.rot / (Math.PI / 2)) * (Math.PI / 2); p.ground = true; p.coyote = 6; }
    else { p.ground = false; p.coyote -= dt; p.rot += .14 * dt; }
    nextGap -= sp * dt;
    if (nextGap <= 0) {
      var kind = Math.random(), o;
      if (kind < .55) o = { w: ri(22, 40), h: ri(34, 62) }; else if (kind < .8) o = { w: ri(70, 120), h: ri(24, 36) }; else o = { w: 30, h: 30, fly: true };
      o.x = WD + 20; o.y = o.fly ? GY - 34 - 30 - ri(18, 30) : GY - o.h; obs.push(o); nextGap = rand(300, 560) + sp * 12;
    }
    obs.forEach(function (o) { o.x -= sp * dt; }); obs = obs.filter(function (o) { return o.x + o.w > -20; });
    var px = 120, m = 5;
    if (obs.some(function (o) { return px + m < o.x + o.w && px + p.w - m > o.x && p.y + m < o.y + o.h && p.y + p.h - m > o.y; })) {
      state = "dead"; var nb = submit(Score.v); overlay("Wipeout!", Score.v + " m" + (nb && Score.v ? " · new best! 🏆" : ""), "Run again", restart);
    }
  }
  draw(t);
}
function draw(t) {
  x.clearRect(0, 0, WD, HT);
  var sky = x.createLinearGradient(0, 0, 0, GY); sky.addColorStop(0, "rgba(10,10,25,.0)"); sky.addColorStop(1, "rgba(108,140,255,.12)"); x.fillStyle = sky; x.fillRect(0, 0, WD, GY);
  x.strokeStyle = "rgba(108,140,255,.25)"; x.lineWidth = 1;
  for (var i = -1; i < 17; i++) { var gx = i * 60 - gridOff; x.beginPath(); x.moveTo(gx, GY); x.lineTo(WD / 2 + (gx - WD / 2) * 2.4, HT); x.stroke(); }
  for (var j = 0; j < 4; j++) { var gy = GY + Math.pow(j / 4, 1.6) * (HT - GY) + 8; x.beginPath(); x.moveTo(0, gy); x.lineTo(WD, gy); x.stroke(); }
  glow(x, C.a, 16); x.strokeStyle = C.al; x.lineWidth = 3; x.beginPath(); x.moveTo(0, GY); x.lineTo(WD, GY); x.stroke();
  obs.forEach(function (o) { glow(x, "#ff6fae", 16); x.fillStyle = "#ff6fae"; rr(x, o.x, o.y, o.w, o.h, 5); x.fill(); });
  x.save(); x.translate(120 + p.w / 2, p.y + p.h / 2); x.rotate(p.rot); glow(x, C.a, 22); x.fillStyle = C.a; rr(x, -p.w / 2, -p.h / 2, p.w, p.h, 7); x.fill();
  x.shadowBlur = 0; x.fillStyle = "rgba(255,255,255,.85)"; x.fillRect(2, -8, 8, 8); x.restore(); x.shadowBlur = 0;
  if (state === "ready") { x.fillStyle = C.text; x.font = "600 18px Segoe UI"; x.textAlign = "center"; x.fillText("Press Space or click to run · hold to jump higher", WD / 2, 130); }
}
var mouseDown = false;
cv.addEventListener("pointerdown", function () { mouseDown = true; jump(); });
addEventListener("pointerup", function () { mouseDown = false; });
addEventListener("keydown", function (e) { if ((e.key === " " || e.key === "ArrowUp" || e.key === "w") && !e.repeat) jump(); });
restart();
""", body='<canvas id="c" width="900" height="360"></canvas>', score_label="Distance", best_label="Best (m)")

# ------------------------------------------------------------------------------ Tic-tac-toe
game("ttt", "Tic-Tac-Toe", "❌", "Three in a row against the computer. Hard mode never loses.", "Click a square", r"""
var grid = $("grid"), sel = $("diff"), bd, over, LINES = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
function restart() { bd = new Array(9).fill(""); over = false; Score.set("Your turn"); draw(); hideOverlay(); }
function winner(b) { for (var i = 0; i < 8; i++) { var l = LINES[i]; if (b[l[0]] && b[l[0]] === b[l[1]] && b[l[1]] === b[l[2]]) return { p: b[l[0]], l: l }; }
  return b.every(function (v) { return v; }) ? { p: "draw" } : null; }
function mm(b, me) {
  var w = winner(b); if (w) return { s: w.p === "O" ? 10 : w.p === "X" ? -10 : 0 };
  var best = { s: me ? -99 : 99, i: -1 };
  for (var i = 0; i < 9; i++) if (!b[i]) { b[i] = me ? "O" : "X"; var r = mm(b, !me); b[i] = "";
    if (me ? r.s > best.s : r.s < best.s) best = { s: r.s, i: i }; }
  return best;
}
function cpu() {
  var free = bd.map(function (v, i) { return v ? -1 : i; }).filter(function (i) { return i >= 0; }), i;
  var chance = { Easy: .6, Normal: .25, Hard: 0 }[sel.value];
  i = Math.random() < chance ? free[ri(0, free.length - 1)] : mm(bd.slice(), true).i;
  bd[i] = "O"; draw(); end();
}
function end() {
  var w = winner(bd); if (!w) { Score.set("Your turn"); return false; }
  over = true; draw(w.l);
  if (w.p === "X") { addWin(); Score.set("You won"); overlay("You win! 🏆", "Nice one.", "Play again", restart); }
  else if (w.p === "O") { Score.set("CPU won"); setTimeout(function () { overlay("Computer wins", "Try again?", "Play again", restart); }, 500); }
  else { Score.set("Draw"); overlay("Draw", "Nobody wins this time.", "Play again", restart); }
  return true;
}
function draw(line) {
  grid.innerHTML = "";
  bd.forEach(function (v, i) { var d = document.createElement("div"); d.className = "sq" + (v ? " " + v : "") + (line && line.indexOf(i) >= 0 ? " win" : "");
    d.dataset.i = i; d.textContent = v === "X" ? "✕" : v === "O" ? "◯" : ""; grid.appendChild(d); });
}
grid.addEventListener("click", function (e) {
  var t = e.target.closest(".sq"); if (!t || over || overlayOpen()) return; var i = +t.dataset.i; if (bd[i]) return;
  bd[i] = "X"; draw(); if (!end()) { Score.set("Thinking…"); setTimeout(cpu, 280); }
});
sel.addEventListener("change", function () { restart(); sel.blur(); });
restart();
""", body='<div id="grid"></div>', score_label="Status", best_label="Wins",
     extra='<select class="b" id="diff"><option>Easy</option><option selected>Normal</option><option>Hard</option></select>', css="""
#grid { display: grid; grid-template-columns: repeat(3, var(--s)); gap: 12px; --s: min(150px, 24vmin); }
.sq { width: var(--s); height: var(--s); border-radius: 18px; background: var(--card); display: grid; place-items: center; cursor: pointer;
      font-size: calc(var(--s) * .55); font-weight: 300; box-shadow: 0 0 0 1px rgba(255,255,255,.07); transition: background .15s; }
.sq:hover { background: color-mix(in srgb, var(--a) 18%, var(--card)); }
.sq.X { color: var(--a); text-shadow: 0 0 18px var(--a); } .sq.O { color: #ff6fae; text-shadow: 0 0 18px #ff6fae; }
.sq.win { box-shadow: 0 0 0 3px #fff; }
""")


def game_meta():
    return [{"id": g["id"], "name": g["name"], "emoji": g["emoji"], "desc": g["desc"], "best_label": g["best_label"]} for g in GAMES]


def build_game_page(g, colors, qjs=""):
    page = GAME_PAGE.replace("<!--QWEBCHANNEL-->", qjs, 1)
    for k, v in (("__CSS__", g["css"]), ("__BODY__", g["body"]), ("__EXTRA__", g["extra"]), ("__JS__", g["js"])):
        page = page.replace(k, v, 1)
    rep = {"__ID__": g["id"], "__NAME__": html.escape(g["name"]), "__EMOJI__": g["emoji"], "__HELP__": html.escape(g["help"]),
           "__SCORE_LABEL__": html.escape(g["score_label"]), "__BEST_LABEL__": html.escape(g["best_label"]),
           "__LOWER__": "true" if g["lower"] else "false",
           "__ACCENT__": colors.get("accent", "#6c8cff"), "__ACCENT_L__": colors.get("accent_light", "#8fa6ff"),
           "__BG__": colors.get("bg", "#15161b"), "__CARD__": colors.get("card", "#23252c"),
           "__TEXT__": colors.get("text", "#e6e6e6"), "__DIM__": colors.get("dim", "#9a9ca6")}
    for k, v in rep.items():
        page = page.replace(k, v)
    return page


# ============================================================================== building the pages
HUB_PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="nova-page" content="hub"><title>Hub</title>
<style>
:root { --a:#6c8cff; --al:#8fa6ff; --bg:#15161b; --card:#23252c; --field:#2b2d34; --line:#3a3d46; --text:#e6e6e6; --dim:#9a9ca6; }
* { box-sizing: border-box; }
html { background: var(--bg); }
body { margin: 0; color: var(--text); font: 14px/1.45 "Segoe UI", sans-serif;
       background: radial-gradient(1200px 500px at 50% -200px, color-mix(in srgb, var(--a) 18%, transparent), transparent), var(--bg); min-height: 100vh; }
a { color: var(--al); }
.wrap { max-width: 1240px; margin: 0 auto; padding: 22px 28px 90px; }
header.top { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 8px; }
h1 { margin: 0 8px 0 0; font-size: 26px; letter-spacing: .05em; font-weight: 700; }
h1 .ic { filter: drop-shadow(0 0 12px color-mix(in srgb, var(--a) 60%, transparent)); }
nav.tabs { display: flex; gap: 4px; background: var(--card); padding: 4px; border-radius: 12px; border: 1px solid rgba(255,255,255,.06); }
nav.tabs button { background: none; border: none; color: var(--dim); padding: 7px 14px; border-radius: 9px; font: inherit; cursor: pointer; }
nav.tabs button:hover { color: var(--text); }
nav.tabs button.on { background: var(--a); color: #fff; }
nav.tabs .badge { background: #ff4d5e; color: #fff; border-radius: 9px; padding: 0 6px; font-size: 11px; margin-left: 5px; }
.spacer { flex: 1; }
.muted { color: var(--dim); } .small { font-size: 12px; }
.btn { background: var(--field); color: var(--text); border: 1px solid var(--line); border-radius: 9px; padding: 7px 13px;
       font: inherit; cursor: pointer; white-space: nowrap; }
.btn:hover { border-color: var(--a); } .btn:disabled { opacity: .5; cursor: default; }
.btn.primary { background: var(--a); border-color: var(--a); color: #fff; }
.btn.ghost { background: transparent; }
.btn.sm { padding: 4px 9px; font-size: 12px; }
input.field, select.field { background: var(--field); color: var(--text); border: 1px solid var(--line); border-radius: 9px;
       padding: 8px 12px; font: inherit; outline: none; }
input.field:focus, select.field:focus { border-color: var(--a); }
h2 { font-size: 12px; letter-spacing: .16em; text-transform: uppercase; color: var(--dim); margin: 28px 0 12px; font-weight: 600;
     display: flex; align-items: center; gap: 10px; }
h2 .line { flex: 1; height: 1px; background: rgba(255,255,255,.07); }
.grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(var(--min, 260px), 1fr)); }
.card { background: var(--card); border: 1px solid rgba(255,255,255,.06); border-radius: 14px; padding: 14px; position: relative; min-width: 0; }
.click { cursor: pointer; transition: transform .15s, border-color .15s, box-shadow .15s; }
.click:hover { transform: translateY(-2px); border-color: color-mix(in srgb, var(--a) 70%, transparent);
               box-shadow: 0 8px 26px rgba(0,0,0,.3); }
.empty { padding: 34px 20px; text-align: center; color: var(--dim); background: var(--card); border-radius: 14px;
         border: 1px dashed rgba(255,255,255,.12); }
.empty b { color: var(--text); font-size: 16px; display: block; margin-bottom: 6px; }
.row { display: flex; align-items: center; gap: 10px; min-width: 0; }
.wrapflex { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { background: var(--field); border: 1px solid var(--line); color: var(--text); border-radius: 20px; padding: 5px 12px;
        font: inherit; font-size: 13px; cursor: pointer; }
.chip:hover { border-color: var(--a); } .chip.on { background: var(--a); border-color: var(--a); color: #fff; }
.ell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.clamp2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.live { color: #ff5a6a; font-weight: 700; }
.live::before { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #ff5a6a; margin-right: 6px;
                animation: pulse 1.4s infinite; vertical-align: 1px; }
@keyframes pulse { 50% { opacity: .25; } }
.win { color: #4fd18b; font-weight: 600; } .loss { color: #ff6b7a; font-weight: 600; }
.logo { width: 34px; height: 34px; object-fit: contain; flex: none; }
.logo.sm { width: 22px; height: 22px; }
.team-card .name { font-weight: 600; font-size: 15px; }
.team-card .line { margin-top: 8px; display: flex; gap: 8px; align-items: baseline; }
.team-card .line .k { color: var(--dim); font-size: 12px; width: 44px; flex: none; text-transform: uppercase; letter-spacing: .06em; }
.stripe { position: absolute; left: 0; top: 12px; bottom: 12px; width: 3px; border-radius: 3px; }
.game-row { display: grid; grid-template-columns: 1fr auto 1fr; gap: 10px; align-items: center; padding: 9px 12px; border-radius: 10px; }
.game-row:hover { background: rgba(255,255,255,.04); }
.game-row .side { display: flex; align-items: center; gap: 8px; min-width: 0; }
.game-row .side.r { justify-content: flex-end; text-align: right; }
.game-row .mid { text-align: center; min-width: 120px; }
.game-row .score { font-size: 17px; font-weight: 700; letter-spacing: .03em; }
.mine { outline: 1px solid color-mix(in srgb, var(--a) 55%, transparent); }
.item { display: flex; gap: 14px; padding: 12px; }
.item .thumb { width: 150px; height: 84px; border-radius: 9px; object-fit: cover; flex: none; background: rgba(255,255,255,.05); }
.item .meta { color: var(--dim); font-size: 12px; margin-bottom: 3px; }
.item .t { font-weight: 600; font-size: 15px; margin-bottom: 4px; }
.item .s { color: #c8cad3; font-size: 13px; }
.kind { font-size: 11px; padding: 1px 7px; border-radius: 6px; background: rgba(255,255,255,.07); color: var(--dim); }
.switch { position: relative; width: 38px; height: 21px; flex: none; cursor: pointer; display: inline-block; }
.switch input { opacity: 0; width: 0; height: 0; position: absolute; }
.switch span { position: absolute; inset: 0; background: var(--line); border-radius: 21px; transition: .2s; }
.switch span::after { content: ""; position: absolute; width: 15px; height: 15px; left: 3px; top: 3px; background: #fff; border-radius: 50%; transition: .2s; }
.switch input:checked + span { background: var(--a); }
.switch input:checked + span::after { transform: translateX(17px); }
.follow-row { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,.05); }
.follow-row:last-child { border-bottom: none; }
.follow-row .ic { width: 30px; height: 30px; display: grid; place-items: center; font-size: 18px; flex: none; }
.lbl { font-size: 11px; color: var(--dim); display: flex; align-items: center; gap: 6px; }
.err { color: #ffb36b; font-size: 12px; }
.team-tile { display: flex; align-items: center; gap: 10px; padding: 10px 12px; }
.team-tile.on { border-color: var(--a); background: color-mix(in srgb, var(--a) 14%, var(--card)); }
.team-tile .check { margin-left: auto; color: var(--a); font-weight: 700; }
.toast { position: fixed; left: 50%; bottom: 26px; transform: translateX(-50%); background: var(--card); border: 1px solid var(--a);
         padding: 10px 18px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,.4); z-index: 50; transition: opacity .3s; }
.modal-bg { position: fixed; inset: 0; background: rgba(0,0,0,.55); z-index: 40; display: grid; place-items: center; padding: 30px; }
.modal { width: min(720px, 100%); max-height: 86vh; display: flex; flex-direction: column; background: var(--bg); border: 1px solid var(--line);
         border-radius: 16px; overflow: hidden; }
.modal header { padding: 16px 18px; border-bottom: 1px solid var(--line); }
.modal .body { overflow: auto; padding: 8px 18px; flex: 1; }
.modal footer { padding: 12px 18px; border-top: 1px solid var(--line); display: flex; gap: 8px; justify-content: flex-end; }
.check-row { display: flex; align-items: center; gap: 12px; padding: 8px 4px; border-bottom: 1px solid rgba(255,255,255,.05); }
.check-row img { width: 92px; height: 34px; object-fit: cover; border-radius: 5px; background: rgba(255,255,255,.05); }
.game-card { padding: 0; overflow: hidden; display: flex; flex-direction: column; }
.game-card .img { height: 128px; background: linear-gradient(135deg, color-mix(in srgb, var(--a) 40%, #000), #111);
                  display: grid; place-items: center; font-size: 46px; position: relative; overflow: hidden; }
.game-card .img img { width: 100%; height: 100%; object-fit: cover; position: absolute; inset: 0; }
.game-card .body { padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 6px; flex: 1; }
.game-card .name { font-weight: 700; font-size: 15px; }
.game-card .actions { display: flex; gap: 6px; align-items: center; margin-top: auto; padding-top: 6px; flex-wrap: wrap; }
.src { position: absolute; top: 8px; left: 8px; font-size: 11px; background: rgba(0,0,0,.65); padding: 2px 8px; border-radius: 6px; z-index: 1; }
.play-card { text-align: center; padding: 22px 14px 16px; }
.play-card .big { font-size: 46px; line-height: 1; margin-bottom: 10px; filter: drop-shadow(0 6px 14px rgba(0,0,0,.4)); }
.play-card .name { font-weight: 700; font-size: 16px; }
.play-card .desc { color: var(--dim); font-size: 12.5px; margin: 6px 0 10px; min-height: 36px; }
.play-card .best { font-size: 12px; color: var(--al); }
.search-results { position: absolute; top: 44px; left: 0; right: 0; z-index: 20; background: var(--bg); border: 1px solid var(--line);
                  border-radius: 12px; box-shadow: 0 14px 40px rgba(0,0,0,.5); max-height: 420px; overflow: auto; }
.search-results .res { display: flex; align-items: center; gap: 10px; padding: 8px 12px; }
.search-results .res:hover { background: rgba(255,255,255,.05); }
.search-results img { width: 92px; height: 34px; object-fit: cover; border-radius: 5px; }
.free-card .img { height: 150px; }
.pill { font-size: 11px; padding: 2px 8px; border-radius: 6px; font-weight: 600; }
.pill.now { background: #2fd38a; color: #04140c; } .pill.soon { background: var(--line); color: var(--text); }
.spin { display: inline-block; animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }
.notice { background: color-mix(in srgb, var(--a) 12%, var(--card)); border: 1px solid color-mix(in srgb, var(--a) 40%, transparent);
          border-radius: 12px; padding: 12px 14px; }
.anime-card { display: flex; gap: 14px; }
.anime-card .cover { width: 92px; height: 130px; border-radius: 10px; object-fit: cover; flex: none; background: rgba(255,255,255,.05); }
.anime-card .info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.anime-card .name { font-weight: 700; font-size: 15px; }
.anime-card .actions { display: flex; gap: 6px; align-items: center; margin-top: auto; flex-wrap: wrap; }
.prog { display: flex; align-items: center; gap: 6px; font-size: 13px; flex-wrap: wrap; }
.prog span { white-space: nowrap; }
.prog b { font-size: 15px; }
.pill.new { background: #ff4d5e; color: #fff; }
.price { font-size: 22px; font-weight: 800; letter-spacing: .01em; }
.strike { text-decoration: line-through; color: var(--dim); font-size: 12px; }
.pill.off { background: #2fd38a; color: #04140c; }
input.field.sm { padding: 4px 8px; width: 86px; font-size: 13px; }
.deal-card .img { height: 96px; }
.level-card { display: flex; align-items: center; gap: 22px; flex-wrap: wrap; padding: 20px 22px;
              background: linear-gradient(135deg, color-mix(in srgb, var(--a) 26%, var(--card)), var(--card)); }
.level-ring { width: 96px; height: 96px; border-radius: 50%; display: grid; place-items: center; flex: none;
              background: conic-gradient(var(--a) calc(var(--p) * 1%), rgba(255,255,255,.08) 0); }
.level-ring div { width: 78px; height: 78px; border-radius: 50%; background: var(--card); display: grid; place-items: center; text-align: center; }
.level-ring b { font-size: 30px; line-height: 1; display: block; } .level-ring span { font-size: 10px; color: var(--dim); letter-spacing: .14em; }
.xpbar { height: 10px; border-radius: 10px; background: rgba(255,255,255,.08); overflow: hidden; margin: 8px 0 6px; }
.xpbar div { height: 100%; background: linear-gradient(90deg, var(--a), var(--al)); border-radius: 10px; }
.stat-chip { background: var(--field); border-radius: 10px; padding: 8px 12px; font-size: 12px; color: var(--dim); }
.stat-chip b { display: block; color: var(--text); font-size: 18px; }
.badge-card { text-align: center; padding: 16px 10px; }
.badge-card .e { font-size: 34px; line-height: 1; margin-bottom: 8px; }
.badge-card.locked .e { filter: grayscale(1); opacity: .3; }
.badge-card.locked .n { color: var(--dim); }
.badge-card .n { font-weight: 700; font-size: 13px; } .badge-card .d { font-size: 11.5px; color: var(--dim); margin-top: 3px; }
.badge-card.got { border-color: color-mix(in srgb, var(--a) 60%, transparent); box-shadow: 0 0 18px color-mix(in srgb, var(--a) 22%, transparent); }
.reward { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,.05); }
.reward:last-child { border-bottom: none; }
.reward .lv { width: 52px; font-size: 11px; color: var(--dim); text-transform: uppercase; letter-spacing: .08em; }
@media (max-width: 700px) { .item .thumb { width: 96px; height: 64px; } .wrap { padding: 16px; } }
</style></head>
<body><div class="wrap" id="app"><div class="empty"><b>Loading…</b></div></div>
<!--QWEBCHANNEL-->
<script>window.HUB = /*HUB_CONFIG*/{};</script>
<script>
(function () {
"use strict";
var H = window.HUB || {}, C = H.colors || {};
var root = document.documentElement.style;
[["--a", C.accent], ["--al", C.accent_light], ["--bg", C.bg], ["--card", C.card], ["--field", C.field], ["--line", C.line],
 ["--text", C.text], ["--dim", C.dim]].forEach(function (p) { if (p[1]) root.setProperty(p[0], p[1]); });
var KIND = H.kind === "games" ? "games" : "follow";
document.title = KIND === "games" ? "🎮 Games" : "📣 Following";
var app = document.getElementById("app");
var nova = null, pending = {}, seq = 0, S = null;
var tab = (function () { try { return sessionStorage.getItem("hub-tab-" + KIND); } catch (e) { return null; } })() ||
          (KIND === "games" ? "play" : "today");
var ui = { league: null, teams: {}, teamQuery: "", feedFilter: "all", gameFilter: "", addMsg: "", searchQ: "", results: null,
           searching: false, modal: null, aQ: "", aResults: null, aSearching: false, dQ: "", dResults: null, dSearching: false };
var TAB_IDS = KIND === "games" ? ["play", "mine", "updates", "free", "deals", "profile"] : ["today", "feed", "anime", "manage"];
function hashTab() { var h = (location.hash || "").replace("#", ""); return TAB_IDS.indexOf(h) >= 0 ? h : null; }
if (hashTab()) tab = hashTab();
addEventListener("hashchange", function () { var h = hashTab(); if (h) setTab(h); });

/* ---------------- helpers ---------------- */
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
  return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
function img(u) { u = String(u || ""); return /^https?:\/\//i.test(u) ? esc(u) : ""; }
function ago(t) {
  if (!t) return ""; var s = Math.max(0, (Date.now() / 1000) - t);
  if (s < 60) return "just now"; if (s < 3600) return Math.floor(s / 60) + "m ago"; if (s < 86400) return Math.floor(s / 3600) + "h ago";
  if (s < 172800) return "yesterday"; if (s < 7 * 86400) return Math.floor(s / 86400) + "d ago";
  return new Date(t * 1000).toLocaleDateString([], { month: "short", day: "numeric" });
}
function when(t) {
  if (!t) return ""; var d = new Date(t * 1000), n = new Date(), tm = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  var day = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - new Date(n.getFullYear(), n.getMonth(), n.getDate())) / 86400000);
  if (day === 0) return "Today " + tm; if (day === 1) return "Tomorrow " + tm; if (day === -1) return "Yesterday " + tm;
  return d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }) + " · " + tm;
}
function shortDate(t) { return t ? new Date(t * 1000).toLocaleDateString([], { month: "short", day: "numeric" }) : ""; }
function toast(msg) {
  var t = document.createElement("div"); t.className = "toast"; t.textContent = msg; document.body.appendChild(t);
  setTimeout(function () { t.style.opacity = "0"; }, 2600); setTimeout(function () { t.remove(); }, 3000);
}
function api(method, args) {
  return new Promise(function (res, rej) {
    if (!nova) { rej("not connected"); return; }
    var id = String(++seq); pending[id] = { res: res, rej: rej };
    nova.call(id, method, JSON.stringify(args || {}));
  });
}
function openUrl(u) { if (/^https?:\/\//i.test(u || "")) api("open", { url: u }); }
function setTab(t) { tab = t; try { sessionStorage.setItem("hub-tab-" + KIND, t); } catch (e) {} render(); window.scrollTo(0, 0); }
function follows(kind) { return (S.follows || []).filter(function (f) { return !kind || f.kind === kind; }); }
function isOn(x) { return x && x.on !== false; }
function sw(id, field, val, title) {
  return '<label class="switch" title="' + esc(title) + '"><input type="checkbox" data-act="toggle" data-id="' + esc(id) +
         '" data-field="' + field + '"' + (val !== false ? " checked" : "") + '><span></span></label>';
}
function leagueOf(key) { var l = (H.leagues || []).filter(function (x) { return x.key === key; })[0]; return l || { name: key, emoji: "🏟" }; }

/* ---------------- shared header ---------------- */
function header(tabs) {
  var st = S.state || {}, upd = st.updated ? "Updated " + ago(st.updated) : "Not updated yet";
  var h = '<header class="top"><h1>' + (KIND === "games" ? '<span class="ic">🎮</span> Games' : '<span class="ic">📣</span> Following') +
          '</h1><nav class="tabs">';
  tabs.forEach(function (t) { h += '<button data-act="tab" data-tab="' + t[0] + '" class="' + (tab === t[0] ? "on" : "") + '">' + t[1] +
                              (t[2] ? '<span class="badge">' + t[2] + "</span>" : "") + "</button>"; });
  h += '</nav><div class="spacer"></div><span class="muted small">' + esc(upd) + '</span>' +
       '<button class="btn sm" data-act="refresh" title="Check for updates now">' + (S.busy ? '<span class="spin">⟳</span>' : "⟳") +
       " Refresh</button></header>";
  return h;
}
function disabledPage(what, key) {
  return '<div class="empty" style="margin-top:40px"><b>' + what + ' is turned off</b>You can turn it back on any time.<br><br>' +
         '<button class="btn primary" data-act="enable" data-key="' + key + '">Turn it on</button></div>';
}

/* ================================================================ FOLLOWING ================================================ */
function vsLine(g, tid) {
  var us = g.home.id === tid ? g.home : g.away, them = g.home.id === tid ? g.away : g.home, at = us === g.home ? "vs" : "@";
  return { us: us, them: them, at: at };
}
function teamStatus(g, tid, label) {
  if (!g) return "";
  if (g.type !== "game") return '<div class="line"><span class="k">' + label + '</span><span class="ell">' + esc(g.short || g.name) + " · " + esc(g.detail) + "</span></div>";
  var v = vsLine(g, tid), txt;
  if (g.state === "in") txt = '<span class="live">LIVE</span> ' + esc(v.us.abbr) + " " + esc(v.us.score) + " – " + esc(v.them.score) + " " +
                              esc(v.them.abbr) + ' <span class="muted">· ' + esc(g.detail) + "</span>";
  else if (g.state === "post") {
    var w = v.us.winner ? '<span class="win">W</span>' : (v.them.winner ? '<span class="loss">L</span>' : "<span>T</span>");
    txt = w + " " + esc(v.us.score) + "–" + esc(v.them.score) + " " + v.at + " " + esc(v.them.abbr) + ' <span class="muted">· ' + esc(shortDate(g.time)) + "</span>";
  } else txt = esc(when(g.time)) + ' <span class="muted">· ' + v.at + " " + esc(v.them.short || v.them.abbr) + "</span>";
  return '<div class="line"><span class="k">' + label + '</span><span class="ell">' + txt + "</span></div>";
}
function gameRow(g) {
  if (g.type !== "game") {
    return '<div class="game-row click" data-act="open" data-url="' + esc(g.link) + '"><div class="side"><b class="ell">' + esc(g.name) +
           '</b></div><div class="mid muted small">' + (g.state === "in" ? '<span class="live">LIVE</span> ' : "") + esc(g.detail) +
           '</div><div class="side r muted small">' + esc(when(g.time)) + "</div></div>";
  }
  var mid = g.state === "pre" ? '<div class="muted">' + esc(when(g.time)) + "</div>" :
    '<div class="score">' + esc(g.away.score) + " – " + esc(g.home.score) + '</div><div class="small ' + (g.state === "in" ? "live" : "muted") + '">' + esc(g.detail) + "</div>";
  return '<div class="game-row click' + (g.mine ? " mine" : "") + '" data-act="open" data-url="' + esc(g.link) + '">' +
    '<div class="side"><img class="logo sm" src="' + img(g.away.logo) + '" onerror="this.style.visibility=\'hidden\'"><span class="ell' +
    (g.away.winner ? " win" : "") + '">' + esc(g.away.short || g.away.name) + "</span></div>" +
    '<div class="mid">' + mid + "</div>" +
    '<div class="side r"><span class="ell' + (g.home.winner ? " win" : "") + '">' + esc(g.home.short || g.home.name) +
    '</span><img class="logo sm" src="' + img(g.home.logo) + '" onerror="this.style.visibility=\'hidden\'"></div></div>';
}
function renderToday() {
  var teams = follows("team").filter(isOn), leagues = follows("league").filter(isOn), st = S.state || {}, h = "";
  if (!teams.length && !leagues.length) {
    return '<div class="empty" style="margin-top:30px"><b>Nothing followed yet</b>Pick your teams and leagues and their scores show up here.<br><br>' +
           '<button class="btn primary" data-act="tab" data-tab="manage">＋ Follow teams</button></div>';
  }
  if (teams.length) {
    h += '<h2>Your teams<span class="line"></span></h2><div class="grid" style="--min:290px">';
    teams.forEach(function (f) {
      var info = (st.teams || {})[f.id] || {}, today = info.today, tid = f.team_id;
      var link = (today && today.link) || (info.next && info.next.link) || (info.last && info.last.link) || "";
      h += '<div class="card team-card click" data-act="open" data-url="' + esc(link) + '">' +
           (f.color ? '<div class="stripe" style="background:#' + esc(f.color) + '"></div>' : "") +
           '<div class="row"><img class="logo" src="' + img(f.logo) + '" onerror="this.style.visibility=\'hidden\'"><div style="min-width:0">' +
           '<div class="name ell">' + esc(f.name) + '</div><div class="muted small ell">' + esc(leagueOf(f.league).name) +
           (info.record ? " · " + esc(info.record) : "") + (info.standing ? " · " + esc(info.standing) : "") + "</div></div></div>";
      if (today) h += teamStatus(today, tid, today.state === "pre" ? "Today" : (today.state === "in" ? "Now" : "Final"));
      if (info.next && (!today || info.next.id !== today.id)) h += teamStatus(info.next, tid, "Next");
      if (info.last && (!today || info.last.id !== today.id)) h += teamStatus(info.last, tid, "Last");
      if (!today && !info.next && !info.last) h += '<div class="line muted small">' + ((st.errors || {})[f.id] ? "Couldn't load right now." : "Loading…") + "</div>";
      h += "</div>";
    });
    h += "</div>";
  }
  var today = (st.today || []), byLeague = {};
  today.forEach(function (g) { (byLeague[g.league] = byLeague[g.league] || []).push(g); });
  var shown = Object.keys(byLeague);
  if (shown.length) {
    shown.forEach(function (lg) {
      var L = leagueOf(lg);
      h += "<h2>" + esc(L.emoji + " " + L.name) + ' scoreboard<span class="line"></span></h2><div class="card" style="padding:6px">';
      byLeague[lg].forEach(function (g) { h += gameRow(g); });
      h += "</div>";
    });
  } else if (leagues.length || teams.length) {
    h += '<h2>Scoreboard<span class="line"></span></h2><div class="empty">No games today for what you follow.</div>';
  }
  return h;
}
function renderFeed() {
  var on = {}, kinds = {}; follows().forEach(function (f) { if (isOn(f)) on[f.id] = f; });
  var items = ((S.state || {}).feed || []).filter(function (i) { return on[i.source_id]; });
  items.forEach(function (i) { kinds[i.kind] = (kinds[i.kind] || 0) + 1; });
  var labels = [["all", "All"], ["sports", "🏟 Sports news"], ["youtube", "▶️ Videos"], ["reddit", "👽 Reddit"], ["rss", "📰 Sites"], ["topic", "🔎 Topics"]];
  var h = '<div class="wrapflex" style="margin:18px 0 6px">';
  labels.forEach(function (l) { if (l[0] === "all" || kinds[l[0]]) h += '<button class="chip' + (ui.feedFilter === l[0] ? " on" : "") +
    '" data-act="feedfilter" data-k="' + l[0] + '">' + l[1] + (l[0] !== "all" ? ' <span class="muted">' + kinds[l[0]] + "</span>" : "") + "</button>"; });
  h += "</div>";
  var shown = items.filter(function (i) { return ui.feedFilter === "all" || i.kind === ui.feedFilter; }).slice(0, 200);
  if (!follows().length) return h + '<div class="empty"><b>Your feed is empty</b>Follow teams, leagues, YouTube channels, subreddits, sites or any topic.<br><br>' +
                         '<button class="btn primary" data-act="tab" data-tab="manage">＋ Follow something</button></div>';
  if (!shown.length) return h + '<div class="empty">' + (S.busy ? "Loading your feed…" : "Nothing new here yet.") + "</div>";
  var lastOpen = (S.last_open || {}).follow || 0;
  h += '<div style="display:flex;flex-direction:column;gap:10px">';
  shown.forEach(function (i) {
    var src = on[i.source_id] || {}, icon = i.kind === "sports" ? "📰" : ({ youtube: "▶️", reddit: "👽", rss: "📰", topic: "🔎" }[i.kind] || "📣");
    h += '<div class="card item click" data-act="open" data-url="' + esc(i.url) + '">' +
         (i.image ? '<img class="thumb" loading="lazy" src="' + img(i.image) + '" onerror="this.remove()">' : "") +
         '<div style="min-width:0;flex:1"><div class="meta">' + icon + " " + esc(i.source || src.name) + " · " + esc(ago(i.time)) +
         (i.time > lastOpen ? ' · <span style="color:var(--al)">new</span>' : "") + "</div>" +
         '<div class="t clamp2">' + esc(i.title) + "</div>" + (i.summary ? '<div class="s clamp2">' + esc(i.summary) + "</div>" : "") + "</div></div>";
  });
  return h + "</div>";
}
function renderManage() {
  var h = '<h2>Sports<span class="line"></span></h2><div class="wrapflex">';
  (H.leagues || []).forEach(function (l) {
    var followed = follows().some(function (f) { return f.league === l.key; });
    h += '<button class="chip' + (ui.league === l.key ? " on" : "") + '" data-act="league" data-k="' + l.key + '">' + esc(l.emoji + " " + l.name) +
         (followed ? " •" : "") + "</button>";
  });
  h += "</div>";
  if (ui.league) {
    var L = leagueOf(ui.league), lf = follows("league").filter(function (f) { return f.league === ui.league; })[0];
    h += '<div class="card" style="margin-top:14px"><div class="row" style="flex-wrap:wrap"><b style="font-size:16px">' + esc(L.emoji + " " + L.name) + "</b>" +
         '<span class="muted small">' + (L.teams ? "Pick teams for scores, schedules & news. Follow the league for all its news and scores." :
         "Follow to get its events, results and news.") + '</span><div class="spacer"></div>' +
         '<button class="btn' + (lf ? "" : " primary") + '" data-act="followleague" data-k="' + L.key + '">' + (lf ? "✓ Following league" : "＋ Follow league") + "</button></div>";
    if (L.teams) {
      var list = ui.teams[ui.league];
      h += '<input class="field" id="teamq" style="width:100%;margin:12px 0" placeholder="Search teams…" data-input="teamq" value="' + esc(ui.teamQuery) + '">';
      if (!list) h += '<div class="muted">Loading teams…</div>';
      else if (list.error) h += '<div class="err">Couldn\'t load teams: ' + esc(list.error) + "</div>";
      else {
        var q = ui.teamQuery.toLowerCase().trim(), mine = {};
        follows("team").forEach(function (f) { mine[f.id] = 1; });
        h += '<div class="grid" style="--min:220px;max-height:420px;overflow:auto;padding:2px">';
        list.filter(function (t) { return !q || (t.name + " " + t.abbr).toLowerCase().indexOf(q) >= 0; }).slice(0, 400).forEach(function (t) {
          var on = mine["team:" + ui.league + ":" + t.id];
          h += '<div class="card team-tile click' + (on ? " on" : "") + '" data-act="team" data-tid="' + esc(t.id) + '">' +
               '<img class="logo sm" loading="lazy" src="' + img(t.logo) + '" onerror="this.style.visibility=\'hidden\'"><span class="ell">' + esc(t.name) +
               '</span><span class="check">' + (on ? "✓" : "＋") + "</span></div>";
        });
        h += "</div>";
      }
    }
    h += "</div>";
  }
  h += '<h2>Channels, subreddits, sites & topics<span class="line"></span></h2><div class="card">' +
       '<div class="row"><input class="field" style="flex:1" id="addsrc" placeholder="Paste a YouTube channel, r/subreddit, a website, or type any topic (a player, a game, a show…)">' +
       '<button class="btn primary" data-act="addsrc">＋ Follow</button></div>' +
       (ui.addMsg ? '<div class="small" style="margin-top:8px">' + esc(ui.addMsg) + "</div>" : "") +
       '<div class="muted small" style="margin:12px 0 6px">Quick picks</div><div class="wrapflex">';
  (H.suggestions || []).forEach(function (s) { h += '<button class="chip" data-act="quick" data-text="' + esc(s) + '">' + esc(s) + "</button>"; });
  h += "</div></div>";
  var all = follows(), errs = (S.state || {}).errors || {};
  h += "<h2>Everything you follow (" + all.length + ')<span class="line"></span></h2>';
  if (!all.length) h += '<div class="empty">Nothing yet. It\'s all your choice: pick teams, leagues, channels or topics above.</div>';
  else {
    h += '<div class="card" style="padding:4px 0">';
    all.forEach(function (f) {
      var icon = f.kind === "team" && f.logo ? '<img class="logo sm" src="' + img(f.logo) + '" onerror="this.replaceWith(\'🏟\')">' :
                 esc(f.kind === "league" ? leagueOf(f.league).emoji : ({ youtube: "▶️", reddit: "👽", rss: "📰", topic: "🔎", anime: "📺" }[f.kind] || "📣"));
      var kindName = { team: "Team · " + leagueOf(f.league).name, league: "League", youtube: "YouTube channel", reddit: "Subreddit", rss: "Website", topic: "News topic", anime: "Anime" }[f.kind] || f.kind;
      h += '<div class="follow-row"><div class="ic">' + icon + '</div><div style="flex:1;min-width:0"><div class="ell"><b>' + esc(f.name) + "</b></div>" +
           '<div class="muted small">' + esc(kindName) + (errs[f.id] ? ' · <span class="err">⚠ ' + esc(errs[f.id]) + "</span>" : "") + "</div></div>" +
           '<span class="lbl">Show ' + sw(f.id, "on", f.on, "Show in Today & Feed") + '</span><span class="lbl">🔔 ' + sw(f.id, "notify", f.notify, "Alerts") +
           '</span><button class="btn sm ghost" data-act="unfollow" data-id="' + esc(f.id) + '" title="Unfollow">✕</button></div>';
    });
    h += "</div>";
  }
  h += '<h2>On your start page<span class="line"></span></h2><div class="card"><div class="row" style="flex-wrap:wrap;gap:18px">' +
       widgetPicker("scores", "My teams widget") + widgetPicker("followfeed", "Following feed widget") + "</div></div>";
  return h;
}
function widgetPicker(w, label) {
  var cur = (S.widgets || {})[w] || "Hidden";
  var h = '<label class="row">' + esc(label) + ' <select class="field" data-input="widget" data-w="' + w + '">';
  ["Hidden", "Left", "Center", "Right"].forEach(function (p) { h += "<option" + (p === cur ? " selected" : "") + ">" + p + "</option>"; });
  return h + "</select></label>";
}
/* ---------------- anime ---------------- */
function countdown(t) {
  var s = t - Date.now() / 1000; if (s <= 0) return "any minute now";
  var d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
  return "in " + (d ? d + "d " + h + "h" : h ? h + "h " + m + "m" : Math.max(1, m) + "m");
}
function animeInfo(f) { return ((S.state || {}).anime || {})[f.id] || {}; }
function watchUrl(info, ep) {
  var u = (info.cr_eps || {})[String(ep)]; if (u) return u; if (info.cr) return info.cr;
  return "https://www.crunchyroll.com/search?q=" + encodeURIComponent(info.romaji || info.title || "");
}
function animeNew(f) { var i = animeInfo(f); return Math.max(0, (i.aired || 0) - (f.progress || 0)); }
var ANIME_STATUS = { RELEASING: "Airing", FINISHED: "Finished", NOT_YET_RELEASED: "Not out yet", HIATUS: "On break", CANCELLED: "Cancelled" };
function renderAnime() {
  var h = '<div class="row" style="margin:18px 0 0"><div style="position:relative;flex:1;min-width:260px">' +
          '<input class="field" style="width:100%" id="asearch" placeholder="Track an anime… (search by name, e.g. Frieren, One Piece, Solo Leveling)" value="' + esc(ui.aQ) + '" data-input="asearch">';
  if (ui.aResults) {
    h += '<div class="search-results">';
    if (ui.aSearching) h += '<div class="res muted">Searching…</div>';
    if (!ui.aSearching && !ui.aResults.length) h += '<div class="res muted">No shows found.</div>';
    ui.aResults.forEach(function (r, i) {
      var have = follows("anime").some(function (f) { return f.anilist_id === r.anilist_id; });
      h += '<div class="res"><img src="' + img(r.image) + '" style="width:40px;height:56px" onerror="this.style.visibility=\'hidden\'"><div style="flex:1;min-width:0"><div class="ell"><b>' + esc(r.title) +
           '</b></div><div class="muted small ell">' + esc([r.format, r.year, ANIME_STATUS[r.status] || "", r.total ? r.total + " eps" : ""].filter(Boolean).join(" · ")) + "</div></div>" +
           (have ? '<span class="muted small">Tracking ✓</span>' : '<button class="btn sm" data-act="trackanime" data-i="' + i + '" data-from="start">＋ From Ep 1</button>' +
           (r.aired ? '<button class="btn sm primary" data-act="trackanime" data-i="' + i + '" data-from="caught">＋ I\'m caught up</button>' : "")) + "</div>";
    });
    h += "</div>";
  }
  h += "</div></div>";
  var shows = follows("anime");
  if (!shows.length) return h + '<div class="empty" style="margin-top:20px"><b>No anime tracked yet</b>Search above to track a show. You\'ll get an alert when each new episode comes out, ' +
                         "a countdown to the next one, and a button that jumps to your next episode on Crunchyroll.</div>";
  shows = shows.slice().sort(function (a, b) {
    var na = animeNew(a), nb = animeNew(b); if (!!na !== !!nb) return nb - na;
    return (animeInfo(a).next_at || 9e12) - (animeInfo(b).next_at || 9e12);
  });
  h += '<h2>Your shows (' + shows.length + ')<span class="line"></span></h2><div class="grid" style="--min:340px">';
  shows.forEach(function (f) {
    var i = animeInfo(f), p = f.progress || 0, aired = i.aired, nw = animeNew(f), lines = "";
    if (nw > 0) lines += '<div class="row small"><span class="pill new">NEW</span><span>Episode ' + (p + 1) + " is out" + (nw > 1 ? " · " + nw + " to watch" : "") + "</span></div>";
    if (i.next_ep && i.next_at) lines += '<div class="small"><span class="muted">Next:</span> Ep ' + i.next_ep + " · " + esc(when(i.next_at)) + ' · <b>' + esc(countdown(i.next_at)) + "</b></div>";
    else if (i.status) lines += '<div class="small muted">' + esc(ANIME_STATUS[i.status] || i.status) + (i.total ? " · " + i.total + " episodes" : "") + "</div>";
    else lines += '<div class="small muted">' + ((S.state.errors || {}).anime ? "Couldn't load right now." : "Loading…") + "</div>";
    var cr = nw > 0 ? '<button class="btn sm primary" data-act="open" data-url="' + esc(watchUrl(i, p + 1)) + '">▶ Watch Ep ' + (p + 1) + "</button>"
                    : '<button class="btn sm" data-act="open" data-url="' + esc(watchUrl(i, p + 1)) + '">🍥 Crunchyroll</button>';
    h += '<div class="card anime-card"' + (isOn(f) ? "" : ' style="opacity:.55"') + '><img class="cover" src="' + img(f.image || i.image) + '" onerror="this.style.visibility=\'hidden\'">' +
         '<div class="info"><div class="name clamp2">' + esc(f.name) + '</div><div class="muted small">' + esc([i.format, ANIME_STATUS[i.status] || ""].filter(Boolean).join(" · ")) + "</div>" + lines +
         '<div class="prog">Watched <b>' + p + "</b>" + (typeof aired === "number" ? '<span class="muted">/ ' + aired + (i.total && i.total !== aired ? " (" + i.total + ")" : "") + "</span>" : "") +
         '<button class="btn sm" data-act="aprog" data-id="' + esc(f.id) + '" data-v="' + (p - 1) + '" title="One less">−</button>' +
         '<button class="btn sm" data-act="aprog" data-id="' + esc(f.id) + '" data-v="' + (p + 1) + '" title="Watched one more">＋</button>' +
         (nw > 0 ? '<button class="btn sm ghost" data-act="aprog" data-id="' + esc(f.id) + '" data-v="' + aired + '" title="Mark everything out so far as watched">✓ Caught up</button>' : "") + "</div>" +
         '<div class="actions">' + cr + '<button class="btn sm ghost" data-act="open" data-url="' + esc(f.url || i.url) + '">AniList</button><div class="spacer"></div>' +
         '<button class="btn sm ghost" data-act="unfollow" data-id="' + esc(f.id) + '" title="Stop tracking">✕</button></div>' +
         '<div class="row" style="gap:16px"><span class="lbl">Show ' + sw(f.id, "on", f.on, "Show it") + '</span><span class="lbl">🔔 New episodes ' + sw(f.id, "notify", f.notify, "Alert when a new episode is out") + "</span></div>" +
         "</div></div>";
  });
  h += "</div>";
  h += '<p class="muted small" style="margin-top:12px">Episode times and links come from AniList. If a show has no Crunchyroll episode link, ▶ opens the show (or a Crunchyroll search) instead.</p>';
  h += '<h2>On your start page<span class="line"></span></h2><div class="card"><div class="row">' + widgetPicker("anime", "Next episodes widget") + "</div></div>";
  return h;
}
function renderFollow() {
  if (!S.enabled.follow) return disabledPage("📣 Following", "hub_follow");
  var unread = 0, lo = (S.last_open || {}).follow || 0, on = {}, newEps = 0;
  follows().forEach(function (f) { if (isOn(f)) on[f.id] = 1; });
  ((S.state || {}).feed || []).forEach(function (i) { if (on[i.source_id] && i.time > lo && i.kind !== "anime") unread++; });
  follows("anime").forEach(function (f) { if (isOn(f) && animeNew(f) > 0) newEps++; });
  return header([["today", "Today"], ["feed", "Feed", unread ? Math.min(unread, 99) : 0], ["anime", "📺 Anime", newEps], ["manage", "＋ Follow"]]) +
         (tab === "feed" ? renderFeed() : tab === "manage" ? renderManage() : tab === "anime" ? renderAnime() : renderToday());
}

/* ================================================================ GAMES ===================================================== */
function bestOf(g) {
  try { var v = localStorage.getItem("nova-game-" + g.id + "-best"); return v == null ? "" : v; } catch (e) { return ""; }
}
function renderPlay() {
  var h = '<h2>Play now · free, nothing to download<span class="line"></span></h2><div class="grid" style="--min:200px">';
  (H.games || []).forEach(function (g) {
    var b = bestOf(g);
    h += '<div class="card play-card click" data-act="play" data-id="' + esc(g.id) + '"><div class="big">' + esc(g.emoji) + '</div><div class="name">' +
         esc(g.name) + '</div><div class="desc">' + esc(g.desc) + '</div><div class="best">' + (b !== "" ? esc(g.best_label || "Best") + ": " + esc(b) : "&nbsp;") + "</div></div>";
  });
  h += "</div>";
  if (S.web_on) {
    h += '<h2>More free games on the web<span class="line"></span></h2><div class="grid" style="--min:230px">';
    (H.sites || []).forEach(function (s) {
      h += '<div class="card click row" data-act="open" data-url="' + esc(s.url) + '"><div style="font-size:28px">' + esc(s.emoji) + '</div><div style="min-width:0">' +
           "<b>" + esc(s.name) + '</b><div class="muted small clamp2">' + esc(s.desc) + "</div></div></div>";
    });
    h += "</div>";
  }
  return h;
}
function latestFor(gid) {
  var n = ((S.state || {}).game_news || []).filter(function (i) { return i.game_id === gid; });
  return n[0];
}
function gameImg(g) {
  var alt = g.appid ? "https://cdn.akamai.steamstatic.com/steam/apps/" + g.appid + "/header.jpg" : "";
  return g.image ? '<img src="' + img(g.image) + '" data-alt="' + esc(alt) + '" onerror="if(this.dataset.alt){this.src=this.dataset.alt;this.dataset.alt=\'\'}else{this.remove()}">' : "";
}
function renderMine() {
  var h = '<div class="row" style="margin:18px 0 0;flex-wrap:wrap"><div style="position:relative;flex:1;min-width:260px">' +
          '<input class="field" style="width:100%" id="gsearch" placeholder="Add a game you own… (search by name)" value="' + esc(ui.searchQ) + '" data-input="gsearch">';
  if (ui.results) {
    h += '<div class="search-results">';
    if (ui.searching) h += '<div class="res muted">Searching…</div>';
    ui.results.forEach(function (r) {
      var linked = (S.games || []).some(function (g) { return g.appid === r.appid; });
      h += '<div class="res"><img src="' + img(r.image) + '" onerror="this.style.visibility=\'hidden\'"><span class="ell" style="flex:1">' + esc(r.name) + "</span>" +
           (linked ? '<span class="muted small">Linked ✓</span>' : '<button class="btn sm primary" data-act="link" data-appid="' + esc(r.appid) + '" data-name="' +
           esc(r.name) + '" data-image="' + esc(r.image) + '">＋ Link</button>') + "</div>";
    });
    if (ui.searchQ.trim().length > 1) h += '<div class="res"><span class="muted small" style="flex:1">Not on Steam (Fortnite, Valorant, Minecraft…)? Follow its news instead:</span>' +
         '<button class="btn sm" data-act="linkname" data-name="' + esc(ui.searchQ.trim()) + '">＋ Add “' + esc(ui.searchQ.trim()) + '”</button></div>';
    h += "</div>";
  }
  h += '</div><button class="btn" data-act="scan">🔍 Find games on this PC</button><button class="btn" data-act="owned">⬇ Import my Steam library</button></div>';
  var games = S.games || [];
  if (!games.length) {
    h += '<div class="empty" style="margin-top:20px"><b>No games linked yet</b>Link the games you own to get their patch notes and news, and start them from here.<br>' +
         "Search above, or let Nova find the Steam & Epic games installed on this PC (you choose which to link).</div>";
    return h;
  }
  h += '<h2>Your games (' + games.length + ')<span class="line"></span></h2><div class="grid" style="--min:250px">';
  games.forEach(function (g) {
    var last = latestFor(g.id), src = { steam: "Steam", epic: "Epic", manual: "Other" }[g.source] || "Game";
    h += '<div class="card game-card"' + (isOn(g) ? "" : ' style="opacity:.55"') + '><div class="img"><span class="src">' + esc(src) + "</span>" + gameImg(g) +
         '<span>🎮</span></div><div class="body"><div class="name ell">' + esc(g.name) + "</div>" +
         (last ? '<div class="small clamp2 click" data-act="open" data-url="' + esc(last.url) + '"><span class="muted">' + esc(ago(last.time)) + " · </span>" + esc(last.title) + "</div>"
               : '<div class="small muted">' + ((S.state.errors || {})[g.id] ? "Couldn't load updates right now." : (g.appid ? "No recent updates." : "Following its news.")) + "</div>") +
         '<div class="actions">' + (g.launch ? '<button class="btn sm primary" data-act="launch" data-id="' + esc(g.id) + '">▶ Play</button>' : "") +
         '<button class="btn sm" data-act="gupdates" data-id="' + esc(g.id) + '">📰 Updates</button><div class="spacer"></div>' +
         '<button class="btn sm ghost" data-act="unfollow" data-id="' + esc(g.id) + '" title="Unlink">✕</button></div>' +
         '<div class="row" style="gap:16px"><span class="lbl">Show ' + sw(g.id, "on", g.on, "Show its updates") + '</span><span class="lbl">🔔 Alerts ' +
         sw(g.id, "notify", g.notify, "Alerts for new updates") + "</span></div></div></div>";
  });
  h += "</div>";
  h += '<h2>On your start page<span class="line"></span></h2><div class="card"><div class="row">' + widgetPicker("gamenews", "Game updates widget") + "</div></div>";
  return h;
}
function renderUpdates() {
  var on = {}; (S.games || []).forEach(function (g) { if (isOn(g)) on[g.id] = g; });
  var items = ((S.state || {}).game_news || []).filter(function (i) { return on[i.game_id] && (!ui.gameFilter || i.game_id === ui.gameFilter); });
  var h = '<div class="row" style="margin:18px 0 10px"><select class="field" data-input="gfilter"><option value="">All your games</option>';
  Object.keys(on).forEach(function (id) { h += '<option value="' + esc(id) + '"' + (ui.gameFilter === id ? " selected" : "") + ">" + esc(on[id].name) + "</option>"; });
  h += "</select></div>";
  if (!(S.games || []).length) return h + '<div class="empty"><b>No games linked</b>Link your games in “My games” to see their updates here.<br><br>' +
                                  '<button class="btn primary" data-act="tab" data-tab="mine">Link games</button></div>';
  if (!items.length) return h + '<div class="empty">' + (S.busy ? "Loading updates…" : "No updates yet.") + "</div>";
  var lo = (S.last_open || {}).games || 0;
  h += '<div style="display:flex;flex-direction:column;gap:10px">';
  items.slice(0, 200).forEach(function (i) {
    h += '<div class="card item click" data-act="open" data-url="' + esc(i.url) + '"><div style="min-width:0;flex:1"><div class="meta">🎮 <b>' + esc(i.game) + "</b> · " +
         esc(i.label || "News") + " · " + esc(ago(i.time)) + (i.official ? ' · <span style="color:var(--al)">official</span>' : "") +
         (i.time > lo ? ' · <span style="color:var(--al)">new</span>' : "") + '</div><div class="t">' + esc(i.title) + "</div>" +
         (i.summary ? '<div class="s clamp2">' + esc(i.summary) + "</div>" : "") + "</div></div>";
  });
  return h + "</div>";
}
function renderFree() {
  if (!S.free_on) return '<div class="empty" style="margin-top:20px"><b>Free games of the week is off</b><br><button class="btn primary" data-act="enable" data-key="games_free_week">Turn it on</button></div>';
  var free = (S.state || {}).free || [];
  var h = '<p class="muted" style="margin:16px 0 0">Games the Epic Games Store gives away to keep forever. You claim them on Epic\'s site with your own account.</p>';
  if (!free.length) return h + '<div class="empty" style="margin-top:14px">' + (S.busy ? "Loading…" : "Nothing listed right now.") + "</div>";
  h += '<div class="grid" style="--min:260px;margin-top:14px">';
  free.forEach(function (g) {
    h += '<div class="card game-card free-card click" data-act="open" data-url="' + esc(g.url) + '"><div class="img">' +
         (g.image ? '<img src="' + img(g.image) + '" onerror="this.remove()">' : "") + '<span>🎁</span></div><div class="body"><div class="row"><span class="pill ' +
         (g.now ? "now" : "soon") + '">' + (g.now ? "FREE NOW" : "COMING SOON") + '</span><span class="muted small">' +
         (g.now ? "until " + esc(shortDate(g.end)) : esc(shortDate(g.start)) + " – " + esc(shortDate(g.end))) + '</span></div><div class="name">' + esc(g.title) +
         '</div><div class="small muted clamp2">' + esc(g.summary) + "</div>" + (g.worth ? '<div class="small muted">Normally $' + (g.worth / 100).toFixed(2) + "</div>" : "") +
         "</div></div>";
  });
  return h + "</div>";
}
/* ---------------- deals ---------------- */
function money(v) { return v == null ? "–" : "$" + Number(v).toFixed(2); }
function dealImg(steam, thumb) {
  var big = steam ? "https://cdn.akamai.steamstatic.com/steam/apps/" + steam + "/header.jpg" : "";
  return big ? '<img src="' + img(big) + '" data-alt="' + esc(thumb || "") + '" onerror="if(this.dataset.alt){this.src=this.dataset.alt;this.dataset.alt=\'\'}else{this.remove()}">'
             : (thumb ? '<img src="' + img(thumb) + '" onerror="this.remove()">' : "");
}
function targetHit(w) { return w.target != null && w.best != null && w.best <= w.target; }
function renderDeals() {
  if (!S.deals_on) return '<div class="empty" style="margin-top:20px"><b>Game deals are off</b><br><button class="btn primary" data-act="enable" data-key="games_deals">Turn them on</button></div>';
  var h = '<div class="row" style="margin:18px 0 0"><div style="position:relative;flex:1;min-width:260px">' +
          '<input class="field" style="width:100%" id="dsearch" placeholder="Add a game to your wishlist… (search by name)" value="' + esc(ui.dQ) + '" data-input="dsearch">';
  if (ui.dResults) {
    h += '<div class="search-results">';
    if (ui.dSearching) h += '<div class="res muted">Searching…</div>';
    if (!ui.dSearching && !ui.dResults.length) h += '<div class="res muted">No games found.</div>';
    ui.dResults.forEach(function (r, i) {
      var have = (S.wishlist || []).some(function (w) { return w.gid === r.gid; });
      h += '<div class="res"><img src="' + img(r.thumb) + '" onerror="this.style.visibility=\'hidden\'"><span class="ell" style="flex:1">' + esc(r.title) + '</span><span class="muted small">' +
           (r.cheapest != null ? "from " + money(r.cheapest) : "") + "</span>" +
           (have ? '<span class="muted small">On wishlist ✓</span>' : '<button class="btn sm primary" data-act="wish" data-i="' + i + '">＋ Wishlist</button>') + "</div>";
    });
    h += "</div>";
  }
  h += "</div></div>";
  var wl = S.wishlist || [];
  if (!wl.length) h += '<div class="empty" style="margin-top:18px"><b>Your wishlist is empty</b>Add games and Nova checks their prices on Steam, Epic, GOG, Humble and more ' +
                       "every hour. You get an alert when the price drops, or when it hits the price you set.</div>";
  else {
    h += '<h2>Your wishlist (' + wl.length + ')<span class="line"></span></h2><div class="grid" style="--min:270px">';
    wl.forEach(function (w) {
      var hit = targetHit(w);
      h += '<div class="card game-card deal-card"' + (hit ? ' style="border-color:#2fd38a"' : "") + '><div class="img">' + dealImg(w.steam, w.thumb) + '<span>💸</span></div><div class="body">' +
           '<div class="name ell">' + esc(w.title) + "</div>" +
           (w.best == null ? '<div class="muted small">' + ((S.state.errors || {}).deals ? "Couldn't check prices right now." : "Checking prices…") + "</div>" :
            '<div class="row"><span class="price">' + money(w.best) + "</span>" + (w.savings ? '<span class="pill off">−' + w.savings + "%</span>" : "") +
            '<span class="muted small ell">at ' + esc(w.store || "") + "</span></div>" +
            '<div class="small muted">' + (w.retail && w.retail > w.best ? "Normally " + money(w.retail) + " · " : "") + (w.lowest != null ? "Lowest ever " + money(w.lowest) : "") + "</div>") +
           (hit ? '<div class="small" style="color:#2fd38a;font-weight:600">🎯 At or below your price!</div>' : "") +
           '<div class="row small">🎯 Alert me at $<input class="field sm" type="number" min="0" step="0.01" placeholder="any drop" data-input="target" data-id="' + esc(w.id) + '" value="' + (w.target != null ? w.target : "") + '"></div>' +
           '<div class="actions">' + (w.deal ? '<button class="btn sm primary" data-act="opendeal" data-deal="' + esc(w.deal) + '">🛒 View deal</button>' : "") +
           '<div class="spacer"></div><span class="lbl">🔔 ' + sw(w.id, "notify", w.notify, "Price alerts") + '</span><button class="btn sm ghost" data-act="wishremove" data-id="' + esc(w.id) + '" title="Remove">✕</button></div></div></div>';
    });
    h += "</div>";
  }
  if (S.top_deals_on) {
    var deals = (S.state || {}).deals || [];
    h += '<h2>🔥 Top deals right now<span class="line"></span><button class="btn sm ghost" data-act="setopt" data-key="games_top_deals" data-v="0">Hide</button></h2>';
    if (!deals.length) h += '<div class="empty">' + (S.busy ? "Loading…" : "No deals loaded yet.") + "</div>";
    else {
      h += '<div class="grid" style="--min:230px">';
      deals.forEach(function (d) {
        h += '<div class="card game-card deal-card click" data-act="opendeal" data-deal="' + esc(d.deal) + '"><div class="img">' + dealImg(d.steam, d.thumb) + '<span class="src">' + esc(d.store) +
             '</span><span>🔥</span></div><div class="body"><div class="name ell">' + esc(d.title) + '</div><div class="row"><span class="price" style="font-size:18px">' + money(d.price) +
             '</span><span class="strike">' + money(d.retail) + '</span><span class="pill off">−' + d.savings + "%</span></div>" +
             (d.rating ? '<div class="small muted">Steam reviews: ' + esc(d.rating) + "</div>" : "") + "</div></div>";
      });
      h += "</div>";
    }
  } else h += '<p style="margin-top:22px"><button class="btn" data-act="setopt" data-key="games_top_deals" data-v="1">🔥 Show top deals</button></p>';
  h += '<p class="muted small" style="margin-top:14px">Prices come from CheapShark. Buying always happens on the store\'s own site.</p>';
  return h;
}

/* ---------------- profile: XP, level, badges, rewards ---------------- */
function renderProfile() {
  var X = S.xp || {}, lv = X.level || 1, span = Math.max(1, (X.next || 100) - (X.floor || 0)), into = (X.total || 0) - (X.floor || 0);
  var pct = Math.max(0, Math.min(100, Math.round(into / span * 100))), st = X.stats || {};
  var got = (X.badges || []).filter(function (b) { return b.got; }).length;
  var h = '<div class="card level-card" style="margin-top:18px"><div class="level-ring" style="--p:' + pct + '"><div><div><span>LEVEL</span><b>' + lv + "</b></div></div></div>" +
          '<div style="flex:1;min-width:240px"><div style="font-size:20px;font-weight:700">' + (X.total || 0).toLocaleString() + ' XP</div>' +
          '<div class="xpbar"><div style="width:' + pct + '%"></div></div><div class="muted small">' + Math.max(0, (X.next || 0) - (X.total || 0)).toLocaleString() + " XP to level " + (lv + 1) +
          " · " + got + " / " + (X.badges || []).length + ' badges</div></div><div style="text-align:center"><div style="font-size:30px">🔥</div><b>' + (X.streak || 0) +
          '-day streak</b><div class="muted small">best ' + (X.best_streak || 0) + "</div></div></div>";
  h += '<div class="wrapflex" style="margin-top:12px">';
  [["Pages browsed", st.pages], ["Games tried", (st.games || 0) + " / 12"], ["Rounds played", st.rounds], ["Episodes watched", st.episodes], ["Things zapped", st.zaps],
   ["Gestures", st.gestures], ["Voice commands", st.voice]].forEach(function (c) { h += '<div class="stat-chip"><b>' + esc(c[1] == null ? 0 : c[1]) + "</b>" + esc(c[0]) + "</div>"; });
  h += "</div>";
  h += '<h2>Badges<span class="line"></span></h2><div class="grid" style="--min:150px">';
  (X.badges || []).slice().sort(function (a, b) { return (b.got ? 1 : 0) - (a.got ? 1 : 0); }).forEach(function (b) {
    h += '<div class="card badge-card ' + (b.got ? "got" : "locked") + '" title="' + esc(b.desc) + '"><div class="e">' + esc(b.emoji) + '</div><div class="n">' + esc(b.name) +
         '</div><div class="d">' + esc(b.desc) + "</div>" + (b.got ? '<div class="small" style="color:var(--al);margin-top:4px">✓ ' + esc(shortDate(b.got)) + "</div>" : "") + "</div>";
  });
  h += '</div><h2>Rewards: style packs you unlock<span class="line"></span></h2><div class="card" style="padding:4px 0">';
  (X.rewards || []).forEach(function (r) {
    h += '<div class="reward"><div class="lv">Level ' + r.level + '</div><div style="flex:1"><b>' + (r.unlocked ? "✨ " : "🔒 ") + esc(r.name) + '</b><div class="muted small">' + esc(r.desc) + "</div></div>" +
         (r.unlocked ? '<button class="btn sm primary" data-act="applypack" data-name="' + esc(r.name) + '">Use it</button>' : '<span class="muted small">Reach level ' + r.level + "</span>") + "</div>";
  });
  h += "</div>";
  var bests = X.best || {}, rows = "";
  (H.games || []).forEach(function (g) { if (bests[g.id] != null) rows += '<div class="stat-chip"><b>' + esc(g.emoji) + " " + esc(bests[g.id]) + "</b>" + esc(g.name) + " · " + esc(g.best_label || "Best") + "</div>"; });
  if (rows) h += '<h2>Your bests<span class="line"></span></h2><div class="wrapflex">' + rows + "</div>";
  h += '<h2>How to earn XP<span class="line"></span></h2><div class="card small muted" style="line-height:1.9">' +
       "🗓 Open the browser each day: <b>+20</b> (+5 more per day of your streak) · 🕹 Play built-in games: <b>+3</b> a round, <b>+10</b> new best, <b>+15</b> a win · " +
       "🏆 Every badge: <b>+50</b> · 📣 Follow something / 🎮 link a game / 💸 wishlist a game: <b>+5</b> · 🍿 Mark an episode watched: <b>+5</b> · " +
       "✦ Nova page summary: <b>+5</b> · 🎯 Zap something: <b>+3</b> · 🎙 Voice command: <b>+2</b> · 🖱 Gesture: <b>+1</b> · 🧭 Every 5 pages: <b>+1</b>.<br>" +
       "Most things have a daily limit, so it can't be farmed. Your XP is saved only on this PC.</div>";
  return h;
}
function renderGames() {
  if (!S.enabled.games) return disabledPage("🎮 Games", "hub_games");
  var n = 0, lo = (S.last_open || {}).games || 0, on = {};
  (S.games || []).forEach(function (g) { if (isOn(g)) on[g.id] = 1; });
  ((S.state || {}).game_news || []).forEach(function (i) { if (on[i.game_id] && i.time > lo) n++; });
  var tabs = [["play", "▶ Play"], ["mine", "My games"], ["updates", "Updates", n ? Math.min(n, 99) : 0]];
  if (S.free_on) tabs.push(["free", "🎁 Free this week"]);
  if (S.deals_on) tabs.push(["deals", "💸 Deals", (S.wishlist || []).filter(targetHit).length]);
  if (S.xp_on !== false) tabs.push(["profile", "🏆 Lv " + ((S.xp || {}).level || 1)]);
  return header(tabs) + (tab === "mine" ? renderMine() : tab === "updates" ? renderUpdates() : tab === "free" ? renderFree() :
                         tab === "deals" ? renderDeals() : (tab === "profile" && S.xp_on !== false) ? renderProfile() : renderPlay());
}

/* ================================================================ modal (scan / Steam library) ============================== */
function renderModal() {
  var m = ui.modal; if (!m) return "";
  var h = '<div class="modal-bg"><div class="modal"><header><b style="font-size:16px">' + esc(m.title) + '</b><div class="muted small">' + esc(m.sub || "") + "</div></header><div class=\"body\">";
  if (m.loading) h += '<div class="muted" style="padding:20px">Looking…</div>';
  else if (m.error) h += '<div class="err" style="padding:20px">' + esc(m.error) + "</div>";
  else if (!m.items.length) h += '<div class="muted" style="padding:20px">No games found.</div>';
  else m.items.forEach(function (g, i) {
    h += '<label class="check-row"><input type="checkbox" data-input="pick" data-i="' + i + '"' + (g.linked ? " disabled checked" : (m.picked[i] ? " checked" : "")) + ">" +
         '<img src="' + img(g.image || (g.appid ? "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/" + g.appid + "/capsule_231x87.jpg" : "")) + '" onerror="this.style.visibility=\'hidden\'">' +
         '<span class="ell" style="flex:1">' + esc(g.name) + "</span><span class=\"muted small\">" + (g.linked ? "linked ✓" :
         (g.hours != null ? esc(g.hours) + " h" : esc({ steam: "Steam", epic: "Epic" }[g.source] || ""))) + "</span></label>";
  });
  var count = Object.keys(m.picked).filter(function (k) { return m.picked[k]; }).length;
  h += '</div><footer><button class="btn ghost" data-act="pickall">Select all</button><div class="spacer"></div><button class="btn" data-act="closemodal">Cancel</button>' +
       '<button class="btn primary" data-act="linkpicked"' + (count ? "" : " disabled") + ">Link " + (count || "") + " game" + (count === 1 ? "" : "s") + "</button></footer></div></div>";
  return h;
}

/* ================================================================ render + events =========================================== */
function render() {
  if (!S) return;
  var focus = document.activeElement && document.activeElement.id, caret = focus && document.activeElement.selectionStart;
  var sy = window.scrollY;
  app.innerHTML = (KIND === "games" ? renderGames() : renderFollow()) + renderModal();
  if (focus && document.getElementById(focus)) { var f = document.getElementById(focus); f.focus(); try { f.setSelectionRange(caret, caret); } catch (e) {} }
  window.scrollTo(0, sy);
}
function loadTeams(lg) {
  if (ui.teams[lg]) return;
  api("teams", { league: lg }).then(function (list) { ui.teams[lg] = list; render(); }, function (e) { ui.teams[lg] = { error: e }; render(); });
}
var searchTimer = null;
function doSearch() {
  var q = ui.searchQ.trim();
  if (q.length < 2) { ui.results = null; render(); return; }
  ui.searching = true; ui.results = ui.results || []; render();
  api("search_games", { q: q }).then(function (r) { if (q !== ui.searchQ.trim()) return; ui.searching = false; ui.results = r; render(); },
                                     function (e) { ui.searching = false; ui.results = []; render(); toast("Search failed: " + e); });
}
var aTimer = null, dTimer = null;
function animeSearch() {
  var q = ui.aQ.trim(); if (q.length < 2) { ui.aResults = null; render(); return; }
  ui.aSearching = true; ui.aResults = ui.aResults || []; render();
  api("anime_search", { q: q }).then(function (r) { if (q !== ui.aQ.trim()) return; ui.aSearching = false; ui.aResults = r; render(); },
                                     function (e) { ui.aSearching = false; ui.aResults = []; render(); toast("Search failed: " + e); });
}
function dealSearch() {
  var q = ui.dQ.trim(); if (q.length < 2) { ui.dResults = null; render(); return; }
  ui.dSearching = true; ui.dResults = ui.dResults || []; render();
  api("deal_search", { q: q }).then(function (r) { if (q !== ui.dQ.trim()) return; ui.dSearching = false; ui.dResults = r; render(); },
                                    function (e) { ui.dSearching = false; ui.dResults = []; render(); toast("Search failed: " + e); });
}
function addSource(text) {
  text = (text || "").trim(); if (!text) return;
  ui.addMsg = "Adding “" + text + "”…"; render();
  api("add_source", { text: text }).then(function (item) { ui.addMsg = "✓ Following " + item.name; var i = document.getElementById("addsrc"); if (i) i.value = ""; render(); },
                                          function (e) { ui.addMsg = "⚠ " + e; render(); });
}
function openModal(title, sub, loader) {
  ui.modal = { title: title, sub: sub, loading: true, items: [], picked: {} }; render();
  loader.then(function (items) { if (!ui.modal) return; ui.modal.loading = false; ui.modal.items = items || []; render(); },
              function (e) { if (!ui.modal) return; ui.modal.loading = false; ui.modal.error = String(e); render(); });
}
document.addEventListener("click", function (e) {
  var t = e.target.closest("[data-act]"); if (!t) return;
  var a = t.dataset.act;
  if (a === "toggle" || t.tagName === "INPUT") return;      // handled by change
  if (t.closest(".switch") || t.closest(".lbl")) { if (a !== "unfollow") return; }
  e.preventDefault();
  if (a === "tab") setTab(t.dataset.tab);
  else if (a === "refresh") { api("refresh"); S.busy = true; render(); }
  else if (a === "open") { if (t.dataset.url) openUrl(t.dataset.url); }
  else if (a === "enable") api("set_option", { key: t.dataset.key, value: true });
  else if (a === "league") { ui.league = ui.league === t.dataset.k ? null : t.dataset.k; ui.teamQuery = ""; if (ui.league && leagueOf(ui.league).teams) loadTeams(ui.league); render(); }
  else if (a === "followleague") {
    var lf = follows("league").filter(function (f) { return f.league === t.dataset.k; })[0];
    (lf ? api("unfollow", { id: lf.id }) : api("follow_league", { league: t.dataset.k })).then(function () { toast(lf ? "Unfollowed" : "Following " + leagueOf(t.dataset.k).name); });
  }
  else if (a === "team") {
    var team = (ui.teams[ui.league] || []).filter(function (x) { return x.id === t.dataset.tid; })[0]; if (!team) return;
    var fid = "team:" + ui.league + ":" + team.id, have = follows("team").some(function (f) { return f.id === fid; });
    (have ? api("unfollow", { id: fid }) : api("follow_team", { league: ui.league, team_id: team.id, name: team.name, abbr: team.abbr, logo: team.logo, color: team.color }))
      .then(function () { toast(have ? "Unfollowed " + team.name : "Following " + team.name); });
  }
  else if (a === "unfollow") { api("unfollow", { id: t.dataset.id }); }
  else if (a === "addsrc") addSource((document.getElementById("addsrc") || {}).value);
  else if (a === "quick") addSource(t.dataset.text);
  else if (a === "play") location.href = "play/" + encodeURIComponent(t.dataset.id) + ".html";
  else if (a === "link") api("link_game", { appid: t.dataset.appid, name: t.dataset.name, image: t.dataset.image }).then(function (g) { toast("Linked " + g.name); });
  else if (a === "linkname") api("link_game", { name: t.dataset.name }).then(function (g) { toast("Following news for " + g.name); ui.results = null; ui.searchQ = ""; render(); });
  else if (a === "launch") api("launch", { id: t.dataset.id }).then(function () { toast("Starting…"); }, function (err) { toast(err); });
  else if (a === "gupdates") { ui.gameFilter = t.dataset.id; setTab("updates"); }
  else if (a === "scan") openModal("Games on this PC", "Pick the games you want to link. Only Steam and Epic games can be found.", api("scan_games"));
  else if (a === "owned") {
    if (!S.has_steam_key) { toast("Add your Steam Web API key + Steam ID in Customize first"); api("customize"); return; }
    openModal("Your Steam library", "Sorted by hours played. Pick the games you want updates for.", api("steam_owned"));
  }
  else if (a === "trackanime") {
    var r = (ui.aResults || [])[+t.dataset.i]; if (!r) return;
    api("follow_anime", { anilist_id: r.anilist_id, name: r.title, image: r.image, url: r.url, progress: t.dataset.from === "caught" ? (r.aired || 0) : 0 })
      .then(function () { toast("Tracking " + r.title); ui.aResults = null; ui.aQ = ""; render(); }, function (e) { toast(String(e)); });
  }
  else if (a === "aprog") api("anime_progress", { id: t.dataset.id, value: +t.dataset.v });
  else if (a === "wish") {
    var d = (ui.dResults || [])[+t.dataset.i]; if (!d) return;
    api("wish_add", { gid: d.gid, title: d.title, thumb: d.thumb }).then(function () { toast("Added " + d.title + " to your wishlist"); ui.dResults = null; ui.dQ = ""; render(); });
  }
  else if (a === "wishremove") api("wish_remove", { id: t.dataset.id });
  else if (a === "opendeal") api("open_deal", { deal: t.dataset.deal });
  else if (a === "setopt") api("set_option", { key: t.dataset.key, value: t.dataset.v === "1" });
  else if (a === "applypack") api("apply_pack", { name: t.dataset.name }).then(function () { toast("✨ " + t.dataset.name + " applied"); }, function (e) { toast(String(e)); });
  else if (a === "pickall") { ui.modal.items.forEach(function (g, i) { if (!g.linked) ui.modal.picked[i] = true; }); render(); }
  else if (a === "closemodal") { ui.modal = null; render(); }
  else if (a === "linkpicked") {
    var m = ui.modal, items = m.items.filter(function (g, i) { return m.picked[i] && !g.linked; });
    m.loading = true; render();
    api("link_scanned", { items: items }).then(function (n) { ui.modal = null; toast("Linked " + n + " game" + (n === 1 ? "" : "s")); setTab("mine"); },
                                                function (e) { ui.modal = null; toast(String(e)); render(); });
  }
});
document.addEventListener("change", function (e) {
  var t = e.target;
  if (t.dataset.act === "toggle") api("toggle", { id: t.dataset.id, field: t.dataset.field, value: t.checked });
  else if (t.dataset.input === "widget") api("set_widget", { widget: t.dataset.w, pos: t.value }).then(function () { toast("Start page updated"); });
  else if (t.dataset.input === "gfilter") { ui.gameFilter = t.value; render(); }
  else if (t.dataset.input === "pick") { ui.modal.picked[t.dataset.i] = t.checked; render(); }
  else if (t.dataset.input === "target") api("wish_target", { id: t.dataset.id, target: t.value }).then(function () { toast(t.value ? "You'll get an alert at $" + Number(t.value).toFixed(2) : "You'll get an alert on any price drop"); }, function (e) { toast(String(e)); });
});
document.addEventListener("input", function (e) {
  var t = e.target;
  if (t.dataset.input === "teamq") { ui.teamQuery = t.value; render(); }
  else if (t.dataset.input === "gsearch") { ui.searchQ = t.value; clearTimeout(searchTimer); searchTimer = setTimeout(doSearch, 350); }
  else if (t.dataset.input === "asearch") { ui.aQ = t.value; clearTimeout(aTimer); aTimer = setTimeout(animeSearch, 400); }
  else if (t.dataset.input === "dsearch") { ui.dQ = t.value; clearTimeout(dTimer); dTimer = setTimeout(dealSearch, 400); }
});
document.addEventListener("keydown", function (e) {
  if (e.key === "Enter" && e.target.id === "addsrc") addSource(e.target.value);
  if (e.key === "Escape") { if (ui.modal) { ui.modal = null; render(); } else if (ui.results || ui.aResults || ui.dResults) { ui.results = ui.aResults = ui.dResults = null; render(); } }
});
document.addEventListener("mousedown", function (e) {
  if (e.target.closest(".search-results")) return;
  var ch = false;
  if (ui.results && e.target.id !== "gsearch") { ui.results = null; ch = true; }
  if (ui.aResults && e.target.id !== "asearch") { ui.aResults = null; ch = true; }
  if (ui.dResults && e.target.id !== "dsearch") { ui.dResults = null; ch = true; }
  if (ch) render();
});
function markSeen() { if (nova && document.visibilityState === "visible") api("mark_seen", { hub: KIND }); }
document.addEventListener("visibilitychange", markSeen);
setInterval(function () { if (S && document.visibilityState === "visible" && !ui.modal && !ui.results && !ui.aResults && !ui.dResults && document.activeElement.tagName !== "INPUT") render(); }, 30000);

/* ---------------- connect to the browser ---------------- */
function connect() {
  if (typeof QWebChannel === "undefined" || !window.qt || !qt.webChannelTransport) {
    app.innerHTML = '<div class="empty" style="margin-top:40px"><b>Couldn\'t connect to Nova Browser</b>Close this tab and open it again from the toolbar.</div>';
    return;
  }
  new QWebChannel(qt.webChannelTransport, function (ch) {
    nova = ch.objects.nova;
    nova.reply.connect(function (id, json) {
      var p = pending[id]; if (!p) return; delete pending[id];
      var r = {}; try { r = JSON.parse(json); } catch (e) {}
      if (r.ok) p.res(r.result); else p.rej(r.error || "failed");
    });
    nova.push.connect(function (kind, json) {
      if (kind === "state") { try { S = JSON.parse(json); } catch (e) { return; } if (!ui.modal && document.activeElement.dataset.input !== "target") render(); }
    });
    api("state").then(function (s) { S = s; render(); markSeen(); if (tab === "manage" && ui.league) loadTeams(ui.league); });
  });
}
connect();
})();
</script>
</body></html>
"""


def hub_dir(data_dir):
    return Path(data_dir) / "hub"


def hub_file(data_dir, kind):
    return hub_dir(data_dir) / ("games.html" if kind == "games" else "following.html")


def hub_kind_of(url, data_dir):
    """'follow' / 'games' when this QUrl is one of the hub pages, 'play' for a built-in game page, else None."""
    try:
        if not url.isLocalFile():
            return None
        p = os.path.normcase(os.path.abspath(url.toLocalFile()))
        for kind in ("follow", "games"):
            if p == os.path.normcase(os.path.abspath(str(hub_file(data_dir, kind)))):
                return kind
        play = os.path.normcase(os.path.abspath(str(hub_dir(data_dir) / "play")))
        if os.path.dirname(p) == play and re.fullmatch(r"[a-z0-9]+\.html", os.path.basename(p)) \
                and os.path.basename(p)[:-5] in GAME_IDS:
            return "play"
    except Exception:
        return None
    return None


def build_pages(data_dir, colors):
    """Writes the hub pages and every game page (with your colours)."""
    d = hub_dir(data_dir)
    (d / "play").mkdir(parents=True, exist_ok=True)
    qjs = qwebchannel_js()
    for kind in ("follow", "games"):
        cfg = {"kind": kind, "colors": colors,
               "leagues": [{"key": k, "name": n, "emoji": e, "teams": t} for k, n, p, e, t in LEAGUES],
               "suggestions": SOURCE_SUGGESTIONS, "games": game_meta(),
               "sites": [{"name": n, "url": u, "emoji": e, "desc": ds} for n, u, e, ds in WEB_GAME_SITES]}
        page = HUB_PAGE.replace("<!--QWEBCHANNEL-->", qjs, 1)
        page = page.replace("/*HUB_CONFIG*/{}", json.dumps(cfg, ensure_ascii=False).replace("</", "<\\/"), 1)
        hub_file(data_dir, kind).write_text(page, encoding="utf-8")
    for g in GAMES:
        (d / "play" / f"{g['id']}.html").write_text(build_game_page(g, colors, qjs), encoding="utf-8")
    return d


def attach_bridge(page, service):
    """Lets this page (a hub page) talk to the browser. Only ever attached to the hub pages."""
    if getattr(page, "_nova_channel", None) is not None:
        return
    from PyQt6.QtWebChannel import QWebChannel
    ch = QWebChannel(page)
    br = HubBridge(service, ch)
    ch.registerObject("nova", br)
    page.setWebChannel(ch, 0)              # 0 = the page's main world
    page._nova_channel = ch


def detach_bridge(page):
    ch = getattr(page, "_nova_channel", None)
    if ch is None:
        return
    page._nova_channel = None
    try:
        page.setWebChannel(None, 0)
    except TypeError:
        page.setWebChannel(None)
    ch.deleteLater()
