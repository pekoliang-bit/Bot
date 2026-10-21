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
    return "Bot is running perfectly!"

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

# -------------------- 標籤詞庫與年齡性別適配 --------------------
UNIVERSAL_TAGS = [
    "初戀臉", "厭世感", "舞台匠人", "釣系", "全能天才", "天籟蜜嗓", 
    "極致反差", "低音砲", "古典氣質", "漫撕人", "高嶺之花", "元氣犬系",
    "性感", "緋聞纏身", "濃顏", "淡顏", "臉蛋天才", "社恐", "社交悍匪", 
    "人間清醒", "毒舌", "劇拋臉", "鬆弛感", "文盲", "花瓶"
]

GENDER_AGE_TAGS = {
    "少年感": lambda age, gen: gen == "男" and age <= 25,
    "老幹部": lambda age, gen: age >= 30,
    "百億少年的夢": lambda age, gen: gen == "女" and age <= 30,
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
    "文盲": ["人間清醒", "才智過人"],
    "花瓶": ["劇拋臉", "舞台匠人", "全能天才"],
    "劇拋臉": ["花瓶"],
    "老幹部": ["少年感", "元氣犬系"],
    "少年感": ["老幹部"]
}

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
        warn_text = f"⚠️ BMI 嚴重偏低（{bmi}，身材過瘦），初始健康值 -20、容貌 -15。"
    elif bmi > 28.0:
        health_penalty, app_penalty = 20, 15
        warn_text = f"⚠️ BMI 嚴重偏高（{bmi}，體態超標），初始健康值 -20、容貌 -15。"
    return max(10, base_health - health_penalty), max(10, base_appearance - app_penalty), bmi, warn_text
# -------------------- 人設單文字爬蟲解析器 --------------------
def parse_character_sheet(content: str) -> dict:
    data = {}
    name_m = re.search(r"本名[／/]?藝名[：:]\s*([^\n\r]+)", content)
    if name_m:
        raw_name = name_m.group(1).strip()
        parts = re.split(r"[／/]", raw_name)
        data["name"] = parts[0].strip()
        data["stage_name"] = parts[1].strip() if len(parts) > 1 else parts[0].strip()

    aff_m = re.search(r"歸屬[^\n\r:：]*[:：]\s*([^\n\r]+)", content)
    if aff_m: data["affiliation_type"] = aff_m.group(1).strip()
    aff_n_m = re.search(r"具體歸屬名稱[／/]?搭檔名[：:]\s*([^\n\r]+)", content)
    if aff_n_m: data["affiliation_name"] = aff_n_m.group(1).strip()

    job_m = re.search(r"職業[：:]\s*([^\n\r]+)", content)
    if job_m: data["job"] = job_m.group(1).strip()
    age_m = re.search(r"年齡[：:]\s*(\d+)", content)
    if age_m: data["age"] = max(18, min(40, int(age_m.group(1))))

    sex_m = re.search(r"性別[／/]?性向[：:]\s*([^\n\r]+)", content)
    if sex_m:
        parts = re.split(r"[／/\s]+", sex_m.group(1).strip())
        data["gender"] = parts[0].strip() if parts else "女"
        data["orientation"] = parts[1].strip() if len(parts) > 1 else "保密"

    nat_m = re.search(r"國籍[：:]\s*([^\n\r]+)", content)
    if nat_m: data["nationality"] = re.split(r"[，,\s（(]", nat_m.group(1).strip())[0].strip()

    edu_m = re.search(r"學歷[：:]\s*([^\n\r]+)", content)
    if edu_m: data["education"] = edu_m.group(1).strip()

    rel_m = re.search(r"情感[：:]\s*([^\n\r]+)", content)
    if rel_m: data["relationship_status"] = rel_m.group(1).strip()

    hw_m = re.search(r"身高[／/]?體重[：:]\s*([^\n\r]+)", content)
    if hw_m:
        nums = re.findall(r"\d+", hw_m.group(1))
        if len(nums) >= 2:
            data["height"] = int(nums[0])
            data["weight"] = int(nums[1])

    track_m = re.search(r"主攻賽道[^\n\r:：]*[:：]\s*([^\n\r]+)", content)
    if track_m:
        for vt in ["唱跳", "演繹", "主持", "歌唱", "綜藝"]:
            if vt in track_m.group(1):
                data["primary_track"] = vt
                break

    tag_m = re.search(r"標籤[：:]\s*([^\n\r]+)", content)
    if tag_m:
        data["tags"] = "、".join([t for t in re.split(r"[,，、\s]+", tag_m.group(1).strip()) if t][:2])

    stat_keys = ["容貌", "才智", "流量熱度", "商業價值", "路人緣", "公關", "影響指數", "個人才藝"]
    st = {}
    for sk in stat_keys:
        sk_m = re.search(rf"{sk}[^\d\n\r]*(\d+)", content)
        st[sk] = int(sk_m.group(1)) if sk_m else 50
    st["死忠粉絲數"] = 0
    st["活躍黑粉數"] = 0
    st["大眾認知度"] = 0
    data["stats"] = st
    return data

