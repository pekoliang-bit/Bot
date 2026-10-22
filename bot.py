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
    """
    統一向管理員指定的官方通知頻道發布廣播
    event_type: 'story', 'crowd_promote', 'rank_up', 'holiday', 'penalty'
    """
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

    # 地位晉升不主動艾特，其餘若有指定身分組則發布艾特
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
        # 檢查該頻道或其父討論串是否在社群監聽名單
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

    # 1. 艾特機器人自動結算字數
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

    # 2. 自動偵測 CP 營業對戲（若發文提及登記的伴侶/CP對象）
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

# -------------------- 地位自動檢驗與晉升廣播引擎 --------------------
async def check_and_update_rank(guild_id: int, char_name: str, channel=None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT stats, works, rank, user_id, theme_color, is_npc FROM characters WHERE guild_id = ? AND name = ?", (guild_id, char_name)) as cur:
            row = await cur.fetchone()
        if not row:
            return
        stats_json, works_json, current_rank, u_id, t_color, is_npc = row
        stats = json.loads(stats_json) if stats_json else {}

        async with db.execute("""
            SELECT rank_order, rank_name, work_req, endorse_req, stat_req, max_slots 
            FROM rank_settings WHERE guild_id = ? ORDER BY rank_order ASC
        """, (guild_id,)) as cur:
            ranks = await cur.fetchall()

        guild = bot.get_guild(guild_id)

        for r_order, r_name, w_req, e_req, s_req, max_slots in ranks:
            if max_slots > 0:
                async with db.execute("SELECT COUNT(*) FROM characters WHERE guild_id = ? AND rank = ?", (guild_id, r_name)) as c_cur:
                    cnt = (await c_cur.fetchone())[0]
                if cnt >= max_slots and current_rank != r_name:
                    continue

            stat_pass = True
            if s_req:
                for part in re.split(r"[,，\s]+", s_req):
                    m = re.search(r"([^\d]+)(\d+)", part)
                    if m:
                        k, v = m.group(1).strip(), int(m.group(2))
                        if stats.get(k, 0) < v:
                            stat_pass = False
                            break
            if not stat_pass:
                continue

            if current_rank != r_name:
                await db.execute("UPDATE characters SET rank = ? WHERE guild_id = ? AND name = ?", (r_name, guild_id, char_name))
                await db.commit()

                card_color = parse_hex_color(t_color, default_color=0xF1C40F)
                promo_embed = discord.Embed(title="👑✨【榮耀加冕・地位晉升】", color=card_color)
                promo_embed.description = (
                    f"經過無數歷練與功勳積累，藝人/修行者 **{char_name}** 順利打破界限！\n\n"
                    f"• 原階級：`{current_rank or '未定級'}`\n"
                    f"• 晉升全新地位：**【{r_name}】**！"
                )
                promo_embed.set_footer(text="全服地位正式認證 ｜ 實力更上一層樓")

                if channel:
                    try:
                        await channel.send(embed=promo_embed)
                    except Exception:
                        pass

                if guild:
                    await broadcast_event(guild, "rank_up", promo_embed, mention_role=None)
                break
# -------------------- 資料庫完整初始化（包含所有核心資料表） --------------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. 角色總表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                guild_id INTEGER,
                user_id INTEGER,
                name TEXT,
                stage_name TEXT DEFAULT '',
                age INTEGER,
                gender TEXT,
                job TEXT,
                faction TEXT DEFAULT '無',
                tags TEXT DEFAULT '',
                relationship_status TEXT DEFAULT '單身',
                cp_info TEXT DEFAULT '{}',
                cash INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                works TEXT DEFAULT '[]',
                created_at REAL,
                stats TEXT DEFAULT '{}',
                ticket_ban_until REAL DEFAULT 0,
                rank TEXT DEFAULT '未定級',
                is_npc INTEGER DEFAULT 0,
                company_id INTEGER DEFAULT 0,
                image_url TEXT DEFAULT '',
                height INTEGER DEFAULT 170,
                weight INTEGER DEFAULT 55,
                nationality TEXT DEFAULT '本國',
                education TEXT DEFAULT '大學',
                orientation TEXT DEFAULT '保密',
                primary_track TEXT DEFAULT '常規',
                char_health INTEGER DEFAULT 100,
                affiliation_type TEXT DEFAULT '單打獨鬥',
                affiliation_name TEXT DEFAULT '無',
                debut_years INTEGER DEFAULT 0,
                debut_age INTEGER DEFAULT 0,
                theme_color TEXT DEFAULT '',
                action_points INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, name)
            )
        """)

        # 2. 個人背包表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                owner_name TEXT,
                item_name TEXT,
                amount INTEGER,
                giver TEXT DEFAULT '系統商城'
            )
        """)

        # 3. 商城商品表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                shop_name TEXT,
                name TEXT,
                price INTEGER,
                description TEXT,
                stat_bonus TEXT DEFAULT '',
                affinity_bonus INTEGER DEFAULT 0,
                usable INTEGER DEFAULT 1,
                target_role_id INTEGER DEFAULT 0,
                seller TEXT DEFAULT '官方',
                asset_type TEXT DEFAULT '一般',
                faction_name TEXT DEFAULT '',
                stock INTEGER DEFAULT -1,
                UNIQUE(guild_id, shop_name, name)
            )
        """)

        # 4. 可購置資產表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS available_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                asset_type TEXT,
                asset_name TEXT,
                price INTEGER,
                description TEXT DEFAULT ''
            )
        """)

        # 5. 個人產權表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS personal_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                owner_name TEXT,
                asset_type TEXT,
                asset_name TEXT,
                price INTEGER,
                details TEXT DEFAULT ''
            )
        """)

        # 6. 人際關係網絡表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                guild_id INTEGER,
                from_char TEXT,
                to_char TEXT,
                tendency TEXT DEFAULT '普通',
                affection INTEGER DEFAULT 0,
                status_desc TEXT DEFAULT '初識',
                PRIMARY KEY (guild_id, from_char, to_char)
            )
        """)

        # 7. 全域系統動態設定表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                guild_id INTEGER,
                key TEXT,
                value TEXT,
                PRIMARY KEY (guild_id, key)
            )
        """)

        # 8. 審核二次進度表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS profile_audits (
                guild_id INTEGER,
                thread_id INTEGER,
                char_name TEXT,
                audit_count INTEGER DEFAULT 0,
                status TEXT DEFAULT '審核中',
                PRIMARY KEY (guild_id, thread_id)
            )
        """)

        # 9. 公司經營體系表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                name TEXT,
                purpose TEXT,
                type_name TEXT,
                structure TEXT,
                creator_name TEXT,
                partners TEXT DEFAULT '[]',
                total_capital INTEGER DEFAULT 0,
                split_ratio REAL DEFAULT 0.5,
                allowed_jobs TEXT DEFAULT '',
                balance INTEGER DEFAULT 0
            )
        """)

        # 10. 陣營總表與成員表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS factions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                name TEXT,
                desc TEXT,
                tax_rate REAL DEFAULT 0.1,
                exit_fee INTEGER DEFAULT 5000,
                treasury INTEGER DEFAULT 0,
                weekly_gift TEXT DEFAULT '{}',
                top_rewards TEXT DEFAULT '[]'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS faction_members (
                guild_id INTEGER,
                faction_name TEXT,
                char_name TEXT,
                contribution INTEGER DEFAULT 0,
                last_gift_week INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, faction_name, char_name)
            )
        """)

        # 11. 任務與歷程表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                category TEXT,
                title TEXT,
                reward_cash INTEGER DEFAULT 0,
                reward_items TEXT DEFAULT '[]',
                reward_stats TEXT DEFAULT '',
                achievement TEXT DEFAULT '',
                honor TEXT DEFAULT '',
                requirement TEXT DEFAULT '',
                time_limit TEXT DEFAULT '',
                report_channel_id INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quest_completions (
                guild_id INTEGER,
                char_name TEXT,
                quest_title TEXT,
                completed_at REAL,
                PRIMARY KEY (guild_id, char_name, quest_title)
            )
        """)

        # 12. 地位限制表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rank_settings (
                guild_id INTEGER,
                rank_order INTEGER,
                rank_name TEXT,
                work_req TEXT DEFAULT '',
                endorse_req TEXT DEFAULT '',
                stat_req TEXT DEFAULT '',
                max_slots INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, rank_order)
            )
        """)

        # 13. 門票簽證表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS active_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                char_name TEXT,
                user_id INTEGER,
                role_id INTEGER,
                ticket_name TEXT,
                start_time REAL,
                expire_time REAL
            )
        """)

        # 14. 傳聞表與寵物表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS character_rumors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                char_name TEXT,
                rumor_text TEXT,
                created_at REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS character_pets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                owner_name TEXT,
                pet_type TEXT,
                pet_name TEXT,
                health INTEGER DEFAULT 500,
                lifespan_years INTEGER,
                adopted_at REAL,
                death_time REAL,
                is_dead INTEGER DEFAULT 0,
                funeral_done INTEGER DEFAULT 0
            )
        """)

        # 15. 劇情設定與攻略進度表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS story_scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                npc_name TEXT,
                story_title TEXT,
                unlock_condition TEXT,
                script_link TEXT,
                script_content TEXT,
                is_active INTEGER DEFAULT 1,
                UNIQUE(guild_id, npc_name, story_title)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS character_story_progress (
                guild_id INTEGER,
                char_name TEXT,
                npc_name TEXT,
                story_title TEXT,
                current_node INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                meet_count INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, char_name, npc_name, story_title)
            )
        """)

        # 16. 社群頻道與規則表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS social_monitor_channels (
                guild_id INTEGER,
                channel_id INTEGER PRIMARY KEY,
                platform_name TEXT DEFAULT '社群動態'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS social_reaction_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                trigger_type TEXT,
                trigger_key TEXT,
                target_type TEXT DEFAULT 'author',
                stat_changes TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS social_relations (
                guild_id INTEGER,
                from_char TEXT,
                to_char TEXT,
                relation_type TEXT,
                created_at REAL,
                PRIMARY KEY (guild_id, from_char, to_char)
            )
        """)

        # 17. 地點日程動作設定表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS action_places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                category TEXT,
                action_name TEXT,
                description TEXT,
                cost_ap INTEGER DEFAULT 1,
                cost_money INTEGER DEFAULT 0,
                reward_money INTEGER DEFAULT 0,
                health_change INTEGER DEFAULT 0,
                fixed_stat_change TEXT DEFAULT '',
                random_stat_types TEXT DEFAULT '',
                special_rewards TEXT DEFAULT '',
                UNIQUE(guild_id, category, action_name)
            )
        """)

        # 18. 路人專用庫（相片、姓名庫）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crowd_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                image_url TEXT,
                gender TEXT DEFAULT '通用',
                used INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crowd_names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                region TEXT,
                name_type TEXT,
                gender TEXT DEFAULT '通用',
                val TEXT
            )
        """)

        # 19. 每日行動與課程限制追蹤表（每日 00:00 自動歸零刷新）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_action_limits (
                guild_id INTEGER,
                char_name TEXT,
                date_str TEXT,
                course_counts TEXT DEFAULT '{}',
                work_places TEXT DEFAULT '[]',
                PRIMARY KEY (guild_id, char_name, date_str)
            )
        """)

        # 20. 娛樂城全服樂透獎池表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lottery_jackpot (
                guild_id INTEGER PRIMARY KEY,
                jackpot_pool INTEGER DEFAULT 10000,
                ticket_price INTEGER DEFAULT 200,
                draw_time REAL DEFAULT 0,
                winning_numbers TEXT DEFAULT ''
            )
        """)

        # 21. 玩家持有的本期樂透彩券表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lottery_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                char_name TEXT,
                user_id INTEGER,
                numbers TEXT,
                bought_at REAL
            )
        """)
        await db.commit()

# -------------------- 資料庫 Schema 擴充函式 --------------------
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

# -------------------- 拍賣行資料庫初始化 --------------------
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
# -------------------- 全系統 10 大定時背景排程群 --------------------
@tasks.loop(hours=24)
async def daily_interest():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT guild_id FROM characters") as cur:
            guild_rows = await cur.fetchall()

        for (g_id,) in guild_rows:
            async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'interest_rate'", (g_id,)) as cur:
                row = await cur.fetchone()
                rate = float(row[0]) if row else 0.05

            await db.execute(f"UPDATE characters SET bank = CAST(bank * (1 + {rate}) AS INTEGER) WHERE guild_id = ? AND bank > 0", (g_id,))
        await db.commit()

@tasks.loop(hours=1)
async def check_ticket_expiration():
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, char_name, user_id, guild_id, role_id, ticket_name FROM active_tickets WHERE expire_time <= ?", (now,)) as cur:
            expired = await cur.fetchall()

        for record in expired:
            rec_id, c_name, u_id, g_id, r_id, t_name = record
            guild = bot.get_guild(g_id)
            if guild:
                member = guild.get_member(u_id)
                role = guild.get_role(r_id)
                if member and role:
                    try:
                        await member.remove_roles(role, reason="門票逾期未歸，強制收回")
                    except Exception:
                        pass

            ban_until = now + (300 * 3600)
            await db.execute("UPDATE characters SET ticket_ban_until = ? WHERE guild_id = ? AND name = ?", (ban_until, g_id, c_name))
            await db.execute("DELETE FROM active_tickets WHERE id = ?", (rec_id,))

        await db.commit()

# 時間變化核心：預設 30 天為遊戲 1 年，年齡自動增長
@tasks.loop(hours=24)
async def monthly_age_up():
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT guild_id FROM characters") as g_cur:
            guilds = await g_cur.fetchall()

        for (g_id,) in guilds:
            async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'days_per_game_year'", (g_id,)) as s_cur:
                s_row = await s_cur.fetchone()
                days_per_year = int(s_row[0]) if s_row else 30

            cycle_seconds = days_per_year * 86400

            async with db.execute("SELECT name, age, created_at FROM characters WHERE guild_id = ?", (g_id,)) as cur:
                rows = await cur.fetchall()
                for name, age, created_at in rows:
                    years_passed = int((now - created_at) // cycle_seconds)
                    if years_passed > 0:
                        await db.execute("""
                            UPDATE characters 
                            SET age = age + ?, created_at = created_at + ? 
                            WHERE guild_id = ? AND name = ?
                        """, (years_passed, years_passed * cycle_seconds, g_id, name))

        await db.commit()

@tasks.loop(hours=48)
async def crowd_npc_fluctuation_task():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT guild_id FROM characters WHERE is_npc = 3") as cur:
            guild_rows = await cur.fetchall()

        for (g_id,) in guild_rows:
            async with db.execute("SELECT key, value FROM system_settings WHERE guild_id = ?", (g_id,)) as cur:
                settings = dict(await cur.fetchall())

            rate = float(settings.get("npc_fluct_rate", "0.05"))
            include_money = settings.get("npc_fluct_money", "1") == "1"
            max_cap = int(settings.get("npc_fluct_cap", "3000"))

            async with db.execute("SELECT name, cash, bank, stats FROM characters WHERE guild_id = ? AND is_npc = 3", (g_id,)) as c_cur:
                npcs = await c_cur.fetchall()

            for n_name, cash, bank, stats_json in npcs:
                stats = json.loads(stats_json) if stats_json else {}
                for k in stats.keys():
                    delta_pct = random.uniform(-rate, rate)
                    stats[k] = max(10, min(max_cap, int(stats[k] * (1 + delta_pct))))

                new_cash, new_bank = cash, bank
                if include_money:
                    m_rate = random.uniform(-0.06, 0.06)
                    new_cash = max(100, int(cash * (1 + m_rate)))
                    new_bank = max(500, int(bank * (1 + m_rate)))

                await db.execute("""
                    UPDATE characters SET stats = ?, cash = ?, bank = ? WHERE guild_id = ? AND name = ?
                """, (json.dumps(stats, ensure_ascii=False), new_cash, new_bank, g_id, n_name))

        await db.commit()

@tasks.loop(hours=24)
async def daily_pet_routine():
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE character_pets SET health = MAX(0, health - 5) WHERE is_dead = 0")
        async with db.execute("SELECT id, guild_id, owner_name, pet_name, pet_type FROM character_pets WHERE is_dead = 0 AND death_time <= ?", (now,)) as cur:
            dead_pets = await cur.fetchall()

        for pet_id, g_id, owner, p_name, p_type in dead_pets:
            await db.execute("UPDATE character_pets SET is_dead = 1 WHERE id = ?", (pet_id,))
            async with db.execute("SELECT user_id FROM characters WHERE guild_id = ? AND name = ?", (g_id, owner)) as u_cur:
                u_row = await u_cur.fetchone()
                if u_row:
                    user = bot.get_user(u_row[0])
                    if user:
                        try:
                            await user.send(f"🕊️ **【陪伴告別通知】**\n角色【{owner}】的夥伴 **{p_name}** ({p_type}) 壽命已盡。可撰寫悼念貼文並使用 `/喪禮結算`。")
                        except Exception:
                            pass
        await db.commit()

@tasks.loop(hours=168)
async def weekly_fans_and_haters_settlement():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT guild_id, user_id, name, bank, stats, is_npc FROM characters") as cur:
            all_chars = await cur.fetchall()

        for g_id, u_id, c_name, bank, stats_json, is_npc in all_chars:
            stats = json.loads(stats_json) if stats_json else {}
            diehard_fans = stats.get("死忠粉絲數", 0)
            haters = stats.get("活躍黑粉數", 0)

            payout = diehard_fans * 10
            new_bank = bank + payout

            hater_loss = haters // 1000
            current_passerby = stats.get("路人緣", 0)
            loss_applied = 0
            if hater_loss > 0 and current_passerby > 0:
                loss_applied = min(current_passerby, hater_loss)
                stats["路人緣"] = current_passerby - loss_applied

            await db.execute("""
                UPDATE characters SET bank = ?, stats = ? WHERE guild_id = ? AND name = ?
            """, (new_bank, json.dumps(stats, ensure_ascii=False), g_id, c_name))
        await db.commit()

@tasks.loop(hours=720)
async def yearly_action_points_reset():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE characters SET action_points = 0 WHERE action_points > 0")
        await db.commit()
    print("🔄【年度清算】全服藝人/角色未使用的日常行動點已全額清零重置！")

@tasks.loop(seconds=60)
async def check_scheduled_broadcasts_task():
    now_ts = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id, guild_id, title, content, reward_cash, reward_items,
                   reward_stats, target_scope, role_id, mention_role_id
            FROM scheduled_broadcasts
            WHERE trigger_time <= ? AND executed = 0
        """, (now_ts,)) as cur:
            tasks_to_run = await cur.fetchall()

        for b_id, g_id, title, content, r_cash, r_items, r_stats, target_scope, target_role_id, mention_role_id in tasks_to_run:
            guild = bot.get_guild(g_id)
            if not guild:
                await db.execute("UPDATE scheduled_broadcasts SET executed = 1 WHERE id = ?", (b_id,))
                continue

            query = "SELECT name, user_id, bank, stats FROM characters WHERE guild_id = ? AND is_npc = 0"
            params = [g_id]
            if target_scope.startswith("faction:"):
                f_name = target_scope.split(":", 1)[1]
                query += " AND faction = ?"
                params.append(f_name)

            async with db.execute(query, tuple(params)) as c_cur:
                eligible_chars = await c_cur.fetchall()

            distributed_count = 0
            for c_name, u_id, cur_bank, s_json in eligible_chars:
                if target_role_id > 0:
                    member = guild.get_member(u_id)
                    if not member or target_role_id not in [r.id for r in member.roles]:
                        continue

                if r_cash > 0:
                    await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (r_cash, g_id, c_name))

                if r_items:
                    for it_token in re.split(r"[,，\s]+", r_items.strip()):
                        if not it_token: continue
                        m = re.match(r"^([^*xX×]+)(?:[*xX×](\d+))?$", it_token)
                        it_name = m.group(1).strip() if m else it_token.strip()
                        it_amt = int(m.group(2)) if (m and m.group(2)) else 1

                        async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, c_name, it_name)) as inv_cur:
                            inv_row = await inv_cur.fetchone()
                            if inv_row:
                                await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (it_amt, inv_row[0]))
                            else:
                                await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, ?, '官方預約活動獎勵')", (g_id, c_name, it_name, it_amt))

                if r_stats:
                    c_stats = json.loads(s_json) if s_json else {}
                    for part in re.split(r"[,，\s]+", r_stats.strip()):
                        m = re.search(r"([^\d+-]+)([+-]?\d+)", part)
                        if m:
                            k, v = m.group(1).strip(), int(m.group(2))
                            c_stats[k] = max(0, c_stats.get(k, 0) + v)
                    await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(c_stats, ensure_ascii=False), g_id, c_name))

                distributed_count += 1

            await db.execute("UPDATE scheduled_broadcasts SET executed = 1 WHERE id = ?", (b_id,))
            await db.commit()

            mention_r = guild.get_role(mention_role_id) if mention_role_id > 0 else None
            embed = discord.Embed(title=f"🎁 官方活動公告：【{title}】", color=0xF1C40F)
            embed.description = f"{content}\n\n"
            
            rew_lines = []
            if r_cash > 0: rew_lines.append(f"• 💰 銀行補貼：**+${r_cash:,}**")
            if r_items: rew_lines.append(f"• 📦 道具犒賞：`{r_items}`")
            if r_stats: rew_lines.append(f"• ✨ 屬性加持：`{r_stats}`")
            
            embed.add_field(name="📜 福利犒賞清單", value="\n".join(rew_lines) if rew_lines else "專屬名譽榮耀", inline=False)
            embed.set_footer(text=f"全自動發放完畢 ｜ 共計 {distributed_count} 位符合資格角色已同步領取")

            await broadcast_event(guild, "holiday", embed, mention_role=mention_r)

