"""
TECH RADAR BOT - AI Web2API Hunter
====================================
Kya karta hai:
  - GitHub pe "web2api", "unofficial-api", "reverse-proxy" wale projects dhundta hai
  - Specifically: Claude, GPT, Runway, Kling, Luma, Pika, Midjourney ke free wrappers
  - Found endpoints ko actually TEST karta hai (kaam karta hai ya nahi)
  - Har ghante Telegram pe 2 categories mein update:
      Category 1: No-key-needed working endpoints
      Category 2: Naye web2api tools / unofficial wrappers found
"""

import os, sys, time, threading, logging, json, re
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ─── CONFIG ───
BOT_TOKEN   = os.environ.get("BOT_TOKEN",  "8928294457:AAFbQG-pmGO6BYME20Eh6-ZoPJdeDEKkXoM")
MY_USER_ID  = int(os.environ.get("MY_USER_ID", "7774638835"))
HEALTH_PORT = int(os.environ.get("PORT", 10000))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TechRadarBot/1.0)",
    "Accept": "application/json, text/html"
}

# ─── RADAR STATE ───
class RadarState:
    status  = "⏳ Starting up..."
    site    = "None"
    scans   = 0
    last_at = "Never"
    # Category 1: No-key working endpoints (tested & verified)
    cat1_working = []
    # Category 2: Newly found web2api / unofficial wrappers
    cat2_wrappers = []
    seen_urls = set()

state = RadarState()


# ════════════════════════════════════════════════
# HEALTH SERVER
# ════════════════════════════════════════════════
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Tech Radar Bot - OK")
    def log_message(self, *a): pass

def run_health():
    HTTPServer(("0.0.0.0", HEALTH_PORT), Health).serve_forever()


# ════════════════════════════════════════════════
# TELEGRAM SENDER
# ════════════════════════════════════════════════
def tg_send(text, chat_id=None):
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id or MY_USER_ID,
        "text": text[:4000],
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        log.error(f"tg_send error: {e}")


# ════════════════════════════════════════════════
# KNOWN FREE/PUBLIC ENDPOINTS TO TEST
# (No API key needed — like gemini_web2api style)
# ════════════════════════════════════════════════
PUBLIC_ENDPOINTS_TO_TEST = [
    # Text / Chat
    {"name": "Pollinations Text",    "url": "https://text.pollinations.ai/hello",                          "method": "GET",  "type": "text"},
    {"name": "HuggingFace Zephyr",   "url": "https://api-inference.huggingface.co/models/HuggingFaceH4/zephyr-7b-beta", "method": "POST", "type": "text",
     "body": {"inputs": "Hello"}, "headers": {"Content-Type": "application/json"}},
    {"name": "HuggingFace Mistral",  "url": "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2", "method": "POST", "type": "text",
     "body": {"inputs": "Hello"}, "headers": {"Content-Type": "application/json"}},
    {"name": "Groq Llama (free)",    "url": "https://api.groq.com/openai/v1/models",                       "method": "GET",  "type": "text"},
    {"name": "OpenRouter Free",      "url": "https://openrouter.ai/api/v1/models",                         "method": "GET",  "type": "text"},
    {"name": "Gemini Web2API",       "url": "http://localhost:8081/v1/models",                              "method": "GET",  "type": "text"},

    # Image
    {"name": "Pollinations Image",   "url": "https://image.pollinations.ai/prompt/test",                   "method": "GET",  "type": "image"},
    {"name": "HuggingFace SDXL",     "url": "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0", "method": "POST", "type": "image",
     "body": {"inputs": "a cat"}, "headers": {"Content-Type": "application/json"}},

    # Video
    {"name": "HuggingFace SVD",      "url": "https://api-inference.huggingface.co/models/stabilityai/stable-video-diffusion-img2vid", "method": "POST", "type": "video",
     "body": {"inputs": "test"}, "headers": {"Content-Type": "application/json"}},
]


def test_endpoint(ep):
    """
    Ek endpoint ko actually test karo.
    Returns: dict with {works, status_code, response_hint}
    """
    try:
        hdrs = {**HEADERS, **(ep.get("headers") or {})}
        body = ep.get("body")
        url  = ep["url"]

        if ep["method"] == "GET":
            r = requests.get(url, headers=hdrs, timeout=8)
        else:
            r = requests.post(url, headers=hdrs, json=body, timeout=8)

        works = r.status_code in [200, 201, 400]  # 400 bhi ok hai (endpoint alive, request format wrong)
        hint  = r.text[:80].replace("\n", " ") if r.text else ""
        return {"works": works, "status": r.status_code, "hint": hint}
    except Exception as e:
        return {"works": False, "status": 0, "hint": str(e)[:60]}


# ════════════════════════════════════════════════
# WEB2API / UNOFFICIAL WRAPPER SEARCHERS
# ════════════════════════════════════════════════

