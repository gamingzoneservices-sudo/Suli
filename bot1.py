import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import random
import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote_plus, urlparse
import warnings
import json

warnings.filterwarnings("ignore", category=DeprecationWarning)

# ==========================================
# 1. الإعدادات الأساسية وقاعدة البيانات
# ==========================================

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True
INTENTS.voice_states = True
INTENTS.guilds = True

BOT = commands.Bot(command_prefix="!", intents=INTENTS)
DB_NAME = "economy_system.db"
admin_dashboard_thread = None
admin_dashboard_port_running = None

# تفعيل WAL mode لتحسين أداء قاعدة البيانات وتجنب مشكلة القفل
def init_database():
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA cache_size=10000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.close()

init_database()

# معرفات الأيقونات المخصصة والمحدثة
EMOJI_BAL = "<:bal:1515329348666789964>"
EMOJI_INV = "<:inv:1515329298448253139>"
EMOJI_CASE = "<:case:1515329271118430468>"
EMOJI_SHOP = "<:shop:1515329325849903255>"
EMOJI_TRADE = "<:trade:1515329146803195904>"
EMOJI_ESPRESSO = "<:espresso:1515329180131262625>"
EMOJI_FLASH = "<:flash:1515329215216484374>"
EMOJI_LB = "<:lb:1515329115174076608>"
EMOJI_COIN = "<:coin:1515333202787700930>"

# أيقونات الصف الثالث المحدثة
EMOJI_LOTTERY = "<:lottery:1515378161901109381>"
EMOJI_GHOST = "<:ghost:1515378133967306823>"
EMOJI_INFO = "<:info:1515378100056100915>"

# رتب المتجر الجديدة
ROLE_SMUGGLER_ID = 1515442831202717706
ROLE_KAMIKAZE_ID = 1515444835262140516
ROLE_JOKER_ID = 1515445676975067297

