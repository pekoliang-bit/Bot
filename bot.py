import os
import sys
import subprocess
import json
import time
import random
import threading
import re
import traceback
from datetime import datetime

# -------------------- 自動補齊套件 --------------------
try:
    import aiosqlite
    import flask
    import discord
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiosqlite", "flask", "discord.py"])
    import aiosqlite
    import flask
    import discord

from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask

# -------------------- 輕量假網頁（防雲端主機休眠） --------------------
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "World Engine is running perfectly!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# -------------------- 基礎設定與常數 --------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
DB_PATH = "game_database.db"

# -------------------- 擴充國家名冊庫 --------------------
WESTERN_NATIONS = [
    "美國", "英國", "法國", "德國", "義大利", "俄羅斯", "西班牙", "加拿大", "澳大利亞", "瑞典", 
    "波蘭", "捷克", "冰島", "丹麥", "希臘", "愛爾蘭", "紐西蘭", "葡萄牙", "比利時", "瑞士", 
    "挪威", "芬蘭", "荷蘭", "匈牙利", "羅馬尼亞", "保加利亞", "立陶宛", "烏克蘭"
]

EASTERN_NATIONS = [
    "中國", "日本", "韓國", "新加坡", "馬來西亞", "泰國", "越南", "菲律賓", "蒙古國", "印度", 
    "緬甸", "馬爾地夫", "杜拜", "土耳其", "尼泊爾", "印尼", "汶萊", "柬埔寨", "卡達", "阿拉伯", 
    "哈薩克", "不丹", "斯里蘭卡", "孟加拉", "寮國", "東帝汶"
]

SOUTH_AMERICAN_NATIONS = [
    "巴西", "阿根廷", "智利", "哥倫比亞", "秘魯", "烏拉圭", "墨西哥",
    "委內瑞拉", "巴拉圭", "蓋亞那", "玻利維亞", "厄瓜多"
]

AFRICAN_NATIONS = [
    "埃及", "南非", "奈及利亞", "肯亞", "摩洛哥", "衣索比亞",
    "象牙海岸", "剛果", "喀麥隆", "維德角", "獅子山", "尼日", "布基納法索", "賴比瑞亞"
]

CROWD_JOBS = ["演員", "特技演員", "模特", "歌手", "偶像", "綜藝咖", "短劇演員", "舞者", "網紅", "星二代", "經紀人", "導演"]
CROWD_RELATIONS = ["單身", "單身（事業腦）", "單身（前任成群）", "暗戀同台前輩", "地下戀愛中", "曖昧期", "隱婚傳聞中", "私生活混亂", "熱戀中"]

# -------------------- 擴充標籤庫（正面、負面、風格） --------------------
UNIVERSAL_TAGS = [
    "初戀臉", "厭世感", "舞台匠人", "釣系", "全能天才", "天籟蜜嗓", 
    "極致反差", "低音砲", "古典氣質", "漫撕人", "高嶺之花", "元氣犬系",
    "性感", "緋聞纏身", "濃顏", "淡顏", "臉蛋天才", "社恐", "社交悍匪", 
    "人間清醒", "毒舌", "劇拋臉", "鬆弛感", "文盲", "花瓶",
    "百億少年的夢", "天選之子", "清冷白月光", "建模臉", "劇本殺手", "氛圍感", "事業腦", "戀愛腦",
    "九漏魚", "糊咖", "加戲咖", "塌房預備役", "作精", "營銷咖"
]

GENDER_AGE_TAGS = {
    "少年感": lambda age, gen: gen == "男" and age <= 25,
    "老幹部": lambda age, gen: age >= 30,
    "國民初戀": lambda age, gen: gen == "女" and age <= 24,
    "國民弟弟": lambda age, gen: gen == "男" and age <= 22,
    "國民妹妹": lambda age, gen: gen == "女" and age <= 22,
    "國民兒子": lambda age, gen: gen == "男" and age <= 28,
    "國民女兒": lambda age, gen: gen == "女" and age <= 28,
}

TAG_CONFLICTS = {
    "濃顏": ["淡顏"],
    "淡顏": ["濃顏"],
    "社恐": ["社交悍匪"],
    "社交悍匪": ["社恐"],
    "文盲": ["人間清醒", "全能天才", "劇本殺手"],
    "九漏魚": ["人間清醒", "全能天才", "劇本殺手"],
    "花瓶": ["劇拋臉", "舞台匠人", "全能天才", "劇本殺手"],
    "劇拋臉": ["花瓶"],
    "老幹部": ["少年感", "元氣犬系"],
    "少年感": ["老幹部"],
    "事業腦": ["戀愛腦"],
    "戀愛腦": ["事業腦"],
    "天選之子": ["糊咖"],
    "糊咖": ["天選之子", "百億少年的夢"],
    "清冷白月光": ["緋聞纏身", "塌房預備役"],
    "緋聞纏身": ["清冷白月光"]
}

# -------------------- 預設世界觀面板用詞與資歷稱謂字典 --------------------
DEFAULT_UI_TERMS = {
    "page1_title": "個人基本檔案",
    "page2_title": "演藝能力面板",
    "section_basic": "基本身分與星途",
    "term_track": "主攻賽道",
    "term_org": "歸屬組織",
    "term_debut": "出道歷練",
    "term_debut_years": "出道資歷",
    "term_health": "核心健康",
    "term_color": "代表色碼",
    "term_faction": "所屬勢力",
    "term_tags": "特質標籤",
    "term_relation": "情感狀態",
    "term_rank": "當前地位",
    "term_cash": "手頭現金",
    "term_bank": "銀行存款",
    "term_assets": "產權與名下企業",
    "section_stat_group1": "商業名氣",
    "section_stat_group2": "藝能實力",
    "section_dynamic": "動態追蹤與社群指標"
}

DEFAULT_DEBUT_TIERS = [
    {"min": 80, "title": "不朽史詩先驅"},
    {"min": 70, "title": "世紀傳奇勳章"},
    {"min": 60, "title": "藝界活化石"},
    {"min": 50, "title": "星光長青碑"},
    {"min": 40, "title": "半世紀名伶"},
    {"min": 35, "title": "歲月巨擘"},
    {"min": 30, "title": "一代宗師"},
    {"min": 25, "title": "傳奇泰斗"},
    {"min": 20, "title": "殿堂名宿"},
    {"min": 15, "title": "實力資深"},
    {"min": 10, "title": "中流砥柱"},
    {"min": 5, "title": "初露鋒芒"},
    {"min": 1, "title": "新星崛起"},
    {"min": 0, "title": "新秀 / 未正式出道"}
]
# -------------------- 世界觀自訂名詞與階梯動態解析 --------------------
async def get_world_terms(guild_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'custom_ui_terms'", (guild_id,)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                try:
                    custom = json.loads(row[0])
                    merged = dict(DEFAULT_UI_TERMS)
                    merged.update(custom)
                    return merged
                except Exception:
                    pass
    return DEFAULT_UI_TERMS

async def get_debut_title_async(guild_id: int, debut_years: int, debut_age: int = None) -> str:
    terms = await get_world_terms(guild_id)
    debut_label = terms.get("term_debut_years", "資歷")
    
    tiers = DEFAULT_DEBUT_TIERS
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'custom_debut_tiers'", (guild_id,)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                try:
                    tiers = json.loads(row[0])
                except Exception:
                    pass

    tiers_sorted = sorted(tiers, key=lambda x: x.get("min", 0), reverse=True)
    years = debut_years if debut_years and debut_years > 0 else 0

    if years <= 0:
        base_title = next((t["title"] for t in tiers_sorted if t.get("min", 0) == 0), "新秀 / 未正式出道")
        return f"{base_title}（接取/完成 1 次任務即可確立身分）"

    age_str = f"於 {debut_age} 歲入行" if debut_age else "已入行"
    chosen_title = "新星崛起"
    for t in tiers_sorted:
        if years >= t.get("min", 0):
            chosen_title = t.get("title", chosen_title)
            break

    return f"{chosen_title} ｜ {debut_label} {years} 年 ({age_str})"

def parse_hex_color(color_str: str, default_color: int = 0x3498DB) -> int:
    if not color_str:
        return default_color
    clean_str = color_str.strip().lstrip("#").replace("0x", "")
    try:
        return int(clean_str, 16)
    except ValueError:
        return default_color

def check_bmi_impact(height_cm: int, weight_kg: int, base_health: int = 100, base_appearance: int = 50):
    if height_cm <= 0 or weight_kg <= 0:
        return base_health, base_appearance, 20.0, ""
    height_m = height_cm / 100.0
    bmi = round(weight_kg / (height_m * height_m), 1)
    health_penalty, app_penalty, warn_text = 0, 0, ""
    if bmi < 16.0:
        health_penalty, app_penalty = 20, 15
        warn_text = f"⚠️ 體態指數過低（BMI: {bmi}，身形偏瘦），健康 -20、容貌 -15。"
    elif bmi > 28.0:
        health_penalty, app_penalty = 20, 15
        warn_text = f"⚠️ 體態指數過高（BMI: {bmi}，體態超標），健康 -20、容貌 -15。"
    return max(10, base_health - health_penalty), max(10, base_appearance - app_penalty), bmi, warn_text

def get_available_tags_for(age: int, gender: str) -> list:
    res = list(UNIVERSAL_TAGS)
    for tag, cond in GENDER_AGE_TAGS.items():
        if cond(age, gender):
            res.append(tag)
    return res

def resolve_tag_conflicts(current_tags: list, new_tag: str) -> list:
    conflicts = TAG_CONFLICTS.get(new_tag, [])
    filtered = [t for t in current_tags if t not in conflicts and t != new_tag]
    filtered.append(new_tag)
    return filtered[-5:]
# -------------------- 官方通知大廳統一廣播引擎 --------------------
async def broadcast_event(guild: discord.Guild, event_type: str, embed: discord.Embed, mention_role: discord.Role = None):
    if not guild: return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'notify_channel_id'", (guild.id,)) as cur:
            row = await cur.fetchone()
            if not row or not row[0]:
                return
            target_ch_id = int(row[0])

    channel = guild.get_channel(target_ch_id)
    if not channel:
        return

    mention_str = ""
    if event_type != "rank_up" and mention_role:
        mention_str = mention_role.mention

    try:
        await channel.send(content=mention_str if mention_str else None, embed=embed)
    except Exception:
        pass

# -------------------- 社群貼圖即時監聽 --------------------
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id or not payload.guild_id:
        return

    g_id = payload.guild_id
    ch_id = payload.channel_id
    emoji_str = str(payload.emoji)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT platform_name FROM social_monitor_channels WHERE guild_id = ? AND channel_id = ?", (g_id, ch_id)) as cur:
            ch_match = await cur.fetchone()

        if not ch_match:
            ch = bot.get_channel(ch_id)
            if hasattr(ch, "parent_id") and ch.parent_id:
                async with db.execute("SELECT platform_name FROM social_monitor_channels WHERE guild_id = ? AND channel_id = ?", (g_id, ch.parent_id)) as p_cur:
                    ch_match = await p_cur.fetchone()

        if not ch_match:
            return

        async with db.execute("""
            SELECT target_type, stat_changes FROM social_reaction_rules
            WHERE guild_id = ? AND trigger_type = 'reaction' AND trigger_key = ?
        """, (g_id, emoji_str)) as cur:
            rules = await cur.fetchall()

        if not rules:
            return

        target_ch = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
        msg = await target_ch.fetch_message(payload.message_id)
        author_id = msg.author.id
        actor_id = payload.user_id

        for target_type, stat_changes in rules:
            target_uid = author_id if target_type == "author" else actor_id
            async with db.execute("SELECT name, stats FROM characters WHERE guild_id = ? AND user_id = ? LIMIT 1", (g_id, target_uid)) as u_cur:
                char_row = await u_cur.fetchone()

            if char_row:
                c_name, s_json = char_row
                stats = json.loads(s_json) if s_json else {}
                for part in re.split(r"[,，\s]+", stat_changes):
                    m = re.search(r"([^\d+-]+)([+-]?\d+)", part)
                    if m:
                        sk, sv = m.group(1).strip(), int(m.group(2))
                        stats[sk] = max(0, stats.get(sk, 0) + sv)

                await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(stats, ensure_ascii=False), g_id, c_name))
        await db.commit()