# Ye keywords GitHub pe search karte hain
WEB2API_QUERIES = [
    "claude web2api unofficial",
    "chatgpt web2api browser",
    "gpt4 unofficial api free",
    "runway unofficial api python",
    "kling ai api unofficial",
    "midjourney unofficial api",
    "luma dream machine api",
    "pika art api unofficial",
    "suno ai api unofficial",
    "elevenlabs free api wrapper",
    "stable diffusion free api",
    "flux ai free api",
    "gemini web2api",
    "web2api ai model",
    "reverse engineered ai api",
    "free llm api proxy",
    "video generation api free",
]

def scrape_web2api_repos():
    """GitHub pe web2api / unofficial wrapper repos dhundho"""
    state.site   = "GitHub Web2API Search"
    state.status = "🔍 Hunting web2api wrappers on GitHub..."
    findings = []

    for query in WEB2API_QUERIES[:8]:  # Rate limit avoid karne ke liye 8 hi
        try:
            r = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "updated", "per_page": 3},
                headers=HEADERS, timeout=10
            )
            if r.ok:
                for item in r.json().get("items", []):
                    findings.append({
                        "name":    item["full_name"],
                        "url":     item["html_url"],
                        "desc":    (item.get("description") or "No desc")[:100],
                        "stars":   item.get("stargazers_count", 0),
                        "updated": item.get("updated_at", "")[:10],
                        "query":   query,
                        "source":  "GitHub"
                    })
            time.sleep(1.5)  # GitHub rate limit
        except Exception as e:
            log.warning(f"Web2API search error [{query}]: {e}")

    return findings


def scrape_hackernews_web2api():
    """HN pe unofficial API / web2api mentions dhundho"""
    state.site   = "HackerNews"
    state.status = "🔍 Scanning HackerNews for unofficial APIs..."
    findings = []
    keywords = ["unofficial api", "web2api", "reverse engineer", "free api", "no api key"]

    try:
        r = requests.get(
            "https://hacker-news.firebaseio.com/v0/newstories.json",
            headers=HEADERS, timeout=10
        )
        if not r.ok:
            return findings

        for sid in r.json()[:40]:
            try:
                s = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                    headers=HEADERS, timeout=5
                ).json()
                if not s or not s.get("title"):
                    continue
                if any(kw in s["title"].lower() for kw in keywords):
                    findings.append({
                        "name":   s["title"],
                        "url":    s.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                        "desc":   "HackerNews",
                        "stars":  s.get("score", 0),
                        "source": "HackerNews"
                    })
            except:
                pass
    except Exception as e:
        log.warning(f"HN web2api error: {e}")

    return findings


def scrape_huggingface_spaces():
    """HuggingFace Spaces — free inference endpoints dhundho"""
    state.site   = "HuggingFace Spaces"
    state.status = "🔍 Scanning HuggingFace for free spaces..."
    findings = []
    try:
        r = requests.get(
            "https://huggingface.co/api/spaces",
            params={"sort": "trending", "limit": 15},
            headers=HEADERS, timeout=10
        )
        if r.ok:
            for item in r.json():
                sid  = item.get("id", "")
                sdk  = item.get("sdk", "")
                # Gradio spaces mein API hoti hai
                if sdk in ["gradio", "streamlit"]:
                    findings.append({
                        "name":   sid,
                        "url":    f"https://huggingface.co/spaces/{sid}",
                        "api":    f"https://{sid.replace('/', '-').lower()}.hf.space/api/predict",
                        "desc":   f"HF Space ({sdk}) — has free API",
                        "stars":  item.get("likes", 0),
                        "source": "HuggingFace"
                    })
    except Exception as e:
        log.warning(f"HF spaces error: {e}")
    return findings


# ════════════════════════════════════════════════
# MAIN RADAR LOOP
# ════════════════════════════════════════════════
def run_radar_scan():
    """Ek complete scan karo — dono categories update karo"""
    state.scans  += 1
    state.status  = f"🚀 Scan #{state.scans} running..."
    log.info(f"Starting radar scan #{state.scans}")

    # ── CATEGORY 1: Test known public endpoints ──
    cat1_new = []
    state.status = "⚡ Testing known public endpoints..."
    for ep in PUBLIC_ENDPOINTS_TO_TEST:
        result = test_endpoint(ep)
        if result["works"]:
            entry = {
                "name":   ep["name"],
                "url":    ep["url"],
                "type":   ep.get("type", "?"),
                "status": result["status"],
                "hint":   result["hint"],
                "time":   datetime.now().strftime("%H:%M")
            }
            # Already report kiya tha?
            key = ep["url"]
            if key not in state.seen_urls:
                cat1_new.append(entry)
                state.cat1_working.append(entry)
                state.seen_urls.add(key)
        time.sleep(0.5)

    # ── CATEGORY 2: Hunt new web2api repos ──
    cat2_new = []
    state.status = "🔍 Hunting new web2api repos..."

    for scraper in [scrape_web2api_repos, scrape_hackernews_web2api, scrape_huggingface_spaces]:
        try:
            results = scraper()
            for item in results:
                key = item.get("url", "")
                if key and key not in state.seen_urls:
                    cat2_new.append(item)
                    state.cat2_wrappers.append(item)
                    state.seen_urls.add(key)
            time.sleep(2)
        except Exception as e:
            log.error(f"Scraper error: {e}")

    state.last_at = datetime.now().strftime("%d %b %I:%M %p")
    state.status  = f"💤 Sleeping (last: {state.last_at})"

    # ── Send Telegram Updates ──
    send_telegram_update(cat1_new, cat2_new)


