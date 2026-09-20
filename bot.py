"""
TECH RADAR BOT - 24/7 AI API Hunter
=====================================
Kya karta hai:
  - GitHub Trending, HackerNews, HuggingFace Spaces ko real HTTP requests se scrape karta hai
  - Naye free AI APIs aur endpoints dhundta hai
  - Har ghante Telegram pe update bhejta hai
  - /status se jaano abhi kahan hai
  - /scan se turant scan shuru karo
  - Render pe deploy ready (no paid APIs needed)
"""

import os, sys, time, threading, logging, json, re
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ─── CONFIG ───
BOT_TOKEN   = os.environ.get("BOT_TOKEN",   "8928294457:AAFbQG-pmGO6BYME20Eh6-ZoPJdeDEKkXoM")
MY_USER_ID  = int(os.environ.get("MY_USER_ID",  "7774638835"))
HEALTH_PORT = int(os.environ.get("PORT", 10000))

# ─── RADAR STATUS (live mein update hota rehta hai) ───
class RadarState:
    status  = "⏳ Starting up..."
    site    = "None"
    found   = []          # list of dicts: {title, url, desc, source, time}
    scans   = 0
    last_at = "Never"

state = RadarState()


# ════════════════════════════════════════════════
# HEALTH SERVER (Render ke liye)
# ════════════════════════════════════════════════
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Tech Radar Bot - OK")
    def log_message(self, *a): pass

def run_health():
    HTTPServer(("0.0.0.0", HEALTH_PORT), Health).serve_forever()


# ════════════════════════════════════════════════
# TELEGRAM SENDER (synchronous — background thread se)
# ════════════════════════════════════════════════
def tg_send(text, chat_id=None):
    chat_id = chat_id or MY_USER_ID
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text[:4000],
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=data, timeout=10)
        return r.ok
    except Exception as e:
        log.error(f"tg_send error: {e}")
        return False


# ════════════════════════════════════════════════
# SCRAPERS — REAL HTTP REQUESTS
# ════════════════════════════════════════════════

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TechRadarBot/1.0)",
    "Accept": "application/json, text/html"
}

def scrape_github_trending():
    """GitHub search API se trending AI/API repos dhundho"""
    state.site   = "GitHub Trending"
    state.status = "🔍 Scanning GitHub for AI APIs..."
    findings = []
    try:
        queries = ["free ai api", "llm api python", "open api ai free"]
        for q in queries:
            r = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": q, "sort": "updated", "per_page": 5},
                headers=HEADERS, timeout=10
            )
            if r.ok:
                for item in r.json().get("items", []):
                    findings.append({
                        "title":  item["full_name"],
                        "url":    item["html_url"],
                        "desc":   (item.get("description") or "No description")[:120],
                        "stars":  item.get("stargazers_count", 0),
                        "source": "GitHub",
                        "time":   datetime.now().strftime("%H:%M")
                    })
            time.sleep(1)
    except Exception as e:
        log.warning(f"GitHub scrape error: {e}")
    return findings


def scrape_hackernews():
    """HackerNews new stories mein API/AI keywords dhundho"""
    state.site   = "HackerNews"
    state.status = "🔍 Scanning HackerNews for API releases..."
    findings = []
    try:
        r = requests.get(
            "https://hacker-news.firebaseio.com/v0/newstories.json",
            headers=HEADERS, timeout=10
        )
        if not r.ok:
            return findings

        story_ids = r.json()[:30]
        keywords  = ["api", "llm", "free model", "open source ai", "language model", "endpoint"]

        for sid in story_ids:
            try:
                s = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                    headers=HEADERS, timeout=5
                ).json()
                if not s or not s.get("title"):
                    continue
                title_lower = s["title"].lower()
                if any(kw in title_lower for kw in keywords):
                    findings.append({
                        "title":  s["title"],
                        "url":    s.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                        "desc":   "HackerNews story",
                        "stars":  s.get("score", 0),
                        "source": "HackerNews",
                        "time":   datetime.now().strftime("%H:%M")
                    })
            except:
                pass
    except Exception as e:
        log.warning(f"HN scrape error: {e}")
    return findings


def scrape_huggingface():
    """HuggingFace Spaces API se trending AI models/spaces dhundho"""
    state.site   = "HuggingFace"
    state.status = "🔍 Scanning HuggingFace Spaces..."
    findings = []
    try:
        r = requests.get(
            "https://huggingface.co/api/spaces",
            params={"sort": "trending", "limit": 10, "filter": "api"},
            headers=HEADERS, timeout=10
        )
        if r.ok:
            for item in r.json():
                findings.append({
                    "title":  item.get("id", "Unknown"),
                    "url":    f"https://huggingface.co/spaces/{item.get('id','')}",
                    "desc":   (item.get("cardData", {}) or {}).get("short_description", "HF Space")[:120],
                    "stars":  item.get("likes", 0),
                    "source": "HuggingFace",
                    "time":   datetime.now().strftime("%H:%M")
                })
    except Exception as e:
        log.warning(f"HuggingFace scrape error: {e}")
    return findings