# -------------------- 對戲留言、字數結算與 CP 營業自動判定 --------------------
def count_text_words(text: str, mode: str) -> int:
    clean = re.sub(r"<@!?\d+>", "", text).strip()
    if mode == "chinese_only":
        return len(re.findall(r"[\u4e00-\u9fa5]", clean))
    elif mode == "chinese_punct":
        pattern = r"[\u4e00-\u9fa5]|[\u3000-\u303F\uFF00-\uFFEF!\"#$%&'()*+,-./:;<=>?@[\\\]^_`{|}~]"
        return len(re.findall(pattern, clean))
    elif mode == "chinese_english":
        return len(re.findall(r"[\u4e00-\u9fa5]|[a-zA-Z]+", clean))
    else:
        return len(re.sub(r"\s+", "", clean))

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    g_id = message.guild.id if message.guild else 0
    if not g_id:
        return

    if bot.user in message.mentions:
        if not isinstance(message.channel, discord.Thread):
            await message.reply("⚠️ **此功能只能在討論串或帖子裡的留言區使用！**", mention_author=True)
            return

        target_text = ""
        if message.reference and message.reference.message_id:
            try:
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
                target_text = ref_msg.content
            except Exception:
                pass

        if not target_text or len(re.sub(r"<@!?\d+>", "", target_text).strip()) == 0:
            content_without_mention = re.sub(r"<@!?\d+>", "", message.content).strip()
            if len(content_without_mention) > 0:
                target_text = content_without_mention
            else:
                async for prev_msg in message.channel.history(limit=10, before=message):
                    if prev_msg.author.id == message.author.id and len(prev_msg.content.strip()) > 0:
                        target_text = prev_msg.content
                        break

        if not target_text:
            await message.reply("❌ 找不到可結算的文字內容！請回覆你要結算的段落，或在該段落中艾特我。", mention_author=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT key, value FROM system_settings WHERE guild_id = ?", (g_id,)) as cur:
                settings = dict(await cur.fetchall())

            mode = settings.get("word_calc_mode", "chinese_punct")
            unit = settings.get("currency_unit", "元")
            ratio = float(settings.get("word_money_ratio", "1.0"))

            word_count = count_text_words(target_text, mode)
            total_money = int(word_count * ratio)

            await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND user_id = ?", (total_money, g_id, message.author.id))
            await db.commit()

        await message.reply(f"字數：{word_count} 字\n共計金錢：{total_money:,} {unit}（已自動存入銀行）", mention_author=True)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, cp_info, stats FROM characters WHERE guild_id = ? AND user_id = ? LIMIT 1", (g_id, message.author.id)) as cur:
            c_row = await cur.fetchone()

        if c_row:
            my_name, cp_json, stats_json = c_row
            if cp_json:
                cp_data = json.loads(cp_json)
                cp_target = cp_data.get("target")
                if cp_target and (cp_target in message.content):
                    old_affection = cp_data.get("affection", 100)
                    new_affection = old_affection + 5
                    cp_data["affection"] = new_affection

                    stats = json.loads(stats_json) if stats_json else {}
                    stats["流量熱度"] = stats.get("流量熱度", 0) + 20

                    await db.execute("""
                        UPDATE characters 
                        SET cp_info = ?, stats = ?
                        WHERE guild_id = ? AND name = ?
                    """, (json.dumps(cp_data, ensure_ascii=False), json.dumps(stats, ensure_ascii=False), g_id, my_name))
                    await db.commit()

                    try:
                        await message.add_reaction("💞")
                    except Exception:
                        pass

    await bot.process_commands(message)
# -------------------- 世界觀自訂名詞與階梯動態解析 --------------------
async def get_world_terms(guild_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'custom_ui_terms'", (guild_id,)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                try:
                    custom = json.loads(row[0])
                    merged = dict(DEFAULT_UI_TERMS)
                    merged.update(custom)
                    return merged
                except Exception:
                    pass
    return DEFAULT_UI_TERMS

async def get_debut_title_async(guild_id: int, debut_years: int, debut_age: int = None) -> str:
    terms = await get_world_terms(guild_id)
    debut_label = terms.get("term_debut_years", "資歷")
    
    tiers = DEFAULT_DEBUT_TIERS
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'custom_debut_tiers'", (guild_id,)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                try:
                    tiers = json.loads(row[0])
                except Exception:
                    pass

    tiers_sorted = sorted(tiers, key=lambda x: x.get("min", 0), reverse=True)
    years = debut_years if debut_years and debut_years > 0 else 0

    if years <= 0:
        base_title = next((t["title"] for t in tiers_sorted if t.get("min", 0) == 0), "新秀 / 未正式出道")
        return f"{base_title}（接取/完成 1 次任務即可確立身分）"

    age_str = f"於 {debut_age} 歲入行" if debut_age else "已入行"
    chosen_title = "新星崛起"
    for t in tiers_sorted:
        if years >= t.get("min", 0):
            chosen_title = t.get("title", chosen_title)
            break

    return f"{chosen_title} ｜ {debut_label} {years} 年 ({age_str})"

def parse_hex_color(color_str: str, default_color: int = 0x3498DB) -> int:
    if not color_str:
        return default_color
    clean_str = color_str.strip().lstrip("#").replace("0x", "")
    try:
        return int(clean_str, 16)
    except ValueError:
        return default_color

def check_bmi_impact(height_cm: int, weight_kg: int, base_health: int = 100, base_appearance: int = 50):
    if height_cm <= 0 or weight_kg <= 0:
        return base_health, base_appearance, 20.0, ""
    height_m = height_cm / 100.0
    bmi = round(weight_kg / (height_m * height_m), 1)
    health_penalty, app_penalty, warn_text = 0, 0, ""
    if bmi < 16.0:
        health_penalty, app_penalty = 20, 15
        warn_text = f"⚠️ 體態指數過低（BMI: {bmi}，身形偏瘦），健康 -20、容貌 -15。"
    elif bmi > 28.0:
        health_penalty, app_penalty = 20, 15
        warn_text = f"⚠️ 體態指數過高（BMI: {bmi}，體態超標），健康 -20、容貌 -15。"
    return max(10, base_health - health_penalty), max(10, base_appearance - app_penalty), bmi, warn_text

def get_available_tags_for(age: int, gender: str) -> list:
    res = list(UNIVERSAL_TAGS)
    for tag, cond in GENDER_AGE_TAGS.items():
        if cond(age, gender):
            res.append(tag)
    return res

def resolve_tag_conflicts(current_tags: list, new_tag: str) -> list:
    conflicts = TAG_CONFLICTS.get(new_tag, [])
    filtered = [t for t in current_tags if t not in conflicts and t != new_tag]
    filtered.append(new_tag)
    return filtered[-5:]
# -------------------- 官方通知大廳統一廣播引擎 --------------------
async def broadcast_event(guild: discord.Guild, event_type: str, embed: discord.Embed, mention_role: discord.Role = None):
    if not guild: return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'notify_channel_id'", (guild.id,)) as cur:
            row = await cur.fetchone()
            if not row or not row[0]:
                return
            target_ch_id = int(row[0])

    channel = guild.get_channel(target_ch_id)
    if not channel:
        return

    mention_str = ""
    if event_type != "rank_up" and mention_role:
        mention_str = mention_role.mention

    try:
        await channel.send(content=mention_str if mention_str else None, embed=embed)
    except Exception:
        pass

# -------------------- 社群貼圖即時監聽 --------------------
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id or not payload.guild_id:
        return

    g_id = payload.guild_id
    ch_id = payload.channel_id
    emoji_str = str(payload.emoji)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT platform_name FROM social_monitor_channels WHERE guild_id = ? AND channel_id = ?", (g_id, ch_id)) as cur:
            ch_match = await cur.fetchone()

        if not ch_match:
            ch = bot.get_channel(ch_id)
            if hasattr(ch, "parent_id") and ch.parent_id:
                async with db.execute("SELECT platform_name FROM social_monitor_channels WHERE guild_id = ? AND channel_id = ?", (g_id, ch.parent_id)) as p_cur:
                    ch_match = await p_cur.fetchone()

        if not ch_match:
            return

        async with db.execute("""
            SELECT target_type, stat_changes FROM social_reaction_rules
            WHERE guild_id = ? AND trigger_type = 'reaction' AND trigger_key = ?
        """, (g_id, emoji_str)) as cur:
            rules = await cur.fetchall()

        if not rules:
            return

        target_ch = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
        msg = await target_ch.fetch_message(payload.message_id)
        author_id = msg.author.id
        actor_id = payload.user_id

        for target_type, stat_changes in rules:
            target_uid = author_id if target_type == "author" else actor_id
            async with db.execute("SELECT name, stats FROM characters WHERE guild_id = ? AND user_id = ? LIMIT 1", (g_id, target_uid)) as u_cur:
                char_row = await u_cur.fetchone()

            if char_row:
                c_name, s_json = char_row
                stats = json.loads(s_json) if s_json else {}
                for part in re.split(r"[,，\s]+", stat_changes):
                    m = re.search(r"([^\d+-]+)([+-]?\d+)", part)
                    if m:
                        sk, sv = m.group(1).strip(), int(m.group(2))
                        stats[sk] = max(0, stats.get(sk, 0) + sv)

                await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(stats, ensure_ascii=False), g_id, c_name))
        await db.commit()