@tasks.loop(minutes=10)
async def check_auction_closings_task():
    now_ts = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id, guild_id, item_name, amount, current_bid, highest_bidder_char, highest_bidder_uid
            FROM auction_house
            WHERE end_time <= ? AND is_closed = 0
        """, (now_ts,)) as cur:
            closed_auctions = await cur.fetchall()

        for a_id, g_id, it_name, it_amt, final_price, winner_char, winner_uid in closed_auctions:
            guild = bot.get_guild(g_id)
            if winner_char and winner_uid > 0:
                async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, winner_char, it_name)) as inv_cur:
                    inv_row = await inv_cur.fetchone()
                    if inv_row:
                        await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (it_amt, inv_row[0]))
                    else:
                        await db.execute("""
                            INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver)
                            VALUES (?, ?, ?, ?, '拍賣行競拍得標')
                        """, (g_id, winner_char, it_name, it_amt))

                if guild:
                    embed = discord.Embed(title=f"🔨【拍賣行結標】《{it_name}》", color=0x2ECC71)
                    embed.description = (
                        f"恭喜 **{winner_char}** (<@{winner_uid}>) 以 **${final_price:,}** 成功競標下【**{it_name}**】×{it_amt}！\n"
                        f"物品已全自動匯入個人背包。"
                    )
                    await broadcast_event(guild, "holiday", embed)
            
            await db.execute("UPDATE auction_house SET is_closed = 1 WHERE id = ?", (a_id,))
        await db.commit()

# 每日午夜 00:00 刷新打工選點上限與課程計數
@tasks.loop(minutes=1)
async def daily_midnight_reset_task():
    now = datetime.now()
    if now.hour == 0 and now.minute == 0:
        today_str = now.strftime("%Y-%m-%d")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM daily_action_limits WHERE date_str != ?", (today_str,))
            await db.commit()
        print("🌙【每日刷新】打工選定地點上限與課程 5 次計數已全數重置！")
# -------------------- 指令：/檔案總覽 --------------------
class MasterDirectoryView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id

    @discord.ui.button(label="📜 玩家指令", style=discord.ButtonStyle.primary, row=0)
    async def cmd_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        text = (
            "**👤 玩家常規指令列表：**\n"
            "• /檔案建立：建立玩家個人角色或原創角色\n"
            "• /檔案更新：修改藝名、職業、感情、CP、色碼與標籤（數值/身材鎖死）\n"
            "• /查看：調閱個人名下角色/原創角面板、成就、寵物、傳聞與攻略指引\n"
            "• /npc查看：開啟官方 NPC 或大眾路人查閱大廳\n"
            "• /行動：執行地點歷練（上課每日限5次、打工每日限2地、人脈好感）\n"
            "• /使用：使用道具（增長數值、增減身材體態、重算BMI、餵寵物）\n"
            "• /商城：購買官方商品、直達快捷購買行動點、二手專區\n"
            "• /售物：二手寄售（個人創作作品享受才智談判溢價認證）\n"
            "• /資產系統：購置名車房產、申請加入或創立公司（計入財富榜）\n"
            "• /拍賣行、/拍賣競標：全服拍賣會場檢視與加價競標\n"
            "• /娛樂城：比大小骰子、九宮格刮刮樂、購買累積樂透彩券\n"
            "• /排行榜：依據各項自訂算式查閱全服各類榜單\n"
            "• /存錢、/取錢、/轉帳：銀行存提款與角色間相互轉帳\n"
            "• /任務、/回報任務：查看通告、回報任務（陣營抽稅與正式出道）\n"
            "• /陣營、/陣營排行榜：陣營九大事務操作與全服總威望榜\n"
            "• /寵物購買、/喪禮結算：認養毛小孩與身後悼念結算"
        )
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="🛡️ 管理員指令", style=discord.ButtonStyle.danger, row=0)
    async def cmd_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        text = (
            "**👑 管理員整合控制指令：**\n"
            "• /系統頻道與開關總管：綁定通知大廳、社群頻道、時間流速與存款利息\n"
            "• /人物與NPC總管：登記官方NPC、生成路人、路人轉正、48小時生態浮動\n"
            "• /世界觀自訂：置換全服面板詞彙、組織名冊與各組屬性清單\n"
            "• /標籤管理：擴充常規標籤、雙向衝突組、設定特殊限定標籤\n"
            "• /動作設定：自訂地點行為、AP與金錢消耗、打工報酬、掉落道具機率\n"
            "• /劇本設定：錄入官方 NPC 專屬攻略劇情\n"
            "• /任務新增：發布各類通告任務與限時任務\n"
            "• /審核通過：兩段式審核人設單（初審打勾、二審核發啟動金與身分組）\n"
            "• /商城總管：商品上下架、發放薪水至手頭現金\n"
            "• /陣營：新增陣營、捐獻、金主、查看領週禮包、買商城、退陣營、加入、全體加成\n"
            "• /資產系統與資產系統更新：購置名車房產、申請加入、創建或上架新資產\n"
            "• /排行榜管理：自由增減排行榜並自訂加減乘除公式\n"
            "• /彩票管理：設定比大小底注、刮刮樂與樂透搖號開獎\n"
            "• /違規懲戒：警告扣10%/20%數值；第3次封殺踢出、撕卡瓜分遺產與拍賣\n"
            "• /發布傳聞：發布傳聞，累積滿3次自動貼標籤\n"
            "• /預約公告發獎：排程全自動發放福利並廣播公告"
        )
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="🏷️ 標籤庫", style=discord.ButtonStyle.secondary, row=1)
    async def view_all_tags(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🏷️ 全體特色標籤一覽表", color=0xF39C12)
        embed.add_field(name="通用特質標籤", value="、".join(UNIVERSAL_TAGS), inline=False)
        conflict_pairs = [f"{k} ⇄ {', '.join(v)}" for k, v in TAG_CONFLICTS.items()]
        embed.add_field(name="雙向衝突互斥組", value="\n".join(conflict_pairs[:8]), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="檔案總覽", description="調閱全系統分類導航總目錄（指令、路人、玩家、標籤）")
async def master_overview_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📑 系統檔案與指令整合導航中心", description="請點選下方按鈕切換查閱各項名冊、指引與標籤規則：", color=0x2ECC71)
    await interaction.response.send_message(embed=embed, view=MasterDirectoryView(interaction.guild_id), ephemeral=True)

# -------------------- 指令：/查看（個人角色雙頁面板調閱） --------------------
@bot.tree.command(name="查看", description="調閱個人角色或原創角色面板（含數值、歷練、寵物、傳聞與攻略指引）")
@app_commands.describe(角色名="【選填】欲直接查閱的角色姓名，留空則開啟名下選單")
async def view_profile_cmd(interaction: discord.Interaction, 角色名: str = None):
    g_id = interaction.guild_id
    u_id = interaction.user.id
    is_admin = interaction.user.guild_permissions.administrator

    # 若玩家有手動填入名字
    if 角色名:
        target_name = 角色名.strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, is_npc FROM characters WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
                row = await cur.fetchone()

        if not row:
            await interaction.response.send_message(f"❌ 查無角色檔案【{target_name}】！", ephemeral=True)
            return

        c_uid, is_npc = row
        # 若為個人角色或原創角，且不是本人也不是管理員，則不可查看隱私或需公開展示
        await render_character_card(interaction, target_name, ephemeral=True)
        return

    # 若留空，自動篩選名下持有的角色（包含 0: 自身角色, 2: 原創角）
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, is_npc FROM characters WHERE guild_id = ? AND user_id = ? AND is_npc IN (0, 2)", (g_id, u_id)) as cur:
            my_chars = await cur.fetchall()

    if not my_chars:
        await interaction.response.send_message("❌ 你目前名下尚未登記任何角色！請先使用 `/檔案建立` 創建個人角色或原創角。", ephemeral=True)
        return

    # 若只有 1 位角色，直接渲染卡片
    if len(my_chars) == 1:
        await render_character_card(interaction, my_chars[0][0], ephemeral=True)
        return

    # 若有多位角色，提供下拉選單挑選
    class PickCharSelect(discord.ui.Select):
        def __init__(self):
            opts = []
            for c_name, c_type in my_chars[:25]:
                label_str = "［原創角］" if c_type == 2 else "［個人角色］"
                opts.append(discord.SelectOption(
                    label=c_name,
                    value=c_name,
                    description=f"查看 {label_str} {c_name} 的詳細檔案面板"
                ))
            super().__init__(placeholder="請選擇欲調閱的角色檔案...", options=opts)

        async def callback(self, s_inter: discord.Interaction):
            chosen = self.values[0]
            await render_character_card(s_inter, chosen, ephemeral=True)

    select_view = discord.ui.View(timeout=120)
    select_view.add_item(PickCharSelect())
    await interaction.response.send_message("📋 你名下持有多位角色，請從下方選單點選欲查看的檔案：", view=select_view, ephemeral=True)


# -------------------- 指令：/npc查看（官方NPC與動態路人大廳） --------------------
@bot.tree.command(name="npc查看", description="調閱伺服器內所有官方重要人物或動態大眾路人 NPC")
@app_commands.choices(類別=[
    app_commands.Choice(name="🌟 官方 NPC (重要角色)", value="official"),
    app_commands.Choice(name="👥 動態大眾路人 NPC", value="crowd")
])
@app_commands.describe(類別="選擇欲查看的 NPC 分類", 姓名="【選填】若已知姓名可直接輸入，留空則列出清單")
async def view_npc_cmd(interaction: discord.Interaction, 類別: app_commands.Choice[str], 姓名: str = None):
    g_id = interaction.guild_id
    cat = 類別.value

    # 若有填寫姓名，直接調閱
    if 姓名:
        target_name = 姓名.strip()
        target_code = 1 if cat == "official" else 3
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM characters WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
                if not await cur.fetchone():
                    await interaction.response.send_message(f"❌ 查無檔案【{target_name}】！", ephemeral=True)
                    return

        await render_character_card(interaction, target_name, ephemeral=True)
        return

    # 若未填姓名，列出清單並提供下拉選單
    target_code = 1 if cat == "official" else 3
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT name, job, faction, rank
            FROM characters 
            WHERE guild_id = ? AND is_npc = ?
            ORDER BY rank DESC, name ASC
        """, (g_id, target_code)) as cur:
            npc_list = await cur.fetchall()

    if not npc_list:
        label = "官方重要人物" if cat == "official" else "動態大眾路人"
        await interaction.response.send_message(f"ℹ️ 本伺服器目前尚未建立任何【{label}】檔案。", ephemeral=True)
        return

    class NpcSelect(discord.ui.Select):
        def __init__(self):
            opts = []
            for n_name, n_job, n_fac, n_rank in npc_list[:25]:
                opts.append(discord.SelectOption(
                    label=f"{n_name}（{n_job}）",
                    value=n_name,
                    description=f"階級: {n_rank or '未定級'} ｜ 所屬: {n_fac}"
                ))
            super().__init__(placeholder=f"請挑選欲查閱的【{類別.name}】...", options=opts)

        async def callback(self, s_inter: discord.Interaction):
            await render_character_card(s_inter, self.values[0], ephemeral=True)

    npc_view = discord.ui.View(timeout=120)
    npc_view.add_item(NpcSelect())

    embed = discord.Embed(
        title=f"🏛️ 演藝界名冊 — 【{類別.name}】",
        description=f"共計收錄 `{len(npc_list)}` 位角色。\n請從下方選單選取欲查閱的檔案卡片：",
        color=0x9B59B6 if cat == "official" else 0xE67E22
    )
    for n_name, n_job, n_fac, n_rank in npc_list[:10]:
        embed.add_field(name=f"• **{n_name}** ({n_job})", value=f"地位: 【{n_rank or '未定級'}】 ｜ 勢力: {n_fac}", inline=True)

    await interaction.response.send_message(embed=embed, view=npc_view, ephemeral=True)
# -------------------- 創角交互流程 View --------------------
class CreateProfileFlowView(discord.ui.View):
    def __init__(self, guild_id: int, char_name: str, age: int, gender: str):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.char_name = char_name
        self.age = age
        self.gender = gender
        self.selected_tags = []

        avail_tags = get_available_tags_for(age, gender)
        tag_options = [
            discord.SelectOption(label=tag, value=tag, description=f"特質標籤：{tag}")
            for tag in avail_tags[:25]
        ]

        class TagSelect(discord.ui.Select):
            def __init__(sub_self):
                super().__init__(
                    placeholder="【步驟 1/2】請勾選特質標籤 (最多 2 個)...",
                    min_values=1,
                    max_values=min(2, len(tag_options)),
                    options=tag_options
                )

            async def callback(sub_self, inter: discord.Interaction):
                chosen = sub_self.values
                if len(chosen) == 2:
                    t1, t2 = chosen[0], chosen[1]
                    if t2 in TAG_CONFLICTS.get(t1, []):
                        await inter.response.send_message(f"❌ 標籤衝突！【{t1}】與【{t2}】互相對立，請重新挑選！", ephemeral=True)
                        return

                sub_self.view.selected_tags = chosen
                sub_self.view.setup_debut_step()
                await inter.response.edit_message(
                    content=f"🏷️ 已選定標籤：`{'、'.join(chosen)}`\n👇 請接著選擇【修行/入行資歷時長】：",
                    view=sub_self.view
                )

        self.add_item(TagSelect())

    def setup_debut_step(self):
        self.clear_items()
        max_d = max(0, self.age - 5)
        step = max(1, max_d // 10)
        opts_years = sorted(list(set([0] + list(range(1, max_d + 1, step)) + [max_d])))

        debut_options = [
            discord.SelectOption(
                label=f"資歷 {y} 年 (於 {self.age - y} 歲入行)",
                value=str(y),
                description="🌟 5~12歲入行將獲認證「國民系列」標籤！" if 5 <= (self.age - y) <= 12 else "常規歷練年資"
            ) for y in opts_years[:25]
        ]

        parent = self

        class DebutSelect(discord.ui.Select):
            def __init__(sub_self):
                super().__init__(placeholder="【步驟 2/2】請點選角色資歷時長...", options=debut_options)

            async def callback(sub_self, inter: discord.Interaction):
                chosen_years = int(sub_self.values[0])
                debut_age = parent.age - chosen_years
                final_tags = list(parent.selected_tags)

                kid_tag_msg = ""
                if 5 <= debut_age <= 12:
                    kid_tag = "國民弟弟" if parent.gender == "男" and parent.age <= 22 else (
                        "國民妹妹" if parent.gender == "女" and parent.age <= 22 else (
                            "國民兒子" if parent.gender == "男" else "國民女兒"
                        )
                    )
                    if kid_tag not in final_tags:
                        final_tags.append(kid_tag)
                        kid_tag_msg = f"\n🎉 **童星/少年入行認證！** 額外獲頒公認標籤：【`{kid_tag}`】"

                tags_str = "、".join(final_tags[:5])
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("""
                        UPDATE characters SET tags = ?, debut_years = ?, debut_age = ?
                        WHERE guild_id = ? AND name = ?
                    """, (tags_str, chosen_years, debut_age, parent.guild_id, parent.char_name))
                    await db.commit()

                await inter.response.edit_message(
                    content=(
                        f"✅ **【{parent.char_name}】建檔全部完成！**\n"
                        f"• 特質標籤：`{tags_str}`\n"
                        f"• 資歷時長：**{chosen_years} 年**（於 {debut_age} 歲入行）{kid_tag_msg}\n"
                        f"隨時可使用 `/查看` 調閱完整檔案！"
                    ),
                    view=None
                )

        self.add_item(DebutSelect())


# -------------------- 指令：/檔案更新（鎖定身材與數值，純個資修改） --------------------
@bot.tree.command(name="檔案更新", description="更新個人角色、原創角或官方NPC的個資資料")
@app_commands.choices(類別=[
    app_commands.Choice(name="自身角色", value="角色"),
    app_commands.Choice(name="原創角", value="原創角"),
    app_commands.Choice(name="官方 NPC (管理員限定)", value="官方npc")
])
async def update_profile_cmd(interaction: discord.Interaction, 類別: app_commands.Choice[str]):
    g_id = interaction.guild_id
    is_admin = interaction.user.guild_permissions.administrator

    async with aiosqlite.connect(DB_PATH) as db:
        if 類別.value == "官方npc":
            if not is_admin:
                await interaction.response.send_message("❌ 僅有管理員可操作官方 NPC！", ephemeral=True)
                return
            async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND is_npc = 1", (g_id,)) as cur:
                candidates = [r[0] for r in await cur.fetchall()]
        elif 類別.value == "原創角":
            async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND user_id = ? AND is_npc = 2", (g_id, interaction.user.id)) as cur:
                candidates = [r[0] for r in await cur.fetchall()]
        else:
            if is_admin:
                async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND is_npc = 0", (g_id,)) as cur:
                    candidates = [r[0] for r in await cur.fetchall()]
            else:
                async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND user_id = ? AND is_npc = 0", (g_id, interaction.user.id)) as cur:
                    candidates = [r[0] for r in await cur.fetchall()]

    if not candidates:
        await interaction.response.send_message(f"❌ 查無符合【{類別.name}】的可操作名單！", ephemeral=True)
        return

    if len(candidates) > 1:
        class CharPickView(discord.ui.View):
            @discord.ui.select(placeholder="請選擇欲更新的檔案...", options=[discord.SelectOption(label=c, value=c) for c in candidates[:25]])
            async def select_callback(self, inter: discord.Interaction, select: discord.ui.Select):
                view = ProfileUpdateStepView(select.values[0], g_id, is_admin)
                await inter.response.send_message(f"⚙️ 正在更新【{select.values[0]}】的檔案，請點選下方操作：", view=view, ephemeral=True)

        await interaction.response.send_message("請先選擇要更新的角色檔案：", view=CharPickView(), ephemeral=True)
    else:
        char_name = candidates[0]
        view = ProfileUpdateStepView(char_name, g_id, is_admin)
        await interaction.response.send_message(f"⚙️ 正在更新【{char_name}】的檔案，請點選下方操作：", view=view, ephemeral=True)
# -------------------- 指令：/商城總管 --------------------
@bot.tree.command(name="商城總管", description="【管理員專用】商城商品上下架、資產上架與直接發放薪水至角色手頭現金")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="📦 上架道具/飲食/用品", value="add_item"),
    app_commands.Choice(name="🚗 上架固定資產 (房產/座駕)", value="add_asset"),
    app_commands.Choice(name="🗑️ 下架商品", value="remove_item"),
    app_commands.Choice(name="💵 發放薪水至手頭現金", value="pay_salary")
])
@app_commands.describe(
    操作="選擇要執行的商城管理項目",
    專區名稱="商城分類專區 (例如: 官方商城、必備用品、美食珍饈、房產座駕)",
    物品名稱="物品、資產名稱",
    價格="販售單價 (純整數)",
    描述="商品或資產功能介紹",
    屬性加成="使用後提供的數值加成 (例如: 容貌+5 流量熱度+20 身高+1 體重-1)",
    限量庫存="庫存數量 (填純數字，填 -1 代表無限庫存)",
    資產類型="若為資產請填寫 (例如: 跑車、豪宅、頂層公寓、私人飛機)",
    發放薪水對象角色="［發放薪水］請填寫收款角色全名",
    發放薪水金額="［發放薪水］發放的手頭現金額度",
    門票身分組="使用後賦予的外地簽證/特殊身分組 (選填)"
)
async def shop_admin_cmd(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    專區名稱: str = "官方商城",
    物品名稱: str = None,
    價格: int = 0,
    描述: str = "官方出品",
    屬性加成: str = "",
    限量庫存: int = -1,
    資產類型: str = "一般",
    發放薪水對象角色: str = None,
    發放薪水金額: int = 0,
    門票身分組: discord.Role = None
):
    g_id = interaction.guild_id
    op = 操作.value

    # 1. 發放薪水至手頭現金
    if op == "pay_salary":
        if not 發放薪水對象角色 or 發放薪水金額 <= 0:
            await interaction.response.send_message("❌ 請填寫【發放薪水對象角色】全名與大於 0 的【發放薪水金額】！", ephemeral=True)
            return

        target_char = 發放薪水對象角色.strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, cash FROM characters WHERE guild_id = ? AND name = ?", (g_id, target_char)) as cur:
                c_row = await cur.fetchone()

            if not c_row:
                await interaction.response.send_message(f"❌ 查無角色檔案【{target_char}】！", ephemeral=True)
                return

            u_id, cur_cash = c_row
            await db.execute("UPDATE characters SET cash = cash + ? WHERE guild_id = ? AND name = ?", (發放薪水金額, g_id, target_char))
            await db.commit()

        # 嘗試私訊通知
        member = interaction.guild.get_member(u_id)
        if member:
            try:
                await member.send(f"💼 **【薪資/酬勞入帳通知】**\n管理員已向你的角色【**{target_char}**】發放薪水 **${發放薪水金額:,}** 現金（手頭現金額度已同步增加）！")
            except Exception:
                pass

        await interaction.response.send_message(
            f"💵 成功向 **{target_char}** (<@{u_id}>) 發放薪資 **${發放薪水金額:,}**！已直接存入其手頭現金。",
            ephemeral=False
        )
        return

    # 2. 上架一般道具／飲食
    elif op == "add_item":
        if not 物品名稱 or 價格 <= 0:
            await interaction.response.send_message("❌ 上架物品必須包含【物品名稱】且【價格】需大於 0！", ephemeral=True)
            return

        i_name = 物品名稱.strip()
        s_name = 專區名稱.strip()
        role_id = 門票身分組.id if 門票身分組 else 0

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO shop_items (
                    guild_id, shop_name, name, price, description,
                    stat_bonus, usable, target_role_id, seller, stock
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, '官方', ?)
                ON CONFLICT(guild_id, shop_name, name) DO UPDATE SET
                    price = excluded.price,
                    description = excluded.description,
                    stat_bonus = excluded.stat_bonus,
                    target_role_id = excluded.target_role_id,
                    stock = excluded.stock
            """, (g_id, s_name, i_name, 價格, 描述.strip(), 屬性加成.strip(), role_id, 限量庫存))
            await db.commit()

        stock_str = "無限" if 限量庫存 == -1 else f"{限量庫存} 件"
        role_str = f" ｜ 關聯身分組: {門票身分組.mention}" if 門票身分組 else ""
        bonus_str = f" ｜ 屬性: `{屬性加成.strip()}`" if 屬性加成.strip() else ""

        await interaction.response.send_message(
            f"✅ **【商品上架成功】**\n"
            f"• 專區：【{s_name}】\n"
            f"• 物品：**{i_name}**\n"
            f"• 單價：**${價格:,}** (庫存: {stock_str}){bonus_str}{role_str}",
            ephemeral=True
        )
        return

    # 3. 上架房產／座駕固定資產
    elif op == "add_asset":
        if not 物品名稱 or 價格 <= 0:
            await interaction.response.send_message("❌ 上架資產必須包含【物品名稱】且【價格】需大於 0！", ephemeral=True)
            return

        a_name = 物品名稱.strip()
        a_type = 資產類型.strip()

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO available_assets (guild_id, asset_type, asset_name, price, description)
                VALUES (?, ?, ?, ?, ?)
            """, (g_id, a_type, a_name, 價格, 描述.strip()))

            # 同步放入專屬商城專區供選購
            await db.execute("""
                INSERT INTO shop_items (
                    guild_id, shop_name, name, price, description, asset_type, usable, seller, stock
                ) VALUES (?, '房產座駕', ?, ?, ?, ?, 0, '官方房產中心', ?)
                ON CONFLICT(guild_id, shop_name, name) DO UPDATE SET
                    price = excluded.price,
                    description = excluded.description,
                    asset_type = excluded.asset_type,
                    stock = excluded.stock
            """, (g_id, a_name, 價格, 描述.strip(), a_type, 限量庫存))
            await db.commit()

        await interaction.response.send_message(
            f"🚗🏡 **【資產物業上架成功】**\n"
            f"• 資產類別：`{a_type}`\n"
            f"• 資產名稱：**{a_name}**\n"
            f"• 售價：**${價格:,}**",
            ephemeral=True
        )
        return

    # 4. 下架商品
    elif op == "remove_item":
        if not 物品名稱:
            await interaction.response.send_message("❌ 請填寫欲下架的【物品名稱】！", ephemeral=True)
            return

        i_name = 物品名稱.strip()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM shop_items WHERE guild_id = ? AND name = ?", (g_id, i_name))
            await db.execute("DELETE FROM available_assets WHERE guild_id = ? AND asset_name = ?", (g_id, i_name))
            await db.commit()

        await interaction.response.send_message(f"🗑️ 已成功將商品/資產【**{i_name}**】從商城全數下架！", ephemeral=True)
        return


# -------------------- 指令：/陣營管理 --------------------
@bot.tree.command(name="陣營管理", description="【管理員專用】創立陣營、調整抽稅與違約金、金主注資與全體犒賞")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="🚩 建立/覆蓋陣營", value="create_faction"),
    app_commands.Choice(name="💰 金主降臨無償注資公款", value="sponsor_fund"),
    app_commands.Choice(name="🎁 發放全陣營榮耀犒賞", value="reward_all_members"),
    app_commands.Choice(name="🗑️ 解散刪除陣營", value="delete_faction")
])
@app_commands.describe(
    操作="選擇要執行的陣營管理動作",
    陣營名稱="目標陣營名稱",
    陣營介紹="陣營背景或勢力綱領",
    抽稅比例="日常任務公款抽稅百分比 (填純數字，例如 10 代表 10%)",
    退出違約金="退出該陣營需賠付的違約金 (純整數，例如 5000)",
    注資或犒賞金額="金主注資數額 或 每人犒賞金額"
)
async def faction_admin_cmd(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    陣營名稱: str,
    陣營介紹: str = "世界觀陣營勢力",
    抽稅比例: float = 10.0,
    退出違約金: int = 5000,
    注資或犒賞金額: int = 0
):
    g_id = interaction.guild_id
    f_name = 陣營名稱.strip()
    op = 操作.value

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. 建立 / 覆蓋陣營
        if op == "create_faction":
            tax_rate = max(0.0, min(1.0, 抽稅比例 / 100.0))
            await db.execute("""
                INSERT INTO factions (guild_id, name, desc, tax_rate, exit_fee)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, name) DO UPDATE SET
                    desc = excluded.desc,
                    tax_rate = excluded.tax_rate,
                    exit_fee = excluded.exit_fee
            """, (g_id, f_name, 陣營介紹.strip(), tax_rate, 退出違約金))
            await db.commit()

            embed = discord.Embed(title=f"🚩 陣營勢力【{f_name}】配置成功", color=0xE74C3C)
            embed.description = f"*{陣營介紹.strip()}*\n\n• 任務公款抽稅：`{抽稅比例}%`\n• 違約解約金：`${退出違約金:,}`"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 2. 金主無償注資公款
        elif op == "sponsor_fund":
            if 注資或犒賞金額 <= 0:
                await interaction.response.send_message("❌ 請填寫大於 0 的【注資或犒賞金額】！", ephemeral=True)
                return

            async with db.execute("SELECT treasury FROM factions WHERE guild_id = ? AND name = ?", (g_id, f_name)) as cur:
                f_row = await cur.fetchone()

            if not f_row:
                await interaction.response.send_message(f"❌ 查無陣營【{f_name}】！", ephemeral=True)
                return

            await db.execute("UPDATE factions SET treasury = treasury + ? WHERE guild_id = ? AND name = ?", (注資或犒賞金額, g_id, f_name))
            await db.commit()

            embed = discord.Embed(title=f"💎 金主注資：【{f_name}】實力暴漲！", color=0xF1C40F)
            embed.description = (
                f"得益於頂級財閥與幕後金主看好，為勢力陣營【**{f_name}**】無償注資注入資金！\n\n"
                f"• 本次注資公款：**+${注資或犒賞金額:,}**\n"
                f"• 公款目前儲備：**${f_row[0] + 注資或犒賞金額:,}**"
            )
            await broadcast_event(interaction.guild, "holiday", embed)
            await interaction.response.send_message(f"✅ 成功為【{f_name}】注資 **${注資或犒賞金額:,}**！已廣播至通知大廳。")
            return

        # 3. 發放全陣營犒賞
        elif op == "reward_all_members":
            if 注資或犒賞金額 <= 0:
                await interaction.response.send_message("❌ 請填寫每位成員可獲得的大於 0 的【注資或犒賞金額】！", ephemeral=True)
                return

            async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND faction = ? AND is_npc = 0", (g_id, f_name)) as cur:
                members = [r[0] for r in await cur.fetchall()]

            if not members:
                await interaction.response.send_message(f"ℹ️ 陣營【{f_name}】目前暫無任何在籍玩家角色。", ephemeral=True)
                return

            await db.execute("""
                UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND faction = ? AND is_npc = 0
            """, (注資或犒賞金額, g_id, f_name))
            await db.commit()

            embed = discord.Embed(title=f"🏆【{f_name}】榮耀加身・全陣營犒賞！", color=0x2ECC71)
            embed.description = (
                f"陣營掌舵人下發特級福利！【**{f_name}**】全體在籍成員榮獲官方專屬犒賞！\n\n"
                f"• 每人銀行到帳：**+${注資或犒賞金額:,}**\n"
                f"• 受惠成員人數：共 `{len(members)}` 位正式成員"
            )
            await broadcast_event(interaction.guild, "holiday", embed)
            await interaction.response.send_message(f"✅ 成功向【{f_name}】共 {len(members)} 位成員發放每人 **${注資或犒賞金額:,}**！")
            return

        # 4. 刪除解散陣營
        elif op == "delete_faction":
            await db.execute("DELETE FROM factions WHERE guild_id = ? AND name = ?", (g_id, f_name))
            await db.execute("UPDATE characters SET faction = '無' WHERE guild_id = ? AND faction = ?", (g_id, f_name))
            await db.execute("DELETE FROM faction_members WHERE guild_id = ? AND faction_name = ?", (g_id, f_name))
            await db.commit()
            await interaction.response.send_message(f"🗑️ 已解散陣營【{f_name}】，原成員已全數重置為無所屬狀態！", ephemeral=True)
            return