# -------------------- 演藝生態核心判定機制 --------------------
def calculate_monthly_quota(traffic: int) -> int:
    return max(15, 15 + (traffic // 100))

def get_commercial_multiplier(commercial_val: int) -> tuple[float, bool]:
    multiplier = 1.0 + (commercial_val / 2000.0)
    ignore_req = commercial_val >= 2500
    return multiplier, ignore_req

def get_pr_cost(pr_val: int, base_cost: int = 50000) -> int:
    if pr_val >= 80:
        return int(base_cost * 0.5)
    elif pr_val < 40:
        return int(base_cost * 2.0)
    return base_cost

def check_backstab_detection(intellect: int) -> bool:
    detect_rate = min(0.90, (intellect * 0.008))
    return random.random() < detect_rate

async def check_and_update_rank(guild_id: int, char_name: str, channel=None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT stats, works, rank FROM characters WHERE guild_id = ? AND name = ?", (guild_id, char_name)) as cur:
            row = await cur.fetchone()
        if not row:
            return
        stats_json, works_json, current_rank = row
        stats = json.loads(stats_json) if stats_json else {}

        async with db.execute("SELECT rank_order, rank_name, work_req, endorse_req, stat_req, max_slots FROM rank_settings WHERE guild_id = ? ORDER BY rank_order ASC", (guild_id,)) as cur:
            ranks = await cur.fetchall()

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
                if channel:
                    try:
                        await channel.send(f"👑✨ **【星光加冕】** 恭喜 **{char_name}** 晉升至全新地位：**【{r_name}】**！")
                    except Exception:
                        pass
                break

async def process_faction_tax(guild_id: int, char_name: str, work_title: str, reward_cash: int, channel=None) -> str:
    if reward_cash <= 0:
        return ""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT faction FROM characters WHERE guild_id = ? AND name = ?", (guild_id, char_name)) as cur:
            row = await cur.fetchone()
        if not row or row[0] == "無":
            return ""
        f_name = row[0]

        async with db.execute("SELECT 1 FROM work_tax_logs WHERE guild_id = ? AND char_name = ? AND work_title = ?", (guild_id, char_name, work_title)) as cur:
            if await cur.fetchone():
                return ""

        async with db.execute("SELECT tax_rate FROM factions WHERE guild_id = ? AND name = ?", (guild_id, f_name)) as cur:
            f_row = await cur.fetchone()
            tax_rate = f_row[0] if f_row else 0.1

        tax_amt = int(reward_cash * tax_rate)
        if tax_amt > 0:
            await db.execute("UPDATE characters SET bank = bank - ? WHERE guild_id = ? AND name = ?", (tax_amt, guild_id, char_name))
            await db.execute("UPDATE factions SET treasury = treasury + ? WHERE guild_id = ? AND name = ?", (tax_amt, guild_id, f_name))
            await db.execute("INSERT INTO work_tax_logs (guild_id, char_name, work_title, tax_paid, paid_at) VALUES (?, ?, ?, ?, ?)", (guild_id, char_name, work_title, tax_amt, time.time()))
            await db.commit()
            return f"\n🚩 陣營抽成：已自動向所屬【{f_name}】上繳 **${tax_amt:,}** 公款（稅率 {int(tax_rate*100)}%）。"
    return ""
# -------------------- 資料庫完整初始化 --------------------
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
                primary_track TEXT DEFAULT '演繹',
                char_health INTEGER DEFAULT 100,
                affiliation_type TEXT DEFAULT '單打獨鬥',
                affiliation_name TEXT DEFAULT '無',
                debut_years INTEGER DEFAULT 0,
                debut_age INTEGER DEFAULT 0,
                theme_color TEXT DEFAULT '',
                PRIMARY KEY (guild_id, name)
            )
        """)
        # 欄位安全檢測補齊
        cols_to_add = [
            ("stage_name", "TEXT DEFAULT ''"),
            ("image_url", "TEXT DEFAULT ''"),
            ("height", "INTEGER DEFAULT 170"),
            ("weight", "INTEGER DEFAULT 55"),
            ("nationality", "TEXT DEFAULT '本國'"),
            ("education", "TEXT DEFAULT '大學'"),
            ("orientation", "TEXT DEFAULT '保密'"),
            ("primary_track", "TEXT DEFAULT '演繹'"),
            ("char_health", "INTEGER DEFAULT 100"),
            ("affiliation_type", "TEXT DEFAULT '單打獨鬥'"),
            ("affiliation_name", "TEXT DEFAULT '無'"),
            ("debut_years", "INTEGER DEFAULT 0"),
            ("debut_age", "INTEGER DEFAULT 0"),
            ("theme_color", "TEXT DEFAULT ''")
        ]
        for col_name, col_def in cols_to_add:
            try:
                await db.execute(f"ALTER TABLE characters ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass

        # 2. 背包
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
        # 3. 商店
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
                faction_name TEXT DEFAULT ''
            )
        """)
        # 4. 可購置車輛與房產
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
        # 5. 個人固定資產
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
        # 6. 人際關係網絡
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
        # 7. 全域系統設定
        await db.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                guild_id INTEGER,
                key TEXT,
                value TEXT,
                PRIMARY KEY (guild_id, key)
            )
        """)
        # 8. 審核進度表 (二次審核)
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
        # 9. 公司經營體系
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
        # 10. 陣營與成員
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS work_tax_logs (
                guild_id INTEGER,
                char_name TEXT,
                work_title TEXT,
                tax_paid INTEGER DEFAULT 0,
                paid_at REAL,
                PRIMARY KEY (guild_id, char_name, work_title)
            )
        """)
        # 11. 任務與回報
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
        # 12. 地位限制與排行榜
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leaderboards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                name TEXT,
                stat_key TEXT
            )
        """)
        # 13. 抽獎資料庫
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lottery_pools (
                guild_id INTEGER,
                pool_name TEXT,
                items_json TEXT,
                allow_repeat TEXT DEFAULT 'yes',
                role_id INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, pool_name)
            )
        """)
        # 14. 門票簽證
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
        # 15. 路人相冊與姓名庫
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
        # 16. 路人影視作品席位與品牌代言庫
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crowd_works (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                title TEXT,
                work_type TEXT,
                role_name TEXT,
                gender TEXT,
                job_limit TEXT,
                is_variety INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crowd_endorsements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                brand_name TEXT,
                level_title TEXT,
                gender TEXT DEFAULT '通用',
                job_limit TEXT DEFAULT '全體'
            )
        """)
        # 17. 傳聞紀錄與關鍵字統計
        await db.execute("""
            CREATE TABLE IF NOT EXISTS character_rumors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                char_name TEXT,
                rumor_text TEXT,
                created_at REAL
            )
        """)
        # 18. 寵物檔案
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
        await db.commit()
# -------------------- 定時背景任務 --------------------
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
                        await member.remove_roles(role, reason="大地圖門票逾期未歸，系統強制遣返")
                    except Exception:
                        pass

            ban_until = now + (300 * 3600)
            await db.execute("UPDATE characters SET ticket_ban_until = ? WHERE guild_id = ? AND name = ?", (ban_until, g_id, c_name))
            await db.execute("DELETE FROM active_tickets WHERE id = ?", (rec_id,))

        await db.commit()

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

            mode = settings.get("npc_fluct_mode", "percent")
            rate = float(settings.get("npc_fluct_rate", "0.05"))
            include_money = settings.get("npc_fluct_money", "1") == "1"
            max_cap = int(settings.get("npc_fluct_cap", "3000"))

            async with db.execute("SELECT name, cash, bank, stats FROM characters WHERE guild_id = ? AND is_npc = 3", (g_id,)) as c_cur:
                npcs = await c_cur.fetchall()

            for n_name, cash, bank, stats_json in npcs:
                stats = json.loads(stats_json) if stats_json else {}
                for k in stats.keys():
                    if mode == "percent":
                        delta_pct = random.uniform(-rate, rate)
                        stats[k] = max(10, min(max_cap, int(stats[k] * (1 + delta_pct))))
                    else:
                        delta_val = random.randint(-int(rate), int(rate))
                        stats[k] = max(10, min(max_cap, stats[k] + delta_val))

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
                            await user.send(f"🕊️ **【陪伴告別通知】**\n角色【{owner}】飼養的寵物 **{p_name}** ({p_type}) 壽命年限已盡，去了汪喵星球。\n可撰寫悼念貼文並使用 `/喪禮結算`，沉澱轉化為巨額路人緣、死忠粉與公益邀約。")
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

            if is_npc == 0 and u_id > 0 and payout > 0:
                user = bot.get_user(u_id)
                if user:
                    try:
                        loss_text = f"\n⚠️ 因活躍黑粉（{haters:,}人）輿論波及，路人緣扣減 `{loss_applied}` 點！" if loss_applied > 0 else ""
                        await user.send(
                            f"📊 **【每週市場與粉絲結算】** {user.mention}\n"
                            f"角色【**{c_name}**】本週死忠粉分紅入帳：**+${payout:,}**（已存入銀行）！{loss_text}"
                        )
                    except Exception:
                        pass
        await db.commit()

# -------------------- 字數統計與監聽 --------------------
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

    if bot.user in message.mentions:
        if not isinstance(message.channel, discord.Thread):
            await message.reply("⚠️ **此功能只能在討論串或帖子裡的留言區使用！**", mention_author=True)
            return

        g_id = message.guild.id
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

    await bot.process_commands(message)
# -------------------- 創角選單 View --------------------
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
                super().__init__(placeholder="【步驟 1/2】請勾選個人特質標籤 (最多 2 個)...", min_values=1, max_values=min(2, len(tag_options)), options=tag_options)

            async def callback(sub_self, inter: discord.Interaction):
                chosen = sub_self.values
                if len(chosen) == 2:
                    t1, t2 = chosen[0], chosen[1]
                    if t2 in TAG_CONFLICTS.get(t1, []):
                        await inter.response.send_message(f"❌ 標籤衝突！【{t1}】與【{t2}】互相對立，請重新選擇！", ephemeral=True)
                        return

                sub_self.view.selected_tags = chosen
                sub_self.view.setup_debut_step()
                await inter.response.edit_message(content=f"🏷️ 已選定標籤：`{'、'.join(chosen)}`\n👇 請點選【出道時長】（5~12歲入行將獲頒國民標籤）：", view=sub_self.view)

        self.add_item(TagSelect())

    def setup_debut_step(self):
        self.clear_items()
        max_d = max(0, self.age - 5)
        step = max(1, max_d // 10)
        opts_years = sorted(list(set([0] + list(range(1, max_d + 1, step)) + [max_d])))

        debut_options = [
            discord.SelectOption(
                label=f"出道 {y} 年 (於 {self.age - y} 歲入行)",
                value=str(y),
                description="🌟 5~12歲入行將獲頒公認「國民」標籤！" if 5 <= (self.age - y) <= 12 else "常規出道年資"
            ) for y in opts_years[:25]
        ]

        parent = self

        class DebutSelect(discord.ui.Select):
            def __init__(sub_self):
                super().__init__(placeholder="【步驟 2/2】請點選角色出道時長 (星途年資)...", options=debut_options)

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
                        kid_tag_msg = f"\n🎉 **童星出道認證！** 額外獲頒公認標籤：【`{kid_tag}`】"

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
                        f"• 出道歷練：**{chosen_years} 年**（於 {debut_age} 歲入行）{kid_tag_msg}\n"
                        f"隨時可使用 `/查看 {parent.char_name}` 調閱完整檔案！"
                    ),
                    view=None
                )

        self.add_item(DebutSelect())

# -------------------- 指令：/檔案建立 --------------------
@bot.tree.command(name="檔案建立", description="建立玩家個人藝人角色或個人NPC檔案（代表色將反映於檔案卡邊框）")
@app_commands.choices(類別=[
    app_commands.Choice(name="玩家角色", value="0"),
    app_commands.Choice(name="玩家NPC", value="2")
])
@app_commands.describe(
    名字="角色全名",
    年齡="純數字 (例如: 22)",
    身高="純數字 (單位: cm，例如: 180)",
    性別="性別",
    國籍="角色國籍 (例如: 中國、英國、韓國等)",
    職業身分="職業或目前身分 (例如: 新人演員、唱作歌手)",
    代表色碼="選填：16進位色碼 (例如: #FF69B4, #3498DB)",
    感情狀況="選填 (例如: 單身, 隱婚, 熱戀中)",
    照片連結="選填：貼上角色立繪或大頭照網址"
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
    照片連結: str = ""
):
    g_id = interaction.guild_id
    target_name = 名字.strip()
    is_npc_val = int(類別.value)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
            if await cur.fetchone():
                await interaction.response.send_message(f"❌ 名稱 **{target_name}** 已存在！", ephemeral=True)
                return

        await db.execute("""
            INSERT INTO characters (
                guild_id, user_id, name, age, gender, job, faction, tags,
                relationship_status, created_at, is_npc, image_url, height, nationality, theme_color
            ) VALUES (?, ?, ?, ?, ?, ?, '無', '', ?, ?, ?, ?, ?, ?, ?)
        """, (
            g_id, interaction.user.id, target_name, 年齡, 性別, 職業身分,
            感情狀況, time.time(), is_npc_val, 照片連結.strip(), 身高, 國籍.strip(), 代表色碼.strip()
        ))
        await db.commit()

    card_color = parse_hex_color(代表色碼, default_color=0x2ECC71)
    label = "玩家角色" if is_npc_val == 0 else "玩家自製 NPC"
    embed = discord.Embed(title=f"🎉【{label}】基礎建檔成功", color=card_color)
    embed.add_field(name="姓名與基本身分", value=f"**{target_name}** ({年齡}歲 / {性別})\n• 身高：`{身高} cm` ｜ 國籍：`{國籍.strip()}`", inline=False)
    embed.add_field(name="身分職業與感情", value=f"• 職業：{職業身分}\n• 感情：{感情狀況}", inline=True)
    if 代表色碼.strip():
        embed.add_field(name="專屬代表色", value=f"`{代表色碼.strip()}`", inline=True)
    if 照片連結.strip().startswith("http"):
        embed.set_thumbnail(url=照片連結.strip())

    flow_view = CreateProfileFlowView(g_id, target_name, 年齡, 性別)
    await interaction.response.send_message(content=f"👉 請點選下方選單，為 **{target_name}** 選擇個人特質標籤：", embed=embed, view=flow_view)

# -------------------- 指令：/官方npc登記 --------------------
@bot.tree.command(name="官方npc登記", description="【管理員專用】登記官方全域 NPC 檔案（代表色將反映於檔案卡邊框）")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    名字="NPC 姓名",
    年齡="年齡",
    身高="純數字 (單位: cm，例如: 185)",
    性別="性別",
    國籍="NPC 國籍",
    職業身分="官方身分或職業",
    代表色碼="選填：16進位色碼 (例如: #9B59B6, #D4AF37)",
    感情狀況="選填 (預設未知)",
    照片連結="選填：貼上官方 NPC 的形象立繪連結"
)
async def register_official_npc(
    interaction: discord.Interaction,
    名字: str,
    年齡: int,
    身高: int,
    性別: str,
    國籍: str,
    職業身分: str,
    代表色碼: str = "",
    感情狀況: str = "未知",
    照片連結: str = ""
):
    g_id = interaction.guild_id
    target_name = 名字.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO characters (
                guild_id, user_id, name, age, gender, job, faction, tags,
                relationship_status, created_at, is_npc, image_url, height, nationality, theme_color
            ) VALUES (?, 0, ?, ?, ?, ?, '官方勢力', '', ?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(guild_id, name) DO UPDATE SET
                age = excluded.age, gender = excluded.gender, job = excluded.job,
                relationship_status = excluded.relationship_status,
                image_url = excluded.image_url, height = excluded.height, nationality = excluded.nationality,
                theme_color = excluded.theme_color
        """, (
            g_id, target_name, 年齡, 性別, 職業身分,
            感情狀況, time.time(), 照片連結.strip(), 身高, 國籍.strip(), 代表色碼.strip()
        ))
        await db.commit()

    card_color = parse_hex_color(代表色碼, default_color=0x9B59B6)
    embed = discord.Embed(title=f"👑 官方 NPC 基礎登記完畢：【{target_name}】", color=card_color)
    embed.add_field(name="基本檔案", value=f"{年齡}歲 ｜ {性別} ｜ `{身高} cm` ｜ 國籍：`{國籍.strip()}`", inline=False)
    embed.add_field(name="身分與感情", value=f"• 職業：{職業身分}\n• 感情：{感情狀況}", inline=True)
    if 代表色碼.strip():
        embed.add_field(name="專屬代表色", value=f"`{代表色碼.strip()}`", inline=True)
    if 照片連結.strip().startswith("http"):
        embed.set_thumbnail(url=照片連結.strip())

    flow_view = CreateProfileFlowView(g_id, target_name, 年齡, 性別)
    await interaction.response.send_message(content=f"👉 請點選下方選單，為官方 NPC **{target_name}** 選擇特質標籤：", embed=embed, view=flow_view)