# -------------------- 對戲留言、字數結算與 CP 營業自動判定 --------------------
def count_text_words(text: str, mode: str) -> int:
    clean = re.sub(r"<@!?\d+>", "", text).strip()
    if mode == "chinese_only":
        return len(re.findall(r"[\u4e00-\u9fa5]", clean))
    elif mode == "chinese_punct":
        pattern = r"[\u4e00-\u9fa5]|[\u3000-\u303F\uFF00-\uFFEF!\"#$%&'()*+,-./:;<=>?@[\\\]^_`{|}~]"
        return len(re.findall(pattern, clean))
    elif mode == "chinese_english":
        return len(re.findall(r"[\u4e00-\u9fa5]|[a-zA-Z]+", clean))
    else:
        return len(re.sub(r"\s+", "", clean))

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    g_id = message.guild.id if message.guild else 0
    if not g_id:
        return

    if bot.user in message.mentions:
        if not isinstance(message.channel, discord.Thread):
            await message.reply("⚠️ **此功能只能在討論串或帖子裡的留言區使用！**", mention_author=True)
            return

        target_text = ""
        if message.reference and message.reference.message_id:
            try:
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
                target_text = ref_msg.content
            except Exception:
                pass

        if not target_text or len(re.sub(r"<@!?\d+>", "", target_text).strip()) == 0:
            content_without_mention = re.sub(r"<@!?\d+>", "", message.content).strip()
            if len(content_without_mention) > 0:
                target_text = content_without_mention
            else:
                async for prev_msg in message.channel.history(limit=10, before=message):
                    if prev_msg.author.id == message.author.id and len(prev_msg.content.strip()) > 0:
                        target_text = prev_msg.content
                        break

        if not target_text:
            await message.reply("❌ 找不到可結算的文字內容！請回覆你要結算的段落，或在該段落中艾特我。", mention_author=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT key, value FROM system_settings WHERE guild_id = ?", (g_id,)) as cur:
                settings = dict(await cur.fetchall())

            mode = settings.get("word_calc_mode", "chinese_punct")
            unit = settings.get("currency_unit", "元")
            ratio = float(settings.get("word_money_ratio", "1.0"))

            word_count = count_text_words(target_text, mode)
            total_money = int(word_count * ratio)

            await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND user_id = ?", (total_money, g_id, message.author.id))
            await db.commit()

        await message.reply(f"字數：{word_count} 字\n共計金錢：{total_money:,} {unit}（已自動存入銀行）", mention_author=True)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, cp_info, stats FROM characters WHERE guild_id = ? AND user_id = ? LIMIT 1", (g_id, message.author.id)) as cur:
            c_row = await cur.fetchone()

        if c_row:
            my_name, cp_json, stats_json = c_row
            if cp_json:
                cp_data = json.loads(cp_json)
                cp_target = cp_data.get("target")
                if cp_target and (cp_target in message.content):
                    old_affection = cp_data.get("affection", 100)
                    new_affection = old_affection + 5
                    cp_data["affection"] = new_affection

                    stats = json.loads(stats_json) if stats_json else {}
                    stats["流量熱度"] = stats.get("流量熱度", 0) + 20

                    await db.execute("""
                        UPDATE characters 
                        SET cp_info = ?, stats = ?
                        WHERE guild_id = ? AND name = ?
                    """, (json.dumps(cp_data, ensure_ascii=False), json.dumps(stats, ensure_ascii=False), g_id, my_name))
                    await db.commit()

                    try:
                        await message.add_reaction("💞")
                    except Exception:
                        pass

    await bot.process_commands(message)
# -------------------- 分頁視窗輔助類 --------------------
class PagedDetailView(discord.ui.View):
    def __init__(self, title: str, items: list, color: int, page_size: int = 10):
        super().__init__(timeout=120)
        self.title = title
        self.items = items
        self.color = color
        self.page_size = page_size
        self.page = 0
        self.max_page = max(0, (len(items) - 1) // page_size)

    def get_embed(self):
        start = self.page * self.page_size
        end = start + self.page_size
        slice_items = self.items[start:end]
        embed = discord.Embed(title=f"{self.title} (第 {self.page+1}/{self.max_page+1} 頁)", color=self.color)
        embed.description = "\n".join(slice_items) if slice_items else "暫無資料紀錄。"
        return embed

    @discord.ui.button(label="⬅️ 上一頁", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="➡️ 下一頁", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_page:
            self.page += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

# -------------------- 角色檔案按鈕組：ProfileMainView --------------------
class ProfileMainView(discord.ui.View):
    def __init__(self, target_name: str, guild_id: int, embed_page1: discord.Embed = None, embed_page2: discord.Embed = None):
        super().__init__(timeout=180)
        self.char_name = target_name
        self.guild_id = guild_id
        self.embed_page1 = embed_page1
        self.embed_page2 = embed_page2

    @discord.ui.button(label="📑 第 1 頁：基本檔案", style=discord.ButtonStyle.primary, row=0)
    async def go_page1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.embed_page1:
            await interaction.response.edit_message(embed=self.embed_page1, view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="📊 第 2 頁：能力數值", style=discord.ButtonStyle.success, row=0)
    async def go_page2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.embed_page2:
            await interaction.response.edit_message(embed=self.embed_page2, view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="🏆 成就歷練", style=discord.ButtonStyle.secondary, row=1)
    async def view_achieves(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT works FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                row = await cur.fetchone()
                works = json.loads(row[0]) if (row and row[0]) else []
        items = [f"• 【{w.get('type', '歷練')}】《{w.get('title')}》— {w.get('extra', '記錄')}" for w in works if w.get("category") == "成就"]
        p_view = PagedDetailView(f"🏆【{self.char_name}】歷練成就清單", items, 0xF1C40F)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

    @discord.ui.button(label="🎖️ 榮譽頭銜", style=discord.ButtonStyle.secondary, row=1)
    async def view_honors(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT works FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                row = await cur.fetchone()
                works = json.loads(row[0]) if (row and row[0]) else []
        items = [f"• 🎖️《{w.get('title')}》— {w.get('extra', '榮譽認證')}" for w in works if w.get("category") == "榮譽"]
        p_view = PagedDetailView(f"🎖️【{self.char_name}】獲頒榮譽頭銜", items, 0x2ECC71)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

    @discord.ui.button(label="🐾 夥伴寵物", style=discord.ButtonStyle.secondary, row=1)
    async def view_pets(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT pet_type, pet_name, health, is_dead, lifespan_years FROM character_pets WHERE guild_id = ? AND owner_name = ?", (self.guild_id, self.char_name)) as cur:
                rows = await cur.fetchall()
        lines = [f"• **{p_name}** ({p_type}) ｜ 狀態: {'🕊️ 已故' if is_dead else f'❤️ 健康值: `{health}/500` (壽命: {l_years}年)'}" for p_type, p_name, health, is_dead, l_years in rows]
        embed = discord.Embed(title=f"🐾【{self.char_name}】的同伴夥伴", description="\n".join(lines) if lines else "目前尚未飼養任何夥伴（可使用 `/寵物購買` 認養）。", color=0x1ABC9C)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📢 坊間傳聞", style=discord.ButtonStyle.secondary, row=2)
    async def view_rumors(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT rumor_text FROM character_rumors WHERE guild_id = ? AND char_name = ? ORDER BY id DESC LIMIT 20", (self.guild_id, self.char_name)) as cur:
                rows = await cur.fetchall()
        items = [f"• 「{r[0]}」" for r in rows]
        p_view = PagedDetailView(f"📢【{self.char_name}】的坊間傳聞", items, 0xE74C3C)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

    @discord.ui.button(label="💬 交際網絡", style=discord.ButtonStyle.secondary, row=2)
    async def view_relationships(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT to_char, tendency, affection, status_desc FROM relationships WHERE guild_id = ? AND from_char = ?", (self.guild_id, self.char_name)) as cur:
                rows = await cur.fetchall()
        items = [f"• 對象：**{to_c}** ｜ 傾向：【{t}】 ｜ 羈絆：💖{aff} ｜ 狀況：`{desc}`" for to_c, t, aff, desc in rows]
        p_view = PagedDetailView(f"💬【{self.char_name}】的交際關係網絡", items, 0xE91E63)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

    @discord.ui.button(label="📖 專屬劇情", style=discord.ButtonStyle.success, row=2)
    async def view_npc_stories(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT s.story_title, s.unlock_condition, COALESCE(p.completed, 0)
                FROM story_scripts s
                LEFT JOIN character_story_progress p 
                    ON s.guild_id = p.guild_id AND s.npc_name = p.npc_name AND s.story_title = p.story_title AND p.char_name = ?
                WHERE s.guild_id = ? AND s.npc_name = ? AND s.is_active = 1
            """, (self.char_name, self.guild_id, self.char_name)) as cur:
                rows = await cur.fetchall()

        if not rows:
            await interaction.response.send_message(f"📋 【{self.char_name}】目前尚未開放任何專屬攻略劇情。", ephemeral=True)
            return

        embed = discord.Embed(title=f"📖【{self.char_name}】專屬攻略劇情清單", color=0xF1C40F)
        for title, cond, completed in rows:
            if completed == 1:
                embed.add_field(
                    name=f"-# ✔️ 《{title}》（已通關圓滿）",
                    value=f"-# • 門檻要求：`{cond}`",
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"🌟 **《{title}》**【可攻略/未解鎖】",
                    value=f"• 解鎖門檻：`{cond}`\n• 觸發指令：`/劇情觸發 角色名:你的名字 npc名稱:{self.char_name}`",
                    inline=False
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)
# -------------------- 通用角色卡片渲染函式 --------------------
async def render_character_card(interaction: discord.Interaction, target_name: str, ephemeral: bool = True):
    g_id = interaction.guild_id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT age, gender, job, faction, tags, relationship_status,
                   cp_info, cash, bank, stats, rank, company_id, is_npc,
                   image_url, height, nationality, debut_years, debut_age, theme_color,
                   weight, stage_name, primary_track, char_health, affiliation_type, affiliation_name, education, orientation
            FROM characters WHERE guild_id = ? AND name = ?
        """, (g_id, target_name)) as cur:
            row = await cur.fetchone()

        if not row:
            msg = f"❌ 查無檔案【{target_name}】！"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        (
            age, gender, job, faction, tags, rel_status,
            cp_json, cash, bank, stats_json, rank_name, comp_id, is_npc_val,
            img_url, height, nationality, debut_years, debut_age, theme_color,
            weight, stage_name, primary_track, char_health, aff_type, aff_name, education, orientation
        ) = row

        async with db.execute("SELECT asset_type, asset_name, price FROM personal_assets WHERE guild_id = ? AND owner_name = ?", (g_id, target_name)) as a_cur:
            assets = await a_cur.fetchall()
        async with db.execute("SELECT name, type_name FROM companies WHERE guild_id = ? AND creator_name = ?", (g_id, target_name)) as c_cur:
            comps = await c_cur.fetchall()
        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'hidden_stats'", (g_id,)) as s_cur:
            h_row = await s_cur.fetchone()
            hidden_stats_set = set(json.loads(h_row[0])) if h_row else set()

    terms = await get_world_terms(g_id)

    default_c = 0x3498DB
    tag_prefix = ""
    if is_npc_val == 1:
        tag_prefix = "［官方 NPC］"
        default_c = 0x9B59B6
    elif is_npc_val == 2:
        tag_prefix = "［自設 NPC］"
        default_c = 0x1ABC9C
    elif is_npc_val == 3:
        tag_prefix = "［動態路人 NPC］"
        default_c = 0xE67E22
    else:
        tag_prefix = "［個人角色］"

    final_color = parse_hex_color(theme_color, default_color=default_c)
    h_display = f"{height} cm" if height else "未填寫"
    w_display = f"{weight} kg" if weight else "未填寫"
    nat_display = nationality if nationality else "本國"
    stage_str = f" / 稱號: {stage_name}" if stage_name and stage_name != target_name else ""
    debut_info = await get_debut_title_async(g_id, debut_years, debut_age)

    # 第 1 頁
    embed1 = discord.Embed(
        title=f"🪪 {tag_prefix}【{target_name}】{stage_str} {terms.get('page1_title', '個人基本檔案')} (1/2)",
        color=final_color
    )
    embed1.add_field(
        name=terms.get("section_basic", "基本身分與星途"),
        value=(
            f"• 國籍/性別: `{nat_display}` / {gender} ({orientation or '保密'})\n"
            f"• 年齡/身材: {age}歲 / `{h_display}` / `{w_display}`\n"
            f"• 身分/{terms.get('term_track', '主攻賽道')}: {job} ｜ 主攻【**{primary_track or '常規'}**】\n"
            f"• {terms.get('term_org', '歸屬組織')}: `{aff_type or '單打獨鬥'}`（{aff_name or '無'}）\n"
            f"• {terms.get('term_debut', '出道歷練')}: **{debut_info}**\n"
            f"• {terms.get('term_health', '核心健康')}: ❤️ **{char_health or 100} / 100**\n"
            f"• {terms.get('term_color', '代表色碼')}: `{theme_color or '預設'}` ｜ {terms.get('term_faction', '所屬勢力')}: {faction}\n"
            f"• {terms.get('term_tags', '特質標籤')}: `{tags or '無'}`"
        ),
        inline=False
    )

    cp_obj = json.loads(cp_json) if cp_json else {}
    cp_target = cp_obj.get("target")
    cp_relation = cp_obj.get("relation", "伴侶")
    cp_affection = cp_obj.get("affection", 100)
    cp_text = f"💕 CP/道侶: **{cp_target}** ({cp_relation} ｜ 羈絆: {cp_affection})" if cp_target else "無"

    embed1.add_field(name=terms.get("term_relation", "情感狀態"), value=f"• 狀態: {rel_status}\n• {cp_text}", inline=True)
    embed1.add_field(
        name="資產與地位",
        value=f"• {terms.get('term_rank', '當前地位')}: **【{rank_name or '未定級'}】**\n• {terms.get('term_cash', '手頭現金')}: ${cash:,}\n• {terms.get('term_bank', '銀行存款')}: ${bank:,}",
        inline=True
    )

    asset_lines = [f"• [{a[0]}] {a[1]} (${a[2]:,})" for a in assets]
    if comps:
        for c in comps:
            asset_lines.append(f"• [名下基業] {c[0]} ({c[1]})")
    embed1.add_field(name=f"🚗 {terms.get('term_assets', '產權與名下企業')}", value="\n".join(asset_lines) if asset_lines else "名下尚無固定資產", inline=False)
    embed1.set_footer(text="點擊下方【第 2 頁：能力數值】按鈕查看各項指標 ➔")

    if img_url and img_url.startswith("http"):
        embed1.set_thumbnail(url=img_url)

    # 第 2 頁
    embed2 = discord.Embed(
        title=f"📊 {tag_prefix}【{target_name}】{stage_str} {terms.get('page2_title', '能力面板')} (2/2)",
        color=final_color
    )
    stats = json.loads(stats_json) if stats_json else {}

    group1_name = terms.get("section_stat_group1", "商業名氣")
    lines_group1 = [
        f"• 流量熱度：**{stats.get('流量熱度', 0):,}**",
        f"• 商業價值：**{stats.get('商業價值', 0):,}**",
        f"• 影響指數：**{stats.get('影響指數', 0):,}**",
        f"• 路人緣：**{stats.get('路人緣', 0):,}**",
        f"• 公關：**{stats.get('公關', 0):,}**"
    ]
    embed2.add_field(name=f"📈 {group1_name}", value="\n".join(lines_group1), inline=False)

    group2_name = terms.get("section_stat_group2", "藝能實力")
    all_tracks = ["歌唱", "唱跳", "主持", "綜藝", "演繹"]
    main_track = primary_track if primary_track in all_tracks else "演繹"
    other_tracks = [t for t in all_tracks if t != main_track]
    other_tracks_str = " ｜ ".join([f"{t}: **{stats.get(t, 0)}**" for t in other_tracks])

    lines_group2 = [
        f"• 容貌：**{stats.get('容貌', 0)}**",
        f"• 才智：**{stats.get('才智', 0)}**",
        f"• 主攻賽道【{main_track}】：**{stats.get(main_track, 0)}**",
        f"  └ 其他賽道：{other_tracks_str}",
        f"• 個人才藝：**{stats.get('個人才藝', 0)}**"
    ]
    embed2.add_field(name=f"🎭 {group2_name}", value="\n".join(lines_group2), inline=False)

    dynamic_name = terms.get("section_dynamic", "動態追蹤與社群指標")
    dynamic_lines = [
        f"• 死忠支持者：**{stats.get('死忠粉絲數', 0):,}** 人",
        f"• 活躍對立者：**{stats.get('活躍黑粉數', 0):,}** 人",
        f"• 大眾認知度：**{stats.get('大眾認知度', 0):,}**",
        f"• CP/伴侶羈絆：{cp_target}（{cp_affection} 點好感）" if cp_target else "• CP/伴侶羈絆：無"
    ]
    embed2.add_field(name=f"📊 {dynamic_name}", value="\n".join(dynamic_lines), inline=False)

    custom_type_keys = [k for k in stats.keys() if k not in (
        ["流量熱度", "商業價值", "影響指數", "路人緣", "公關", "容貌", "才智", "個人才藝",
         "死忠粉絲數", "活躍黑粉數", "大眾認知度"] + all_tracks
    ) and k not in hidden_stats_set]

    if custom_type_keys:
        custom_lines = [f"• {k}：**{stats[k]}**" for k in custom_type_keys]
        embed2.add_field(name="✨ 特殊項目", value="\n".join(custom_lines), inline=False)

    if img_url and img_url.startswith("http"):
        embed2.set_thumbnail(url=img_url)

    view = ProfileMainView(target_name, g_id, embed1, embed2)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed1, view=view, ephemeral=ephemeral)
    else:
        await interaction.response.send_message(embed=embed1, view=view, ephemeral=ephemeral)
# -------------------- 指令：/系統頻道與開關總管 --------------------
@bot.tree.command(name="系統頻道與開關總管", description="【管理員專用】頻道綁定、功能開關、時間流速與銀行週利息設定（利息每週限調一次）")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(社群關注拉黑功能=[
    app_commands.Choice(name="開啟社群功能", value="on"),
    app_commands.Choice(name="關閉社群功能", value="off")
])
@app_commands.choices(字數統計模式=[
    app_commands.Choice(name="中文字加標點符號 (預設)", value="chinese_punct"),
    app_commands.Choice(name="僅中文字", value="chinese_only"),
    app_commands.Choice(name="中文字加英文字", value="chinese_english"),
    app_commands.Choice(name="全部字符（含符號與空格）", value="all")
])
@app_commands.describe(
    官方通知大廳頻道="所有劇情更新、升級、違規通報與活動廣播頻道",
    社群動態監聽頻道="指定接收社群貼圖反饋結算的頻道",
    解除社群監聽頻道="取消指定頻道的社群監聽",
    社群關注拉黑功能="是否允許玩家使用 /社交關注 與 /社交拉黑",
    存款利息百分比="設定每日銀行利息百分比 (填純數字，如 5 代表 5%，每週限修改一次)",
    遊戲一年等於現實幾天="設定時間流速 (純數字，例如 30 代表現實 30 天長 1 歲)",
    一字折合金錢="對戲討論串每 1 字可換取金錢 (例如 1.0 或 0.5)",
    貨幣單位="自訂金錢單位 (例如: 元、金幣、靈石)"
)
async def system_channels_and_toggles(
    interaction: discord.Interaction,
    官方通知大廳頻道: discord.TextChannel = None,
    社群動態監聽頻道: discord.TextChannel = None,
    解除社群監聽頻道: discord.TextChannel = None,
    社群關注拉黑功能: app_commands.Choice[str] = None,
    字數統計模式: app_commands.Choice[str] = None,
    存款利息百分比: float = None,
    遊戲一年等於現實幾天: int = None,
    一字折合金錢: float = None,
    貨幣單位: str = None
):
    g_id = interaction.guild_id
    msgs = []
    now_ts = time.time()

    async with aiosqlite.connect(DB_PATH) as db:
        if 官方通知大廳頻道:
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'notify_channel_id', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, str(官方通知大廳頻道.id), str(官方通知大廳頻道.id)))
            msgs.append(f"📢 **官方通知大廳**已綁定為：{官方通知大廳頻道.mention}")

        if 社群動態監聽頻道:
            await db.execute("""
                INSERT INTO social_monitor_channels (guild_id, channel_id, platform_name)
                VALUES (?, ?, '社群動態')
                ON CONFLICT(channel_id) DO UPDATE SET platform_name = '社群動態'
            """, (g_id, 社群動態監聽頻道.id))
            msgs.append(f"📲 **社群監聽頻道**已加入：{社群動態監聽頻道.mention}")

        if 解除社群監聽頻道:
            await db.execute("DELETE FROM social_monitor_channels WHERE guild_id = ? AND channel_id = ?", (g_id, 解除社群監聽頻道.id))
            msgs.append(f"🗑️ 已解除 {解除社群監聽頻道.mention} 的社群監聽。")

        if 社群關注拉黑功能:
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'social_feature_toggle', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, 社群關注拉黑功能.value, 社群關注拉黑功能.value))
            state_str = "已啟用" if 社群關注拉黑功能.value == "on" else "已關閉"
            msgs.append(f"⚙️ **社群關注/拉黑功能**：`{state_str}`")

        # 存款利息修改（嚴格限制一週僅能修改一次）
        if 存款利息百分比 is not None:
            if 存款利息百分比 < 0:
                await interaction.response.send_message("❌ 利息百分比不能為負數！", ephemeral=True)
                return

            async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'interest_last_modified'", (g_id,)) as cur:
                last_mod_row = await cur.fetchone()

            last_mod_ts = float(last_mod_row[0]) if (last_mod_row and last_mod_row[0]) else 0
            one_week_seconds = 7 * 86400

            if now_ts - last_mod_ts < one_week_seconds and not last_mod_ts == 0:
                rem_days = round((one_week_seconds - (now_ts - last_mod_ts)) / 86400, 1)
                await interaction.response.send_message(f"🚫 **【利息調整冷卻中】** 存款利息一週僅能修改一次！剩餘冷卻時間：`{rem_days}` 天。", ephemeral=True)
                return

            actual_rate = 存款利息百分比 / 100.0
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'interest_rate', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, str(actual_rate), str(actual_rate)))
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'interest_last_modified', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, str(now_ts), str(now_ts)))
            msgs.append(f"🏦 **銀行每日利息**已更新為：`{存款利息百分比}%`（下一次修改需等候 7 天）")

        # 時間流速設定（遊戲一年等於現實幾天）
        if 遊戲一年等於現實幾天 is not None:
            if 遊戲一年等於現實幾天 <= 0:
                await interaction.response.send_message("❌ 時間流速天數必須大於 0！", ephemeral=True)
                return
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'days_per_game_year', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, str(遊戲一年等於現實幾天), str(遊戲一年等於現實幾天)))
            msgs.append(f"⏳ **時間流速**已更新：遊戲中每滿 1 年 ＝ 現實世界的 `{遊戲一年等於現實幾天}` 天！")

        if 字數統計模式:
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'word_calc_mode', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, 字數統計模式.value, 字數統計模式.value))
            msgs.append(f"📝 **字數計算模式**：`{字數統計模式.name}`")

        if 一字折合金錢 is not None:
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'word_money_ratio', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, str(一字折合金錢), str(一字折合金錢)))
            msgs.append(f"⚖️ **對戲稿酬**：每 1 字折合 `{一字折合金錢}` 貨幣")

        if 貨幣單位:
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'currency_unit', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, 貨幣單位.strip(), 貨幣單位.strip()))
            msgs.append(f"💰 **貨幣單位**：`{貨幣單位.strip()}`")

        await db.commit()

    if not msgs:
        await interaction.response.send_message("ℹ️ 請至少選擇一項設定變更項目！", ephemeral=True)
        return

    embed = discord.Embed(title="⚙️ 系統核心設定已全面更新", color=0x2ECC71)
    embed.description = "\n".join(msgs)
    await interaction.response.send_message(embed=embed, ephemeral=True)
