"""
TECH RADAR BOT - CONTINUOUS PROXY ROTATION EDITION
===================================================
1. Continuous Work Loop (No more 1-hour sleeping)
2. Proxy Rotation (Scrapes free proxies & rotates them)
3. Immediate Send + How to Use (Python snippet) for WORKING endpoints
4. 24-Hour File Dump for non-working/informational repos
"""

import os, time, threading, logging, json, random, io, re
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html"
}

# ════════════════════════════════════════════════
# PROXY MANAGER
# ════════════════════════════════════════════════
proxies_list = []

def refresh_proxies():
    """ProxyScrape se free proxies fetch karta hai"""
    global proxies_list
    try:
        url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all"
        r = requests.get(url, timeout=15)
        if r.ok:
            new_proxies = [f"http://{p.strip()}" for p in r.text.split("\n") if ":" in p]
            if new_proxies:
                proxies_list = new_proxies
                log.info(f"🔄 Loaded {len(proxies_list)} fresh proxies")
    except Exception as e:
        log.error(f"Proxy refresh failed: {e}")

def make_request(url, method="GET", payload=None, timeout=15):
    """Proxy rotate karke request marta hai. IP block se bachne ke liye."""
    # Try with random proxies 3 times
    for _ in range(3):
        proxy = random.choice(proxies_list) if proxies_list else None
        px_dict = {"http": proxy, "https": proxy} if proxy else None
        try:
            if method == "GET":
                r = requests.get(url, headers=HEADERS, proxies=px_dict, timeout=timeout)
            else:
                r = requests.post(url, headers=HEADERS, json=payload, proxies=px_dict, timeout=timeout)
            return r
        except:
            continue
    
    # Fallback to direct connection if proxies fail
    try:
        if method == "GET":
            return requests.get(url, headers=HEADERS, timeout=timeout)
        else:
            return requests.post(url, headers=HEADERS, json=payload, timeout=timeout)
    except:
        return None


# ════════════════════════════════════════════════
# PERSISTENT MEMORY
# ════════════════════════════════════════════════
MEMORY_FILE = "radar_memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {"seen_urls": [], "daily_junk": [], "working_apis": [], "last_dump_time": time.time()}

def save_memory():
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump({
                "seen_urls": list(state.seen_urls),
                "daily_junk": state.daily_junk,
                "working_apis": state.working_apis,
                "last_dump_time": state.last_dump_time
            }, f)
    except: pass


# ─── STATE ───
class RadarState:
    def __init__(self):
        mem = load_memory()
        self.seen_urls = set(mem.get("seen_urls", []))
        self.daily_junk = mem.get("daily_junk", [])
        self.working_apis = mem.get("working_apis", [])
        self.last_dump_time = mem.get("last_dump_time", time.time())
        self.status = "⏳ Starting continuous scan..."

state = RadarState()


# ════════════════════════════════════════════════
# TELEGRAM SENDERS
# ════════════════════════════════════════════════
def tg_send_instant(ep_name, ep_url, method, payload=None, response_sample=""):
    """Jab koi unlimited endpoint milta hai, turant 'How to use' ke sath bhejta hai"""
    
    # Generate Python Snippet
    code = f"import requests\n\nurl = '{ep_url}'\n"
    if method == "GET":
        code += f"response = requests.get(url)\nprint(response.text)"
    else:
        code += f"payload = {json.dumps(payload, indent=2)}\n"
        code += f"response = requests.post(url, json=payload)\nprint(response.json())"

    msg = (
        f"🚨 *WORKING UNLIMITED API FOUND!* 🚨\n\n"
        f"🎯 *Name:* `{ep_name}`\n"
        f"🔗 *URL:* `{ep_url}`\n\n"
        f"💻 *How to Use (Python):*\n```python\n{code}\n```\n\n"
        f"📄 *Output Sample:*\n`{response_sample[:100]}...`"
    )
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": MY_USER_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True})