# -------------------- 指令：/審核通過 --------------------
@bot.tree.command(name="審核通過", description="【管理員專用】在人設討論串中直接審核，兩次自動正式入籍")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    角色名="【選填】若已知角色名可填寫，留空則自動從人設單解析",
    人設單文章連結="【選填】貼上人設帖子連結，留空則自動抓取本討論串貼文"
)
async def audit_pass_cmd(interaction: discord.Interaction, 角色名: str = None, 人設單文章連結: str = None):
    g_id = interaction.guild_id
    ch = interaction.channel
    await interaction.response.defer(ephemeral=False)

    target_content, post_author_id = "", 0
    if 人設單文章連結:
        link_m = re.search(r"channels/\d+/(\d+)(?:/(\d+))?", 人設單文章連結.strip())
        if link_m:
            c_id = int(link_m.group(1))
            m_id = int(link_m.group(2)) if link_m.group(2) else None
            try:
                fetch_ch = interaction.client.get_channel(c_id) or await interaction.client.fetch_channel(c_id)
                if isinstance(fetch_ch, discord.Thread):
                    first_msg = await fetch_ch.fetch_message(fetch_ch.id)
                    target_content = first_msg.content
                    post_author_id = first_msg.author.id
                elif m_id:
                    m = await fetch_ch.fetch_message(m_id)
                    target_content = m.content
                    post_author_id = m.author.id
            except Exception:
                pass
    elif isinstance(ch, discord.Thread):
        try:
            starter = await ch.parent.fetch_message(ch.id) if hasattr(ch, "parent") else None
            if not starter:
                starter = await ch.fetch_message(ch.id)
            target_content = starter.content
            post_author_id = starter.author.id
        except Exception:
            async for msg in ch.history(limit=5, oldest_first=True):
                if not msg.author.bot:
                    target_content = msg.content
                    post_author_id = msg.author.id
                    break

    parsed = parse_character_sheet(target_content) if target_content else {}
    c_name = 角色名.strip() if 角色名 else parsed.get("name", "")

    if not c_name:
        await interaction.followup.send("❌ 無法偵測到角色姓名！請手動填寫【角色名】參數或確認人設單格式。", ephemeral=True)
        return

    thread_id = ch.id if isinstance(ch, discord.Thread) else 0

    async with aiosqlite.connect(DB_PATH) as db:
        current_count = 0
        if thread_id:
            async with db.execute("SELECT audit_count FROM profile_audits WHERE guild_id = ? AND thread_id = ?", (g_id, thread_id)) as a_cur:
                rec = await a_cur.fetchone()
                current_count = rec[0] if rec else 0

        # 初審通過
        if current_count == 0:
            if thread_id:
                await db.execute("""
                    INSERT INTO profile_audits (guild_id, thread_id, char_name, audit_count, status)
                    VALUES (?, ?, ?, 1, '初審通過')
                    ON CONFLICT(guild_id, thread_id) DO UPDATE SET audit_count = 1, status = '初審通過', char_name = excluded.char_name
                """, (g_id, thread_id, c_name))
                await db.commit()

            embed = discord.Embed(
                title=f"📝【{c_name}】人設初審通過（1/2）",
                description=f"審核管理員：{interaction.user.mention}\n本檔案已完成第一階段審核，請等待第二位管理員進行終審！",
                color=0xF1C40F
            )
            embed.set_footer(text="提示：第二位管理員在此輸入 /審核通過 即可正式完成入籍發放福利。")
            await interaction.followup.send(embed=embed)
            return

        # 終審通過
        elif current_count == 1:
            if thread_id:
                await db.execute("UPDATE profile_audits SET audit_count = 2, status = '終審完畢' WHERE guild_id = ? AND thread_id = ?", (g_id, thread_id))

            h = parsed.get("height", 175)
            w = parsed.get("weight", 55)
            st = parsed.get("stats", {})
            f_health, f_app, bmi_val, warn_bmi = check_bmi_impact(h, w, 100, st.get("容貌", 50))
            st["容貌"] = f_app

            assigned_user_id = post_author_id if post_author_id else interaction.user.id
            await db.execute("""
                INSERT INTO characters (
                    guild_id, user_id, name, stage_name, age, gender, job, faction,
                    tags, relationship_status, created_at, is_npc, height, weight,
                    nationality, education, orientation, primary_track, char_health,
                    affiliation_type, affiliation_name, cash, bank, stats
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '無', ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, 10000, 50000, ?)
                ON CONFLICT(guild_id, name) DO UPDATE SET
                    stage_name = excluded.stage_name, age = excluded.age, gender = excluded.gender,
                    job = excluded.job, height = excluded.height, weight = excluded.weight,
                    nationality = excluded.nationality, education = excluded.education,
                    orientation = excluded.orientation, primary_track = excluded.primary_track,
                    char_health = excluded.char_health, affiliation_type = excluded.affiliation_type,
                    affiliation_name = excluded.affiliation_name, stats = excluded.stats
            """, (
                g_id, assigned_user_id, c_name, parsed.get("stage_name", c_name),
                parsed.get("age", 22), parsed.get("gender", "女"), parsed.get("job", "新人演員"),
                parsed.get("tags", ""), parsed.get("relationship_status", "單身"),
                time.time(), h, w, parsed.get("nationality", "本國"),
                parsed.get("education", "大學"), parsed.get("orientation", "保密"),
                parsed.get("primary_track", "演繹"), f_health,
                parsed.get("affiliation_type", "單打獨鬥"), parsed.get("affiliation_name", "無"),
                json.dumps(st, ensure_ascii=False)
            ))
            await db.commit()

            owner_mention = f"<@{assigned_user_id}>"
            embed = discord.Embed(
                title=f"🎉【{c_name}】終審通過，正式入籍！",
                description=(
                    f"受審角色：**{c_name}**（藝名：{parsed.get('stage_name', '無')}）\n"
                    f"持有人：{owner_mention} ｜ 終審管理員：{interaction.user.mention}\n\n"
                    f"📋 **已自動同步登記入冊：**\n"
                    f"• 歸屬：`{parsed.get('affiliation_type', '單打獨鬥')}`（{parsed.get('affiliation_name', '無')}）\n"
                    f"• 賽道：主攻【**{parsed.get('primary_track', '演繹')}**】\n"
                    f"• 身材：{h} cm / {w} kg (BMI: `{bmi_val}`)\n"
                    f"• 初始健康度：**{f_health} / 100**\n"
                    f"• 國籍/學歷/性向：`{parsed.get('nationality', '本國')}` ｜ `{parsed.get('education', '大學')}` ｜ `{parsed.get('orientation', '保密')}`\n\n"
                    f"💰 **新手福利：** 初始發放 **$10,000** 現金，**$50,000** 已存入銀行！"
                ),
                color=0x2ECC71
            )
            if warn_bmi:
                embed.add_field(name="⚠️ 身材指數提醒", value=warn_bmi, inline=False)

            if not parsed.get("tags"):
                flow_view = CreateProfileFlowView(g_id, c_name, parsed.get("age", 22), parsed.get("gender", "女"))
                await interaction.followup.send(content=f"{owner_mention} 請點選下方選單補齊特質標籤與星途年資：", embed=embed, view=flow_view)
            else:
                await interaction.followup.send(content=owner_mention, embed=embed)
            return
        else:
            await interaction.followup.send(f"⚠️ 角色【{c_name}】早已完成雙重審核並已入籍！", ephemeral=True)