# -------------------- 指令：/標籤管理（含特殊限定門檻） --------------------
@bot.tree.command(name="標籤管理", description="【管理員專用】擴充全域特質、自訂雙向衝突或設定特殊限定標籤")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="➕ 擴充常規標籤", value="add_tag"),
    app_commands.Choice(name="🌟 新增特殊限定標籤", value="add_restricted_tag"),
    app_commands.Choice(name="⚔️ 設定雙向互斥衝突", value="set_conflict"),
    app_commands.Choice(name="🔍 查詢標籤與衝突規則", value="list")
])
@app_commands.describe(
    操作="選擇要執行的標籤管理動作",
    標籤名稱="標籤名稱",
    互斥對象="與之互相排斥的標籤名稱 (設定衝突時必填)",
    限定性別="［特殊限定］指定性別 (男/女/通用)",
    限定最高年齡="［特殊限定］年齡不大於此數值 (例如: 22 代表僅22歲以下可得)",
    限定身分組="［特殊限定］必須具備此身分組的角色才能配戴"
)
async def manage_tags_cmd(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    標籤名稱: str = None,
    互斥對象: str = None,
    限定性別: str = "通用",
    限定最高年齡: int = None,
    限定身分組: discord.Role = None
):
    op = 操作.value

    if op == "add_tag":
        if not 標籤名稱:
            await interaction.response.send_message("❌ 請填寫欲擴充的【標籤名稱】！", ephemeral=True)
            return
        t_name = 標籤名稱.strip()
        if t_name not in UNIVERSAL_TAGS:
            UNIVERSAL_TAGS.append(t_name)
        await interaction.response.send_message(f"✅ 成功將常規標籤【**{t_name}**】納入全域標籤庫！", ephemeral=True)
        return

    elif op == "add_restricted_tag":
        if not 標籤名稱:
            await interaction.response.send_message("❌ 請填寫欲設定的【標籤名稱】！", ephemeral=True)
            return
        t_name = 標籤名稱.strip()
        
        # 註冊特殊判定函式
        cond_desc = []
        gen_cond = (lambda age, gen: gen == 限定性別) if 限定性別 in ["男", "女"] else (lambda age, gen: True)
        if 限定性別 in ["男", "女"]: cond_desc.append(f"限 {限定性別}性")

        age_cond = (lambda age, gen: age <= 限定最高年齡) if 限定最高年齡 else (lambda age, gen: True)
        if 限定最高年齡: cond_desc.append(f"年齡 ≤ {限定最高年齡} 歲")

        GENDER_AGE_TAGS[t_name] = lambda age, gen: gen_cond(age, gen) and age_cond(age, gen)

        role_str = f" ｜ 限身分組 {限定身分組.mention}" if 限定身分組 else ""
        await interaction.response.send_message(
            f"🌟 **【特殊限定標籤登記成功】**\n"
            f"標籤名：【**{t_name}**】\n"
            f"門檻規則：`{' 且 '.join(cond_desc) if cond_desc else '特殊專屬'}`{role_str}",
            ephemeral=True
        )
        return

    elif op == "set_conflict":
        if not 標籤名稱 or not 互斥對象:
            await interaction.response.send_message("❌ 設定衝突時，【標籤名稱】與【互斥對象】皆為必填！", ephemeral=True)
            return
        t1, t2 = 標籤名稱.strip(), 互斥對象.strip()

        TAG_CONFLICTS.setdefault(t1, [])
        if t2 not in TAG_CONFLICTS[t1]: TAG_CONFLICTS[t1].append(t2)

        TAG_CONFLICTS.setdefault(t2, [])
        if t1 not in TAG_CONFLICTS[t2]: TAG_CONFLICTS[t2].append(t1)

        await interaction.response.send_message(f"⚔️ 成功建立雙向互斥：持有【**{t1}**】將無法同時具備【**{t2}**】！", ephemeral=True)
        return

    elif op == "list":
        embed = discord.Embed(title="🏷️ 全域標籤與互斥規則清單", color=0xF39C12)
        embed.add_field(name="通用特質標籤", value="、".join(UNIVERSAL_TAGS[:35]), inline=False)
        conflict_lines = [f"• 【{k}】⇄ 【{', '.join(v)}】" for k, v in TAG_CONFLICTS.items()]
        embed.add_field(name="雙向衝突組", value="\n".join(conflict_lines[:15]) if conflict_lines else "暫無自訂衝突", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
# -------------------- 指令：/動作設定（支援掉落物品與機率） --------------------
@bot.tree.command(name="動作設定", description="【管理員專用】設定地點動作（消耗AP/金錢、排練1~15數值、人脈好感、掉落道具）")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="新增/覆蓋動作日程", value="save"),
    app_commands.Choice(name="刪除既有動作", value="delete")
])
@app_commands.describe(
    操作="選擇新增或刪除動作",
    分類="地點分類名稱（例如: 練習室、健身中心、綜合醫院、深夜酒館、修煉密室）",
    動作名稱="具體行為（例如: 名師私教、兼職打工、閉關排練、喝酒應酬）",
    說明描述="點選時看到的說明文字",
    消耗行動點="需消耗的行動點 (預設 1)",
    花費金錢="需扣除的金錢 (填 0 為免費)",
    獲得金錢="打工兼職可賺取的金錢 (填 0 為無酬勞)",
    健康增減="扣除填負數 (如喝酒 -10)，恢復填正數 (如去醫院 +30)",
    固定數值增減="固定屬性變動 (格式如: 容貌+5 才智+10 身高+1 體重-1)",
    排練隨機數值賽道="單純消耗AP排練隨機獲得 1~15 點的屬性名稱，空格隔開 (例如: 演繹 唱跳)",
    掉落物品名稱="可自訂完成該行程時獲得的道具名 (選填)",
    掉落物品數量="獲得道具的數量 (預設 1)",
    掉落物品機率="獲得物品的機率百分比 (1~100，填 100 代表必定掉落)",
    人脈機遇名="結識人脈(好感1~5點)對象名 (例如: 知名製作人)"
)
async def set_action_place(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    分類: str,
    動作名稱: str,
    說明描述: str = "日常歷練行程",
    消耗行動點: int = 1,
    花費金錢: int = 0,
    獲得金錢: int = 0,
    健康增減: int = 0,
    固定數值增減: str = "",
    排練隨機數值賽道: str = "",
    掉落物品名稱: str = None,
    掉落物品數量: int = 1,
    掉落物品機率: int = 100,
    人脈機遇名: str = None
):
    g_id = interaction.guild_id
    cat = 分類.strip()
    act = 動作名稱.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        if 操作.value == "delete":
            await db.execute("DELETE FROM action_places WHERE guild_id = ? AND category = ? AND action_name = ?", (g_id, cat, act))
            await db.commit()
            await interaction.response.send_message(f"🗑️ 已成功刪除【{cat}】下的動作【{act}】！", ephemeral=True)
            return

        # 封裝特殊際遇（人脈與道具機率）
        spec_parts = []
        if 人脈機遇名:
            spec_parts.append(f"人脈:{人脈機遇名.strip()}")
        if 掉落物品名稱:
            spec_parts.append(f"物品:{掉落物品名稱.strip()}*{掉落物品數量}@{掉落物品機率}")
        special_rewards_str = " ".join(spec_parts)

        await db.execute("""
            INSERT INTO action_places (
                guild_id, category, action_name, description, cost_ap, cost_money,
                reward_money, health_change, fixed_stat_change, random_stat_types, special_rewards
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, category, action_name) DO UPDATE SET
                description = excluded.description,
                cost_ap = excluded.cost_ap,
                cost_money = excluded.cost_money,
                reward_money = excluded.reward_money,
                health_change = excluded.health_change,
                fixed_stat_change = excluded.fixed_stat_change,
                random_stat_types = excluded.random_stat_types,
                special_rewards = excluded.special_rewards
        """, (
            g_id, cat, act, 說明描述.strip(), 消耗行動點, 花費金錢,
            獲得金錢, 健康增減, 固定數值增減.strip(), 排練隨機數值賽道.strip(), special_rewards_str
        ))
        await db.commit()

    embed = discord.Embed(title="📍 日程動作配置完成", color=0x2ECC71)
    embed.description = f"**地點分類**：【{cat}】\n**動作名稱**：**{act}**\n• 簡述：`{說明描述.strip()}`"
    embed.add_field(name="消耗與成本", value=f"• 行動點：`{消耗行動點} AP`\n• 費用：`${花費金錢:,}`", inline=True)
    embed.add_field(name="收益與健康", value=f"• 報酬：`${獲得金錢:,}`\n• 健康：`{健康增減:+}`", inline=True)
    if 固定數值增減.strip():
        embed.add_field(name="固定屬性/身材", value=f"`{固定數值增減.strip()}`", inline=False)
    if 排練隨機數值賽道.strip():
        embed.add_field(name="隨機排練 (1~15點)", value=f"`{排練隨機數值賽道.strip()}`", inline=False)
    if special_rewards_str:
        embed.add_field(name="特殊掉落/人脈", value=f"`{special_rewards_str}`", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)