# -------------------- 排行榜資料庫 Schema 擴充 --------------------
async def init_leaderboard_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        # 自訂動態排行榜設定表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS custom_leaderboards (
                guild_id INTEGER,
                board_name TEXT,
                formula TEXT,
                description TEXT DEFAULT '',
                PRIMARY KEY (guild_id, board_name)
            )
        """)
        await db.commit()

# 安全四則運算算分解析器
def safe_eval_formula(formula: str, char_data: dict) -> float:
    try:
        expr = formula
        # 替換變數名稱為具體數值
        for key in sorted(char_data.keys(), key=len, reverse=True):
            if key in expr:
                val = str(char_data.get(key, 0))
                expr = re.sub(rf"\b{re.escape(key)}\b", val, expr)

        # 僅允許數字與基本運算符，防止代碼注入
        if not re.match(r"^[\d\s\+\-\*\/\(\)\.]+$", expr):
            return 0.0

        # 計算結果
        return round(float(eval(expr, {"__builtins__": None}, {})), 1)
    except Exception:
        return 0.0

# -------------------- 指令：/排行榜管理（管理員設定算式增減） --------------------
@bot.tree.command(name="排行榜管理", description="【管理員專用】新增、刪除自訂排行榜，並設定加減乘除算分公式")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="➕ 新增/更新排行榜", value="set"),
    app_commands.Choice(name="🗑️ 刪除指定排行榜", value="delete"),
    app_commands.Choice(name="📋 查看已建排行榜清單", value="list")
])
@app_commands.describe(
    操作="選擇要執行的管理動作",
    榜單名稱="排行榜名稱 (例如: 頂流綜合榜、仙途戰力榜、全城首富榜)",
    算分公式="支援 + - * / (例如: 流量熱度 * 0.5 + 商業價值 * 0.3 + 容貌 * 10 或 cash + bank)",
    榜單說明="榜單簡短描述介紹"
)
async def manage_leaderboard_cmd(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    榜單名稱: str = None,
    算分公式: str = None,
    榜單說明: str = "官方官方認證榮譽榜"
):
    g_id = interaction.guild_id
    op = 操作.value

    async with aiosqlite.connect(DB_PATH) as db:
        if op == "delete":
            if not 榜單名稱:
                await interaction.response.send_message("❌ 請填寫欲刪除的【榜單名稱】！", ephemeral=True)
                return
            await db.execute("DELETE FROM custom_leaderboards WHERE guild_id = ? AND board_name = ?", (g_id, 榜單名稱.strip()))
            await db.commit()
            await interaction.response.send_message(f"🗑️ 已成功刪除排行榜【**{榜單名稱.strip()}**】！", ephemeral=True)
            return

        elif op == "list":
            async with db.execute("SELECT board_name, formula, description FROM custom_leaderboards WHERE guild_id = ?", (g_id,)) as cur:
                boards = await cur.fetchall()

            if not boards:
                await interaction.response.send_message("ℹ️ 目前尚未建立任何自訂排行榜。", ephemeral=True)
                return

            embed = discord.Embed(title="📊 全服已啟用之自訂排行榜名冊", color=0x3498DB)
            for b_name, b_form, b_desc in boards:
                embed.add_field(
                    name=f"🏆【{b_name}】",
                    value=f"• 描述: `{b_desc}`\n• 算式: `{b_form}`",
                    inline=False
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        elif op == "set":
            if not 榜單名稱 or not 算分公式:
                await interaction.response.send_message("❌ 新增排行榜時，【榜單名稱】與【算分公式】皆為必填！", ephemeral=True)
                return

            b_name = 榜單名稱.strip()
            b_formula = 算分公式.strip()

            await db.execute("""
                INSERT INTO custom_leaderboards (guild_id, board_name, formula, description)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, board_name) DO UPDATE SET
                    formula = excluded.formula,
                    description = excluded.description
            """, (g_id, b_name, b_formula, 榜單說明.strip()))
            await db.commit()

            embed = discord.Embed(title="🏆 全新排行榜設定成功", color=0x2ECC71)
            embed.description = (
                f"**榜單名稱**：【**{b_name}**】\n"
                f"**介紹說明**：`{榜單說明.strip()}`\n\n"
                f"🧮 **計分公式**：\n```python\n得分 = {b_formula}```\n"
                f"玩家現在可以使用 `/排行榜` 查看即時全服排位！"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


# -------------------- 指令：/排行榜（玩家查看自訂榜單） --------------------
@bot.tree.command(name="排行榜", description="查閱全服各類權威榮譽排行榜（頂流、財富、戰力等）")
@app_commands.describe(指定榜單="【選填】直接輸入榜單名稱，留空則開啟選單挑選")
async def show_leaderboard_cmd(interaction: discord.Interaction, 指定榜單: str = None):
    g_id = interaction.guild_id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT board_name, formula, description FROM custom_leaderboards WHERE guild_id = ?", (g_id,)) as cur:
            boards = await cur.fetchall()

    if not boards:
        await interaction.response.send_message("🏛️ 目前管理員尚未建立任何自訂排行榜，敬請期待！", ephemeral=True)
        return

    async def generate_board_embed(board_name: str, formula: str, desc: str) -> discord.Embed:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT name, cash, bank, stats, rank, affiliation_name
                FROM characters WHERE guild_id = ? AND is_npc IN (0, 1)
            """, (g_id,)) as cur:
                chars = await cur.fetchall()

        ranking_list = []
        for name, cash, bank, s_json, rank_name, aff_name in chars:
            stats = json.loads(s_json) if s_json else {}
            # 合併所有可用於公式的數值環境
            context = dict(stats)
            context["cash"] = cash
            context["bank"] = bank
            context["total_money"] = cash + bank

            score = safe_eval_formula(formula, context)
            ranking_list.append((name, score, rank_name or "未定級", aff_name or "個人"))

        # 由高至低排序
        ranking_list.sort(key=lambda x: x[1], reverse=True)

        embed = discord.Embed(title=f"🏆【全服權威榜】— {board_name}", color=0xF1C40F)
        embed.description = f"*{desc}*\n📐 計分依據：`{formula}`\n"

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        if not ranking_list:
            embed.description += "\n暫無符合資格的角色記錄。"
        else:
            for idx, (c_name, score, r_name, aff) in enumerate(ranking_list[:10]):
                m_icon = medals[idx] if idx < len(medals) else f"`#{idx+1}`"
                embed.add_field(
                    name=f"{m_icon} **{c_name}** ｜ 得分: `{score:,}` 分",
                    value=f"• 當前地位: 【{r_name}】 ｜ 歸屬: {aff}",
                    inline=False
                )
        embed.set_footer(text="數據依據各角色即時屬性動態計算生成")
        return embed

    # 若玩家有指定榜單名稱
    if 指定榜單:
        match = next((b for b in boards if b[0] == 指定榜單.strip()), None)
        if not match:
            await interaction.response.send_message(f"❌ 查無排行榜【{指定榜單}】！", ephemeral=True)
            return
        embed = await generate_board_embed(match[0], match[1], match[2])
        await interaction.response.send_message(embed=embed)
        return

    # 若留空，提供下拉選單切換
    class BoardSelect(discord.ui.Select):
        def __init__(self):
            opts = [discord.SelectOption(label=b[0], value=b[0], description=b[2][:40]) for b in boards[:25]]
            super().__init__(placeholder="請選擇欲調閱的榮譽排行榜...", options=opts)

        async def callback(self, s_inter: discord.Interaction):
            chosen = self.values[0]
            m = next(b for b in boards if b[0] == chosen)
            e = await generate_board_embed(m[0], m[1], m[2])
            await s_inter.response.edit_message(embed=e, view=self.view)

    view = discord.ui.View(timeout=120)
    view.add_item(BoardSelect())
    first_embed = await generate_board_embed(boards[0][0], boards[0][1], boards[0][2])
    await interaction.response.send_message(embed=first_embed, view=view)


# -------------------- 指令：/陣營排行榜（全服陣營與內部排行） --------------------
@bot.tree.command(name="陣營排行榜", description="查閱全服勢力陣營總威望榜（10元=1點）或指定陣營內部成員排行")
@app_commands.choices(類型=[
    app_commands.Choice(name="🚩 全服陣營總威望排名 (10元=1點)", value="all_factions"),
    app_commands.Choice(name="👥 指定陣營內部成員貢獻排行", value="faction_members")
])
@app_commands.describe(
    類型="選擇全服陣營總榜或特定陣營內部成員榜",
    陣營名稱="［陣營內部成員］請輸入欲查詢的陣營名稱"
)
async def faction_leaderboard_cmd(
    interaction: discord.Interaction,
    類型: app_commands.Choice[str],
    陣營名稱: str = None
):
    g_id = interaction.guild_id
    mode = 類型.value

    # 1. 全服陣營總榜（10元 = 1點威望）
    if mode == "all_factions":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT f.name, f.treasury, f.desc, COUNT(m.char_name) as member_count
                FROM factions f
                LEFT JOIN faction_members m ON f.guild_id = m.guild_id AND f.name = m.faction_name
                WHERE f.guild_id = ?
                GROUP BY f.name
            """, (g_id,)) as cur:
                factions_data = await cur.fetchall()

        if not factions_data:
            await interaction.response.send_message("ℹ️ 當前伺服器尚無任何勢力陣營成立。", ephemeral=True)
            return

        # 換算規則：每 10 元 = 1 點總威望點數
        f_ranked = []
        for f_name, treasury, desc, m_count in factions_data:
            prestige_points = treasury // 10
            f_ranked.append((f_name, treasury, prestige_points, desc, m_count))

        f_ranked.sort(key=lambda x: x[2], reverse=True)

        embed = discord.Embed(title="🚩【全服勢力陣營總威望榜】", color=0xE74C3C)
        embed.description = "規則說明：陣營金庫每累積 **$10 元公款**，即換算為 **1 點總威望**！\n"

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for idx, (fn, treas, pts, desc, mc) in enumerate(f_ranked[:10]):
            m_icon = medals[idx] if idx < len(medals) else f"`#{idx+1}`"
            embed.add_field(
                name=f"{m_icon} **【{fn}】** ｜ 總威望：`{pts:,}` 點",
                value=f"• 💰 金庫公款儲備：**${treas:,}**\n• 👥 在籍成員：`{mc}` 位 ｜ 綱領: `{desc}`",
                inline=False
            )
        embed.set_footer(text="可使用 /陣營 進行公款捐獻為陣營增添威望")
        await interaction.response.send_message(embed=embed)
        return

    # 2. 指定陣營內部成員排行
    elif mode == "faction_members":
        if not 陣營名稱:
            await interaction.response.send_message("❌ 請填寫欲查詢內部排行的【陣營名稱】！", ephemeral=True)
            return

        target_faction = 陣營名稱.strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT treasury, desc FROM factions WHERE guild_id = ? AND name = ?", (g_id, target_faction)) as f_cur:
                f_info = await f_cur.fetchone()

            if not f_info:
                await interaction.response.send_message(f"❌ 查無勢力陣營【{target_faction}】！", ephemeral=True)
                return

            treasury, desc = f_info
            async with db.execute("""
                SELECT char_name, contribution
                FROM faction_members
                WHERE guild_id = ? AND faction_name = ?
                ORDER BY contribution DESC
            """, (g_id, target_faction)) as cur:
                members_rank = await cur.fetchall()

        embed = discord.Embed(title=f"👥【{target_faction}】內部核心成員貢獻榜", color=0x9B59B6)
        embed.description = f"*{desc}*\n💰 陣營總金庫公款：**${treasury:,}**（總威望: `{treasury//10:,}` 點）\n"

        if not members_rank:
            embed.description += "\n該陣營目前暫無任何成員貢獻記錄。"
        else:
            medals = ["👑", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            for idx, (c_name, contrib) in enumerate(members_rank[:15]):
                icon = medals[idx] if idx < len(medals) else f"`#{idx+1}`"
                contrib_pts = contrib // 10
                embed.add_field(
                    name=f"{icon} **{c_name}**",
                    value=f"• 累計捐款：**${contrib:,}** (貢獻威望 `{contrib_pts:,}` 點)",
                    inline=True
                )
        embed.set_footer(text="內部貢獻直接反映成員在陣營中的話語權")
        await interaction.response.send_message(embed=embed)
# -------------------- 指令：/人物與NPC總管 --------------------
@bot.tree.command(name="人物與NPC總管", description="【管理員專用】登記官方NPC、批量生成大眾路人、路人轉正與生態浮動設定")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="🌟 登記/更新官方重要人物 (NPC)", value="create_official"),
    app_commands.Choice(name="👥 批量生成大眾路人 NPC", value="gen_crowd"),
    app_commands.Choice(name="🎖️ 將大眾路人轉正為官方 NPC", value="promote_crowd"),
    app_commands.Choice(name="⚙️ 設定路人48小時生態浮動參數", value="cfg_fluct")
])
@app_commands.choices(性別=[
    app_commands.Choice(name="男", value="男"),
    app_commands.Choice(name="女", value="女")
])
@app_commands.describe(
    操作="選擇要執行的 NPC 管理項目",
    姓名="NPC 角色姓名",
    藝名稱號="對外藝名、道號或稱謂 (選填)",
    性別="性別 (男/女)",
    年齡="純數字 (例如: 25)",
    職業="身分或職業賽道 (例如: 影帝、王牌經紀人、金牌製作人)",
    國籍="角色國籍或出身地 (預設: 本國)",
    身高="純數字 (單位: cm，例如: 182)",
    體重="純數字 (單位: kg，例如: 70)",
    代表色碼="16進位色碼 (例如: #9B59B6)",
    立繪連結="立繪圖片網址",
    生成數量="［批量生成路人］欲隨機生成的人數 (1~20)",
    浮動百分比="［生態浮動］每次浮動最大幅度 (例如 5 代表 ±5%)",
    金錢是否浮動="［生態浮動］True 代表路人資產同步微幅變動",
    浮動上限封頂="［生態浮動］數值浮動最高上限 (預設: 3000)"
)
async def npc_admin_cmd(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    姓名: str = None,
    藝名稱號: str = None,
    性別: app_commands.Choice[str] = None,
    年齡: int = 24,
    職業: str = "藝人",
    國籍: str = "本國",
    身高: int = 175,
    體重: int = 60,
    代表色碼: str = "#9B59B6",
    立繪連結: str = "",
    生成數量: int = 5,
    浮動百分比: float = 5.0,
    金錢是否浮動: bool = True,
    浮動上限封頂: int = 3000
):
    g_id = interaction.guild_id
    op = 操作.value

    # 1. 登記 / 更新官方核心 NPC
    if op == "create_official":
        if not 姓名:
            await interaction.response.send_message("❌ 請填寫欲登記的官方 NPC【姓名】！", ephemeral=True)
            return

        c_name = 姓名.strip()
        s_name = 藝名稱號.strip() if 藝名稱號 else c_name
        gen_str = 性別.value if 性別 else "女"
        color_str = 代表色碼.strip() if 代表色碼 else "#9B59B6"

        f_hp, f_face, bmi_val, _ = check_bmi_impact(身高, 體重, 100, 75)
        init_stats = {
            "流量熱度": 500, "商業價值": 500, "影響指數": 400, "路人緣": 80,
            "公關": 80, "容貌": f_face, "才智": 80, "個人才藝": 80,
            "唱跳": 70, "演繹": 70, "主持": 70, "歌唱": 70, "綜藝": 70,
            "死忠粉絲數": 5000, "活躍黑粉數": 100, "大眾認知度": 600
        }

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO characters (
                    guild_id, user_id, name, stage_name, age, gender, job, faction,
                    tags, relationship_status, created_at, is_npc, image_url, height, weight,
                    nationality, theme_color, char_health, primary_track, cash, bank, stats
                ) VALUES (?, 0, ?, ?, ?, ?, ?, '官方勢力', '', '單身', ?, 1, ?, ?, ?, ?, ?, ?, '常規', 50000, 500000, ?)
                ON CONFLICT(guild_id, name) DO UPDATE SET
                    stage_name = excluded.stage_name, age = excluded.age, gender = excluded.gender,
                    job = excluded.job, height = excluded.height, weight = excluded.weight,
                    nationality = excluded.nationality, theme_color = excluded.theme_color,
                    image_url = excluded.image_url, is_npc = 1
            """, (
                g_id, c_name, s_name, 年齡, gen_str, 職業.strip(),
                time.time(), 立繪連結.strip(), 身高, 體重,
                國籍.strip(), color_str, f_hp, json.dumps(init_stats, ensure_ascii=False)
            ))
            await db.commit()

        embed = discord.Embed(title=f"🌟 官方重要人物【{c_name}】建檔完畢", color=parse_hex_color(color_str))
        embed.description = (
            f"• 稱號/藝名: **{s_name}**\n"
            f"• 身分/賽道: {職業.strip()} ({國籍.strip()} / {gen_str} / {年齡}歲)\n"
            f"• 體態數據: `{身高} cm` / `{體重} kg` (BMI: `{bmi_val}`)\n"
            f"• 初始健康度: ❤️ **{f_hp} / 100**\n\n"
            f"已正式指派為官方 NPC（`is_npc = 1`），可直接使用 `/劇本設定` 開放攻略劇情！"
        )
        if 立繪連結.strip().startswith("http"):
            embed.set_thumbnail(url=立繪連結.strip())

        await interaction.response.send_message(embed=embed)
        return

    # 2. 批量生成大眾路人 NPC
    elif op == "gen_crowd":
        count = max(1, min(20, 生成數量))
        all_nations = WESTERN_NATIONS + EASTERN_NATIONS + SOUTH_AMERICAN_NATIONS + AFRICAN_NATIONS

        surnames = ["林", "陳", "李", "張", "王", "趙", "沈", "顧", "陸", "蘇", "葉", "白", "謝", "宋", "韓"]
        male_names = ["澤", "宇", "辰", "軒", "揚", "皓", "霖", "風", "澈", "然", "朗", "鳴"]
        female_names = ["瑤", "涵", "薇", "萱", "語", "晴", "凝", "曼", "玥", "茜", "詩", "柔"]

        generated_names = []
        async with aiosqlite.connect(DB_PATH) as db:
            for _ in range(count):
                c_gen = random.choice(["男", "女"])
                c_age = random.randint(18, 38)
                c_surname = random.choice(surnames)
                c_given = random.choice(male_names if c_gen == "男" else female_names)
                if random.random() < 0.5:
                    c_given += random.choice(male_names if c_gen == "男" else female_names)
                full_name = f"{c_surname}{c_given}"

                c_nat = random.choice(all_nations)
                c_job = random.choice(CROWD_JOBS)
                c_rel = random.choice(CROWD_RELATIONS)
                c_h = random.randint(160, 188) if c_gen == "男" else random.randint(155, 175)
                c_w = int(21.5 * ((c_h / 100.0) ** 2))

                avail_tags = get_available_tags_for(c_age, c_gen)
                c_tags = "、".join(random.sample(avail_tags, min(2, len(avail_tags))))

                init_stats = {
                    "流量熱度": random.randint(30, 200),
                    "商業價值": random.randint(30, 200),
                    "影響指數": random.randint(20, 150),
                    "路人緣": random.randint(40, 75),
                    "公關": random.randint(30, 60),
                    "容貌": random.randint(45, 80),
                    "才智": random.randint(40, 75),
                    "個人才藝": random.randint(30, 70),
                    "唱跳": random.randint(20, 60),
                    "演繹": random.randint(20, 60),
                    "主持": random.randint(20, 60),
                    "歌唱": random.randint(20, 60),
                    "綜藝": random.randint(20, 60),
                    "死忠粉絲數": random.randint(50, 800),
                    "活躍黑粉數": random.randint(0, 50),
                    "大眾認知度": random.randint(50, 300)
                }

                await db.execute("""
                    INSERT INTO characters (
                        guild_id, user_id, name, stage_name, age, gender, job, faction,
                        tags, relationship_status, created_at, is_npc, height, weight,
                        nationality, theme_color, char_health, cash, bank, stats
                    ) VALUES (?, 0, ?, ?, ?, ?, ?, '無', ?, ?, ?, 3, ?, ?, ?, '#E67E22', 100, ?, ?, ?)
                    ON CONFLICT(guild_id, name) DO NOTHING
                """, (
                    g_id, full_name, full_name, c_age, c_gen, c_job,
                    c_tags, c_rel, time.time(), c_h, c_w, c_nat,
                    random.randint(2000, 15000), random.randint(10000, 80000),
                    json.dumps(init_stats, ensure_ascii=False)
                ))
                generated_names.append(f"**{full_name}** ({c_gen}/{c_age}歲/{c_job}/{c_nat})")

            await db.commit()

        embed = discord.Embed(title=f"👥 成功批量生成 {len(generated_names)} 位大眾路人 NPC", color=0xE67E22)
        embed.description = "\n".join(generated_names)
        embed.set_footer(text="路人角色將受 48 小時生態系統自動進行小幅行情浮動")
        await interaction.response.send_message(embed=embed)
        return

    # 3. 大眾路人轉正官方 NPC
    elif op == "promote_crowd":
        if not 姓名:
            await interaction.response.send_message("❌ 請填寫欲轉正的路人【姓名】！", ephemeral=True)
            return

        c_name = 姓名.strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT is_npc, theme_color FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
                row = await cur.fetchone()

            if not row:
                await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
                return
            if row[0] != 3:
                await interaction.response.send_message(f"ℹ️ 角色【{c_name}】目前身分並非大眾路人（代碼: {row[0]}），無需轉正。", ephemeral=True)
                return

            await db.execute("""
                UPDATE characters 
                SET is_npc = 1, faction = '官方勢力', theme_color = '#9B59B6'
                WHERE guild_id = ? AND name = ?
            """, (g_id, c_name))
            await db.commit()

        embed = discord.Embed(title="🌟【大眾路人・正式晉升官方人物】", color=0x9B59B6)
        embed.description = (
            f"大眾動態路人 **{c_name}** 表現優異，已正式晉升確立為 **官方 NPC**！\n\n"
            f"• 標籤身分已轉為：`［官方 NPC］`\n"
            f"• 勢力歸屬調整為：`官方勢力`\n"
            f"管理員現已可使用 `/劇本設定` 為其編寫專屬攻略互動劇情！"
        )
        await broadcast_event(interaction.guild, "crowd_promote", embed)
        await interaction.response.send_message(embed=embed)
        return

    # 4. 設定 48 小時生態浮動參數
    elif op == "cfg_fluct":
        rate_val = round(max(0.01, min(0.30, 浮動百分比 / 100.0)), 3)
        money_flag = "1" if 金錢是否浮動 else "0"

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'npc_fluct_rate', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, str(rate_val), str(rate_val)))
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'npc_fluct_money', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, money_flag, money_flag))
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'npc_fluct_cap', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, str(浮動上限封頂), str(浮動上限封頂)))
            await db.commit()

        embed = discord.Embed(title="⚙️ 大眾路人生態浮動機制設定更新", color=0x2ECC71)
        embed.description = (
            f"• 每 48 小時數值浮動幅度：`±{浮動百分比}%`\n"
            f"• 金錢資產是否同步浮動：`{'是' if 金錢是否浮動 else '否'}`\n"
            f"• 數值浮動上限封頂：`{浮動上限封頂:,}` 點"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
# -------------------- 購買數量 Modal 彈跳視窗 --------------------
class PurchaseQuantityModal(discord.ui.Modal):
    def __init__(self, guild_id: int, char_name: str, item_id: int, item_name: str, price: int, stock: int, seller: str):
        super().__init__(title=f"購買【{item_name[:15]}】")
        self.guild_id = guild_id
        self.char_name = char_name
        self.item_id = item_id
        self.item_name = item_name
        self.price = price
        self.stock = stock
        self.seller = seller

        stock_hint = "無限制" if stock == -1 else f"剩餘 {stock} 件"
        self.qty_input = discord.ui.TextInput(
            label=f"請輸入購買數量（單價 ${price:,} ｜ 庫存: {stock_hint}）",
            placeholder="請輸入欲購買的數量（純正整數，例如: 1、5、20）",
            default="1",
            min_length=1,
            max_length=6
        )
        self.add_item(self.qty_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.qty_input.value.strip())
            if qty <= 0: raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ 請輸入大於 0 的有效購買數量！", ephemeral=True)
            return

        total_cost = self.price * qty

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT stock, seller FROM shop_items WHERE id = ?", (self.item_id,)) as cur:
                curr_item = await cur.fetchone()

            if not curr_item:
                await interaction.response.send_message("❌ 抱歉，該商品已下架或售罄！", ephemeral=True)
                return

            curr_stock, seller_name = curr_item
            if curr_stock != -1 and curr_stock < qty:
                await interaction.response.send_message(f"❌ 庫存不足！該商品目前僅剩 **{curr_stock}** 件可供購買。", ephemeral=True)
                return

            async with db.execute("SELECT cash, bank FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                cash, bank = await cur.fetchone()

            if cash + bank < total_cost:
                await interaction.response.send_message(
                    f"❌ 總資金不足！購買 **{qty}** 件【{self.item_name}】共需 **${total_cost:,}**。\n"
                    f"目前手頭現金 **${cash:,}**，銀行存款 **${bank:,}**！",
                    ephemeral=True
                )
                return

            # 優先扣除現金，不足扣銀行
            if cash >= total_cost:
                await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (total_cost, self.guild_id, self.char_name))
            else:
                rem = total_cost - cash
                await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (rem, self.guild_id, self.char_name))

            # 扣減庫存
            if curr_stock != -1:
                new_stock = curr_stock - qty
                if new_stock <= 0 and seller_name != "官方":
                    await db.execute("DELETE FROM shop_items WHERE id = ?", (self.item_id,))
                else:
                    await db.execute("UPDATE shop_items SET stock = ? WHERE id = ?", (new_stock, self.item_id))

            # 款項注入賣家或所屬公司
            if seller_name != "官方":
                async with db.execute("SELECT id FROM companies WHERE guild_id = ? AND name = ?", (self.guild_id, seller_name)) as comp_cur:
                    comp_match = await comp_cur.fetchone()
                if comp_match:
                    await db.execute("UPDATE companies SET balance = balance + ? WHERE id = ?", (total_cost, comp_match[0]))
                else:
                    await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (total_cost, self.guild_id, seller_name))

            # 若是行動點直接充值，其他道具放入個人背包
            if any(k in self.item_name for k in ["行動點", "AP", "精力", "行動值"]):
                points_to_add = qty
                await db.execute("UPDATE characters SET action_points = action_points + ? WHERE guild_id = ? AND name = ?", (points_to_add, self.guild_id, self.char_name))
                receive_msg = f"⚡ 已成功為 **{self.char_name}** 充值 **+{points_to_add}** 點行動點（AP）！"
            else:
                async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (self.guild_id, self.char_name, self.item_name)) as inv_cur:
                    inv_entry = await inv_cur.fetchone()
                    if inv_entry:
                        await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (qty, inv_entry[0]))
                    else:
                        await db.execute("""
                            INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver)
                            VALUES (?, ?, ?, ?, ?)
                        """, (self.guild_id, self.char_name, self.item_name, qty, f"購入自({seller_name})"))
                receive_msg = f"📦 已將【**{self.item_name}**】×{qty} 放入個人背包！"

            await db.commit()

        await interaction.response.send_message(
            f"🛍️ 購買成功！**{self.char_name}** 消費 **${total_cost:,}** 購入【**{self.item_name}**】×{qty}！\n{receive_msg}"
        )