def tg_send_daily_file():
    """Jo APIs test me fail hue ya sirf repos hain, unka txt file bhejo 24h me"""
    if not state.daily_junk:
        return

    content = "TECH RADAR - DAILY DUMP (Not working directly, requires manual check)\n"
    content += "="*70 + "\n\n"
    for item in state.daily_junk:
        content += f"Name: {item.get('name')}\nURL: {item.get('url')}\nDesc: {item.get('desc')}\n\n"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    files = {'document': ('daily_dump.txt', io.BytesIO(content.encode('utf-8')))}
    data = {'chat_id': MY_USER_ID, 'caption': f"📂 *24H Radar Dump*\nTotal items: {len(state.daily_junk)}\n_(Ye direct kaam nahi kar rahe, par useful tools ho sakte hain)_", 'parse_mode': 'Markdown'}
    
    try:
        requests.post(url, data=data, files=files)
        # Reset after send
        state.daily_junk = []
        state.last_dump_time = time.time()
        save_memory()
    except Exception as e:
        log.error(f"Daily dump send failed: {e}")


# ════════════════════════════════════════════════
# DEEP TESTING LOGIC
# ════════════════════════════════════════════════
def test_and_process(name, url, desc=""):
    """
    URL ko deep test karta hai. 
    Agar working API hai -> tg_send_instant
    Agar sirf repo/site hai -> add to daily_junk
    """
    if url in state.seen_urls:
        return
    state.seen_urls.add(url)
    
    # 1. Try treating it as a direct POST API (like OpenAI format)
    payload = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 10}
    r_post = make_request(url, method="POST", payload=payload, timeout=8)
    
    if r_post and r_post.status_code in [200, 201] and any(k in r_post.text.lower() for k in ["choices", "response", "hello", "generated"]):
        tg_send_instant(name, url, "POST", payload, r_post.text)
        state.working_apis.append({"name": name, "url": url, "type": "POST"})
        save_memory()
        return

    # 2. Try treating it as a GET API
    r_get = make_request(url, method="GET", timeout=8)
    if r_get and r_get.status_code == 200:
        ctype = r_get.headers.get("Content-Type", "")
        # Agar JSON api hai ya image hai
        if "application/json" in ctype or "image" in ctype:
            tg_send_instant(name, url, "GET", None, f"[{ctype}] {r_get.text[:80]}")
            state.working_apis.append({"name": name, "url": url, "type": "GET"})
            save_memory()
            return
            
    # 3. Agar API test fail hua, but GitHub repo ya site hai, toh Daily Dump me dalo
    state.daily_junk.append({"name": name, "url": url, "desc": desc[:150]})
    save_memory()


# ════════════════════════════════════════════════
# CONTINUOUS SCRAPERS
# ════════════════════════════════════════════════
QUERIES = [
    "claude web2api", "chatgpt proxy free", "gpt4 unofficial api", "free llm api no key",
    "reverse engineered api ai", "midjourney free wrapper", "runwayml unofficial",
    "kling video api proxy", "luma ai free endpoint", "suno ai unofficial api",
    "openrouter proxy", "huggingface api proxy", "gemini web2api",
    "unlimited ai api free", "no credit video api", "free audio model api",
    "text to video api no limit", "unlimited video generation api", "free chat model api unlimited"
]

def scan_github():
    state.status = "🔍 Scanning GitHub..."
    q = random.choice(QUERIES)
    api_url = f"https://api.github.com/search/repositories?q={q}&sort=updated&per_page=10"
    r = make_request(api_url, method="GET")
    if r and r.ok:
        for item in r.json().get("items", []):
            test_and_process(item["full_name"], item["html_url"], item.get("description", ""))