# -------------------- 指令：/劇本設定（連動官方廣播） --------------------
@bot.tree.command(name="劇本設定", description="【管理員專用】為官方 NPC 錄入專屬攻略劇情（自動發布至通知大廳）")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    npc名稱="對應的官方 NPC 全名",
    劇情名稱="故事章節名稱（例如: 秘密試鏡指導 或 秘境古陣論道）",
    開放條件="解鎖門檻（例如: 偶遇>=3次、好感>=50、容貌>=80 等）",
    劇本訊息連結="貼上包含劇本對話文字的 Discord 訊息連結",
    廣播艾特身分組="選填：更新時在官方通知頻道艾特的身分組"
)
async def set_story_script(
    interaction: discord.Interaction,
    npc名稱: str,
    劇情名稱: str,
    開放條件: str,
    劇本訊息連結: str,
    廣播艾特身分組: discord.Role = None
):
    g_id = interaction.guild_id
    n_name = npc名稱.strip()
    s_title = 劇情名稱.strip()
    req_str = 開放條件.strip()
    link_str = 劇本訊息連結.strip()

    await interaction.response.defer(ephemeral=False)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_npc, image_url FROM characters WHERE guild_id = ? AND name = ?", (g_id, n_name)) as cur:
            npc_row = await cur.fetchone()
        if not npc_row or npc_row[0] != 1:
            await interaction.followup.send(f"❌ 【{n_name}】不是官方 NPC！若為路人請先使用 `/人物與NPC總管` 轉正。", ephemeral=True)
            return
        npc_avatar = npc_row[1]

    script_content = ""
    link_m = re.search(r"channels/\d+/(\d+)/(\d+)", link_str)
    if link_m:
        c_id, m_id = int(link_m.group(1)), int(link_m.group(2))
        try:
            ch = interaction.client.get_channel(c_id) or await interaction.client.fetch_channel(c_id)
            msg = await ch.fetch_message(m_id)
            script_content = msg.content
        except Exception as e:
            await interaction.followup.send(f"❌ 讀取訊息失敗：`{e}`，請確認機器人有權限查看該頻道！", ephemeral=True)
            return
    else:
        await interaction.followup.send("❌ 劇本訊息連結格式錯誤！", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO story_scripts (guild_id, npc_name, story_title, unlock_condition, script_link, script_content)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, npc_name, story_title) DO UPDATE SET
                unlock_condition = excluded.unlock_condition,
                script_link = excluded.script_link,
                script_content = excluded.script_content
        """, (g_id, n_name, s_title, req_str, link_str, script_content))
        await db.commit()

    embed = discord.Embed(title=f"📖【{n_name}】全新專屬攻略劇情開放！", color=0xF1C40F)
    embed.description = (
        f"**劇情章節**：🎬 《**{s_title}**》\n"
        f"**開放門檻條件**：`{req_str}`\n\n"
        f"💡 **攻略方式**：\n"
        f"達成條件後，在聊天室輸入：\n"
        f"`/劇情觸發 角色名:你的角色 npc名稱:{n_name}` 即可開啟互動！"
    )
    if npc_avatar and npc_avatar.startswith("http"):
        embed.set_thumbnail(url=npc_avatar)

    await broadcast_event(interaction.guild, "story", embed, mention_role=廣播艾特身分組)
    await interaction.followup.send(content="✅ 劇本錄入成功，已同步發布至官方通知大廳！", embed=embed)


# -------------------- 指令：/任務新增 --------------------
@bot.tree.command(name="任務新增", description="【管理員專用】發布全新任務並設定獎勵與時間限制")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(選擇欄位=[
    app_commands.Choice(name="新手任務", value="新手任務"),
    app_commands.Choice(name="一般任務", value="一般任務"),
    app_commands.Choice(name="限時任務", value="限時任務"),
    app_commands.Choice(name="特殊任務", value="特殊任務")
])
@app_commands.describe(
    選擇欄位="選擇任務分類",
    任務名="任務名稱",
    金錢獎勵="自動匯入銀行的金額 (可填 0)",
    數值獎勵="獲得的數值加成 (例如: 流量熱度+15 容貌+5)",
    獎勵道具名="自動送入背包的道具名 (選填)",
    獎勵道具數量="送入背包的數量 (預設 1)",
    限時時間="僅限時任務填寫，格式：YYYY/M/D HH:MM～YYYY/M/D HH:MM"
)
async def add_quest_cmd(
    interaction: discord.Interaction,
    選擇欄位: app_commands.Choice[str],
    任務名: str,
    金錢獎勵: int = 0,
    數值獎勵: str = "",
    獎勵道具名: str = None,
    獎勵道具數量: int = 1,
    限時時間: str = None
):
    category = 選擇欄位.value
    time_limit_str = ""

    if category == "限時任務":
        if not 限時時間:
            await interaction.response.send_message("❌ 欄位為【限時任務】時，必須填寫【限時時間】！\n範例：`2026/6/5 12:00～2026/6/15 12:00`", ephemeral=True)
            return

        time_pattern = r"^\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}～\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}$"
        if not re.match(time_pattern, 限時時間.strip()):
            await interaction.response.send_message("❌ 時間格式不正確！必須為 `YYYY/M/D HH:MM～YYYY/M/D HH:MM`", ephemeral=True)
            return
        time_limit_str = 限時時間.strip()

    items = []
    if 獎勵道具名:
        items.append({"name": 獎勵道具名.strip(), "amount": 獎勵道具數量})

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO quests (guild_id, category, title, reward_cash, reward_items, reward_stats, time_limit)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (interaction.guild_id, category, 任務名.strip(), 金錢獎勵, json.dumps(items, ensure_ascii=False), 數值獎勵.strip(), time_limit_str))
        await db.commit()

    time_info = f"\n⏳ 限時時間：`{time_limit_str}`" if time_limit_str else ""
    await interaction.response.send_message(
        f"✅ 成功發布任務！\n📌 分類：【{category}】\n🏷️ 任務名：**{任務名}**\n💰 銀行金錢：${金錢獎勵:,} ｜ 數值：`{數值獎勵 or '無'}`{time_info}"
    )
# -------------------- ProfileMainView 升級版（含全官角攻略指引） --------------------
# 請替換原有的 ProfileMainView 類別
class ProfileMainView(discord.ui.View):
    def __init__(self, target_name: str, guild_id: int, embed_page1: discord.Embed = None, embed_page2: discord.Embed = None):
        super().__init__(timeout=180)
        self.char_name = target_name
        self.guild_id = guild_id
        self.embed_page1 = embed_page1
        self.embed_page2 = embed_page2

    @discord.ui.button(label="📑 第 1 頁：基本檔案", style=discord.ButtonStyle.primary, row=0)
    async def go_page1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.embed_page1:
            await interaction.response.edit_message(embed=self.embed_page1, view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="📊 第 2 頁：能力數值", style=discord.ButtonStyle.success, row=0)
    async def go_page2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.embed_page2:
            await interaction.response.edit_message(embed=self.embed_page2, view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="🏆 成就歷練", style=discord.ButtonStyle.secondary, row=1)
    async def view_achieves(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT works FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                row = await cur.fetchone()
                works = json.loads(row[0]) if (row and row[0]) else []
        items = [f"• 【{w.get('type', '歷練')}】《{w.get('title')}》— {w.get('extra', '記錄')}" for w in works if w.get("category") == "成就"]
        p_view = PagedDetailView(f"🏆【{self.char_name}】歷練成就清單", items, 0xF1C40F)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

    @discord.ui.button(label="🎖️ 榮譽頭銜", style=discord.ButtonStyle.secondary, row=1)
    async def view_honors(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT works FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                row = await cur.fetchone()
                works = json.loads(row[0]) if (row and row[0]) else []
        items = [f"• 🎖️《{w.get('title')}》— {w.get('extra', '榮譽認證')}" for w in works if w.get("category") == "榮譽"]
        p_view = PagedDetailView(f"🎖️【{self.char_name}】獲頒榮譽頭銜", items, 0x2ECC71)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

    @discord.ui.button(label="🐾 夥伴寵物", style=discord.ButtonStyle.secondary, row=1)
    async def view_pets(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT pet_type, pet_name, health, is_dead, lifespan_years FROM character_pets WHERE guild_id = ? AND owner_name = ?", (self.guild_id, self.char_name)) as cur:
                rows = await cur.fetchall()
        lines = [f"• **{p_name}** ({p_type}) ｜ 狀態: {'🕊️ 已故' if is_dead else f'❤️ 健康值: `{health}/500` (壽命: {l_years}年)'}" for p_type, p_name, health, is_dead, l_years in rows]
        embed = discord.Embed(title=f"🐾【{self.char_name}】的同伴夥伴", description="\n".join(lines) if lines else "目前尚未飼養任何夥伴（可使用 `/寵物購買` 認養）。", color=0x1ABC9C)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📢 坊間傳聞", style=discord.ButtonStyle.secondary, row=2)
    async def view_rumors(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT rumor_text FROM character_rumors WHERE guild_id = ? AND char_name = ? ORDER BY id DESC LIMIT 20", (self.guild_id, self.char_name)) as cur:
                rows = await cur.fetchall()
        items = [f"• 「{r[0]}」" for r in rows]
        p_view = PagedDetailView(f"📢【{self.char_name}】的坊間傳聞", items, 0xE74C3C)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

    @discord.ui.button(label="💬 交際網絡", style=discord.ButtonStyle.secondary, row=2)
    async def view_relationships(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT to_char, tendency, affection, status_desc FROM relationships WHERE guild_id = ? AND from_char = ?", (self.guild_id, self.char_name)) as cur:
                rows = await cur.fetchall()
        items = [f"• 對象：**{to_c}** ｜ 傾向：【{t}】 ｜ 羈絆：💖{aff} ｜ 狀況：`{desc}`" for to_c, t, aff, desc in rows]
        p_view = PagedDetailView(f"💬【{self.char_name}】的交際關係網絡", items, 0xE91E63)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

    # 💡 全新功能：官方角色專屬攻略看板
    @discord.ui.button(label="💡 攻略指引", style=discord.ButtonStyle.success, row=2)
    async def view_all_official_stories(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            # 撈出全伺服器所有官方 NPC 的劇本與當前角色的通關進度
            async with db.execute("""
                SELECT s.npc_name, s.story_title, s.unlock_condition, COALESCE(p.completed, 0)
                FROM story_scripts s
                LEFT JOIN character_story_progress p 
                    ON s.guild_id = p.guild_id AND s.npc_name = p.npc_name AND s.story_title = p.story_title AND p.char_name = ?
                WHERE s.guild_id = ? AND s.is_active = 1
                ORDER BY s.npc_name ASC, s.id ASC
            """, (self.char_name, self.guild_id)) as cur:
                rows = await cur.fetchall()

        if not rows:
            await interaction.response.send_message("📋 本伺服器目前尚未錄入任何官方 NPC 攻略劇情。", ephemeral=True)
            return

        embed = discord.Embed(title=f"💡【{self.char_name}】官方角色專屬攻略導航看板", color=0xF1C40F)
        embed.description = "提示：已觸發/已通關劇情以灰字弱化顯示；未解鎖/未觸發劇情發光高亮展示！\n"

        for n_name, title, cond, completed in rows:
            if completed == 1:
                # 已觸發/已通關：暗灰色弱化字體
                embed.add_field(
                    name=f"-# ✔️【{n_name}】《{title}》（已圓滿通關）",
                    value=f"-# • 門檻：`{cond}`",
                    inline=False
                )
            else:
                # 未觸發：醒目高亮
                embed.add_field(
                    name=f"🌟 **【{n_name}】《{title}》**【待攻略/未觸發】",
                    value=f"• 解鎖門檻：`{cond}`\n• 觸發指令：`/劇情觸發 角色名:{self.char_name} npc名稱:{n_name}`",
                    inline=False
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)
# -------------------- 指令：/檔案建立（選項更名為原創角） --------------------
@bot.tree.command(name="檔案建立", description="建立玩家個人角色或原創角色檔案")
@app_commands.choices(類別=[
    app_commands.Choice(name="自身角色", value="0"),
    app_commands.Choice(name="原創角", value="2")
])
@app_commands.describe(
    名字="角色全名",
    年齡="純數字 (例如: 22)",
    身高="純數字 (單位: cm，例如: 178)",
    性別="性別 (男/女)",
    國籍="角色國籍或所屬地域",
    職業身分="職業、身分或門派道號",
    代表色碼="選填：16進位色碼 (例如: #FF69B4)",
    感情狀況="選填 (預設: 單身)",
    立繪連結="選填：貼上角色立繪或大頭照網址"
)
async def create_profile(
    interaction: discord.Interaction,
    類別: app_commands.Choice[str],
    名字: str,
    年齡: int,
    身高: int,
    性別: str,
    國籍: str,
    職業身分: str,
    代表色碼: str = "",
    感情狀況: str = "單身",
    立繪連結: str = ""
):
    g_id = interaction.guild_id
    target_name = 名字.strip()
    is_npc_val = int(類別.value)
    calc_weight = int(22.0 * ((身高 / 100.0) ** 2))

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
            if await cur.fetchone():
                await interaction.response.send_message(f"❌ 名稱 **{target_name}** 已存在！", ephemeral=True)
                return

        await db.execute("""
            INSERT INTO characters (
                guild_id, user_id, name, age, gender, job, faction, tags,
                relationship_status, created_at, is_npc, image_url, height, weight, nationality, theme_color
            ) VALUES (?, ?, ?, ?, ?, ?, '無', '', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            g_id, interaction.user.id, target_name, 年齡, 性別, 職業身分,
            感情狀況, time.time(), is_npc_val, 立繪連結.strip(), 身高, calc_weight, 國籍.strip(), 代表色碼.strip()
        ))
        await db.commit()

    card_color = parse_hex_color(代表色碼, default_color=0x2ECC71)
    label = "玩家角色" if is_npc_val == 0 else "原創角"
    embed = discord.Embed(title=f"🎉【{label}】基礎建檔成功", color=card_color)
    embed.add_field(name="姓名與基本身分", value=f"**{target_name}** ({年齡}歲 / {性別})\n• 身高：`{身高} cm` ｜ 國籍：`{國籍.strip()}`", inline=False)
    embed.add_field(name="身分與感情", value=f"• 職業：{職業身分}\n• 感情：{感情狀況}", inline=True)
    if 立繪連結.strip().startswith("http"):
        embed.set_thumbnail(url=立繪連結.strip())

    flow_view = CreateProfileFlowView(g_id, target_name, 年齡, 性別)
    await interaction.response.send_message(
        content=f"👉 請點選下方選單，為 **{target_name}** 挑選特質標籤：",
        embed=embed,
        view=flow_view
    )