# -------------------- 指令：/商城（含行動點快捷視窗） --------------------
@bot.tree.command(name="商城", description="進入商城選單購買官方好物、直接購買行動點、公司商品或二手珍品")
@app_commands.describe(角色名="欲進入商城選購的角色名稱")
async def shop(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, action_points, cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()
            if not c_row:
                await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
                return

        async with db.execute("SELECT DISTINCT shop_name FROM shop_items WHERE guild_id = ? AND shop_name != '官方商城'", (g_id,)) as cur:
            other_shops = [row[0] for row in await cur.fetchall()]

    all_shops = ["官方商城"]
    for s in other_shops:
        if s not in all_shops:
            all_shops.append(s)
    for def_s in ["必備用品", "票務系統", "二手"]:
        if def_s not in all_shops:
            all_shops.append(def_s)

    class BuyItemSelect(discord.ui.Select):
        def __init__(self, shop_name: str, items: list):
            self.shop_name = shop_name
            self.items_map = {str(it[0]): it for it in items}
            opts = []
            for it in items[:25]:
                stock_str = "無限" if it[5] == -1 else f"餘{it[5]}"
                opts.append(discord.SelectOption(
                    label=f"{it[1]} (${it[2]:,})",
                    value=str(it[0]),
                    description=f"庫存:{stock_str} ｜ {it[3][:30]}"
                ))
            super().__init__(placeholder=f"請挑選【{shop_name}】欲購買的商品...", options=opts)

        async def callback(self, s_inter: discord.Interaction):
            item_id = int(self.values[0])
            it = self.items_map[str(item_id)]
            await s_inter.response.send_modal(PurchaseQuantityModal(
                guild_id=g_id,
                char_name=c_name,
                item_id=it[0],
                item_name=it[1],
                price=it[2],
                stock=it[5],
                seller=it[4]
            ))

    class ShopSelectView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            for shop_title in all_shops[:20]:
                btn = discord.ui.Button(
                    label=shop_title[:20],
                    style=discord.ButtonStyle.success if shop_title == "官方商城" else discord.ButtonStyle.primary
                )
                btn.callback = self.make_cb(shop_title)
                self.add_item(btn)

        def make_cb(self, s_name: str):
            async def cb(inter: discord.Interaction):
                # 官方商城：直達行動點快捷購買彈窗按鈕
                if s_name == "官方商城":
                    class OfficialAPModal(discord.ui.Modal, title="⚡ 購買行動點（AP）"):
                        ap_qty = discord.ui.TextInput(
                            label="欲購買的行動點數量（1點 $500，無上限）",
                            placeholder="請填入欲購買的數量（例如: 5、10、50）",
                            default="5",
                            min_length=1,
                            max_length=6
                        )

                        async def on_submit(m_self, m_inter: discord.Interaction):
                            try:
                                count = int(m_self.ap_qty.value.strip())
                                if count <= 0: raise ValueError
                            except ValueError:
                                await m_inter.response.send_message("❌ 請填寫有效的行動點數量！", ephemeral=True)
                                return

                            cost = count * 500
                            async with aiosqlite.connect(DB_PATH) as db:
                                async with db.execute("SELECT cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
                                    cash, bank = await cur.fetchone()

                                if cash + bank < cost:
                                    await m_inter.response.send_message(f"❌ 資金不足！購買 **{count}** AP 需 **${cost:,}**！", ephemeral=True)
                                    return

                                if cash >= cost:
                                    await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (cost, g_id, c_name))
                                else:
                                    rem = cost - cash
                                    await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (rem, g_id, c_name))

                                await db.execute("UPDATE characters SET action_points = action_points + ? WHERE guild_id = ? AND name = ?", (count, g_id, c_name))
                                await db.commit()

                            await m_inter.response.send_message(f"⚡ 成功購入 **{count}** 點行動點！已扣款 **${cost:,}**，精力已立即到帳！")

                    class OfficialView(discord.ui.View):
                        @discord.ui.button(label="⚡ 快捷購買行動點 (1點 $500，點擊輸入數量)", style=discord.ButtonStyle.success)
                        async def buy_ap_btn(self, sub_inter: discord.Interaction, button: discord.ui.Button):
                            await sub_inter.response.send_modal(OfficialAPModal())

                    embed = discord.Embed(
                        title="🏬 官方直營中心 — 行動點專區",
                        description=(
                            f"買家：**{c_name}**\n\n"
                            f"⚡ **【行動點機制】**\n"
                            f"• 單價：**$500 / 點**（無購買上限）\n"
                            f"• 用途：用於 `/行動` 進行排練（1~15數值）、私教培訓、打工兼職或應酬\n"
                            f"• 每年清算：現實每月（遊戲每年）重置一次，不跨年保留\n\n"
                            f"👇 請點擊下方綠色按鈕填入欲購買數量："
                        ),
                        color=0x2ECC71
                    )
                    await inter.response.send_message(embed=embed, view=OfficialView(), ephemeral=True)
                    return

                # 其他常規專區
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("""
                        SELECT id, name, price, description, seller, COALESCE(stock, -1)
                        FROM shop_items WHERE guild_id = ? AND shop_name = ?
                    """, (g_id, s_name)) as cur:
                        items = await cur.fetchall()

                if not items:
                    await inter.response.send_message(f"🏪 專區【{s_name}】目前暫無上架商品。", ephemeral=True)
                    return

                sub_view = discord.ui.View()
                sub_view.add_item(BuyItemSelect(s_name, items))
                embed = discord.Embed(title=f"🏪 商城專區 — 【{s_name}】", description="請點選下方選單挑選商品，點選後即可輸入購買數量：", color=0xF39C12)
                for it in items[:10]:
                    stock_str = "無限" if it[5] == -1 else f"限量 {it[5]} 件"
                    embed.add_field(name=f"📦 {it[1]} — ${it[2]:,} ({stock_str})", value=f"簡介: {it[3]}", inline=False)

                await inter.response.send_message(embed=embed, view=sub_view, ephemeral=True)
            return cb

    embed = discord.Embed(
        title="🏪 全城商城中心",
        description="• **官方商城**：直達行動點快捷購買按鈕\n• **其餘專區**：點擊專區選單挑選商品，彈跳視窗輸入數量",
        color=0x34495E
    )
    await interaction.response.send_message(embed=embed, view=ShopSelectView(), ephemeral=True)


# -------------------- 指令：/售物（二手寄售、創作作品享才智溢價） --------------------
@bot.tree.command(name="售物", description="將背包物品或個人創作作品上架至【二手】商城販售（創作作品受才智溢價認定）")
@app_commands.choices(物品類型=[
    app_commands.Choice(name="一般二手物品 / 禮品", value="general"),
    app_commands.Choice(name="個人創作作品 (劇本/單曲/陣圖/版權)", value="creation")
])
@app_commands.describe(
    賣家角色名="持有該物品並進行販售的角色姓名",
    物品名稱="背包中欲出售的物品名稱",
    定價="販售單價 (純整數)",
    物品類型="選擇一般物品或原創作品",
    物品介紹="自訂商品描述說明"
)
async def sell_item_cmd(
    interaction: discord.Interaction,
    賣家角色名: str,
    物品名稱: str,
    定價: int,
    物品類型: app_commands.Choice[str],
    物品介紹: str = "賣家自用寄售 / 原創創作"
):
    g_id = interaction.guild_id
    seller_name = 賣家角色名.strip()
    item_name = 物品名稱.strip()

    if 定價 <= 0:
        await interaction.response.send_message("❌ 販售定價必須大於 0！", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, user_id, stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, seller_name)) as cur:
            char_row = await cur.fetchone()

        if not char_row:
            await interaction.response.send_message(f"❌ 查無角色【{seller_name}】！", ephemeral=True)
            return

        c_db_id, u_id, stats_json = char_row
        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 你無權操作此角色的背包物品！", ephemeral=True)
            return

        async with db.execute("SELECT id, amount FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, seller_name, item_name)) as inv_cur:
            inv_row = await inv_cur.fetchone()

        if not inv_row or inv_row[1] <= 0:
            await interaction.response.send_message(f"❌ 【{seller_name}】背包內沒有【{item_name}】！", ephemeral=True)
            return

        inv_id, current_amount = inv_row
        char_stats = json.loads(stats_json) if stats_json else {}

        # 原創作品享受才智談判溢價認證
        talent_bonus_note = ""
        if 物品類型.value == "creation":
            intellect = char_stats.get("才智", 50)
            max_allowed_price = int(50000 * (1.0 + (intellect / 100.0)))
            if 定價 > max_allowed_price:
                await interaction.response.send_message(
                    f"⚠️ **【談判與創作溢價不足】**\n**{seller_name}** 當前才智為 `{intellect}`，該作品最高認可售價上限為 **${max_allowed_price:,}**！",
                    ephemeral=True
                )
                return
            talent_bonus_note = f"\n🧠 **才智溢價認證**：才智 `{intellect}`，定價合規（上限 ${max_allowed_price:,}）！"

        # 從個人背包扣除 1 件
        if current_amount > 1:
            await db.execute("UPDATE inventory SET amount = amount - 1 WHERE id = ?", (inv_id,))
        else:
            await db.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))

        # 上架至二手商城
        await db.execute("""
            INSERT INTO shop_items (guild_id, shop_name, name, price, description, stat_bonus, usable, seller)
            VALUES (?, '二手', ?, ?, ?, '', 1, ?)
        """, (g_id, item_name, 定價, 物品介紹.strip(), seller_name))
        await db.commit()

    embed = discord.Embed(
        title="🏷️ 物品/作品已成功上架至【二手商城】！",
        description=(
            f"• 寄售賣家：**{seller_name}**\n"
            f"• 物品名稱：**{item_name}**\n"
            f"• 二手售價：**${定價:,}**\n"
            f"• 商品備註：`{物品介紹.strip()}`{talent_bonus_note}"
        ),
        color=0xE67E22
    )
    await interaction.response.send_message(embed=embed)