# -------------------- 角色檔案按鈕組：ProfileMainView --------------------
class ProfileMainView(discord.ui.View):
    def __init__(self, char_name: str, guild_id: int):
        super().__init__(timeout=180)
        self.char_name = char_name
        self.guild_id = guild_id

    @discord.ui.button(label="🏆 成就作品", style=discord.ButtonStyle.primary, row=0)
    async def view_achieves(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT works FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                row = await cur.fetchone()
                works = json.loads(row[0]) if (row and row[0]) else []
        items = [f"• 【{w.get('type', '作品')}】《{w.get('title')}》— {w.get('extra', '參演')}" for w in works if w.get("category") == "成就"]
        p_view = PagedDetailView(f"🏆【{self.char_name}】歷練成就作品清單", items, 0xF1C40F)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

    @discord.ui.button(label="🎖️ 榮譽代言", style=discord.ButtonStyle.success, row=0)
    async def view_honors(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT works FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                row = await cur.fetchone()
                works = json.loads(row[0]) if (row and row[0]) else []
        items = [f"• 🎖️《{w.get('title')}》— {w.get('extra', '榮譽認證')}" for w in works if w.get("category") == "榮譽"]
        p_view = PagedDetailView(f"🎖️【{self.char_name}】獲頒榮譽與品牌代言", items, 0x2ECC71)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

    @discord.ui.button(label="🐾 寵物夥伴", style=discord.ButtonStyle.secondary, row=0)
    async def view_pets(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT pet_type, pet_name, health, is_dead, lifespan_years FROM character_pets WHERE guild_id = ? AND owner_name = ?", (self.guild_id, self.char_name)) as cur:
                rows = await cur.fetchall()
        lines = [f"• **{p_name}** ({p_type}) ｜ 狀態: {'🕊️ 已故' if is_dead else f'❤️ 健康值: `{health}/500` (壽命: {l_years}年)'}" for p_type, p_name, health, is_dead, l_years in rows]
        embed = discord.Embed(title=f"🐾【{self.char_name}】的寵物夥伴", description="\n".join(lines) if lines else "目前尚未飼養任何毛小孩（可使用 `/寵物購買` 認養）。", color=0x1ABC9C)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📢 圈內傳聞", style=discord.ButtonStyle.secondary, row=1)
    async def view_rumors(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT rumor_text FROM character_rumors WHERE guild_id = ? AND char_name = ? ORDER BY id DESC LIMIT 20", (self.guild_id, self.char_name)) as cur:
                rows = await cur.fetchall()
        items = [f"• 「{r[0]}」" for r in rows]
        p_view = PagedDetailView(f"📢【{self.char_name}】的坊間八卦與傳聞", items, 0xE74C3C)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

    @discord.ui.button(label="💬 社交網絡", style=discord.ButtonStyle.danger, row=1)
    async def view_relationships(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT to_char, tendency, affection, status_desc FROM relationships WHERE guild_id = ? AND from_char = ?", (self.guild_id, self.char_name)) as cur:
                rows = await cur.fetchall()
        items = [f"• 對象：**{to_c}** ｜ 傾向：【{t}】 ｜ 羈絆：💖{aff} ｜ 狀況：`{desc}`" for to_c, t, aff, desc in rows]
        p_view = PagedDetailView(f"💬【{self.char_name}】的交際關係網絡", items, 0xE91E63)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

# -------------------- 指令：/查看 --------------------
@bot.tree.command(name="查看", description="調閱個人角色、官方角色或大眾路人詳細檔案與資產面板")
@app_commands.describe(名字="角色或 NPC 姓名")
async def view_char_cmd(interaction: discord.Interaction, 名字: str):
    g_id = interaction.guild_id
    target_name = 名字.strip()
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=False)

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
            await interaction.followup.send(f"❌ 查無檔案【{target_name}】！", ephemeral=True)
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

    final_color = parse_hex_color(theme_color, default_color=default_c)
    h_display = f"{height} cm" if height else "未填寫"
    w_display = f"{weight} kg" if weight else "未填寫"
    nat_display = nationality if nationality else "本國"
    debut_info = f"{debut_years} 年 (於 {debut_age} 歲入行)" if (debut_years and debut_years > 0) else "新秀 / 未正式出道"
    stage_str = f" / 藝名: {stage_name}" if stage_name and stage_name != target_name else ""

    embed = discord.Embed(title=f"🪪 {tag_prefix}【{target_name}】{stage_str} 個人資料面板", color=final_color)
    embed.add_field(
        name="基本身分與星途",
        value=(
            f"• 國籍/性別: `{nat_display}` / {gender} ({orientation or '保密'})\n"
            f"• 年齡/身材: {age}歲 / `{h_display}` / `{w_display}`\n"
            f"• 身分/賽道: {job} ｜ 主攻【**{primary_track or '演繹'}**】\n"
            f"• 歸屬組織: `{aff_type or '單打獨鬥'}`（{aff_name or '無'}）\n"
            f"• 出道歷練: **{debut_info}**\n"
            f"• 核心健康: ❤️ **{char_health or 100} / 100**\n"
            f"• 代表色碼: `{theme_color or '預設'}` ｜ 所屬勢力: {faction}\n"
            f"• 特質標籤: `{tags or '無'}`"
        ),
        inline=False
    )
    cp_obj = json.loads(cp_json) if cp_json else {}
    cp_text = f"💕 CP: **{cp_obj.get('target')}** ({cp_obj.get('relation')})" if cp_obj.get("target") else "無"
    embed.add_field(name="情感狀態", value=f"• 感情: {rel_status}\n• {cp_text}", inline=True)
    embed.add_field(name="資產與地位", value=f"• 當前地位: **【{rank_name or '未定級'}】**\n• 手頭現金: ${cash:,}\n• 銀行存款: ${bank:,}", inline=True)

    asset_lines = [f"• [{a[0]}] {a[1]} (${a[2]:,})" for a in assets]
    if comps:
        for c in comps: asset_lines.append(f"• [旗下公司] {c[0]} ({c[1]})")
    embed.add_field(name="🚗 產權與名下企業", value="\n".join(asset_lines) if asset_lines else "名下尚無固定資產", inline=False)

    stats = json.loads(stats_json) if stats_json else {}
    stat_texts = [f"{k}: **{v}**" for k, v in stats.items() if k not in hidden_stats_set]
    embed.add_field(name="📊 核心演藝數值", value=" ｜ ".join(stat_texts) if stat_texts else "尚未登記任何公開數值", inline=False)

    if img_url and img_url.startswith("http"):
        embed.set_thumbnail(url=img_url)

    await interaction.followup.send(embed=embed, view=ProfileMainView(target_name, g_id))

# -------------------- 指令：/npc查看 --------------------
@bot.tree.command(name="npc查看", description="查看已登記的官方 NPC 名冊大廳或個別檔案")
@app_commands.describe(npc名稱="【選填】輸入特定官方 NPC 姓名，留空則開啟名錄大廳")
async def view_npc_cmd(interaction: discord.Interaction, npc名稱: str = None):
    g_id = interaction.guild_id
    if npc名稱:
        await view_char_cmd(interaction, npc名稱)
        return

    await interaction.response.defer(ephemeral=True)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, age, gender, job, nationality, height FROM characters WHERE guild_id = ? AND is_npc = 1", (g_id,)) as cur:
            all_npcs = await cur.fetchall()

    if not all_npcs:
        await interaction.followup.send("📋 目前尚未登記任何官方 NPC！", ephemeral=True)
        return

    embed = discord.Embed(title="👥 官方 NPC 名錄大廳", description="請點選下方選單調閱各官方 NPC 個人詳細檔案：", color=0x9B59B6)
    for npc in all_npcs[:15]:
        h_str = f" ｜ {npc[5]}cm" if npc[5] else ""
        embed.add_field(name=f"👑 {npc[0]} ({npc[1]}歲 / {npc[2]})", value=f"國籍：`{npc[4] or '本國'}`{h_str}\n身分：{npc[3]}", inline=True)

    class NPCDropdown(discord.ui.Select):
        def __init__(self):
            opts = [discord.SelectOption(label=n[0], description=f"{n[1]}歲 ｜ {n[2]} ｜ {n[3]}", emoji="👑") for n in all_npcs[:25]]
            super().__init__(placeholder="點此選擇欲調閱檔案的官方 NPC...", options=opts)

        async def callback(self, inter: discord.Interaction):
            await view_char_cmd(inter, self.values[0])

    view = discord.ui.View()
    view.add_item(NPCDropdown())
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
# -------------------- 指令：/任務新增 --------------------
@bot.tree.command(name="任務新增", description="【管理員專用】發布或修改任務（含成就/榮譽/大眾認知度門檻與整合物品獎勵）")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="新增任務", value="add"),
    app_commands.Choice(name="修改既有任務", value="edit")
])
@app_commands.choices(選擇欄位=[
    app_commands.Choice(name="新手任務", value="新手任務"),
    app_commands.Choice(name="一般任務", value="一般任務"),
    app_commands.Choice(name="限時任務", value="限時任務"),
    app_commands.Choice(name="特殊任務", value="特殊任務"),
])
@app_commands.describe(
    操作="選擇新增或修改任務內容",
    選擇欄位="任務所屬分類",
    任務名="任務名稱（玩家文章標題需包含此名稱）",
    金錢獎勵="自動匯入銀行的金錢 (純整數，可填 0)",
    數值獎勵="【選填】格式例如: 容貌50 才智60 或 商業價值+20",
    獎勵物品="【選填】格式例如: 美容膏*1 花束*2，多項以空白或逗號隔開",
    成就="【選填】完成時賦予的成就名稱或標籤",
    榮譽="【選填】完成時賦予的榮譽稱號或等級",
    認知度限制="【選填】大眾認知度最低門檻 (純整數，例如: 500)",
    限制條件="【選填】其他接取門檻（例如：地位限一線、性別限女、勢力限某某）",
    限時時間="僅限時任務需填寫，格式：YYYY/M/D HH:MM～YYYY/M/D HH:MM",
    回報頻道="【選填】限定回報的文字頻道/討論串/論壇，留空則全服任意頻道可回報"
)
async def add_quest_cmd(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    選擇欄位: app_commands.Choice[str],
    任務名: str,
    金錢獎勵: int = 0,
    數值獎勵: str = "",
    獎勵物品: str = "",
    成就: str = "",
    榮譽: str = "",
    認知度限制: int = 0,
    限制條件: str = "",
    限時時間: str = None,
    回報頻道: discord.abc.GuildChannel = None
):
    g_id = interaction.guild_id
    category = 選擇欄位.value
    time_limit_str = 限時時間.strip() if (category == "限時任務" and 限時時間) else ""
    rep_ch_id = 回報頻道.id if 回報頻道 else 0

    parsed_items = []
    if 獎勵物品 and 獎勵物品.strip():
        tokens = re.split(r"[,，\n\r\s]+", 獎勵物品.strip())
        for token in tokens:
            if not token:
                continue
            match = re.match(r"^([^*xX×]+)(?:[*xX×](\d+))?$", token)
            if match:
                i_name = match.group(1).strip()
                i_amt = int(match.group(2)) if match.group(2) else 1
                parsed_items.append({"name": i_name, "amount": i_amt})
            else:
                parsed_items.append({"name": token.strip(), "amount": 1})

    full_req = 限制條件.strip()
    if 認知度限制 > 0:
        full_req = f"認知度>{認知度限制}; {full_req}".strip("; ")

    items_json = json.dumps(parsed_items, ensure_ascii=False)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM quests WHERE guild_id = ? AND title = ?", (g_id, 任務名.strip())) as cur:
            exists = await cur.fetchone()

        if 操作.value == "add":
            if exists:
                await interaction.response.send_message(f"❌ 任務名稱 `{任務名}` 已經存在！", ephemeral=True)
                return
            await db.execute("""
                INSERT INTO quests (
                    guild_id, category, title, reward_cash, reward_items, reward_stats,
                    achievement, honor, requirement, time_limit, report_channel_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                g_id, category, 任務名.strip(), 金錢獎勵, items_json,
                數值獎勵.strip(), 成就.strip(), 榮譽.strip(), full_req,
                time_limit_str, rep_ch_id
            ))
            op_label = "新增"
        else:
            if not exists:
                await interaction.response.send_message(f"❌ 找不到欲修改的任務 `{任務名}`！", ephemeral=True)
                return
            await db.execute("""
                UPDATE quests SET
                    category = ?, reward_cash = ?, reward_items = ?, reward_stats = ?,
                    achievement = ?, honor = ?, requirement = ?, time_limit = ?, report_channel_id = ?
                WHERE guild_id = ? AND title = ?
            """, (
                category, 金錢獎勵, items_json, 數值獎勵.strip(),
                成就.strip(), 榮譽.strip(), full_req, time_limit_str,
                rep_ch_id, g_id, 任務名.strip()
            ))
            op_label = "修改"

        await db.commit()

    rewards_list = []
    if 金錢獎勵 > 0:
        rewards_list.append(f"${金錢獎勵:,}")
    if 數值獎勵.strip():
        rewards_list.append(f"{數值獎勵.strip()}")
    if parsed_items:
        rewards_list.append(" ".join([f"{it['name']}×{it['amount']}" for it in parsed_items]))
    reward_summary = " ｜ ".join(rewards_list) if rewards_list else "無實質物資獎勵"

    achieve_desc = f"\n🏆 成就獎勵：【{成就}】" if 成就 else ""
    honor_desc = f"\n🎖️ 榮譽稱號：【{榮譽}】" if 榮譽 else ""
    req_desc = f"\n🚫 接取限制門檻：【{full_req}】" if full_req else ""
    ch_desc = f"\n📍 限定回報區：{回報頻道.mention}" if 回報頻道 else "\n📍 限定回報區：全伺服器皆可"

    await interaction.response.send_message(
        f"✅ 成功{op_label}任務！\n"
        f"📌 分類：【{category}】\n"
        f"🏷️ 任務名：**{任務名}**\n"
        f"🎁 獎勵：{reward_summary}{achieve_desc}{honor_desc}{req_desc}{ch_desc}"
    )

# -------------------- 指令：/回報任務 --------------------
@bot.tree.command(name="回報任務", description="回報任務文章連結，領取獎勵（自動完成陣營抽成、生態加成與檢測地位）")
@app_commands.describe(角色名="回報任務的角色名稱", 文章連結="你所發表文章的帖子/討論串或訊息連結")
async def report_quest(interaction: discord.Interaction, 角色名: str, 文章連結: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    await interaction.response.defer(ephemeral=False)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT user_id, gender, faction, stats, rank, works, primary_track, cash, bank
            FROM characters WHERE guild_id = ? AND name = ?
        """, (g_id, c_name)) as cur:
            row = await cur.fetchone()
            if not row:
                await interaction.followup.send(f"❌ 查無角色 `{c_name}`！", ephemeral=True)
                return
            u_id, gender, faction, stats_json, rank_name, works_json, primary_track, cash, bank = row
            if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ 你只能為自己持有的角色回報任務！", ephemeral=True)
                return

    link_pattern = r"channels/\d+/(\d+)(?:/(\d+))?"
    match = re.search(link_pattern, 文章連結)
    if not match:
        await interaction.followup.send("❌ 無法識別文章連結格式！", ephemeral=True)
        return

    target_channel_id = int(match.group(1))
    target_msg_id = int(match.group(2)) if match.group(2) else None
    target_title = ""

    try:
        channel_or_thread = interaction.client.get_channel(target_channel_id) or await interaction.client.fetch_channel(target_channel_id)
        if isinstance(channel_or_thread, discord.Thread):
            target_title = channel_or_thread.name
        elif target_msg_id:
            msg = await channel_or_thread.fetch_message(target_msg_id)
            target_title = msg.content
    except Exception:
        pass

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT title, reward_cash, reward_items, reward_stats, achievement, honor, requirement, time_limit, report_channel_id
            FROM quests WHERE guild_id = ?
        """, (g_id,)) as cur:
            all_quests = await cur.fetchall()

        matched_quest = None
        for q in all_quests:
            if q[0] in target_title:
                matched_quest = q
                break

        if not matched_quest:
            await interaction.followup.send("❌ 驗證失敗：無法在文章標題中匹配到正確的任務名稱！", ephemeral=True)
            return

        q_title, r_cash, r_items_json, r_stats, achieve_val, honor_val, requirement, time_limit, req_channel_id = matched_quest

        if req_channel_id and req_channel_id > 0:
            current_ch = interaction.channel
            is_correct = (current_ch.id == req_channel_id) or (hasattr(current_ch, "parent_id") and current_ch.parent_id == req_channel_id)
            if not is_correct:
                await interaction.followup.send(f"❌ 此任務限定在指定的專屬回報區操作！請前往：<#{req_channel_id}>", ephemeral=True)
                return

        async with db.execute("SELECT 1 FROM quest_completions WHERE guild_id = ? AND char_name = ? AND quest_title = ?", (g_id, c_name, q_title)) as cur:
            if await cur.fetchone():
                await interaction.followup.send(f"⚠️ 角色 **{c_name}** 已經完成過任務【{q_title}】，不可重複回報！", ephemeral=True)
                return

        char_stats = json.loads(stats_json) if stats_json else {}
        works = json.loads(works_json) if works_json else []

        # 通告數量上限檢驗 (最少 15 個)
        traffic = char_stats.get("流量熱度", 0)
        max_quota = max(15, 15 + (traffic // 100))
        current_month_done = sum(1 for w in works if w.get("type") == "通告")
        if current_month_done >= max_quota:
            await interaction.followup.send(
                f"❌ **【檔期已滿】** **{c_name}** 當前流量熱度為 `{traffic}`，本月通告接取上限為 **{max_quota}** 部（已達標）！請提升熱度以解鎖更多檔期。",
                ephemeral=True
            )
            return

        comm_val = char_stats.get("商業價值", 50)
        comm_mult = 1.0 + (comm_val / 2000.0)
        can_ignore_req = (comm_val >= 2500)

        if requirement and not can_ignore_req:
            cog_match = re.search(r"認知度>(\d+)", requirement)
            if cog_match:
                min_cog = int(cog_match.group(1))
                if char_stats.get("大眾認知度", 0) < min_cog:
                    await interaction.followup.send(f"❌ 資格不符：此榮譽任務要求大眾認知度達 **{min_cog}**，你當前僅有 **{char_stats.get('大眾認知度', 0)}**！（商業價值達 2500 可無視門檻）", ephemeral=True)
                    return
            if "地位" in requirement and rank_name not in requirement:
                await interaction.followup.send(f"❌ 資格不符：此任務要求【{requirement}】，你當前地位為【{rank_name}】！", ephemeral=True)
                return
            if "性別" in requirement and gender not in requirement:
                await interaction.followup.send(f"❌ 資格不符：此任務限制性別！", ephemeral=True)
                return
            if "勢力" in requirement and faction not in requirement:
                await interaction.followup.send(f"❌ 資格不符：此任務限制指定勢力參與！", ephemeral=True)
                return

        # 主攻賽道契合度 (1.3x 錢, 1.5x 數值)
        track_boost = 1.5 if (primary_track and primary_track in q_title) else 1.0
        track_cash_mult = 1.3 if (primary_track and primary_track in q_title) else 1.0

        # 路人緣低於 50 黑紅抵制
        passerby = char_stats.get("路人緣", 50)
        reputation_mult = 0.6 if passerby < 50 else 1.0

        final_cash = int(r_cash * comm_mult * track_cash_mult * reputation_mult)

        stat_changes = []
        if r_stats:
            stat_tokens = re.split(r"[,，、\s]+", r_stats.strip())
            for token in stat_tokens:
                m = re.search(r"([^\d+-]+)([+-]?\d+)", token)
                if m:
                    s_name = m.group(1).strip()
                    base_val = int(m.group(2))
                    earned_stat = int(base_val * track_boost)
                    char_stats[s_name] = max(0, char_stats.get(s_name, 0) + earned_stat)
                    sign = "+" if earned_stat >= 0 else ""
                    stat_changes.append(f"{s_name} {sign}{earned_stat}")

        # 容貌熱搜擴散
        app_val = char_stats.get("容貌", 50)
        hot_search_bonus = 0
        if random.random() < min(0.40, app_val / 250.0):
            hot_search_bonus = random.randint(50, 180)
            char_stats["流量熱度"] = char_stats.get("流量熱度", 0) + hot_search_bonus

        if final_cash > 0:
            await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (final_cash, g_id, c_name))

        items = json.loads(r_items_json) if r_items_json else []
        for it in items:
            it_name, it_amt = it.get("name"), it.get("amount", 1)
            async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ? AND giver = '任務獎勵'", (g_id, c_name, it_name)) as cur:
                inv_row = await cur.fetchone()
                if inv_row:
                    await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (it_amt, inv_row[0]))
                else:
                    await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, ?, '任務獎勵')", (g_id, c_name, it_name, it_amt))

        if achieve_val:
            works.append({"category": "成就", "type": "通告", "title": q_title, "extra": achieve_val})
        if honor_val:
            works.append({"category": "榮譽", "type": "通告", "title": q_title, "extra": honor_val})
        if not achieve_val and not honor_val:
            works.append({"category": "歷練", "type": "通告", "title": q_title, "extra": "常規通告"})

        await db.execute("""
            UPDATE characters SET stats = ?, works = ? WHERE guild_id = ? AND name = ?
        """, (json.dumps(char_stats, ensure_ascii=False), json.dumps(works, ensure_ascii=False), g_id, c_name))
        await db.execute("INSERT INTO quest_completions (guild_id, char_name, quest_title, completed_at) VALUES (?, ?, ?, ?)", (g_id, c_name, q_title, time.time()))
        await db.commit()

    tax_info = await process_faction_tax(g_id, c_name, q_title, final_cash, interaction.channel)
    await check_and_update_rank(g_id, c_name, interaction.channel)

    earned = []
    if final_cash > 0:
        earned.append(f"$ {final_cash:,}")
    if stat_changes:
        earned.append(f"+ 數值【{'、'.join(stat_changes)}】")
    if items:
        earned.append(f"物品【{' '.join([f'{i['name']}×{i['amount']}' for i in items])}】")
    if achieve_val:
        earned.append(f"成就【{achieve_val}】")
    if honor_val:
        earned.append(f"榮譽【{honor_val}】")
    earned_str = " ｜ ".join(earned) if earned else "無實質物資獎勵"

    notes = []
    if track_boost > 1.0:
        notes.append(f"🎯 **主攻賽道契合**（報酬加成 1.3x，數值成長 1.5x）")
    if passerby < 50:
        notes.append("⚠️ **黑紅抵制**（路人緣低於 50，收益縮水 40%）")
    if hot_search_bonus > 0:
        notes.append(f"🔥 **顏值熱搜爆發**（容貌擴散，流量熱度 +{hot_search_bonus}）")
    note_str = f"\n> " + "\n> ".join(notes) if notes else ""

    await interaction.followup.send(
        f"‼️ **任務確認完成**\n"
        f"獎勵：{earned_str}{tax_info}{note_str}\n"
        f"恭喜 {interaction.user.mention} 的【**{c_name}**】完成任務《**{q_title}**》！✅（本月通告進度：`{current_month_done + 1}/{max_quota}`）"
    )
# -------------------- 指令：/公司 --------------------
@bot.tree.command(name="公司", description="管理名下公司、設立旗下專屬商店售賣商品或檢視所在公司")
async def company_cmd(interaction: discord.Interaction):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND user_id = ?", (g_id, interaction.user.id)) as cur:
            c_row = await cur.fetchone()
            if not c_row:
                await interaction.response.send_message("❌ 你尚未擁有任何角色檔案！", ephemeral=True)
                return
            my_char = c_row[0]

        async with db.execute("SELECT id, name, split_ratio, balance, allowed_jobs FROM companies WHERE guild_id = ? AND creator_name = ?", (g_id, my_char)) as cur:
            my_own_comp = await cur.fetchone()

    view = discord.ui.View()
    if my_own_comp:
        comp_id, comp_name, split_ratio, balance, allowed_jobs = my_own_comp

        btn_run = discord.ui.Button(label="💼 年度經營結算", style=discord.ButtonStyle.success)
        btn_rule = discord.ui.Button(label="📝 規則修正", style=discord.ButtonStyle.secondary)
        btn_shop = discord.ui.Button(label="🏪 設立/管理旗下商店", style=discord.ButtonStyle.primary)
        btn_withdraw = discord.ui.Button(label="💰 提領公司利潤", style=discord.ButtonStyle.danger)

        async def run_cb(inter: discord.Interaction):
            revenue = random.randint(50000, 200000)
            cost = int(revenue * 0.3)
            profit = revenue - cost
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE companies SET balance = balance + ? WHERE id = ?", (profit, comp_id))
                await db.commit()
            await inter.response.send_message(f"📊 【{comp_name}】年度經營結算：\n• 總營收：+${revenue:,}\n• 營運支出：-${cost:,}\n• 實質盈餘入庫：**+${profit:,}**！")

        async def rule_cb(inter: discord.Interaction):
            class RuleModal(discord.ui.Modal, title=f"修正【{comp_name}】公司規則"):
                split = discord.ui.TextInput(label="員工分成比例 (0.1 ~ 0.9)", placeholder="例如: 0.5")
                jobs = discord.ui.TextInput(label="收納職業/身分限制", placeholder="例如: 演員, 歌手, 主持人", required=False)

                async def on_submit(m_self, m_inter: discord.Interaction):
                    try:
                        s_val = float(m_self.split.value.strip())
                    except ValueError:
                        s_val = 0.5
                    j_val = m_self.jobs.value.strip()
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("UPDATE companies SET split_ratio = ?, allowed_jobs = ? WHERE id = ?", (s_val, j_val, comp_id))
                        await db.commit()
                    await m_inter.response.send_message(f"✅ 公司規章已更新！分成調整為 `{int(s_val*100)}%`，職業限制：`{j_val or '無限制'}`！", ephemeral=True)
            await inter.response.send_modal(RuleModal())

        async def shop_cb(inter: discord.Interaction):
            class AddProductModal(discord.ui.Modal, title=f"【{comp_name}】品牌門市商品上架"):
                p_name = discord.ui.TextInput(label="商品名稱", placeholder="例如: 聯名香水、高階教程")
                p_price = discord.ui.TextInput(label="販售單價 (純數字)", placeholder="例如: 15000")
                p_desc = discord.ui.TextInput(label="商品介紹", placeholder="例如: 使用後散發迷人氣質")
                p_bonus = discord.ui.TextInput(label="使用獲得數值 (選填)", placeholder="例如: 容貌+15、商業價值+10", required=False)
                p_aff = discord.ui.TextInput(label="贈予好感加成 (純數字，選填)", placeholder="例如: 10", required=False)

                async def on_submit(m_self, m_inter: discord.Interaction):
                    try:
                        price = int(m_self.p_price.value.strip())
                        if price <= 0: raise ValueError
                    except ValueError:
                        await m_inter.response.send_message("❌ 販售單價必須為正整數！", ephemeral=True)
                        return
                    aff = int(m_self.p_aff.value.strip()) if m_self.p_aff.value.strip().isdigit() else 0
                    prod_name = m_self.p_name.value.strip()
                    prod_desc = m_self.p_desc.value.strip()
                    prod_bonus = m_self.p_bonus.value.strip()
                    shop_title = f"{comp_name}旗艦店"

                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("""
                            INSERT INTO shop_items (guild_id, shop_name, name, price, description, stat_bonus, affinity_bonus, usable, seller)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                        """, (g_id, shop_title, prod_name, price, prod_desc, prod_bonus, aff, comp_name))
                        await db.commit()

                    await m_inter.response.send_message(
                        f"🎉 成功在【{shop_title}】上架新商品！\n"
                        f"📦 商品：**{prod_name}** ｜ 單價：**${price:,}**\n"
                        f"全服成員已可在 `/商城` 中購買，收益將自動匯入公司金庫！"
                    )
            await inter.response.send_modal(AddProductModal())

        async def withdraw_cb(inter: discord.Interaction):
            class WithdrawModal(discord.ui.Modal, title=f"提領【{comp_name}】營運盈餘"):
                amount_input = discord.ui.TextInput(label=f"提領金額 (金庫儲備: ${balance:,})", placeholder="輸入轉入個人銀行的金額")

                async def on_submit(m_self, m_inter: discord.Interaction):
                    try:
                        amt = int(m_self.amount_input.value.strip())
                        if amt <= 0 or amt > balance: raise ValueError
                    except ValueError:
                        await m_inter.response.send_message(f"❌ 請輸入小於金庫儲備 (${balance:,}) 的有效金額！", ephemeral=True)
                        return

                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("UPDATE companies SET balance = balance - ? WHERE id = ?", (amt, comp_id))
                        await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (amt, g_id, my_char))
                        await db.commit()
                    await m_inter.response.send_message(f"💰 成功提領 **${amt:,}** 至負責人 **{my_char}** 的個人銀行！")
            await inter.response.send_modal(WithdrawModal())

        btn_run.callback = run_cb
        btn_rule.callback = rule_cb
        btn_shop.callback = shop_cb
        btn_withdraw.callback = withdraw_cb

        view.add_item(btn_run)
        view.add_item(btn_shop)
        view.add_item(btn_withdraw)
        view.add_item(btn_rule)

        embed = discord.Embed(title=f"🏢 名下企業控制台：【{comp_name}】", color=0x2ECC71)
        embed.description = (
            f"• 法定代表人：**{my_char}**\n"
            f"• 公司金庫總儲備：**${balance:,}**\n"
            f"• 員工分成比率：`{int(split_ratio*100)}%`\n"
            f"• 招募職業門檻：`{allowed_jobs or '全職業開放'}`"
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(f"ℹ️ 角色 **{my_char}** 目前名下無自主創立的公司。", ephemeral=True)

# -------------------- 指令：/商城 --------------------
@bot.tree.command(name="商城", description="進入商城選單購買官方好物、公司獨家商品或二手珍品")
@app_commands.describe(角色名="欲進入商城選購的角色名稱")
async def shop(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            if not await cur.fetchone():
                await interaction.response.send_message("❌ 查無此角色檔案！", ephemeral=True)
                return

        async with db.execute("SELECT DISTINCT shop_name FROM shop_items WHERE guild_id = ?", (g_id,)) as cur:
            shops = [row[0] for row in await cur.fetchall()]

    for default_s in ["官方商城", "票務系統", "二手"]:
        if default_s not in shops:
            shops.append(default_s)

    class BuyItemSelect(discord.ui.Select):
        def __init__(self, shop_name: str, items: list):
            self.shop_name = shop_name
            options = [
                discord.SelectOption(
                    label=f"{it[1]} (${it[2]:,})",
                    value=str(it[0]),
                    description=it[3][:50] if it[3] else "熱銷好物"
                ) for it in items[:25]
            ]
            super().__init__(placeholder=f"請挑選【{shop_name}】欲購買的商品...", options=options)

        async def callback(self, s_inter: discord.Interaction):
            item_id = int(self.values[0])
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT name, price, seller, stat_bonus FROM shop_items WHERE id = ?", (item_id,)) as cur:
                    it_row = await cur.fetchone()
                if not it_row:
                    await s_inter.response.send_message("❌ 該商品已售罄或下架！", ephemeral=True)
                    return

                i_name, price, seller, stat_bonus = it_row

                async with db.execute("SELECT cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
                    char_row = await cur.fetchone()
                    cash, bank = char_row

                if cash + bank < price:
                    await s_inter.response.send_message(f"❌ 餘額不足！購買【{i_name}】需 ${price:,}，你手頭與存款總額不足以支付。", ephemeral=True)
                    return

                if cash >= price:
                    await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (price, g_id, c_name))
                else:
                    remain = price - cash
                    await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (remain, g_id, c_name))

                seller_info = ""
                async with db.execute("SELECT id FROM companies WHERE guild_id = ? AND name = ?", (g_id, seller)) as c_cur:
                    comp_match = await c_cur.fetchone()

                if comp_match:
                    await db.execute("UPDATE companies SET balance = balance + ? WHERE id = ?", (price, comp_match[0]))
                    seller_info = f"\n🏢 貨款 **${price:,}** 已全額匯入【**{seller}**】公司金庫！"
                elif seller != "官方":
                    await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (price, g_id, seller))
                    await db.execute("DELETE FROM shop_items WHERE id = ?", (item_id,))
                    seller_info = f"\n🏷️ 貨款已轉入原賣家 **{seller}** 銀行帳戶！"

                async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, c_name, i_name)) as cur:
                    inv_row = await cur.fetchone()
                    if inv_row:
                        await db.execute("UPDATE inventory SET amount = amount + 1 WHERE id = ?", (inv_row[0],))
                    else:
                        await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, 1, ?)", (g_id, c_name, i_name, f"購入自({seller})"))

                await db.commit()

            await s_inter.response.send_message(f"🛍️ 購買成功！**{c_name}** 購得 **{i_name}**（扣款 ${price:,}），物品已放入個人背包，隨時可使用或贈予！{seller_info}")

    class ShopSelectView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            for shop_title in shops[:20]:
                btn = discord.ui.Button(label=shop_title[:20], style=discord.ButtonStyle.primary)
                btn.callback = self.make_cb(shop_title)
                self.add_item(btn)

        def make_cb(self, s_name):
            async def cb(inter: discord.Interaction):
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT id, name, price, description, stat_bonus FROM shop_items WHERE guild_id = ? AND shop_name = ?", (g_id, s_name)) as cur:
                        items = await cur.fetchall()

                if not items:
                    await inter.response.send_message(f"🏪 專區【{s_name}】目前暫無上架商品。", ephemeral=True)
                    return

                sub_view = discord.ui.View()
                sub_view.add_item(BuyItemSelect(s_name, items))
                embed = discord.Embed(title=f"🏪 商城專區 — 【{s_name}】", description=f"歡迎光臨！請自下方選單挑選商品：", color=0xF39C12)
                for it in items[:10]:
                    embed.add_field(name=f"📦 {it[1]} — ${it[2]:,}", value=f"簡介: {it[3]}\n效果: {it[4] or '無加成'}", inline=False)
                await inter.response.send_message(embed=embed, view=sub_view, ephemeral=True)
            return cb

    await interaction.response.send_message(f"🏬 請點選進入欲光顧的商城專區：", view=ShopSelectView(), ephemeral=True)

# -------------------- 指令：/售物 --------------------
@bot.tree.command(name="售物", description="將背包物品或個人創作作品上架至【二手】商城販售（作品售價受才智影響）")
@app_commands.choices(物品類型=[
    app_commands.Choice(name="一般二手物品 / 禮品", value="general"),
    app_commands.Choice(name="個人創作作品 (劇本/單曲/版權)", value="creation")
])
@app_commands.describe(
    賣家角色名="持有該物品並進行販售的角色姓名",
    物品名稱="背包中欲出售的物品名稱",
    定價="販售單價 (純整數)",
    物品類型="選擇一般物品或原創作品",
    物品介紹="【選填】自訂二手/作品商品描述"
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
        await interaction.response.send_message("❌ 販售定價必須為正整數！", ephemeral=True)
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

        if current_amount > 1:
            await db.execute("UPDATE inventory SET amount = amount - 1 WHERE id = ?", (inv_id,))
        else:
            await db.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))

        await db.execute("""
            INSERT INTO shop_items (guild_id, shop_name, name, price, description, stat_bonus, affinity_bonus, usable, seller)
            VALUES (?, '二手', ?, ?, ?, '', 0, 1, ?)
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
# -------------------- 指令：/暗算 --------------------
@bot.tree.command(name="暗算", description="對競爭對手買黑通稿或暗算（掠奪影響指數，但若被對方才智識破將遭全網反噬）")
@app_commands.describe(發起角色="你的角色名稱", 目標角色="欲暗算的競爭對手姓名")
async def backstab_cmd(interaction: discord.Interaction, 發起角色: str, 目標角色: str):
    g_id = interaction.guild_id
    a_name, t_name = 發起角色.strip(), 目標角色.strip()

    if a_name == t_name:
        await interaction.response.send_message("❌ 你無法暗算自己！", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT stats, user_id FROM characters WHERE guild_id = ? AND name = ?", (g_id, a_name)) as cur:
            a_row = await cur.fetchone()
        async with db.execute("SELECT stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, t_name)) as cur:
            t_row = await cur.fetchone()

        if not a_row or not t_row:
            await interaction.response.send_message("❌ 查無發起方或目標角色！", ephemeral=True)
            return

        a_stats = json.loads(a_row[0]) if a_row[0] else {}
        t_stats = json.loads(t_row[0]) if t_row[0] else {}

        t_intellect = t_stats.get("才智", 50)
        is_detected = random.random() < min(0.90, (t_intellect * 0.008))

        if is_detected:
            penalty_inf = int(a_stats.get("影響指數", 100) * 0.15)
            a_stats["影響指數"] = max(0, a_stats.get("影響指數", 100) - penalty_inf)
            a_stats["活躍黑粉數"] = a_stats.get("活躍黑粉數", 0) + 500
            t_stats["路人緣"] = t_stats.get("路人緣", 50) + 30

            await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(a_stats, ensure_ascii=False), g_id, a_name))
            await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(t_stats, ensure_ascii=False), g_id, t_name))
            await db.commit()

            embed = discord.Embed(title="🛡️ 暗算失敗！對家才智過人，當場識破！", color=0xE74C3C)
            embed.description = (
                f"**{a_name}** 試圖暗算 **{t_name}**，但被 **{t_name}** 憑藉才智（{t_intellect}）識破！\n\n"
                f"• **{a_name}** 影響指數 **-{penalty_inf}**、活躍黑粉 **+500**！\n"
                f"• **{t_name}** 獲得同情，路人緣 **+30**！"
            )
            await interaction.response.send_message(embed=embed)
        else:
            stolen_inf = int(t_stats.get("影響指數", 100) * 0.10)
            t_stats["影響指數"] = max(0, t_stats.get("影響指數", 100) - stolen_inf)
            a_stats["影響指數"] = a_stats.get("影響指數", 100) + stolen_inf
            t_stats["活躍黑粉數"] = t_stats.get("活躍黑粉數", 0) + 300

            await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(a_stats, ensure_ascii=False), g_id, a_name))
            await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(t_stats, ensure_ascii=False), g_id, t_name))
            await db.commit()

            embed = discord.Embed(title="🗡️ 暗算得手！榜單爭頂籌碼已掠奪！", color=0x2C3E50)
            embed.description = (
                f"**{a_name}** 成功引導輿論暗算 **{t_name}**！\n\n"
                f"• 掠奪目標影響指數：**+{stolen_inf}** 點！\n"
                f"• **{t_name}** 活躍黑粉 **+300**！"
            )
            await interaction.response.send_message(embed=embed)