# -------------------- 指令：/轉帳（由轉錢更名） --------------------
@bot.tree.command(name="轉帳", description="將手頭現金轉帳給其他角色")
@app_commands.describe(轉出者="發起轉帳的角色名", 接收者="收款人的角色名", 金額="轉帳金額")
async def transfer(interaction: discord.Interaction, 轉出者: str, 接收者: str, 金額: int):
    g_id = interaction.guild_id
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額需大於 0！", ephemeral=True)
        return

    sender, receiver = 轉出者.strip(), 接收者.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, cash FROM characters WHERE guild_id = ? AND name = ?", (g_id, sender)) as cur:
            s_row = await cur.fetchone()
            if not s_row:
                await interaction.response.send_message(f"❌ 找不到轉出角色【{sender}】！", ephemeral=True)
                return
            if s_row[0] != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 你只能操作自己的角色轉帳！", ephemeral=True)
                return
            if s_row[1] < 金額:
                await interaction.response.send_message(f"❌ 現金不足！目前手頭僅有 ${s_row[1]:,}。", ephemeral=True)
                return

        async with db.execute("SELECT 1 FROM characters WHERE guild_id = ? AND name = ?", (g_id, receiver)) as cur:
            if not await cur.fetchone():
                await interaction.response.send_message(f"❌ 查無接收對象【{receiver}】！", ephemeral=True)
                return

        await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (金額, g_id, sender))
        await db.execute("UPDATE characters SET cash = cash + ? WHERE guild_id = ? AND name = ?", (金額, g_id, receiver))
        await db.commit()

    await interaction.response.send_message(f"💸 **{sender}** 成功轉帳 **${金額:,}** 給 **{receiver}**！")