# -------------------- 指令：/世界觀自訂 --------------------
@bot.tree.command(name="世界觀自訂", description="【管理員專用】自訂面板所有用詞、組織名冊與各組屬性清單（多個詞以空格隔開即可）")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    面板第一頁標題="預設: 個人基本檔案 (例如: 仙途履歷)",
    能力第二頁標題="預設: 演藝能力面板 (例如: 道行境界面板)",
    賽道系統名稱="賽道欄位名稱 (例如: 主攻賽道、本命靈根、核心傳承)",
    賽道可選清單="多個以空格隔開，不限數量 (例如: 劍修 體修 丹道 陣法 符道 禦獸)",
    組織系統名稱="組織欄位名稱 (例如: 歸屬組織、宗門家族、效忠陣營)",
    組織可選清單="多個以空格隔開，不限數量 (例如: 青雲宗 萬劍山莊 縹緲閣 玄陰殿 天策府)",
    第一能力組名稱="第一組屬性標題 (例如: 江湖聲望、商業名氣、朝堂威權)",
    第一組能力清單="多個以空格隔開，不限數量 (例如: 聲望 威壓 功名 香火 人脈 貢獻)",
    第二能力組名稱="第二組屬性標題 (例如: 仙道修為、藝能實力、基礎根骨)",
    第二組能力清單="多個以空格隔開，不限數量 (例如: 根骨 悟性 靈力 神識 氣血 壽元)",
    資歷稱謂="資歷欄位名稱 (例如: 修行年歲、入道時長、出道歷練)",
    自訂資歷階級="【選填】JSON 格式階梯稱號，留空維持預設"
)
async def custom_world_terms_cmd(
    interaction: discord.Interaction,
    面板第一頁標題: str = None,
    能力第二頁標題: str = None,
    賽道系統名稱: str = None,
    賽道可選清單: str = None,
    組織系統名稱: str = None,
    組織可選清單: str = None,
    第一能力組名稱: str = None,
    第一組能力清單: str = None,
    第二能力組名稱: str = None,
    第二組能力清單: str = None,
    資歷稱謂: str = None,
    自訂資歷階級: str = None
):
    g_id = interaction.guild_id
    current_terms = await get_world_terms(g_id)

    if 面板第一頁標題: current_terms["page1_title"] = 面板第一頁標題.strip()
    if 能力第二頁標題: current_terms["page2_title"] = 能力第二頁標題.strip()
    if 賽道系統名稱: current_terms["term_track"] = 賽道系統名稱.strip()
    if 組織系統名稱: current_terms["term_org"] = 組織系統名稱.strip()
    if 資歷稱謂: 
        current_terms["term_debut"] = 資歷稱謂.strip()
        current_terms["term_debut_years"] = 資歷稱謂.strip()
    if 第一能力組名稱: current_terms["section_stat_group1"] = 第一能力組名稱.strip()
    if 第二能力組名稱: current_terms["section_stat_group2"] = 第二能力組名稱.strip()

    def split_items(raw_str: str) -> list:
        if not raw_str: return []
        return [item.strip() for item in re.split(r"[,，、\s]+", raw_str.strip()) if item.strip()]

    track_list = split_items(賽道可選清單)
    if track_list: current_terms["track_list"] = track_list

    org_list = split_items(組織可選清單)
    if org_list: current_terms["org_list"] = org_list

    group1_stats = split_items(第一組能力清單)
    if group1_stats: current_terms["stat_group1_keys"] = group1_stats

    group2_stats = split_items(第二組能力清單)
    if group2_stats: current_terms["stat_group2_keys"] = group2_stats

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'custom_ui_terms', ?)
            ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
        """, (g_id, json.dumps(current_terms, ensure_ascii=False), json.dumps(current_terms, ensure_ascii=False)))

        if org_list:
            for org in org_list:
                await db.execute("""
                    INSERT INTO factions (guild_id, name, desc) VALUES (?, ?, '世界觀官方勢力')
                    ON CONFLICT(guild_id, name) DO NOTHING
                """, (g_id, org))

        if 自訂資歷階級:
            try:
                parsed_tiers = json.loads(自訂資歷階級.strip())
                await db.execute("""
                    INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'custom_debut_tiers', ?)
                    ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
                """, (g_id, json.dumps(parsed_tiers, ensure_ascii=False), json.dumps(parsed_tiers, ensure_ascii=False)))
            except Exception as e:
                await interaction.response.send_message(f"⚠️ 詞彙設定已保存，但資歷階級 JSON 格式有誤：`{e}`", ephemeral=True)
                return

        await db.commit()

    embed = discord.Embed(title="🌐 世界觀體系與能力清單自訂已套用", color=0x2ECC71)
    embed.description = (
        f"**📋 基本標題**\n"
        f"• 第一頁：`{current_terms['page1_title']}`\n"
        f"• 第二頁：`{current_terms['page2_title']}`\n"
        f"• 資歷稱號：`{current_terms['term_debut']}`\n\n"
        f"**⚔️ 核心傳承／賽道【{current_terms['term_track']}】**\n"
        f"• 包含項目：`{'、'.join(current_terms.get('track_list', ['唱跳', '演繹', '主持', '歌唱', '綜藝']))}`\n\n"
        f"**🏰 勢力陣營／組織【{current_terms['term_org']}】**\n"
        f"• 包含名冊：`{'、'.join(current_terms.get('org_list', ['官方勢力', '獨立個人']))}`\n\n"
        f"**📈 第一能力組【{current_terms['section_stat_group1']}】**\n"
        f"• 屬性項目：`{'、'.join(current_terms.get('stat_group1_keys', ['流量熱度', '商業價值', '影響指數', '路人緣', '公關']))}`\n\n"
        f"**🎭 第二能力組【{current_terms['section_stat_group2']}】**\n"
        f"• 屬性項目：`{'、'.join(current_terms.get('stat_group2_keys', ['容貌', '才智', '個人才藝']))}`"
    )
    await interaction.response.send_message(embed=embed)


# -------------------- 指令：/違規懲戒（警告扣減、撕卡拍賣與遺產瓜分） --------------------
@bot.tree.command(name="違規懲戒", description="【管理員專用】警告扣減10%/20%數值；第3次封殺撕卡並將遺產全服瓜分與拍賣")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(處置處分=[
    app_commands.Choice(name="正式警告記點 (第1次扣10%、第2次扣20%、第3次封殺撕卡)", value="warn"),
    app_commands.Choice(name="重大違規直接封殺 (直接撕卡並瓜分遺產)", value="kick_ban")
])
@app_commands.describe(
    對象玩家="違規的伺服器成員",
    角色名="違規角色全名 (撕卡與扣數值對象)",
    違反規章條款="違規條款項目 (例如: 規章第三條禁止惡意引戰)",
    規章連結="放規則的頻道/討論串連結",
    處分理由="具體違規事件說明",
    存證連結="對話訊息連結或截圖網址作為實質證據",
    處置處分="選擇警告記點或重大違規直接處刑"
)
async def penalty_cmd(
    interaction: discord.Interaction,
    對象玩家: discord.Member,
    角色名: str,
    違反規章條款: str,
    規章連結: str,
    處分理由: str,
    存證連結: str,
    處置處分: app_commands.Choice[str] = None
):
    g_id = interaction.guild_id
    u_id = 對象玩家.id
    c_name = 角色名.strip()
    clause = 違反規章條款.strip()
    rule_url = 規章連結.strip()
    reason_text = 處分理由.strip()
    evidence_url = 存證連結.strip()
    action = 處置處分.value if 處置處分 else "warn"

    await interaction.response.defer(ephemeral=False)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT cash, bank, stats, theme_color FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()

        if not c_row:
            await interaction.followup.send(f"❌ 查無受懲處角色【{c_name}】！請確認角色全名。", ephemeral=True)
            return

        cash, bank, stats_json, t_color = c_row
        stats = json.loads(stats_json) if stats_json else {}

        await db.execute("""
            INSERT INTO character_warnings (
                guild_id, user_id, char_name, rule_clause, reason, evidence_link, admin_name, warned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (g_id, u_id, c_name, clause, reason_text, evidence_url, interaction.user.display_name, time.time()))

        async with db.execute("SELECT COUNT(*) FROM character_warnings WHERE guild_id = ? AND user_id = ?", (g_id, u_id)) as cur:
            warn_count = (await cur.fetchone())[0]

        punishment_details = []
        is_ban_and_rip = (action == "kick_ban") or (warn_count >= 3)

        if not is_ban_and_rip:
            # 警告處分：第 1 次扣 10%，第 2 次扣 20%
            decay_rate = 0.10 if warn_count == 1 else 0.20
            percent_str = "10%" if warn_count == 1 else "20%"

            deducted_stats_list = []
            for k, v in list(stats.items()):
                if isinstance(v, (int, float)) and v > 0:
                    lost = int(v * decay_rate)
                    if lost > 0:
                        stats[k] = max(0, v - lost)
                        deducted_stats_list.append(f"• {k}: -{lost} (剩餘 {stats[k]})")

            await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(stats, ensure_ascii=False), g_id, c_name))
            await db.commit()

            punishment_details.append(f"⚠️ **【數值懲處】** 累積第 {warn_count} 次違規，各項能力數值扣除 **{percent_str}**：")
            punishment_details.extend(deducted_stats_list[:8])
            if len(deducted_stats_list) > 8:
                punishment_details.append(f"└ 及其他 {len(deducted_stats_list) - 8} 項數值全額衰減。")

        else:
            # 滿 3 次或重大違規：終生封殺、踢出、角色撕卡、瓜分遺產
            async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND is_npc IN (0, 1) AND name != ?", (g_id, c_name)) as ben_cur:
                beneficiaries = [r[0] for r in await ben_cur.fetchall()]

            total_beneficiaries = len(beneficiaries)
            total_legacy_pool_money = cash + bank

            auction_items = []
            liquidated_items_money = 0

            async with db.execute("SELECT item_name, amount FROM inventory WHERE guild_id = ? AND owner_name = ?", (g_id, c_name)) as inv_cur:
                rip_inv = await inv_cur.fetchall()

            for it_name, it_amt in rip_inv:
                async with db.execute("SELECT price FROM shop_items WHERE guild_id = ? AND name = ?", (g_id, it_name)) as p_cur:
                    p_row = await p_cur.fetchone()

                if p_row and p_row[0] > 0:
                    item_val = p_row[0] * it_amt
                    liquidated_items_money += item_val
                else:
                    auc_end_time = time.time() + (48 * 3600)
                    await db.execute("""
                        INSERT INTO auction_house (
                            guild_id, item_name, amount, seller_name,
                            current_bid, min_increment, created_at, end_time, is_closed
                        ) VALUES (?, ?, ?, '違規撕卡清算', 1000, 200, ?, ?, 0)
                    """, (g_id, it_name, it_amt, time.time(), auc_end_time))
                    auction_items.append(f"• **{it_name}** ×{it_amt} (起拍價 $1,000，結標倒數 48 小時)")

            total_legacy_pool_money += liquidated_items_money

            # 瓜分金錢至全服其他角色/官角銀行
            share_money_per_char = 0
            if total_beneficiaries > 0 and total_legacy_pool_money > 0:
                share_money_per_char = max(1, total_legacy_pool_money // total_beneficiaries)
                await db.execute("""
                    UPDATE characters SET bank = bank + ? 
                    WHERE guild_id = ? AND is_npc IN (0, 1) AND name != ?
                """, (share_money_per_char, g_id, c_name))

            # 瓜分能力值（修為保底均分）
            stat_distributions = []
            if total_beneficiaries > 0 and stats:
                for k, v in stats.items():
                    if isinstance(v, (int, float)) and v > 0:
                        per_stat = max(1, v // total_beneficiaries)
                        for b_name in beneficiaries:
                            async with db.execute("SELECT stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, b_name)) as b_cur:
                                b_row = await b_cur.fetchone()
                                b_st = json.loads(b_row[0]) if (b_row and b_row[0]) else {}
                                b_st[k] = b_st.get(k, 0) + per_stat
                                await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(b_st, ensure_ascii=False), g_id, b_name))
                        stat_distributions.append(f"{k} +{per_stat}")

            # 徹底撕卡註銷
            await db.execute("DELETE FROM inventory WHERE guild_id = ? AND owner_name = ?", (g_id, c_name))
            await db.execute("DELETE FROM personal_assets WHERE guild_id = ? AND owner_name = ?", (g_id, c_name))
            await db.execute("DELETE FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name))
            await db.commit()

            try:
                await 對象玩家.kick(reason=f"違反規章：{clause}（累積 {warn_count} 次違規，全服封殺撕卡）")
            except Exception:
                pass

            punishment_details.append("⛔ **【終生封殺與撕卡處決】**")
            punishment_details.append(f"該成員已被逐出伺服器，角色【**{c_name}**】檔案已徹底撕毀註銷！")
            punishment_details.append(f"\n🎁 **【全服遺產繼承（共 {total_beneficiaries} 位角色/官角）】**")
            punishment_details.append(f"• 💰 遺產金錢總額：**${total_legacy_pool_money:,}**（每人銀行入帳 **+${share_money_per_char:,}**）")
            if stat_distributions:
                punishment_details.append(f"• ✨ 屬性修為瓜分（保底補足）：**{', '.join(stat_distributions[:5])}**")
            if auction_items:
                punishment_details.append(f"• 🏷️ 特殊物品無法折算，已移交拍賣行：\n  " + "\n  ".join(auction_items))

    status_title = f"🚨【重大違規・全服封殺撕卡通報】" if is_ban_and_rip else f"⚠️【違規懲處公示 — 第 {warn_count} 次告誡】"
    embed_color = 0x992D22 if is_ban_and_rip else 0xE67E22

    public_embed = discord.Embed(title=status_title, color=embed_color)
    public_embed.description = (
        f"**違規受懲成員**：{對象玩家.mention} ｜ 涉及角色：**{c_name}**\n"
        f"**執法管理員**：{interaction.user.mention}\n"
        f"**累積違規次數**：`{warn_count}` 次\n\n"
        f"📌 **違反規章條款**：`{clause}`\n"
        f"📜 **官方規章連結**：[點此前往閱讀規章詳情]({rule_url})\n\n"
        f"📝 **具體事由**：\n> {reason_text}\n\n"
        f"🔍 **實質存證連結**：[點此檢視違規截圖或紀錄]({evidence_url})\n\n"
        + "\n".join(punishment_details)
    )

    try:
        dm_msg = (
            f"⚖️ **【伺服器違規懲處通知】**\n"
            f"你在伺服器【{interaction.guild.name}】因違反規定被登記懲處：\n"
            f"• 違反條款：{clause}\n"
            f"• 規章詳情：{rule_url}\n"
            f"• 處分事由：{reason_text}\n"
            f"• 實質存證：{evidence_url}\n"
            f"• 當前累積警告：{warn_count} 次\n\n"
            + ("⛔ 你已被永久逐出伺服器，角色已遭撕卡並瓜分遺產！" if is_ban_and_rip else f"⚠️ 角色【{c_name}】數值已受扣除懲處，請立即端正規範言行！")
        )
        await 對象玩家.send(dm_msg)
    except Exception:
        pass

    await broadcast_event(interaction.guild, "penalty", public_embed)
    await interaction.followup.send(embed=public_embed)
# -------------------- 指令：/拍賣行 --------------------
@bot.tree.command(name="拍賣行", description="查閱全服拍賣行進行中的珍品、稀有道具與即時競標看板")
async def auction_house_cmd(interaction: discord.Interaction):
    g_id = interaction.guild_id
    now_ts = time.time()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id, item_name, amount, seller_name, current_bid, highest_bidder_char, end_time, min_increment
            FROM auction_house
            WHERE guild_id = ? AND is_closed = 0 AND end_time > ?
            ORDER BY end_time ASC
        """, (g_id, now_ts)) as cur:
            items = await cur.fetchall()

    if not items:
        await interaction.response.send_message("🏛️ 全服拍賣行目前暫無正在競標的商品。敬請期待官方活動或留意違規拍賣！", ephemeral=True)
        return

    item_lines = []
    for a_id, i_name, amt, seller, cur_bid, top_bidder, end_t, min_inc in items:
        rem_seconds = int(end_t - now_ts)
        rem_hours = rem_seconds // 3600
        rem_minutes = (rem_seconds % 3600) // 60
        time_str = f"{rem_hours}時{rem_minutes}分" if rem_hours > 0 else f"{rem_minutes}分鐘"

        top_info = f"領先者: **{top_bidder}**" if top_bidder else "目前暫無人出價"
        item_lines.append(
            f"• **[ID: {a_id}] 《{i_name}》** ×{amt}\n"
            f"  └ 來源: `{seller}` ｜ 當前最高標: **${cur_bid:,}** ({top_info})\n"
            f"  └ 最低每次加價: `${min_inc:,}` ｜ ⏳ 剩餘時間: `{time_str}`"
        )

    p_view = PagedDetailView("🏛️ 全服公開拍賣行會場", item_lines, 0xF1C40F, page_size=5)
    first_embed = p_view.get_embed()
    first_embed.set_footer(text="競標指令：/拍賣競標 拍賣品編號:ID 競標角色名:你的角色 出價金額:金額")
    await interaction.response.send_message(embed=first_embed, view=p_view)


# -------------------- 指令：/拍賣競標 --------------------
@bot.tree.command(name="拍賣競標", description="在全服拍賣行對指定拍賣品出價（最低加價 $200，超車原出價者全額秒退）")
@app_commands.describe(
    拍賣品編號="拍賣品 ID（可從 /拍賣行 查看）",
    競標角色名="參與出價競標的角色全名",
    出價金額="欲出的總金額 (必須大於當前最高標 + 最低加價額度)"
)
async def auction_bid_cmd(
    interaction: discord.Interaction,
    拍賣品編號: int,
    競標角色名: str,
    出價金額: int
):
    g_id = interaction.guild_id
    a_id = 拍賣品編號
    c_name = 競標角色名.strip()
    bid_amount = 出價金額
    now_ts = time.time()

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. 檢驗拍賣品存在與是否過期
        async with db.execute("""
            SELECT item_name, amount, current_bid, highest_bidder_char, highest_bidder_uid, end_time, min_increment, is_closed
            FROM auction_house WHERE id = ? AND guild_id = ?
        """, (a_id, g_id)) as cur:
            auc = await cur.fetchone()

        if not auc or auc[7] == 1 or auc[5] <= now_ts:
            await interaction.response.send_message("❌ 該拍賣品不存在、已結標或已超過競標時限！", ephemeral=True)
            return

        i_name, amt, cur_bid, prev_bidder_char, prev_bidder_uid, end_t, min_inc, _ = auc

        # 2. 檢驗角色身分權限
        async with db.execute("SELECT user_id, cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as c_cur:
            c_row = await c_cur.fetchone()

        if not c_row:
            await interaction.response.send_message(f"❌ 查無競標角色【{c_name}】！", ephemeral=True)
            return

        u_id, cash, bank = c_row
        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 你只能代表自己名下的角色進行競標！", ephemeral=True)
            return

        if prev_bidder_char == c_name:
            await interaction.response.send_message("ℹ️ 你目前已經是該物品的最高出價領先者，無需重複出價！", ephemeral=True)
            return

        # 3. 檢驗出價金額門檻（當前價 + 最低加價門檻，預設 200）
        required_min_bid = cur_bid + min_inc
        if bid_amount < required_min_bid:
            await interaction.response.send_message(
                f"❌ 出價金額不足！當前最高標為 **${cur_bid:,}**，每次最低加價需 **${min_inc:,}**。\n"
                f"最低允許出價金額為：**${required_min_bid:,}**！",
                ephemeral=True
            )
            return

        # 4. 檢驗出價者資金
        total_funds = cash + bank
        if total_funds < bid_amount:
            await interaction.response.send_message(
                f"❌ 資金不足！本次競標出價 **${bid_amount:,}**，但 **{c_name}** 名下手頭現金與銀行存款總計僅有 **${total_funds:,}**！",
                ephemeral=True
            )
            return

        # 5. 扣款凍結出價者資金（優先扣除現金，不足扣銀行）
        if cash >= bid_amount:
            await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (bid_amount, g_id, c_name))
        else:
            rem = bid_amount - cash
            await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (rem, g_id, c_name))

        # 6. 超車原領先者：全額秒退原出價款項至其銀行
        refund_note = ""
        if prev_bidder_char and cur_bid > 0:
            await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (cur_bid, g_id, prev_bidder_char))
            refund_note = f"\n💸 原領先者 **{prev_bidder_char}** 的保證金 **${cur_bid:,}** 已秒退回其銀行存款！"

            # 嘗試私訊通知被超車玩家
            if prev_bidder_uid > 0:
                prev_member = interaction.guild.get_member(prev_bidder_uid)
                if prev_member:
                    try:
                        await prev_member.send(
                            f"🔔 **【拍賣超車通知】**\n你在拍賣行競標的【**{i_name}**】已被 **{c_name}** 以 **${bid_amount:,}** 超車！\n"
                            f"你原先出價的 **${cur_bid:,}** 已全額退還至【{prev_bidder_char}】的銀行帳戶。"
                        )
                    except Exception:
                        pass

        # 7. 更新拍賣品最高出價
        await db.execute("""
            UPDATE auction_house
            SET current_bid = ?, highest_bidder_char = ?, highest_bidder_uid = ?
            WHERE id = ?
        """, (bid_amount, c_name, u_id, a_id))
        await db.commit()

    embed = discord.Embed(title="🔨 拍賣競標成功・出價領先！", color=0x2ECC71)
    embed.description = (
        f"**{c_name}** (<@{u_id}>) 成功在拍賣行對【**{i_name}**】×{amt} 出價！\n\n"
        f"• 最新最高出價：**${bid_amount:,}**\n"
        f"• 結標前若無更高出價，到期時系統將全自動派發至個人背包。{refund_note}"
    )
    await interaction.response.send_message(embed=embed)
# -------------------- 指令：/娛樂城 --------------------
@bot.tree.command(name="娛樂城", description="進入娛樂大廳參與比大小、九宮格幸運刮刮樂或購買全服累積樂透")
@app_commands.choices(遊戲項目=[
    app_commands.Choice(name="🎲 骰子比大小", value="dice"),
    app_commands.Choice(name="🎫 九宮格幸運刮刮樂", value="scratch"),
    app_commands.Choice(name="🎰 購買本期全服累積樂透彩券", value="lottery")
])
@app_commands.choices(押注大小=[
    app_commands.Choice(name="大 (11~17 點)", value="big"),
    app_commands.Choice(name="小 (4~10 點)", value="small")
])
@app_commands.describe(
    角色名="參與遊玩的角色全名",
    遊戲項目="選擇欲體驗的娛樂城項目",
    押注大小="［骰子比大小專用］選擇押大或押小",
    下注或購票金額="［骰子下注金額］純整數",
    樂透自選號碼="［樂透專用］5個1~39的數字，以空格或逗號隔開 (留空則機選)"
)
async def casino_cmd(
    interaction: discord.Interaction,
    角色名: str,
    遊戲項目: app_commands.Choice[str],
    押注大小: app_commands.Choice[str] = None,
    下注或購票金額: int = 500,
    樂透自選號碼: str = None
):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    game = 遊戲項目.value

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()

        if not c_row:
            await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
            return

        u_id, cash, bank = c_row
        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 你只能代表自己的角色在娛樂城遊玩！", ephemeral=True)
            return

        # 1. 骰子比大小
        if game == "dice":
            if not 押注大小:
                await interaction.response.send_message("❌ 進行骰子比大小時，請指定【押注大小】！", ephemeral=True)
                return
            if 下注或購票金額 <= 0:
                await interaction.response.send_message("❌ 下注金額需大於 0！", ephemeral=True)
                return

            bet = 下注或購票金額
            if cash < bet:
                await interaction.response.send_message(f"❌ 手頭現金不足！目前僅有現金 **${cash:,}**（骰子只接受手頭現金下注）。", ephemeral=True)
                return

            d1, d2, d3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
            total_pts = d1 + d2 + d3

            # 圍骰判定（通殺）
            is_leopard = (d1 == d2 == d3)
            result_str = "圍骰 (莊家通殺)" if is_leopard else ("大" if total_pts >= 11 else "小")
            win = (not is_leopard) and ((押注大小.value == "big" and total_pts >= 11) or (押注大小.value == "small" and total_pts <= 10))

            if win:
                win_money = bet
                await db.execute("UPDATE characters SET cash = cash + ? WHERE guild_id = ? AND name = ?", (win_money, g_id, c_name))
                outcome_text = f"🎉 **【恭喜中獎】** 贏得彩金 **+${win_money:,}**！"
                card_color = 0x2ECC71
            else:
                await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (bet, g_id, c_name))
                outcome_text = f"💸 **【很遺憾未中】** 損失下注金 **-${bet:,}**！"
                card_color = 0xE74C3C

            await db.commit()

            embed = discord.Embed(title=f"🎲 骰子比大小結算 — 【{c_name}】", color=card_color)
            embed.description = (
                f"• 開獎點數：🎲 `[{d1}]` + `[{d2}]` + `[{d3}]` ＝ **{total_pts} 點**\n"
                f"• 開出盤口：【**{result_str}**】 ｜ 你的押注：【**{押注大小.name}**】\n\n"
                f"{outcome_text}"
            )
            await interaction.response.send_message(embed=embed)
            return

        # 2. 九宮格幸運刮刮樂
        elif game == "scratch":
            ticket_price = 300
            if cash < ticket_price:
                await interaction.response.send_message(f"❌ 現金不足！購買一張九宮格刮刮樂需 **${ticket_price:,}** 現金。", ephemeral=True)
                return

            # 九宮格色彩隨機生成
            palette = ["🟦", "🟦", "🟩", "🟩", "🟨", "🟧", "🟥", "🟪", "✨"]
            grid = [random.choice(palette) for _ in range(9)]
            gold_count = grid.count("✨")
            purple_count = grid.count("🟪")

            prize = 0
            if gold_count >= 3:
                prize = ticket_price * 50
                win_desc = f"🌟 **【極光特獎】** 刮出 3 個 ✨ 幸運星！獲得 50 倍大獎 **${prize:,}**！"
            elif gold_count == 2:
                prize = ticket_price * 10
                win_desc = f"🎁 **【二等幸運獎】** 刮出 2 個 ✨ 幸運星！獲得 10 倍獎金 **${prize:,}**！"
            elif gold_count == 1 or purple_count >= 3:
                prize = ticket_price * 3
                win_desc = f"🎈 **【歡樂普獎】** 刮出稀有色塊！獲得 3 倍獎金 **${prize:,}**！"
            else:
                win_desc = "💨 差一點點！這張刮刮樂沒有中獎，再接再厲。"

            diff = prize - ticket_price
            await db.execute("UPDATE characters SET cash = cash + ? WHERE guild_id = ? AND name = ?", (diff, g_id, c_name))
            await db.commit()

            grid_view = (
                f"{grid[0]} ｜ {grid[1]} ｜ {grid[2]}\n"
                f"{grid[3]} ｜ {grid[4]} ｜ {grid[5]}\n"
                f"{grid[6]} ｜ {grid[7]} ｜ {grid[8]}"
            )

            embed = discord.Embed(title=f"🎫 九宮格刮刮樂開獎 — 【{c_name}】", color=0xF1C40F if prize > 0 else 0x95A5A6)
            embed.description = f"**九宮格刮開結果：**\n\n{grid_view}\n\n{win_desc}"
            embed.set_footer(text=f"每張票面售價 ${ticket_price:,} ｜ 現金即時派彩結算")
            await interaction.response.send_message(embed=embed)
            return

        # 3. 購買本期累積樂透彩券
        elif game == "lottery":
            async with db.execute("SELECT ticket_price, jackpot_pool FROM lottery_jackpot WHERE guild_id = ?", (g_id,)) as j_cur:
                j_row = await j_cur.fetchone()

            ticket_cost = j_row[0] if (j_row and j_row[0]) else 200

            if cash < ticket_cost:
                await interaction.response.send_message(f"❌ 手頭現金不足！購買 1 注樂透彩券需 **${ticket_cost:,}** 現金。", ephemeral=True)
                return

            # 解析號碼（5 個 1~39 不重複）
            chosen_numbers = []
            if 樂透自選號碼:
                raw_nums = re.split(r"[,，\s]+", 樂透自選號碼.strip())
                for rn in raw_nums:
                    try:
                        n = int(rn)
                        if 1 <= n <= 39 and n not in chosen_numbers:
                            chosen_numbers.append(n)
                    except ValueError:
                        pass

            if len(chosen_numbers) != 5:
                # 號碼不足或格式錯誤時自動隨機補足
                chosen_numbers = sorted(random.sample(range(1, 40), 5))
                tip_note = "（系統已為你隨機機選 5 個幸運號碼）"
            else:
                chosen_numbers.sort()
                tip_note = "（自選號碼下注）"

            nums_str = " ".join([f"{n:02d}" for n in chosen_numbers])

            # 扣款並注入累積獎池
            await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (ticket_cost, g_id, c_name))
            await db.execute("""
                INSERT INTO lottery_jackpot (guild_id, jackpot_pool, ticket_price)
                VALUES (?, 10000 + ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET jackpot_pool = jackpot_pool + ?
            """, (g_id, ticket_cost, ticket_cost, ticket_cost))

            # 登記個人持有彩券
            await db.execute("""
                INSERT INTO lottery_tickets (guild_id, char_name, user_id, numbers, bought_at)
                VALUES (?, ?, ?, ?, ?)
            """, (g_id, c_name, u_id, nums_str, time.time()))
            await db.commit()

            async with db.execute("SELECT jackpot_pool FROM lottery_jackpot WHERE guild_id = ?", (g_id,)) as cur:
                curr_pool = (await cur.fetchone())[0]

            embed = discord.Embed(title="🎰【樂透彩券購買成功】", color=0x9B59B6)
            embed.description = (
                f"• 持有角色：**{c_name}** (<@{u_id}>)\n"
                f"• 彩券號碼：`{nums_str}` {tip_note}\n"
                f"• 投注花費：**${ticket_cost:,}** 現金\n\n"
                f"💰 **全服本期累積總獎池：** **${curr_pool:,}**！\n"
                f"等待管理員使用 `/彩票管理` 進行即時或預約搖獎開出頭獎！"
            )
            await interaction.response.send_message(embed=embed)
            return


# -------------------- 指令：/彩票管理（開獎與彩池設定） --------------------
@bot.tree.command(name="彩票管理", description="【管理員專用】手動搖號開獎、注資獎池或設定樂透單價")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="🎉 本期全服樂透搖號開獎", value="draw_lottery"),
    app_commands.Choice(name="💰 向累積獎池手動注資加碼", value="inject_jackpot"),
    app_commands.Choice(name="⚙️ 設定彩券單價", value="cfg_ticket")
])
@app_commands.describe(
    操作="選擇要執行的彩票管理動作",
    金額="［注資加碼或單價設定］純數字"
)
async def lottery_admin_cmd(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    金額: int = 0
):
    g_id = interaction.guild_id
    op = 操作.value

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. 獎池注資
        if op == "inject_jackpot":
            if 金額 <= 0:
                await interaction.response.send_message("❌ 注資金額需大於 0！", ephemeral=True)
                return

            await db.execute("""
                INSERT INTO lottery_jackpot (guild_id, jackpot_pool) VALUES (?, 10000 + ?)
                ON CONFLICT(guild_id) DO UPDATE SET jackpot_pool = jackpot_pool + ?
            """, (g_id, 金額, 金額))
            await db.commit()

            async with db.execute("SELECT jackpot_pool FROM lottery_jackpot WHERE guild_id = ?", (g_id,)) as cur:
                new_pool = (await cur.fetchone())[0]

            await interaction.response.send_message(f"💰 成功為全服樂透獎池注資 **${金額:,}**！當前累積總彩池達到 **${new_pool:,}**！")
            return

        # 2. 設定彩券單價
        elif op == "cfg_ticket":
            if 金額 <= 0:
                await interaction.response.send_message("❌ 單價需大於 0！", ephemeral=True)
                return

            await db.execute("""
                INSERT INTO lottery_jackpot (guild_id, ticket_price) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET ticket_price = ?
            """, (g_id, 金額, 金額))
            await db.commit()

            await interaction.response.send_message(f"⚙️ 每注樂透彩券售價已調整為 **${金額:,}** 現金！", ephemeral=True)
            return

        # 3. 樂透搖號開獎
        elif op == "draw_lottery":
            await interaction.response.defer(ephemeral=False)

            async with db.execute("SELECT jackpot_pool FROM lottery_jackpot WHERE guild_id = ?", (g_id,)) as cur:
                j_row = await cur.fetchone()

            total_pool = j_row[0] if (j_row and j_row[0]) else 10000

            # 搖出 5 個不重複中獎號碼
            winning_numbers = sorted(random.sample(range(1, 40), 5))
            win_str = " ".join([f"{n:02d}" for n in winning_numbers])

            async with db.execute("SELECT id, char_name, user_id, numbers FROM lottery_tickets WHERE guild_id = ?", (g_id,)) as cur:
                all_tickets = await cur.fetchall()

            jackpot_winners = []
            for t_id, c_name, u_id, t_nums in all_tickets:
                if t_nums.strip() == win_str.strip():
                    jackpot_winners.append((c_name, u_id))

            if jackpot_winners:
                # 命中頭獎：瓜分總獎金
                per_prize = total_pool // len(jackpot_winners)
                winner_names = []
                for c_name, u_id in jackpot_winners:
                    await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (per_prize, g_id, c_name))
                    winner_names.append(f"**{c_name}** (<@{u_id}>)")

                # 獎池重置為保底 10000
                await db.execute("UPDATE lottery_jackpot SET jackpot_pool = 10000 WHERE guild_id = ?", (g_id,))
                result_announcement = (
                    f"🏆 **【頭獎開出・全彩池瓜分】**\n"
                    f"恭喜以下幸運兒精準命中全部 5 個號碼：\n"
                    f"{'、'.join(winner_names)}\n\n"
                    f"每位獲派彩金：**+${per_prize:,}**（已全額匯入銀行戶頭）！"
                )
                embed_color = 0x2ECC71
            else:
                # 無人中獎：獎金滾入下期
                result_announcement = (
                    f"💨 **【本期頭獎槓龜・全額滾入下期】**\n"
                    f"本期售出 `{len(all_tickets)}` 注彩券，無人精準命中全部 5 個號碼。\n"
                    f"目前累積總彩池 **${total_pool:,}** 將全數保留，繼續累積至下期開獎！"
                )
                embed_color = 0xF1C40F

            # 清空本期持有的彩券
            await db.execute("DELETE FROM lottery_tickets WHERE guild_id = ?", (g_id,))
            await db.commit()

            embed = discord.Embed(title="🎰✨【全服樂透搖號開獎大會】", color=embed_color)
            embed.description = (
                f"🎲 **本期中獎幸運號碼：**\n"
                f"## 🌟 ` {win_str} ` 🌟\n\n"
                f"💰 **本期累積獎池總額：** **${total_pool:,}**\n\n"
                f"{result_announcement}"
            )
            embed.set_footer(text="娛樂城樂透已全自動清算完畢 ｜ 玩家可隨時使用 /娛樂城 購買新一期彩券")

            await broadcast_event(interaction.guild, "holiday", embed)
            await interaction.followup.send(embed=embed)
            return
# -------------------- 指令：/存錢 --------------------
@bot.tree.command(name="存錢", description="將角色手頭現金存入銀行（純數字或輸入［全部］）")
@app_commands.describe(角色名="欲進行存款的角色姓名", 金額="純整數金額，或輸入［全部］")
async def deposit_cmd(interaction: discord.Interaction, 角色名: str, 金額: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()

        if not c_row:
            await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
            return

        u_id, cash, bank = c_row
        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 你只能為自己的角色辦理存款業務！", ephemeral=True)
            return

        if 金額.strip() in ["全部", "all", "All"]:
            deposit_val = cash
        else:
            try:
                deposit_val = int(金額.strip())
                if deposit_val <= 0: raise ValueError
            except ValueError:
                await interaction.response.send_message("❌ 請輸入大於 0 的有效金額或輸入［全部］！", ephemeral=True)
                return

        if deposit_val > cash:
            await interaction.response.send_message(f"❌ 現金不足！手頭僅有現金 **${cash:,}**。", ephemeral=True)
            return

        if deposit_val <= 0:
            await interaction.response.send_message("ℹ️ 手頭上沒有現金可存入銀行。", ephemeral=True)
            return

        await db.execute("""
            UPDATE characters SET cash = cash - ?, bank = bank + ? WHERE guild_id = ? AND name = ?
        """, (deposit_val, deposit_val, g_id, c_name))
        await db.commit()

    await interaction.response.send_message(
        f"🏦 **{c_name}** 成功存入 **${deposit_val:,}**！\n"
        f"• 最新手頭現金：**${cash - deposit_val:,}**\n"
        f"• 最新銀行存款：**${bank + deposit_val:,}**（享有每日銀行利息）"
    )


# -------------------- 指令：/取錢 --------------------
@bot.tree.command(name="取錢", description="自銀行提領存款至手頭現金（純數字或輸入［全部］）")
@app_commands.describe(角色名="欲進行提款的角色姓名", 金額="純整數金額，或輸入［全部］")
async def withdraw_cmd(interaction: discord.Interaction, 角色名: str, 金額: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()

        if not c_row:
            await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
            return

        u_id, cash, bank = c_row
        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 你只能為自己的角色辦理提款業務！", ephemeral=True)
            return

        if 金額.strip() in ["全部", "all", "All"]:
            withdraw_val = bank
        else:
            try:
                withdraw_val = int(金額.strip())
                if withdraw_val <= 0: raise ValueError
            except ValueError:
                await interaction.response.send_message("❌ 請輸入大於 0 的有效金額或輸入［全部］！", ephemeral=True)
                return

        if withdraw_val > bank:
            await interaction.response.send_message(f"❌ 存款不足！銀行戶頭僅有存款 **${bank:,}**。", ephemeral=True)
            return

        if withdraw_val <= 0:
            await interaction.response.send_message("ℹ️ 銀行帳戶內沒有存款可供提領。", ephemeral=True)
            return

        await db.execute("""
            UPDATE characters SET cash = cash + ?, bank = bank - ? WHERE guild_id = ? AND name = ?", (withdraw_val, withdraw_val, g_id, c_name))
        """, (withdraw_val, withdraw_val, g_id, c_name))
        await db.commit()

    await interaction.response.send_message(
        f"💸 **{c_name}** 成功從銀行提領 **${withdraw_val:,}**！\n"
        f"• 最新手頭現金：**${cash + withdraw_val:,}**\n"
        f"• 銀行剩餘存款：**${bank - withdraw_val:,}**"
    )


# -------------------- 指令：/任務 --------------------
@bot.tree.command(name="任務", description="查閱全服通告任務、新手引導、限時通告與特殊歷練清單")
@app_commands.choices(分類=[
    app_commands.Choice(name="全部任務", value="all"),
    app_commands.Choice(name="新手任務", value="新手任務"),
    app_commands.Choice(name="一般任務", value="一般任務"),
    app_commands.Choice(name="限時任務", value="限時任務"),
    app_commands.Choice(name="特殊任務", value="特殊任務")
])
@app_commands.describe(分類="挑選欲查看的任務板塊")
async def quests_list_cmd(interaction: discord.Interaction, 分類: app_commands.Choice[str] = None):
    g_id = interaction.guild_id
    target_cat = 分類.value if 分類 else "all"

    query = "SELECT category, title, reward_cash, reward_items, reward_stats, time_limit FROM quests WHERE guild_id = ?"
    params = [g_id]
    if target_cat != "all":
        query += " AND category = ?"
        params.append(target_cat)
    query += " ORDER BY id DESC"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(query, tuple(params)) as cur:
            all_quests = await cur.fetchall()

    if not all_quests:
        await interaction.response.send_message("📋 目前任務公告欄暫無對應任務。管理員可使用 `/任務新增` 發布通告！", ephemeral=True)
        return

    quest_lines = []
    for cat, title, cash_r, items_r, stats_r, t_limit in all_quests:
        rew_desc = []
        if cash_r > 0: rew_desc.append(f"${cash_r:,}")
        if stats_r: rew_desc.append(f"數值: `{stats_r}`")
        if items_r and items_r != "[]":
            try:
                its = json.loads(items_r)
                rew_desc.append("道具: " + "、".join([f"`{it.get('name')}×{it.get('amount',1)}`" for it in its]))
            except Exception:
                rew_desc.append(f"道具: `{items_r}`")

        time_note = f" ｜ ⏳ `{t_limit}`" if t_limit else ""
        quest_lines.append(
            f"• 【{cat}】**《{title}》**{time_note}\n"
            f"  └ 酬勞：{' ｜ '.join(rew_desc) if rew_desc else '聲譽歷練'}"
        )

    p_view = PagedDetailView("📜 官方任務與通告公告大廳", quest_lines, 0x3498DB, page_size=6)
    first_embed = p_view.get_embed()
    first_embed.set_footer(text="完成通告後請使用 /回報任務 領取酬勞與確立正式出道身分！")
    await interaction.response.send_message(embed=first_embed, view=p_view)


# -------------------- 指令：/回報任務（自動結算、陣營抽稅與新秀轉正出道） --------------------
@bot.tree.command(name="回報任務", description="回報已完成的任務（自動入帳銀行、道具入背包、陣營抽稅與新秀轉正正式出道）")
@app_commands.describe(角色名="回報任務的角色全名", 任務名稱="任務完整名稱")
async def report_quest_cmd(interaction: discord.Interaction, 角色名: str, 任務名稱: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    q_title = 任務名稱.strip()

    await interaction.response.defer(ephemeral=False)

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. 檢驗角色存在
        async with db.execute("""
            SELECT user_id, faction, bank, stats, debut_years, debut_age
            FROM characters WHERE guild_id = ? AND name = ?
        """, (g_id, c_name)) as cur:
            c_row = await cur.fetchone()

        if not c_row:
            await interaction.followup.send(f"❌ 查無角色檔案【{c_name}】！", ephemeral=True)
            return

        u_id, faction_name, cur_bank, stats_json, debut_years, debut_age = c_row
        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ 你只能為自己的角色回報完成任務！", ephemeral=True)
            return

        # 2. 檢驗任務存在
        async with db.execute("""
            SELECT category, reward_cash, reward_items, reward_stats, time_limit
            FROM quests WHERE guild_id = ? AND title = ?
        """, (g_id, q_title)) as q_cur:
            q_row = await q_cur.fetchone()

        if not q_row:
            await interaction.followup.send(f"❌ 查無任務【{q_title}】！請至 `/任務` 核對完整名稱。", ephemeral=True)
            return

        cat, rew_cash, rew_items_json, rew_stats_str, time_limit = q_row

        # 3. 陣營抽稅計算
        tax_deducted = 0
        actual_cash_to_player = rew_cash
        tax_msg = ""

        if faction_name and faction_name != "無" and rew_cash > 0:
            async with db.execute("SELECT tax_rate FROM factions WHERE guild_id = ? AND name = ?", (g_id, faction_name)) as f_cur:
                f_row = await f_cur.fetchone()

            if f_row and f_row[0] > 0:
                tax_rate = f_row[0]
                tax_deducted = int(rew_cash * tax_rate)
                actual_cash_to_player = rew_cash - tax_deducted

                # 注入陣營金庫公款並累計成員貢獻
                await db.execute("UPDATE factions SET treasury = treasury + ? WHERE guild_id = ? AND name = ?", (tax_deducted, g_id, faction_name))
                await db.execute("""
                    INSERT INTO faction_members (guild_id, faction_name, char_name, contribution)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(guild_id, faction_name, char_name) DO UPDATE SET contribution = contribution + ?
                """, (g_id, faction_name, c_name, tax_deducted, tax_deducted))
                tax_msg = f"\n🚩 **【陣營抽稅】** 繳交 {int(tax_rate*100)}% 稅金 **${tax_deducted:,}** 至【{faction_name}】金庫（貢獻度 +{tax_deducted}）！"

        # 4. 發放金錢與道具
        if actual_cash_to_player > 0:
            await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (actual_cash_to_player, g_id, c_name))

        reward_items_notes = []
        if rew_items_json and rew_items_json != "[]":
            try:
                its = json.loads(rew_items_json)
                for it in its:
                    it_name = it.get("name")
                    it_amt = it.get("amount", 1)
                    if it_name:
                        async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, c_name, it_name)) as inv_cur:
                            inv_row = await inv_cur.fetchone()
                            if inv_row:
                                await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (it_amt, inv_row[0]))
                            else:
                                await db.execute("""
                                    INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver)
                                    VALUES (?, ?, ?, ?, '任務完成通告獎勵')
                                """, (g_id, c_name, it_name, it_amt))
                        reward_items_notes.append(f"`{it_name} ×{it_amt}`")
            except Exception:
                pass

        # 5. 發放屬性加成
        stats = json.loads(stats_json) if stats_json else {}
        stat_gain_notes = []
        if rew_stats_str:
            for part in re.split(r"[,，、\s]+", rew_stats_str.strip()):
                m = re.search(r"([^\d+-]+)([+-]?\d+)", part)
                if m:
                    sk, sv = m.group(1).strip(), int(m.group(2))
                    stats[sk] = max(0, stats.get(sk, 0) + sv)
                    sign = "+" if sv >= 0 else ""
                    stat_gain_notes.append(f"{sk} {sign}{sv}")

        # 6. 新秀正式出道身分確立（資歷 0 年 -> 1 年轉正）
        debut_upgrade_note = ""
        new_debut_years = debut_years or 0
        if new_debut_years <= 0:
            new_debut_years = 1
            debut_upgrade_note = (
                f"\n🎉🌟 **【正式出道資格確立】**\n"
                f"**{c_name}** 順利圓滿完成首次通告歷練，正式告別新秀／未出道身分，**確立為正式出道藝人／修行者**（資歷晉升為 1 年）！"
            )

        # 登記歷練履歷 Works
        async with db.execute("SELECT works FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as w_cur:
            works_data = json.loads((await w_cur.fetchone())[0] or "[]")
        works_data.append({"category": "成就", "type": "通告", "title": q_title, "extra": "官方驗證完成"})

        await db.execute("""
            UPDATE characters 
            SET stats = ?, debut_years = ?, works = ?
            WHERE guild_id = ? AND name = ?
        """, (json.dumps(stats, ensure_ascii=False), new_debut_years, json.dumps(works_data, ensure_ascii=False), g_id, c_name))

        # 記錄任務完成歷史
        await db.execute("""
            INSERT INTO quest_completions (guild_id, char_name, quest_title, completed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, char_name, quest_title) DO UPDATE SET completed_at = excluded.completed_at
        """, (g_id, c_name, q_title, time.time()))
        await db.commit()

    # 自動觸發地位檢驗晉升
    await check_and_update_rank(g_id, c_name, interaction.channel)

    embed = discord.Embed(title=f"🎬 任務完成結算：【{c_name}】— 《{q_title}》", color=0x2ECC71)
    embed.description = (
        f"**通告任務圓滿達成！**\n\n"
        f"• 💰 銀行實領酬勞：**+${actual_cash_to_player:,}**{tax_msg}\n"
        + (f"• 📦 道具犒賞：{'、'.join(reward_items_notes)}\n" if reward_items_notes else "")
        + (f"• ✨ 實力提升：{'、'.join(stat_gain_notes)}\n" if stat_gain_notes else "")
        + f"{debut_upgrade_note}"
    )
    embed.set_footer(text="通告歷練已收錄至角色履歷中 ｜ 隨時可使用 /查看 調閱")
    await interaction.followup.send(embed=embed)
# -------------------- ProfileUpdateStepView（個資編輯面板） --------------------
class ProfileUpdateStepView(discord.ui.View):
    def __init__(self, char_name: str, guild_id: int, is_admin: bool):
        super().__init__(timeout=180)
        self.char_name = char_name
        self.guild_id = guild_id
        self.is_admin = is_admin

    @discord.ui.button(label="✏️ 修改藝名/稱號", style=discord.ButtonStyle.primary, row=0)
    async def edit_stage_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        class NameModal(discord.ui.Modal, title=f"修改【{self.char_name}】的藝名/稱號"):
            new_name = discord.ui.TextInput(label="請輸入全新藝名、道號或稱呼", max_length=20)

            async def on_submit(m_self, m_inter: discord.Interaction):
                val = m_self.new_name.value.strip()
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("UPDATE characters SET stage_name = ? WHERE guild_id = ? AND name = ?", (val, self.guild_id, self.char_name))
                    await db.commit()
                await m_inter.response.send_message(f"✅ 藝名/稱號已更新為：**{val}**！", ephemeral=True)

        await interaction.response.send_modal(NameModal())

    @discord.ui.button(label="💼 修改職業/身分", style=discord.ButtonStyle.primary, row=0)
    async def edit_job(self, interaction: discord.Interaction, button: discord.ui.Button):
        class JobModal(discord.ui.Modal, title=f"修改【{self.char_name}】的職業/門派身分"):
            new_job = discord.ui.TextInput(label="請輸入全新職業或身分名稱", max_length=20)

            async def on_submit(m_self, m_inter: discord.Interaction):
                val = m_self.new_job.value.strip()
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("UPDATE characters SET job = ? WHERE guild_id = ? AND name = ?", (val, self.guild_id, self.char_name))
                    await db.commit()
                await m_inter.response.send_message(f"✅ 職業身分已更新為：**{val}**！", ephemeral=True)

        await interaction.response.send_modal(JobModal())

    @discord.ui.button(label="💞 登記/修改 CP 對象", style=discord.ButtonStyle.success, row=1)
    async def edit_cp(self, interaction: discord.Interaction, button: discord.ui.Button):
        class CPModal(discord.ui.Modal, title=f"登記【{self.char_name}】的道侶/CP"):
            target_name = discord.ui.TextInput(label="CP/道侶角色全名", placeholder="請填寫對象角色姓名")
            rel_type = discord.ui.TextInput(label="關係稱呼 (預設: 伴侶)", default="伴侶", max_length=10)

            async def on_submit(m_self, m_inter: discord.Interaction):
                t_name = m_self.target_name.value.strip()
                r_type = m_self.rel_type.value.strip()
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT 1 FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, t_name)) as cur:
                        if not await cur.fetchone():
                            await m_inter.response.send_message(f"❌ 查無對象【{t_name}】！", ephemeral=True)
                            return

                    cp_data = {"target": t_name, "relation": r_type, "affection": 100}
                    await db.execute("""
                        UPDATE characters 
                        SET cp_info = ?, relationship_status = ? 
                        WHERE guild_id = ? AND name = ?
                    """, (json.dumps(cp_data, ensure_ascii=False), f"與 {t_name} 熱戀中", self.guild_id, self.char_name))
                    await db.commit()

                await m_inter.response.send_message(f"💞 成功將 **{self.char_name}** 的 CP 伴侶登記為 **{t_name}**（關係：`{r_type}`，初始羈絆 100）！", ephemeral=True)

        await interaction.response.send_modal(CPModal())

    @discord.ui.button(label="🎨 變更代表色碼", style=discord.ButtonStyle.secondary, row=1)
    async def edit_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        class ColorModal(discord.ui.Modal, title=f"變更【{self.char_name}】的個人面板代表色"):
            hex_color = discord.ui.TextInput(label="16 進位色碼 (例如: #FF69B4 或 0x3498DB)", max_length=10)

            async def on_submit(m_self, m_inter: discord.Interaction):
                val = m_self.hex_color.value.strip()
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("UPDATE characters SET theme_color = ? WHERE guild_id = ? AND name = ?", (val, self.guild_id, self.char_name))
                    await db.commit()
                await m_inter.response.send_message(f"🎨 面板代表色已更新為：`{val}`！", ephemeral=True)

        await interaction.response.send_modal(ColorModal())


# -------------------- 指令：/陣營（查看金庫、捐款威望與解約退出） --------------------
@bot.tree.command(name="陣營", description="查閱所屬陣營資訊、向公款金庫捐款累積威望（10元=1點）或退出陣營")
@app_commands.choices(操作=[
    app_commands.Choice(name="🚩 查看當前陣營詳情", value="info"),
    app_commands.Choice(name="💰 捐款至陣營公款金庫 (10元=1點威望)", value="donate"),
    app_commands.Choice(name="🚪 付違約金退出陣營", value="leave")
])
@app_commands.describe(
    操作="選擇執行的陣營事務",
    角色名="操作的角色全名",
    捐款金額="［捐款專用］自銀行或現金捐出的金額 (純整數)"
)
async def faction_user_cmd(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    角色名: str,
    捐款金額: int = 0
):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    op = 操作.value

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT user_id, faction, cash, bank FROM characters WHERE guild_id = ? AND name = ?
        """, (g_id, c_name)) as cur:
            c_row = await cur.fetchone()

        if not c_row:
            await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
            return

        u_id, faction_name, cash, bank = c_row
        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 你只能為自己的角色處理陣營事務！", ephemeral=True)
            return

        if faction_name == "無" or not faction_name:
            await interaction.response.send_message(f"ℹ️ **{c_name}** 目前尚未加入任何勢力陣營。", ephemeral=True)
            return

        async with db.execute("""
            SELECT desc, tax_rate, exit_fee, treasury FROM factions WHERE guild_id = ? AND name = ?
        """, (g_id, faction_name)) as f_cur:
            f_row = await f_cur.fetchone()

        if not f_row:
            await interaction.response.send_message(f"❌ 陣營【{faction_name}】資料已異常或已解散！", ephemeral=True)
            return

        desc, tax_rate, exit_fee, treasury = f_row

        # 1. 查看陣營詳情
        if op == "info":
            async with db.execute("SELECT contribution FROM faction_members WHERE guild_id = ? AND faction_name = ? AND char_name = ?", (g_id, faction_name, c_name)) as m_cur:
                m_row = await m_cur.fetchone()
            my_contrib = m_row[0] if m_row else 0

            embed = discord.Embed(title=f"🚩 陣營勢力樞紐 — 【{faction_name}】", color=0xE74C3C)
            embed.description = (
                f"*{desc}*\n\n"
                f"• 💰 陣營金庫公款：**${treasury:,}**（總威望 `{treasury//10:,}` 點）\n"
                f"• 📈 通告抽稅比例：`{int(tax_rate*100)}%`\n"
                f"• 🚪 解約違約保證金：`${exit_fee:,}`\n\n"
                f"👤 **【個人在籍貢獻】**\n"
                f"• 累計為金庫貢獻：**${my_contrib:,}**（奉獻威望 `{my_contrib//10:,}` 點）"
            )
            embed.set_footer(text="可使用 /陣營排行榜 檢閱全服總榜與內部座次")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 2. 捐款注資陣營金庫
        elif op == "donate":
            if 捐款金額 <= 0:
                await interaction.response.send_message("❌ 捐款金額需大於 0！", ephemeral=True)
                return

            total_money = cash + bank
            if total_money < 捐款金額:
                await interaction.response.send_message(f"❌ 資金不足！名下總資金僅有 **${total_money:,}**。", ephemeral=True)
                return

            if cash >= 捐款金額:
                await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (捐款金額, g_id, c_name))
            else:
                rem = 捐款金額 - cash
                await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (rem, g_id, c_name))

            await db.execute("UPDATE factions SET treasury = treasury + ? WHERE guild_id = ? AND name = ?", (捐款金額, g_id, faction_name))
            await db.execute("""
                INSERT INTO faction_members (guild_id, faction_name, char_name, contribution)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, faction_name, char_name) DO UPDATE SET contribution = contribution + ?
            """, (g_id, faction_name, c_name, 捐款金額, 捐款金額))
            await db.commit()

            gained_prestige = 捐款金額 // 10
            await interaction.response.send_message(
                f"💎 **{c_name}** 向陣營【**{faction_name}**】公款金庫捐獻 **${捐款金額:,}**！\n"
                f"陣營總威望增加 **+{gained_prestige:,}** 點，個人貢獻度同步累計！"
            )
            return

        # 3. 退出陣營
        elif op == "leave":
            total_money = cash + bank
            if total_money < exit_fee:
                await interaction.response.send_message(f"❌ 解約違約金不足！退出【{faction_name}】需支付違約金 **${exit_fee:,}**！", ephemeral=True)
                return

            if cash >= exit_fee:
                await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (exit_fee, g_id, c_name))
            else:
                rem = exit_fee - cash
                await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (rem, g_id, c_name))

            await db.execute("UPDATE factions SET treasury = treasury + ? WHERE guild_id = ? AND name = ?", (exit_fee, g_id, faction_name))
            await db.execute("UPDATE characters SET faction = '無' WHERE guild_id = ? AND name = ?", (g_id, c_name))
            await db.execute("DELETE FROM faction_members WHERE guild_id = ? AND faction_name = ? AND char_name = ?", (g_id, faction_name, c_name))
            await db.commit()

            await interaction.response.send_message(
                f"🚪 **{c_name}** 已繳付違約金 **${exit_fee:,}**，正式退出陣營【**{faction_name}**】回復自由身！"
            )
            return