# -------------------- 指令：/危機公關 --------------------
@bot.tree.command(name="危機公關", description="撤除負面熱搜、清洗黑粉與止血（公關數值決定消耗資金）")
@app_commands.describe(角色名="欲進行危機公關的角色名稱")
async def crisis_pr_cmd(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT cash, bank, stats, user_id FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            row = await cur.fetchone()
        if not row:
            await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
            return

        cash, bank, stats_json, u_id = row
        stats = json.loads(stats_json) if stats_json else {}
        pr_val = stats.get("公關", 50)
        haters = stats.get("活躍黑粉數", 0)

        cost = int(50000 * 0.5) if pr_val >= 80 else (int(50000 * 2.0) if pr_val < 40 else 50000)

        if cash + bank < cost:
            await interaction.response.send_message(f"❌ 資金不足！當前公關數值 `{pr_val}`，撤熱搜需消耗 **${cost:,}**！", ephemeral=True)
            return

        if cash >= cost:
            await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (cost, g_id, c_name))
        else:
            await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (cost - cash, g_id, c_name))

        cleaned_haters = haters // 2
        stats["活躍黑粉數"] = haters - cleaned_haters
        stats["路人緣"] = stats.get("路人緣", 50) + 20

        await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(stats, ensure_ascii=False), g_id, c_name))
        await db.commit()

    pr_status = "優秀 (享 50% 折扣)" if pr_val >= 80 else ("低下 (遭加倍收費)" if pr_val < 40 else "正常")
    embed = discord.Embed(title=f"🕊️ 危機公關止血完畢：【{c_name}】", color=0x3498DB)
    embed.description = (
        f"• 公關團隊評級：`{pr_status}`\n"
        f"• 撤熱搜與洗白總花費：**${cost:,}**\n"
        f"• 清洗活躍黑粉：**-{cleaned_haters:,}** 人\n"
        f"• 路人緣修復：**+20** 點（當前：`{stats['路人緣']}`）"
    )
    await interaction.response.send_message(embed=embed)