def scan_huggingface():
    state.status = "🔍 Scanning HuggingFace Spaces..."
    r = make_request("https://huggingface.co/api/spaces?sort=trending&limit=20")
    if r and r.ok:
        for item in r.json():
            sid = item.get("id", "")
            if item.get("sdk") in ["gradio", "streamlit"]:
                api_url = f"https://{sid.replace('/', '-').lower()}.hf.space/api/predict"
                test_and_process(sid, api_url, "HuggingFace Space API")


# ════════════════════════════════════════════════
# MAIN CONTINUOUS LOOP
# ════════════════════════════════════════════════
def continuous_radar():
    time.sleep(5)
    refresh_proxies()
    proxy_refresh_time = time.time()
    
    while True:
        try:
            # 1. 24h Daily Dump Check (86400 seconds)
            if time.time() - state.last_dump_time > 86400:
                tg_send_daily_file()
            
            # 2. Refresh proxies every 1 hour
            if time.time() - proxy_refresh_time > 3600:
                refresh_proxies()
                proxy_refresh_time = time.time()

            # 3. Scrape and Test
            scan_github()
            time.sleep(random.randint(10, 20)) # Random delay between 10-20s
            
            scan_huggingface()
            time.sleep(random.randint(10, 20))

        except Exception as e:
            log.error(f"Loop error: {e}")
            time.sleep(30)


# ════════════════════════════════════════════════
# HEALTH & BOT 
# ════════════════════════════════════════════════
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Radar Continuous - OK")
    def log_message(self, *a): pass

def run_telegram_bot():
    from telegram import Update
    from telegram.ext import Application, CommandHandler

    async def cmd_start(u: Update, c):
        await u.message.reply_text(
            "🤖 *Tech Radar Bot is running 24/7!*\n\n"
            "/status - Check current radar state\n"
            "/working - View recent working unlimited APIs\n"
            "/queue - View recent items in daily dump queue\n"
            "/dump - Force send the daily dump right now",
            parse_mode="Markdown"
        )

    async def cmd_status(u: Update, c):
        msg = (
            f"📡 *Radar Status*\n\n"
            f"📝 Status: `{state.status}`\n"
            f"🔄 Proxies Loaded: `{len(proxies_list)}`\n"
            f"✅ Working APIs Found: `{len(state.working_apis)}`\n"
            f"🗑️ Daily Junk Items: `{len(state.daily_junk)}`\n"
            f"🌐 Total Seen URLs: `{len(state.seen_urls)}`\n"
        )
        await u.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_working(u: Update, c):
        if not state.working_apis:
            await u.message.reply_text("Abhi tak koi 'Working API' nahi mili hai.")
            return
        msg = "✅ *Recent Working APIs (Tested):*\n\n"
        for item in state.working_apis[-10:]:
            msg += f"*{item['name']}* ({item['type']})\n🔗 `{item['url']}`\n\n"
        await u.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

    async def cmd_queue(u: Update, c):
        if not state.daily_junk:
            await u.message.reply_text("Dump queue abhi khali hai.")
            return
        msg = f"🗑️ *Items in Queue for Next Dump ({len(state.daily_junk)} total):*\n\n"
        for item in state.daily_junk[-10:]:
            msg += f"*{item['name']}*\n🔗 `{item['url']}`\n\n"
        await u.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

    async def cmd_dump(u: Update, c):
        if not state.daily_junk:
            await u.message.reply_text("Dump karne ke liye kuch nahi hai.")
            return
        await u.message.reply_text("📂 Generating dump file manually...")
        tg_send_daily_file()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("working", cmd_working))
    app.add_handler(CommandHandler("queue", cmd_queue))
    app.add_handler(CommandHandler("dump", cmd_dump))
    
    log.info("✅ Telegram Polling Started (New Token Mode)!")
    app.run_polling()


if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(("0.0.0.0", HEALTH_PORT), Health).serve_forever(), daemon=True).start()
    
    log.info("🚀 Starting Continuous Radar in background...")
    threading.Thread(target=continuous_radar, daemon=True).start()
    
    # Run Telegram bot in the main thread so it can listen to /status commands
    run_telegram_bot()