# -------------------- 指令：/寵物購買 與 /喪禮結算 --------------------
@bot.tree.command(name="寵物購買", description="為角色認養同伴寵物（初始健康 500/500，依自訂壽命陪伴成長）")
@app_commands.describe(
    角色名="主人角色全名",
    寵物種類="種類 (例如: 柴犬、布偶貓、赤焰玄狐、靈雀)",
    寵物暱稱="寵物的名字",
    壽命年數="陪伴時長 (遊戲年數，預設 15 年，例如: 15)",
    領養花費="認養費用 (純數字，預設 5000)"
)
async def buy_pet_cmd(
    interaction: discord.Interaction,
    角色名: str,
    寵物種類: str,
    寵物暱稱: str,
    壽命年數: int = 15,
    領養花費: int = 5000
):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    p_type = 寵物種類.strip()
    p_name = 寵物暱稱.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()

        if not c_row:
            await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
            return

        u_id, cash, bank = c_row
        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 你只能為自己的角色認養寵物！", ephemeral=True)
            return

        total_funds = cash + bank
        if total_funds < 領養花費:
            await interaction.response.send_message(f"❌ 資金不足！領養需花費 **${領養花費:,}**。", ephemeral=True)
            return

        if cash >= 領養花費:
            await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (領養花費, g_id, c_name))
        else:
            rem = 領養花費 - cash
            await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (rem, g_id, c_name))

        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'days_per_game_year'", (g_id,)) as s_cur:
            s_row = await s_cur.fetchone()
            days_per_year = int(s_row[0]) if s_row else 30

        now_ts = time.time()
        death_ts = now_ts + (壽命年數 * days_per_year * 86400)

        await db.execute("""
            INSERT INTO character_pets (
                guild_id, owner_name, pet_type, pet_name, health, lifespan_years, adopted_at, death_time
            ) VALUES (?, ?, ?, ?, 500, ?, ?, ?)
        """, (g_id, c_name, p_type, p_name, 壽命年數, now_ts, death_ts))
        await db.commit()

    embed = discord.Embed(title="🐾【同伴夥伴認養成功】", color=0x1ABC9C)
    embed.description = (
        f"恭喜 **{c_name}** 迎來了全新夥伴 **{p_name}** ({p_type})！\n\n"
        f"• ❤️ 初始健康度：**500 / 500**（日常可使用飼料照料）\n"
        f"• ⏳ 陪伴壽命：**{壽命年數} 遊戲年**\n"
        f"隨時可透過 `/查看` 點擊【🐾 夥伴寵物】調閱健康動態！"
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="喪禮結算", description="為壽終已故的寵物撰寫悼詞貼文並辦理喪禮結算（獲頒專屬歷練與治癒撫慰）")
@app_commands.describe(
    角色名="主人角色全名",
    寵物暱稱="已故寵物名字",
    悼念貼文訊息連結="已在頻道或討論串發布的悼念貼文網址"
)
async def pet_funeral_cmd(interaction: discord.Interaction, 角色名: str, 寵物暱稱: str, 悼念貼文訊息連結: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    p_name = 寵物暱稱.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id, pet_type, is_dead, funeral_done 
            FROM character_pets 
            WHERE guild_id = ? AND owner_name = ? AND pet_name = ?
        """, (g_id, c_name, p_name)) as cur:
            p_row = await cur.fetchone()

        if not p_row:
            await interaction.response.send_message(f"❌ 查無夥伴【{p_name}】記錄！", ephemeral=True)
            return

        pet_id, p_type, is_dead, funeral_done = p_row
        if is_dead == 0:
            await interaction.response.send_message(f"🐾 夥伴【{p_name}】依然健康陪伴著你，尚未壽終！", ephemeral=True)
            return
        if funeral_done == 1:
            await interaction.response.send_message(f"🕊️ 夥伴【{p_name}】的治喪事宜此前已圓滿完成結算。", ephemeral=True)
            return

        async with db.execute("SELECT works, stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as c_cur:
            c_row = await c_cur.fetchone()
            works = json.loads(c_row[0] or "[]")
            stats = json.loads(c_row[1] or "{}")

        works.append({"category": "成就", "type": "陪伴", "title": f"致最愛的夥伴《{p_name}》", "extra": f"悼念送別({p_type})"})
        stats["路人緣"] = stats.get("路人緣", 0) + 20

        await db.execute("UPDATE character_pets SET funeral_done = 1 WHERE id = ?", (pet_id,))
        await db.execute("""
            UPDATE characters SET works = ?, stats = ? WHERE guild_id = ? AND name = ?
        """, (json.dumps(works, ensure_ascii=False), json.dumps(stats, ensure_ascii=False), g_id, c_name))
        await db.commit()

    embed = discord.Embed(title=f"🕊️ 治喪圓滿・告別守護 — 【{p_name}】", color=0x95A5A6)
    embed.description = (
        f"**{c_name}** 為一生相伴的夥伴 **{p_name}** ({p_type}) 辦理了溫暖的悼念送別。\n\n"
        f"📜 悼念紀錄：[點此檢閱悼念文]({悼念貼文訊息連結.strip()})\n"
        f"• 榮獲履歷收錄：【成就】致最愛的夥伴《{p_name}》\n"
        f"• 感恩撫慰反饋：路人緣 **+20**！"
    )
    await interaction.response.send_message(embed=embed)


# -------------------- 指令：/發布傳聞（累積滿3次自動貼標籤） --------------------
@bot.tree.command(name="發布傳聞", description="【管理員專用】針對特定角色發布坊間傳聞（同關鍵字累積3次自動賦予標籤）")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    角色名="目標角色姓名",
    傳聞內容="坊間八卦流言 (例如: 劇組工作人員爆料其演技精湛實乃劇拋臉)",
    自動關聯特質標籤="選填：若累積滿3次欲自動賦予的標籤名稱 (例如: 劇拋臉、作精、緋聞纏身)"
)
async def post_rumor_cmd(
    interaction: discord.Interaction,
    角色名: str,
    傳聞內容: str,
    自動關聯特質標籤: str = None
):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    r_text = 傳聞內容.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT tags, theme_color FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()

        if not c_row:
            await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
            return

        cur_tags_str, t_color = c_row
        cur_tags = [t.strip() for t in cur_tags_str.split("、") if t.strip()]

        await db.execute("""
            INSERT INTO character_rumors (guild_id, char_name, rumor_text, created_at)
            VALUES (?, ?, ?, ?)
        """, (g_id, c_name, r_text, time.time()))

        tag_granted_msg = ""
        if 自動關聯特質標籤:
            target_tag = 自動關聯特質標籤.strip()
            async with db.execute("""
                SELECT COUNT(*) FROM character_rumors 
                WHERE guild_id = ? AND char_name = ? AND rumor_text LIKE ?
            """, (g_id, c_name, f"%{target_tag}%")) as cnt_cur:
                times = (await cnt_cur.fetchone())[0]

            if times >= 3 and target_tag not in cur_tags:
                new_tags = resolve_tag_conflicts(cur_tags, target_tag)
                await db.execute("UPDATE characters SET tags = ? WHERE guild_id = ? AND name = ?", ("、".join(new_tags), g_id, c_name))
                tag_granted_msg = f"\n🏷️ **【輿論坐實・自動打標】** 相關傳聞已累積滿 3 次，**{c_name}** 已被貼上特質標籤：【`{target_tag}`】！"

        await db.commit()

    embed = discord.Embed(title=f"📢 圈內頭條傳聞 — 【{c_name}】", color=0xE74C3C)
    embed.description = f"「{r_text}」{tag_granted_msg}"
    embed.set_footer(text="可使用 /查看 點擊【📢 坊間傳聞】調閱歷史流言紀錄")

    await broadcast_event(interaction.guild, "penalty", embed)
    await interaction.response.send_message(embed=embed)


# -------------------- 指令：/預約公告發獎 --------------------
@bot.tree.command(name="預約公告發獎", description="【管理員專用】預約在指定時間全自動向全服/陣營發送金錢、道具、屬性並發布公告")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    活動標題="公告大標題 (例如: 端午節盛典福利大放送)",
    公告內容="欲向官方通知大廳發布的公告內文",
    觸發時間="格式: YYYY/M/D HH:MM (例如: 2026/6/5 12:00)",
    銀行獎金="發放至角色的銀行存款 (可填 0)",
    獎勵道具="填寫格式: 物品名*數量 (例如: 避毒丹*2，多個用空格隔開)",
    獎勵屬性="填寫格式: 屬性名+數值 (例如: 流量熱度+50 容貌+5)",
    發送範圍="填寫 all 代表全服；若指定陣營填寫 faction:陣營名",
    目標身分組="選填：僅具備此身分組的角色才可獲得獎勵",
    公告艾特身分組="選填：在通知大廳廣播時艾特的身分組"
)
async def schedule_broadcast_cmd(
    interaction: discord.Interaction,
    活動標題: str,
    公告內容: str,
    觸發時間: str,
    銀行獎金: int = 0,
    獎勵道具: str = "",
    獎勵屬性: str = "",
    發送範圍: str = "all",
    目標身分組: discord.Role = None,
    公告艾特身分組: discord.Role = None
):
    g_id = interaction.guild_id
    t_str = 觸發時間.strip()

    try:
        dt = datetime.strptime(t_str, "%Y/%m/%d %H:%M")
        trigger_ts = dt.timestamp()
    except Exception:
        await interaction.response.send_message("❌ 時間格式錯誤！請嚴格按照 `YYYY/M/D HH:MM`（例如: `2026/6/5 12:00`）輸入！", ephemeral=True)
        return

    if trigger_ts <= time.time():
        await interaction.response.send_message("❌ 預約觸發時間必須是未來的時間！", ephemeral=True)
        return

    target_role_id = 目標身分組.id if 目標身分組 else 0
    mention_role_id = 公告艾特身分組.id if 公告艾特身分組 else 0

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO scheduled_broadcasts (
                guild_id, title, content, trigger_time, reward_cash, reward_items,
                reward_stats, target_scope, role_id, mention_role_id, executed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            g_id, 活動標題.strip(), 公告內容.strip(), trigger_ts, 銀行獎金,
            獎勵道具.strip(), 獎勵屬性.strip(), 發送範圍.strip(), target_role_id, mention_role_id
        ))
        await db.commit()

    embed = discord.Embed(title="⏰ 預約活動排程發布成功", color=0x2ECC71)
    embed.description = (
        f"**活動標題**：【**{活動標題.strip()}**】\n"
        f"• 預定執行時間：`{t_str}`\n"
        f"• 發放範圍：`{發送範圍.strip()}`\n"
        f"• 銀行福利：**+${銀行獎金:,}**\n"
        f"• 贈送物品：`{獎勵道具.strip() or '無'}`\n"
        f"• 屬性增益：`{獎勵屬性.strip() or '無'}`\n\n"
        f"系統將在設定時間全自動批次發放福利至角色帳戶，並在通知頻道發布全服公告！"
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# -------------------- 指令：/審核通過（初審與二審全自動核發） --------------------
@bot.tree.command(name="審核通過", description="【管理員專用】兩段式審核：初審引導對話打勾、二審按年齡/資歷秘密發放初始金幣與解鎖身分")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    審核角色名="人設討論串對應的角色全名",
    給予身分組="二審通過時解鎖賦予的正式玩家身分組",
    審核備註="選填：管理員審查評語或補充指引"
)
async def audit_pass_cmd(
    interaction: discord.Interaction,
    審核角色名: str,
    給予身分組: discord.Role = None,
    審核備註: str = "檔案格式規範健全，核准進入世界觀！"
):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message("⚠️ 此指令必須在人設討論串（Thread）中執行！", ephemeral=True)
        return

    g_id = interaction.guild_id
    th_id = interaction.channel_id
    c_name = 審核角色名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT audit_count FROM profile_audits WHERE guild_id = ? AND thread_id = ?", (g_id, th_id)) as cur:
            audit_row = await cur.fetchone()

        current_count = audit_row[0] if audit_row else 0
        new_count = current_count + 1

        if new_count == 1:
            # 一審通過：初審引導打勾
            await db.execute("""
                INSERT INTO profile_audits (guild_id, thread_id, char_name, audit_count, status)
                VALUES (?, ?, ?, 1, '初審通過')
                ON CONFLICT(guild_id, thread_id) DO UPDATE SET audit_count = 1, status = '初審通過'
            """, (g_id, th_id, c_name))
            await db.commit()

            embed = discord.Embed(title=f"✅【初審通過】— 角色【{c_name}】", color=0x3498DB)
            embed.description = (
                f"審核管理員：{interaction.user.mention}\n"
                f"• 審查意見：`{審核備註}`\n\n"
                f"📋 **【初審指引與注意事項】**\n"
                f"1. 請創作者確認身材數值、國籍、職業與特質標籤是否合乎世界觀設定。\n"
                f"2. 檔案格式已基本達標，已標記初審打勾 ✔️！\n"
                f"3. 請等候二審管理員覆核，完成二審後將自動發放初始啟動金與身分組！"
            )
            await interaction.response.send_message(embed=embed)
            return

        elif new_count >= 2:
            # 二審通過：按公式核發初始資金與身分組
            async with db.execute("SELECT user_id, age, debut_years FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as c_cur:
                c_data = await c_cur.fetchone()

            if not c_data:
                await interaction.response.send_message(f"❌ 查無角色檔案【{c_name}】！請先確認其已完成 `/檔案建立`。", ephemeral=True)
                return

            u_id, age, debut_y = c_data
            d_years = debut_y or 0

            # 初始啟動資金換算公式：基礎 20,000 + (年齡 * 500) + (資歷 * 5,000)
            initial_grant = 20000 + (age * 500) + (d_years * 5000)

            await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (initial_grant, g_id, c_name))
            await db.execute("""
                INSERT INTO profile_audits (guild_id, thread_id, char_name, audit_count, status)
                VALUES (?, ?, ?, 2, '正式通過')
                ON CONFLICT(guild_id, thread_id) DO UPDATE SET audit_count = 2, status = '正式通過'
            """, (g_id, th_id, c_name))
            await db.commit()

            role_msg = ""
            if 給予身分組:
                member = interaction.guild.get_member(u_id)
                if member:
                    try:
                        await member.add_roles(給予身分組, reason=f"人設單【{c_name}】二審正式通過解鎖")
                        role_msg = f"\n🎖️ 已自動解鎖正式身分組：{給予身分組.mention}！"
                    except Exception:
                        pass

            embed = discord.Embed(title=f"🎉🏆【二審終審通過・正式入駐】— 【{c_name}】", color=0x2ECC71)
            embed.description = (
                f"審核管理員：{interaction.user.mention}\n"
                f"創作者：<@{u_id}>\n"
                f"• 評語：`{審核備註}`\n\n"
                f"💰 **【初始資源與啟動金核發】**\n"
                f"• 依據年齡 ({age}歲) 與資歷 ({d_years}年) 計算：\n"
                f"• 系統已自動將 **+${initial_grant:,}** 存入 **{c_name}** 的銀行帳戶！{role_msg}\n\n"
                f"🌟 人設單已正式收錄入庫，祝在世界觀中歷練愉快！"
            )
            await interaction.response.send_message(embed=embed)
            return

# -------------------- 【資產系統】完整模組 --------------------
class JoinCompanyApprovalView(discord.ui.View):
    def __init__(self, comp_id: int, applicant_char: str, applicant_uid: int, owner_uid: int):
        super().__init__(timeout=86400)
        self.comp_id = comp_id
        self.applicant_char = applicant_char
        self.applicant_uid = applicant_uid
        self.owner_uid = owner_uid

    @discord.ui.button(label="✅ 同意加入", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_uid and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 只有該公司的登記負責人或管理員才能審核！", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name FROM companies WHERE id = ?", (self.comp_id,)) as cur:
                c_row = await cur.fetchone()
            comp_name = c_row[0] if c_row else "公司"

            await db.execute("""
                UPDATE characters 
                SET company_id = ?, affiliation_type = '旗下成員', affiliation_name = ?
                WHERE guild_id = ? AND name = ?
            """, (self.comp_id, comp_name, interaction.guild_id, self.applicant_char))
            await db.commit()

        self.stop()
        await interaction.response.edit_message(content=f"🎉 **【審核通過】** 負責人已同意 **{self.applicant_char}** (<@{self.applicant_uid}>) 正式加入【**{comp_name}**】！", view=None)

    @discord.ui.button(label="❌ 婉拒申請", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_uid and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 只有該公司的登記負責人或管理員才能審核！", ephemeral=True)
            return

        self.stop()
        await interaction.response.edit_message(content=f"🚫 負責人已婉拒 **{self.applicant_char}** 加入該公司的申請。", view=None)

class BuyAssetSelect(discord.ui.Select):
    def __init__(self, char_name: str, guild_id: int, assets: list):
        self.char_name = char_name
        self.guild_id = guild_id
        self.assets_map = {str(a[0]): a for a in assets}
        opts = [
            discord.SelectOption(
                label=f"{a[2]} ({a[1]}) - ${a[3]:,}",
                value=str(a[0]),
                description=a[4][:40] if a[4] else "官方認證產權"
            ) for a in assets[:25]
        ]
        super().__init__(placeholder="請選擇欲購買的房產或車輛...", options=opts)

    async def callback(self, interaction: discord.Interaction):
        item_id = self.values[0]
        _, a_type, a_name, price, desc = self.assets_map[item_id]

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT cash, bank FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                cash, bank = await cur.fetchone()

            if cash + bank < price:
                await interaction.response.send_message(f"❌ 資金不足！購買【{a_name}】需要 **${price:,}**，當前名下資金僅有 **${cash+bank:,}**！", ephemeral=True)
                return

            if cash >= price:
                await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (price, self.guild_id, self.char_name))
            else:
                rem = price - cash
                await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (rem, self.guild_id, self.char_name))

            await db.execute("""
                INSERT INTO personal_assets (guild_id, owner_name, asset_type, asset_name, price, details)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (self.guild_id, self.char_name, a_type, a_name, price, desc))
            await db.commit()

        await interaction.response.send_message(f"🎉 購買成功！**{self.char_name}** 順利購入【{a_type}】**{a_name}**（已計入個人產權與財富榜）！")