def scrape_github_topics():
    """GitHub topics API se free-api tagged repos dhundho"""
    state.site   = "GitHub Topics"
    state.status = "🔍 Scanning GitHub Topics..."
    findings = []
    topics = ["free-api", "openai-api", "llm", "ai-api"]
    try:
        for topic in topics:
            r = requests.get(
                f"https://api.github.com/search/repositories",
                params={"q": f"topic:{topic}", "sort": "stars", "per_page": 3},
                headers={**HEADERS, "Accept": "application/vnd.github.mercy-preview+json"},
                timeout=10
            )
            if r.ok:
                for item in r.json().get("items", []):
                    findings.append({
                        "title":  item["full_name"],
                        "url":    item["html_url"],
                        "desc":   (item.get("description") or "No desc")[:120],
                        "stars":  item.get("stargazers_count", 0),
                        "source": f"GitHub/{topic}",
                        "time":   datetime.now().strftime("%H:%M")
                    })
            time.sleep(1)
    except Exception as e:
        log.warning(f"GitHub topics error: {e}")
    return findings


# ════════════════════════════════════════════════
# RADAR LOOP — 24/7
# ════════════════════════════════════════════════
def run_radar():
    """Main 24/7 loop — scrapes every 60 minutes, sends Telegram update"""
    time.sleep(8)  # Bot ready hone do pehle

    while True:
        try:
            state.scans  += 1
            state.status  = "🚀 Starting hourly scan..."
            log.info(f"Radar scan #{state.scans} starting...")

            all_findings = []
            for scraper in [scrape_github_trending, scrape_hackernews,
                            scrape_huggingface, scrape_github_topics]:
                try:
                    results = scraper()
                    all_findings.extend(results)
                    time.sleep(2)
                except Exception as e:
                    log.error(f"Scraper error: {e}")

            state.last_at = datetime.now().strftime("%d %b %I:%M %p")
            state.status  = f"💤 Sleeping (last scan: {state.last_at})"

            # New findings dhundho (URL already dekha?)
            seen_urls = {f["url"] for f in state.found}
            new_ones  = [f for f in all_findings if f["url"] not in seen_urls]

            if new_ones:
                state.found.extend(new_ones)
                state.found = state.found[-100:]  # Last 100 rakh

                # Telegram pe bhejo
                msg = f"📡 *Tech Radar Update #{state.scans}*\n"
                msg += f"🕐 `{state.last_at}` | {len(new_ones)} naye items\n\n"

                for item in new_ones[:8]:  # Max 8 items per message
                    src = item["source"]
                    stars_txt = f"⭐ {item['stars']}" if item['stars'] else ""
                    msg += f"*{item['title']}* {stars_txt}\n"
                    msg += f"🔗 {item['url']}\n"
                    msg += f"_{item['desc'][:80]}_\n\n"

                tg_send(msg)
                log.info(f"Sent {len(new_ones)} new findings to Telegram")
            else:
                log.info(f"Scan #{state.scans} complete. No new findings.")

        except Exception as e:
            state.status = f"❌ Error: {e}"
            log.error(f"Radar loop error: {e}")

        # 1 ghante baad phir
        time.sleep(3600)


# ════════════════════════════════════════════════
# TELEGRAM BOT (python-telegram-bot)
# ════════════════════════════════════════════════
def run_bot():
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters

    async def cmd_start(u: Update, c):
        await u.message.reply_text(
            "🤖 *Tech Radar Bot*\n\n"
            "Main 24/7 GitHub, HackerNews aur HuggingFace monitor karta hoon "
            "naye AI APIs dhundne ke liye.\n\n"
            "Commands:\n"
            "/status — Abhi kya ho raha hai\n"
            "/found  — Aaj tak kya mila\n"
            "/scan   — Abhi turant scan karo",
            parse_mode="Markdown"
        )

    async def cmd_status(u: Update, c):
        msg = (
            f"📡 *Radar Status*\n\n"
            f"🌐 Site: `{state.site}`\n"
            f"📝 Status: `{state.status}`\n"
            f"🔄 Total Scans: `{state.scans}`\n"
            f"🔑 Total Found: `{len(state.found)}`\n"
            f"🕐 Last Scan: `{state.last_at}`"
        )
        await u.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_found(u: Update, c):
        if not state.found:
            await u.message.reply_text("Abhi kuch nahi mila. /scan karo!")
            return
        msg = f"🔑 *Found Items (Last {min(5, len(state.found))}):*\n\n"
        for item in state.found[-5:]:
            msg += f"*{item['title']}*\n🔗 {item['url']}\n_{item['desc'][:60]}_\n\n"
        await u.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

    async def cmd_scan(u: Update, c):
        await u.message.reply_text("🚀 Manual scan shuru! Results aane pe Telegram pe update aayega.")
        threading.Thread(target=run_radar_once, daemon=True).start()

    def run_radar_once():
        """Single scan — /scan command ke liye"""
        try:
            all_findings = []
            for scraper in [scrape_github_trending, scrape_hackernews,
                            scrape_huggingface, scrape_github_topics]:
                try:
                    all_findings.extend(scraper())
                    time.sleep(1)
                except: pass

            seen_urls = {f["url"] for f in state.found}
            new_ones  = [f for f in all_findings if f["url"] not in seen_urls]
            state.found.extend(new_ones)

            if new_ones:
                msg = f"⚡ *Manual Scan Results*\n{len(new_ones)} naye items mile!\n\n"
                for item in new_ones[:6]:
                    msg += f"*{item['title']}*\n🔗 {item['url']}\n\n"
                tg_send(msg)
            else:
                tg_send("⚡ *Manual Scan Complete* — Koi naya item nahi mila.")
        except Exception as e:
            tg_send(f"❌ Scan error: {e}")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("found",  cmd_found))
    app.add_handler(CommandHandler("scan",   cmd_scan))

    log.info("✅ Tech Radar Bot started!")
    app.run_polling()


# ════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════
if __name__ == "__main__":
    threading.Thread(target=run_health, daemon=True).start()
    threading.Thread(target=run_radar,  daemon=True).start()
    run_bot()