# آيدي الشات العام لرسائل الشبح
GHOST_TARGET_CHANNEL_ID = 1257909845382664212

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 1000,
        flashbang_count INTEGER DEFAULT 0,
        shield_count INTEGER DEFAULT 0,
        espresso_count INTEGER DEFAULT 0,
        ticket_count INTEGER DEFAULT 0,
        ghost_count INTEGER DEFAULT 0,
        siren_count INTEGER DEFAULT 0,
        mine_count INTEGER DEFAULT 0,
        kamikaze_uses INTEGER DEFAULT 0,
        joker_trolls INTEGER DEFAULT 0,
        shop_banned_until TEXT DEFAULT NULL,
        shop_ban_reason TEXT DEFAULT NULL
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS active_effects (
        user_id INTEGER,
        guild_id INTEGER, 
        effect_type TEXT, 
        expire_time TEXT,
        PRIMARY KEY (user_id, effect_type)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS joker_targets (
        user_id INTEGER PRIMARY KEY,
        guild_id INTEGER,
        trolled_name TEXT,
        expire_time TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS steam_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_name TEXT,
        key_code TEXT UNIQUE,
        used INTEGER DEFAULT 0
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value_str TEXT,
        value_int INTEGER
    )''')
    
    cursor.execute('''DROP TABLE IF EXISTS voice_tracking''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS voice_tracking (
        user_id INTEGER PRIMARY KEY,
        guild_id INTEGER,
        channel_id INTEGER,
        join_timestamp REAL,
        last_reward_timestamp REAL DEFAULT 0
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS blacklisted_channels (
        channel_id INTEGER PRIMARY KEY
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS logs_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action_type TEXT,
        details TEXT,
        timestamp TEXT
    )''')

    default_config = [
        ('price_flashbang', None, 2500),
        ('price_shield', None, 2000),
        ('price_espresso', None, 3500),
        ('price_ticket', None, 500),
        ('price_ghost', None, 650),
        ('price_case', None, 1500),
        ('price_smuggle_role', None, 1500),
        ('price_kamikaze_role', None, 700),
        ('price_joker_role', None, 950),
        ('lang_default', None, 1), 
        ('dashboard_channel', None, 0),
        ('log_channel', None, 0),
        ('dashboard_embed_img', "https://shorturl.at/jxSRx", None),
        ('enable_admin_dashboard', None, 0),
        ('admin_dashboard_port', None, 8080),
        ('admin_dashboard_token', "", None),
        ('info_text_ar', "### 📋 دليل ونظام اقتصاد Blade X المتكامل:\n\n**📊 الحساب والرصيد الأساسي**\n- تحصل دائماً على **1000 BLZ** عند الانضمام.\n- يمكنك كسب العملات عبر التفاعل في الدردشة، نشر الوسائط، والتواجد الصوتي.\n\n**💹 نظام التسعيرات والمكسب**\n- قضاء ساعة كاملة في الصوت (مع آخر) = **200 BLZ**\n- إرفاق وسائط (صور/فيديو) = **50 BLZ**\n- رسالة نصية = **30 BLZ**\n- تفاعل (Reaction) = **10 BLZ**\n\n**🎁 شرح الأيتمات والأدوات**\n- 💥 **فلاش بانج (Flashbang):** يقوم بصمت صوتي ووقت آوت مؤقت للمستخدم المستهدف.\n- 🛡️ **درع (Shield):** يعترض ويحجب تأثيرات الفلاش لتجنب الصمت الصوتي.\n- ☕ **إسبريسو (Espresso):** يمنح مضاعف أرباح X2 لفترة محددة.\n- 🎟️ **تذكرة الحظ (Lucky Ticket):** تتيح فرصة للفوز بمبلغ عملات (مثلاً 1200 BLZ).\n- 👻 **الشبح (Ghost):** يرسل رسالة أمبد مجهولة المصدر إلى القناة العامة.\n- 📦 **صندوق الحظ (Lucky Box):** صندوق عشوائي يحتوي على احتمال الحصول على أيتمات نادرة، خصومات للـSmuggler، عملات نقدية، أو مفاجآت خاصة.\n\n**🤠 نظام العم شمشون (Uncle Samson)**\n- ميكانيك خاص داخل صندوق الحظ بنسبة ظهور تقريبية **15%**.\n- يطلب كلمة أو سؤال محرج من قائمة مكوّنة من 50 سؤالاً بالعربية والإنجليزية.\n- أوضاع العم: Angry (خصم 1000 BLZ), Normal (خصم 500 BLZ), Happy (لا توجد عقوبة).\n- يمكنك قبول أو إلغاء العقوبة حسب مزاج العم؛ عند الإجابة بشكل مقبول تحصل على مكافأة عشوائية من المتجر.\n\n**🎁 هدية عيد الميلاد (B-day Gift)**\n- زر خاص في لوحة التحكم لإرسال هدايا عيد الميلاد للأصدقاء.\n- يمكنك تحديد المستلم، المبلغ، ورسالة اختيارية.\n- الحد الأدنى للإرسال: **1500 BLZ** (1000 للمستلم + 500 رسوم).", None),
        ('info_text_en', "### 📋 Economy & Control Panel Manual:\n\n**Currency & Base Wallet System**\n- Every user receives **1000 BLZ** upon first entry.\n- Earn coins organically through chat activity, attaching media, and voice presence.\n\n**📊 Pricing & Earning System**\n- 1 full hour in voice (with others) = **200 BLZ**\n- Attaching media (videos/images) = **50 BLZ**\n- Message = **30 BLZ**\n- Reaction = **10 BLZ**\n\n**🎁 Items & Special Roles Guide**\n- 💥 **Flashbang:** Timeouts and voice-mutes a targeted member.\n- 🛡️ **Shield:** Intercepts and blocks incoming flashbang attacks to protect the holder.\n- ☕ **Espresso:** Grants an instant **X2** multiplier on earnings for a limited period.\n- 🎟️ **Lucky Ticket:** Chance to win a coin prize (e.g., **1200 BLZ**).\n- 👻 **Ghost:** Broadcasts an anonymous embed message to general chat.\n- 📦 **Lucky Box:** Random case with chances to award rare items, shop discounts, instant coin rewards, or special surprises.\n\n**🤠 Uncle Samson System**\n- Special Lucky Box mechanic with ~**15%** appearance rate.\n- Asks an embarrassing question chosen from a list of 50 (Arabic & English).\n- Modes: Angry (1000 penalty), Normal (500 penalty), Happy (no penalty).\n- Answer acceptably to receive a random shop reward.\n\n**🎁 B-day Gift**\n- Control-panel button to send birthday gifts to friends.\n- Specify recipient, amount, and an optional message.\n- Minimum sending amount is **1500 BLZ** (1000 to recipient + 500 tax).", None),
        ('lucky_common', None, 50),
        ('lucky_rare', None, 30),
        ('lucky_uncle', None, 15),
        ('lucky_legendary', None, 5),
    ]
    for key, v_str, v_int in default_config:
        cursor.execute("INSERT OR IGNORE INTO config (key, value_str, value_int) VALUES (?, ?, ?)", (key, v_str, v_int))
        
    conn.commit()
    conn.close()

# Add new security columns if they are missing from existing DB schema
try:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE users ADD COLUMN economy_banned_until TEXT DEFAULT NULL")
    cursor.execute("ALTER TABLE users ADD COLUMN economy_ban_reason TEXT DEFAULT NULL")
    conn.commit()
    conn.close()
except sqlite3.OperationalError:
    # Column already exists or table schema already in place
    pass

init_db()

# ==========================================
# 2. الترجمات والوظائف المساعدة
# ==========================================

LOCALIZATION = {
    "ar": {
        "no_money": f"❌ رصيدك غير كافٍ! تحتاج إلى {{}} BLZ {EMOJI_COIN}.",
        "buy_success": f"✅ تم شراء {{}} بنجاح! تم خصم {{}} BLZ {EMOJI_COIN}.",
        "case_win_common": f"📦 فتحت صندوقاً وربحت حزمة عملات شائعة بقيمة {{}} BLZ {EMOJI_COIN}!",
        "case_win_item": "📦 أسطوري/نادر! فتحت صندوقاً ووجدت بداخله: **{}**!",
        "case_win_steam": "🎉 الجائزة الكبرى الأسطورية! لقد ربحت مفتاح لعبة Steam حقيقي للعبة {}! تم إرساله لخاصك 🔑",
        "no_keys": f"📦 لقد ربحت الجائزة الكبرى ولكن نفذت مفاتيح Steam من المخزن! تم تعويضك بـ 5000 BLZ {EMOJI_COIN}.",
        "flash_shielded": "🛡️ حاول أحدهم إلقاء فلاش عليك، ولكن تم صد الهجوم بنجاح باستهلاك الدرع الخاص بك!",
        "flash_success": "💥 تم إلقاء فلاش بانج على {} بنجاح وكتمه لمدة دقيقتين!",
        "flash_self": "❌ لا يمكنك إلقاء فلاش على نفسك!",
        "no_item": "❌ أنت لا تملك هذا الأيتم في حقيبتك حالياً!",
        "espresso_active": "☕ شربت كوب إسبريسو! حصلت على رتبة Active Barista ومضاعف نقاط X2 لمدة ساعتين.",
        "bal_msg": f"💰 رصيدك الحالي هو: **{{}} BLZ {EMOJI_COIN}**",
        "inv_msg": "💼 **حقيبتك الحالية:**\n"
                    "- 💥 فلاش: {}\n- 🛡️ دروع حماية: {}\n- ☕ كوب إسبريسو: {}\n"
                    f"- 🎰 تذاكر اليانصيب: {{}}\n- 👻 الشبح الخفي: {{}}",
        "trade_modal_title": "طلب تداول الأيتمات",
        "user_name_label": "اسم المستخدم المراد التداول معه",
        "item_name_label": "الأيتم: flash/shield/espresso/ticket/ghost",
        "trade_invalid_user": "❌ لم يتم العثور على هذا العضو في السيرفر!",
        "trade_sent_dm": "✅ تم إرسال طلب التداول إلى الخاص الخاص بالعضو بنجاح!",
        "shop_banned": "❌ أنت محظور مؤقتاً من استخدام المتجر! السبب: {}",
        "lottery_win": "🎰 **[تذكرة الحظ]:** مبروك! فزت في السحب الفوري وتضاعفت تذكرتك إلى **1200 BLZ** {EMOJI_COIN}!",
        "lottery_lose": "🎰 للأسف خسرت السحب الفوري وذهبت الـ 500 BLZ أدراج الرياح!",
        "rate_limited_generic": "⏳ رجاءً انتظر {} ثانية قبل إعادة استخدام هذه الميزة."
    },
    "en": {
        "no_money": f"❌ Insufficient balance! You need {{}} BLZ {EMOJI_COIN}.",
        "buy_success": f"✅ Successfully bought {{}}! Deducted {{}} BLZ {EMOJI_COIN}.",
        "case_win_common": f"📦 You opened a case and found a common cash pack containing {{}} BLZ {EMOJI_COIN}!",
        "case_win_item": "📦 Rare/Epic! You opened a case and found: **{}**!",
        "case_win_steam": "🎉 JACKPOT! You won a real Steam Game Key for {}! Check your DMs 🔑",
        "no_keys": f"📦 You won the jackpot but Steam keys are out of stock! Compensated with 5000 BLZ {EMOJI_COIN}.",
        "flash_shielded": "🛡️ Someone tried to flash you, but your Shield absorbed the hit successfully!",
        "flash_success": "💥 Successfully flashed {} for 2 minutes!",
        "flash_self": "❌ You cannot flashbang yourself!",
        "no_item": "❌ You don't own this item in your inventory!",
        "espresso_active": "☕ You drank an Espresso Shot! Granted Active Barista role & X2 Multiplier for 2 hours.",
        "bal_msg": f"💰 Your current balance is: **{{}} BLZ {EMOJI_COIN}**",
        "inv_msg": "💼 **Your Inventory:**\n"
                    "- 💥 Flashbang: {}\n- 🛡️ Shield: {}\n- ☕ Espresso Shot: {}\n"
                    "- 🎰 Lucky Tickets: {}\n- 👻 Ghost Whisper: {}",
        "trade_modal_title": "Item Trade Request",
        "user_name_label": "Target Username",
        "item_name_label": "Item: flash/shield/espresso/ticket/ghost",
        "trade_invalid_user": "❌ Target user not found in this guild!",
        "trade_sent_dm": "✅ Trade request successfully dispatched to target user's DMs!",
        "shop_banned": "❌ You are temporarily banned from using the shop! Reason: {}",
        "lottery_win": "🎰 **[Lucky Ticket]:** Congratulations! You won the instant draw and received **1200 BLZ** {EMOJI_COIN}!",
        "lottery_lose": "🎰 Unfortunately you lost the instant draw and the 500 BLZ is gone!",
        "rate_limited_generic": "⏳ Please wait {} seconds before using this feature again."
    }
}

def get_lang(guild_id=None):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("SELECT value_int FROM config WHERE key='lang_default'")
        res = cursor.fetchone()
        conn.close()
        return "ar" if (res and res[0] == 1) else "en"
    except:
        return "en"

def get_price(item_key):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("SELECT value_int FROM config WHERE key=?", (f"price_{item_key}",))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else 1000
    except:
        return 1000

def get_config_int(key_name):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("SELECT value_int FROM config WHERE key=?", (key_name,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else 0
    except:
        return 0

def get_config_str(key_name):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("SELECT value_str FROM config WHERE key=?", (key_name,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else ""
    except:
        return ""


def set_config_str(key_name, value):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO config (key, value_str, value_int) VALUES (?, ?, NULL)", (key_name, value))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Config write error: {e}")


def set_config_int(key_name, value):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO config (key, value_str, value_int) VALUES (?, NULL, ?)", (key_name, value))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Config write error: {e}")


db_lock = asyncio.Lock()

def update_balance(user_id, amount):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        cursor.execute("UPDATE users SET balance = MAX(0, balance + ?) WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()
    except sqlite3.OperationalError as e:
        print(f"Database error in update_balance: {e}")

def log_action(user_id, action_type, details):
    """Schedule a non-blocking log write to the DB.
    This schedules an async background task so callers don't block the event loop.
    """
    try:
        asyncio.create_task(_async_log_action(user_id, action_type, details))
    except RuntimeError:
        # If we're not in an event loop, fallback to synchronous write in a thread
        try:
            _write_log_to_db(user_id, action_type, details)
        except Exception as e:
            print(f"Fallback log failed: {e}")


async def _async_log_action(user_id, action_type, details):
    # Retry loop with backoff to avoid OperationalError due to locking
    for attempt in range(6):
        try:
            await asyncio.to_thread(_write_log_to_db, user_id, action_type, details)
            break
        except sqlite3.OperationalError as e:
            # short backoff
            await asyncio.sleep(0.05 * (attempt + 1))
    else:
        print(f"Database error in log_action after retries: DB busy or locked for action {action_type}")


def _write_log_to_db(user_id, action_type, details):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    cursor = conn.cursor()
    # Store timestamp in CEST for logs as requested (Europe/Berlin)
    now_utc = datetime.now(timezone.utc)
    try:
        now_cest = now_utc.astimezone(ZoneInfo("Europe/Berlin")).strftime('%Y-%m-%d %H:%M:%S %Z')
    except Exception:
        # fallback to UTC string if zoneinfo unavailable
        now_cest = now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')

    # Format details: include user mention and timestamp for DB and channel
    user_tag = f"<@{user_id}>"
    formatted_details = f"{user_tag} | {now_cest} | {details}"

    cursor.execute("INSERT INTO logs_history (user_id, action_type, details, timestamp) VALUES (?, ?, ?, ?)",
                   (user_id, action_type, formatted_details, now_cest))
    conn.commit()
    conn.close()

    log_channel_id = get_config_int("log_channel")
    if log_channel_id:
        try:
            # Build a neat embed for logs
            embed = discord.Embed(title=f"📝 [LOG - {action_type}]", color=discord.Color.dark_blue())
            embed.add_field(name="User", value=user_tag, inline=True)
            embed.add_field(name="Time (CEST)", value=now_cest, inline=True)
            # Keep details readable and preserve language
            embed.add_field(name="Details", value=details if len(details) <= 1000 else details[:997] + '...', inline=False)
            # dispatch_log_msg is async; schedule it in event loop if available
            asyncio.get_running_loop().create_task(dispatch_log_msg(log_channel_id, embed=embed))
        except RuntimeError:
            try:
                asyncio.run_coroutine_threadsafe(dispatch_log_msg(log_channel_id, embed=embed), BOT.loop)
            except:
                pass

async def dispatch_log_msg(channel_id, text=None, embed: discord.Embed=None):
    try:
        channel = BOT.get_channel(channel_id) or await BOT.fetch_channel(channel_id)
        if channel:
            if embed is not None:
                await channel.send(embed=embed)
            elif text is not None:
                await channel.send(text)
    except: pass

async def send_temporary_dm(user, embed=None, content=None, view=None, duration=300):
    try:
        msg = await user.send(content=content, embed=embed, view=view)
        async def delayed_delete():
            await asyncio.sleep(duration)
            try: await msg.delete()
            except: pass
        BOT.loop.create_task(delayed_delete())
        return msg
    except: return None

def is_shop_banned(user_id):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("SELECT shop_banned_until, shop_ban_reason FROM users WHERE user_id=?", (user_id,))
        res = cursor.fetchone()
        conn.close()
        
        if not res or not res[0]:
            return None
        
        try:
            ban_until = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
            if datetime.now(timezone.utc).replace(tzinfo=None) < ban_until:
                return res[1]  # Return ban reason
        except: pass
        
        # Clear expired ban
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET shop_banned_until = NULL, shop_ban_reason = NULL WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        return None
    except:
        return None


def is_economy_banned(user_id):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("SELECT economy_banned_until, economy_ban_reason FROM users WHERE user_id=?", (user_id,))
        res = cursor.fetchone()
        conn.close()
        if not res or not res[0]:
            return None
        try:
            ban_until = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
            if datetime.now(timezone.utc).replace(tzinfo=None) < ban_until:
                return res[1]
        except: pass
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET economy_banned_until = NULL, economy_ban_reason = NULL WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        return None
    except:
        return None

# ==========================================
# دالة إنشاء صورة التهنئة (B-day Gift)
# ==========================================

async def create_birthday_gift_image(member, amount, message):
    """
    إنشاء صورة تهنئة عيد الميلاد (نسخة مبسطة بدون PIL)
    """
    # جلب رابط الصورة من قاعدة البيانات أو استخدام الرابط الافتراضي
    base_image_url = get_config_str("bday_gift_image")
    if not base_image_url:
        base_image_url = "https://cdn.discordapp.com/attachments/1515015394853785662/1515888443056590968/Beige_and_Grey_Modern_Minimalist_Student_ID_Card.png?ex=6a30a4a0&is=6a2f5320&hm=3a6251ef02d67841d8d1d91fca25bbf69060e078579630cfa03c03baa9c66a5a&"
    
    # ملاحظة: لمعالجة الصور المتقدمة (توسيط البروفايل والاسم)، 
    # يجب تثبيت مكتبة Pillow: pip install Pillow
    # حالياً نرجع رابط الصورة الأصلي
    return base_image_url

# ==========================================
# نظام العم شمشون (أسئلة محرجة)
# ==========================================

UNCLE_SHAMSHON_QUESTIONS = [
    {"ar": "ما هو أكثر شيء محرج حدث لك في المدرسة؟", "en": "What's the most embarrassing thing that happened to you in school?"},
    {"ar": "هل سبق لك أن ناديت شخصاً باسم خاطئ أمام الجميع؟ ماذا حدث؟", "en": "Have you ever called someone by the wrong name in front of everyone? What happened?"},
    {"ar": "ما هو أغرب حلم رأيته؟", "en": "What's the weirdest dream you've ever had?"},
    {"ar": "هل سبق لك أن تقيأت في مكان عام؟ أين؟", "en": "Have you ever thrown up in a public place? Where?"},
    {"ar": "ما هو أكثر شيء سخيف فعلته وأنت طفل؟", "en": "What's the silliest thing you did as a child?"},
    {"ar": "هل سبق لك أن نطقت كلمة خاطئة في خطاب رسمي؟ ما هي؟", "en": "Have you ever said the wrong word during a formal speech? What was it?"},
    {"ar": "ما هو أكثر شيء حرج في هاتفك الآن؟", "en": "What's the most embarrassing thing on your phone right now?"},
    {"ar": "هل سبق لك أن وقعت أمام شخص تحبه؟", "en": "Have you ever fallen in front of someone you like?"},
    {"ar": "ما هو أغنى كذبة قلتها لوالديك؟", "en": "What's the biggest lie you ever told your parents?"},
    {"ar": "هل سبق لك أن سرقت شيئاً صغيراً؟ ماذا؟", "en": "Have you ever stolen something small? What?"},
    {"ar": "ما هو أكثر شيء محرج في تاريخ البحث لديك؟", "en": "What's the most embarrassing thing in your browser history?"},
    {"ar": "هل سبق لك أن أرسلت رسالة للشخص الخطأ؟ ماذا كانت؟", "en": "Have you ever sent a message to the wrong person? What was it?"},
    {"ar": "ما هو أغرب عادة لديك؟", "en": "What's your weirdest habit?"},
    {"ar": "هل سبق لك أن نطقت باسم حبيبك السابق بالخطأ؟", "en": "Have you ever accidentally called your ex's name?"},
    {"ar": "ما هو أكثر شيء سخيف اشتريته؟", "en": "What's the silliest thing you've ever bought?"},
    {"ar": "هل سبق لك أن بكيت في فيلم؟ أي فيلم؟", "en": "Have you ever cried during a movie? Which movie?"},
    {"ar": "ما هو أكثر شيء محرج قاله لك شخص؟", "en": "What's the most embarrassing thing someone has said to you?"},
    {"ar": "هل سبق لك أن ناديت معلمك بأبي/أمي؟", "en": "Have you ever called your teacher mom/dad?"},
    {"ar": "ما هو أغلى شيء كسرته؟", "en": "What's the most expensive thing you've broken?"},
    {"ar": "هل سبق لك أن أكلت شيئاً من الأرض؟", "en": "Have you ever eaten food off the ground?"},
    {"ar": "ما هو أكثر شيء محرج في صورك القديمة؟", "en": "What's the most embarrassing thing in your old photos?"},
    {"ar": "هل سبق لك أن نسيت اسم شخص تعرفه جيداً؟", "en": "Have you ever forgotten the name of someone you know well?"},
    {"ar": "ما هو أغرب شيء فعلته وأنت نائم؟", "en": "What's the weirdest thing you've done while sleeping?"},
    {"ar": "هل سبق لك أن ارتديت ملابس من الداخل للخارج؟", "en": "Have you ever worn your underwear inside out?"},
    {"ar": "ما هو أكثر شيء سخيف قلته في مقابلة عمل؟", "en": "What's the silliest thing you've said in a job interview?"},
    {"ar": "هل سبق لك أن شربت من كوب شخص آخر دون علمه؟", "en": "Have you ever drunk from someone else's cup without them knowing?"},
    {"ar": "ما هو أغنى سر تخفيه عن أصدقائك؟", "en": "What's the biggest secret you're hiding from your friends?"},
    {"ar": "هل سبق لك أن أرسلت صورة للشخص الخطأ؟", "en": "Have you ever sent a photo to the wrong person?"},
    {"ar": "ما هو أكثر شيء محرج في حسابات التواصل الاجتماعي الخاصة بك؟", "en": "What's the most embarrassing thing on your social media?"},
    {"ar": "هل سبق لك أن نطقت باسم حيوانك الأليف في مكان عام؟", "en": "Have you ever called your pet's name in public?"},
    {"ar": "ما هو أغرب شيء فعلته لتنال إعجاب شخص؟", "en": "What's the weirdest thing you've done to impress someone?"},
    {"ar": "هل سبق لك أن تظاهرت بأنك مريض؟", "en": "Have you ever pretended to be sick?"},
    {"ar": "ما هو أكثر شيء سخيف فعلته في مطعم؟", "en": "What's the silliest thing you've done in a restaurant?"},
    {"ar": "هل سبق لك أن رقصت وحدك في غرفتك؟", "en": "Have you ever danced alone in your room?"},
    {"ar": "ما هو أغلى شيء خسرته؟", "en": "What's the most expensive thing you've lost?"},
    {"ar": "هل سبق لك أن قمت بشيء محرج في الحمام العام؟", "en": "Have you ever done something embarrassing in a public restroom?"},
    {"ar": "ما هو أكثر شيء محرج قاله لك طبيب؟", "en": "What's the most embarrassing thing a doctor has said to you?"},
    {"ar": "هل سبق لك أن ارتديت ملابس لا تناسب الموسم؟", "en": "Have you ever worn clothes that don't fit the season?"},
    {"ar": "ما هو أغرب شيء فعلته لتهرب من شيء؟", "en": "What's the weirdest thing you've done to avoid something?"},
    {"ar": "هل سبق لك أن أكلت طعاماً غير مطبوخ؟", "en": "Have you ever eaten raw food?"},
    {"ar": "ما هو أكثر شيء سخيف قلته لشخص تحبه؟", "en": "What's the silliest thing you've said to someone you like?"},
    {"ar": "هل سبق لك أن نسيت موعداً مهماً؟", "en": "Have you ever forgotten an important appointment?"},
    {"ar": "ما هو أغلى شيء سرقته؟", "en": "What's the most expensive thing you've stolen?"},
    {"ar": "هل سبق لك أن شتمت شخصاً بالخطأ؟", "en": "Have you ever insulted someone by mistake?"},
    {"ar": "ما هو أكثر شيء محرج في رسائلك الخاصة؟", "en": "What's the most embarrassing thing in your private messages?"},
    {"ar": "هل سبق لك أن فعلت شيئاً محرجاً أمام جيرانك؟", "en": "Have you ever done something embarrassing in front of your neighbors?"},
    {"ar": "ما هو أغنى شيء تخفيه عن عائلتك؟", "en": "What's the biggest secret you're hiding from your family?"},
    {"ar": "هل سبق لك أن قمت بشيء محرج في العمل؟", "en": "Have you ever done something embarrassing at work?"},
    {"ar": "ما هو أكثر شيء سخيف فعلته في المدرسة؟", "en": "What's the silliest thing you've done in school?"}
]

# ==========================================
# 3. الواجهات ونظام التداول والأدوات المحدثة
# ==========================================

class InfoExplanationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="العربية", style=discord.ButtonStyle.primary, emoji="🇸🇦")
    async def explanation_ar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=" # 📖 دليل ونظام اقتصاد السيرفر المتكامل",
            description=(
                "## **نظام العملات والحساب الرئيسي**\n"
                f"• تحصل تلقائياً على **1000 عملة** عند الانضمام {EMOJI_COIN}.\n"
                "• يُمكنك كسب العملات عبر التفاعل بالشات والميديا، والتواجد الصوتي الفعال.\n\n"
                "## **📊 نظام التسعيرات والكسب**\n"
                f"• قضاء ساعة كاملة بالسيرفر (مع شخص آخر) = **200 BLZ** {EMOJI_COIN}\n"
                f"• إرفاق وسائط (فيديوهات، صور) = **50 BLZ** {EMOJI_COIN}\n"
                f"• رسالة = **30 BLZ** {EMOJI_COIN}\n"
                f"• رياكشن = **10 BLZ** {EMOJI_COIN}\n\n"
                "## **شرح وظائف الأيتمات والأدوات بالأيقونات**\n"
                "• 💥 **الفلاش بانج (Flashbang):**حجب صوتي وكتم مؤقت للضحية المستهدفة لمدة دقيقتين.\n"
                "• 🛡️ **الدرع (Shield):** الحامي التلقائي لصد وتفادي ضربات الفلاش.\n"
                "• ☕ **الإسبريسو (Espresso):** لتفعيل مضاعف نقاط X2 المالي.\n"
                "• 🎰 **اليانصيب (Lottery):** شراء تذكرة حظ تمنحك سحباً فورياً للربح المضاعف أو الخسارة.\n"
                "• 👻 **الشبح الخفي (Ghost):** يتيح لك إرسال رسائل غامضة مجهولة المصدر بالكامل تلقائياً للشات العام.\n\n"
                "## **🕵️ الرتب الخاصة والجديدة في المتجر**\n"
                "• **تاجر السوق السوداء:** تفتح لك رومات سرية لبيع أغراضك كاش أو الشراء بخصم 30% عالي (`!smuggle-buy` / `!smuggle-sell`).\n"
                "• **المفجّر (Kamikaze):** تعطيك القدرة لمرة واحدة لتفجير وطرد الكل من الروم الصوتي بلمشة (`!explode`).\n"
                "• **الملك المشاغب (Joker):** تمنحك القدرة على تغيير أسماء الضحايا لأسماء مضحكة رغماً عنهم لـ 4 ساعات (`!troll`).\n\n"
                "## **🎭 العم شمشون (Uncle Samson)**\n"
                "• نظام خاص في صندوق الحظ (Lucky Box) بنسبة 15% للظهور.\n"
                "• يطرح عليك سؤالاً محرجاً من قائمة 50 سؤالاً بالعربي والإنجليزي.\n"
                "• لديك 3 حالات للعم: عصبي (خصم 1000)، عادي (خصم 500)، سعيد (بدون خصم).\n"
                "• يمكنك الإجابة أو الإلغاء مع خصم حسب حالة العم.\n"
                "• إذا أجبت بشكل مقبول، ستحصل على جائزة عشوائية من المتجر.\n\n"

                "## **صندوق الحظ📦**\n"
                "• **صندوق الحظ فرصتك للحصول على الجائزة الكبرى!.**\n"
                "• **محتوى الصندوق كالأتي:** عملات, أيتمات المعروضة بالمتجر (باستثناء الرولات), العم شمشون, كود تفعيل لعبة على ستيم.\n"

                "## **🎁 هدية عيد الميلاد (B-day Gift)**\n"
                "• زر خاص في لوحة التحكم لإرسال هدايا عيد الميلاد للأصدقاء.\n"
                "• يمكنك تحديد المستلم، المبلغ، ورسالة اختيارية.\n"
                "• الحد الأدنى للإرسال 1500 BLZ (1000 للمستلم + 500 ضريبة).\n"
                "• يرسل البوت صورة تهنئة في DM للمستلم مع تفاصيل الهدية."
            ),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="English", style=discord.ButtonStyle.secondary, emoji="🇺🇸")
    async def explanation_en(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="# 📖 Economy & Control Panel Manual",
            description=(
                "## **Currency & Base Wallet System**\n"
                f"• Every user receives **1000 credits** upon first entry {EMOJI_COIN}.\n"
                "• Earn coins organically through chat activity, text media, and voice channel presence.\n\n"
                "## **📊 Pricing & Earning System**\n"
                f"• Spending 1 full hour in voice (with others) = **200 BLZ** {EMOJI_COIN}\n"
                f"• Attaching media (videos, images) = **50 BLZ** {EMOJI_COIN}\n"
                f"• Message = **30 BLZ** {EMOJI_COIN}\n"
                f"• Reaction = **10 BLZ** {EMOJI_COIN}\n\n"
                "## **Items & Special Roles Guide**\n"
                "• 💥 **Flashbang:** Used to timeout and voice mute a targeted text server member.\n"
                "• 🛡️ **Shield:** Automatically intercepts and shatters incoming flashbang attacks safely.\n"
                "• ☕ **Espresso Shot:** Grants an instant X2 multiplier on all earnings.\n"
                "• 👻 **Ghost Whisper:** Broadcasts an absolute anonymous text embed message directly to general chat.\n"
                "• 🕵️ **The Smuggler:** Unlocks hidden black market rooms with 30% buy discounts & instant cash-out selling powers.\n"
                "• 💥 **The Kamikaze:** Allows an instant single-use tactical explosion to drop all active voice users out (`!explode`).\n"
                "• 🦹 **The Joker:** Lock and enforce hilarious usernames upon targeted server friends for 4 whole hours (`!troll`).\n\n"
                "## **🎭 Uncle Samson System**\n"
                "• Special system in the Lucky Box with 15% appearance rate.\n"
                "• Asks you an embarrassing question from a list of 50 questions in Arabic and English.\n"
                "• 3 moods for Uncle Samson: Angry (1000 penalty), Normal (500 penalty), Happy (no penalty).\n"
                "• You can answer or cancel with penalty based on Uncle's mood.\n"
                "• If you answer acceptably, you'll receive a random reward from the shop.\n\n"
"## **📦 Lucky Box**\n"
"• The Luck Box is your chance to win the grand prize!\n"
"• Box contents include: Coins, items available in the store (excluding Rolls).\n"
"• You also have a chance to win Uncle Samson or a Steam game activation code.\n\n"

"## **🎁 B-day Gift**\n"
"• Special button in the control panel to send birthday gifts to friends.\n"
"• You can specify the recipient, amount, and an optional message.\n"
"• Minimum sending amount is 1500 BLZ (1000 for recipient + 500 tax).\n"
"• The bot sends a congratulatory image to the recipient's DM with gift details."
            ),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TradeResponseView(discord.ui.View):
    def __init__(self, sender_id, receiver_id, db_column, item_display):
        super().__init__(timeout=300)
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.db_column = db_column
        self.item_display = item_display

    @discord.ui.button(label="✅ قبول / Accept", style=discord.ButtonStyle.success)
    async def accept_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with db_lock:
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute(f"SELECT {self.db_column} FROM users WHERE user_id=?", (self.sender_id,))
            res = cursor.fetchone()
            
            if not res or res[0] <= 0:
                await interaction.response.send_message("❌ المرسل لم يعد يملك هذا الأيتم حالياً لإتمام العملية!", ephemeral=True)
                conn.close()
                self.stop()
                return
                
            cursor.execute(f"UPDATE users SET {self.db_column} = {self.db_column} - 1 WHERE user_id=?", (self.sender_id,))
            cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (self.receiver_id,))
            cursor.execute(f"UPDATE users SET {self.db_column} = {self.db_column} + 1 WHERE user_id=?", (self.receiver_id,))
            conn.commit()
            conn.close()
            
        log_action(self.sender_id, "TRADE_SUCCESS", f"قام بالتداول بنجاح ونقل أيتم {self.item_display} إلى العضو ذو الآيدي {self.receiver_id}")
        await interaction.response.send_message("🤝 تم قبول طلب التداول بنجاح، ونقل الأيتم إلى حقيبتك!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="❌ رفض / Decline", style=discord.ButtonStyle.danger)
    async def decline_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ لقد قمت برفض طلب التداول بنجاح.", ephemeral=True)
        self.stop()


class TradeModal(discord.ui.Modal):
    def __init__(self, lang_txt):
        super().__init__(title=lang_txt["trade_modal_title"])
        self.lang_txt = lang_txt
        self.username_input = discord.ui.TextInput(label=lang_txt["user_name_label"], required=True)
        self.item_input = discord.ui.TextInput(label=lang_txt["item_name_label"], required=True)
        self.add_item(self.username_input)
        self.add_item(self.item_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target_username = self.username_input.value.strip()
        item_choice = self.item_input.value.strip().lower()
        
        target_member = discord.utils.find(lambda m: m.name.lower()==target_username.lower() or m.display_name.lower()==target_username.lower(), interaction.guild.members)
                
        if not target_member:
            await interaction.followup.send(self.lang_txt["trade_invalid_user"], ephemeral=True)
            return
            
        db_col = None
        if "flash" in item_choice: db_col = "flashbang_count"
        elif "shield" in item_choice: db_col = "shield_count"
        elif "espresso" in item_choice: db_col = "espresso_count"
        elif "ticket" in item_choice: db_col = "ticket_count"
        elif "ghost" in item_choice: db_col = "ghost_count"
        
        if not db_col:
            await interaction.followup.send("❌ اسم الأيتم غير صحيح للتداول!", ephemeral=True)
            return

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(f"SELECT {db_col} FROM users WHERE user_id=?", (interaction.user.id,))
        res = cursor.fetchone()
        conn.close()
        
        if not res or res[0] <= 0:
            await interaction.followup.send(self.lang_txt["no_item"], ephemeral=True)
            return
            
        embed = discord.Embed(
            title="🤝 طلب تداول جديد / New Trade Request",
            description=f"📩 وصلك طلب تداول من **{interaction.user.name}**\nيرغب في إعطائك أيتم: **{item_choice}**\n\nلديك 5 دقائق للموافقة أو الرفض قبل انتهاء الصلاحية.",
            color=discord.Color.blue()
        )
        view = TradeResponseView(interaction.user.id, target_member.id, db_col, item_choice)
        
        dm_sent = await send_temporary_dm(target_member, embed=embed, view=view, duration=300)
        if dm_sent:
            log_action(interaction.user.id, "TRADE_REQUEST", f"أرسل طلب تداول {item_choice} إلى {target_member.name}")
            await interaction.followup.send(self.lang_txt["trade_sent_dm"], ephemeral=True)
        else:
            log_action(interaction.user.id, "TRADE_FAILED", f"فشل إرسال طلب تداول {item_choice} إلى {target_member.name} (DM مغلق)")
            await interaction.followup.send("❌ فشل إرسال رسالة لخاص هذا العضو، يبدو أن ملفه مغلق!", ephemeral=True)


class FlashbangModal(discord.ui.Modal):
    def __init__(self, lang_txt):
        super().__init__(title="💥 استخدام فلاش")
        self.lang_txt = lang_txt
        self.target_input = discord.ui.TextInput(label="اسم المستخدم الضحية (Username)", required=True)
        self.add_item(self.target_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        econ_ban = is_economy_banned(interaction.user.id)
        if econ_ban:
            await interaction.followup.send(f"❌ You are blocked from economy actions: {econ_ban}", ephemeral=True)
            return
        
        try:
            log_action(interaction.user.id, "FLASHBANG_USE", f"حاول استخدام Flashbang ضد {self.target_input.value.strip()}")
        except: pass
        
        target_username = self.target_input.value.strip()
        
        target_member = None
        for m in interaction.guild.members:
            if m.name == target_username:
                target_member = m
                break
                
        if not target_member:
            await interaction.followup.send("❌ لم يتم العثور على العضو المكتوب بالسيرفر!", ephemeral=True)
            return
            
        if target_member.id == interaction.user.id:
            await interaction.followup.send(self.lang_txt["flash_self"], ephemeral=True)
            return

        async with db_lock:
            try:
                conn = sqlite3.connect(DB_NAME, timeout=30.0)
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT flashbang_count FROM users WHERE user_id=?", (interaction.user.id,))
                user_res = cursor.fetchone()
                
                if not user_res or user_res[0] <= 0:
                    await interaction.followup.send(self.lang_txt["no_item"], ephemeral=True)
                    conn.close()
                    return
                    
                cursor.execute("SELECT shield_count FROM users WHERE user_id=?", (target_member.id,))
                target_res = cursor.fetchone()
                cursor.execute("UPDATE users SET flashbang_count = flashbang_count - 1 WHERE user_id=?", (interaction.user.id,))
                
                if target_res and target_res[0] > 0:
                    cursor.execute("UPDATE users SET shield_count = shield_count - 1 WHERE user_id=?", (target_member.id,))
                    conn.commit()
                    conn.close()
                    try:
                        log_action(interaction.user.id, "FLASH_SHIELDED", f"حاول استخدام فلاش ضد {target_member.name} ولكن تم صدها بدرع")
                    except: pass
                    await interaction.channel.send(f"{target_member.mention} {self.lang_txt['flash_shielded']}")
                    return

                expire = (datetime.now(timezone.utc) + timedelta(minutes=2)).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("INSERT OR REPLACE INTO active_effects (user_id, guild_id, effect_type, expire_time) VALUES (?, ?, 'flashbang', ?)",
                               (target_member.id, interaction.guild.id, expire))
                conn.commit()
                conn.close()
            except sqlite3.OperationalError:
                await interaction.followup.send("❌ خطأ في قاعدة البيانات، الرجاء المحاولة لاحقاً!", ephemeral=True)
                return

        try:
            log_action(interaction.user.id, "USE_FLASHBANG", f"ألقى فلاش بانج بنجاح على العضو {target_member.name}")
        except: pass
        
        try:
            if target_member.voice: await target_member.edit(mute=True)
            await interaction.channel.send(self.lang_txt["flash_success"].format(target_member.mention))
        except Exception as e:
            print(f"[ERROR] Flashbang mute failed: {e}")
            await interaction.channel.send(f"💥 {target_member.mention} Has been flashed textually!")


class GhostModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="👻 همس الشبح الخفي")
        self.msg_input = discord.ui.TextInput(label="اكتب الرسالة المجهولة هنا", style=discord.TextStyle.long, required=True)
        self.add_item(self.msg_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with db_lock:
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("SELECT ghost_count FROM users WHERE user_id=?", (interaction.user.id,))
            res = cursor.fetchone()
            if not res or res[0] <= 0:
                await interaction.followup.send("❌ لا تملك أيتم الشبح في حقيبتك!", ephemeral=True)
                conn.close()
                return
            cursor.execute("UPDATE users SET ghost_count = ghost_count - 1 WHERE user_id=?", (interaction.user.id,))
            conn.commit()
            conn.close()

        log_action(interaction.user.id, "USE_GHOST", "أرسل رسالة مجهولة عبر الشبح الخفي")
        
        embed = discord.Embed(
            title="👻 شبح السيرفر الخفي يهمس لكم...",
            description=f"```익명\n{self.msg_input.value}```",
            color=discord.Color.dark_gray()
        )
        
        # إرسال الرسالة مباشرة إلى روم الشات الرسمي المطلوب عبر الـ ID
        target_channel = BOT.get_channel(1257909845382664212)
        if target_channel:
            await target_channel.send(embed=embed)
        else:
            await interaction.channel.send(embed=embed)
            
        await interaction.followup.send("✅ تم إرسال همستك الشبحية بنجاح!", ephemeral=True)


class BirthdayGiftModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="🎁 B-day Gift")
        self.username_input = discord.ui.TextInput(label="Username للمستلم", style=discord.TextStyle.short, required=True)
        self.amount_input = discord.ui.TextInput(label="Amount للمبلغ", style=discord.TextStyle.short, required=True)
        self.message_input = discord.ui.TextInput(label="Message لرسالة اختيارية", style=discord.TextStyle.long, required=False)
        self.add_item(self.username_input)
        self.add_item(self.amount_input)
        self.add_item(self.message_input)


class UncleShamshonAnswerView(discord.ui.View):
    def __init__(self, user_id, mood, question_ar, question_en):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.mood = mood
        self.question_ar = question_ar
        self.question_en = question_en

    @discord.ui.button(label="💬 الرد / Answer", style=discord.ButtonStyle.primary)
    async def answer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        log_action(self.user_id, "UNCLE_SHAMSHON_ANSWER", f"اختار الإجابة على سؤال العم شمشون | السؤال: {self.question_ar} | Question: {self.question_en} (الحالة: {self.mood})")
        await interaction.response.send_modal(UncleShamshonAnswerModal(self.user_id, self.mood, self.question_ar, self.question_en))
        self.stop()

    @discord.ui.button(label="❌ إلغاء / Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        log_action(self.user_id, "UNCLE_SHAMSHON_CANCEL", f"اختار إلغاء سؤال العم شمشون (الحالة: {self.mood})")
        # إرسال تأكيد الإلغاء
        view = UncleShamshonCancelConfirmView(self.user_id, self.mood)
        embed = discord.Embed(
            title="⚠️ تأكيد الإلغاء / Cancel Confirmation",
            description="هل أنت متأكد من إلغاء التحدي؟\nAre you sure you want to cancel the challenge?",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        self.stop()


class UncleShamshonCancelConfirmView(discord.ui.View):
    def __init__(self, user_id, mood):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.mood = mood

    @discord.ui.button(label="✅ نعم، أريد الإلغاء / Yes, Cancel", style=discord.ButtonStyle.danger)
    async def confirm_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        # تحديد المبلغ المخصم حسب الحالة
        if self.mood == "angry":
            penalty = 1000
        elif self.mood == "normal":
            penalty = 500
        else:  # happy
            penalty = 0
        
        if penalty > 0:
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (penalty, self.user_id))
            conn.commit()
            conn.close()
            
            await interaction.followup.send(f"❌ تم إلغاء التحدي وخصم {penalty} BLZ من رصيدك!\nChallenge cancelled and {penalty} BLZ deducted from your balance!", ephemeral=True)
            log_action(self.user_id, "UNCLE_SHAMSHON_CANCEL", f"إلغاء التحدي - خصم {penalty} BLZ")
        else:
            await interaction.followup.send("✅ تم إلغاء التحدي بدون خصم (العم سعيد!)\nChallenge cancelled without penalty (Uncle is happy!)", ephemeral=True)
            log_action(self.user_id, "UNCLE_SHAMSHON_CANCEL", "إلغاء التحدي بدون خصم")
        
        self.stop()

    @discord.ui.button(label="🔙 عودة / Back", style=discord.ButtonStyle.secondary)
    async def go_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ تم إلغاء عملية الإلغاء.\nCancel operation cancelled.", ephemeral=True)
        self.stop()


class UncleShamshonAnswerModal(discord.ui.Modal):
    def __init__(self, user_id, mood, question_ar, question_en):
        super().__init__(title="🎭 العم شمشون يسألك")
        self.user_id = user_id
        self.mood = mood
        self.question_ar = question_ar
        self.question_en = question_en
        self.answer_input = discord.ui.TextInput(
            label="أجب على السؤال / Answer the question",
            style=discord.TextStyle.long,
            required=True,
            placeholder="اكتب إجابتك هنا..."
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        log_action(self.user_id, "UNCLE_SHAMSHON_SUBMIT", f"السؤال: {self.question_ar} | Question: {self.question_en} -- الإجابة: {self.answer_input.value} (الحالة: {self.mood})")
        
        # إرسال embed للتفكير
        embed = discord.Embed(
            title="🎭 العم شمشون يفكر...",
            description=f"إجابتك: {self.answer_input.value}\n\nالعم شمشون يقرر الآن...",
            color=discord.Color.orange()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # انتظار قصير ثم اتخاذ قرار تلقائي
        await asyncio.sleep(2)
        
        # اتخاذ قرار عشوائي حسب الحالة
        if self.mood == "happy":
            # العم سعيد: 90% إجابة ممتازة، 10% إجابة مقبولة
            decision = random.choices(["excellent", "acceptable"], weights=[90, 10])[0]
        elif self.mood == "normal":
            # العم عادي: 60% إجابة ممتازة، 30% إجابة مقبولة، 10% إجابة مرفوضة
            decision = random.choices(["excellent", "acceptable", "rejected"], weights=[60, 30, 10])[0]
        else:  # angry
            # العم عصبي: 40% إجابة ممتازة، 40% إجابة مقبولة، 20% إجابة مرفوضة
            decision = random.choices(["excellent", "acceptable", "rejected"], weights=[40, 40, 20])[0]
        
        # تنفيذ القرار
        if decision == "excellent":
            won_item = random.choice(["flashbang_count", "shield_count", "espresso_count", "ticket_count", "ghost_count"])
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute(f"UPDATE users SET {won_item} = {won_item} + 1 WHERE user_id=?", (self.user_id,))
            conn.commit()
            conn.close()
            
            if self.mood == "happy":
                result_msg = (
                    f"🎉 العم شمشون سعيد جداً! إجابتك رائعة! حصلت على **{won_item.replace('_count', '')}**!\n"
                    f"Uncle Samson is very happy! Your answer is great and you won **{won_item.replace('_count', '')}**!"
                )
            elif self.mood == "normal":
                result_msg = (
                    f"✅ العم شمشون قبل إجابتك! حصلت على **{won_item.replace('_count', '')}**!\n"
                    f"Uncle Samson accepted your answer and you received **{won_item.replace('_count', '')}**!"
                )
            else:  # angry
                result_msg = (
                    f"😤 العم شمشون هدأ قليلاً! إجابتك مقبولة. حصلت على **{won_item.replace('_count', '')}**!\n"
                    f"Uncle Samson calmed down a bit. Your answer is acceptable. You got **{won_item.replace('_count', '')}**!"
                )
            
            # Detailed log with question and answer
            try:
                log_action(self.user_id, "UNCLE_SHAMSHON_EXCELLENT", f"إجابة ممتازة - حصل على {won_item} | السؤال: {self.question_ar} | Question: {self.question_en} | الإجابة: {self.answer_input.value}")
            except: 
                pass
            
        elif decision == "acceptable":
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = balance - 500 WHERE user_id=?", (self.user_id,))
            won_item = random.choice(["flashbang_count", "shield_count", "espresso_count", "ticket_count", "ghost_count"])
            cursor.execute(f"UPDATE users SET {won_item} = {won_item} + 1 WHERE user_id=?", (self.user_id,))
            conn.commit()
            conn.close()
            
            if self.mood == "happy":
                result_msg = f"😊 العم شمشون سعيد رغم ذلك! تم خصم 500 BLZ فقط وحصلت على **{won_item.replace('_count', '')}**!"
            elif self.mood == "normal":
                result_msg = f"😐 العم شمشون قبل إجابتك لكنه غير راضٍ تماماً. تم خصم 500 BLZ وحصلت على **{won_item.replace('_count', '')}**!"
            else:  # angry
                result_msg = f"😡 العم شمشون غاضب جداً! تم خصم 500 BLZ وحصلت على **{won_item.replace('_count', '')}**!"
            
            try:
                log_action(self.user_id, "UNCLE_SHAMSHON_ACCEPTABLE", f"إجابة مقبولة - خصم 500 وحصل على {won_item} | السؤال: {self.question_ar} | Question: {self.question_en} | الإجابة: {self.answer_input.value}")
            except:
                pass
            
        else:  # rejected
            if self.mood == "happy":
                penalty = 0
            elif self.mood == "normal":
                penalty = 500
            else:  # angry
                penalty = 1000
            
            if penalty > 0:
                conn = sqlite3.connect(DB_NAME, timeout=30.0)
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (penalty, self.user_id))
                conn.commit()
                conn.close()
                
                if self.mood == "normal":
                    result_msg = f"😐 العم شمشون لم يعجبه إجابتك! تم خصم {penalty} BLZ من رصيدك!"
                else:  # angry
                    result_msg = f"😡 العم شمشون غاضب جداً! لم يعجبه إجابتك! تم خصم {penalty} BLZ من رصيدك!"
            else:
                result_msg = f"😊 العم شمشون سعيد رغم إجابتك! لم يتم خصم أي شيء!"
            
            try:
                log_action(self.user_id, "UNCLE_SHAMSHON_REJECTED", f"إجابة مرفوضة - خصم {penalty} | السؤال: {self.question_ar} | Question: {self.question_en} | الإجابة: {self.answer_input.value}")
            except:
                pass
        
        # إرسال النتيجة
        result_embed = discord.Embed(
            title="🎭 قرار العم شمشون",
            description=result_msg,
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=result_embed, ephemeral=True)


class UncleShamshonRatingView(discord.ui.View):
    def __init__(self, user_id, answer, mood):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.answer = answer
        self.mood = mood

    @discord.ui.button(label="✅ إجابة ممتازة / Excellent", style=discord.ButtonStyle.success)
    async def excellent_answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        # منح جائزة عشوائية بدون خصم
        won_item = random.choice(["flashbang_count", "shield_count", "espresso_count", "ticket_count", "ghost_count"])
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute(f"UPDATE users SET {won_item} = {won_item} + 1 WHERE user_id=?", (self.user_id,))
        conn.commit()
        conn.close()
        
        if self.mood == "happy":
            await interaction.followup.send(f"🎉 العم شمشون سعيد جداً! إجابتك رائعة! حصلت على **{won_item.replace('_count', '')}**!", ephemeral=True)
        elif self.mood == "normal":
            await interaction.followup.send(f"✅ العم شمشون قبل إجابتك! حصلت على **{won_item.replace('_count', '')}**!", ephemeral=True)
        else:  # angry
            await interaction.followup.send(f"😤 العم شمشون هدأ قليلاً! إجابتك مقبولة. حصلت على **{won_item.replace('_count', '')}**!", ephemeral=True)
        
        try:
            log_action(self.user_id, "UNCLE_SHAMSHON_EXCELLENT", f"إجابة ممتازة - حصل على {won_item} | الإجابة: {self.answer} | الحالة: {self.mood}")
        except: pass
        self.stop()

    @discord.ui.button(label="😐 إجابة مقبولة (مع غضب) / Acceptable (Angry)", style=discord.ButtonStyle.primary)
    async def acceptable_answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        # خصم 500 BLZ ومنح جائزة
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance - 500 WHERE user_id=?", (self.user_id,))
        won_item = random.choice(["flashbang_count", "shield_count", "espresso_count", "ticket_count", "ghost_count"])
        cursor.execute(f"UPDATE users SET {won_item} = {won_item} + 1 WHERE user_id=?", (self.user_id,))
        conn.commit()
        conn.close()
        
        if self.mood == "happy":
            await interaction.followup.send(f"😊 العم شمشون سعيد رغم ذلك! تم خصم 500 BLZ فقط وحصلت على **{won_item.replace('_count', '')}**!", ephemeral=True)
        elif self.mood == "normal":
            await interaction.followup.send(f"😐 العم شمشون قبل إجابتك لكنه غير راضٍ تماماً. تم خصم 500 BLZ وحصلت على **{won_item.replace('_count', '')}**!", ephemeral=True)
        else:  # angry
            await interaction.followup.send(f"😡 العم شمشون غاضب جداً! تم خصم 500 BLZ وحصلت على **{won_item.replace('_count', '')}**!", ephemeral=True)
        
        try:
            log_action(self.user_id, "UNCLE_SHAMSHON_ACCEPTABLE", f"إجابة مقبولة - خصم 500 وحصل على {won_item} | الإجابة: {self.answer} | الحالة: {self.mood}")
        except: pass
        self.stop()

    @discord.ui.button(label="❌ إجابة مرفوضة / Rejected", style=discord.ButtonStyle.danger)
    async def rejected_answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        # تحديد المبلغ المخصم حسب الحالة
        if self.mood == "happy":
            penalty = 0
        elif self.mood == "normal":
            penalty = 500
        else:  # angry
            penalty = 1000
        
        if penalty > 0:
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (penalty, self.user_id))
            conn.commit()
            conn.close()
            
            if self.mood == "normal":
                await interaction.followup.send(f"😐 العم شمشون لم يعجبه إجابتك! تم خصم {penalty} BLZ من رصيدك!", ephemeral=True)
            else:  # angry
                await interaction.followup.send(f"😡 العم شمشون غاضب جداً! لم يعجبه إجابتك! تم خصم {penalty} BLZ من رصيدك!", ephemeral=True)
        else:
            await interaction.followup.send(f"😊 العم شمشون سعيد رغم إجابتك! لم يتم خصم أي شيء!", ephemeral=True)
        
        try:
            log_action(self.user_id, "UNCLE_SHAMSHON_REJECTED", f"إجابة مرفوضة - خصم {penalty} | السؤال: {self.answer} | الإجابة: {self.answer} | الحالة: {self.mood}")
        except:
            pass
        self.stop()


class BirthdayGiftModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="🎁 B-day Gift")
        self.username_input = discord.ui.TextInput(label="Username للمستلم", style=discord.TextStyle.short, required=True)
        self.amount_input = discord.ui.TextInput(label="Amount للمبلغ", style=discord.TextStyle.short, required=True)
        self.message_input = discord.ui.TextInput(label="Message لرسالة اختيارية", style=discord.TextStyle.long, required=False)
        self.add_item(self.username_input)
        self.add_item(self.amount_input)
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # التحقق من المبلغ
        try:
            amount = int(self.amount_input.value)
            if amount <= 0:
                await interaction.followup.send("❌ المبلغ يجب أن يكون رقماً موجباً!", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ المبلغ يجب أن يكون رقماً صحيحاً!", ephemeral=True)
            return
        
        # التحقق من الحد الأدنى (1500 BLZ كحد أدنى للإرسال)
        if amount < 1500:
            await interaction.followup.send("❌ الحد الأدنى للإرسال هو 1500 BLZ (1000 للمستلم + 500 ضريبة)!", ephemeral=True)
            return
        
        # التحقق من رصيد المرسل (المبلغ + 500 رسوم)
        total_cost = amount + 500
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (interaction.user.id,))
        res = cursor.fetchone()
        bal = res[0] if res else 1000
        
        if bal < total_cost:
            await interaction.followup.send(f"❌ رصيدك غير كافٍ! تحتاج إلى {total_cost} BLZ (المبلغ + 500 رسوم).", ephemeral=True)
            conn.close()
            return
        
        # خصم المبلغ
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (total_cost, interaction.user.id))
        conn.commit()
        conn.close()
        
        # البحث عن المستلم
        username = self.username_input.value.strip()
        target_member = None
        
        # محاولة البحث بالمنشن
        if username.startswith("<@") and username.endswith(">"):
            user_id = int(username.strip("<@!>"))
            target_member = interaction.guild.get_member(user_id)
        else:
            # البحث بالاسم
            for member in interaction.guild.members:
                if member.name.lower() == username.lower() or (member.nick and member.nick.lower() == username.lower()):
                    target_member = member
                    break
        
        if not target_member:
            await interaction.followup.send("❌ لم يتم العثور على هذا المستخدم في السيرفر!", ephemeral=True)
            # إرجاع المبلغ
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (total_cost, interaction.user.id))
            conn.commit()
            conn.close()
            return
        
        # إرسال صورة التهنئة في DM
        try:
            # المستلم يصله المبلغ ناقص 500
            recipient_amount = amount - 500
            
            # إضافة المبلغ للمستلم
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (target_member.id,))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (recipient_amount, target_member.id))
            conn.commit()
            conn.close()
            
            # إنشاء الصورة مع توسيط الاسم والبروفايل
            gift_image_url = await create_birthday_gift_image(target_member, amount, self.message_input.value)
            
            embed = discord.Embed(
                title="🎁 B-day Gift!",
                description=f"أرسل لك {interaction.user.mention} هدية عيد ميلاد بقيمة **{recipient_amount} BLZ**! (تم خصم 500 BLZ كرسوم)",
                color=discord.Color.pink()
            )
            if gift_image_url:
                embed.set_image(url=gift_image_url)
            
            if self.message_input.value:
                embed.add_field(name="رسالة", value=self.message_input.value, inline=False)
            
            await target_member.send(embed=embed)
            await interaction.followup.send(f"✅ تم إرسال الهدية بنجاح إلى {target_member.mention}! المستلم حصل على {recipient_amount} BLZ", ephemeral=True)
            log_action(interaction.user.id, "BDAY_GIFT", f"أرسل هدية بقيمة {amount} BLZ إلى {target_member.name}، المستلم حصل على {recipient_amount} BLZ")
            
        except discord.Forbidden:
            await interaction.followup.send("❌ المستلم لا يقبل رسائل DM خاصة!", ephemeral=True)
            # إرجاع المبلغ
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (total_cost, interaction.user.id))
            conn.commit()
            conn.close()
        except Exception as e:
            await interaction.followup.send(f"❌ حدث خطأ: {e}", ephemeral=True)
            # إرجاع المبلغ
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (total_cost, interaction.user.id))
            conn.commit()
            conn.close()


class TransferCoinsModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="💸 إرسال العملات / Transfer Coins")
        self.username_input = discord.ui.TextInput(label="Username للمستلم / Recipient Username", style=discord.TextStyle.short, required=True)
        self.amount_input = discord.ui.TextInput(label="Amount للمبلغ / Amount", style=discord.TextStyle.short, required=True)
        self.reason_input = discord.ui.TextInput(label="السبب / Reason (Required)", style=discord.TextStyle.long, required=True)
        self.add_item(self.username_input)
        self.add_item(self.amount_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        econ_ban = is_economy_banned(interaction.user.id)
        if econ_ban:
            await interaction.followup.send(f"❌ You are blocked from economy actions: {econ_ban}", ephemeral=True)
            return
        
        # التحقق من المبلغ
        try:
            amount = int(self.amount_input.value)
            if amount <= 0:
                await interaction.followup.send("❌ المبلغ يجب أن يكون رقماً موجباً! / Amount must be positive!", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ المبلغ يجب أن يكون رقماً صحيحاً! / Amount must be an integer!", ephemeral=True)
            return
        
        # حساب الضريبة (10% على كل 100 عملة)
        tax = int(amount * 0.1)
        total_deduction = amount + tax
        
        # البحث عن المستلم
        recipient_username = self.username_input.value.strip()
        target_member = None
        
        # البحث في السيرفر
        for member in interaction.guild.members:
            if member.name.lower() == recipient_username.lower() or member.display_name.lower() == recipient_username.lower():
                target_member = member
                break
        
        if not target_member:
            await interaction.followup.send(f"❌ لم يتم العثور على المستخدم {recipient_username}! / User not found!", ephemeral=True)
            return
        
        if target_member.id == interaction.user.id:
            await interaction.followup.send("❌ لا يمكنك تحويل العملات لنفسك! / You cannot transfer coins to yourself!", ephemeral=True)
            return
        
        # التحقق من رصيد المرسل
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (interaction.user.id,))
        res = cursor.fetchone()
        sender_balance = res[0] if res else 1000
        
        if sender_balance < total_deduction:
            await interaction.followup.send(f"❌ رصيدك غير كافٍ! تحتاج إلى {total_deduction} BLZ (المبلغ + الضريبة {tax} BLZ)!\nInsufficient balance! You need {total_deduction} BLZ (Amount + Tax {tax} BLZ)!", ephemeral=True)
            conn.close()
            return
        
        # خصم المبلغ والضريبة من المرسل
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (total_deduction, interaction.user.id))
        
        # إضافة المبلغ للمستلم (بدون الضريبة)
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (target_member.id,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, target_member.id))
        
        conn.commit()
        conn.close()
        
        # إرسال DM للمستلم
        try:
            transfer_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            embed = discord.Embed(
                title="💸 حوالة جديدة! / New Transfer!",
                description=f"استلمت حوالة جديدة من {interaction.user.mention}\nYou received a new transfer from {interaction.user.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="المبلغ المرسل / Sent Amount", value=f"{amount} BLZ", inline=False)
            embed.add_field(name="الضريبة / Tax", value=f"{tax} BLZ", inline=False)
            embed.add_field(name="المبلغ المستلم / Received Amount", value=f"{amount} BLZ", inline=False)
            embed.add_field(name="السبب / Reason", value=self.reason_input.value, inline=False)
            embed.add_field(name="التاريخ والوقت / Date & Time", value=transfer_time, inline=False)
            await target_member.send(embed=embed)
            
            await interaction.followup.send(f"✅ تم تحويل {amount} BLZ إلى {target_member.mention} بنجاح! (ضريبة: {tax} BLZ)\nSuccessfully transferred {amount} BLZ to {target_member.mention}! (Tax: {tax} BLZ)", ephemeral=True)
            log_action(interaction.user.id, "TRANSFER_COINS", f"حول {amount} BLZ إلى {target_member.name} (السبب: {self.reason_input.value})")
            
        except discord.Forbidden:
            await interaction.followup.send(f"✅ تم التحويل بنجاح لكن المستلم لا يقبل رسائل DM!\nTransfer successful but recipient doesn't accept DMs!", ephemeral=True)
            log_action(interaction.user.id, "TRANSFER_COINS", f"حول {amount} BLZ إلى {target_member.name} (السبب: {self.reason_input.value})")
        
        except Exception as e:
            await interaction.followup.send(f"❌ حدث خطأ أثناء إرسال DM للمستلم: {e}", ephemeral=True)


# ==========================================
# 4. قائمة الشراء المحدثة بالرتب الـ 3 الجديدة
# ==========================================

class ShopDropdown(discord.ui.Select):
    def __init__(self, lang_txt):
        self.lang_txt = lang_txt
        options = [
            discord.SelectOption(label=f"Flashbang ({get_price('flashbang')} BLZ)", value="flashbang", emoji="💥"),
            discord.SelectOption(label=f"Shield ({get_price('shield')} BLZ)", value="shield", emoji="🛡️"),
            discord.SelectOption(label=f"Espresso Shot ({get_price('espresso')} BLZ)", value="espresso", emoji="☕"),
            discord.SelectOption(label=f"Lucky Ticket ({get_price('ticket')} BLZ)", value="ticket", emoji="🎰"),
            discord.SelectOption(label=f"Ghost Whisper ({get_price('ghost')} BLZ)", value="ghost", emoji="👻"),
            discord.SelectOption(label=f"The Smuggler Role ({get_price('smuggle_role')} BLZ) [45m]", value="smuggle_role", emoji="🕵️"),
            discord.SelectOption(label=f"The Kamikaze Role ({get_price('kamikaze_role')} BLZ) [1 Use]", value="kamikaze_role", emoji="💣"),
            discord.SelectOption(label=f"The Joker Role ({get_price('joker_role')} BLZ) [4h]", value="joker_role", emoji="🦹"),
        ]
        super().__init__(placeholder="Select an item or role to buy...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if user is shop banned
        ban_reason = is_shop_banned(interaction.user.id)
        if ban_reason:
            lang_txt = self.get_txt(interaction)
            await interaction.followup.send(lang_txt["shop_banned"].format(ban_reason), ephemeral=True)
            return
        econ_ban = is_economy_banned(interaction.user.id)
        if econ_ban:
            await interaction.followup.send(f"❌ You are blocked from economy actions: {econ_ban}", ephemeral=True)
            return
        
        item = self.values[0]
        price = get_price(item)
        
        async with db_lock:
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM users WHERE user_id=?", (interaction.user.id,))
            res = cursor.fetchone()
            bal = res[0] if res else 1000
            
            if bal < price:
                await interaction.followup.send(self.lang_txt["no_money"].format(price), ephemeral=True)
                conn.close()
                return
                
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (price, interaction.user.id))
            
            # معالجة شراء الرتب الاستثنائية الجديدة مع تعديل المهرب لـ 45 دقيقة وسحبها تلقائياً عند النفاذ
            if item == "smuggle_role":
                expire = (datetime.now(timezone.utc) + timedelta(minutes=45)).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("INSERT OR REPLACE INTO active_effects (user_id, guild_id, effect_type, expire_time) VALUES (?, ?, 'smugpler', ?)",
                               (interaction.user.id, interaction.guild.id, expire))
                try:
                    r = interaction.guild.get_role(ROLE_SMUGGLER_ID)
                    if r: await interaction.user.add_roles(r)
                except: pass
                msg = "🕵️ تم شراء رتبة **تاجر السوق السوداء** بنجاح لمدة 45 دقيقة! يفتح لك الروم المخفي ويمكنك استخدام `!smuggle-buy` و `!smuggle-sell` الآن بخصومات قوية."
                
            elif item == "kamikaze_role":
                cursor.execute("UPDATE users SET kamikaze_uses = kamikaze_uses + 1 WHERE user_id=?", (interaction.user.id,))
                try:
                    r = interaction.guild.get_role(ROLE_KAMIKAZE_ID)
                    if r: await interaction.user.add_roles(r)
                except: pass
                msg = "💣 تم شراء رتبة **المفجّر (The Kamikaze)** بنجاح لمرة واحدة! يمكنك الذهاب لأي روم صوتي وكتابة `!explode` لتفجير الغرفة وطرد الجميع فوراً."
                
            elif item == "joker_role":
                expire = (datetime.now(timezone.utc) + timedelta(hours=4)).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("INSERT OR REPLACE INTO active_effects (user_id, guild_id, effect_type, expire_time) VALUES (?, ?, 'joker', ?)",
                               (interaction.user.id, interaction.guild.id, expire))
                cursor.execute("UPDATE users SET joker_trolls = 3 WHERE user_id=?", (interaction.user.id,))
                try:
                    r = interaction.guild.get_role(ROLE_JOKER_ID)
                    if r: await interaction.user.add_roles(r)
                except: pass
                msg = "🦹 تم شراء رتبة **الملك المشاغب (The Joker)** بنجاح لمدة 4 ساعات! تم منحك 3 محاولات لتغيير أسماء أصدقائك إجبارياً عبر أمر `!troll`."
                
            else:
                col_name = f"{item}_count"
                cursor.execute(f"UPDATE users SET {col_name} = {col_name} + 1 WHERE user_id=?", (interaction.user.id,))
                msg = self.lang_txt["buy_success"].format(item, price)
                
            conn.commit()
            conn.close()
            
        log_action(interaction.user.id, "BUY_SHOP", f"اشترى {item} بمبلغ {price}")
        if msg:  # فقط أرسل الرسالة إذا لم تكن None
            await interaction.followup.send(msg, ephemeral=True)
            await asyncio.sleep(15)
            try:
                await interaction.delete_original_response()
            except Exception:
                pass

    def get_txt(self, interaction):
        return LOCALIZATION[get_lang(interaction.guild_id)]


class EditPanelModal(discord.ui.Modal):
    def __init__(self, initial_ar, initial_en):
        super().__init__(title="Edit Hub Info & Items Description")
        self.ar = discord.ui.TextInput(label="Info Arabic - صناديق الحظ والأيتمات", style=discord.TextStyle.long, required=False, default=initial_ar, max_length=4000, placeholder="اكتب وصف لوحة التحكم والأيتمات المتاحة بالعربية")
        self.en = discord.ui.TextInput(label="Info English - Lucky Box & Items", style=discord.TextStyle.long, required=False, default=initial_en, max_length=4000, placeholder="Describe the control panel and available items in English")
        self.add_item(self.ar)
        self.add_item(self.en)

    async def on_submit(self, interaction: discord.Interaction):
        # Save both
        set_config_str('info_text_ar', self.ar.value)
        set_config_str('info_text_en', self.en.value)
        await interaction.response.send_message("✅ تم حفظ نص لوحة التحكم بنجاح. اكتب !setup-hub لإعادة نشر الـ Hub.", ephemeral=True)
        try: log_action(interaction.user.id, "EDIT_PANEL", "Updated hub info text via modal")
        except: pass


class SingleLangInfoModal(discord.ui.Modal):
    def __init__(self, lang, initial):
        title = "Edit Lucky Box & Items Info (AR)" if lang=='ar' else "Edit Lucky Box & Items Info (EN)"
        super().__init__(title=title)
        self.lang = lang
        ar_placeholder = "اكتب وصف صندوق الحظ والأيتمات المتاحة بالعربية"
        en_placeholder = "Describe the Lucky Box and available items in English"
        placeholder = ar_placeholder if lang=='ar' else en_placeholder
        label = f"Lucky Box & Items ({'عربي' if lang=='ar' else 'English'})"
        self.input = discord.ui.TextInput(label=label, style=discord.TextStyle.long, required=False, default=initial, max_length=4000, placeholder=placeholder)
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        if self.lang == 'ar':
            set_config_str('info_text_ar', self.input.value)
        else:
            set_config_str('info_text_en', self.input.value)
        await interaction.response.send_message("✅ تم حفظ التعديل. اكتب !setup-hub لإعادة نشر اللوحة.", ephemeral=True)
        try: log_action(interaction.user.id, "EDIT_INFO_MODAL", f"Edited info {self.lang}")
        except: pass


class ControlPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def get_txt(self, interaction):
        return LOCALIZATION[get_lang(interaction.guild_id)]

    @discord.ui.button(emoji=EMOJI_SHOP, style=discord.ButtonStyle.secondary, custom_id="cp_shop", row=0)
    async def shop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang_txt = self.get_txt(interaction)
        view = discord.ui.View()
        view.add_item(ShopDropdown(lang_txt))
        await interaction.response.send_message(f"🛒 **Marketplace Buy List ({EMOJI_COIN}):**", view=view, ephemeral=True)
        await asyncio.sleep(15)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass

    @discord.ui.button(emoji=EMOJI_CASE, style=discord.ButtonStyle.secondary, custom_id="cp_case", row=0)
    async def case_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        # Simple rate-limit to prevent spam/abuse
        if not check_cooldown(interaction.user.id, 'case', 2):
            await interaction.followup.send(self.get_txt(interaction)['rate_limited_generic'].format(2), ephemeral=True)
            return
        
        # Check if user is shop banned
        ban_reason = is_shop_banned(interaction.user.id)
        if ban_reason:
            lang_txt = self.get_txt(interaction)
            await interaction.followup.send(lang_txt["shop_banned"].format(ban_reason), ephemeral=True)
            return
        econ_ban = is_economy_banned(interaction.user.id)
        if econ_ban:
            await interaction.followup.send(f"❌ You are blocked from economy actions: {econ_ban}", ephemeral=True)
            return
        
        lang_txt = self.get_txt(interaction)
        price = get_price("case")
        
        # 1) Quick check & deduct price under lock
        async with db_lock:
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM users WHERE user_id=?", (interaction.user.id,))
            res = cursor.fetchone()
            bal = res[0] if res else 1000
            
            if bal < price:
                await interaction.followup.send(lang_txt["no_money"].format(price), ephemeral=True)
                conn.close()
                return
            
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (price, interaction.user.id))
            conn.commit()
            conn.close()
        
        # 2) Release lock for animation/delay
        await interaction.followup.send("🎲 Rolling Loot Box...  🟩 🟥 🟨 🟦", ephemeral=True)
        await asyncio.sleep(1.5)
        
        # 3) Determine outcome
        rand = random.randint(1, 100)
        c1 = get_config_int("lucky_common")
        c2 = c1 + get_config_int("lucky_rare")
        c3 = c2 + get_config_int("lucky_uncle")
        msg = None
        if rand <= c1:
            # Common: cash back
            cash_back = random.randint(600, 2000)
            async with db_lock:
                conn = sqlite3.connect(DB_NAME, timeout=30.0)
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (cash_back, interaction.user.id))
                conn.commit()
                conn.close()
            msg = lang_txt["case_win_common"].format(cash_back)
            try: log_action(interaction.user.id, "LUCKY_BOX_WIN_COMMON", f"ربح {cash_back} BLZ من صندوق الحظ")
            except: pass
        elif rand <= c2:
            # Rare: give an item
            won_item = random.choice(["flashbang_count", "shield_count", "espresso_count", "ticket_count", "ghost_count"])
            async with db_lock:
                conn = sqlite3.connect(DB_NAME, timeout=30.0)
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute(f"UPDATE users SET {won_item} = {won_item} + 1 WHERE user_id=?", (interaction.user.id,))
                conn.commit()
                conn.close()
            msg = lang_txt["case_win_item"].format(won_item.replace("_count", ""))
            try: log_action(interaction.user.id, "LUCKY_BOX_WIN_RARE", f"ربح {won_item.replace('_count', '')} من صندوق الحظ")
            except: pass
        elif rand <= c3:
            # Special Uncle Shamshon event (no DB write required)
            mood = random.choice(["angry", "normal", "happy"])
            choice_pair = random.choice(UNCLE_SHAMSHON_QUESTIONS)
            question_ar = choice_pair["ar"]
            question_en = choice_pair["en"]
            if mood == "angry":
                image_url = "https://shorturl.at/GClmU"
                title = "😡 العم شمشون غاضب!"
                description = f"**السؤال:** {question_ar}\n**Question:** {question_en}\n\n⚠️ العم شمشون في حالة عصبية! كن حذراً!\nUncle Samson is in an angry mood! Be careful!"
                color = discord.Color.red()
            elif mood == "normal":
                image_url = "https://shorturl.at/JZPhb"
                title = "😐 العم شمشون في مزاج عادي"
                description = f"**السؤال:** {question_ar}\n**Question:** {question_en}\n\n🤔 العم شمشون بمزاج معكر نسبياً.\nUncle Samson is in a somewhat grumpy mood."
                color = discord.Color.orange()
            else:
                image_url = "https://shorturl.at/UFajG"
                title = "😊 العم شمشون سعيد!"
                description = f"**السؤال:** {question_ar}\n**Question:** {question_en}\n\n🎉 العم شمشون في حالة سعيدة! استمتع!\nUncle Samson is in a happy mood! Enjoy!"
                color = discord.Color.green()
            embed = discord.Embed(title=title, description=description, color=color)
            view = UncleShamshonAnswerView(interaction.user.id, mood, question_ar, question_en)
            # Try fetching the image and attach as a local file so Discord shows it reliably
            try:
                import urllib.request, io
                def _fetch(u):
                    with urllib.request.urlopen(u, timeout=8) as resp:
                        return resp.getheader('Content-Type'), resp.read()
                ctype, imgdata = await asyncio.to_thread(_fetch, image_url)
                if ctype and ctype.startswith('image') and imgdata:
                    bio = io.BytesIO(imgdata)
                    bio.seek(0)
                    filename = f"uncle_{mood}.png"
                    file = discord.File(bio, filename=filename)
                    embed.set_image(url=f"attachment://{filename}")
                    await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)
                else:
                    embed.set_image(url=image_url)
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            except Exception:
                try:
                    embed.set_image(url=image_url)
                except:
                    pass
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            msg = None
            try:
                log_action(interaction.user.id, "LUCKY_BOX_UNCLE_SHAMSHON", f"ظهر العم شمشون (الحالة: {mood}) | السؤال: {question_ar} | Question: {question_en}")
            except:
                pass
        else:
            # Legendary: check for steam key
            async with db_lock:
                conn = sqlite3.connect(DB_NAME, timeout=30.0)
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT id, game_name, key_code FROM steam_keys WHERE used=0 LIMIT 1")
                key_res = cursor.fetchone()
                if key_res:
                    key_id, g_name, code = key_res
                    cursor.execute("UPDATE steam_keys SET used=1 WHERE id=?", (key_id,))
                    conn.commit()
                else:
                    cursor.execute("UPDATE users SET balance = balance + 5000 WHERE user_id=?", (interaction.user.id,))
                    conn.commit()
                conn.close()
            if key_res:
                key_id, g_name, code = key_res
                msg = lang_txt["case_win_steam"].format(g_name)
                embed_key = discord.Embed(title="🔑 جائزة ستيم الأسطورية", description=f"اللعبة: **{g_name}**\nالمفتاح: `{code}`", color=discord.Color.gold())
                await send_temporary_dm(interaction.user, embed=embed_key, duration=300)
                try: log_action(interaction.user.id, "LUCKY_BOX_WIN_STEAM", f"ربح لعبة ستيم: {g_name}")
                except: pass
            else:
                msg = lang_txt["no_keys"]
                try: log_action(interaction.user.id, "LUCKY_BOX_WIN_CASHBACK", f"ربح 5000 BLZ بدلاً من لعبة ستيم")
                except: pass
        
        if msg:
            await interaction.followup.send(msg, ephemeral=True)

    @discord.ui.button(emoji=EMOJI_INV, style=discord.ButtonStyle.secondary, custom_id="cp_inv", row=0)
    async def inv_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute("SELECT flashbang_count, shield_count, espresso_count, ticket_count, ghost_count FROM users WHERE user_id=?", (interaction.user.id,))
        res = cursor.fetchone()
        conn.close()
        f, s, e, t, g = res if res else (0, 0, 0, 0, 0)
        lang_txt = self.get_txt(interaction)
        await interaction.response.send_message(lang_txt["inv_msg"].format(f, s, e, t, g), ephemeral=True)
        await asyncio.sleep(15)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass

    @discord.ui.button(emoji=EMOJI_BAL, style=discord.ButtonStyle.secondary, custom_id="cp_bal", row=0)
    async def bal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang_txt = self.get_txt(interaction)
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (interaction.user.id,))
        res = cursor.fetchone()
        conn.close()
        bal = res[0] if res else 1000
        await interaction.response.send_message(lang_txt["bal_msg"].format(bal), ephemeral=True)
        await asyncio.sleep(15)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass

    @discord.ui.button(emoji=EMOJI_FLASH, style=discord.ButtonStyle.secondary, custom_id="cp_use_flash", row=1)
    async def use_flash(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang_txt = self.get_txt(interaction)
        await interaction.response.send_modal(FlashbangModal(lang_txt))

    @discord.ui.button(emoji=EMOJI_ESPRESSO, style=discord.ButtonStyle.secondary, custom_id="cp_use_espresso", row=1)
    async def use_espresso(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        lang_txt = self.get_txt(interaction)
        async with db_lock:
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("SELECT espresso_count FROM users WHERE user_id=?", (interaction.user.id,))
            res = cursor.fetchone()
            if not res or res[0] <= 0:
                await interaction.followup.send(lang_txt["no_item"], ephemeral=True)
                conn.close()
                return
            cursor.execute("UPDATE users SET espresso_count = espresso_count - 1 WHERE user_id=?", (interaction.user.id,))
            expire = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("INSERT OR REPLACE INTO active_effects (user_id, guild_id, effect_type, expire_time) VALUES (?, ?, 'espresso', ?)",
                           (interaction.user.id, interaction.guild.id, expire))
            conn.commit()
            conn.close()
            log_action(interaction.user.id, "USE_ESPRESSO", f"استخدم Espresso Shot")
        try:
            role = discord.utils.get(interaction.guild.roles, name="Active Barista")
            if not role: role = await interaction.guild.create_role(name="Active Barista", color=discord.Color.brown())
            await interaction.user.add_roles(role)
        except: pass
        await interaction.followup.send(lang_txt["espresso_active"], ephemeral=True)

    @discord.ui.button(emoji=EMOJI_TRADE, style=discord.ButtonStyle.secondary, custom_id="cp_trade", row=1)
    async def trade_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang_txt = self.get_txt(interaction)
        await interaction.response.send_modal(TradeModal(lang_txt))

    @discord.ui.button(emoji=EMOJI_LB, style=discord.ButtonStyle.secondary, custom_id="cp_lb", row=1)
    async def lb_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10")
        top_users = cursor.fetchall()
        conn.close()
        embed = discord.Embed(title=f"🏆 TOP 10 WALLETS (BLZ) {EMOJI_COIN}", color=discord.Color.gold())
        for idx, (u_id, bal) in enumerate(top_users, 1):
            # Use mention so user is pinged in the embed
            embed.add_field(name=f"#{idx} User", value=f"<@{u_id}> - **{bal} BLZ**", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(emoji="<:send:1515960860793765918>", style=discord.ButtonStyle.secondary, custom_id="cp_transfer", row=2)
    async def transfer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TransferCoinsModal())

    @discord.ui.button(emoji=EMOJI_LOTTERY, style=discord.ButtonStyle.secondary, custom_id="cp_use_ticket", row=2)
    async def use_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        # rate limit for lottery
        if not check_cooldown(interaction.user.id, 'lottery', 10):
            await interaction.followup.send(self.get_txt(interaction)['rate_limited_generic'].format(10), ephemeral=True)
            return
        lang_txt = self.get_txt(interaction)
        async with db_lock:
            conn = sqlite3.connect(DB_NAME, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("SELECT ticket_count FROM users WHERE user_id=?", (interaction.user.id,))
            res = cursor.fetchone()
            if not res or res[0] <= 0:
                await interaction.followup.send(lang_txt.get('no_item', '❌ You don\'t own a ticket right now!'), ephemeral=True)
                conn.close()
                return
            cursor.execute("UPDATE users SET ticket_count = ticket_count - 1 WHERE user_id=?", (interaction.user.id,))
            win = random.choice([True, False])
            if win:
                cursor.execute("UPDATE users SET balance = balance + 1200 WHERE user_id=?", (interaction.user.id,))
                msg = lang_txt.get('lottery_win', f"🎰 You won 1200 BLZ!")
                try:
                    log_action(interaction.user.id, "LOTTERY_WIN", f"فاز في السحب الفوري وحصل على 1200 BLZ")
                except: pass
            else:
                msg = lang_txt.get('lottery_lose', f"🎰 You lost the instant draw and 500 BLZ is gone.")
                try:
                    log_action(interaction.user.id, "LOTTERY_LOSE", f"خسر في السحب الفوري")
                except: pass
            conn.commit()
            conn.close()
        await interaction.followup.send(msg, ephemeral=True)

    @discord.ui.button(emoji=EMOJI_GHOST, style=discord.ButtonStyle.secondary, custom_id="cp_use_ghost", row=2)
    async def use_ghost(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            log_action(interaction.user.id, "GHOST_MODAL_OPEN", "فتح Modal Ghost")
        except: pass
        await interaction.response.send_modal(GhostModal())

    @discord.ui.button(emoji="<:gift:1515886157399986297>", style=discord.ButtonStyle.secondary, custom_id="cp_bday", row=2)
    async def bday_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            log_action(interaction.user.id, "BDAY_GIFT_MODAL_OPEN", "فتح Modal B-day Gift")
        except: pass
        await interaction.response.send_modal(BirthdayGiftModal())

    @discord.ui.button(emoji="<:lang:1516290853658693732>", style=discord.ButtonStyle.secondary, custom_id="cp_toggle_lang", row=3)
    async def toggle_lang_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Toggle default language between ar and en
        current = get_lang(interaction.guild_id)
        new = 'en' if current == 'ar' else 'ar'
        set_config_int('lang_default', 1 if new == 'ar' else 0)
        try:
            log_action(interaction.user.id, "TOGGLE_LANG", f"Toggled default language to {new}")
        except: pass
        await interaction.response.send_message(f"✅ تم تعيين اللغة الافتراضية إلى {'العربية' if new == 'ar' else 'الإنجليزية'}! / Default language set to {new}.", ephemeral=True)

    @discord.ui.button(emoji=EMOJI_INFO, style=discord.ButtonStyle.secondary, custom_id="cp_info_manual", row=3)
    async def info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = InfoExplanationView()
        await interaction.response.send_message("🌐 اختر لغتك لعرض شرح نظام الاقتصاد والأدوات بالكامل:\nSelect your language to view the economy guide:", view=view, ephemeral=True)

# ==========================================
# 5. محرك الكسب ونظام التكافؤ الصوتي (نظام MEE6 للعملات)
# ==========================================

COOLDOWNS = {}

def check_cooldown(user_id, action, seconds):
    now = datetime.now(timezone.utc)
    key = f"{user_id}_{action}"
    if key in COOLDOWNS and (now - COOLDOWNS[key]).total_seconds() < seconds:
        return False
    COOLDOWNS[key] = now
    return True

def has_espresso_multiplier(user_id):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("SELECT expire_time FROM active_effects WHERE user_id=? AND effect_type='espresso'", (user_id,))
        res = cursor.fetchone()
        conn.close()
        if res:
            try:
                expire = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
                if datetime.now(timezone.utc).replace(tzinfo=None) < expire:
                    return True
            except: pass
        return False
    except:
        return False

def is_channel_blacklisted(channel_id):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("SELECT channel_id FROM blacklisted_channels WHERE channel_id=?", (channel_id,))
        res = cursor.fetchone()
        conn.close()
        return True if res else False
    except:
        return False

def is_flashbanged(user_id):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("SELECT expire_time FROM active_effects WHERE user_id=? AND effect_type='flashbang'", (user_id,))
        res = cursor.fetchone()
        conn.close()
        if res:
            try:
                expire = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
                if datetime.now(timezone.utc).replace(tzinfo=None) < expire:
                    return True
            except: pass
        return False
    except:
        return False

@BOT.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    if is_channel_blacklisted(message.channel.id):
        await BOT.process_commands(message)
        return

    if is_economy_banned(message.author.id):
        await BOT.process_commands(message)
        return

    # Delete messages from flashbanged users (text mute)
    if is_flashbanged(message.author.id):
        try:
            await message.delete()
            print(f"[FLASHBANG] Deleted message from flashbanged user {message.author.id}")
        except:
            pass
        return

    if message.attachments:
        reward = 50 * (2 if has_espresso_multiplier(message.author.id) else 1)
        update_balance(message.author.id, reward)
    elif check_cooldown(message.author.id, "chat", 5):
        reward = 30 * (2 if has_espresso_multiplier(message.author.id) else 1)
        update_balance(message.author.id, reward)

    await BOT.process_commands(message)

@BOT.event
async def on_reaction_add(reaction, user):
    if user.bot or not reaction.message.guild: return
    if is_channel_blacklisted(reaction.message.channel.id): return
    if is_economy_banned(user.id): return
    if check_cooldown(user.id, "reaction", 3):
        reward = 10 * (2 if has_espresso_multiplier(user.id) else 1)
        update_balance(user.id, reward)

@BOT.event
async def on_member_join(member):
    update_balance(member.id, 1000)

@BOT.event
async def on_voice_state_update(member, before, after):
    # نظام تتبع الصوت المحسن - مثل MEE6
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    
    # عضو انضم لغرفة صوتية
    if after.channel and not before.channel:
        now = datetime.now(timezone.utc).timestamp()
        cursor.execute("INSERT OR REPLACE INTO voice_tracking (user_id, guild_id, channel_id, join_timestamp, last_reward_timestamp) VALUES (?, ?, ?, ?, ?)",
                       (member.id, member.guild.id, after.channel.id, now, now))
        conn.commit()
    
    # عضو غادر غرفة صوتية أو انتقل
    elif before.channel and (not after.channel or after.channel != before.channel):
        cursor.execute("DELETE FROM voice_tracking WHERE user_id=?", (member.id,))
        conn.commit()
    
    conn.close()

# 🛡️ حماية الأسماء الإجبارية للجوكر وتثبيتها
@BOT.event
async def on_member_update(before, after):
    if before.bot: return
    if before.timed_out_until is None and after.timed_out_until is not None:
        update_balance(after.id, -100)
        return

    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT trolled_name, expire_time FROM joker_targets WHERE user_id=?", (after.id,))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        t_name, exp_str = res
        try:
            expire = datetime.strptime(exp_str, '%Y-%m-%d %H:%M:%S')
            if datetime.now(timezone.utc).replace(tzinfo=None) < expire:
                if after.display_name != t_name:
                    try: await after.edit(nick=t_name, reason="Joker Target Lock Active")
                    except: pass
        except: pass

# ==========================================
# 6. المهمات الدورية الخلفية وتنظيف الرتب
# ==========================================

@tasks.loop(seconds=10)
async def check_expired_effects():
    await BOT.wait_until_ready()
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    
    # سحب رتب المتجر تلقائياً فور نفاذ المدة من ديسكورد ومن قاعدة البيانات بدون بقائها
    cursor.execute("SELECT user_id, guild_id, effect_type FROM active_effects WHERE expire_time <= ? AND expire_time != 'PERMANENT'", (now_str,))
    expired = cursor.fetchall()
    for user_id, guild_id, effect_type in expired:
        guild = BOT.get_guild(guild_id)
        if guild:
            try:
                member = await guild.fetch_member(user_id)
                if effect_type == "flashbang":
                    try:
                        await member.edit(mute=False)
                        print(f"[FLASHBANG] Unmuted user {user_id} after effect expired")
                    except Exception as e:
                        print(f"[ERROR] Failed to unmute user {user_id}: {e}")
                        # Fallback: if unmute fails, try disconnecting and reconnecting
                        if member.voice and member.voice.channel:
                            try:
                                original_channel = member.voice.channel
                                await member.move_to(None, reason="Flashbang unmute fallback")
                                await asyncio.sleep(0.5)
                                await member.move_to(original_channel, reason="Flashbang unmute fallback")
                                print(f"[FLASHBANG] Used disconnect/reconnect fallback for user {user_id}")
                            except Exception as e2:
                                print(f"[ERROR] Fallback also failed for user {user_id}: {e2}")
                elif effect_type == "espresso":
                    role = discord.utils.get(guild.roles, name="Active Barista")
                    if role: await member.remove_roles(role)
                elif effect_type == "smugpler":
                    r = guild.get_role(ROLE_SMUGGLER_ID)
                    if r: await member.remove_roles(r)
                elif effect_type == "joker":
                    r = guild.get_role(ROLE_JOKER_ID)
                    if r: await member.remove_roles(r)
            except Exception as e:
                print(f"[ERROR] Failed to process expired effect for user {user_id}: {e}")
        cursor.execute("DELETE FROM active_effects WHERE user_id=? AND effect_type=?", (user_id, effect_type))
        
    cursor.execute("SELECT user_id, guild_id FROM joker_targets WHERE expire_time <= ?", (now_str,))
    expired_trolls = cursor.fetchall()
    for u_id, g_id in expired_trolls:
        g = BOT.get_guild(g_id)
        if g:
            try:
                m = await g.fetch_member(u_id)
                await m.edit(nick=None, reason="Joker Troll Expired")
            except: pass
        cursor.execute("DELETE FROM joker_targets WHERE user_id=?", (u_id,))
        
    conn.commit()
    conn.close()

# ==========================================
# 7. محرك كسب العملات الصوتي (نظام MEE6 - 200 BLZ بالساعة)
# ==========================================

@tasks.loop(minutes=1)
async def voice_rewards_engine():
    """
    محرك كسب العملات الصوتي - مثل MEE6
    يعطي 200 BLZ لكل ساعة قضاها العضو في غرفة صوتية مع شخص آخر
    """
    await BOT.wait_until_ready()
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    
    now = datetime.now(timezone.utc).timestamp()
    
    # جلب جميع الأعضاء في الغرف الصوتية
    cursor.execute("SELECT user_id, guild_id, channel_id, join_timestamp, last_reward_timestamp FROM voice_tracking")
    tracked_users = cursor.fetchall()
    
    for user_id, guild_id, channel_id, join_timestamp, last_reward_timestamp in tracked_users:
        guild = BOT.get_guild(guild_id)
        if not guild:
            continue
            
        member = guild.get_member(user_id)
        if not member or member.bot:
            cursor.execute("DELETE FROM voice_tracking WHERE user_id=?", (user_id,))
            continue
        
        # التحقق من أن العضو لا يزال في غرفة صوتية
        if not member.voice or not member.voice.channel:
            cursor.execute("DELETE FROM voice_tracking WHERE user_id=?", (user_id,))
            continue
        
        # التحقق من أن هناك شخص آخر في الغرفة (ليس وحده)
        voice_channel = member.voice.channel
        active_members = [m for m in voice_channel.members if not m.bot and not m.voice.self_mute and not m.voice.self_deaf]
        
        if len(active_members) < 2:
            continue  # لا يعطي مكافأة إذا كان وحده
        
        # حساب الوقت المنقضي منذ آخر مكافأة
        time_since_last_reward = now - last_reward_timestamp
        
        # جلب مكسب الصوت من قاعدة البيانات
        voice_reward = get_config_int("voice_reward") or 3  # الافتراضي 3 BLZ بالدقيقة
        
        # إعطاء مكافأة كل دقيقة
        if time_since_last_reward >= 60:  # كل دقيقة
            base_reward = voice_reward
            
            # مضاعف الإسبريسو
            if has_espresso_multiplier(user_id):
                base_reward *= 2
            
            cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (base_reward, user_id))
            cursor.execute("UPDATE voice_tracking SET last_reward_timestamp = ? WHERE user_id = ?", (now, user_id))
            
            conn.commit()
    
    conn.close()

# ==========================================
# 8. الأوامر البرمجية الحصرية للرتب الجديدة
# ==========================================

# [أوامر تاجر السوق السوداء - The Smuggler]
@BOT.command(name="smuggle-buy")
async def smuggle_buy(ctx, item_name: str):
    role = ctx.guild.get_role(ROLE_SMUGGLER_ID)
    if not role or role not in ctx.author.roles:
        await ctx.send("❌ هذا الأمر حصري فقط لأعضاء رتبة **تاجر السوق السوداء**!", delete_after=10)
        return
        
    item = item_name.lower().strip()
    if item not in ["flashbang", "shield", "espresso", "ticket", "ghost"]:
        await ctx.send("❌ الأيتم غير صحيح! الأيتمات المتاحة: (flashbang / shield / espresso / ticket / ghost)")
        return
        
    base_price = get_price(item)
    discounted_price = int(base_price * 0.70)
    
    async with db_lock:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (ctx.author.id,))
        res = cursor.fetchone()
        bal = res[0] if res else 1000
        
        if bal < discounted_price:
            await ctx.send(f"❌ رصيدك غير كافٍ! تحتاج إلى {discounted_price} BLZ بعد خصم السوق السوداء.")
            conn.close()
            return
            
        col_name = f"{item}_count"
        cursor.execute(f"UPDATE users SET balance = balance - ?, {col_name} = {col_name} + 1 WHERE user_id=?", (discounted_price, ctx.author.id))
        conn.commit()
        conn.close()
        
    log_action(ctx.author.id, "SMUGGLE_BUY", f"اشترى {item} بخصم السوق السوداء بسعر {discounted_price}")
    await ctx.send(f"🕵️‍♂️ **[مهرب السوق السوداء]:** تم شراء الأيتم بنجاح بخصم المهربين الحصري! تم خصم **{discounted_price} BLZ** فقط.")


@BOT.command(name="smuggle-sell")
async def smuggle_sell(ctx, item_name: str):
    role = ctx.guild.get_role(ROLE_SMUGGLER_ID)
    if not role or role not in ctx.author.roles:
        await ctx.send("❌ هذا الأمر حصري فقط لأعضاء رتبة **تاجر السوق السوداء**!", delete_after=10)
        return
        
    item = item_name.lower().strip()
    if item not in ["flashbang", "shield", "espresso", "ticket", "ghost"]:
        await ctx.send("❌ الأيتم غير صحيح للبيع!")
        return
        
    col_name = f"{item}_count"
    base_price = get_price(item)
    sell_cash = int(base_price * 0.50)
    
    async with db_lock:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute(f"SELECT {col_name} FROM users WHERE user_id=?", (ctx.author.id,))
        res = cursor.fetchone()
        
        if not res or res[0] <= 0:
            await ctx.send("❌ أنت لا تملك هذا الأيتم في حقيبتك لتبادل بيعه كاش!")
            conn.close()
            return
            
        cursor.execute(f"UPDATE users SET {col_name} = {col_name} - 1, balance = balance + ? WHERE user_id=?", (sell_cash, ctx.author.id))
        conn.commit()
        conn.close()
        
    log_action(ctx.author.id, "SMUGGLE_SELL", f"باع أيتم {item} للسوق السوداء كاش مقابل {sell_cash}")
    await ctx.send(f"🕵️‍♂️ **[مهرب السوق السوداء]:** قمت ببيع قطعة واحدة من {item} للبوت كاش بنجاح! وتم إضافة **+{sell_cash} BLZ** لحسابك.")


# [أمر رتبة المفجّر - The Kamikaze]
@BOT.command(name="explode")
async def explode_cmd(ctx):
    role = ctx.guild.get_role(ROLE_KAMIKAZE_ID)
    if not role or role not in ctx.author.roles:
        await ctx.send("❌ هذا الأمر حصري فقط لأعضاء رتبة **المفجّر (The Kamikaze)**!")
        return
        
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT kamikaze_uses FROM users WHERE user_id=?", (ctx.author.id,))
    res = cursor.fetchone()
    uses = res[0] if res else 0
    
    if uses <= 0:
        await ctx.send("❌ نفذت صلاحية التفجير المتاحة لك!")
        conn.close()
        return
    
    log_action(ctx.author.id, "KAMIKAZE_EXPLODE", f"استخدم أمر explode (المتبقي: {uses - 1})")
        
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ يجب أن تكون متواجداً داخل غرفة صوتية (Voice Channel) لتنفيذ التفجير!")
        conn.close()
        return
        
    voice_channel = ctx.author.voice.channel
    members_to_kick = list(voice_channel.members)
    
    cursor.execute("UPDATE users SET kamikaze_uses = MAX(0, kamikaze_uses - 1) WHERE user_id=?", (ctx.author.id,))
    conn.commit()
    conn.close()
    
    try: await ctx.author.remove_roles(role)
    except: pass
    
    log_action(ctx.author.id, "KAMIKAZE_EXPLODE", f"قام بتفجير الغرفة الصوتية {voice_channel.name}")
    await ctx.send(f"💀 **تم تفجير الغرفة بنجاح!**")
    
    for member in members_to_kick:
        try: await member.move_to(None, reason="Kamikaze Tactical Explosion!")
        except: pass


# [أمر رتبة الملك المشاغب - The Joker] (تم إدراج صد وحماية الدرع الكامل ضد هذا الهجوم هنا)
@BOT.command(name="troll")
async def troll_cmd(ctx, member: discord.Member, *, new_funny_name: str):
    role = ctx.guild.get_role(ROLE_JOKER_ID)
    if not role or role not in ctx.author.roles:
        await ctx.send("❌ هذا الأمر حصري فقط لأعضاء رتبة **الملك المشاغب (The Joker)**!")
        return

    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute("SELECT joker_trolls FROM users WHERE user_id=?", (ctx.author.id,))
    res = cursor.fetchone()
    trolls_left = res[0] if res else 0
    
    log_action(ctx.author.id, "JOKER_TROLL_ATTEMPT", f"حاول تغيير اسم {member.name} إلى {new_funny_name} (المتبقي: {trolls_left})")

    # 1) التحقق فوراً إذا كانت المحاولات منتهية مسبقاً وسحب الرتبة
    if trolls_left <= 0:
        await ctx.send("❌ لقد استهلكت الـ 3 محاولات المتاحة لك لتغيير الأسماء!")
        if role and role in ctx.author.roles:
            try:
                await ctx.author.remove_roles(role, reason="Blade X: استهلاك محاولات رتبة الجوكر كاملة")
                await ctx.send(f"👤 {ctx.author.mention} تم سحب رتبة الجوكر منك لانتهاء جميع محاولاتك الحصرية.")
            except Exception as e:
                print(f"[ERROR] Could not remove Joker role: {e}")
        conn.close()
        return

    # 2) هنا يبدأ كود الحماية وفحص الدرع للعضو المستهدف (السطر 1048 المصلح)
    cursor.execute("SELECT shield_count FROM users WHERE user_id=?", (member.id,))
    res_shield = cursor.fetchone()
    shield_count = res_shield[0] if res_shield else 0

    if shield_count > 0:
        await ctx.send(f"🛡️ لا يمكنك عمل ترول على {member.mention} لأنه محمي بدرع فعال!")
        conn.close()
        return

    # 3) تنفيذ أمر تغيير الاسم بنجاح وخصم المحاولة
    try:
        await member.edit(nick=f"[الملك المشاغب] {new_funny_name}")
        cursor.execute("UPDATE users SET joker_trolls = joker_trolls - 1 WHERE user_id=?", (ctx.author.id,))
        conn.commit()
        
        # تحديث القيمة الحالية بعد الخصم مباشرة
        trolls_left -= 1
        await ctx.send(f"🎰 تم تغيير اسم {member.mention} بنجاح! متبقي لديك: **{trolls_left}** محاولات.")
        
        # إذا كانت هذه هي المحاولة الأخيرة ووصل للصفر، نسحب الرتبة فوراً
        if trolls_left <= 0:
            if role and role in ctx.author.roles:
                await ctx.author.remove_roles(role, reason="Blade X: استهلاك المحاولة الأخيرة")
                await ctx.send(f"👤 {ctx.author.mention} تم سحب رتبة الجوكر منك الآن لانتهاء جميع محاولاتك!")
                
    except Exception as e:
        await ctx.send(f"❌ لم أتمكن من تغيير اسم العضو، قد تكون رتبته أعلى من رتبة البوت!")
        print(f"[ERROR] Nickname edit failed: {e}")

    conn.close()
    
    try:
        await member.edit(nick=new_funny_name, reason="Trolled by The Joker!")
        await ctx.send(f"🤡 **[الملك المشاغب]:** تم تبديل اسم {member.mention} إجبارياً إلى: **({new_funny_name})** ولن يستطيع تعديله لـ 4 ساعات كاملة!")
    except Exception as e:
        await ctx.send("❌ حدث خطأ أثناء تغيير اسم الضحية، يرجى مراجعة ترتيب رتبة البوت!")
    
    log_action(ctx.author.id, "JOKER_TROLL", f"تلاعب باسم {member.name} وجعله: {new_funny_name}")

# ==========================================
# 9. بقية الأوامر الإدارية والإعداد
# ==========================================

@BOT.tree.command(name="edit-panel", description="تغيير نص لوحة التحكم (Admin only)")
@commands.has_permissions(administrator=True)
async def edit_panel(interaction: discord.Interaction):
    """Open modal to edit Hub embed info (both languages)"""
    current_ar = get_config_str('info_text_ar')
    current_en = get_config_str('info_text_en')
    modal = EditPanelModal(current_ar, current_en)
    await interaction.response.send_modal(modal)


@BOT.tree.command(name="edit-bday-image", description="تغيير صورة هدية عيد الميلاد (Admin only)")
@commands.has_permissions(administrator=True)
async def edit_bday_image(interaction: discord.Interaction, image_url: str):
    """تغيير صورة هدية عيد الميلاد"""
    await interaction.response.defer(ephemeral=True)
    
    # حفظ الرابط الجديد في قاعدة البيانات
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO config (key, value_str, value_int) VALUES ('bday_gift_image', ?, NULL)", (image_url,))
    conn.commit()
    conn.close()
    
    await interaction.followup.send("✅ تم تحديث صورة هدية عيد الميلاد بنجاح!", ephemeral=True)
    log_action(interaction.user.id, "EDIT_BDAY_IMAGE", f"تغيير صورة هدية عيد الميلاد")


@BOT.tree.command(name="edit-info-ar", description="تعديل نص ال Info بالعربي (Admin only)")
@commands.has_permissions(administrator=True)
async def edit_info_ar(interaction: discord.Interaction):
    """Open modal to edit Arabic Info text"""
    current = get_config_str('info_text_ar')
    modal = SingleLangInfoModal('ar', current)
    await interaction.response.send_modal(modal)


@BOT.tree.command(name="edit-info-en", description="تعديل نص ال Info بالإنجليزي (Admin only)")
@commands.has_permissions(administrator=True)
async def edit_info_en(interaction: discord.Interaction):
    """Open modal to edit English Info text"""
    current = get_config_str('info_text_en')
    modal = SingleLangInfoModal('en', current)
    await interaction.response.send_modal(modal)


# -----------------------------------------
# New convenience slash commands to edit Hub Info per-language
# These open a modal pre-filled with the current Hub Info text so small edits are easy
# -----------------------------------------
@BOT.tree.command(name="edit-info-cp-ar", description="تعديل نص الـ Hub (Info) بالعربي — Admin only")
@commands.has_permissions(administrator=True)
async def edit_info_cp_ar(interaction: discord.Interaction):
    """Open modal pre-filled with current Hub Info (Arabic)"""
    current = get_config_str('info_text_ar')
    modal = SingleLangInfoModal('ar', current)
    await interaction.response.send_modal(modal)


@BOT.tree.command(name="edit-info-cp-en", description="Edit Hub Info (Info) English — Admin only")
@commands.has_permissions(administrator=True)
async def edit_info_cp_en(interaction: discord.Interaction):
    """Open modal pre-filled with current Hub Info (English)"""
    current = get_config_str('info_text_en')
    modal = SingleLangInfoModal('en', current)
    await interaction.response.send_modal(modal)


@BOT.tree.command(name="edit-bday-message", description="تعديل نص رسالة B-day gift (Admin only)")
@commands.has_permissions(administrator=True)
async def edit_bday_message(interaction: discord.Interaction, new_text: str):
    """تعديل نص رسالة B-day gift"""
    await interaction.response.defer(ephemeral=True)
    
    # حفظ النص الجديد في قاعدة البيانات
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO config (key, value_str, value_int) VALUES ('bday_gift_message', ?, NULL)", (new_text,))
    conn.commit()
    conn.close()
    
    await interaction.followup.send("✅ تم تحديث نص رسالة B-day gift بنجاح!", ephemeral=True)
    log_action(interaction.user.id, "EDIT_BDAY_MESSAGE", f"تعديل نص رسالة B-day gift")


@BOT.tree.command(name="edit-lucky-box", description="تعديل نسب Lucky Box (Admin only)")
@commands.has_permissions(administrator=True)
async def edit_lucky_box(interaction: discord.Interaction, common_percent: int, rare_percent: int, uncle_percent: int, legendary_percent: int):
    """تعديل نسب Lucky Box"""
    await interaction.response.defer(ephemeral=True)
    
    # التحقق من أن النسب صحيحة
    if common_percent + rare_percent + uncle_percent + legendary_percent != 100:
        await interaction.followup.send("❌ مجموع النسب يجب أن يكون 100%!", ephemeral=True)
        return
    
    # حفظ النسب في قاعدة البيانات
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO config (key, value_str, value_int) VALUES ('lucky_common', NULL, ?)", (common_percent,))
    cursor.execute("INSERT OR REPLACE INTO config (key, value_str, value_int) VALUES ('lucky_rare', NULL, ?)", (rare_percent,))
    cursor.execute("INSERT OR REPLACE INTO config (key, value_str, value_int) VALUES ('lucky_uncle', NULL, ?)", (uncle_percent,))
    cursor.execute("INSERT OR REPLACE INTO config (key, value_str, value_int) VALUES ('lucky_legendary', NULL, ?)", (legendary_percent,))
    conn.commit()
    conn.close()
    
    await interaction.followup.send(f"✅ تم تحديث نسب Lucky Box بنجاح!\nCommon: {common_percent}%\nRare: {rare_percent}%\nUncle: {uncle_percent}%\nLegendary: {legendary_percent}%", ephemeral=True)
    log_action(interaction.user.id, "EDIT_LUCKY_BOX", f"تعديل نسب Lucky Box: {common_percent}%/{rare_percent}%/{uncle_percent}%/{legendary_percent}%")


@BOT.tree.command(name="edit-earning-rates", description="تعديل مكسب الأعضاء عملات من كل فعل (Admin only)")
@commands.has_permissions(administrator=True)
async def edit_earning_rates(interaction: discord.Interaction, message_reward: int, voice_reward: int, interaction_reward: int):
    """تعديل مكسب الأعضاء عملات من كل فعل"""
    await interaction.response.defer(ephemeral=True)
    
    # حفظ القيم في قاعدة البيانات
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO config (key, value_str, value_int) VALUES ('message_reward', NULL, ?)", (message_reward,))
    cursor.execute("INSERT OR REPLACE INTO config (key, value_str, value_int) VALUES ('voice_reward', NULL, ?)", (voice_reward,))
    cursor.execute("INSERT OR REPLACE INTO config (key, value_str, value_int) VALUES ('interaction_reward', NULL, ?)", (interaction_reward,))
    conn.commit()
    conn.close()
    
    await interaction.followup.send(f"✅ تم تحديث مكسب الأعضاء بنجاح!\nمكسب الرسالة: {message_reward} BLZ\nمكسب الصوت: {voice_reward} BLZ/دقيقة\nمكسب التفاعل: {interaction_reward} BLZ", ephemeral=True)
    log_action(interaction.user.id, "EDIT_EARNING_RATES", f"تعديل مكسب الأعضاء: الرسالة {message_reward}, الصوت {voice_reward}, التفاعل {interaction_reward}")

@BOT.command(name="setup-hub")
@commands.has_permissions(administrator=True)
async def setup_hub(ctx):
    embed_url = get_config_str("dashboard_embed_img")
    
    # Use stored info text if available (per-language)
    info_ar = get_config_str('info_text_ar')
    info_en = get_config_str('info_text_en')
    # Build a bilingual embed showing both, prefer configured ones
    description = ''
    if info_ar:
        description += info_ar + "\n\n"
    if info_en:
        description += info_en + "\n\n"
    if not description:
        description = (
            "# لوحة التحكم • متجر العملات (BLZ EMOJI)\n"
            "# Control Hub • Currency Shop\n"
            "\n"
            "## مرحباً بك في محرك الاقتصاد الخاص بنا | Welcome to Our Economy System\n"
            "\n"
            "### 📋 الميزات الأساسية | Main Features:\n"
            "**📊 الحساب (Balance):** إدارة رصيدك وممتلكاتك بسهولة\n"
            "**🛒 المتجر (Shop):** شراء الرتب والمميزات الحصرية\n"
            "**📦 صندوق الحظ (Lucky Box):** فتح الصناديق واختبار حظك مع مكافآت عظيمة\n"
            "\n"
            "### 🎁 الأيتمات المتاحة | Available Items:\n"
            "**💥 فلاش بانج (Flashbang):** تعطيل مستخدم لمدة دقيقتين\n"
            "**🛡️ درع (Shield):** حماية من هجمات الفلاش\n"
            "**☕ إسبريسو (Espresso):** مضاعف نقاط X2 لمدة ساعتين\n"
            "**🎰 تذكرة الحظ (Lucky Ticket):** فرصة للفوز بـ 1200 BLZ\n"
            "**👻 الشبح (Ghost):** إرسال رسالة غامضة\n"
            "**📦 صندوق الحظ (Lucky Box):** فرصة للحصول على عناصر نادرة وجوائز كبرى\n"
            "\n"
            "⚙️ BLZ System Engine • Powered by Suli"
        )

    embed = discord.Embed(
        description=description,
        color=discord.Color.from_str("#595959")
    )
    if embed_url:
        embed.set_image(url=embed_url)
        
    view = ControlPanelView()
    await ctx.send(embed=embed, view=view)


@BOT.command(name="cp.image.change")
@commands.has_permissions(administrator=True)
async def cp_image_change(ctx, url: str):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE config SET value_str=? WHERE key='dashboard_embed_img'", (url,))
    conn.commit()
    conn.close()
    await ctx.send("✅ تم تحديث الرابط الجديد لصورة إمبيد لوحة التحكم بنجاح! يرجى كتابة الأمر `!setup-hub` لإعادة النشر.")


@BOT.command(name="user-profile")
async def user_profile(ctx, member: discord.Member = None):
    member = member or ctx.author
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (member.id,))
    bal_res = cursor.fetchone()
    balance = bal_res[0] if bal_res else 1000
    
    cursor.execute("SELECT action_type, details, timestamp FROM logs_history WHERE user_id=? ORDER BY id DESC LIMIT 5", (member.id,))
    history_rows = cursor.fetchall()
    conn.close()
    
    embed = discord.Embed(title=f"👤 التقرير الإداري الاقتصادي لـ {member.name}", color=discord.Color.orange())
    # include requester avatar as small author icon
    try:
        embed.set_author(name=f"Requested by {ctx.author.display_name}", icon_url=str(ctx.author.display_avatar.url))
    except:
        pass
    try:
        embed.set_thumbnail(url=member.display_avatar.url)
    except:
        pass
    embed.add_field(name="💰 الرصيد الحالي", value=f"**{balance} BLZ** {EMOJI_COIN}", inline=True)
    
    history_text = ""
    for act, det, ts in history_rows:
        history_text += f"• `[{ts}]` ({act}): {det}\n"
        
    embed.add_field(name="📜 آخر 5 عمليات مسجلة بالسجل الاقتصادي والعقوبات", value=history_text if history_text else "لا يوجد سجل عمليات مسجل له حتى الآن.", inline=False)
    await ctx.send(embed=embed)

@BOT.tree.command(name="user-profile", description="View a user's economic profile (slash)")
async def slash_user_profile(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (member.id,))
    bal_res = cursor.fetchone()
    balance = bal_res[0] if bal_res else 1000
    cursor.execute("SELECT action_type, details, timestamp FROM logs_history WHERE user_id=? ORDER BY id DESC LIMIT 5", (member.id,))
    history_rows = cursor.fetchall()
    conn.close()
    embed = discord.Embed(title=f"👤 التقرير الإداري الاقتصادي لـ {member.name}", color=discord.Color.orange())
    # include requester user avatar as author icon
    try:
        embed.set_author(name=f"Requested by {interaction.user.display_name}", icon_url=str(interaction.user.display_avatar.url))
    except:
        pass
    try:
        embed.set_thumbnail(url=member.display_avatar.url)
    except:
        pass
    embed.add_field(name="💰 الرصيد الحالي", value=f"**{balance} BLZ** {EMOJI_COIN}", inline=True)
    history_text = ""
    for act, det, ts in history_rows:
        history_text += f"• `[{ts}]` ({act}): {det}\n"
    embed.add_field(name="📜 آخر 5 عمليات مسجلة بالسجل الاقتصادي والعقوبات", value=history_text if history_text else "لا يوجد سجل عمليات مسجل له حتى الآن.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@BOT.tree.command(name="profile", description="View a user's economic profile (alias)")
async def slash_profile(interaction: discord.Interaction, member: discord.Member = None):
    # Delegate to the existing user-profile handler so logic stays in one place
    await slash_user_profile(interaction, member)


@BOT.command(name="give-item")
@commands.has_permissions(administrator=True)
async def give_item(ctx, member: discord.Member, item_name: str, quantity: int):
    db_col = f"{item_name.lower()}_count" if "espresso" not in item_name.lower() else "espresso_count"
    if "flash" in item_name.lower(): db_col = "flashbang_count"
    elif "shield" in item_name.lower(): db_col = "shield_count"
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (member.id,))
        cursor.execute(f"UPDATE users SET {db_col} = {db_col} + ? WHERE user_id=?", (quantity, member.id))
        conn.commit()
        await ctx.send(f"✅ تم منح {member.mention} عدد {quantity} من أيتم **{item_name}** بنجاح!")
    except: await ctx.send("❌ حدث خطأ، يرجى التأكد من كتابة اسم الأيتم بشكل صحيح.")
    finally: conn.close()

@BOT.command(name="take-item")
@commands.has_permissions(administrator=True)
async def take_item(ctx, member: discord.Member, item_name: str, quantity: int):
    db_col = f"{item_name.lower()}_count" if "espresso" not in item_name.lower() else "espresso_count"
    if "flash" in item_name.lower(): db_col = "flashbang_count"
    elif "shield" in item_name.lower(): db_col = "shield_count"
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    try:
        cursor.execute(f"UPDATE users SET {col_name} = MAX(0, {col_name} - ?) WHERE user_id=?", (quantity, member.id))
        conn.commit()
        await ctx.send(f"✅ تم مصادرة {quantity} من أيتم **{item_name}** من حقيبة {member.mention}!")
    except: await ctx.send("❌ حدث خطأ، تأكد من مطابقة اسم الأيتم.")
    finally: conn.close()

@BOT.command(name="clear-effects")
@commands.has_permissions(administrator=True)
async def clear_effects(ctx, member: discord.Member):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_effects WHERE user_id=?", (member.id,))
    cursor.execute("DELETE FROM joker_targets WHERE user_id=?", (member.id,))
    conn.commit()
    conn.close()
    try:
        if member.voice: await member.edit(mute=False)
        await member.timeout(None)
        await member.edit(nick=None)
    except: pass
    await ctx.send(f"✅ تم تطهير كل التأثيرات النشطة وإعادة الاسم الأصلي لـ {member.mention} بنجاح!")

@BOT.command(name="add-key")
@commands.has_permissions(administrator=True)
async def add_key(ctx, game_name: str, steam_key: str):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO steam_keys (game_name, key_code) VALUES (?, ?)", (game_name, steam_key))
        conn.commit()
        await ctx.send(f"🔑 تم شحن الخزنة بمفتاح جديد للعبة **[{game_name}]** بنجاح!")
    except sqlite3.IntegrityError: await ctx.send("❌ هذا المفتاح مضاف مسبقاً!")
    finally: conn.close()

@BOT.command(name="stock-keys")
@commands.has_permissions(administrator=True)
async def stock_keys(ctx):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT game_name, COUNT(*) FROM steam_keys WHERE used=0 GROUP BY game_name")
    rows = cursor.fetchall()
    conn.close()
    embed = discord.Embed(title="🔑 مخزن مفاتيح Steam الحالية", color=discord.Color.blue())
    if not rows: embed.description = "❌ المخزن فارغ تماماً حالياً! يرجى شحنه عبر `!add-key`."
    else:
        for g_name, count in rows: embed.add_field(name=f"🎮 {g_name}", value=f"المفاتيح المتاحة: **{count} مفتاح**", inline=False)
    await ctx.send(embed=embed)

@BOT.command(name="set-dashboard-channel")
@commands.has_permissions(administrator=True)
async def set_dashboard_channel(ctx, channel: discord.TextChannel):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE config SET value_int=? WHERE key='dashboard_channel'", (channel.id,))
    conn.commit()
    conn.close()
    await ctx.send(f"✅ تم تحديد قناة لوحة التحكم لتكون: {channel.mention}")

@BOT.command(name="set-language")
@commands.has_permissions(administrator=True)
async def set_language(ctx, lang_code: str):
    lang_code = lang_code.lower().strip()
    if lang_code not in ["ar", "en"]:
        await ctx.send("❌ اللغة غير مدعومة. استخدم: ar أو en. / Unsupported language. Use: ar or en.")
        return
    set_config_int('lang_default', 1 if lang_code == 'ar' else 0)
    await ctx.send(f"✅ تم ضبط اللغة الافتراضية إلى {'العربية' if lang_code == 'ar' else 'الإنجليزية'}! / Default language set to {lang_code}.")
    log_action(ctx.author.id, "SET_LANGUAGE", f"Set default language to {lang_code}")

@BOT.command(name="get-language")
async def get_language(ctx):
    current = get_lang()
    await ctx.send(f"✅ اللغة الافتراضية الحالية: {'العربية' if current == 'ar' else 'English'} ({current}).")

@BOT.command(name="enable-dashboard")
@commands.has_permissions(administrator=True)
async def enable_dashboard(ctx):
    set_config_int('enable_admin_dashboard', 1)
    port = get_config_int('admin_dashboard_port') or 8080
    try:
        start_admin_dashboard(port=port)
        await ctx.send(f"✅ تم تفعيل لوحة التحكم على الويب على المنفذ {port}. / Web admin dashboard enabled on port {port}.")
    except Exception as e:
        await ctx.send(f"❌ حدث خطأ عند تشغيل لوحة التحكم: {e}")
        return
    log_action(ctx.author.id, "ENABLE_DASHBOARD", "Enabled admin dashboard")

@BOT.command(name="disable-dashboard")
@commands.has_permissions(administrator=True)
async def disable_dashboard(ctx):
    set_config_int('enable_admin_dashboard', 0)
    await ctx.send("✅ تم تعطيل لوحة التحكم على الويب. / Web admin dashboard disabled.")
    log_action(ctx.author.id, "DISABLE_DASHBOARD", "Disabled admin dashboard")

@BOT.command(name="set-dashboard-token")
@commands.has_permissions(administrator=True)
async def set_dashboard_token(ctx, token: str):
    set_config_str('admin_dashboard_token', token)
    await ctx.send("✅ تم تعيين رمز الوصول للوحة التحكم. استخدمه في عنوان URL كـ ?token=<token>")
    log_action(ctx.author.id, "SET_DASHBOARD_TOKEN", "Updated admin dashboard token")

@BOT.command(name="set-dashboard-port")
@commands.has_permissions(administrator=True)
async def set_dashboard_port(ctx, port: int):
    if port < 1 or port > 65535:
        await ctx.send("❌ رقم المنفذ غير صالح. اختر رقم بين 1 و 65535.")
        return
    set_config_int('admin_dashboard_port', port)
    if admin_dashboard_thread and admin_dashboard_thread.is_alive():
        await ctx.send(f"✅ تم ضبط منفذ لوحة التحكم إلى {port}. / Dashboard port set to {port}.\n⚠️ إذا كانت اللوحة تعمل حالياً، فأعد تشغيل البوت لتطبيق هذا المنفذ الجديد.")
    else:
        await ctx.send(f"✅ تم ضبط منفذ لوحة التحكم إلى {port}. / Dashboard port set to {port}.")
    log_action(ctx.author.id, "SET_DASHBOARD_PORT", f"Set dashboard port to {port}")

@BOT.command(name="dashboard")
@commands.has_permissions(administrator=True)
async def dashboard(ctx):
    port = get_config_int('admin_dashboard_port') or 8080
    token = get_config_str('admin_dashboard_token')
    if not token:
        await ctx.send("❌ لم يتم تعيين رمز لوحة التحكم بعد. استخدم !set-dashboard-token <token>")
        return
    await ctx.send(
        f"🔐 رابط لوحة التحكم:\n`http://localhost:{port}/?token={token}`\n" \
        "إذا كان البوت يعمل على سيرفر آخر، استبدل localhost بعنوان السيرفر."
    )

@BOT.command(name="ban-economy")
@commands.has_permissions(administrator=True)
async def ban_economy(ctx, member: discord.Member, duration_hours: int, *, reason: str = "Restricted by admin"):
    if duration_hours <= 0:
        await ctx.send("❌ يجب أن تكون المدة أكبر من صفر ساعة!")
        return
    ban_until = (datetime.now(timezone.utc) + timedelta(hours=duration_hours)).strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (member.id,))
    cursor.execute("UPDATE users SET economy_banned_until = ?, economy_ban_reason = ? WHERE user_id=?", (ban_until, reason, member.id))
    conn.commit()
    conn.close()
    await ctx.send(f"⛔ تم حظر {member.mention} من استخدام النظام الاقتصادي لمدة {duration_hours} ساعة. / Economy access blocked for {duration_hours} hours.")
    log_action(ctx.author.id, "BAN_ECONOMY", f"Banned {member.name} from economy for {duration_hours}h. Reason: {reason}")

@BOT.command(name="unban-economy")
@commands.has_permissions(administrator=True)
async def unban_economy(ctx, member: discord.Member):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET economy_banned_until = NULL, economy_ban_reason = NULL WHERE user_id=?", (member.id,))
    conn.commit()
    conn.close()
    await ctx.send(f"✅ تم رفع حظر النظام الاقتصادي عن {member.mention}. / Economy access restored.")
    log_action(ctx.author.id, "UNBAN_ECONOMY", f"Unbanned {member.name} from economy")

@BOT.command(name="blacklist-channel")
@commands.has_permissions(administrator=True)
async def blacklist_channel(ctx, channel: discord.TextChannel):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO blacklisted_channels (channel_id) VALUES (?)", (channel.id,))
        conn.commit()
        await ctx.send(f"⛔ تم حظر القناة {channel.mention} من كسب نقاط العملات بنجاح!")
    except sqlite3.IntegrityError:
        cursor.execute("DELETE FROM blacklisted_channels WHERE channel_id=?", (channel.id,))
        conn.commit()
        await ctx.send(f"✅ تم إلغاء حظر القناة وإعادتها لنظام الكسب.")
    finally: conn.close()

@BOT.command(name="set-log-channel")
@commands.has_permissions(administrator=True)
async def set_log_channel(ctx, channel: discord.TextChannel):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE config SET value_int=? WHERE key='log_channel'", (channel.id,))
    conn.commit()
    conn.close()
    await ctx.send(f"📝 تم ربط قناة سجل العمليات (Logs) بنجاح على الروم: {channel.mention}")

@BOT.command(name="add-blz")
@commands.has_permissions(administrator=True)
async def add_blz(ctx, member: discord.Member, amount: int):
    update_balance(member.id, amount)
    await ctx.send(f"✅ Added {amount} BLZ to {member.mention}.")

@BOT.command(name="set-price")
@commands.has_permissions(administrator=True)
async def set_price(ctx, item_name: str, new_price: int):
    key = f"price_{item_name.lower()}"
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE config SET value_int=? WHERE key=?", (new_price, key))
    conn.commit()
    conn.close()
    await ctx.send(f"⚙️ Price of **{item_name}** dynamically adjusted to **{new_price} BLZ**!")

# ==========================================
# 10. أوامر السلاش المحدثة للتحكم الإداري الكامل
# ==========================================

@BOT.tree.command(name="admin-set-price", description="تعديل أسعار الأيتمات والمنتجات المعروضة بالمتجر ديناميكياً")
@app_commands.checks.has_permissions(administrator=True)
async def slash_set_price(interaction: discord.Interaction, item_name: str, new_price: int):
    key = f"price_{item_name.lower().strip()}"
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE config SET value_int=? WHERE key=?", (new_price, key))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"⚙️ تم تعديل سعر منتج **{item_name}** في المتجر بنجاح إلى **{new_price} BLZ**!", ephemeral=True)

@BOT.tree.command(name="admin-give-item", description="منح وشحن قطع أيتمات إضافية في حقيبة عضو محدد بالسيرفر")
@app_commands.checks.has_permissions(administrator=True)
async def slash_give_item(interaction: discord.Interaction, member: discord.Member, item_name: str, quantity: int):
    db_col = f"{item_name.lower().strip()}_count"
    if "flash" in item_name.lower(): db_col = "flashbang_count"
    elif "shield" in item_name.lower(): db_col = "shield_count"
    elif "espresso" in item_name.lower(): db_col = "espresso_count"
    elif "ticket" in item_name.lower(): db_col = "ticket_count"
    elif "ghost" in item_name.lower(): db_col = "ghost_count"
    
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (member.id,))
        cursor.execute(f"UPDATE users SET {db_col} = {db_col} + ? WHERE user_id=?", (quantity, member.id))
        conn.commit()
        await interaction.response.send_message(f"✅ تم بنجاح شحن حقيبة {member.mention} بـ {quantity} قطع من الأيتم [{item_name}].", ephemeral=True)
    except:
        await interaction.response.send_message("❌ فشل العثور على اسم الأيتم المحدد، يرجى كتابته بشكل صحيح.", ephemeral=True)
    finally: conn.close()

@BOT.tree.command(name="admin-add-steam-key", description="شحن خزنة السحب الكبرى بمفاتيح ألعاب ستيم حقيقية جديدة")
@app_commands.checks.has_permissions(administrator=True)
async def slash_add_key(interaction: discord.Interaction, game_name: str, steam_key: str):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO steam_keys (game_name, key_code) VALUES (?, ?)", (game_name, steam_key))
        conn.commit()
        await interaction.response.send_message(f"🔑 تم إيداع كود لعبة **[{game_name}]** الجديد داخل المخزن بنجاح!", ephemeral=True)
    except sqlite3.IntegrityError:
        await interaction.response.send_message("❌ هذا المفتاح مكرر ومضاف في الخزنة مسبقاً!", ephemeral=True)
    finally: conn.close()

@BOT.tree.command(name="admin-control-panel-image", description="تحديث وتغيير رابط صورة الإمبيد الرئيسية للوحة تحكم المتجر والـ Hub")
@app_commands.checks.has_permissions(administrator=True)
async def slash_cp_image_change(interaction: discord.Interaction, image_url: str):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE config SET value_str=? WHERE key='dashboard_embed_img'", (image_url,))
    conn.commit()
    conn.close()
    await interaction.response.send_message("✅ تم تحديث مظهر ورابط صورة لوحة الـ Hub بنجاح! اكتب `!setup-hub` لنشر اللوحة المحدثة بالكامل.", ephemeral=True)

# ==========================================
# 11. أوامر السلاش الإدارية الجديدة المطلوبة
# ==========================================

@BOT.tree.command(name="admin-wipe-user", description="إزالة جميع الفلوس وجميع الأيتمات لعضو محدد")
@app_commands.checks.has_permissions(administrator=True)
async def slash_wipe_user(interaction: discord.Interaction, member: discord.Member):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (member.id,))
        cursor.execute("UPDATE users SET balance = 0, flashbang_count = 0, shield_count = 0, espresso_count = 0, ticket_count = 0, ghost_count = 0, kamikaze_uses = 0, joker_trolls = 0 WHERE user_id = ?", (member.id,))
        conn.commit()
        await interaction.response.send_message(f"✅ تم إزالة جميع الفلوس والأيتمات من {member.mention} بنجاح!", ephemeral=True)
        log_action(interaction.user.id, "ADMIN_WIPE_USER", f"قام بمسح جميع بيانات {member.name}")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)
    finally: conn.close()

@BOT.tree.command(name="admin-transfer-coins", description="تحويل عملات من شخص لشخص معين")
@app_commands.checks.has_permissions(administrator=True)
async def slash_transfer_coins(interaction: discord.Interaction, from_member: discord.Member, to_member: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ يجب أن يكون المبلغ أكبر من صفر!", ephemeral=True)
        return
    
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (from_member.id,))
        res = cursor.fetchone()
        from_bal = res[0] if res else 0
        
        if from_bal < amount:
            await interaction.response.send_message(f"❌ رصيد {from_member.mention} غير كافٍ! رصيده الحالي: {from_bal} BLZ", ephemeral=True)
            return
        
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, from_member.id))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, to_member.id))
        conn.commit()
        
        await interaction.response.send_message(f"✅ تم تحويل **{amount} BLZ** من {from_member.mention} إلى {to_member.mention} بنجاح!", ephemeral=True)
        log_action(interaction.user.id, "ADMIN_TRANSFER", f"حول {amount} BLZ من {from_member.name} إلى {to_member.name}")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)
    finally: conn.close()

@BOT.tree.command(name="admin-set-log-channel", description="تعيين روم اللوجز من خلال السلاش")
@app_commands.checks.has_permissions(administrator=True)
async def slash_set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE config SET value_int=? WHERE key='log_channel'", (channel.id,))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"📝 تم تعيين قناة اللوجز بنجاح: {channel.mention}", ephemeral=True)
    log_action(interaction.user.id, "ADMIN_SET_LOG_CHANNEL", f"عين قناة اللوجز: {channel.name}")

@BOT.tree.command(name="admin-ban-shop", description="منع شخص ما مؤقتا من استخدام الشوب مع إرسال السبب بالخاص")
@app_commands.checks.has_permissions(administrator=True)
async def slash_ban_shop(interaction: discord.Interaction, member: discord.Member, duration_hours: int, reason: str):
    if duration_hours <= 0:
        await interaction.response.send_message("❌ يجب أن تكون المدة أكبر من صفر ساعة!", ephemeral=True)
        return
    
    ban_until = (datetime.now(timezone.utc) + timedelta(hours=duration_hours)).strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (member.id,))
        cursor.execute("UPDATE users SET shop_banned_until = ?, shop_ban_reason = ? WHERE user_id = ?", (ban_until, reason, member.id))
        conn.commit()
        
        await interaction.response.send_message(f"✅ تم منع {member.mention} من استخدام المتجر لمدة **{duration_hours} ساعة**!", ephemeral=True)
        log_action(interaction.user.id, "ADMIN_SHOP_BAN", f"منع {member.name} من الشوب لمدة {duration_hours} ساعة. السبب: {reason}")
        
        # إرسال السبب للعضو على الخاص
        try:
            embed = discord.Embed(
                title="⚠️ إشعار منع من المتجر",
                description=f"لقد تم منعك مؤقتاً من استخدام متجر السيرفر.\n\n**المدة:** {duration_hours} ساعة\n**السبب:** {reason}\n**تنتهي في:** {ban_until}",
                color=discord.Color.red()
            )
            await member.send(embed=embed)
        except:
            pass  # العضو قد يكون أغلق خاصه
            
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)
    finally: conn.close()

@BOT.tree.command(name="admin-unban-shop", description="إلغاء منع شخص من استخدام الشوب")
@app_commands.checks.has_permissions(administrator=True)
async def slash_unban_shop(interaction: discord.Interaction, member: discord.Member):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET shop_banned_until = NULL, shop_ban_reason = NULL WHERE user_id = ?", (member.id,))
        conn.commit()
        
        await interaction.response.send_message(f"✅ تم إلغاء منع {member.mention} من استخدام المتجر بنجاح!", ephemeral=True)
        log_action(interaction.user.id, "ADMIN_SHOP_UNBAN", f"ألغى منع {member.name} من الشوب")
        
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)
    finally: conn.close()

# ==========================================
# 12. الإقلاع والتشغيل الكامل للمحركات الصامتة
# ==========================================

def resolve_user_to_id(q):
    """Resolve a user identifier (numeric ID, mention <@id>, username#discriminator, or username/display name)
    to a numeric user ID using the bot cache and available guild member caches."""
    import re
    if not q:
        return None
    q = str(q)
    # remove control and zero-width characters that may come from URL encoding or paste
    q = re.sub(r'[\x00-\x1f\x7f\u200b\u200e\u200f\u202a-\u202e]', '', q)
    q = q.strip()
    # drop a trailing solitary '#' (common paste)
    if q.endswith('#'):
        q = q[:-1].strip()
    # direct numeric id
    if q.isdigit():
        try:
            return int(q)
        except:
            pass
    # mention like <@!123> or any digits in string
    m = re.search(r'(\d{17,20})', q)
    if m:
        try:
            return int(m.group(1))
        except:
            pass
    # username#discriminator (exact)
    if '#' in q:
        name, disc = q.rsplit('#', 1)
        if disc.isdigit():
            for u in BOT.users:
                try:
                    if u.name == name and u.discriminator == disc:
                        return u.id
                except:
                    continue
            # search guild member caches for exact tag
            for g in BOT.guilds:
                for mm in g.members:
                    try:
                        if mm.name == name and mm.discriminator == disc:
                            return mm.id
                    except:
                        continue
        else:
            # if no valid discriminator, fall back to bare name
            q = q.replace('#', '')
    # fallback: match by username (case-insensitive) in cached users
    for u in BOT.users:
        try:
            if u.name.lower() == q.lower():
                return u.id
        except:
            continue
    # fallback: search guild members by name or display_name
    for g in BOT.guilds:
        for mm in g.members:
            try:
                if mm.name.lower() == q.lower() or mm.display_name.lower() == q.lower():
                    return mm.id
            except:
                continue
    return None


def start_admin_dashboard(port=8080):
    class AdminHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            # Serve static assets (font, logo)
            if path.startswith('/static/'):
                try:
                    if path == '/static/readex.ttf':
                        with open(r"c:\\Users\\Sulim\\Downloads\\ReadexPro-VariableFont_HEXP,wght.ttf", 'rb') as f:
                            data = f.read()
                        self.send_response(200)
                        self.send_header('Content-type', 'font/ttf')
                        self.send_header('Content-Length', str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        return
                    elif path == '/static/bxlogo.png':
                        with open(r"c:\\Users\\Sulim\\AppData\\Roaming\\Code\\User\\globalStorage\\github.copilot-chat\\copilot-cli-images\\1781582742594-wzr1zonr.png", 'rb') as f:
                            data = f.read()
                        self.send_response(200)
                        self.send_header('Content-type', 'image/png')
                        self.send_header('Content-Length', str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        return
                except Exception as e:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Not found")
                    return

            # serve favicon without requiring token to avoid browser 403 noise
            if path == '/favicon.ico':
                self.send_response(204)
                self.end_headers()
                return

            token = query.get('token', [''])[0]
            expected_token = get_config_str('admin_dashboard_token')
            # slot to inject profile view HTML
            profile_html = ''
            if get_config_int('enable_admin_dashboard') != 1 or not expected_token or token != expected_token:
                self.send_response(403)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(b"<html><body><h1>403 Forbidden</h1><p>Admin dashboard access denied.</p></body></html>")
                return

            action = query.get('action', [''])[0]
            action_message = ""

            try:
                if action == 'set-lang':
                    lang = query.get('lang', [''])[0]
                    if lang in ('ar', 'en'):
                        set_config_int('lang_default', 1 if lang == 'ar' else 0)
                        action_message = f"Default language set to {lang}."
                elif action == 'enable-dashboard':
                    set_config_int('enable_admin_dashboard', 1)
                    action_message = "Dashboard enabled."
                elif action == 'disable-dashboard':
                    set_config_int('enable_admin_dashboard', 0)
                    action_message = "Dashboard disabled."
                elif action == 'set-port':
                    port_value = query.get('port', [''])[0]
                    try:
                        port_num = int(port_value)
                        if 1 <= port_num <= 65535:
                            set_config_int('admin_dashboard_port', port_num)
                            action_message = f"Dashboard port updated to {port_num}."
                    except ValueError:
                        pass
                elif action == 'set-token':
                    token_value = query.get('new_token', [''])[0]
                    if token_value:
                        set_config_str('admin_dashboard_token', token_value)
                        action_message = "Dashboard token updated."
                elif action == 'edit-info-form':
                    lang = query.get('lang', [''])[0]
                    if lang in ('ar','en'):
                        try:
                            cur_text = get_config_str('info_text_ar' if lang == 'ar' else 'info_text_en') or ''
                        except:
                            cur_text = ''
                        def _esc(s):
                            return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'", '&#39;')
                        cur_esc = _esc(cur_text)
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.end_headers()
                        html_form = f'''<html><body style="background:#222;color:#fff;font-family:Arial;padding:20px;">
                        <h2>Edit Info ({'Arabic' if lang == 'ar' else 'English'})</h2>
                        <form method="get">
                        <input type="hidden" name="token" value="{expected_token}">
                        <input type="hidden" name="action" value="save-info">
                        <input type="hidden" name="lang" value="{lang}">
                        <textarea name="new_text" style="width:100%;height:400px;background:#333;color:#fff;border:0;padding:12px;border-radius:6px;">{cur_esc}</textarea>
                        <div style="margin-top:12px;">
                        <button class="dash-btn" type="submit" style="background:#333333;color:#fff;padding:10px 14px;border-radius:8px;border:0;">Save</button>
                        </div>
                        </form></body></html>'''
                        self.wfile.write(html_form.encode('utf-8'))
                        return
                elif action == 'save-info':
                    lang = query.get('lang', [''])[0]
                    new_text = query.get('new_text', [''])[0]
                    if lang in ('ar','en') and new_text is not None:
                        try:
                            if lang == 'ar':
                                set_config_str('info_text_ar', new_text)
                            else:
                                set_config_str('info_text_en', new_text)
                            action_message = "Info text updated."
                        except Exception:
                            action_message = "Unable to update info text."
                elif action == 'view-profile':
                    q = query.get('user', [''])[0]
                    uid = resolve_user_to_id(q)
                    if uid:
                        try:
                            conn = sqlite3.connect(DB_NAME, timeout=10.0)
                            cursor = conn.cursor()
                            cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
                            res = cursor.fetchone()
                            balance = res[0] if res else 0
                            cursor.execute("SELECT timestamp, action_type, details FROM logs_history WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,))
                            user_logs = cursor.fetchall()
                            conn.close()
                        except Exception:
                            user_logs = []
                            balance = 0
                        u = BOT.get_user(uid)
                        uname = f"{u.name}#{u.discriminator}" if u else str(uid)
                        avatar_url = ''
                        try:
                            avatar_url = str(u.display_avatar.url) if u else ''
                        except:
                            avatar_url = ''
                        profile_html = f"<div class='panel' style='margin-top:12px;'><h3>Profile: {uname}</h3>"
                        if avatar_url:
                            profile_html += f"<img src='{avatar_url}' style='width:64px;height:64px;border-radius:8px;float:right;margin-left:8px;'>"
                        profile_html += f"<div>Balance: <strong>{balance} BLZ</strong></div><div style='margin-top:8px;'><strong>Recent Logs</strong>"
                        for lts, ltype, ldet in user_logs:
                            profile_html += f"<div style='padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04);'><strong>{lts}</strong> [{ltype}] - {ldet}</div>"
                        profile_html += "</div></div>"
                        action_message = f"Profile loaded for {uname}."
                    else:
                        action_message = "User not found (try ID or mention)."
                elif action == 'wipe-user':
                    q = query.get('user_id', [''])[0]
                    uid = resolve_user_to_id(q)
                    if uid:
                        try:
                            conn = sqlite3.connect(DB_NAME, timeout=10.0)
                            cursor = conn.cursor()
                            cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
                            cursor.execute("UPDATE users SET balance = 0, flashbang_count = 0, shield_count = 0, espresso_count = 0, ticket_count = 0, ghost_count = 0, kamikaze_uses = 0, joker_trolls = 0 WHERE user_id = ?", (uid,))
                            conn.commit()
                            conn.close()
                            action_message = f"Wiped user data for {uid}."
                        except Exception:
                            action_message = "Unable to wipe user."
                    else:
                        action_message = "User not found to wipe."
                elif action == 'ban-shop':
                    user_id_raw = query.get('user_id', [''])[0]
                    hours = int(query.get('hours', ['0'])[0]) if query.get('hours') else 0
                    reason = query.get('reason', ['Manual shop ban'])[0]
                    uid = resolve_user_to_id(user_id_raw)
                    if uid and hours > 0:
                        ban_until = (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
                        conn = sqlite3.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (int(uid),))
                        cursor.execute("UPDATE users SET shop_banned_until = ?, shop_ban_reason = ? WHERE user_id=?", (ban_until, reason, int(uid)))
                        conn.commit()
                        conn.close()
                        action_message = f"Shop ban for {uid} active until {ban_until}."
                elif action == 'unban-shop':
                    user_id_raw = query.get('user_id', [''])[0]
                    uid = resolve_user_to_id(user_id_raw)
                    if uid:
                        conn = sqlite3.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        cursor.execute("UPDATE users SET shop_banned_until = NULL, shop_ban_reason = NULL WHERE user_id=?", (int(uid),))
                        conn.commit()
                        conn.close()
                        action_message = f"Shop ban removed for {uid}."
                elif action == 'ban-economy':
                    user_id_raw = query.get('user_id', [''])[0]
                    hours = int(query.get('hours', ['0'])[0]) if query.get('hours') else 0
                    reason = query.get('reason', ['Manual economy ban'])[0]
                    uid = resolve_user_to_id(user_id_raw)
                    if uid and hours > 0:
                        ban_until = (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
                        conn = sqlite3.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (int(uid),))
                        cursor.execute("UPDATE users SET economy_banned_until = ?, economy_ban_reason = ? WHERE user_id=?", (ban_until, reason, int(uid)))
                        conn.commit()
                        conn.close()
                        action_message = f"Economy ban for {uid} active until {ban_until}."
                elif action == 'unban-economy':
                    user_id_raw = query.get('user_id', [''])[0]
                    uid = resolve_user_to_id(user_id_raw)
                    if uid:
                        conn = sqlite3.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        cursor.execute("UPDATE users SET economy_banned_until = NULL, economy_ban_reason = NULL WHERE user_id=?", (int(uid),))
                        conn.commit()
                        conn.close()
                        action_message = f"Economy ban removed for {uid}."
            except Exception:
                action_message = "Unable to process action."

            try:
                conn = sqlite3.connect(DB_NAME, timeout=10.0)
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 20")
                top = cursor.fetchall()
                cursor.execute("SELECT timestamp, action_type, details FROM logs_history ORDER BY id DESC LIMIT 30")
                logs = cursor.fetchall()
                cursor.execute("SELECT user_id, effect_type, expire_time FROM active_effects ORDER BY expire_time DESC LIMIT 20")
                active_effects = cursor.fetchall()
                cursor.execute("SELECT channel_id FROM blacklisted_channels")
                blacklisted = [row[0] for row in cursor.fetchall()]
                cursor.execute("SELECT user_id, shop_banned_until, shop_ban_reason FROM users WHERE shop_banned_until IS NOT NULL")
                shop_bans = cursor.fetchall()
                cursor.execute("SELECT user_id, economy_banned_until, economy_ban_reason FROM users WHERE economy_banned_until IS NOT NULL")
                economy_bans = cursor.fetchall()
                conn.close()
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Error reading DB: {e}".encode())
                return

            # If a request asks to view full logs, prepare detailed logs HTML for injection
            if action == 'view-logs':
                try:
                    logs_html = "<div class='panel' style='margin-top:12px;'><h3>Full Logs</h3><div style='max-height:420px; overflow:auto; padding-top:8px;'>"
                    for ts, atype, det in logs:
                        logs_html += f"<div style='padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04);'><strong>{ts}</strong> <span style='opacity:0.85'>[{atype}]</span><div style='opacity:0.9;margin-top:4px'>{det}</div></div>"
                    logs_html += "</div></div>"
                    profile_html = logs_html
                    action_message = "Showing full logs."
                except Exception:
                    profile_html = "<div class='panel' style='margin-top:12px;'><h3>Full Logs</h3><div>Unable to load logs.</div></div>"

            masked_token = expected_token[:4] + '...' if expected_token else '(not set)'

            # Build modern dashboard HTML with custom theme and font
            lang_label = 'العربية' if get_config_int('lang_default') == 1 else 'English'
            bx_logo_path = r"c:\Users\Sulim\AppData\Roaming\Code\User\globalStorage\github.copilot-chat\copilot-cli-images\1781582742594-wzr1zonr.png"
            font_path = r"c:\Users\Sulim\Downloads\ReadexPro-VariableFont_HEXP,wght.ttf"

            html = f"""
            <!doctype html>
            <html lang="en">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>Blade X Admin Dashboard</title>
              <style>
                @font-face {{
                  font-family: 'ReadexProCustom';
                  src: url('/static/readex.ttf') format('truetype');
                  font-weight: 100 900;
                }}
                :root {{
                  --bg: #353535;
                  --card: #595959;
                  --text: #ffffff;
                  --accent: #2dbb8f;
                }}
                * {{ box-sizing: border-box; font-family: 'ReadexProCustom', Arial, sans-serif; color: var(--text); }}
                body {{ margin:0; background:var(--bg); color:var(--text); }}
                .container {{ max-width:1200px; margin:24px auto; padding:20px; }}
                .header {{ display:flex; align-items:center; gap:16px; }}
                .logo {{ width:96px; height:96px; background:#000; padding:8px; border-radius:8px; display:flex; align-items:center; justify-content:center; }}
                .title {{ font-size:24px; font-weight:700; }}
                .grid {{ display:grid; grid-template-columns: 1fr 360px; gap:18px; margin-top:18px; }}
                .panel {{ background:var(--card); padding:16px; border-radius:10px; box-shadow: 0 4px 12px rgba(0,0,0,0.35); }}
                .panel h3 {{ margin-top:0; color:var(--text); }}
                .buttons-grid {{ display:grid; grid-template-columns: repeat(4,1fr); gap:10px; }}
                .top-sections {{ margin-top:14px; }}
                .container-sections {{ display:flex; gap:12px; justify-content:space-between; margin-bottom:12px; }}
                button.section-item {{ background:#2b2b2b; color:#fff; padding:10px 14px; border-radius:8px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); font-weight:700; border:0; cursor:pointer; }}
                button.section-item:hover {{ transform:translateY(-2px); box-shadow:0 6px 16px rgba(0,0,0,0.35); }}
                .cmd-pill {{ background:#444; padding:6px 10px; border-radius:8px; color:#fff; font-weight:600; }}
                .dash-btn {{ background:#333333; color:#fff; border:0; padding:12px 14px; border-radius:10px; cursor:pointer; display:inline-flex; align-items:center; gap:8px; justify-content:center; transition: transform .12s, box-shadow .12s, background .12s; box-shadow: 0 4px 12px rgba(0,0,0,0.35); font-weight:700; }}
                .dash-btn:hover {{ transform: translateY(-3px); background:#3d3d3d; box-shadow: 0 8px 24px rgba(0,0,0,0.45); }}
                .site-footer {{ margin-top:24px; text-align:center; font-size:13px; color:var(--text); opacity:0.9; padding:18px 0; }}
                .small-input {{ width:100%; padding:8px; border-radius:6px; border:0; background:#444; color:var(--text); margin-top:8px; }}
                .footer {{ margin-top:18px; text-align:center; font-size:13px; color:var(--text); opacity:0.9; }}
                .bottom-actions {{ display:flex; gap:8px; justify-content:flex-start; margin-top:12px; }}
                .icon {{ width:20px; height:20px; filter:invert(1); }}
                .user-list {{ max-height:220px; overflow:auto; margin-top:8px; }}
                table {{ width:100%; border-collapse:collapse; color:var(--text); }}
                th, td {{ padding:8px; text-align:left; border-bottom:1px solid rgba(255,255,255,0.06); }}
                .signature {{ font-size:12px; margin-top:18px; font-weight:600; }}
              </style>
            </head>
            <body>
              <div class="container">
                <div class="header">
                  <div class="logo"><img src="/static/bxlogo.png" alt="BX" style="max-width:100%; max-height:100%;"></div>
                  <div>
                    <div class="title">Blade X • Admin Dashboard</div>
                    <div style="opacity:0.8; margin-top:6px;">Language: {lang_label} • Port: {get_config_int('admin_dashboard_port') or port}</div>
                    <div style="margin-top:8px;color:#9cdfb8;font-weight:700;">{action_message}</div>
                  </div>
                </div>

                <div class="top-sections">
                    <div class="container-sections">
                        <button class="section-item" onclick="showSection('admin-guide')">Administration Guide</button>
                        <button class="section-item" onclick="showSection('moderation-tools')">Moderation Tools</button>
                        <button class="section-item" onclick="showSection('economy-settings')">Economy Settings</button>
                        <button class="section-item" onclick="showSection('logs-auditing')">Logs & Auditing</button>
                    </div>
                    <div id="section-area"></div>
                    </div>
                </div>
                <div class="grid">
                  <div>
                    <div class="panel">
                      <h3>Quick Actions</h3>
                      <div class="buttons-grid">
                        <!-- Example action buttons; click to show form below -->
                        <button class="dash-btn" onclick="showForm('ban-shop')">🛒 Ban Shop</button>
                        <button class="dash-btn" onclick="showForm('ban-economy')">💸 Ban Economy</button>
                        <button class="dash-btn" onclick="showForm('unban-shop')">✅ Unban Shop</button>
                        <button class="dash-btn" onclick="showForm('unban-economy')">✅ Unban Economy</button>

                        <button class="dash-btn" onclick="showForm('set-token')">🔑 Set Token</button>
                        <button class="dash-btn" onclick="showForm('set-port')">🔌 Set Port</button>
                        <button class="dash-btn" onclick="showForm('set-lang')">🌐 Set Default Lang</button>
                        <button class="dash-btn" onclick="showForm('wipe-user')">🧹 Wipe User</button>
                        <button class="dash-btn" onclick="showForm('view-profile')">👤 View Profile</button>

                        <button class="dash-btn" onclick="showForm('transfer')">🔁 Transfer Coins</button>
                        <button class="dash-btn" onclick="showForm('add-key')">🔐 Add Steam Key</button>
                        <button class="dash-btn" onclick="showForm('edit-info-ar')">✏️ Edit Info (AR)</button>
                        <button class="dash-btn" onclick="showForm('edit-info-en')">✏️ Edit Info (EN)</button>
                        <button class="dash-btn" onclick="showForm('cp-image')">🖼️ Update Hub Image</button>
                        <button class="dash-btn" onclick="showForm('clear-effects')">✨ Clear Effects</button>
                      </div>

                      <div id="form-area" style="margin-top:12px;">
                        <!-- dynamic form fields inserted here -->
                      </div>
                    </div>

                    <div class="panel" style="margin-top:12px;">
                      <h3>Top Wallets</h3>
                      <div class="user-list">
                        <table>
                          <tr><th>Rank</th><th>User</th><th>Balance</th></tr>
            """

            # build rows for top wallets using usernames
            for idx, (uid, bal) in enumerate(top, 1):
                try:
                    u = BOT.get_user(uid)
                    if u:
                        uname = f"{u.name}#{u.discriminator}"
                    else:
                        uname = str(uid)
                except Exception:
                    uname = str(uid)
                html += f"<tr><td>{idx}</td><td>{uname}</td><td>{bal}</td></tr>\n"

            html += """
                        </table>
                      </div>
                    </div>

                  </div>

                  <div>
                    <div class="panel">
                      <h3>Recent Logs</h3>
                      <div style="max-height:260px; overflow:auto;">
            """

            for ts, atype, det in logs:
                html += f"<div style='padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04);'><strong>{ts}</strong> <span style='opacity:0.85'>[{atype}]</span><div style='opacity:0.9;margin-top:4px'>{det}</div></div>\n"

            html += """
                      </div>

                      <div style="margin-top:12px;">
                        <h4>Active Effects</h4>
            """

            for user_id, effect_type, expire_time in active_effects:
                try:
                    u = BOT.get_user(user_id)
                    uname = f"{u.name}#{u.discriminator}" if u else str(user_id)
                except Exception:
                    uname = str(user_id)
                html += f"<div style='padding:6px 0'>{uname} - {effect_type} until {expire_time}</div>\n"

            html += """
                      </div>

                      <div style="margin-top:12px;">
                        <h4>Bans</h4>
                        <div style='font-size:13px;'>Shop bans:</div>
            """

            for user_id, ban_until, reason in shop_bans:
                try:
                    u = BOT.get_user(user_id)
                    uname = f"{u.name}#{u.discriminator}" if u else str(user_id)
                except Exception:
                    uname = str(user_id)
                html += f"<div style='padding:4px 0'>{uname} until {ban_until} ({reason})</div>\n"

            html += """
                        <div style='margin-top:6px;font-size:13px;'>Economy bans:</div>
            """

            for user_id, ban_until, reason in economy_bans:
                try:
                    u = BOT.get_user(user_id)
                    uname = f"{u.name}#{u.discriminator}" if u else str(user_id)
                except Exception:
                    uname = str(user_id)
                html += f"<div style='padding:4px 0'>{uname} until {ban_until} ({reason})</div>\n"

            html += """
                      </div>

                    </div>

            </body>
            </html>
            """

            # include profile HTML if any (insert before closing </body> to keep page valid)
            if profile_html:
                html = html.replace("</body>", profile_html + "</body>")

            # inject form templates & showForm override using server-side safe token insertion
            try:
                import re
                script_src_path = r"c:\\Users\\Sulim\\Desktop\\Blade X (BLZ Shop)\\bot1.py"
                with open(script_src_path, 'r', encoding='utf-8') as f:
                    src_text = f.read()
                # extract slash and text commands with descriptions
                tree_matches = re.findall(r"@BOT\\.tree\\.command\s*\(([^)]*)\)\s*(?:async\s+def|def)\s+([A-Za-z0-9_]+)\s*\(", src_text, flags=re.S)
                text_matches = re.findall(r"@BOT\\.command\s*\(([^)]*)\)\s*(?:async\s+def|def)\s+([A-Za-z0-9_]+)\s*\(", src_text, flags=re.S)
                slash_cmds = []
                for args, func in tree_matches:
                    name_m = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", args)
                    desc_m = re.search(r"description\s*=\s*['\"]([^'\"]+)['\"]", args)
                    name = name_m.group(1) if name_m else func
                    desc = desc_m.group(1) if desc_m else ''
                    slash_cmds.append((name, desc))
                text_cmds_list = []
                for args, func in text_matches:
                    name_m = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", args)
                    desc_m = re.search(r"description\s*=\s*['\"]([^'\"]+)['\"]", args)
                    name = name_m.group(1) if name_m else func
                    desc = desc_m.group(1) if desc_m else ''
                    text_cmds_list.append((name, desc))
                # Build HTML with descriptions
                cmds_html = '<div class="panel"><h3>All Commands</h3><div style="display:flex;gap:12px;margin-top:8px;">'
                cmds_html += '<div style="flex:1;"><h4>Text Commands (!)</h4>'
                if text_cmds_list:
                    for n,d in text_cmds_list:
                        safe_d = (d or '').replace('"', '&quot;').replace("'", '&#39;')
                        cmds_html += f'<div class="cmd-pill"><strong>!{n}</strong><div style="font-size:12px;opacity:0.85;margin-top:6px">{safe_d}</div></div>'
                else:
                    cmds_html += '<div>No text commands found.</div>'
                cmds_html += '</div>'
                cmds_html += '<div style="flex:1;"><h4>Slash Commands (/)</h4>'
                if slash_cmds:
                    for n,d in slash_cmds:
                        safe_d = (d or '').replace('"', '&quot;').replace("'", '&#39;')
                        cmds_html += f'<div class="cmd-pill"><strong>/{n}</strong><div style="font-size:12px;opacity:0.85;margin-top:6px">{safe_d}</div></div>'
                else:
                    cmds_html += '<div>No slash commands found.</div>'
                cmds_html += '</div></div></div>'

            except Exception:
                cmds_html = '<div class="panel"><h3>All Commands</h3><div>Unable to load commands.</div></div>'

            sections = {}
            try:
                # Build commands list from running bot (text and slash) to reliably show names + descriptions
                text_cmds_list = []
                try:
                    for c in getattr(BOT, 'commands', []):
                        try:
                            desc = c.help or ''
                        except:
                            desc = ''
                        text_cmds_list.append((c.name, desc))
                except Exception:
                    text_cmds_list = []

                slash_cmds = []
                try:
                    # prefer walk_commands if available
                    walker = getattr(BOT.tree, 'walk_commands', None)
                    if callable(walker):
                        all_slash = list(walker())
                    else:
                        all_slash = getattr(BOT.tree, 'commands', [])
                    for ac in all_slash:
                        try:
                            desc = getattr(ac, 'description', '') or ''
                        except:
                            desc = ''
                        try:
                            display_name = getattr(ac, 'qualified_name', getattr(ac, 'name', ''))
                        except:
                            display_name = getattr(ac, 'name', '')
                        slash_cmds.append((display_name, desc))
                except Exception:
                    slash_cmds = []

                # assemble HTML
                cmds_html = '<div class="panel"><h3>All Commands</h3><div style="display:flex;gap:12px;margin-top:8px;">'
                cmds_html += '<div style="flex:1;"><h4>Text Commands (!)</h4>'
                if text_cmds_list:
                    for n,d in text_cmds_list:
                        safe_d = (d or '').replace('"', '&quot;').replace("'", '&#39;')
                        cmds_html += f'<div class="cmd-pill"><strong>!{n}</strong><div style="font-size:12px;opacity:0.85;margin-top:6px">{safe_d}</div></div>'
                else:
                    cmds_html += '<div>No text commands found.</div>'
                cmds_html += '</div>'
                cmds_html += '<div style="flex:1;"><h4>Slash Commands (/)</h4>'
                if slash_cmds:
                    for n,d in slash_cmds:
                        safe_d = (d or '').replace('"', '&quot;').replace("'", '&#39;')
                        cmds_html += f'<div class="cmd-pill"><strong>/{n}</strong><div style="font-size:12px;opacity:0.85;margin-top:6px">{safe_d}</div></div>'
                else:
                    cmds_html += '<div>No slash commands found.</div>'
                cmds_html += '</div></div></div>'
                sections['admin-guide'] = cmds_html
            except Exception:
                sections['admin-guide'] = '<div class="panel"><h3>All Commands</h3><div>Unable to load commands.</div></div>'

            sections['admin-guide'] = cmds_html
            sections['moderation-tools'] = '<div class="panel"><h3>Moderation Tools</h3><div class="buttons-grid">' + \
                '<button class="dash-btn" onclick="showForm(\'ban-shop\')">🛒 Ban Shop</button>' + \
                '<button class="dash-btn" onclick="showForm(\'ban-economy\')">💸 Ban Economy</button>' + \
                '<button class="dash-btn" onclick="showForm(\'unban-shop\')">✅ Unban Shop</button>' + \
                '<button class="dash-btn" onclick="showForm(\'unban-economy\')">✅ Unban Economy</button>' + \
                '<button class="dash-btn" onclick="showForm(\'wipe-user\')">🧹 Wipe User</button>' + \
                '</div></div>'

            sections['economy-settings'] = '<div class="panel"><h3>Economy Settings</h3><div class="buttons-grid">' + \
                '<button class="dash-btn" onclick="showForm(\'transfer\')">🔁 Transfer Coins</button>' + \
                '<button class="dash-btn" onclick="showForm(\'add-key\')">🔐 Add Steam Key</button>' + \
                '<button class="dash-btn" onclick="showForm(\'cp-image\')">🖼️ Update Hub Image</button>' + \
                '</div></div>'

            sections['logs-auditing'] = '<div class="panel"><h3>Logs & Auditing</h3><div><button class="dash-btn" onclick="showForm(\'view-logs\')">📜 View Full Logs</button></div></div>'

            script_templates = """<div class='site-footer'><div style='max-width:1200px;margin:0 auto;padding:12px 0;color:#bbb;text-align:center;'>BLZ System Engine • Powered by Suli</div></div><script>
            (function(){
              var DASH_TOKEN = %s;
              var templates = {};
              templates['ban-shop'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="ban-shop"><input name="user_id" placeholder="User ID or username" class="small-input"><input name="hours" placeholder="Hours" class="small-input"><input name="reason" placeholder="Reason" class="small-input"><button class="dash-btn" type="submit">Ban Shop</button></form>';
              templates['ban-economy'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="ban-economy"><input name="user_id" placeholder="User ID or username" class="small-input"><input name="hours" placeholder="Hours" class="small-input"><input name="reason" placeholder="Reason" class="small-input"><button class="dash-btn" type="submit">Ban Economy</button></form>';
              templates['unban-shop'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="unban-shop"><input name="user_id" placeholder="User ID or username" class="small-input"><button class="dash-btn" type="submit">Unban Shop</button></form>';
              templates['unban-economy'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="unban-economy"><input name="user_id" placeholder="User ID or username" class="small-input"><button class="dash-btn" type="submit">Unban Economy</button></form>';
              templates['set-token'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="set-token"><input name="new_token" placeholder="New token" class="small-input"><button class="dash-btn" type="submit">Update Token</button></form>';
              templates['set-port'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="set-port"><input name="port" placeholder="Port" class="small-input"><button class="dash-btn" type="submit">Set Port</button></form>';
              templates['set-lang'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="set-lang"><select name="lang" class="small-input"><option value="ar">Arabic</option><option value="en">English</option></select><button class="dash-btn" type="submit">Set Language</button></form>';
              templates['wipe-user'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="wipe-user"><input name="user_id" placeholder="User ID" class="small-input"><button class="dash-btn" type="submit">Wipe User</button></form>';
              templates['transfer'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="transfer"><input name="from_id" placeholder="From User ID" class="small-input"><input name="to_id" placeholder="To User ID" class="small-input"><input name="amount" placeholder="Amount" class="small-input"><button class="dash-btn" type="submit">Transfer</button></form>';
              templates['add-key'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="add-key"><input name="game_name" placeholder="Game Name" class="small-input"><input name="steam_key" placeholder="Key" class="small-input"><button class="dash-btn" type="submit">Add Key</button></form>';
              templates['edit-info-ar'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="edit-info-form"><input type="hidden" name="lang" value="ar"><button class="dash-btn" type="submit">Edit Info (AR)</button></form>';
              templates['edit-info-en'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="edit-info-form"><input type="hidden" name="lang" value="en"><button class="dash-btn" type="submit">Edit Info (EN)</button></form>';
              templates['cp-image'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="cp-image"><input name="image_url" placeholder="Image URL" class="small-input"><button class="dash-btn" type="submit">Update Image</button></form>';
              templates['clear-effects'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="clear-effects"><input name="user_id" placeholder="User ID" class="small-input"><button class="dash-btn" type="submit">Clear Effects</button></form>';
              templates['view-profile'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="view-profile"><input name="user" placeholder="ID, mention or username#1234" class="small-input"><button class="dash-btn" type="submit">View Profile</button></form>';
              templates['view-logs'] = '<form method="get"><input type="hidden" name="token" value="' + DASH_TOKEN + '"><input type="hidden" name="action" value="view-logs"><button class="dash-btn" type="submit">View Full Logs</button></form>';
              window.__dashTemplates = templates;
              window.__dashSections = %s;
            })();

            function showForm(action){
              var area = document.getElementById('form-area');
              var tpl = window.__dashTemplates && window.__dashTemplates[action];
              area.innerHTML = tpl || '';
            }
            function showSection(id){
              var area = document.getElementById('section-area');
              var html = window.__dashSections && window.__dashSections[id];
              area.innerHTML = html || '';
              if(area) area.scrollIntoView({ behavior: 'smooth' });
            }
            </script>""" % (json.dumps(token), json.dumps(sections))

            html = html.replace("</body>", script_templates + "</body>")
            # auto-show admin guide commands panel on load
            html = html.replace("</body>", "<script>setTimeout(function(){ try{ if(window.__dashSections && window.__dashSections['admin-guide']) showSection('admin-guide'); } catch(e){} }, 200);</script></body>")
            # send response
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

    def run_server():
        server_address = ('', port)
        httpd = HTTPServer(server_address, AdminHandler)
        try:
            httpd.serve_forever()
        except Exception:
            pass

    global admin_dashboard_thread, admin_dashboard_port_running
    if admin_dashboard_thread and admin_dashboard_thread.is_alive():
        if admin_dashboard_port_running == port:
            print(f"Admin dashboard already running on port {port}")
            return
        print(f"Admin dashboard already running on port {admin_dashboard_port_running}. Restart bot to change port.")
        return

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    admin_dashboard_thread = thread
    admin_dashboard_port_running = port

@BOT.event
async def on_ready():
    print(f"Logged in safely as: {BOT.user.name} (ID: {BOT.user.id})")
    
    # بدء المحركات
    voice_rewards_engine.start()
    check_expired_effects.start()
    
    try:
        synced = await BOT.tree.sync()
        print(f"📡 Successfully Synced {len(synced)} Slash Commands for Advanced Control.")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
        
    print("------ System Engines Active v6.0 [MEE6 Voice Engine & Shop Ban System] ------")

    # Start admin dashboard if enabled in config
    try:
        if get_config_int('enable_admin_dashboard') == 1:
            port = get_config_int('admin_dashboard_port') or 8080
            start_admin_dashboard(port=port)
            print(f"Admin dashboard started on port {port}")
    except Exception as e:
        print(f"Failed to start admin dashboard: {e}")

# ==========================================
# تشغيل البوت النهائي
# ==========================================

BOT.run("MTUxNTI5Njk4MzQzNzQxMDMzNw.G9O_rK.gdKUuwv6KT8gca-JhGQTKVf9IDwFcfX_JEygtg")