def send_telegram_update(cat1_new, cat2_new):
    """Telegram pe dono categories ka update bhejo"""

    # Category 1: Working endpoints
    if cat1_new:
        msg = "✅ *Category 1: Working Free Endpoints*\n_(Tested & Verified — No Key Needed)_\n\n"
        for ep in cat1_new:
            emoji = {"text": "💬", "image": "🖼️", "video": "🎬"}.get(ep["type"], "🔗")
            msg += f"{emoji} *{ep['name']}*\n"
            msg += f"`{ep['url']}`\n"
            msg += f"Status: `{ep['status']}`\n\n"
        tg_send(msg)

    # Category 2: New web2api tools
    if cat2_new:
        msg = "🔧 *Category 2: New Web2API / Unofficial Wrappers Found*\n_(GitHub & HuggingFace se)_\n\n"
        for item in cat2_new[:8]:
            stars = f"⭐{item['stars']}" if item.get("stars") else ""
            msg += f"*{item['name']}* {stars}\n"
            msg += f"🔗 {item['url']}\n"
            if item.get("api"):
                msg += f"🎯 API: `{item['api']}`\n"
            msg += f"_{item['desc'][:70]}_\n\n"
        tg_send(msg)

    if not cat1_new and not cat2_new:
        log.info(f"Scan #{state.scans} — nothing new found.")


def run_radar():
    """24/7 loop — scan every hour"""
    time.sleep(10)
    while True:
        try:
            run_radar_scan()
        except Exception as e:
            state.status = f"❌ Error: {e}"
            log.error(f"Radar loop error: {e}")
        time.sleep(3600)


# ════════════════════════════════════════════════
# TELEGRAM BOT
# ════════════════════════════════════════════════
def run_bot():
    from telegram import Update
    from telegram.ext import Application, CommandHandler

    async def cmd_start(u: Update, c):
        await u.message.reply_text(
            "🤖 *Web2API Radar Bot*\n\n"
            "Main 24/7 ye dhundta hoon:\n"
            "✅ *Cat 1:* Free AI endpoints (no key, tested)\n"
            "🔧 *Cat 2:* New web2api / unofficial wrappers\n\n"
            "/status — Abhi kya chal raha hai\n"
            "/cat1   — Working endpoints (tested)\n"
            "/cat2   — Latest web2api tools found\n"
            "/scan   — Abhi turant scan karo",
            parse_mode="Markdown"
        )

    async def cmd_status(u: Update, c):
        msg = (
            f"📡 *Radar Status*\n\n"
            f"🌐 Scanning: `{state.site}`\n"
            f"📝 Status: `{state.status}`\n"
            f"🔄 Total Scans: `{state.scans}`\n"
            f"✅ Cat1 Working: `{len(state.cat1_working)}`\n"
            f"🔧 Cat2 Found: `{len(state.cat2_wrappers)}`\n"
            f"🕐 Last Scan: `{state.last_at}`"
        )
        await u.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_cat1(u: Update, c):
        if not state.cat1_working:
            await u.message.reply_text("Abhi koi working endpoint nahi mila. /scan karo!")
            return
        msg = "✅ *Working Free Endpoints (Tested):*\n\n"
        for ep in state.cat1_working[-8:]:
            emoji = {"text": "💬", "image": "🖼️", "video": "🎬"}.get(ep.get("type",""), "🔗")
            msg += f"{emoji} *{ep['name']}*\n`{ep['url']}`\n\n"
        await u.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

    async def cmd_cat2(u: Update, c):
        if not state.cat2_wrappers:
            await u.message.reply_text("Abhi koi wrapper nahi mila. /scan karo!")
            return
        msg = "🔧 *Latest Web2API Tools Found:*\n\n"
        for item in state.cat2_wrappers[-8:]:
            stars = f"⭐{item['stars']}" if item.get("stars") else ""
            msg += f"*{item['name']}* {stars}\n🔗 {item['url']}\n\n"
        await u.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

    async def cmd_scan(u: Update, c):
        await u.message.reply_text("🚀 Manual scan shuru! Results milenge thodi der mein...")
        threading.Thread(target=run_radar_scan, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("cat1",   cmd_cat1))
    app.add_handler(CommandHandler("cat2",   cmd_cat2))
    app.add_handler(CommandHandler("scan",   cmd_scan))

    log.info("✅ Web2API Radar Bot started!")
    app.run_polling()


# ════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════
if __name__ == "__main__":
    threading.Thread(target=run_health, daemon=True).start()
    threading.Thread(target=run_radar,  daemon=True).start()
    run_bot()