# -------------------- 指令：/贈予（含同國籍 35% 好感暴擊） --------------------
@bot.tree.command(name="贈予", description="將背包道具轉交給其他角色或 NPC（遇同國籍有概率額外激增好感度）")
@app_commands.describe(角色名="轉出道具的自己角色", 對象名="接收道具的對象名稱", 物品名="贈送的物品名稱", 數量="贈送數量 (預設 1)")
async def gift_item(interaction: discord.Interaction, 角色名: str, 對象名: str, 物品名: str, 數量: int = 1):
    g_id = interaction.guild_id
    if 數量 <= 0:
        await interaction.response.send_message("❌ 贈送數量必須大於 0！", ephemeral=True)
        return

    sender = 角色名.strip()
    receiver = 對象名.strip()
    i_name = 物品名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, nationality FROM characters WHERE guild_id = ? AND name = ?", (g_id, sender)) as cur:
            s_row = await cur.fetchone()
            if not s_row:
                await interaction.response.send_message(f"❌ 查無轉出角色【{sender}】！", ephemeral=True)
                return
            if s_row[0] != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 你只能為自己的角色操作道具！", ephemeral=True)
                return
            s_nat = s_row[1]

        async with db.execute("SELECT is_npc, nationality FROM characters WHERE guild_id = ? AND name = ?", (g_id, receiver)) as cur:
            r_row = await cur.fetchone()
            if not r_row:
                await interaction.response.send_message(f"❌ 查無接收對象【{receiver}】！", ephemeral=True)
                return
            is_npc_target = r_row[0] > 0
            r_nat = r_row[1]

        async with db.execute("SELECT id, amount FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, sender, i_name)) as cur:
            inv = await cur.fetchone()
            if not inv or inv[1] < 數量:
                await interaction.response.send_message(f"❌ 背包內【{i_name}】數量不足，無法贈送！", ephemeral=True)
                return
            inv_id, current_amt = inv

        if current_amt == 數量:
            await db.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
        else:
            await db.execute("UPDATE inventory SET amount = amount - ? WHERE id = ?", (數量, inv_id))

        async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, receiver, i_name)) as cur:
            r_inv = await cur.fetchone()
            if r_inv:
                await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (數量, r_inv[0]))
            else:
                await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, ?, ?)", (g_id, receiver, i_name, 數量, f"{sender} 贈送"))

        bonus_msg = ""
        compat_msg = ""
        extra_aff = 0
        if s_nat and r_nat and s_nat == r_nat and s_nat != "本國":
            if random.random() <= 0.35:
                extra_aff = random.randint(3, 8) * 數量
                compat_msg = f"\n🌏 **【同鄉眷顧】** 兩人皆來自【**{s_nat}**】，相談甚歡下羈絆額外 **+{extra_aff}**！"

        if is_npc_target:
            async with db.execute("SELECT affinity_bonus FROM shop_items WHERE guild_id = ? AND name = ?", (g_id, i_name)) as cur:
                aff_row = await cur.fetchone()
                base_aff = (aff_row[0] if (aff_row and aff_row[0] > 0) else 5) * 數量

            total_added_aff = base_aff + extra_aff
            await db.execute("""
                INSERT INTO relationships (guild_id, from_char, to_char, affection, status_desc)
                VALUES (?, ?, ?, ?, '深受感動')
                ON CONFLICT(guild_id, from_char, to_char) DO UPDATE SET affection = affection + ?, status_desc = '備受禮遇'
            """, (g_id, receiver, sender, total_added_aff, total_added_aff))
            bonus_msg = f"\n💖 官方 NPC **{receiver}** 對 **{sender}** 的好感度羈絆提升了 **+{total_added_aff}** 點！"

        await db.commit()

    await interaction.response.send_message(f"🎁 **{sender}** 成功將 **{i_name}** ×{數量} 贈送給了 **{receiver}**！{compat_msg}{bonus_msg}")