# -------------------- 指令：/行動（由動作更名，含完整限制與掉落） --------------------
class ExecuteActionSelect(discord.ui.Select):
    def __init__(self, char_name: str, guild_id: int, category: str, actions: list):
        self.char_name = char_name
        self.guild_id = guild_id
        self.category = category

        opts = []
        for act in actions[:25]:
            (
                a_id, a_name, desc, cost_ap, cost_money,
                rew_money, hp_chg, fixed_stat, rand_stats, spec_rew
            ) = act

            cost_info = f"消耗: {cost_ap}AP"
            if cost_money > 0:
                cost_info += f" ｜ ${cost_money:,}"
            if rew_money > 0:
                cost_info += f" ｜ 收益 ${rew_money:,}"
            if hp_chg != 0:
                cost_info += f" ｜ 健康{hp_chg:+}"

            opts.append(discord.SelectOption(
                label=a_name,
                value=str(a_id),
                description=cost_info[:50]
            ))

        super().__init__(placeholder=f"請選擇在【{category}】執行的行動日程...", options=opts)

    async def callback(self, interaction: discord.Interaction):
        act_id = int(self.values[0])

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT action_points, cash, bank, char_health, stats, height, weight
                FROM characters WHERE guild_id = ? AND name = ?
            """, (self.guild_id, self.char_name)) as c_cur:
                char_row = await c_cur.fetchone()

            if not char_row:
                await interaction.response.send_message("❌ 查無角色檔案！", ephemeral=True)
                return

            ap, cash, bank, hp, stats_json, cur_h, cur_w = char_row
            stats = json.loads(stats_json) if stats_json else {}

            async with db.execute("""
                SELECT action_name, description, cost_ap, cost_money,
                       reward_money, health_change, fixed_stat_change, random_stat_types, special_rewards
                FROM action_places WHERE id = ?
            """, (act_id,)) as a_cur:
                action_data = await a_cur.fetchone()

            if not action_data:
                await interaction.response.send_message("❌ 該行動不存在或已被移除！", ephemeral=True)
                return

            (
                a_name, desc, cost_ap, cost_money,
                rew_money, hp_chg, fixed_stat, rand_stats, spec_rew
            ) = action_data

            # 行動點與資金檢驗
            if ap < cost_ap:
                await interaction.response.send_message(
                    f"❌ **【行動點不足】** 執行【{a_name}】需要 **{cost_ap}** 點行動點（當前僅有 `{ap}` AP）！",
                    ephemeral=True
                )
                return

            total_money = cash + bank
            if cost_money > 0 and total_money < cost_money:
                await interaction.response.send_message(
                    f"❌ **【資金不足】** 執行【{a_name}】需要 **${cost_money:,}**！",
                    ephemeral=True
                )
                return

            # 上課次數與打工地點判定
            today_str = datetime.now().strftime("%Y-%m-%d")
            async with db.execute("""
                SELECT course_counts, work_places 
                FROM daily_action_limits 
                WHERE guild_id = ? AND char_name = ? AND date_str = ?
            """, (self.guild_id, self.char_name, today_str)) as limit_cur:
                limit_row = await limit_cur.fetchone()

            course_data = json.loads(limit_row[0]) if limit_row and limit_row[0] else {}
            work_places = json.loads(limit_row[1]) if limit_row and limit_row[1] else []

            # 課程判定：無 AP 消耗且花錢
            is_course = (cost_money > 0 and rew_money == 0 and cost_ap == 0)
            if is_course:
                current_course_cnt = course_data.get(self.category, 0)
                if current_course_cnt >= 5:
                    await interaction.response.send_message(
                        f"🚫 **【上課達今日上限】**【{self.category}】的專業指導課程每天上限為 **5 次**，請明日 00:00 刷新後再來！",
                        ephemeral=True
                    )
                    return
                course_data[self.category] = current_course_cnt + 1

            # 打工兼職判定：有賺錢
            is_work = (rew_money > 0)
            if is_work:
                if self.category not in work_places:
                    if len(work_places) >= 2:
                        await interaction.response.send_message(
                            f"🚫 **【打工兼職地點達上限】** 今日已在【{'、'.join(work_places)}】打工！每天最多只能選 2 個地點（每晚 12 點重置）。",
                            ephemeral=True
                        )
                        return
                    work_places.append(self.category)

            await db.execute("""
                INSERT INTO daily_action_limits (guild_id, char_name, date_str, course_counts, work_places)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, char_name, date_str) DO UPDATE SET
                    course_counts = excluded.course_counts,
                    work_places = excluded.work_places
            """, (self.guild_id, self.char_name, today_str, json.dumps(course_data), json.dumps(work_places)))

            # 金錢與行動點扣減
            if cost_money > 0:
                if cash >= cost_money:
                    await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (cost_money, self.guild_id, self.char_name))
                else:
                    rem = cost_money - cash
                    await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (rem, self.guild_id, self.char_name))

            if rew_money > 0:
                await db.execute("UPDATE characters SET cash = cash + ? WHERE guild_id = ? AND name = ?", (rew_money, self.guild_id, self.char_name))

            new_ap = ap - cost_ap
            new_hp = max(10, min(100, (hp or 100) + hp_chg))

            earned_notes = []
            if fixed_stat:
                for part in re.split(r"[,，、\s]+", fixed_stat):
                    m = re.search(r"([^\d+-]+)([+-]?\d+)", part)
                    if m:
                        sk, sv = m.group(1).strip(), int(m.group(2))
                        stats[sk] = max(0, stats.get(sk, 0) + sv)
                        sign = "+" if sv >= 0 else ""
                        earned_notes.append(f"{sk} {sign}{sv}")

            if rand_stats:
                stat_targets = [s.strip() for s in re.split(r"[,，、\s]+", rand_stats) if s.strip()]
                for target_stat in stat_targets:
                    random_gain = random.randint(1, 15)
                    stats[target_stat] = stats.get(target_stat, 0) + random_gain
                    earned_notes.append(f"🎯 {target_stat} +{random_gain}")

            # 解析特殊獎勵（人脈與自訂掉落物品機率）
            special_notes = []
            if spec_rew:
                tokens = re.split(r"[,，\n\r\s]+", spec_rew.strip())
                for tk in tokens:
                    if not tk: continue
                    if tk.startswith("人脈:"):
                        p_name = tk.split(":", 1)[1].strip()
                        gain_aff = random.randint(1, 5)
                        await db.execute("""
                            INSERT INTO relationships (guild_id, from_char, to_char, affection, status_desc)
                            VALUES (?, ?, ?, ?, '萍水相逢')
                            ON CONFLICT(guild_id, from_char, to_char) DO UPDATE SET affection = affection + ?
                        """, (self.guild_id, self.char_name, p_name, gain_aff, gain_aff))
                        special_notes.append(f"🤝 **【人脈結識】** 結識了 **{p_name}**，羈絆好感 **+{gain_aff}**！")
                    elif tk.startswith("物品:"):
                        # 格式：物品:名稱*數量@機率
                        raw_item_str = tk.split(":", 1)[1].strip()
                        prob = 100
                        if "@" in raw_item_str:
                            raw_item_str, prob_str = raw_item_str.split("@", 1)
                            try: prob = int(prob_str)
                            except ValueError: prob = 100

                        if random.randint(1, 100) <= prob:
                            m_item = re.match(r"^([^*xX×]+)(?:[*xX×](\d+))?$", raw_item_str)
                            it_name = m_item.group(1).strip() if m_item else raw_item_str.strip()
                            it_amt = int(m_item.group(2)) if (m_item and m_item.group(2)) else 1

                            async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (self.guild_id, self.char_name, it_name)) as inv_cur:
                                inv_row = await inv_cur.fetchone()
                                if inv_row:
                                    await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (it_amt, inv_row[0]))
                                else:
                                    await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, ?, '日常歷練機遇')", (self.guild_id, self.char_name, it_name, it_amt))
                            special_notes.append(f"🎁 **【機遇掉落】** 獲得物品：`{it_name} ×{it_amt}`！")

            await db.execute("""
                UPDATE characters
                SET action_points = ?, char_health = ?, stats = ?
                WHERE guild_id = ? AND name = ?
            """, (new_ap, new_hp, json.dumps(stats, ensure_ascii=False), self.guild_id, self.char_name))
            await db.commit()

        await check_and_update_rank(self.guild_id, self.char_name, interaction.channel)

        embed = discord.Embed(title=f"🎬 行程結算：【{self.char_name}】— {a_name}", color=0x2ECC71)
        embed.description = f"*{desc}*\n\n• 剩餘行動點：`{new_ap} AP` (-{cost_ap})\n• 當前健康度：❤️ **{new_hp} / 100** ({hp_chg:+})"
        if cost_money > 0:
            embed.add_field(name="支出費用", value=f"-${cost_money:,}", inline=True)
        if rew_money > 0:
            embed.add_field(name="所得酬勞", value=f"+${rew_money:,}", inline=True)
        if earned_notes:
            embed.add_field(name="成長收穫", value="\n".join(earned_notes), inline=False)
        if special_notes:
            embed.add_field(name="特殊機遇", value="\n".join(special_notes), inline=False)

        await interaction.response.send_message(embed=embed)


@bot.tree.command(name="行動", description="消耗行動點進行歷練、排練、私教培訓或休閒應酬")
@app_commands.describe(角色名="欲執行日常行動的角色名稱")
async def action_cmd(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, action_points, char_health FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            char_row = await cur.fetchone()

        if not char_row:
            await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
            return

        u_id, ap, hp = char_row
        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 你只能為自己的角色執行日常行動！", ephemeral=True)
            return

        async with db.execute("SELECT DISTINCT category FROM action_places WHERE guild_id = ?", (g_id,)) as cur:
            categories = [row[0] for row in await cur.fetchall()]

    if not categories:
        categories = ["練習室", "健身中心", "綜合醫院", "深夜酒館"]

    class PlaceCategoryView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            for cat_name in categories[:20]:
                btn = discord.ui.Button(label=cat_name[:20], style=discord.ButtonStyle.primary)
                btn.callback = self.make_cb(cat_name)
                self.add_item(btn)

        def make_cb(self, category_name: str):
            async def cb(inter: discord.Interaction):
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("""
                        SELECT id, action_name, description, cost_ap, cost_money,
                               reward_money, health_change, fixed_stat_change, random_stat_types, special_rewards
                        FROM action_places WHERE guild_id = ? AND category = ?
                    """, (g_id, category_name)) as cur:
                        actions = await cur.fetchall()

                if not actions:
                    await inter.response.send_message(f"📍 地點【{category_name}】目前暫未設定可執行的動作日程。", ephemeral=True)
                    return

                sub_view = discord.ui.View()
                sub_view.add_item(ExecuteActionSelect(c_name, g_id, category_name, actions))
                embed = discord.Embed(
                    title=f"📍 日程清單 — 【{category_name}】",
                    description=(
                        f"當前角色：**{c_name}**\n"
                        f"• 行動點存量：`{ap} AP`\n"
                        f"• 當前健康值：❤️ `{hp or 100} / 100`\n\n"
                        f"請從下方選單挑選欲執行的歷練："
                    ),
                    color=0x3498DB
                )
                await inter.response.send_message(embed=embed, view=sub_view, ephemeral=True)
            return cb

    embed = discord.Embed(
        title="🏙️ 演藝歷練與日常行動大廳",
        description=(
            f"操作者：**{c_name}** ｜ 行動點存量：`{ap} AP` ｜ 健康值：❤️ `{hp or 100}/100`\n\n"
            f"請點選下方你想前往的地點專區："
        ),
        color=0x2C3E50
    )
    await interaction.response.send_message(embed=embed, view=PlaceCategoryView(), ephemeral=True)
# -------------------- 指令：/使用（精確增長各項數值與體態變化） --------------------
@bot.tree.command(name="使用", description="使用背包中的道具（支援飲食身材增減、精確提升各項屬性、簽證或餵食寵物）")
@app_commands.describe(
    角色名="使用者角色名稱",
    物品名="背包中的道具名稱",
    使用數量="填純數字，或填寫［全部］（預設 1）",
    餵食目標寵物="選填：若道具為飼料/寵物用品，請填寫欲照料的寵物暱稱"
)
async def use_item(
    interaction: discord.Interaction,
    角色名: str,
    物品名: str,
    使用數量: str = "1",
    餵食目標寵物: str = None
):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    i_name = 物品名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT user_id, stats, ticket_ban_until, height, weight, char_health
            FROM characters WHERE guild_id = ? AND name = ?
        """, (g_id, c_name)) as cur:
            c_row = await cur.fetchone()
            if not c_row:
                await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
                return
            u_id, stats_json, ticket_ban, cur_h, cur_w, cur_hp = c_row

        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 你只能為自己的角色使用道具！", ephemeral=True)
            return

        async with db.execute("SELECT id, amount FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, c_name, i_name)) as cur:
            inv = await cur.fetchone()
            if not inv or inv[1] <= 0:
                await interaction.response.send_message(f"❌ 背包中查無道具【{i_name}】！", ephemeral=True)
                return
            inv_id, cur_amt = inv

        if 使用數量.strip() in ["全部", "all", "All"]:
            use_cnt = cur_amt
        else:
            try:
                use_cnt = int(使用數量.strip())
                if use_cnt <= 0: raise ValueError
            except ValueError:
                await interaction.response.send_message("❌ 請輸入正確的使用數量（純整數或填寫［全部］）！", ephemeral=True)
                return

        if use_cnt > cur_amt:
            await interaction.response.send_message(f"❌ 數量不足！背包中僅有 **{cur_amt}** 件【{i_name}】。", ephemeral=True)
            return

        async with db.execute("SELECT stat_bonus, usable, target_role_id, description FROM shop_items WHERE guild_id = ? AND name = ?", (g_id, i_name)) as cur:
            item_info = await cur.fetchone()

        stat_bonus = item_info[0] if (item_info and item_info[0]) else ""
        usable = item_info[1] if item_info else 1
        role_id = item_info[2] if item_info else 0
        desc_text = item_info[3] if (item_info and item_info[3]) else ""

        if usable == 0:
            await interaction.response.send_message(f"ℹ️ 道具【{i_name}】為純收藏紀念品，無法直接使用。", ephemeral=True)
            return

        now = time.time()
        if role_id > 0:
            if now < ticket_ban:
                rem_h = int((ticket_ban - now) / 3600)
                await interaction.response.send_message(f"🚫 該角色仍在禁令懲罰中！剩餘時間：**{rem_h}** 小時。", ephemeral=True)
                return

            role = interaction.guild.get_role(role_id)
            if role:
                try:
                    await interaction.user.add_roles(role, reason="使用地圖門票出境")
                except Exception:
                    pass

            expire_at = now + (336 * 3600)
            await db.execute("""
                INSERT INTO active_tickets (guild_id, char_name, user_id, role_id, ticket_name, start_time, expire_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (g_id, c_name, interaction.user.id, role_id, i_name, now, expire_at))

        if use_cnt == cur_amt:
            await db.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
        else:
            await db.execute("UPDATE inventory SET amount = amount - ? WHERE id = ?", (use_cnt, inv_id))

        # 1. 身高與體態動態增減
        body_change_msg = ""
        combined_text = f"{stat_bonus} {desc_text}"
        h_change, w_change = 0, 0

        h_match = re.search(r"身高([+-]?\d+)", combined_text)
        if h_match: h_change = int(h_match.group(1)) * use_cnt

        w_match = re.search(r"體重([+-]?\d+)", combined_text)
        if w_match: w_change = int(w_match.group(1)) * use_cnt

        if not w_match:
            if any(k in i_name for k in ["減脂餐", "沙拉", "排毒", "辟穀丹"]):
                w_change = -1 * use_cnt
            elif any(k in i_name for k in ["炸雞", "烤肉", "火鍋", "甜點", "大餐"]):
                w_change = 1 * use_cnt

        new_height = max(100, min(230, (cur_h or 170) + h_change))
        new_weight = max(30, min(200, (cur_w or 55) + w_change))

        char_stats = json.loads(stats_json) if stats_json else {}
        if h_change != 0 or w_change != 0:
            final_hp, final_face, new_bmi, warn_text = check_bmi_impact(new_height, new_weight, cur_hp or 100, char_stats.get("容貌", 50))
            char_stats["容貌"] = final_face
            body_change_msg = f"\n📏 **【體態變化】** 身高：`{new_height} cm` ({h_change:+}) ｜ 體重：`{new_weight} kg` ({w_change:+}) ｜ BMI: `{new_bmi}`"
            if warn_text: body_change_msg += f"\n{warn_text}"

        # 2. 寵物餵食照料
        pet_heal_msg = ""
        if "飼料" in i_name or "罐頭" in i_name or "零食" in i_name or 餵食目標寵物:
            p_target = 餵食目標寵物.strip() if 餵食目標寵物 else ""
            query = "SELECT id, pet_name, health FROM character_pets WHERE guild_id = ? AND owner_name = ? AND is_dead = 0"
            params = [g_id, c_name]
            if p_target:
                query += " AND pet_name = ?"
                params.append(p_target)
            query += " LIMIT 1"

            async with db.execute(query, tuple(params)) as p_cur:
                pet_row = await p_cur.fetchone()
                if pet_row:
                    pet_id, p_name, curr_h = pet_row
                    heal_amt = 50 * use_cnt
                    new_h = min(500, curr_h + heal_amt)
                    await db.execute("UPDATE character_pets SET health = ? WHERE id = ?", (new_h, pet_id))
                    pet_heal_msg = f"\n🐾 寵物【**{p_name}**】獲得照料，健康度提升至 **{new_h}/500** (+{heal_amt})！"

        # 3. 屬性數值精準累加
        applied_stats = []
        if stat_bonus:
            for part in re.split(r"[,，、\s]+", stat_bonus.strip()):
                m = re.search(r"([^\d+-]+)([+-]?\d+)", part)
                if m:
                    s_name = m.group(1).strip()
                    if s_name not in ["身高", "體重"]:
                        s_delta = int(m.group(2)) * use_cnt
                        char_stats[s_name] = max(0, char_stats.get(s_name, 0) + s_delta)
                        sign = "+" if s_delta >= 0 else ""
                        applied_stats.append(f"{s_name} {sign}{s_delta}")

        await db.execute("""
            UPDATE characters 
            SET height = ?, weight = ?, stats = ?
            WHERE guild_id = ? AND name = ?
        """, (new_height, new_weight, json.dumps(char_stats, ensure_ascii=False), g_id, c_name))
        await db.commit()

    if applied_stats:
        await check_and_update_rank(g_id, c_name, interaction.channel)

    extra_msg = f"\n🎫 已啟用外地簽證身分組！有效時間為 **336 小時**。" if role_id > 0 else ""
    bonus_msg = f"\n📊 **【屬性成長】** " + "、".join(applied_stats) if applied_stats else ""

    await interaction.response.send_message(
        f"✨ **{c_name}** 成功使用了道具【**{i_name}**】×{use_cnt}！{body_change_msg}{bonus_msg}{extra_msg}{pet_heal_msg}"
    )
# -------------------- 資料庫 Schema 擴充函式補齊 --------------------
async def extend_database_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        # 違規警告與處分紀錄表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS character_warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                char_name TEXT,
                rule_clause TEXT,
                reason TEXT,
                evidence_link TEXT,
                admin_name TEXT,
                warned_at REAL
            )
        """)

        # 定時自動全服公告與發獎排程表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                title TEXT,
                content TEXT,
                trigger_time REAL,
                reward_cash INTEGER DEFAULT 0,
                reward_items TEXT DEFAULT '',
                reward_stats TEXT DEFAULT '',
                target_scope TEXT DEFAULT 'all',
                role_id INTEGER DEFAULT 0,
                mention_role_id INTEGER DEFAULT 0,
                executed INTEGER DEFAULT 0
            )
        """)
        await db.commit()

async def init_auction_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS auction_house (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                item_name TEXT,
                amount INTEGER DEFAULT 1,
                seller_name TEXT DEFAULT '官方拍賣行',
                current_bid INTEGER DEFAULT 1000,
                highest_bidder_char TEXT DEFAULT '',
                highest_bidder_uid INTEGER DEFAULT 0,
                min_increment INTEGER DEFAULT 200,
                created_at REAL,
                end_time REAL,
                is_closed INTEGER DEFAULT 0
            )
        """)
        await db.commit()