class AssetHubView(discord.ui.View):
    def __init__(self, char_name: str, guild_id: int):
        super().__init__(timeout=180)
        self.char_name = char_name
        self.guild_id = guild_id

    @discord.ui.button(label="🚗 購買車子/房產", style=discord.ButtonStyle.primary, row=0)
    async def buy_asset_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT id, asset_type, asset_name, price, description FROM available_assets WHERE guild_id = ?", (self.guild_id,)) as cur:
                assets = await cur.fetchall()

        if not assets:
            await interaction.response.send_message("🏢 目前市場上暫無在售的固定資產。管理員可使用 `/資產系統更新` 上架！", ephemeral=True)
            return

        sub_view = discord.ui.View(timeout=120)
        sub_view.add_item(BuyAssetSelect(self.char_name, self.guild_id, assets))
        await interaction.response.send_message("請挑選欲購置的名車或房產物業：", view=sub_view, ephemeral=True)

    @discord.ui.button(label="🏢 申請加入公司", style=discord.ButtonStyle.success, row=0)
    async def join_company_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT id, name, creator_name FROM companies WHERE guild_id = ?", (self.guild_id,)) as cur:
                comps = await cur.fetchall()

        if not comps:
            await interaction.response.send_message("ℹ️ 目前伺服器暫無已註冊的公司。", ephemeral=True)
            return

        class CompanyPickSelect(discord.ui.Select):
            def __init__(s_self):
                opts = [discord.SelectOption(label=c[1], value=str(c[0]), description=f"負責人: {c[2]}") for c in comps[:25]]
                super().__init__(placeholder="請選擇欲申請加入的公司...", options=opts)

            async def callback(s_self, s_inter: discord.Interaction):
                comp_id = int(s_self.values[0])
                chosen_comp = next(c for c in comps if c[0] == comp_id)
                comp_name, owner_char = chosen_comp[1], chosen_comp[2]

                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT user_id FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, owner_char)) as u_cur:
                        u_row = await u_cur.fetchone()

                if not u_row or u_row[0] == 0:
                    await s_inter.response.send_message(f"❌ 無法聯繫該公司的法定登記人【{owner_char}】！", ephemeral=True)
                    return

                owner_uid = u_row[0]
                approval_view = JoinCompanyApprovalView(comp_id, self.char_name, s_inter.user.id, owner_uid)
                await s_inter.channel.send(
                    content=f"🔔 <@{owner_uid}> 登記人請注意！角色 **{self.char_name}** (<@{s_inter.user.id}>) 申請加入您的公司【**{comp_name}**】，請點擊下方按鈕審核：",
                    view=approval_view
                )
                await s_inter.response.send_message(f"✅ 已為您向【{comp_name}】負責人送出加入申請並在頻道艾特通知！", ephemeral=True)

        v = discord.ui.View(timeout=120)
        v.add_item(CompanyPickSelect())
        await interaction.response.send_message("請挑選您欲投奔加入的公司：", view=v, ephemeral=True)

    @discord.ui.button(label="🏷️ 二手出售資產", style=discord.ButtonStyle.secondary, row=1)
    async def sell_asset_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT id, asset_type, asset_name, price FROM personal_assets WHERE guild_id = ? AND owner_name = ?", (self.guild_id, self.char_name)) as cur:
                my_assets = await cur.fetchall()

        if not my_assets:
            await interaction.response.send_message("❌ 您名下目前沒有任何房產或車輛資產可供出售！", ephemeral=True)
            return

        class SellAssetSelect(discord.ui.Select):
            def __init__(s_self):
                opts = [discord.SelectOption(label=f"{a[2]} ({a[1]})", value=str(a[0]), description=f"原價 ${a[3]:,}") for a in my_assets[:25]]
                super().__init__(placeholder="請選擇欲放到二手商城出售的資產...", options=opts)

            async def callback(s_self, s_inter: discord.Interaction):
                chosen_id = int(s_self.values[0])
                asset_obj = next(a for a in my_assets if a[0] == chosen_id)
                a_id, a_type, a_name, a_price = asset_obj

                class AssetPriceModal(discord.ui.Modal, title=f"二手出售【{a_name}】"):
                    sale_price = discord.ui.TextInput(label="二手標價 (純整數)", default=str(int(a_price * 0.8)))

                    async def on_submit(m_self, m_inter: discord.Interaction):
                        try:
                            final_p = int(m_self.sale_price.value.strip())
                            if final_p <= 0: raise ValueError
                        except ValueError:
                            await m_inter.response.send_message("❌ 請輸入有效的售價！", ephemeral=True)
                            return

                        async with aiosqlite.connect(DB_PATH) as db:
                            await db.execute("DELETE FROM personal_assets WHERE id = ?", (a_id,))
                            await db.execute("""
                                INSERT INTO shop_items (guild_id, shop_name, name, price, description, seller, usable)
                                VALUES (?, '二手', ?, ?, ?, ?, 0)
                            """, (s_self.view.guild_id, a_name, final_p, f"二手【{a_type}】轉讓出售", s_self.view.char_name))
                            await db.commit()

                        await m_inter.response.send_message(f"🏷️ 成功將【{a_name}】以 **${final_p:,}** 上架至二手商城！")

                await s_inter.response.send_modal(AssetPriceModal())

        v = discord.ui.View(timeout=120)
        v.char_name = self.char_name
        v.guild_id = self.guild_id
        v.add_item(SellAssetSelect())
        await interaction.response.send_message("請選擇欲轉賣的固定資產：", view=v, ephemeral=True)