# -------------------- 指令：/使用（完整數值更新與寵物照料） --------------------
@bot.tree.command(name="使用", description="使用背包中的道具（自動更新角色屬性數值至個人檔案，可指定餵食照料寵物）")
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
        # 1. 驗證角色存在與操作權限
        async with db.execute("SELECT user_id, stats, ticket_ban_until FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()
            if not c_row:
                await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
                return
            u_id, stats_json, ticket_ban = c_row

        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 你只能為自己的角色使用道具！", ephemeral=True)
            return

        # 2. 檢驗背包存量
        async with db.execute("SELECT id, amount FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, c_name, i_name)) as cur:
            inv = await cur.fetchone()
            if not inv or inv[1] <= 0:
                await interaction.response.send_message(f"❌ 背包中查無道具【{i_name}】！", ephemeral=True)
                return
            inv_id, cur_amt = inv

        # 3. 計算本次使用數量
        if 使用數量.strip() in ["全部", "all", "All"]:
            use_cnt = cur_amt
        else:
            try:
                use_cnt = int(使用數量.strip())
                if use_cnt <= 0:
                    raise ValueError
            except ValueError:
                await interaction.response.send_message("❌ 請輸入正確的使用數量（純整數或填寫［全部］）！", ephemeral=True)
                return

        if use_cnt > cur_amt:
            await interaction.response.send_message(f"❌ 數量不足！背包中僅有 **{cur_amt}** 件【{i_name}】。", ephemeral=True)
            return

        # 4. 讀取道具效果（支援 stat_bonus 解析）
        async with db.execute("SELECT stat_bonus, usable, target_role_id FROM shop_items WHERE guild_id = ? AND name = ?", (g_id, i_name)) as cur:
            item_info = await cur.fetchone()

        stat_bonus = item_info[0] if (item_info and item_info[0]) else ""
        usable = item_info[1] if item_info else 1
        role_id = item_info[2] if item_info else 0

        if usable == 0:
            await interaction.response.send_message(f"ℹ️ 道具【{i_name}】為純收藏紀念品，無法直接使用。", ephemeral=True)
            return

        now = time.time()
        # 5. 地圖門票判定
        if role_id > 0:
            if now < ticket_ban:
                rem_h = int((ticket_ban - now) / 3600)
                await interaction.response.send_message(f"🚫 該角色先前曾逾期未歸，仍在禁令懲罰中！剩餘懲罰時間：**{rem_h}** 小時。", ephemeral=True)
                return

            role = interaction.guild.get_role(role_id)
            if role:
                try:
                    await interaction.user.add_roles(role, reason="使用大地圖門票出境")
                except Exception:
                    pass

            expire_at = now + (336 * 3600)
            await db.execute("""
                INSERT INTO active_tickets (guild_id, char_name, user_id, role_id, ticket_name, start_time, expire_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (g_id, c_name, interaction.user.id, role_id, i_name, now, expire_at))

        # 6. 扣除背包數量
        if use_cnt == cur_amt:
            await db.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
        else:
            await db.execute("UPDATE inventory SET amount = amount - ? WHERE id = ?", (use_cnt, inv_id))

        # 7. 寵物餵食回血處理
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
                    pet_heal_msg = f"\n🐾 寵物【**{p_name}**】吃飽喝足，健康值恢復至 **{new_h}/500** (+{heal_amt})！"

        # 8. 核心數值解析與確實更新至 characters.stats
        applied_stats = []
        char_stats = json.loads(stats_json) if stats_json else {}

        if stat_bonus:
            # 支援以逗號、頓號、空格分隔多項數值（例如: 容貌+10、商業價值+20、才智-5）
            for part in re.split(r"[,，、\s]+", stat_bonus.strip()):
                m = re.search(r"([^\d+-]+)([+-]?\d+)", part)
                if m:
                    s_name = m.group(1).strip()
                    s_delta = int(m.group(2)) * use_cnt
                    # 數值累加（最低為 0，避免出現負數屬性）
                    char_stats[s_name] = max(0, char_stats.get(s_name, 0) + s_delta)
                    sign = "+" if s_delta >= 0 else ""
                    applied_stats.append(f"{s_name} {sign}{s_delta} (現值: **{char_stats[s_name]}**)")

            # 確實寫入資料庫
            await db.execute(
                "UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?",
                (json.dumps(char_stats, ensure_ascii=False), g_id, c_name)
            )

        await db.commit()

    # 9. 檢查是否有觸發地位晉升門檻
    if applied_stats:
        await check_and_update_rank(g_id, c_name, interaction.channel)

    extra_msg = f"\n🎫 已啟用外地簽證身分組！有效停留時間為 **336 小時（兩週）**，請記得在期限前使用 `/返回原本地圖`！" if role_id > 0 else ""
    bonus_msg = f"\n📊 **【角色屬性即時成長】**\n• " + "\n• ".join(applied_stats) if applied_stats else ""

    await interaction.response.send_message(
        f"✨ **{c_name}** 成功使用了道具【**{i_name}**】×{use_cnt}！{bonus_msg}{extra_msg}{pet_heal_msg}"
    )

# -------------------- 指令：/檔案總覽 --------------------
class MasterDirectoryView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id

    @discord.ui.button(label="📜 一般指令", style=discord.ButtonStyle.primary, row=0)
    async def cmd_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        text = (
            "**👤 玩家常規指令列表：**\n"
            "• `/檔案建立`：建立玩家角色或玩家自設 NPC\n"
            "• `/查看`：調閱個人角色或任何 NPC 面板、寵物與傳聞\n"
            "• `/背包`、`/使用`、`/贈予`：道具資產管理與送禮增加好感\n"
            "• `/商城`、`/售物`：選購官方/二手/各公司門市商品\n"
            "• `/存錢`、`/取錢`、`/轉錢`：銀行金融交易與角色互轉\n"
            "• `/任務`、`/回報任務`：查看公告任務、回報文章與獲取獎勵\n"
            "• `/陣營`：查看所屬陣營、捐獻公款、購買全體加成或退陣\n"
            "• `/排行查詢`：查閱各大實力榜單或個人名次\n"
            "• `/寵物購買`、`/喪禮結算`：認養毛小孩與身後悼念結算"
        )
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="🛡️ 管理員指令", style=discord.ButtonStyle.danger, row=0)
    async def cmd_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        text = (
            "**👑 管理員專用指令列表：**\n"
            "• `/官方npc登記`：登記全域官方重要 NPC\n"
            "• `/大眾路人大量發生中`：全自動抽選姓名、立繪、數值生成路人\n"
            "• `/路人資源補給`：補充路人相冊與姓名、作品、代言庫\n"
            "• `/路人生態設定`：設定路人每 48 小時屬性與金錢浮動規則\n"
            "• `/數值登記`：加減數值、自訂新增數值類型、管理隱藏數值\n"
            "• `/任務新增`：發布各類別任務、成就、榮譽與認知度限制\n"
            "• `/地位等級限制`：設定地位順位與晉級標準門檻\n"
            "• `/發布傳聞`：寫下一句傳聞，自動統計累積 3 次貼新標籤"
        )
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="👑 官方角色", style=discord.ButtonStyle.success, row=0)
    async def view_official(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name, age, gender, job FROM characters WHERE guild_id = ? AND is_npc = 1", (self.guild_id,)) as cur:
                rows = await cur.fetchall()
        lines = [f"• **{r[0]}** ({r[1]}歲 / {r[2]}) ｜ {r[3]}" for r in rows]
        embed = discord.Embed(title="👑 官方 NPC 名冊", description="\n".join(lines) if lines else "暫無官方 NPC", color=0x9B59B6)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎭 大眾路人", style=discord.ButtonStyle.secondary, row=1)
    async def view_crowd(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name, nationality, age, gender, job FROM characters WHERE guild_id = ? AND is_npc = 3 LIMIT 25", (self.guild_id,)) as cur:
                rows = await cur.fetchall()
        lines = [f"• **{r[0]}** [{r[1]}] ({r[2]}歲 / {r[3]}) ｜ {r[4]}" for r in rows]
        embed = discord.Embed(title="🎭 大眾動態路人清單 (前 25 名)", description="\n".join(lines) if lines else "暫無大眾路人", color=0x1ABC9C)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="👥 玩家名錄", style=discord.ButtonStyle.primary, row=1)
    async def view_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name, is_npc, job, rank FROM characters WHERE guild_id = ? AND is_npc IN (0, 2)", (self.guild_id,)) as cur:
                rows = await cur.fetchall()
        lines = [f"• **{name}**{' `[自設NPC]`' if is_npc == 2 else ''} ｜ 職業: {job} ｜ 地位: 【{rank}】" for name, is_npc, job, rank in rows]
        embed = discord.Embed(title="👥 全體玩家與自設角色名錄", description="\n".join(lines) if lines else "暫無玩家建檔", color=0x3498DB)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🏷️ 標籤彙整", style=discord.ButtonStyle.secondary, row=1)
    async def view_all_tags(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🏷️ 全體特色標籤一覽表", color=0xF39C12)
        embed.add_field(name="全體通用特質", value="、".join(UNIVERSAL_TAGS), inline=False)
        embed.add_field(name="性別與年齡限定", value="少年感 (男<=25)、老幹部 (>=30)、百億少年的夢 (女<=30)、國民初戀/國民弟弟/國民妹妹/國民兒女", inline=False)
        embed.add_field(name="互斥衝突組", value="濃顏 ⇄ 淡顏 ｜ 社恐 ⇄ 社交悍匪 ｜ 文盲 ⇄ 人間清醒 ｜ 花瓶 ⇄ 劇拋臉", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="檔案總覽", description="調閱全系統分類導航總目錄（指令、官方角、路人、玩家、標籤）")
async def master_overview_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📑 系統檔案與指令整合導航中心", description="請點選下方按鈕切換查閱各項名冊、指引與標籤規則：", color=0x2C3E50)
    await interaction.response.send_message(embed=embed, view=MasterDirectoryView(interaction.guild_id), ephemeral=True)

# -------------------- 指令：/數值登記 --------------------
@bot.tree.command(name="數值登記", description="為角色/NPC登記數值，管理員更可新增數值類型或切換隱藏設定")
@app_commands.choices(操作=[
    app_commands.Choice(name="常規數值增減 (一般操作)", value="adjust"),
    app_commands.Choice(name="【管理員】新增全域自訂數值類型", value="add_type"),
    app_commands.Choice(name="【管理員】隱藏/取消隱藏特定數值", value="toggle_hide")
])
@app_commands.describe(
    操作="選擇執行的動作",
    名字="角色或 NPC 姓名 (常規調整必填)",
    數值調整串="常規調整用 (例如: 死忠粉絲數+1000、大眾認知度+200、活躍黑粉數-50)",
    新增數值名稱="【管理員新增類型用】欲全域新增的數值名稱",
    隱藏數值名稱="【管理員隱藏設定用】輸入欲隱藏的數值 (例如: 活躍黑粉數)"
)
async def register_stats_multi(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    名字: str = None,
    數值調整串: str = None,
    新增數值名稱: str = None,
    隱藏數值名稱: str = None
):
    g_id = interaction.guild_id
    is_admin = interaction.user.guild_permissions.administrator
    op = 操作.value

    if op == "add_type":
        if not is_admin:
            await interaction.response.send_message("🚫 只有管理員可以新增數值類型！", ephemeral=True)
            return
        if not 新增數值名稱:
            await interaction.response.send_message("❌ 請填寫【新增數值名稱】！", ephemeral=True)
            return
        t_name = 新增數值名稱.strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'custom_stat_types'", (g_id,)) as cur:
                row = await cur.fetchone()
                type_list = json.loads(row[0]) if row else []
            if t_name not in type_list:
                type_list.append(t_name)
                await db.execute("INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'custom_stat_types', ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = ?", (g_id, json.dumps(type_list, ensure_ascii=False), json.dumps(type_list, ensure_ascii=False)))
                await db.commit()
        await interaction.response.send_message(f"✅ 已成功登記全新數值類型：【**{t_name}**】！", ephemeral=True)
        return

    if op == "toggle_hide":
        if not is_admin:
            await interaction.response.send_message("🚫 只有管理員可以調整數值顯示/隱藏狀態！", ephemeral=True)
            return
        if not 隱藏數值名稱:
            await interaction.response.send_message("❌ 請填寫【隱藏數值名稱】！", ephemeral=True)
            return
        h_name = 隱藏數值名稱.strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'hidden_stats'", (g_id,)) as cur:
                row = await cur.fetchone()
                hidden_list = json.loads(row[0]) if row else []

            if h_name in hidden_list:
                hidden_list.remove(h_name)
                msg = f"👁️ 已將數值【**{h_name}**】恢復為公開顯示！"
            else:
                hidden_list.append(h_name)
                msg = f"🔒 已將數值【**{h_name}**】設定為隱藏！"

            await db.execute("INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'hidden_stats', ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = ?", (g_id, json.dumps(hidden_list, ensure_ascii=False), json.dumps(hidden_list, ensure_ascii=False)))
            await db.commit()
        await interaction.response.send_message(msg, ephemeral=True)
        return

    if not 名字 or not 數值調整串:
        await interaction.response.send_message("❌ 請填寫【名字】與【數值調整串】！", ephemeral=True)
        return

    target_name = 名字.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
            row = await cur.fetchone()
        if not row:
            await interaction.response.send_message(f"❌ 查無【{target_name}】！", ephemeral=True)
            return

        u_id, stats_json = row
        if not is_admin and u_id != interaction.user.id:
            await interaction.response.send_message("❌ 你無權操作此角色數值！", ephemeral=True)
            return

        char_stats = json.loads(stats_json) if stats_json else {}
        changes = []
        for part in re.split(r"[,，、\s]+", 數值調整串.strip()):
            m = re.search(r"([^\d+-]+)([+-]?\d+)", part)
            if m:
                s_name = m.group(1).strip()
                s_delta = int(m.group(2))
                char_stats[s_name] = max(0, char_stats.get(s_name, 0) + s_delta)
                sign = "+" if s_delta >= 0 else ""
                changes.append(f"{s_name} {sign}{s_delta}")

        await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(char_stats, ensure_ascii=False), g_id, target_name))
        await db.commit()

    await check_and_update_rank(g_id, target_name, interaction.channel)
    await interaction.response.send_message(f"✅ 【{target_name}】數值更新完畢：`{'、'.join(changes)}`！")

# -------------------- 指令：/新增抽獎 --------------------
@bot.tree.command(name="新增抽獎", description="【管理員專用】新增抽獎池（支援以 物品*數量 一口氣設定獎項）")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(獎品可否重複=[
    app_commands.Choice(name="是（無限抽）", value="yes"),
    app_commands.Choice(name="否（抽完為止/限抽一次）", value="no")
])
@app_commands.describe(
    獎項="抽獎池名稱（玩家必須在同名的討論串/帖子中抽獎）",
    獎品內容="格式：物品*數量，可填寫多項（例如: 包子*5 饅頭*5 飯糰*5）",
    獎品可否重複="選擇獎品是否可重複抽取",
    可抽獎的身分組="【選填】限制特定身分組方可參與抽獎"
)
async def add_lottery_cmd(
    interaction: discord.Interaction,
    獎項: str,
    獎品內容: str,
    獎品可否重複: app_commands.Choice[str],
    可抽獎的身分組: discord.Role = None
):
    g_id = interaction.guild_id
    pool_name = 獎項.strip()
    raw_content = 獎品內容.strip()

    parsed_items = []
    tokens = re.split(r"[,，\n\r\s]+", raw_content)
    for token in tokens:
        if not token:
            continue
        match = re.match(r"^([^*xX×]+)(?:[*xX×](\d+))?$", token)
        if match:
            item_name = match.group(1).strip()
            amount = int(match.group(2)) if match.group(2) else 1
            parsed_items.append({"name": item_name, "amount": amount})
        else:
            parsed_items.append({"name": token.strip(), "amount": 1})

    if not parsed_items:
        await interaction.response.send_message("❌ 請至少輸入一項有效的獎品內容！格式範例：`饅頭*5 包子*5 飯糰*5`", ephemeral=True)
        return

    display_prizes = " ".join([f"{it['name']}×{it['amount']}" if it['amount'] > 1 else it['name'] for it in parsed_items])
    role_desc = 可抽獎的身分組.mention if 可抽獎的身分組 else "全體無限制"
    repeat_desc = "是（無限抽）" if 獎品可否重複.value == "yes" else "否（抽完即止）"
    role_id = 可抽獎的身分組.id if 可抽獎的身分組 else 0

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO lottery_pools (guild_id, pool_name, items_json, allow_repeat, role_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, pool_name) DO UPDATE SET
                items_json = excluded.items_json,
                allow_repeat = excluded.allow_repeat,
                role_id = excluded.role_id
        """, (g_id, pool_name, json.dumps(parsed_items, ensure_ascii=False), 獎品可否重複.value, role_id))
        await db.commit()

    embed = discord.Embed(color=0xE74C3C)
    embed.description = (
        f"**{pool_name}**\n"
        f"**獎品內容**\n"
        f"{display_prizes}\n"
        f"**抽獎資格**\n"
        f"{role_desc}\n"
        f"**可否重複**\n"
        f"{repeat_desc}\n\n"
        f"提示：請至同名討論串【{pool_name}】中輸入 `/我要抽獎`"
    )
    await interaction.response.send_message(embed=embed)

# -------------------- 啟動與全域同步（含 Token 嚴格防呆） --------------------
@bot.event
async def on_ready():
    await init_db()

    if not daily_interest.is_running(): daily_interest.start()
    if not monthly_age_up.is_running(): monthly_age_up.start()
    if not check_ticket_expiration.is_running(): check_ticket_expiration.start()
    if not daily_pet_routine.is_running(): daily_pet_routine.start()
    if not crowd_npc_fluctuation_task.is_running(): crowd_npc_fluctuation_task.start()
    if not weekly_fans_and_haters_settlement.is_running(): weekly_fans_and_haters_settlement.start()

    try:
        synced = await bot.tree.sync()
        print(f"====================================")
        print(f"🎉 成功同步了 {len(synced)} 個 Slash 指令！")
        for cmd in synced:
            print(f"📌 指令: /{cmd.name}")
        print(f"====================================")
    except Exception as e:
        print(f"❌ 指令同步失敗: {e}")

    print(f"系統核心已順利就緒：{bot.user}")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ 錯誤：未偵測到環境變數 DISCORD_TOKEN！請至雲端平台後台的 Environment 設定中填寫正確的 Bot Token。")
    sys.exit(1)

try:
    bot.run(TOKEN)
except Exception as e:
    print(f"❌ 機器人啟動崩潰: {e}")
    traceback.print_exc()
    sys.exit(1)