# -------------------- 系統就緒啟動與定時排程掛載 --------------------
@bot.event
async def on_ready():
    await init_db()
    await extend_database_tables()
    await init_auction_table()

    # 啟動 10 大背景定時任務
    if not daily_interest.is_running(): daily_interest.start()
    if not monthly_age_up.is_running(): monthly_age_up.start()
    if not check_ticket_expiration.is_running(): check_ticket_expiration.start()
    if not daily_pet_routine.is_running(): daily_pet_routine.start()
    if not crowd_npc_fluctuation_task.is_running(): crowd_npc_fluctuation_task.start()
    if not weekly_fans_and_haters_settlement.is_running(): weekly_fans_and_haters_settlement.start()
    if not yearly_action_points_reset.is_running(): yearly_action_points_reset.start()
    if not check_scheduled_broadcasts_task.is_running(): check_scheduled_broadcasts_task.start()
    if not check_auction_closings_task.is_running(): check_auction_closings_task.start()
    if not daily_midnight_reset_task.is_running(): daily_midnight_reset_task.start()

    try:
        synced = await bot.tree.sync()
        print(f"====================================")
        print(f"🎉 成功同步了 {len(synced)} 個 Slash 指令！")
        for cmd in synced:
            print(f"📌 指令: /{cmd.name}")
        print(f"====================================")
    except Exception as e:
        print(f"❌ 指令同步失敗: {e}")

    print(f"🌟 World Engine 系統核心已順利就緒：{bot.user}")

# -------------------- 主程式啟動入口 --------------------
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ 錯誤：未偵測到環境變數 DISCORD_TOKEN！請至雲端平台後台 Environment 設定正確的 Token。")
    sys.exit(1)

try:
    bot.run(TOKEN)
except Exception as e:
    print(f"❌ 機器人啟動崩潰: {e}")
    traceback.print_exc()
    sys.exit(1)