@bot.tree.command(name="資產系統", description="購買車輛/房產、賣出二手資產、申請加入或創建公司（計入財富榜）")
@app_commands.choices(操作=[
    app_commands.Choice(name="🏢 開啟資產大廳 (買房買車/加入公司/轉賣二手)", value="hub"),
    app_commands.Choice(name="👑 創立新公司 (自動驗證總資產與剩餘儲備金)", value="create_comp")
])
@app_commands.choices(公司體制=[
    app_commands.Choice(name="有限公司 (1人即可，最低出資 10 萬)", value="limited"),
    app_commands.Choice(name="股份有限公司 (2人以上，每人最低出資 5 萬)", value="joint_stock")
])
@app_commands.describe(
    操作="選擇開啟資產總覽或直接建立公司",
    角色名="操作的角色全名",
    公司體制="［創立公司］選擇有限或股份有限公司",
    公司名稱="［創立公司］企業全稱",
    經營用途="［創立公司］業務方向與宗旨",
    出資額="［創立公司］你的角色出資金額",
    合作投資人角色="［創立公司］股份有限公司必填：合夥人角色名，多個用空格隔開",
    艾特合作投資人="［創立公司］股份有限公司必填：艾特合夥投資人的 Discord 帳號"
)
async def asset_system_cmd(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    角色名: str,
    公司體制: app_commands.Choice[str] = None,
    公司名稱: str = None,
    經營用途: str = "綜合娛樂與影視演藝經紀",
    出資額: int = 100000,
    合作投資人角色: str = "",
    艾特合作投資人: discord.Member = None
):
    g_id = interaction.guild_id
    c_name = 角色名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()

    if not c_row:
        await interaction.response.send_message(f"❌ 查無角色檔案【{c_name}】！", ephemeral=True)
        return

    u_id, cash, bank = c_row
    if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 你只能為自己的角色操作資產系統！", ephemeral=True)
        return

    # 1. 開啟資產大廳
    if 操作.value == "hub":
        embed = discord.Embed(title=f"🚗 房產、名車與企業資產中心 — 【{c_name}】", color=0x34495E)
        embed.description = (
            f"持有者：**{c_name}** (<@{u_id}>)\n"
            f"• 手頭現金：`${cash:,}` ｜ 銀行存款：`${bank:,}`\n"
            f"• 總流動資本：**${cash+bank:,}**（已全數納入財富排行榜）\n\n"
            f"請點擊下方按鈕購買車房、申請加入企業或將名下產權轉賣二手："
        )
        await interaction.response.send_message(embed=embed, view=AssetHubView(c_name, g_id), ephemeral=True)
        return

    # 2. 創立公司（嚴格檢驗最低出資與剩餘1/2儲備金規則）
    elif 操作.value == "create_comp":
        if not 公司名稱 or not 公司體制:
            await interaction.response.send_message("❌ 創立公司時，必須填寫【公司名稱】與【公司體制】！", ephemeral=True)
            return

        comp_name = 公司名稱.strip()
        structure_label = "有限公司" if 公司體制.value == "limited" else "股份有限公司"

        # 檢驗重名
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM companies WHERE guild_id = ? AND name = ?", (g_id, comp_name)) as cur:
                if await cur.fetchone():
                    await interaction.response.send_message(f"❌ 公司名稱【{comp_name}】已被註冊！", ephemeral=True)
                    return

        # 門檻檢查：有限公司最低 10 萬；股份制每人最低 5 萬
        min_req = 100000 if 公司體制.value == "limited" else 50000
        if 出資額 < min_req:
            await interaction.response.send_message(f"❌ 出資金額不符法規！【{structure_label}】創辦最低出資額為 **${min_req:,}**！", ephemeral=True)
            return

        # 關鍵驗證規則：總資產扣除投資金額後，剩餘的錢必須大於或等於投資金額的 1/2
        my_total = cash + bank
        my_remaining = my_total - 出資額
        required_reserve = 出資額 / 2.0

        if my_remaining < required_reserve:
            await interaction.response.send_message(
                f"🚫 **【資產健康度不足・無法立案】**\n"
                f"商業法規規定：角色總資產在扣除投資額後，**剩餘儲備金必須至少為投資額的 1/2（需留 ${int(required_reserve):,}）**！\n"
                f"• 你目前總資產：`${my_total:,}`\n"
                f"• 預定出資額：`${出資額:,}`\n"
                f"• 扣除後僅剩：`${my_remaining:,}`（低於法定保底要求的 ${int(required_reserve):,}）！",
                ephemeral=True
            )
            return

        partners_list = []
        mention_note = ""

        # 股份有限公司多人合資檢驗
        if 公司體制.value == "joint_stock":
            if not 合作投資人角色 or not 艾特合作投資人:
                await interaction.response.send_message("❌ 創立【股份有限公司】必須填寫【合作投資人角色】並【艾特合作投資人】！", ephemeral=True)
                return

            partner_char = 合作投資人角色.strip()
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT user_id, cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, partner_char)) as p_cur:
                    p_row = await p_cur.fetchone()

            if not p_row:
                await interaction.response.send_message(f"❌ 查無合作投資人角色【{partner_char}】！", ephemeral=True)
                return

            p_uid, p_cash, p_bank = p_row
            p_total = p_cash + p_bank
            p_invest = 出資額  # 預設對等出資或每人最少 5 萬
            p_remain = p_total - p_invest
            p_req = p_invest / 2.0

            if p_remain < p_req:
                await interaction.response.send_message(
                    f"🚫 **【合作投資人資產不足】** 合夥角色 **{partner_char}** 總資產在扣除投資後，剩餘資金不足出資額的 1/2（需剩餘 ${int(p_req):,}）！",
                    ephemeral=True
                )
                return

            # 扣除合夥人資金
            async with aiosqlite.connect(DB_PATH) as db:
                if p_cash >= p_invest:
                    await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (p_invest, g_id, partner_char))
                else:
                    r_p = p_invest - p_cash
                    await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (r_p, g_id, partner_char))
                await db.commit()

            partners_list.append(partner_char)
            mention_note = f"\n🤝 合夥股東：**{partner_char}** ({艾特合作投資人.mention}) 出資 **${p_invest:,}**"

        # 扣除發起人資金
        async with aiosqlite.connect(DB_PATH) as db:
            if cash >= 出資額:
                await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (出資額, g_id, c_name))
            else:
                rem = 出資額 - cash
                await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (rem, g_id, c_name))

            total_capital = 出資額 * (2 if 公司體制.value == "joint_stock" else 1)

            await db.execute("""
                INSERT INTO companies (
                    guild_id, name, purpose, type_name, structure, creator_name,
                    partners, total_capital, split_ratio, balance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0.2, ?)
            """, (
                g_id, comp_name, 經營用途.strip(), "影視經紀", structure_label,
                c_name, json.dumps(partners_list, ensure_ascii=False), total_capital, total_capital
            ))

            async with db.execute("SELECT id FROM companies WHERE guild_id = ? AND name = ?", (g_id, comp_name)) as id_cur:
                new_c_id = (await id_cur.fetchone())[0]

            await db.execute("""
                UPDATE characters 
                SET company_id = ?, affiliation_type = '名下企業', affiliation_name = ?
                WHERE guild_id = ? AND name = ?
            """, (new_c_id, comp_name, g_id, c_name))
            await db.commit()

        embed = discord.Embed(title=f"🏢【企業核准立案】— {comp_name}", color=0xF1C40F)
        embed.description = (
            f"經商業管理機構嚴格審核，企業資本適足率合規，正式掛牌！\n\n"
            f"• 企業體制：**{structure_label}**\n"
            f"• 法人創辦：**{c_name}** (<@{u_id}>) 出資 **${出資額:,}**\n"
            f"• 營運金庫初資：**${total_capital:,}**\n"
            f"• 經營業務：`{經營用途.strip()}`{mention_note}\n\n"
            f"全服角色可使用 `/資產系統` 申請投奔加入旗下面板！"
        )
        await broadcast_event(interaction.guild, "holiday", embed)
        await interaction.response.send_message(embed=embed)


# -------------------- 指令：/資產系統更新 --------------------
@bot.tree.command(name="資產系統更新", description="【管理員專用】上架全新的可購置房產或豪車座駕")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(資產類型=[
    app_commands.Choice(name="豪宅房產 (頂層公寓/別墅/莊園)", value="房產"),
    app_commands.Choice(name="名車座駕 (跑車/保母車/直升機)", value="座駕")
])
@app_commands.describe(
    資產類型="選擇物業或車輛",
    資產名稱="資產名稱 (例如: 湯臣一品頂層複式、勞斯萊斯幻影)",
    售價="定價金額 (純整數)",
    特色介紹="物業亮點或車輛性能介紹"
)
async def update_asset_catalog_cmd(
    interaction: discord.Interaction,
    資產類型: app_commands.Choice[str],
    資產名稱: str,
    售價: int,
    特色介紹: str = "極致奢華尊榮象徵"
):
    g_id = interaction.guild_id
    a_name = 資產名稱.strip()
    a_type = 資產類型.value

    if 售價 <= 0:
        await interaction.response.send_message("❌ 售價必須大於 0！", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO available_assets (guild_id, asset_type, asset_name, price, description)
            VALUES (?, ?, ?, ?, ?)
        """, (g_id, a_type, a_name, 售價, 特色介紹.strip()))
        await db.commit()

    await interaction.response.send_message(
        f"✅ 成功將【{a_type}】**{a_name}**（售價 **${售價:,}**）錄入資產庫！玩家與 NPC 現已可於 `/資產系統` 購置。",
        ephemeral=True
    )


# -------------------- 【陣營系統】完整九大功能模組 --------------------
@bot.tree.command(name="陣營", description="陣營事務：新增、捐獻、金主、查看領週禮包、買商城、退陣營、加入、全體加成")
@app_commands.choices(操作=[
    app_commands.Choice(name="① 新增 (僅管理員：設名稱/比例/前五名獎/內部商城)", value="admin_create"),
    app_commands.Choice(name="② 捐獻 (扣款進陣營金庫)", value="donate"),
    app_commands.Choice(name="③ 金主降臨 (系統注資公款)", value="sponsor"),
    app_commands.Choice(name="④ 查看 (經費/名單/排名/順便領取每週禮包)", value="view_hub"),
    app_commands.Choice(name="⑤ 購買 (購買內部商城品更新背包/數值)", value="shop"),
    app_commands.Choice(name="⑥ 退出 (強制扣除退出費用解除歸屬)", value="leave"),
    app_commands.Choice(name="⑦ 加入 (選擇角色加入新陣營)", value="join"),
    app_commands.Choice(name="⑧ 經費對抗全體加成 (內部排行前二名負責人專屬)", value="buff_all")
])
@app_commands.describe(
    操作="選擇執行的陣營事務",
    角色名="操作的角色全名",
    陣營名稱="目標陣營名稱",
    金額="捐獻/金主/違約金等數值",
    抽成比例="［新增專用］任務公款抽稅百分比 (例如: 10 代表 10%)",
    退出費用="［新增專用］脫離需賠付之違約金",
    每週禮包金錢="［新增專用］每週查看可領取之金錢",
    前五名獎勵設定="［新增專用］如: 第1名+10000 第2名+5000",
    內部商城物品設定="［新增專用］格式: 靈芝*5000*容貌+5 (名稱*價格*效果)",
    全體加成花費="［全體加成］消耗陣營經費金額 (需正副負責人)",
    全體加成屬性="［全體加成］全體成員同享之屬性 (如: 流量熱度+30 商業價值+20)"
)
async def faction_master_cmd(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    角色名: str = None,
    陣營名稱: str = None,
    金額: int = 0,
    抽成比例: float = 10.0,
    退出費用: int = 5000,
    每週禮包金錢: int = 1000,
    前五名獎勵設定: str = "",
    內部商城物品設定: str = "",
    全體加成花費: int = 20000,
    全體加成屬性: str = "流量熱度+30"
):
    g_id = interaction.guild_id
    op = 操作.value

    # ① 新增（僅管理員）
    if op == "admin_create":
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 只有管理員可以使用【新增】陣營功能！", ephemeral=True)
            return
        if not 陣營名稱:
            await interaction.response.send_message("❌ 請填寫【陣營名稱】！", ephemeral=True)
            return

        f_name = 陣營名稱.strip()
        tax = max(0.0, min(1.0, 抽成比例 / 100.0))
        gift_data = {"weekly_cash": 每週禮包金錢}

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO factions (
                    guild_id, name, desc, tax_rate, exit_fee, weekly_gift, top_rewards
                ) VALUES (?, ?, '核心勢力陣營', ?, ?, ?, ?)
                ON CONFLICT(guild_id, name) DO UPDATE SET
                    tax_rate = excluded.tax_rate,
                    exit_fee = excluded.exit_fee,
                    weekly_gift = excluded.weekly_gift,
                    top_rewards = excluded.top_rewards
            """, (g_id, f_name, tax, 退出費用, json.dumps(gift_data), 前五名獎勵設定.strip()))

            # 若有內部專屬商城物品，直接注入商城表
            if 內部商城物品設定:
                # 格式：名稱*價格*效果
                for item_token in re.split(r"[,，\s]+", 內部商城物品設定.strip()):
                    parts = item_token.split("*")
                    if len(parts) >= 2:
                        it_n = parts[0].strip()
                        it_p = int(parts[1].strip())
                        it_eff = parts[2].strip() if len(parts) > 2 else ""
                        await db.execute("""
                            INSERT INTO shop_items (guild_id, shop_name, name, price, description, stat_bonus, faction_name)
                            VALUES (?, '陣營內部專區', ?, ?, '陣營專屬物資', ?, ?)
                            ON CONFLICT(guild_id, shop_name, name) DO UPDATE SET price = excluded.price, stat_bonus = excluded.stat_bonus
                        """, (g_id, it_n, it_p, it_eff, f_name))

            await db.commit()

        embed = discord.Embed(title=f"🚩 陣營【{f_name}】創立完畢", color=0xE74C3C)
        embed.description = (
            f"• 任務公款抽稅比例：`{抽成比例}%`\n"
            f"• 退出解約違約金：`${退出費用:,}`\n"
            f"• 每週在籍成員禮包：`${每週禮包金錢:,}`\n"
            + (f"• 前五名專屬獎勵：`{前五名獎勵設定.strip()}`\n" if 前五名獎勵設定 else "")
            + (f"• 內部商城物資已同步上架至陣營專區！\n" if 內部商城物品設定 else "")
        )
        await interaction.response.send_message(embed=embed)
        return

    # 其餘操作需指定角色
    if not 角色名:
        await interaction.response.send_message("❌ 請填寫操作之【角色名】！", ephemeral=True)
        return

    c_name = 角色名.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, faction, cash, bank, stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()

    if not c_row:
        await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
        return

    u_id, my_faction, cash, bank, stats_json = c_row
    if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 你只能代表自己的角色執行陣營操作！", ephemeral=True)
        return

    # ② 捐獻
    if op == "donate":
        if my_faction == "無" or not my_faction:
            await interaction.response.send_message("❌ 該角色尚未加入任何陣營！", ephemeral=True)
            return
        if 金額 <= 0:
            await interaction.response.send_message("❌ 捐款金額需大於 0！", ephemeral=True)
            return
        if cash + bank < 金額:
            await interaction.response.send_message(f"❌ 資金不足！名下總資金僅有 **${cash+bank:,}**。", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            if cash >= 金額:
                await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (金額, g_id, c_name))
            else:
                rem = 金額 - cash
                await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (rem, g_id, c_name))

            await db.execute("UPDATE factions SET treasury = treasury + ? WHERE guild_id = ? AND name = ?", (金額, g_id, my_faction))
            await db.execute("""
                INSERT INTO faction_members (guild_id, faction_name, char_name, contribution)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, faction_name, char_name) DO UPDATE SET contribution = contribution + ?
            """, (g_id, my_faction, c_name, 金額, 金額))
            await db.commit()

        await interaction.response.send_message(f"💎 **{c_name}** 成功向陣營【**{my_faction}**】捐款 **${金額:,}**！總威望增加 **+{金額//10:,}** 點！")
        return

    # ③ 金主降臨（系統/管理員專用注資）
    elif op == "sponsor":
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 只有系統管理員能觸發金主降臨注資！", ephemeral=True)
            return
        target_f = 陣營名稱.strip() if 陣營名稱 else my_faction
        if not target_f or target_f == "無":
            await interaction.response.send_message("❌ 請填寫注資的【陣營名稱】！", ephemeral=True)
            return
        if 金額 <= 0:
            await interaction.response.send_message("❌ 注資金額需大於 0！", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE factions SET treasury = treasury + ? WHERE guild_id = ? AND name = ?", (金額, g_id, target_f))
            await db.commit()

        embed = discord.Embed(title=f"👑 金主降臨：【{target_f}】公款暴漲！", color=0xF1C40F)
        embed.description = f"幕後頂級財團降臨，為【**{target_f}**】無償注資公款 **+${金額:,}**！"
        await broadcast_event(interaction.guild, "holiday", embed)
        await interaction.response.send_message(embed=embed)
        return

    # ④ 查看（經費/成員/內部貢獻排名/順便領取每週禮包）
    elif op == "view_hub":
        target_f = 陣營名稱.strip() if 陣營名稱 else my_faction
        if not target_f or target_f == "無":
            await interaction.response.send_message("❌ 請指定陣營名稱或先加入陣營！", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT treasury, weekly_gift, top_rewards FROM factions WHERE guild_id = ? AND name = ?", (g_id, target_f)) as f_cur:
                f_row = await f_cur.fetchone()

            if not f_row:
                await interaction.response.send_message(f"❌ 查無陣營【{target_f}】！", ephemeral=True)
                return

            treasury, gift_json, top_rew = f_row
            gift_data = json.loads(gift_json or "{}")
            weekly_money = gift_data.get("weekly_cash", 1000)

            # 內部排名
            async with db.execute("""
                SELECT char_name, contribution FROM faction_members 
                WHERE guild_id = ? AND faction_name = ? ORDER BY contribution DESC
            """, (g_id, target_f)) as m_cur:
                members_ranked = await m_cur.fetchall()

            # 領取每週禮包判定（以當週週數計算）
            current_week = int(time.time() // 604800)
            async with db.execute("SELECT last_gift_week FROM faction_members WHERE guild_id = ? AND faction_name = ? AND char_name = ?", (g_id, target_f, c_name)) as g_cur:
                g_row = await g_cur.fetchone()

            gift_claimed_msg = ""
            if g_row and my_faction == target_f:
                last_w = g_row[0] or 0
                if current_week > last_w:
                    await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (weekly_money, g_id, c_name))
                    await db.execute("UPDATE faction_members SET last_gift_week = ? WHERE guild_id = ? AND faction_name = ? AND char_name = ?", (current_week, g_id, target_f, c_name))
                    await db.commit()
                    gift_claimed_msg = f"\n🎁 **【每週例行禮包領取成功】** 銀行入帳 **+${weekly_money:,}**！"
                else:
                    gift_claimed_msg = "\nℹ️ 本週每週例行禮包已領取過，請下週再來！"

        embed = discord.Embed(title=f"🚩 陣營動態大廳 — 【{target_f}】", color=0x9B59B6)
        embed.description = (
            f"• 💰 公款總經費：**${treasury:,}**（威望 `{treasury//10:,}` 點）\n"
            f"• 👥 在籍成員總數：`{len(members_ranked)}` 位{gift_claimed_msg}\n\n"
            f"**🏆【內部成員貢獻排行榜（前 5 名專享）】**\n"
        )
        medals = ["🥇 正負責人", "🥈 副負責人", "🥉 核心元老", "4️⃣ 骨幹成員", "5️⃣ 菁英成員"]
        for idx, (m_char, m_contrib) in enumerate(members_ranked[:5]):
            embed.description += f"{medals[idx]}：**{m_char}** ｜ 累計奉獻 `${m_contrib:,}`\n"

        await interaction.response.send_message(embed=embed)
        return

    # ⑤ 購買內部商城品
    elif op == "shop":
        target_f = 陣營名稱.strip() if 陣營名稱 else my_faction
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT id, name, price, stat_bonus FROM shop_items WHERE guild_id = ? AND faction_name = ?", (g_id, target_f)) as cur:
                f_items = await cur.fetchall()

        if not f_items:
            await interaction.response.send_message(f"🏪 陣營【{target_f}】目前沒有內部商城物品供購買。", ephemeral=True)
            return

        class FactionShopSelect(discord.ui.Select):
            def __init__(s_self):
                opts = [discord.SelectOption(label=f"{it[1]} (${it[2]:,})", value=str(it[0]), description=it[3][:40] if it[3] else "專屬物資") for it in f_items[:25]]
                super().__init__(placeholder="請選擇欲購買的陣營內部物資...", options=opts)

            async def callback(s_self, s_inter: discord.Interaction):
                chosen_id = int(s_self.values[0])
                it = next(x for x in f_items if x[0] == chosen_id)
                i_id, i_name, i_price, i_eff = it

                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT cash, bank, stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as c_cur:
                        c_cash, c_bank, s_json = await c_cur.fetchone()

                    if c_cash + c_bank < i_price:
                        await s_inter.response.send_message(f"❌ 資金不足！需要 **${i_price:,}**！", ephemeral=True)
                        return

                    if c_cash >= i_price:
                        await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (i_price, g_id, c_name))
                    else:
                        rem = i_price - c_cash
                        await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (rem, g_id, c_name))

                    # 增加物品到背包
                    await db.execute("""
                        INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver)
                        VALUES (?, ?, ?, 1, ?)
                    """, (g_id, c_name, i_name, f"陣營內部({target_f})"))

                    # 更新數值
                    c_stats = json.loads(s_json or "{}")
                    if i_eff:
                        for p in re.split(r"[,，\s]+", i_eff):
                            m = re.search(r"([^\d+-]+)([+-]?\d+)", p)
                            if m:
                                k, v = m.group(1).strip(), int(m.group(2))
                                c_stats[k] = max(0, c_stats.get(k, 0) + v)
                        await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(c_stats, ensure_ascii=False), g_id, c_name))

                    await db.commit()

                await s_inter.response.send_message(f"🛒 成功購入【**{i_name}**】！已扣除 **${i_price:,}**，道具已入背包，數值加成已同步生效！")

        v = discord.ui.View(timeout=120)
        v.add_item(FactionShopSelect())
        await interaction.response.send_message("請挑選陣營專屬特供物品：", view=v, ephemeral=True)
        return

    # ⑥ 退出陣營
    elif op == "leave":
        if my_faction == "無" or not my_faction:
            await interaction.response.send_message("❌ 你尚未加入任何陣營，無法退出！", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT exit_fee FROM factions WHERE guild_id = ? AND name = ?", (g_id, my_faction)) as f_cur:
                f_row = await f_cur.fetchone()

            exit_fee = f_row[0] if f_row else 5000
            if cash + bank < exit_fee:
                await interaction.response.send_message(f"❌ 資金不足！脫離【{my_faction}】需扣除退出違約金 **${exit_fee:,}**！", ephemeral=True)
                return

            if cash >= exit_fee:
                await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (exit_fee, g_id, c_name))
            else:
                rem = exit_fee - cash
                await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (rem, g_id, c_name))

            await db.execute("UPDATE factions SET treasury = treasury + ? WHERE guild_id = ? AND name = ?", (exit_fee, g_id, my_faction))
            await db.execute("UPDATE characters SET faction = '無' WHERE guild_id = ? AND name = ?", (g_id, c_name))
            await db.execute("DELETE FROM faction_members WHERE guild_id = ? AND faction_name = ? AND char_name = ?", (g_id, my_faction, c_name))
            await db.commit()

        await interaction.response.send_message(f"🚪 **{c_name}** 支付違約金 **${exit_fee:,}**，已正式脫離陣營【**{my_faction}**】！")
        return

    # ⑦ 加入陣營
    elif op == "join":
        if not 陣營名稱:
            await interaction.response.send_message("❌ 請指定欲加入的【陣營名稱】！", ephemeral=True)
            return

        target_f = 陣營名稱.strip()
        if my_faction != "無" and my_faction:
            await interaction.response.send_message(f"❌ 你當前已有陣營【{my_faction}】！請先選擇【⑥ 退出】繳納違約金後再來加入新陣營。", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM factions WHERE guild_id = ? AND name = ?", (g_id, target_f)) as cur:
                if not await cur.fetchone():
                    await interaction.response.send_message(f"❌ 查無陣營【{target_f}】！", ephemeral=True)
                    return

            await db.execute("UPDATE characters SET faction = ? WHERE guild_id = ? AND name = ?", (target_f, g_id, c_name))
            await db.execute("""
                INSERT INTO faction_members (guild_id, faction_name, char_name, contribution, last_gift_week)
                VALUES (?, ?, ?, 0, ?)
            """, (g_id, target_f, c_name, int(time.time() // 604800)))
            await db.commit()

        await interaction.response.send_message(f"🚩 恭喜！**{c_name}** 正式加入陣營【**{target_f}**】！")
        return

    # ⑧ 經費對抗與全體加成（僅內部排行第 1、第 2 名正副負責人可購買）
    elif op == "buff_all":
        if my_faction == "無" or not my_faction:
            await interaction.response.send_message("❌ 該角色沒有陣營！", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            # 檢查是否為前兩名
            async with db.execute("""
                SELECT char_name FROM faction_members 
                WHERE guild_id = ? AND faction_name = ? ORDER BY contribution DESC LIMIT 2
            """, (g_id, my_faction)) as top_cur:
                top_leaders = [r[0] for r in await top_cur.fetchall()]

            if c_name not in top_leaders and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    f"🚫 **【權限不足】** 經費對抗與全體加成屬於戰略決策，**只有內部排行第一與第二名（正副負責人）** 才能購買！",
                    ephemeral=True
                )
                return

            async with db.execute("SELECT treasury FROM factions WHERE guild_id = ? AND name = ?", (g_id, my_faction)) as cur:
                treasury = (await cur.fetchone())[0]

            if treasury < 全體加成花費:
                await interaction.response.send_message(f"❌ 陣營公款不足！本次全體加成需公款 **${全體加成花費:,}**，當前僅剩 **${treasury:,}**！", ephemeral=True)
                return

            await db.execute("UPDATE factions SET treasury = treasury - ? WHERE guild_id = ? AND name = ?", (全體加成花費, g_id, my_faction))

            # 為所有在籍成員賦予屬性加成
            async with db.execute("SELECT name, stats FROM characters WHERE guild_id = ? AND faction = ?", (g_id, my_faction)) as all_cur:
                all_members = await all_cur.fetchall()

            for m_name, s_json in all_members:
                m_stats = json.loads(s_json or "{}")
                for p in re.split(r"[,，\s]+", 全體加成屬性.strip()):
                    m = re.search(r"([^\d+-]+)([+-]?\d+)", p)
                    if m:
                        k, v = m.group(1).strip(), int(m.group(2))
                        m_stats[k] = max(0, m_stats.get(k, 0) + v)
                await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(m_stats, ensure_ascii=False), g_id, m_name))

            await db.commit()

        embed = discord.Embed(title=f"⚔️ 陣營戰略全體加成發動！— 【{my_faction}】", color=0x2ECC71)
        embed.description = (
            f"負責人 **{c_name}** 動用陣營公款經費 **${全體加成花費:,}**，啟動陣營全體戰略激勵！\n\n"
            f"• 獲得全體加成效果：`{全體加成屬性.strip()}`\n"
            f"• 受益成員人數：共計 `{len(all_members)}` 位在籍成員同享加成！"
        )
        await broadcast_event(interaction.guild, "holiday", embed)
        await interaction.response.send_message(embed=embed)
        return

# -------------------- 系統就緒啟動中樞與定時排程掛載 --------------------
@bot.event
async def on_ready():
    # 初始化資料庫所有資料表
    await init_db()
    await extend_database_tables()
    await init_auction_table()
    await init_leaderboard_tables()

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
