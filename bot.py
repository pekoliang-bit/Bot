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
# -------------------- 擴充標籤庫（正面、負面、風格） --------------------
UNIVERSAL_TAGS = [
    # 原有特質
    "初戀臉", "厭世感", "舞台匠人", "釣系", "全能天才", "天籟蜜嗓", 
    "極致反差", "低音砲", "古典氣質", "漫撕人", "高嶺之花", "元氣犬系",
    "性感", "緋聞纏身", "濃顏", "淡顏", "臉蛋天才", "社恐", "社交悍匪", 
    "人間清醒", "毒舌", "劇拋臉", "鬆弛感", "文盲", "花瓶",
    # 擴充特質（百億少年的夢已移入男女通用無年齡限制）
    "百億少年的夢", "天選之子", "清冷白月光", "建模臉", "劇本殺手", "氛圍感", "事業腦", "戀愛腦",
    # 擴充負面特質
    "九漏魚", "糊咖", "加戲咖", "塌房預備役", "作精", "營銷咖"
]

# 性別與年齡限定標籤（少年感、老幹部、國民系列）
GENDER_AGE_TAGS = {
    "少年感": lambda age, gen: gen == "男" and age <= 25,
    "老幹部": lambda age, gen: age >= 30,
    "國民初戀": lambda age, gen: gen == "女" and age <= 24,
    "國民弟弟": lambda age, gen: gen == "男" and age <= 22,
    "國民妹妹": lambda age, gen: gen == "女" and age <= 22,
    "國民兒子": lambda age, gen: gen == "男" and age <= 28,
    "國民女兒": lambda age, gen: gen == "女" and age <= 28,
}

# 擴充互斥衝突組
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
    # -------------------- 社群貼圖與留言即時監聽 --------------------
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id or not payload.guild_id:
        return

    g_id = payload.guild_id
    ch_id = payload.channel_id
    emoji_str = str(payload.emoji)

    async with aiosqlite.connect(DB_PATH) as db:
        # 檢查該頻道或其父討論串是否在監聽名單
        async with db.execute("SELECT platform_name FROM social_monitor_channels WHERE guild_id = ? AND channel_id = ?", (g_id, ch_id)) as cur:
            ch_match = await cur.fetchone()

        if not ch_match:
            # 檢查 thread parent
            ch = bot.get_channel(ch_id)
            if hasattr(ch, "parent_id") and ch.parent_id:
                async with db.execute("SELECT platform_name FROM social_monitor_channels WHERE guild_id = ? AND channel_id = ?", (g_id, ch.parent_id)) as p_cur:
                    ch_match = await p_cur.fetchone()

        if not ch_match:
            return

        # 查詢表情對應規則
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

# -------------------- 色彩、身材檢驗與分頁視窗 --------------------
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
        warn_text = f"⚠️ BMI 嚴重偏低（{bmi}，過輕偏瘦），初始健康值 -20、容貌 -15。"
    elif bmi > 28.0:
        health_penalty, app_penalty = 20, 15
        warn_text = f"⚠️ BMI 嚴重偏高（{bmi}，體態超標），初始健康值 -20、容貌 -15。"
    return max(10, base_health - health_penalty), max(10, base_appearance - app_penalty), bmi, warn_text

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
# -------------------- 演藝生態核心輔助函式 --------------------
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
# -------------------- 第 7 段：資料庫完整初始化（完整 23 張獨立資料表） --------------------
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
                faction_name TEXT DEFAULT ''
            )
        """)

        # 4. 可購置車輛與房產名冊表
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

        # 5. 個人固定資產產權表
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

        # 6. 人際關係網絡與好感表
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

        # 8. 人設單連結審核紀錄表（原版相容）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                guild_id INTEGER,
                message_link TEXT,
                char_name TEXT,
                audit_count INTEGER DEFAULT 1,
                PRIMARY KEY (guild_id, message_link)
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

        # 10. 陣營勢力總表
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

        # 11. 陣營成員表
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

        # 12. 陣營作品抽稅紀錄表
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

        # 13. 任務總表
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

        # 14. 任務完成歷程紀錄表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quest_completions (
                guild_id INTEGER,
                char_name TEXT,
                quest_title TEXT,
                completed_at REAL,
                PRIMARY KEY (guild_id, char_name, quest_title)
            )
        """)

        # 15. 地位等級限制與門檻表
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

        # 16. 排行榜公式表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leaderboards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                name TEXT,
                stat_key TEXT
            )
        """)

        # 17. 抽獎活動池表
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

        # 18. 門票外地簽證追蹤表
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

        # 19. 路人專用相冊庫
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crowd_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                image_url TEXT,
                gender TEXT DEFAULT '通用',
                used INTEGER DEFAULT 0
            )
        """)

        # 20. 路人姓名資源庫
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

        # 21. 路人影視綜藝作品角色席位庫
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

        # 22. 路人品牌代言榮譽庫
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

        # 23. 討論串審核二次進度表
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

        # 24. 傳聞歷史紀錄表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS character_rumors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                char_name TEXT,
                rumor_text TEXT,
                created_at REAL
            )
        """)

        # 25. 寵物檔案表
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
        # 26. 劇情劇本設定表
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

        # 27. 玩家劇情攻略進度與次數記錄
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

        # 28. 社交平台監聽頻道設定表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS social_monitor_channels (
                guild_id INTEGER,
                channel_id INTEGER PRIMARY KEY,
                platform_name TEXT DEFAULT '社群動態'
            )
        """)

        # 29. 社交符號與關鍵字結算規則表
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

        # 30. 社交平台關注與拉黑追蹤表
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

# -------------------- 定時排程 A --------------------
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
# -------------------- 定時排程 B --------------------
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
# -------------------- 訊息監聽與結算調整 --------------------
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

# -------------------- 指令：/結算調整 --------------------
@bot.tree.command(name="結算調整", description="【管理員專用】自訂字數計算規則、貨幣單位與兌換比率")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(計算內容=[
    app_commands.Choice(name="中文字加標點符號 (預設)", value="chinese_punct"),
    app_commands.Choice(name="僅中文字", value="chinese_only"),
    app_commands.Choice(name="中文字加英文字", value="chinese_english"),
    app_commands.Choice(name="全部（含所有語言文字、符號、標點）", value="all"),
])
@app_commands.describe(
    計算內容="選擇艾特結算時的統計模式",
    貨幣單位="自訂金錢單位（例如：元、銀子、銅錢，預設為元）",
    一字折合金錢="設定每 1 字可換得多少金錢 (例如: 1 或 0.5，預設 1)"
)
async def adjust_word_settlement(
    interaction: discord.Interaction,
    計算內容: app_commands.Choice[str],
    貨幣單位: str = "元",
    一字折合金錢: float = 1.0
):
    g_id = interaction.guild_id
    if 一字折合金錢 <= 0:
        await interaction.response.send_message("❌ 折合金錢比率需大於 0！", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'word_calc_mode', ?)
            ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
        """, (g_id, 計算內容.value, 計算內容.value))

        await db.execute("""
            INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'currency_unit', ?)
            ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
        """, (g_id, 貨幣單位.strip(), 貨幣單位.strip()))

        await db.execute("""
            INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'word_money_ratio', ?)
            ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
        """, (g_id, str(一字折合金錢), str(一字折合金錢)))
        await db.commit()

    embed = discord.Embed(title="⚙️ 討論串字數結算規則已更新", color=0x2ECC71)
    embed.add_field(name="計算模式", value=f"【{計算內容.name}】", inline=False)
    embed.add_field(name="貨幣單位", value=f"【{貨幣單位.strip()}】", inline=True)
    embed.add_field(name="換算比率", value=f"每 1 字 = {一字折合金錢} {貨幣單位.strip()}", inline=True)
    await interaction.response.send_message(embed=embed)
    # -------------------- Webhook 角色代發與劇本解析 --------------------
async def send_npc_webhook_message(channel: discord.TextChannel, npc_name: str, avatar_url: str, content: str, view: discord.ui.View = None):
    """透過 Webhook 換上 NPC 頭像與名字說話"""
    # 討論串中需要向 parent channel 申請 Webhook
    target_channel = channel.parent if isinstance(channel, discord.Thread) else channel
    thread_to_send = channel if isinstance(channel, discord.Thread) else None

    webhooks = await target_channel.webhooks()
    hook = next((w for w in webhooks if w.name == "DramaEngine"), None)
    if not hook:
        hook = await target_channel.create_webhook(name="DramaEngine")

    # 發送帶頭像與名稱的角色扮演對話
    kwargs = {
        "content": content,
        "username": npc_name,
        "avatar_url": avatar_url if avatar_url.startswith("http") else None
    }
    if view:
        kwargs["view"] = view
    if thread_to_send:
        kwargs["thread"] = thread_to_send

    return await hook.send(**kwargs)

def parse_story_script_blocks(raw_text: str) -> list:
    """
    解析劇本格式：
    角色名字：劇情段落
    選擇按鈕—選項A關鍵字 / 選項B關鍵字
    選項A關鍵字：角色回應A
    選項B關鍵字：角色回應B
    """
    blocks = []
    # 依照按鈕分割段落
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    current_block = {"speaker": "", "text": "", "choices": {}}
    
    for line in lines:
        if line.startswith("選擇按鈕") or "—" in line and "選擇" in line:
            parts = re.split(r"[—\-:]+", line, 1)
            if len(parts) > 1:
                btn_tokens = re.split(r"[/,，\s]+", parts[1].strip())
                current_block["choices"] = {b.strip(): "" for b in btn_tokens if b.strip()}
        elif "：" in line or ":" in line:
            sp, txt = re.split(r"[:：]", line, 1)
            # 檢查是否為針對選擇按鈕的回應
            matched_btn = None
            for btn_key in current_block.get("choices", {}).keys():
                if btn_key in sp:
                    matched_btn = btn_key
                    break
            
            if matched_btn:
                current_block["choices"][matched_btn] = txt.strip()
            else:
                if current_block.get("text"):
                    blocks.append(current_block)
                    current_block = {"speaker": sp.strip(), "text": txt.strip(), "choices": {}}
                else:
                    current_block["speaker"] = sp.strip()
                    current_block["text"] = txt.strip()
    if current_block.get("text"):
        blocks.append(current_block)
    return blocks
# -------------------- 劇情分支互動按鈕 View --------------------
class StoryBranchView(discord.ui.View):
    def __init__(self, guild_id: int, char_name: str, npc_name: str, story_title: str, choices: dict, avatar_url: str):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.char_name = char_name
        self.npc_name = npc_name
        self.story_title = story_title
        self.choices = choices
        self.avatar_url = avatar_url

        for choice_label, response_text in choices.items():
            button = discord.ui.Button(label=choice_label, style=discord.ButtonStyle.primary)
            button.callback = self.make_choice_callback(choice_label, response_text)
            self.add_item(button)

    def make_choice_callback(self, label: str, resp_text: str):
        async def callback(interaction: discord.Interaction):
            async with aiosqlite.connect(DB_PATH) as db:
                # 結算與對象好感 +5
                await db.execute("""
                    INSERT INTO relationships (guild_id, from_char, to_char, affection, status_desc)
                    VALUES (?, ?, ?, 5, '共同回憶')
                    ON CONFLICT(guild_id, from_char, to_char) DO UPDATE SET affection = affection + 5
                """, (self.guild_id, self.npc_name, self.char_name))

                # 標記攻略完成
                await db.execute("""
                    INSERT INTO character_story_progress (guild_id, char_name, npc_name, story_title, completed)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(guild_id, char_name, npc_name, story_title) DO UPDATE SET completed = 1
                """, (self.guild_id, self.char_name, self.npc_name, self.story_title))
                await db.commit()

            # 停用按鈕並編輯原訊息
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(view=self)

            # NPC 使用頭像發布後續回應
            final_reply = resp_text if resp_text else f"（{self.npc_name} 讚許地看著你，點了點頭。）"
            await send_npc_webhook_message(
                interaction.channel,
                self.npc_name,
                self.avatar_url,
                f"**{final_reply}**\n\n*(✨ 劇情《{self.story_title}》順利通關！與【{self.npc_name}】的羈絆 +5)*"
            )

        return callback

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
                    placeholder="【步驟 1/2】請勾選個人特質標籤 (最多 2 個)...",
                    min_values=1,
                    max_values=min(2, len(tag_options)),
                    options=tag_options
                )

            async def callback(sub_self, inter: discord.Interaction):
                chosen = sub_self.values
                if len(chosen) == 2:
                    t1, t2 = chosen[0], chosen[1]
                    if t2 in TAG_CONFLICTS.get(t1, []):
                        await inter.response.send_message(f"❌ 標籤衝突！【{t1}】與【{t2}】互相對立，請重新選擇！", ephemeral=True)
                        return

                sub_self.view.selected_tags = chosen
                sub_self.view.setup_debut_step()
                await inter.response.edit_message(
                    content=f"🏷️ 已選定標籤：`{'、'.join(chosen)}`\n👇 請接著選擇【出道時長】（5~12歲童星出道將自動解鎖國民標籤）：",
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
                        kid_tag_msg = f"\n🎉 **童星身分認證！** 額外獲頒公認標籤：【`{kid_tag}`】"

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
    await interaction.response.send_message(
        content=f"👉 請點選下方選單，為 **{target_name}** 選擇個人特質標籤：",
        embed=embed,
        view=flow_view
    )
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
    await interaction.response.send_message(
        content=f"👉 請點選下方選單，為官方 NPC **{target_name}** 選擇特質標籤：",
        embed=embed,
        view=flow_view
    )
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
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ 查無檔案【{target_name}】！", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ 查無檔案【{target_name}】！", ephemeral=True)
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
    else:
        tag_prefix = "［個人角色］"

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
        for c in comps:
            asset_lines.append(f"• [旗下公司] {c[0]} ({c[1]})")
    embed.add_field(name="🚗 產權與名下企業", value="\n".join(asset_lines) if asset_lines else "名下尚無固定資產", inline=False)

    stats = json.loads(stats_json) if stats_json else {}
    stat_texts = [f"{k}: **{v}**" for k, v in stats.items() if k not in hidden_stats_set]
    embed.add_field(name="📊 核心演藝數值", value=" ｜ ".join(stat_texts) if stat_texts else "尚未登記任何公開數值", inline=False)

    if img_url and img_url.startswith("http"):
        embed.set_thumbnail(url=img_url)

    view = ProfileMainView(target_name, g_id)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=ephemeral)

# -------------------- 指令：/查看 --------------------
@bot.tree.command(name="查看", description="調閱自己持有的角色或自設 NPC 檔案面板（自動列出個人名下所有角色）")
async def view_char_cmd(interaction: discord.Interaction):
    g_id = interaction.guild_id
    u_id = interaction.user.id

    async with aiosqlite.connect(DB_PATH) as db:
        # 只撈取該使用者持有的「玩家角色(0)」與「自設NPC(2)」
        async with db.execute("""
            SELECT name, is_npc, job, rank FROM characters 
            WHERE guild_id = ? AND user_id = ? AND is_npc IN (0, 2)
            ORDER BY is_npc ASC, created_at ASC
        """, (g_id, u_id)) as cur:
            my_characters = await cur.fetchall()

    if not my_characters:
        await interaction.response.send_message("❌ 你在此伺服器尚未建立任何角色或自設 NPC！請先使用 `/檔案建立`。", ephemeral=True)
        return

    # 若名下只有 1 個角色，直接展示檔案
    if len(my_characters) == 1:
        await render_character_card(interaction, my_characters[0][0], ephemeral=False)
        return

    # 若有多個角色，彈出下拉選單讓玩家挑選
    class MyCharSelect(discord.ui.Select):
        def __init__(self):
            opts = [
                discord.SelectOption(
                    label=c[0],
                    description=f"[{'自設NPC' if c[1] == 2 else '玩家角色'}] {c[2]} ｜ 地位: 【{c[3]}】",
                    emoji="🎭" if c[1] == 2 else "👤",
                    value=c[0]
                ) for c in my_characters[:25]
            ]
            super().__init__(placeholder="請選擇欲調閱的角色或自設 NPC 檔案...", options=opts)

        async def callback(self, inter: discord.Interaction):
            await render_character_card(inter, self.values[0], ephemeral=False)

    view = discord.ui.View()
    view.add_item(MyCharSelect())
    await interaction.response.send_message("📋 偵測到你名下有多個角色檔案，請從下方選單選擇：", view=view, ephemeral=True)

# -------------------- ProfileMainView 增加攻略劇本按鈕 --------------------
# 請在 ProfileMainView 內加入以下按鈕（展示 NPC 專屬劇情名稱與解鎖條件）:
    @discord.ui.button(label="📖 專屬劇情", style=discord.ButtonStyle.success, row=1)
    async def view_npc_stories(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT story_title, unlock_condition FROM story_scripts 
                WHERE guild_id = ? AND npc_name = ? AND is_active = 1
            """, (self.guild_id, self.char_name)) as cur:
                rows = await cur.fetchall()

        if not rows:
            await interaction.response.send_message(f"📋 【{self.char_name}】目前尚未開放任何專屬攻略劇情。", ephemeral=True)
            return

        embed = discord.Embed(title=f"📖【{self.char_name}】專屬攻略劇情清單", color=0xF1C40F)
        for title, cond in rows:
            embed.add_field(name=f"🎬 《{title}》", value=f"• 解鎖條件：`{cond}`\n• 觸發指令：`/劇情觸發 角色名:你的名字 npc名稱:{self.char_name}`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# -------------------- 指令：/npc查看 --------------------
class NPCLobbySelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id

    @discord.ui.button(label="👑 官方 NPC", style=discord.ButtonStyle.primary)
    async def official_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT name, age, gender, job, nationality FROM characters 
                WHERE guild_id = ? AND is_npc = 1 ORDER BY name ASC
            """, (self.guild_id,)) as cur:
                npcs = await cur.fetchall()

        if not npcs:
            await interaction.response.send_message("📋 目前伺服器尚未登記任何【官方 NPC】！", ephemeral=True)
            return

        class OfficialSelect(discord.ui.Select):
            def __init__(self):
                opts = [
                    discord.SelectOption(
                        label=n[0],
                        description=f"{n[1]}歲 / {n[2]} ｜ {n[4]} ｜ {n[3]}",
                        emoji="👑",
                        value=n[0]
                    ) for n in npcs[:25]
                ]
                super().__init__(placeholder="請點選欲調閱的官方 NPC...", options=opts)

            async def callback(self, inter: discord.Interaction):
                await render_character_card(inter, self.values[0], ephemeral=False)

        v = discord.ui.View()
        v.add_item(OfficialSelect())
        await interaction.response.send_message("👑 請從下方選單挑選欲查看的官方 NPC：", view=v, ephemeral=True)

    @discord.ui.button(label="🎭 大眾路人", style=discord.ButtonStyle.secondary)
    async def crowd_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT name, age, gender, job, nationality FROM characters 
                WHERE guild_id = ? AND is_npc = 3 ORDER BY created_at DESC
            """, (self.guild_id,)) as cur:
                crowds = await cur.fetchall()

        if not crowds:
            await interaction.response.send_message("📋 目前伺服器尚未生成任何【大眾路人】！可使用 `/大眾路人大量發生中` 生成。", ephemeral=True)
            return

        class CrowdSelect(discord.ui.Select):
            def __init__(self):
                opts = [
                    discord.SelectOption(
                        label=c[0],
                        description=f"{c[1]}歲 / {c[2]} ｜ {c[4]} ｜ {c[3]}",
                        emoji="🎭",
                        value=c[0]
                    ) for c in crowds[:25]
                ]
                super().__init__(placeholder="請點選欲調閱的大眾路人檔案...", options=opts)

            async def callback(self, inter: discord.Interaction):
                await render_character_card(inter, self.values[0], ephemeral=False)

        v = discord.ui.View()
        v.add_item(CrowdSelect())
        await interaction.response.send_message("🎭 請從下方選單挑選欲查看的大眾路人：", view=v, ephemeral=True)

@bot.tree.command(name="npc查看", description="開啟 NPC 查閱大廳（按鈕切換官方 NPC 或大眾路人下拉選單）")
async def view_npc_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="👥 NPC 檔案查閱大廳",
        description=(
            "請點選下方按鈕，系統將彈出對應的下拉選單供你選擇：\n\n"
            "• 👑 **官方 NPC**：查看全域領袖、重要角色與具備攻略劇情的官方人物\n"
            "• 🎭 **大眾路人**：查看在全城參與行情浮動與競爭的動態路人"
        ),
        color=0x34495E
    )
    await interaction.response.send_message(embed=embed, view=NPCLobbySelectView(interaction.guild_id), ephemeral=True)

# -------------------- ProfileUpdateStepView --------------------
class ProfileUpdateStepView(discord.ui.View):
    def __init__(self, char_name: str, guild_id: int, is_admin: bool):
        super().__init__(timeout=180)
        self.char_name = char_name
        self.guild_id = guild_id
        self.is_admin = is_admin

    @discord.ui.button(label="📝 個資更新", style=discord.ButtonStyle.primary)
    async def update_base(self, interaction: discord.Interaction, button: discord.ui.Button):
        class BaseModal(discord.ui.Modal, title=f"更新【{self.char_name}】個人資料"):
            field_choice = discord.ui.TextInput(label="欲修改欄位 (職業/感情狀況/CP)", placeholder="例如: 感情狀況 或 CP")
            new_val = discord.ui.TextInput(label="修改後內容", placeholder="填入新資料，若為CP請填: 名字/關係")

            async def on_submit(m_self, inter: discord.Interaction):
                f_name = m_self.field_choice.value.strip()
                val = m_self.new_val.value.strip()
                async with aiosqlite.connect(DB_PATH) as db:
                    if f_name in ["職業", "身分", "job"]:
                        await db.execute("UPDATE characters SET job = ? WHERE guild_id = ? AND name = ?", (val, self.guild_id, self.char_name))
                    elif f_name in ["標籤", "tags"]:
                        await db.execute("UPDATE characters SET tags = ? WHERE guild_id = ? AND name = ?", (val, self.guild_id, self.char_name))
                    elif f_name in ["感情狀況", "感情"]:
                        await db.execute("UPDATE characters SET relationship_status = ? WHERE guild_id = ? AND name = ?", (val, self.guild_id, self.char_name))
                    elif f_name in ["CP", "cp"]:
                        cp_parts = re.split(r"[/,，\s]+", val)
                        cp_obj = {"target": cp_parts[0], "relation": cp_parts[1] if len(cp_parts) > 1 else "伴侶"}
                        await db.execute("UPDATE characters SET cp_info = ? WHERE guild_id = ? AND name = ?", (json.dumps(cp_obj, ensure_ascii=False), self.guild_id, self.char_name))
                    else:
                        await inter.response.send_message("❌ 無法識別該欄位名稱！", ephemeral=True)
                        return
                    await db.commit()
                await inter.response.send_message(f"✅ 【{self.char_name}】的 **{f_name}** 已更新為：`{val}`！", ephemeral=True)

        await interaction.response.send_modal(BaseModal())

    @discord.ui.button(label="🏆 成就更新", style=discord.ButtonStyle.success)
    async def update_achievement(self, interaction: discord.Interaction, button: discord.ui.Button):
        class AchieveModal(discord.ui.Modal, title=f"登記【{self.char_name}】成就歷練"):
            category = discord.ui.TextInput(label="分類 (電影/電視劇/綜藝/大型事件等)", placeholder="例如: 電影")
            title = discord.ui.TextInput(label="作品/成就名稱", placeholder="例如: 楚門的世界")
            role_type = discord.ui.TextInput(label="擔任/番位", placeholder="例如: 女主、男配、主策劃")

            async def on_submit(m_self, inter: discord.Interaction):
                entry = {
                    "category": "成就",
                    "type": m_self.category.value.strip(),
                    "title": m_self.title.value.strip(),
                    "extra": m_self.role_type.value.strip()
                }
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT works FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                        works = json.loads((await cur.fetchone())[0] or "[]")
                    works.append(entry)
                    await db.execute("UPDATE characters SET works = ? WHERE guild_id = ? AND name = ?", (json.dumps(works, ensure_ascii=False), self.guild_id, self.char_name))
                    await db.commit()

                await check_and_update_rank(self.guild_id, self.char_name, inter.channel)
                await inter.response.send_message(f"✅ 成功為 **{self.char_name}** 登記成就：【{entry['type']}】《{entry['title']}》（{entry['extra']}）！", ephemeral=True)

        await interaction.response.send_modal(AchieveModal())

    @discord.ui.button(label="🎖️ 榮譽更新", style=discord.ButtonStyle.secondary)
    async def update_honor(self, interaction: discord.Interaction, button: discord.ui.Button):
        class HonorModal(discord.ui.Modal, title=f"登記【{self.char_name}】榮譽頭銜"):
            name = discord.ui.TextInput(label="榮譽名稱 / 代言商品", placeholder="例如: 香奈兒全球代言")
            level = discord.ui.TextInput(label="級別 (如: 奢華, S+, 頂級)", placeholder="例如: 奢華")
            title_name = discord.ui.TextInput(label="授予頭銜", placeholder="例如: 品牌摯友 / 終身榮譽會員")

            async def on_submit(m_self, inter: discord.Interaction):
                entry = {
                    "category": "榮譽",
                    "title": m_self.name.value.strip(),
                    "extra": f"{m_self.level.value.strip()} ｜ {m_self.title_name.value.strip()}"
                }
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT works FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                        works = json.loads((await cur.fetchone())[0] or "[]")
                    works.append(entry)
                    await db.execute("UPDATE characters SET works = ? WHERE guild_id = ? AND name = ?", (json.dumps(works, ensure_ascii=False), self.guild_id, self.char_name))
                    await db.commit()

                await check_and_update_rank(self.guild_id, self.char_name, inter.channel)
                await inter.response.send_message(f"✅ 成功為 **{self.char_name}** 登記榮譽：【{entry['title']}】（{entry['extra']}）！", ephemeral=True)

        await interaction.response.send_modal(HonorModal())

    @discord.ui.button(label="💬 交際關係傾向", style=discord.ButtonStyle.danger)
    async def update_relationship(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'tendency_list'", (self.guild_id,)) as cur:
                row = await cur.fetchone()
                tendencies = json.loads(row[0]) if row and row[0] else ["傾心", "好奇", "觀察", "痴迷", "友好", "敵對", "利用"]

        class RelationModal(discord.ui.Modal, title=f"變更【{self.char_name}】對其他人的交際傾向"):
            target = discord.ui.TextInput(label="目標角色/NPC 名稱", placeholder="輸入對方全名")
            tendency = discord.ui.TextInput(label=f"交際傾向 ({'/'.join(tendencies[:6])})", placeholder="輸入傾向詞彙")
            status = discord.ui.TextInput(label="狀況敘述 (可選)", placeholder="例如: 暗中保護、針鋒相對", required=False)

            async def on_submit(m_self, inter: discord.Interaction):
                t_name = m_self.target.value.strip()
                t_val = m_self.tendency.value.strip()
                s_val = m_self.status.value.strip() or "普通往來"

                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("""
                        INSERT INTO relationships (guild_id, from_char, to_char, tendency, status_desc)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(guild_id, from_char, to_char) DO UPDATE SET tendency = ?, status_desc = ?
                    """, (self.guild_id, self.char_name, t_name, t_val, s_val, t_val, s_val))
                    await db.commit()
                await inter.response.send_message(f"💞 已更新 **{self.char_name}** ➔ **{t_name}** 的交際傾向為【{t_val}】（狀態：{s_val}）！", ephemeral=True)

        await interaction.response.send_modal(RelationModal())
# -------------------- 指令：/檔案更新 --------------------
@bot.tree.command(name="檔案更新", description="更新個資、成就、榮譽或交際關係")
@app_commands.choices(類別=[
    app_commands.Choice(name="官方 NPC", value="官方npc"),
    app_commands.Choice(name="玩家自設 NPC", value="玩家npc"),
    app_commands.Choice(name="自身角色", value="角色")
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
        elif 類別.value == "玩家npc":
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
            @discord.ui.select(placeholder="請選擇欲操作的檔案...", options=[discord.SelectOption(label=c, value=c) for c in candidates[:25]])
            async def select_callback(self, inter: discord.Interaction, select: discord.ui.Select):
                view = ProfileUpdateStepView(select.values[0], g_id, is_admin)
                await inter.response.send_message(f"⚙️ 正在更新【{select.values[0]}】的檔案，請點選下方操作：", view=view, ephemeral=True)

        await interaction.response.send_message("請先選擇要更新的角色檔案：", view=CharPickView(), ephemeral=True)
    else:
        char_name = candidates[0]
        view = ProfileUpdateStepView(char_name, g_id, is_admin)
        await interaction.response.send_message(f"⚙️ 正在更新【{char_name}】的檔案，請點選下方操作：", view=view, ephemeral=True)
# -------------------- 指令：/傾向管理 --------------------
@bot.tree.command(name="傾向管理", description="【管理員專用】新增或刪減交際傾向詞庫（傾心、好奇、觀察、痴迷等）")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="新增傾向", value="add"),
    app_commands.Choice(name="刪除傾向", value="remove"),
    app_commands.Choice(name="列出目前傾向", value="list")
])
@app_commands.describe(操作="選擇要執行的動作", 詞彙="欲新增或刪減的傾向名稱")
async def manage_tendency(interaction: discord.Interaction, 操作: app_commands.Choice[str], 詞彙: str = None):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'tendency_list'", (g_id,)) as cur:
            row = await cur.fetchone()
            tendencies = json.loads(row[0]) if row and row[0] else ["傾心", "好奇", "觀察", "痴迷", "友好", "敵對", "利用"]

        if 操作.value == "list":
            await interaction.response.send_message(f"📋 目前伺服器交際傾向詞庫：\n`{'、'.join(tendencies)}`", ephemeral=True)
            return

        if not 詞彙:
            await interaction.response.send_message("❌ 請填寫傾向詞彙！", ephemeral=True)
            return

        word = 詞彙.strip()
        if 操作.value == "add":
            if word not in tendencies:
                tendencies.append(word)
        elif 操作.value == "remove":
            if word in tendencies:
                tendencies.remove(word)

        await db.execute("""
            INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'tendency_list', ?)
            ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
        """, (g_id, json.dumps(tendencies, ensure_ascii=False), json.dumps(tendencies, ensure_ascii=False)))
        await db.commit()

    await interaction.response.send_message(f"✅ 傾向詞庫已更新！目前包含：`{'、'.join(tendencies)}`", ephemeral=True)
# -------------------- 指令：/資產系統更新 --------------------
@bot.tree.command(name="資產系統更新", description="【管理員專用】上架車輛/房產、設定價格或管理公司開關")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="🚗 上架新車輛", value="add_vehicle"),
    app_commands.Choice(name="🏠 上架新房產", value="add_house"),
    app_commands.Choice(name="🗑️ 移除架上資產", value="remove_asset"),
    app_commands.Choice(name="🏢 設定是否隱藏公司", value="toggle_company")
])
@app_commands.describe(
    操作="選擇要執行的資產管理動作",
    資產名稱="車輛或房產名稱（移除時填欲下架的資產名）",
    價格="售價 (純數字)",
    詳細說明="例如: 超跑/越野車，或市中心大平層/豪華別墅",
    隱藏公司系統="僅在操作為【設定是否隱藏公司】時選擇 (1 為隱藏, 0 為開放)"
)
async def asset_system_update(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    資產名稱: str = None,
    價格: int = 0,
    詳細說明: str = "官方認證物業資產",
    隱藏公司系統: str = None
):
    g_id = interaction.guild_id
    op = 操作.value

    if op == "toggle_company":
        if not 隱藏公司系統:
            await interaction.response.send_message("❌ 請選擇【隱藏公司系統】（填 1 為隱藏，0 為開放）！", ephemeral=True)
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'hide_company', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, 隱藏公司系統.strip(), 隱藏公司系統.strip()))
            await db.commit()
        state = "已隱藏" if 隱藏公司系統.strip() == "1" else "已開放"
        await interaction.response.send_message(f"⚙️ 公司系統顯示狀態已設定為：**{state}**！", ephemeral=True)
        return

    if op in ["add_vehicle", "add_house"]:
        if not 資產名稱 or 價格 <= 0:
            await interaction.response.send_message("❌ 上架資產時，**【資產名稱】與【價格】(需大於0)** 為必填！", ephemeral=True)
            return
        asset_type = "車輛" if op == "add_vehicle" else "房產"
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO available_assets (guild_id, asset_type, asset_name, price, description)
                VALUES (?, ?, ?, ?, ?)
            """, (g_id, asset_type, 資產名稱.strip(), 價格, 詳細說明.strip()))
            await db.commit()
        emoji = "🚗" if asset_type == "車輛" else "🏠"
        await interaction.response.send_message(f"✅ 成功上架【{asset_type}】！\n{emoji} 名稱：**{資產名稱.strip()}** ｜ 價格：**${價格:,}**\n📝 描述：`{詳細說明.strip()}`")

    elif op == "remove_asset":
        if not 資產名稱:
            await interaction.response.send_message("❌ 請填寫欲下架的【資產名稱】！", ephemeral=True)
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM available_assets WHERE guild_id = ? AND asset_name = ?", (g_id, 資產名稱.strip()))
            await db.commit()
        await interaction.response.send_message(f"🗑️ 已成功將資產【{資產名稱.strip()}】自購買名單中下架！", ephemeral=True)
# -------------------- 指令：/資產系統 --------------------
class BuyAssetSelect(discord.ui.Select):
    def __init__(self, char_name: str, guild_id: int, asset_type: str, assets: list):
        self.char_name = char_name
        self.guild_id = guild_id
        self.asset_type = asset_type
        self.assets = assets

        options = [
            discord.SelectOption(
                label=f"{a[0]} (${a[1]:,})",
                value=f"{a[0]}:{a[1]}",
                description=a[2][:50] if a[2] else "官方名品"
            ) for a in assets[:25]
        ]
        super().__init__(placeholder=f"請挑選欲購置的【{asset_type}】...", options=options)

    async def callback(self, interaction: discord.Interaction):
        asset_name, price_str = self.values[0].split(":", 1)
        price = int(price_str)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT cash, bank FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                c_row = await cur.fetchone()
                if not c_row:
                    await interaction.response.send_message("❌ 查無此角色！", ephemeral=True)
                    return
                cash, bank = c_row

            total_money = cash + bank
            if total_money < price:
                await interaction.response.send_message(
                    f"❌ 購買失敗！資產【{asset_name}】售價 **${price:,}**。\n"
                    f"你手頭現金僅有 **${cash:,}**，銀行存款 **${bank:,}**（總額不足以支付）！",
                    ephemeral=True
                )
                return

            if cash >= price:
                await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (price, self.guild_id, self.char_name))
            else:
                remain = price - cash
                await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (remain, self.guild_id, self.char_name))

            await db.execute("""
                INSERT INTO personal_assets (guild_id, owner_name, asset_type, asset_name, price, details)
                VALUES (?, ?, ?, ?, ?, '官方購置資產')
            """, (self.guild_id, self.char_name, self.asset_type, asset_name, price))
            await db.commit()

        emoji = "🚗" if self.asset_type == "車輛" else "🏠"
        await interaction.response.send_message(
            f"🎉 購置成功！\n"
            f"恭喜 **{self.char_name}** 正式將 {emoji} **{asset_name}** 納入個人名下資產！\n"
            f"💰 系統已自動扣繳款項 **${price:,}**，資產已同步計入財富面板！"
        )

@bot.tree.command(name="資產系統", description="購買車輛、房產或申請創立/加入公司")
@app_commands.describe(角色名="欲進行資產購置或創立的角色名稱")
async def asset_system(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()
            if not c_row:
                await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
                return
            if c_row[0] != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 你只能為自己的角色操作資產！", ephemeral=True)
                return

        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'hide_company'", (g_id,)) as cur:
            row = await cur.fetchone()
            hide_comp = row and row[0] == "1"

    embed = discord.Embed(title=f"🏙️ 資產與產權管理中心 — 操作人：【{c_name}】", description="請點選下方按鈕選購車輛、物業或進行公司設立：", color=0x34495E)
    view = discord.ui.View()

    btn_vehicle = discord.ui.Button(label="🚗 購置車輛", style=discord.ButtonStyle.primary)
    btn_house = discord.ui.Button(label="🏠 置辦房產", style=discord.ButtonStyle.success)

    async def buy_vehicle_cb(inter: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT asset_name, price, description FROM available_assets WHERE guild_id = ? AND asset_type = '車輛'", (g_id,)) as cur:
                v_list = await cur.fetchall()
        if not v_list:
            await inter.response.send_message("🏪 目前車行暫無可購置的車輛！請聯繫管理員透過 `/資產系統更新` 上架。", ephemeral=True)
            return
        v_view = discord.ui.View()
        v_view.add_item(BuyAssetSelect(c_name, g_id, "車輛", v_list))
        await inter.response.send_message("🚘 請挑選欲全款購置的豪華座駕：", view=v_view, ephemeral=True)

    async def buy_house_cb(inter: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT asset_name, price, description FROM available_assets WHERE guild_id = ? AND asset_type = '房產'", (g_id,)) as cur:
                h_list = await cur.fetchall()
        if not h_list:
            await inter.response.send_message("🏢 目前房產中心暫無可購置的物業！請聯繫管理員透過 `/資產系統更新` 上架。", ephemeral=True)
            return
        h_view = discord.ui.View()
        h_view.add_item(BuyAssetSelect(c_name, g_id, "房產", h_list))
        await inter.response.send_message("🏡 請挑選欲登記產權的名下房產：", view=h_view, ephemeral=True)

    btn_vehicle.callback = buy_vehicle_cb
    btn_house.callback = buy_house_cb
    view.add_item(btn_vehicle)
    view.add_item(btn_house)

    if not hide_comp:
        btn_join_comp = discord.ui.Button(label="🏢 加入公司", style=discord.ButtonStyle.secondary)
        btn_create_comp = discord.ui.Button(label="🏗️ 創建公司", style=discord.ButtonStyle.danger)

        async def join_comp_cb(inter: discord.Interaction):
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT id, name, creator_name FROM companies WHERE guild_id = ?", (g_id,)) as cur:
                    comps = await cur.fetchall()
            if not comps:
                await inter.response.send_message("🏢 目前全城尚無可加入的公司！", ephemeral=True)
                return

            class JoinCompSelect(discord.ui.Select):
                def __init__(self):
                    opts = [discord.SelectOption(label=c[1], description=f"所有人: {c[2]}", value=f"{c[0]}:{c[1]}:{c[2]}") for c in comps[:25]]
                    super().__init__(placeholder="請選擇欲申請加入的公司...", options=opts)

                async def callback(self, s_inter: discord.Interaction):
                    c_id, comp_name, creator = self.values[0].split(":", 2)
                    async with aiosqlite.connect(DB_PATH) as db:
                        async with db.execute("SELECT user_id FROM characters WHERE guild_id = ? AND name = ?", (g_id, creator)) as cur:
                            cr_row = await cur.fetchone()
                            owner_uid = cr_row[0] if cr_row else None

                    mention_str = f"<@{owner_uid}>" if owner_uid else f"登記人 **{creator}**"
                    await s_inter.response.send_message(
                        f"📩 **【入職申請已送出】**\n"
                        f"角色 **{c_name}** 已向公司【**{comp_name}**】提出加入申請！\n"
                        f"請 {mention_str} 留意，確認同意後即可正式登記為所屬員工！"
                    )

            j_view = discord.ui.View()
            j_view.add_item(JoinCompSelect())
            await inter.response.send_message("請選擇想投遞履歷的公司：", view=j_view, ephemeral=True)

        async def create_comp_cb(inter: discord.Interaction):
            class CreateCompanyModal(discord.ui.Modal, title="創立全新公司/工作室"):
                comp_name = discord.ui.TextInput(label="公司名稱")
                purpose = discord.ui.TextInput(label="用途宗旨", placeholder="例如: 貿易、藝人經紀")
                comp_type = discord.ui.TextInput(label="類型 (個人工作室/影業/公司等)")
                structure = discord.ui.TextInput(label="有限公司/股份有限公司 (填: 1人 或 2人以上)")
                capital_and_partners = discord.ui.TextInput(
                    label="出資額與合夥人",
                    placeholder="獨資填金額(低消10萬)；多人填: 金額 @合夥人 (每人低消5萬)",
                    style=discord.TextStyle.paragraph
                )

                async def on_submit(m_self, m_inter: discord.Interaction):
                    c_comp_name = m_self.comp_name.value.strip()
                    s_type = m_self.structure.value.strip()
                    raw_cap = m_self.capital_and_partners.value.strip()

                    nums = [int(n) for n in re.findall(r"\d+", raw_cap)]
                    if not nums:
                        await m_inter.response.send_message("❌ 請填寫出資金額！", ephemeral=True)
                        return

                    my_inv = nums[0]
                    async with aiosqlite.connect(DB_PATH) as db:
                        async with db.execute("SELECT cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
                            u_char = await cur.fetchone()
                            my_total_money = u_char[0] + u_char[1]

                        if "1人" in s_type or "有限" in s_type:
                            if my_inv < 100000:
                                await m_inter.response.send_message("❌ 個人獨資最低出資金額為 **$100,000**！", ephemeral=True)
                                return
                            if (my_total_money - my_inv) < (my_inv / 2):
                                await m_inter.response.send_message("❌ 資產門檻不足！創立後剩餘錢款必須達出資金額的 **1/2**！", ephemeral=True)
                                return

                            await db.execute("""
                                INSERT INTO companies (guild_id, name, purpose, type_name, structure, creator_name, total_capital, balance)
                                VALUES (?, ?, ?, ?, '有限公司', ?, ?, ?)
                            """, (g_id, c_comp_name, m_self.purpose.value.strip(), m_self.comp_type.value.strip(), c_name, my_inv, my_inv))
                            await db.execute("UPDATE characters SET bank = bank - ? WHERE guild_id = ? AND name = ?", (my_inv, g_id, c_name))
                            await db.commit()
                            await m_inter.response.send_message(f"🎉 恭喜！有限公司【**{c_comp_name}**】成功註冊成立，資本額 **${my_inv:,}**！")
                        else:
                            if my_inv < 50000:
                                await m_inter.response.send_message("❌ 多人合夥每人最低出資金額為 **$50,000**！", ephemeral=True)
                                return
                            await m_inter.response.send_message(f"📩 多人股份有限公司【{c_comp_name}】申請已送出！已通知所有合夥人備妥資金驗資。")

            await inter.response.send_modal(CreateCompanyModal())

        btn_join_comp.callback = join_comp_cb
        btn_create_comp.callback = create_comp_cb
        view.add_item(btn_join_comp)
        view.add_item(btn_create_comp)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
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
        await interaction.response.send_message(f"ℹ️ 角色 **{my_char}** 目前無名下公司。", ephemeral=True)
# -------------------- 指令：/商店與物品管理 --------------------
@bot.tree.command(name="商店與物品管理", description="【管理員專用】上架、修改商城商品、門票身分組或新增寵物品種")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="上架/新增商品或寵物", value="add"),
    app_commands.Choice(name="修改既有商品", value="edit"),
    app_commands.Choice(name="下架商品或寵物", value="remove")
])
@app_commands.describe(
    操作="選擇執行的動作",
    商店="商品歸屬商店（填［寵物］可直接上架寵物；或填 官方商城、票務系統 等）",
    商品名="物品或寵物品種名稱（例如: 布偶貓、柴犬、優質貓糧）",
    價格="售價 (純數字)",
    簡介="商品介紹或描述",
    增加數值="［道具］加成數值(如: 容貌+10) ｜ ［寵物］填預期壽命年數(如: 15)",
    增加好感="贈予 NPC 時額外增加的好感度點數",
    可否使用="1 代表可使用生效，0 代表僅供收藏",
    是否為門票="是否為大地圖傳送門票",
    對應地圖身分組="若為門票，請指定使用後賦予的身分組"
)
async def manage_shop_items(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    商店: str,
    商品名: str,
    價格: int = 0,
    簡介: str = "官方精選正品",
    增加數值: str = "",
    增加好感: int = 0,
    可否使用: int = 1,
    是否為門票: bool = False,
    對應地圖身分組: discord.Role = None
):
    g_id = interaction.guild_id
    op = 操作.value
    i_name = 商品名.strip()
    s_name = 商店.strip()
    role_id = 對應地圖身分組.id if (是否為門票 and 對應地圖身分組) else 0
    is_pet_shop = s_name in ["寵物", "寵物中心", "寵物店"]

    async with aiosqlite.connect(DB_PATH) as db:
        if op == "remove":
            async with db.execute("SELECT id FROM shop_items WHERE guild_id = ? AND shop_name = ? AND name = ?", (g_id, s_name, i_name)) as cur:
                exists = await cur.fetchone()

            if not exists:
                await interaction.response.send_message(f"❌ 查無【{s_name}】的項目【{i_name}】！", ephemeral=True)
                return

            await db.execute("DELETE FROM shop_items WHERE id = ?", (exists[0],))
            await db.commit()
            await interaction.response.send_message(f"🗑️ 已成功將【{i_name}】從【{s_name}】下架！", ephemeral=True)
            return

        if 價格 <= 0:
            await interaction.response.send_message("❌ 販售價格必須大於 0！", ephemeral=True)
            return

        async with db.execute("SELECT id FROM shop_items WHERE guild_id = ? AND shop_name = ? AND name = ?", (g_id, s_name, i_name)) as cur:
            exists = await cur.fetchone()

        if op == "add":
            if exists:
                await interaction.response.send_message(f"❌ 【{s_name}】已有同名項目【{i_name}】！若要調整請選修改。", ephemeral=True)
                return

            await db.execute("""
                INSERT INTO shop_items (guild_id, shop_name, name, price, description, stat_bonus, affinity_bonus, usable, target_role_id, seller)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '官方')
            """, (g_id, s_name, i_name, 價格, 簡介.strip(), 增加數值.strip(), 增加好感, 可否使用, role_id))
            action_str = "上架"
        else:
            if not exists:
                await interaction.response.send_message(f"❌ 查無欲修改的項目【{i_name}】！", ephemeral=True)
                return

            await db.execute("""
                UPDATE shop_items SET price = ?, description = ?, stat_bonus = ?, affinity_bonus = ?, usable = ?, target_role_id = ?
                WHERE id = ?
            """, (價格, 簡介.strip(), 增加數值.strip(), 增加好感, 可否使用, role_id, exists[0]))
            action_str = "修改"

        await db.commit()

    ticket_text = f"（🎫 綁定身分組: {對應地圖身分組.mention}）" if role_id > 0 else ""
    await interaction.response.send_message(
        f"✅ 成功{action_str}！\n"
        f"🏪 所屬專區：【{s_name}】\n"
        f"📦 名稱：**{i_name}** ｜ 價格：**${價格:,}** {ticket_text}\n"
        f"📝 簡介：`{簡介.strip()}`"
    )
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
# -------------------- 指令：/背包 與 /使用 --------------------
@bot.tree.command(name="背包", description="查看角色背包物品與來源")
@app_commands.describe(角色名="欲查閱背包的角色名稱")
async def inventory(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT item_name, amount, giver FROM inventory WHERE guild_id = ? AND owner_name = ?", (g_id, c_name)) as cur:
            items = await cur.fetchall()

    if not items:
        await interaction.response.send_message(f"🎒 **{c_name}** 的背包空空如也，暫無任何物品。", ephemeral=True)
        return

    embed = discord.Embed(title=f"🎒【{c_name}】的專屬背包", color=0x3498DB)
    for name, amt, giver in items:
        embed.add_field(name=f"📦 {name} × {amt}", value=f"來源/途徑: `{giver}`", inline=True)

    await interaction.response.send_message(embed=embed)

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
        async with db.execute("SELECT user_id, stats, ticket_ban_until FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()
            if not c_row:
                await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
                return
            u_id, stats_json, ticket_ban = c_row

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

        async with db.execute("SELECT stat_bonus, usable, target_role_id FROM shop_items WHERE guild_id = ? AND name = ?", (g_id, i_name)) as cur:
            item_info = await cur.fetchone()

        stat_bonus = item_info[0] if (item_info and item_info[0]) else ""
        usable = item_info[1] if item_info else 1
        role_id = item_info[2] if item_info else 0

        if usable == 0:
            await interaction.response.send_message(f"ℹ️ 道具【{i_name}】為純收藏紀念品，無法直接使用。", ephemeral=True)
            return

        now = time.time()
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

        if use_cnt == cur_amt:
            await db.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
        else:
            await db.execute("UPDATE inventory SET amount = amount - ? WHERE id = ?", (use_cnt, inv_id))

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

        applied_stats = []
        char_stats = json.loads(stats_json) if stats_json else {}

        if stat_bonus:
            for part in re.split(r"[,，、\s]+", stat_bonus.strip()):
                m = re.search(r"([^\d+-]+)([+-]?\d+)", part)
                if m:
                    s_name = m.group(1).strip()
                    s_delta = int(m.group(2)) * use_cnt
                    char_stats[s_name] = max(0, char_stats.get(s_name, 0) + s_delta)
                    sign = "+" if s_delta >= 0 else ""
                    applied_stats.append(f"{s_name} {sign}{s_delta} (現值: **{char_stats[s_name]}**)")

            await db.execute(
                "UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?",
                (json.dumps(char_stats, ensure_ascii=False), g_id, c_name)
            )

        await db.commit()

    if applied_stats:
        await check_and_update_rank(g_id, c_name, interaction.channel)

    extra_msg = f"\n🎫 已啟用外地簽證身分組！有效停留時間為 **336 小時（兩週）**，請記得在期限前使用 `/返回原本地圖`！" if role_id > 0 else ""
    bonus_msg = f"\n📊 **【角色屬性即時成長】**\n• " + "\n• ".join(applied_stats) if applied_stats else ""

    await interaction.response.send_message(
        f"✨ **{c_name}** 成功使用了道具【**{i_name}**】×{use_cnt}！{bonus_msg}{extra_msg}{pet_heal_msg}"
    )
# -------------------- 指令：/返回原本地圖 --------------------
@bot.tree.command(name="返回原本地圖", description="主動結束地圖旅行並收回身分組（免除遣返與禁令懲罰）")
@app_commands.describe(角色名="出境中的角色名稱")
async def return_home(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, role_id FROM active_tickets WHERE guild_id = ? AND char_name = ?", (g_id, c_name)) as cur:
            ticket = await cur.fetchone()
            if not ticket:
                await interaction.response.send_message(f"ℹ️ 角色 **{c_name}** 目前並無啟用中的外地簽證或門票身分組！", ephemeral=True)
                return

            t_id, role_id = ticket
            role = interaction.guild.get_role(role_id)
            if role:
                try:
                    await interaction.user.remove_roles(role, reason="玩家主動返回原本地圖")
                except Exception:
                    pass

            await db.execute("DELETE FROM active_tickets WHERE id = ?", (t_id,))
            await db.commit()

    await interaction.response.send_message(f"🏠 **{c_name}** 已順利返回原本地圖！已安全繳回門票身分組，無任何懲罰。")
# -------------------- 指令：/贈予 --------------------
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
# -------------------- 指令：/任務 --------------------
@bot.tree.command(name="任務", description="查看角色當前完成與未完成的任務看板")
@app_commands.describe(角色名="欲查閱任務看板的角色名稱")
async def view_quests(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND name = ?", (g_id, 角色名)) as cur:
            if not await cur.fetchone():
                await interaction.response.send_message(f"❌ 查無角色 `{角色名}`！", ephemeral=True)
                return

        async with db.execute("SELECT category, title, reward_cash, reward_stats, achievement, honor, requirement, time_limit, report_channel_id FROM quests WHERE guild_id = ? ORDER BY id ASC", (g_id,)) as cur:
            all_quests = await cur.fetchall()

        async with db.execute("SELECT quest_title FROM quest_completions WHERE guild_id = ? AND char_name = ?", (g_id, 角色名)) as cur:
            done_titles = {row[0] for row in await cur.fetchall()}

    if not all_quests:
        await interaction.response.send_message("📋 目前尚未發布任何任務！", ephemeral=True)
        return

    categories = ["新手任務", "一般任務", "限時任務", "特殊任務"]
    embed = discord.Embed(title=f"📜【{角色名}】的任務清單看板", color=0xF1C40F)

    for cat in categories:
        cat_quests = [q for q in all_quests if q[0] == cat]
        if not cat_quests:
            embed.add_field(name=f"📌 {cat}欄", value="暫無任務", inline=False)
            continue

        lines = []
        for _, title, r_cash, r_stats, achieve, honor, req, time_limit, r_ch_id in cat_quests:
            status = "✅" if title in done_titles else "❌"
            limit_str = f" ⏳ `{time_limit}`" if time_limit else ""
            ch_str = f" 📍 <#{r_ch_id}>" if r_ch_id > 0 else ""
            achieve_str = f" 🏆`{achieve}`" if achieve else ""
            honor_str = f" 🎖️`{honor}`" if honor else ""
            req_str = f" 🚫 限`{req}`" if req else ""

            rew_parts = []
            if r_cash > 0: rew_parts.append(f"${r_cash:,}")
            if r_stats: rew_parts.append(f"{r_stats}")
            rew_str = " ｜ ".join(rew_parts) if rew_parts else "履歷證明"

            lines.append(f"• **{title}**{achieve_str}{honor_str}{req_str}{limit_str}{ch_str}\n  └ 獎勵：{rew_str} ［{status}］")

        embed.add_field(name=f"📌 {cat}欄", value="\n".join(lines), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)
# -------------------- 指令：/陣營 --------------------
@bot.tree.command(name="陣營", description="陣營主控台：捐獻、查看金庫排名、購買商城全體加成或退出")
@app_commands.choices(操作=[
    app_commands.Choice(name="查看現況與領週禮包", value="view"),
    app_commands.Choice(name="捐獻資金", value="donate"),
    app_commands.Choice(name="購買陣營商城Buff(正副負責人限定)", value="buy"),
    app_commands.Choice(name="退出陣營(需付費)", value="exit"),
    app_commands.Choice(name="加入陣營", value="join")
])
@app_commands.describe(操作="選擇要執行的動作", 角色名="欲操作的角色名稱", 金額="捐獻或購買時填寫的金額", 陣營名稱="指定陣營名")
async def faction_cmd(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    角色名: str,
    金額: int = 0,
    陣營名稱: str = None
):
    g_id = interaction.guild_id
    c_name = 角色名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT faction, cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            char_row = await cur.fetchone()
            if not char_row:
                await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
                return
            my_faction, cash, bank = char_row

    op = 操作.value

    if op == "view":
        if my_faction == "無":
            await interaction.response.send_message(f"ℹ️ 【{c_name}】目前不屬於任何陣營，請先使用加入陣營！", ephemeral=True)
            return
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT treasury, desc, weekly_gift FROM factions WHERE guild_id = ? AND name = ?", (g_id, my_faction)) as cur:
                f_info = await cur.fetchone()
            async with db.execute("SELECT char_name, contribution FROM faction_members WHERE guild_id = ? AND faction_name = ? ORDER BY contribution DESC LIMIT 5", (g_id, my_faction)) as cur:
                rankings = await cur.fetchall()

        treasury, desc, weekly_gift = f_info if f_info else (0, "無簡介", "{}")
        embed = discord.Embed(title=f"🚩 陣營面板：【{my_faction}】", color=0xE74C3C)
        embed.description = f"{desc}\n\n💰 **陣營金庫公款**：${treasury:,}"

        rank_lines = [f"`#{i+1}` **{r[0]}** ｜ 貢獻度: {r[1]:,}" for i, r in enumerate(rankings)]
        embed.add_field(name="🏆 陣營內部貢獻前五名 (正副負責人擁商城權限)", value="\n".join(rank_lines) if rank_lines else "暫無貢獻紀錄", inline=False)
        await interaction.response.send_message(embed=embed)

    elif op == "donate":
        if 金額 <= 0:
            await interaction.response.send_message("❌ 捐獻金額需大於 0！", ephemeral=True)
            return
        if cash < 金額:
            await interaction.response.send_message(f"❌ 現金不足！目前手頭現金僅有 ${cash:,}。", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (金額, g_id, c_name))
            await db.execute("UPDATE factions SET treasury = treasury + ? WHERE guild_id = ? AND name = ?", (金額, g_id, my_faction))
            await db.execute("""
                INSERT INTO faction_members (guild_id, faction_name, char_name, contribution)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, faction_name, char_name) DO UPDATE SET contribution = contribution + ?
            """, (g_id, my_faction, c_name, 金額, 金額))
            await db.commit()

        await interaction.response.send_message(f"🤝 **{c_name}** 為陣營【{my_faction}】成功捐獻 **${金額:,}**！貢獻度同步增加。")

    elif op == "buy":
        if my_faction == "無":
            await interaction.response.send_message("❌ 你尚未加入任何陣營！", ephemeral=True)
            return

        cost = 金額 if 金額 > 0 else 50000
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT treasury FROM factions WHERE guild_id = ? AND name = ?", (g_id, my_faction)) as cur:
                f_row = await cur.fetchone()
                treasury = f_row[0] if f_row else 0

            if treasury < cost:
                await interaction.response.send_message(f"❌ 陣營金庫公款不足！需要公款 **${cost:,}**。", ephemeral=True)
                return

            await db.execute("UPDATE factions SET treasury = treasury - ? WHERE guild_id = ? AND name = ?", (cost, g_id, my_faction))
            await db.execute("UPDATE characters SET bank = bank + 10000 WHERE guild_id = ? AND faction = ?", (g_id, my_faction))
            await db.commit()

        await interaction.response.send_message(f"🚩✨ 負責人 **{c_name}** 動用陣營公款 **${cost:,}** 啟動全陣營激勵！【{my_faction}】全體成員銀行帳戶各入帳福利獎金 **$10,000**！")

    elif op == "exit":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT exit_fee FROM factions WHERE guild_id = ? AND name = ?", (g_id, my_faction)) as cur:
                f_row = await cur.fetchone()
                exit_fee = f_row[0] if f_row else 5000

            if cash < exit_fee:
                await interaction.response.send_message(f"❌ 現金不足以支付退出罰金！需要手頭現金 **${exit_fee:,}**。", ephemeral=True)
                return

            await db.execute("UPDATE characters SET cash = cash - ?, faction = '無' WHERE guild_id = ? AND name = ?", (exit_fee, g_id, c_name))
            await db.execute("DELETE FROM faction_members WHERE guild_id = ? AND char_name = ?", (g_id, c_name))
            await db.commit()

        await interaction.response.send_message(f"🚪 **{c_name}** 支付了違約賠償金 **${exit_fee:,}**，正式退出陣營【{my_faction}】！")

    elif op == "join":
        if not 陣營名稱:
            await interaction.response.send_message("❌ 請填寫欲加入的【陣營名稱】！", ephemeral=True)
            return
        t_faction = 陣營名稱.strip()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM factions WHERE guild_id = ? AND name = ?", (g_id, t_faction)) as cur:
                if not await cur.fetchone():
                    await interaction.response.send_message(f"❌ 查無陣營【{t_faction}】！", ephemeral=True)
                    return
            await db.execute("UPDATE characters SET faction = ? WHERE guild_id = ? AND name = ?", (t_faction, g_id, c_name))
            await db.commit()
        await interaction.response.send_message(f"🚩 恭喜 **{c_name}** 正式加入陣營【{t_faction}】！")
# -------------------- 指令：/陣營管理 與 /金主降臨 --------------------
@bot.tree.command(name="陣營管理", description="【管理員專用】建立全新陣營或向陣營全體發放獎勵")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="建立新陣營", value="create"),
    app_commands.Choice(name="陣營榜首犒賞", value="reward_top")
])
@app_commands.describe(陣營名稱="陣營名稱", 簡介="理念介紹", 抽成比例="0.1 代表 10%", 退出費用="脫離違約金")
async def manage_faction_admin(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    陣營名稱: str,
    簡介: str = "自治勢力",
    抽成比例: float = 0.1,
    退出費用: int = 5000
):
    g_id = interaction.guild_id
    f_name = 陣營名稱.strip()

    if 操作.value == "create":
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO factions (guild_id, name, desc, tax_rate, exit_fee)
                VALUES (?, ?, ?, ?, ?)
            """, (g_id, f_name, 簡介.strip(), 抽成比例, 退出費用))
            await db.commit()
        await interaction.response.send_message(f"🚩 成功註冊勢力陣營：【**{f_name}**】（退出違約金：${退出費用:,}，抽成率：{int(抽成比例*100)}%）！")
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE characters SET bank = bank + 50000 WHERE guild_id = ? AND faction = ?", (g_id, f_name))
            await db.commit()
        await interaction.response.send_message(f"🏆 管理員已下發榮耀犒賞！【{f_name}】全體陣營成員銀行各入帳 **$50,000**！")

@bot.tree.command(name="金主降臨", description="【系統/管理員專用】為指定陣營金庫無償注入巨額公款")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(陣營名稱="目標陣營", 金額="注入的金庫公款金額")
async def patron_sponsor(interaction: discord.Interaction, 陣營名稱: str, 金額: int):
    g_id = interaction.guild_id
    f_name = 陣營名稱.strip()
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額必須大於 0！", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE factions SET treasury = treasury + ? WHERE guild_id = ? AND name = ?", (金額, g_id, f_name))
        await db.commit()

    await interaction.response.send_message(f"🌟 金主天降！神祕贊助商向【{f_name}】金庫無償注入公款：**+${金額:,}**！")

@bot.tree.command(name="陣營排行", description="查看各大陣營金庫與實力總積分排行榜")
async def faction_leaderboard_cmd(interaction: discord.Interaction):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, treasury FROM factions WHERE guild_id = ? ORDER BY treasury DESC", (g_id,)) as cur:
            rows = await cur.fetchall()

    if not rows:
        await interaction.response.send_message("📋 尚未註冊任何陣營！", ephemeral=True)
        return

    embed = discord.Embed(title="🏆 全服各大勢力陣營積分排行", color=0xF1C40F)
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (name, treasury) in enumerate(rows):
        prefix = medals[i] if i < 3 else f"`#{i+1}`"
        points = treasury // 10
        lines.append(f"{prefix} **{name}** ｜ 金庫：${treasury:,} ｜ 總積分：**{points:,}** 分")

    embed.description = "\n".join(lines)
    embed.set_footer(text="折算規則：每 10 元公款折合 1 點陣營榮譽積分。")
    await interaction.response.send_message(embed=embed)
# -------------------- 指令：金融流通與薪水 --------------------
@bot.tree.command(name="薪水", description="【管理員專用】發放薪水直接匯入角色或 NPC 的手頭現金")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(名字="角色或官方 NPC 名稱", 金額="發放的薪水金額 (純整數)")
async def salary_cmd(interaction: discord.Interaction, 名字: str, 金額: int):
    g_id = interaction.guild_id
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額必須大於 0！", ephemeral=True)
        return

    target_name = 名字.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM characters WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
            if not await cur.fetchone():
                await interaction.response.send_message(f"❌ 查無名為 `{target_name}` 的角色或 NPC！", ephemeral=True)
                return

        await db.execute("UPDATE characters SET cash = cash + ? WHERE guild_id = ? AND name = ?", (金額, g_id, target_name))
        await db.commit()

    await interaction.response.send_message(f"💵 薪水 **${金額:,}** 已成功發放並入帳至【**{target_name}**】的手頭現金！")

@bot.tree.command(name="轉錢", description="將手頭現金轉帳給其他角色或官方 NPC")
@app_commands.describe(轉出者="發起轉帳的名字 (你的角色)", 接收者="收款人的名字", 金額="轉帳金額")
async def transfer(interaction: discord.Interaction, 轉出者: str, 接收者: str, 金額: int):
    g_id = interaction.guild_id
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額需大於 0！", ephemeral=True)
        return

    sender = 轉出者.strip()
    receiver = 接收者.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, cash FROM characters WHERE guild_id = ? AND name = ?", (g_id, sender)) as cur:
            s_row = await cur.fetchone()
            if not s_row:
                await interaction.response.send_message(f"❌ 找不到轉出角色【{sender}】！", ephemeral=True)
                return
            if s_row[0] != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 你只能操作自己持有的角色進行轉帳！", ephemeral=True)
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

@bot.tree.command(name="存錢", description="將手頭現金存入銀行")
@app_commands.describe(名字="角色或 NPC 姓名", 金額="存入金額")
async def deposit(interaction: discord.Interaction, 名字: str, 金額: int):
    g_id = interaction.guild_id
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額需大於 0！", ephemeral=True)
        return

    target = 名字.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, cash FROM characters WHERE guild_id = ? AND name = ?", (g_id, target)) as cur:
            row = await cur.fetchone()
            if not row:
                await interaction.response.send_message(f"❌ 找不到角色【{target}】！", ephemeral=True)
                return
            if row[0] != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 你只能為自己的角色存錢！", ephemeral=True)
                return
            if row[1] < 金額:
                await interaction.response.send_message(f"❌ 現金不足！目前僅有 ${row[1]:,}。", ephemeral=True)
                return

        await db.execute("UPDATE characters SET cash = cash - ?, bank = bank + ? WHERE guild_id = ? AND name = ?", (金額, 金額, g_id, target))
        await db.commit()

    await interaction.response.send_message(f"🏦 **{target}** 成功將 **${金額:,}** 存入銀行帳戶！")

@bot.tree.command(name="取錢", description="從銀行提取現金")
@app_commands.describe(名字="角色或 NPC 姓名", 金額="提領金額")
async def withdraw(interaction: discord.Interaction, 名字: str, 金額: int):
    g_id = interaction.guild_id
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額需大於 0！", ephemeral=True)
        return

    target = 名字.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, target)) as cur:
            row = await cur.fetchone()
            if not row:
                await interaction.response.send_message(f"❌ 找不到角色【{target}】！", ephemeral=True)
                return
            if row[0] != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 你只能為自己的角色提款！", ephemeral=True)
                return
            if row[1] < 金額:
                await interaction.response.send_message(f"❌ 存款不足！當前存款僅有 ${row[1]:,}。", ephemeral=True)
                return

        await db.execute("UPDATE characters SET bank = bank - ?, cash = cash + ? WHERE guild_id = ? AND name = ?", (金額, 金額, g_id, target))
        await db.commit()

    await interaction.response.send_message(f"💵 **{target}** 成功從銀行提領 **${金額:,}** 現金！")

@bot.tree.command(name="利息調整", description="【管理員專用】每 168 小時調整一次銀行利率")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(利率百分比="例如填 5 代表 5%")
async def set_interest(interaction: discord.Interaction, 利率百分比: float):
    g_id = interaction.guild_id
    now = time.time()
    one_week = 168 * 3600

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'last_rate_update'", (g_id,)) as cur:
            row = await cur.fetchone()
            last_update = float(row[0]) if row else 0

        if now - last_update < one_week:
            remain_h = int((one_week - (now - last_update)) / 3600)
            await interaction.response.send_message(f"⏳ 利率冷卻中！還需等待約 **{remain_h}** 小時。", ephemeral=True)
            return

        new_rate = 利率百分比 / 100.0
        await db.execute("""
            INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'interest_rate', ?)
            ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
        """, (g_id, str(new_rate), str(new_rate)))
        await db.execute("""
            INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'last_rate_update', ?)
            ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
        """, (g_id, str(now), str(now)))
        await db.commit()

    await interaction.response.send_message(f"📈 銀行利率已調整為 **{利率百分比}%**！")
# -------------------- 指令：/排行查詢 --------------------
def eval_stat_formula(formula: str, stats: dict) -> int:
    expr = formula
    sorted_keys = sorted(stats.keys(), key=len, reverse=True)
    for k in sorted_keys:
        if k in expr:
            expr = expr.replace(k, str(stats.get(k, 0)))
    expr = re.sub(r"[\u4e00-\u9fa5]+", "0", expr)
    clean_expr = re.sub(r"[^0-9+\-*/().\s]", "", expr)
    try:
        val = eval(clean_expr, {"__builtins__": None}, {})
        return int(val)
    except Exception:
        return 0

class LeaderboardView(discord.ui.View):
    def __init__(self, target_char: str = None, guild_id: int = None):
        super().__init__(timeout=180)
        self.target_char = target_char
        self.guild_id = guild_id

    @discord.ui.button(label="📜 完整榜單", style=discord.ButtonStyle.primary)
    async def full_board(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name, stat_key FROM leaderboards WHERE guild_id = ?", (self.guild_id,)) as cur:
                boards = await cur.fetchall()

        if not boards:
            await interaction.response.send_message("📋 目前尚未建立任何榜單！", ephemeral=True)
            return

        parent_guild = self.guild_id

        class BoardSelect(discord.ui.Select):
            def __init__(self):
                opts = [discord.SelectOption(label=b[0], description=f"依據：{b[1][:50]}", value=f"{b[0]}:{b[1]}") for b in boards[:25]]
                super().__init__(placeholder="請選擇欲調閱的排行榜單...", options=opts)

            async def callback(self, inter: discord.Interaction):
                b_name, formula = self.values[0].split(":", 1)
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT name, stats, rank, is_npc FROM characters WHERE guild_id = ?", (parent_guild,)) as cur:
                        all_chars = await cur.fetchall()

                ranked = []
                for name, s_json, r_name, is_npc_val in all_chars:
                    st = json.loads(s_json) if s_json else {}
                    ranked.append((name, eval_stat_formula(formula, st), is_npc_val > 0, r_name))

                ranked.sort(key=lambda x: x[1], reverse=True)

                embed = discord.Embed(title=f"🏆【{b_name}】全城實力排行", color=0xF1C40F)
                lines = []
                medals = ["🥇", "🥈", "🥉"]
                for i, (cname, val, is_npc, r_name) in enumerate(ranked[:15]):
                    prefix = medals[i] if i < 3 else f"`#{i+1}`"
                    npc_tag = " `[NPC]`" if is_npc else ""
                    lines.append(f"{prefix} **{cname}**{npc_tag} ［{r_name or '未定級'}］ ｜ 得分：**{val:,}**")

                embed.description = "\n".join(lines) if lines else "暫無數據"
                embed.set_footer(text=f"計分依據：{formula}")
                await inter.response.send_message(embed=embed, ephemeral=True)

        v = discord.ui.View()
        v.add_item(BoardSelect())
        await interaction.response.send_message("請選擇想查閱的榜單：", view=v, ephemeral=True)

    @discord.ui.button(label="👤 個人/NPC 排名", style=discord.ButtonStyle.secondary)
    async def personal_rank(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.target_char:
            await interaction.response.send_message("⚠️ 請於發送指令時指定【名字】，以便查詢名次！", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name, stat_key FROM leaderboards WHERE guild_id = ?", (self.guild_id,)) as cur:
                boards = await cur.fetchall()
            async with db.execute("SELECT name, stats FROM characters WHERE guild_id = ?", (self.guild_id,)) as cur:
                all_chars = await cur.fetchall()

        if self.target_char not in [c[0] for c in all_chars]:
            await interaction.response.send_message(f"❌ 查無名為 `{self.target_char}` 的角色或 NPC！", ephemeral=True)
            return

        embed = discord.Embed(title=f"📊【{self.target_char}】各榜單排行成績", color=0x3498DB)
        lines = []

        for b_name, formula in boards:
            ranked = []
            for name, s_json in all_chars:
                ranked.append((name, eval_stat_formula(formula, json.loads(s_json) if s_json else {})))

            ranked.sort(key=lambda x: x[1], reverse=True)
            rank_pos = "未入榜"
            val = 0
            for idx, (cname, score) in enumerate(ranked):
                if cname == self.target_char:
                    rank_pos = f"第 **{idx + 1}** 名"
                    val = score
                    break
            lines.append(f"• **{b_name}**：{rank_pos} ｜ 分數：`{val:,}`")

        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="排行查詢", description="查詢各項實力榜單或查看個人/NPC 的各項榜單名次")
@app_commands.describe(名字="若要查看個人或 NPC 排名，請填寫對應名稱")
async def rank_query(interaction: discord.Interaction, 名字: str = None):
    view = LeaderboardView(target_char=名字, guild_id=interaction.guild_id)
    await interaction.response.send_message("🏆 請選擇你想查看的排行形式：", view=view, ephemeral=True)
# -------------------- 榜單管理、地位門檻與獎勵登記 --------------------
@bot.tree.command(name="榜單管理", description="【管理員專用】新增或修改排行榜單公式")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="新增榜單", value="add"),
    app_commands.Choice(name="修改既有榜單", value="edit")
])
@app_commands.describe(操作="選擇新增或修改榜單", 榜單名字="榜單名稱", 相關數值="計算公式或屬性 (例如: 流量熱度 * 1.5 + 商業價值)")
async def manage_leaderboard(interaction: discord.Interaction, 操作: app_commands.Choice[str], 榜單名字: str, 相關數值: str):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM leaderboards WHERE guild_id = ? AND name = ?", (g_id, 榜單名字.strip())) as cur:
            exists = await cur.fetchone()

        if 操作.value == "add":
            if exists:
                await interaction.response.send_message(f"❌ 榜單 `{榜單名字}` 已存在！", ephemeral=True)
                return
            await db.execute("INSERT INTO leaderboards (guild_id, name, stat_key) VALUES (?, ?, ?)", (g_id, 榜單名字.strip(), 相關數值.strip()))
            op_label = "建立"
        else:
            if not exists:
                await interaction.response.send_message(f"❌ 查無欲修改的榜單 `{榜單名字}`！", ephemeral=True)
                return
            await db.execute("UPDATE leaderboards SET stat_key = ? WHERE guild_id = ? AND name = ?", (相關數值.strip(), g_id, 榜單名字.strip()))
            op_label = "更新"

        await db.commit()

    await interaction.response.send_message(f"🏆 成功{op_label}榜單：**【{榜單名字}】**（公式：`{相關數值}`）！")

@bot.tree.command(name="地位等級限制", description="【管理員專用】設定、新增或修改地位晉級標準")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作模式=[
    app_commands.Choice(name="增加（貼上文字/連結自動解析）", value="add"),
    app_commands.Choice(name="修改（手動微調特定順位標準）", value="edit"),
    app_commands.Choice(name="清單檢視（查看當前所有地位門檻）", value="list")
])
@app_commands.describe(
    操作模式="選擇增加、修改或查看地位規則",
    內容或連結="［增加模式］貼上包含順序、成就、榮譽、數值、人數的文字或帖子連結",
    順序="［修改模式］欲修改的地位級別 (純數字，越小越高)",
    地位等級="［修改模式］地位名稱 (如: 一線巨星、頂流領袖)",
    成就限制="［修改模式］成就條件 (如: 史詩歷練2, 終極冒險1)",
    榮譽限制="［修改模式］榮譽標籤條件 (如: 奢華2, 傳說1)",
    數值限制="［修改模式］數值門檻 (如: 商業價值500, 流量熱度300)",
    人數="［修改模式］席位名額限制 (填 0 為不限名額)"
)
async def rank_setting_cmd(
    interaction: discord.Interaction,
    操作模式: app_commands.Choice[str],
    內容或連結: str = None,
    順序: int = None,
    地位等級: str = None,
    成就限制: str = "",
    榮譽限制: str = "",
    數值限制: str = "",
    人數: int = 0
):
    g_id = interaction.guild_id
    mode = 操作模式.value

    if mode == "list":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT rank_order, rank_name, work_req, endorse_req, stat_req, max_slots FROM rank_settings WHERE guild_id = ? ORDER BY rank_order ASC", (g_id,)) as cur:
                rows = await cur.fetchall()

        if not rows:
            await interaction.response.send_message("📋 尚未建立任何地位限制等級！", ephemeral=True)
            return

        embed = discord.Embed(title="👑 地位限制規範一覽表", color=0xF1C40F)
        for r_order, r_name, w_req, e_req, s_req, slots in rows:
            slot_str = f"限量 {slots} 人" if slots > 0 else "名額不限"
            detail = f"• 成就限制：{w_req or '無'}\n• 榮譽限制：{e_req or '無'}\n• 數值限制：{s_req or '無'}\n• 席位限制：{slot_str}"
            embed.add_field(name=f"順序 {r_order} ｜ 【{r_name}】", value=detail, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if mode == "edit":
        if 順序 is None or not 地位等級:
            await interaction.response.send_message("❌ 修改模式下，**【順序】與【地位等級】為必填項目**！", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO rank_settings (guild_id, rank_order, rank_name, work_req, endorse_req, stat_req, max_slots)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, rank_order) DO UPDATE SET
                    rank_name = excluded.rank_name,
                    work_req = excluded.work_req,
                    endorse_req = excluded.endorse_req,
                    stat_req = excluded.stat_req,
                    max_slots = excluded.max_slots
            """, (g_id, 順序, 地位等級.strip(), 成就限制.strip(), 榮譽限制.strip(), 數值限制.strip(), 人數))
            await db.commit()

        await interaction.response.send_message(f"✅ 已成功更新順位 **{順序}** 之地位【**{地位等級}**】標準！", ephemeral=True)
        return

    if mode == "add":
        if not 內容或連結:
            await interaction.response.send_message("❌ 增加模式下，請於【內容或連結】欄位貼上文字或文章連結！", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        raw_text = 內容或連結

        link_match = re.search(r"channels/\d+/(\d+)(?:/(\d+))?", 內容或連結)
        if link_match:
            c_id = int(link_match.group(1))
            m_id = int(link_match.group(2)) if link_match.group(2) else None
            try:
                ch = interaction.client.get_channel(c_id) or await interaction.client.fetch_channel(c_id)
                if isinstance(ch, discord.Thread):
                    first_msg = None
                    async for msg in ch.history(limit=3, oldest_first=True):
                        first_msg = msg
                        break
                    raw_text = first_msg.content if first_msg else ch.name
                elif m_id:
                    msg = await ch.fetch_message(m_id)
                    raw_text = msg.content
            except Exception as e:
                await interaction.followup.send(f"❌ 讀取連結內容失敗: {e}", ephemeral=True)
                return

        order_match = re.search(r"(?:順序|順位|級別|等級)[^\d]*(\d+)", raw_text)
        rank_name_match = re.search(r"(?:地位|稱號|頭銜|階級)[^\w]*([^\n\r,，]+)", raw_text)
        work_match = re.search(r"(?:成就限制|成就需求|成就|歷練)[^\n\r:]*[:：]?([^\n\r]+)", raw_text)
        endorse_match = re.search(r"(?:榮譽限制|榮譽需求|榮譽|稱號)[^\n\r:]*[:：]?([^\n\r]+)", raw_text)
        stat_match = re.search(r"(?:數值限制|數值需求|屬性)[^\n\r:]*[:：]?([^\n\r]+)", raw_text)
        slots_match = re.search(r"(?:人數|名額|席位)[^\d]*(\d+)", raw_text)

        parsed_order = int(order_match.group(1)) if order_match else 1
        parsed_name = rank_name_match.group(1).strip() if rank_name_match else "未命名地位"
        parsed_work = work_match.group(1).strip() if work_match else ""
        parsed_endorse = endorse_match.group(1).strip() if endorse_match else ""
        parsed_stat = stat_match.group(1).strip() if stat_match else ""
        parsed_slots = int(slots_match.group(1)) if slots_match else 0

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO rank_settings (guild_id, rank_order, rank_name, work_req, endorse_req, stat_req, max_slots)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, rank_order) DO UPDATE SET
                    rank_name = excluded.rank_name,
                    work_req = excluded.work_req,
                    endorse_req = excluded.endorse_req,
                    stat_req = excluded.stat_req,
                    max_slots = excluded.max_slots
            """, (g_id, parsed_order, parsed_name, parsed_work, parsed_endorse, parsed_stat, parsed_slots))
            await db.commit()

        await interaction.followup.send(
            f"🎉 成功錄入地位標準！\n"
            f"• 順位：`#{parsed_order}`\n"
            f"• 地位名稱：**【{parsed_name}】**\n"
            f"• 成就限制：`{parsed_work or '無'}`\n"
            f"• 榮譽限制：`{parsed_endorse or '無'}`\n"
            f"• 數值限制：`{parsed_stat or '無'}`\n"
            f"• 席位名額：`{parsed_slots if parsed_slots > 0 else '不限'}`"
        )

@bot.tree.command(name="獎勵登記", description="【管理員專用】下發綜合獎勵（金錢入銀行、物品入背包、數值加總）")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    名字="角色或 NPC 名稱",
    金錢="匯入銀行的金額 (可填 0)",
    物品名稱="直接匯入背包的道具名 (選填)",
    物品數量="匯入背包的數量 (預設 1)",
    數值名稱="增加的數值項目 (例如: 容貌、才智)",
    數值點數="增加的點數 (可填 0)"
)
async def admin_reward(
    interaction: discord.Interaction,
    名字: str,
    金錢: int = 0,
    物品名稱: str = None,
    物品數量: int = 1,
    數值名稱: str = None,
    數值點數: int = 0
):
    g_id = interaction.guild_id
    target_name = 名字.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
            row = await cur.fetchone()

        if not row:
            await interaction.response.send_message(f"❌ 查無名為 `{target_name}` 的角色或 NPC！", ephemeral=True)
            return

        stats = json.loads(row[0]) if row[0] else {}
        reward_msgs = []

        if 金錢 > 0:
            await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (金錢, g_id, target_name))
            reward_msgs.append(f"💰 銀行存款 +${金錢:,}")

        if 物品名稱:
            async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ? AND giver = '管理員獎勵'", (g_id, target_name, 物品名稱)) as cur:
                inv_row = await cur.fetchone()
                if inv_row:
                    await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (物品數量, inv_row[0]))
                else:
                    await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, ?, '管理員獎勵')", (g_id, target_name, 物品名稱, 物品數量))
            reward_msgs.append(f"📦 物品 **{物品名稱}** ×{物品數量}")

        if 數值名稱 and 數值點數 != 0:
            stats[數值名稱] = stats.get(數值名稱, 0) + 數值點數
            await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(stats, ensure_ascii=False), g_id, target_name))
            reward_msgs.append(f"✨ 數值【{數值名稱}】+{數值點數} (總計: {stats[數值名稱]})")

        await db.commit()

    await check_and_update_rank(g_id, target_name, interaction.channel)
    detail = " ｜ ".join(reward_msgs) if reward_msgs else "無實質資產變動"
    await interaction.response.send_message(f"🎁 管理員已成功為【{target_name}】發放資源：\n{detail}")
# -------------------- 抽獎系統指令 --------------------
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

@bot.tree.command(name="查看獎項", description="查看目前所有發布中的抽獎活動與剩餘狀態")
async def view_lottery(interaction: discord.Interaction):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT pool_name, items_json, allow_repeat, role_id FROM lottery_pools WHERE guild_id = ?", (g_id,)) as cur:
            pools = await cur.fetchall()

    if not pools:
        await interaction.response.send_message("📋 目前尚未舉辦任何抽獎活動！", ephemeral=True)
        return

    embed = discord.Embed(title="🎊 抽獎活動一覽", description="請前往對應討論串輸入 `/我要抽獎` 進行抽取：", color=0xF1C40F)
    for p_name, i_json, allow_rep, r_id in pools[:10]:
        items = json.loads(i_json) if i_json else []
        item_str = " ".join([f"{it.get('name')}×{it.get('amount')}" for it in items])
        r_info = f"<@&{r_id}>" if r_id > 0 else "全員可抽"
        rep_info = "可重複抽" if allow_rep == "yes" else "不可重複"
        embed.add_field(name=f"🎯 {p_name}", value=f"• 包含獎項：{item_str}\n• 資格：{r_info} ｜ {rep_info}", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="我要抽獎", description="在對應獎項的討論串中進行抽獎（討論串名需與獎項名相同）")
async def play_lottery(interaction: discord.Interaction):
    g_id = interaction.guild_id
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message("❌ **【我要抽獎】只能在專屬的獎項討論串內使用！**", ephemeral=True)
        return

    thread_name = interaction.channel.name.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT items_json, allow_repeat, role_id FROM lottery_pools WHERE guild_id = ? AND pool_name = ?",
            (g_id, thread_name)
        ) as cur:
            pool = await cur.fetchone()

        if not pool:
            await interaction.response.send_message(f"❌ 查無與當前討論串【**{thread_name}**】同名的抽獎活動！", ephemeral=True)
            return

        items_json, allow_repeat, req_role = pool
        items = json.loads(items_json) if items_json else []

        if not items:
            await interaction.response.send_message(f"😢 很遺憾，【{thread_name}】的所有獎品已經被全數抽完，活動已結束！", ephemeral=True)
            return

        if req_role > 0:
            user_role_ids = [r.id for r in interaction.user.roles]
            if req_role not in user_role_ids:
                await interaction.response.send_message(f"🚫 資格不符！本獎項限定持有身分組 <@&{req_role}> 才能抽取。", ephemeral=True)
                return

        # 隨機抽取一件獎品
        chosen_idx = random.randrange(len(items))
        chosen_item = items[chosen_idx]
        won_name = chosen_item["name"]

        # 不可重複抽取時扣減庫存
        if allow_repeat == "no":
            chosen_item["amount"] -= 1
            if chosen_item["amount"] <= 0:
                items.pop(chosen_idx)
            await db.execute("UPDATE lottery_pools SET items_json = ? WHERE guild_id = ? AND pool_name = ?", (json.dumps(items, ensure_ascii=False), g_id, thread_name))

        # 發放獎品至該使用者的角色背包（預設取第一位擁有的角色）
        async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND user_id = ? LIMIT 1", (g_id, interaction.user.id)) as u_cur:
            char_row = await u_cur.fetchone()
            if char_row:
                c_name = char_row[0]
                async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, c_name, won_name)) as inv_cur:
                    inv_entry = await inv_cur.fetchone()
                    if inv_entry:
                        await db.execute("UPDATE inventory SET amount = amount + 1 WHERE id = ?", (inv_entry[0],))
                    else:
                        await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, 1, '幸運抽獎')", (g_id, c_name, won_name))

        await db.commit()

    await interaction.response.send_message(f"🎰✨ **【幸運開獎】** ✨🎰\n恭喜 {interaction.user.mention} 成功在【{thread_name}】抽中了：\n🎁 **{won_name}**！已自動發放至角色背包。")
# -------------------- 指令：/路人資源補給 --------------------
@bot.tree.command(name="路人資源補給", description="【管理員專用】批次補充路人相冊、姓名庫、影視作品與品牌代言庫")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    貼文或相冊連結="選填：貼上 Discord 討論串/訊息連結，自動解析相片、作品席位與代言",
    地區分類="若有補充姓名時選擇 (東方/西方/南美/非洲)",
    姓氏串="選填：空白隔開的姓氏",
    名字串="選填：空白隔開的名字",
    新增照片檔案="選填：直接上傳一張相片入庫"
)
async def supply_crowd_resources(
    interaction: discord.Interaction,
    貼文或相冊連結: str = None,
    地區分類: str = "東方",
    姓氏串: str = None,
    名字串: str = None,
    新增照片檔案: discord.Attachment = None
):
    g_id = interaction.guild_id
    await interaction.response.defer(ephemeral=True)
    added_photos, added_names, added_works, added_endorsements = 0, 0, 0, 0

    async with aiosqlite.connect(DB_PATH) as db:
        if 新增照片檔案:
            await db.execute("INSERT INTO crowd_photos (guild_id, image_url, gender) VALUES (?, ?, '通用')", (g_id, 新增照片檔案.url))
            added_photos += 1

        if 貼文或相冊連結:
            link_match = re.search(r"channels/\d+/(\d+)(?:/(\d+))?", 貼文或相冊連結)
            if link_match:
                c_id = int(link_match.group(1))
                m_id = int(link_match.group(2)) if link_match.group(2) else None
                try:
                    ch = interaction.client.get_channel(c_id) or await interaction.client.fetch_channel(c_id)
                    messages = []
                    if isinstance(ch, discord.Thread):
                        async for msg in ch.history(limit=30): messages.append(msg)
                    elif m_id:
                        messages.append(await ch.fetch_message(m_id))

                    for m in messages:
                        for att in m.attachments:
                            if any(att.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']):
                                await db.execute("INSERT INTO crowd_photos (guild_id, image_url, gender) VALUES (?, ?, '通用')", (g_id, att.url))
                                added_photos += 1

                        for line in m.content.splitlines():
                            line = line.strip()
                            work_match = re.search(r"《([^》]+)》[/\s]+([^\s]+)(.*)", line)
                            if work_match:
                                w_title = work_match.group(1).strip()
                                w_type = work_match.group(2).strip()
                                is_var = 1 if "綜藝" in w_type else 0
                                for token in work_match.group(3).strip().split():
                                    r_match = re.match(r"([男女]?[^\d]+)(\d+)?", token)
                                    if r_match:
                                        r_name = r_match.group(1).strip()
                                        r_count = int(r_match.group(2)) if r_match.group(2) else 1
                                        r_gen = "男" if "男" in r_name else ("女" if "女" in r_name else "通用")
                                        job_lim = "全體" if is_var else "演員"
                                        for _ in range(r_count):
                                            await db.execute("""
                                                INSERT INTO crowd_works (guild_id, title, work_type, role_name, gender, job_limit, is_variety)
                                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                            """, (g_id, w_title, w_type, r_name, r_gen, job_lim, is_variety))
                                            added_works += 1

                            end_match = re.search(r"代言[：:]\s*([^/\s]+)[/\s]+([^\s]+)", line)
                            if end_match:
                                await db.execute("""
                                    INSERT INTO crowd_endorsements (guild_id, brand_name, level_title, gender, job_limit)
                                    VALUES (?, ?, ?, '通用', '全體')
                                """, (g_id, end_match.group(1).strip(), end_match.group(2).strip()))
                                added_endorsements += 1
                except Exception:
                    pass

        if 姓氏串:
            for s in re.split(r"[,，\s]+", 姓氏串.strip()):
                if s:
                    await db.execute("INSERT INTO crowd_names (guild_id, region, name_type, gender, val) VALUES (?, ?, 'surname', '通用', ?)", (g_id, 地區分類, s))
                    added_names += 1
        if 名字串:
            for f in re.split(r"[,，\s]+", 名字串.strip()):
                if f:
                    await db.execute("INSERT INTO crowd_names (guild_id, region, name_type, gender, val) VALUES (?, ?, 'firstname', '通用', ?)", (g_id, 地區分類, f))
                    added_names += 1

        await db.commit()

    embed = discord.Embed(title="📦 大眾路人資源入庫成果", color=0x3498DB)
    embed.add_field(name="相冊與姓名", value=f"• 照片入庫：**+{added_photos}** 張\n• 姓名庫入庫：**+{added_names}** 筆", inline=False)
    embed.add_field(name="作品席位與代言", value=f"• 角色席位：**+{added_works}** 席\n• 品牌代言：**+{added_endorsements}** 個", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)
# -------------------- 指令：/大眾路人大量發生中 --------------------
@bot.tree.command(name="大眾路人大量發生中", description="【管理員專用】全自動生成具備作品、代言與出道歷練的路人角色")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(體系偏好=[
    app_commands.Choice(name="隨機混血／全文化混抽", value="random"),
    app_commands.Choice(name="限定東方風格", value="東方"),
    app_commands.Choice(name="限定西方風格", value="西方"),
    app_commands.Choice(name="限定南美風格", value="南美"),
    app_commands.Choice(name="限定非洲風格", value="非洲")
])
@app_commands.choices(性別偏好=[
    app_commands.Choice(name="隨機性別", value="隨機"),
    app_commands.Choice(name="男", value="男"),
    app_commands.Choice(name="女", value="女")
])
@app_commands.describe(生成數量="一次生成數量 (1～5)", 體系偏好="文化風格", 性別偏好="性別")
async def spawn_crowd_batch(
    interaction: discord.Interaction,
    生成數量: int = 1,
    體系偏好: app_commands.Choice[str] = None,
    性別偏好: app_commands.Choice[str] = None
):
    g_id = interaction.guild_id
    await interaction.response.defer(ephemeral=False)
    count = max(1, min(5, 生成數量))
    created_list, low_photo_warn = [], False

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'custom_nationalities'", (g_id,)) as cur:
            c_nat_row = await cur.fetchone()
            custom_nats = json.loads(c_nat_row[0]) if c_nat_row else []

        async with db.execute("SELECT rank_name FROM rank_settings WHERE guild_id = ? ORDER BY rank_order DESC", (g_id,)) as cur:
            all_ranks = [r[0] for r in await cur.fetchall()]
        default_rank = all_ranks[0] if all_ranks else "未定級"

        for _ in range(count):
            gen = 性別偏好.value if (性別偏好 and 性別偏好.value != "隨機") else random.choice(["男", "女"])
            chosen_reg = 體系偏好.value if (體系偏好 and 體系偏好.value != "random") else random.choice(["東方", "西方", "南美", "非洲"])

            async with db.execute("SELECT val FROM crowd_names WHERE guild_id = ? AND region = ? AND name_type = 'surname' AND gender IN (?, '通用') ORDER BY RANDOM() LIMIT 1", (g_id, chosen_reg, gen)) as cur:
                s_row = await cur.fetchone()
            async with db.execute("SELECT val FROM crowd_names WHERE guild_id = ? AND region = ? AND name_type = 'firstname' AND gender IN (?, '通用') ORDER BY RANDOM() LIMIT 1", (g_id, chosen_reg, gen)) as cur:
                f_row = await cur.fetchone()

            if chosen_reg == "東方":
                surname = s_row[0] if s_row else random.choice(["沈", "顧", "林", "裴", "許", "江"])
                firstname = f_row[0] if f_row else random.choice(["星川", "晚寧", "知意", "野", "淮", "瑤"])
                full_name = f"{surname}{firstname}"
                nation = random.choice(custom_nats or EASTERN_NATIONS)
            elif chosen_reg == "南美":
                surname = s_row[0] if s_row else random.choice(["席爾瓦", "桑托斯", "羅德里奎茲"])
                firstname = f_row[0] if f_row else random.choice(["盧卡斯", "馬特奧", "索菲亞"])
                full_name = f"{firstname}•{surname}"
                nation = random.choice(SOUTH_AMERICAN_NATIONS)
            elif chosen_reg == "非洲":
                surname = s_row[0] if s_row else random.choice(["奧卡福", "曼德拉", "特拉奧雷"])
                firstname = f_row[0] if f_row else random.choice(["阿瑪拉", "贊達", "卡里姆"])
                full_name = f"{firstname}•{surname}"
                nation = random.choice(AFRICAN_NATIONS)
            else:
                surname = s_row[0] if s_row else random.choice(["斯圖爾特", "羅曼諾夫", "溫莎"])
                firstname = f_row[0] if f_row else random.choice(["安妮", "維克多", "奧利維亞"])
                full_name = f"{firstname}•{surname}"
                nation = random.choice(WESTERN_NATIONS)

            age = random.randint(16, 50)
            height = random.randint(172, 192) if gen == "男" else random.randint(158, 176)
            job = random.choice(CROWD_JOBS)

            max_debut = max(0, age - 5)
            debut_years = random.randint(0, max_debut)
            debut_age = age - debut_years

            raw_tags = random.sample(get_available_tags_for(age, gen), k=random.randint(1, 2))
            if 5 <= debut_age <= 12:
                kid_tag = "國民弟弟" if gen == "男" and age <= 22 else ("國民妹妹" if gen == "女" and age <= 22 else ("國民兒子" if gen == "男" else "國民女兒"))
                if kid_tag not in raw_tags: raw_tags.append(kid_tag)
            tags = "、".join(raw_tags[:5])
            rel_status = random.choice(CROWD_RELATIONS)

            async with db.execute("SELECT id, image_url FROM crowd_photos WHERE guild_id = ? AND used = 0 AND gender IN (?, '通用') ORDER BY RANDOM() LIMIT 1", (g_id, gen)) as cur:
                p_row = await cur.fetchone()
            img_url = ""
            if p_row:
                p_id, img_url = p_row
                await db.execute("UPDATE crowd_photos SET used = 1 WHERE id = ?", (p_id,))

            works_history = []
            async with db.execute("""
                SELECT id, title, work_type, role_name FROM crowd_works
                WHERE guild_id = ? AND gender IN (?, '通用') AND (job_limit = '全體' OR job_limit = ?)
                ORDER BY RANDOM() LIMIT ?
            """, (g_id, gen, job, random.randint(2, 3))) as w_cur:
                for w_id, w_title, w_type, r_name in await w_cur.fetchall():
                    works_history.append({"category": "成就", "type": w_type, "title": w_title, "extra": f"角色: {r_name}"})

            async with db.execute("""
                SELECT id, brand_name, level_title FROM crowd_endorsements
                WHERE guild_id = ? AND gender IN (?, '通用') AND (job_limit = '全體' OR job_limit = ?)
                ORDER BY RANDOM() LIMIT ?
            """, (g_id, gen, job, random.randint(2, 4))) as e_cur:
                for e_id, b_name, l_title in await e_cur.fetchall():
                    works_history.append({"category": "榮譽", "type": "品牌代言", "title": f"【{b_name}】{l_title}", "extra": "官方商業合約"})

            stat_names = ["流量熱度", "商業價值", "路人緣", "公關", "影響指數", "容貌", "才智", "個人才藝", "演繹", "唱跳"]
            stats = {k: random.randint(300, 2500) for k in stat_names}
            stats["死忠粉絲數"] = random.randint(500, 15000)
            stats["活躍黑粉數"] = random.randint(50, 3000)
            stats["大眾認知度"] = random.randint(200, 2000)

            await db.execute("""
                INSERT INTO characters (
                    guild_id, user_id, name, age, gender, job, faction, tags,
                    relationship_status, created_at, is_npc, image_url, cash, bank, stats, rank, nationality, height, works, debut_years, debut_age
                ) VALUES (?, 0, ?, ?, ?, ?, '無', ?, ?, ?, 3, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                g_id, full_name, age, gen, job, tags, rel_status, time.time(), img_url,
                random.randint(8000, 50000), random.randint(50000, 300000),
                json.dumps(stats, ensure_ascii=False), default_rank, nation, height,
                json.dumps(works_history, ensure_ascii=False), debut_years, debut_age
            ))
            created_list.append((full_name, gen, age, nation, job, debut_years, debut_age, len(works_history), img_url))

        async with db.execute("SELECT COUNT(*) FROM crowd_photos WHERE guild_id = ? AND used = 0", (g_id,)) as cur:
            rem_photos = (await cur.fetchone())[0]
            if rem_photos <= 5: low_photo_warn = True

        await db.commit()

    embed = discord.Embed(title=f"🎭 成功生成 {len(created_list)} 位動態路人角", color=0x1ABC9C)
    for c in created_list:
        embed.add_field(name=f"🌟 {c[0]} ({c[1]} / {c[3]})", value=f"• 年齡/身分：{c[2]}歲 ｜ {c[4]}\n• 出道歷練：**{c[5]} 年** ({c[6]}歲出道)\n• 演藝資歷：帶入 **{c[7]}** 項作品與品牌代言", inline=False)
    if len(created_list) == 1 and created_list[0][8]:
        embed.set_thumbnail(url=created_list[0][8])

    warn_msg = f"\n🚨 **【相冊預警】** 庫存僅剩 **{rem_photos}** 張未使用相片！" if low_photo_warn else ""
    await interaction.followup.send(content=warn_msg if low_photo_warn else None, embed=embed)
# -------------------- 指令：/路人生態設定 --------------------
@bot.tree.command(name="路人生態設定", description="【管理員專用】調整大眾路人每 48 小時浮動規則，或自訂國籍地區名冊")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(計算模式=[
    app_commands.Choice(name="百分比浮動 (例如 ±5%)", value="percent"),
    app_commands.Choice(name="固定點數浮動 (例如 ±50點)", value="fixed")
])
@app_commands.choices(金錢是否浮動=[
    app_commands.Choice(name="是（資產與數值連帶波動）", value="1"),
    app_commands.Choice(name="否（僅屬性能力浮動）", value="0")
])
@app_commands.describe(
    計算模式="選擇增減是按比例還是固定點數",
    增減量="純數字。若選百分比填 5 代表 ±5%；若選固定點數填 50 代表 ±50 點",
    單項最高上限="數值最高上限 (預設 3000)",
    金錢是否浮動="資產是否隨市場波動",
    自訂國家清單="【選填】新增/覆蓋自訂國籍名冊，空白隔開（例如: 香港 台灣 摩納哥 冰島）"
)
async def setting_crowd_npc(
    interaction: discord.Interaction,
    計算模式: app_commands.Choice[str],
    增減量: float,
    金錢是否浮動: app_commands.Choice[str],
    單項最高上限: int = 3000,
    自訂國家清單: str = None
):
    g_id = interaction.guild_id
    rate_val = (增減量 / 100.0) if 計算模式.value == "percent" else 增減量

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'npc_fluct_mode', ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = ?", (g_id, 計算模式.value, 計算模式.value))
        await db.execute("INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'npc_fluct_rate', ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = ?", (g_id, str(rate_val), str(rate_val)))
        await db.execute("INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'npc_fluct_money', ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = ?", (g_id, 金錢是否浮動.value, 金錢是否浮動.value))
        await db.execute("INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'npc_fluct_cap', ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = ?", (g_id, str(單項最高上限), str(單項最高上限)))

        nat_note = ""
        if 自訂國家清單:
            nats = [n.strip() for n in re.split(r"[,，\s]+", 自訂國家清單.strip()) if n.strip()]
            if nats:
                await db.execute("INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'custom_nationalities', ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = ?", (g_id, json.dumps(nats, ensure_ascii=False), json.dumps(nats, ensure_ascii=False)))
                nat_note = f"\n🌍 **自訂國籍地區已登記**：`{'、'.join(nats)}`"
        await db.commit()

    unit_desc = f"±{增減量}%" if 計算模式.value == "percent" else f"±{int(增減量)} 點"
    embed = discord.Embed(title="⚙️ 大眾路人生態行情已更新", color=0x2ECC71)
    embed.add_field(name="48小時波動機制", value=f"【{計算模式.name}】（幅度：`{unit_desc}`）", inline=False)
    embed.add_field(name="金錢資產連動", value="已開啟" if 金錢是否浮動.value == "1" else "已關閉", inline=True)
    embed.add_field(name="屬性天花板", value=f"最高 {單項最高上限} 點", inline=True)
    await interaction.response.send_message(f"生態設定保存完畢！{nat_note}", embed=embed)

# -------------------- 指令：/發布傳聞 --------------------
@bot.tree.command(name="發布傳聞", description="【管理員專用】針對角色發布一句圈內傳聞（自動統計關鍵字貼標）")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(角色名="目標角色名稱", 傳聞內容="寫下一句傳聞")
async def add_rumor_cmd(interaction: discord.Interaction, 角色名: str, 傳聞內容: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    r_text = 傳聞內容.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT age, gender, tags FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            row = await cur.fetchone()
            if not row:
                await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
                return
            age, gen, tags_str = row

        await db.execute("INSERT INTO character_rumors (guild_id, char_name, rumor_text, created_at) VALUES (?, ?, ?, ?)", (g_id, c_name, r_text, time.time()))
        async with db.execute("SELECT rumor_text FROM character_rumors WHERE guild_id = ? AND char_name = ?", (g_id, c_name)) as cur:
            all_r = [r[0] for r in await cur.fetchall()]

        curr_tags = [t.strip() for t in tags_str.split("、") if t.strip()] if tags_str else []
        avail_pool = get_available_tags_for(age, gen)
        tag_changed, new_tag_added = False, ""

        for tag in avail_pool:
            if tag not in curr_tags:
                if sum(1 for t in all_r if tag in t) >= 3:
                    curr_tags = resolve_tag_conflicts(curr_tags, tag)
                    tag_changed = True
                    new_tag_added = tag
                    break

        if tag_changed:
            new_tags_str = "、".join(curr_tags)
            await db.execute("UPDATE characters SET tags = ? WHERE guild_id = ? AND name = ?", (new_tags_str, g_id, c_name))
        await db.commit()

    bonus_msg = f"\n🔥 **【輿論反響】** 坊間傳聞發酵！【{c_name}】被貼上新標籤：`{new_tag_added}`！（目前標籤：`{new_tags_str}`）" if tag_changed else ""
    await interaction.response.send_message(f"📢 圈內傳聞已記錄至【{c_name}】檔案中：\n> *「{r_text}」*{bonus_msg}")

# -------------------- 指令：/標籤與衝突管理 --------------------
@bot.tree.command(name="標籤與衝突管理", description="【管理員專用】檢視或設定特定標籤互斥規則")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(標籤名稱="欲查詢或設定的標籤", 衝突對象="欲與之互斥的標籤名稱")
async def manage_tag_conflicts(interaction: discord.Interaction, 標籤名稱: str, 衝突對象: str = None):
    t_name = 標籤名稱.strip()
    if 衝突對象:
        c_target = 衝突對象.strip()
        TAG_CONFLICTS.setdefault(t_name, []).append(c_target)
        TAG_CONFLICTS.setdefault(c_target, []).append(t_name)
        await interaction.response.send_message(f"✅ 成功將【{t_name}】與【{c_target}】設為雙向互斥標籤！", ephemeral=True)
    else:
        conflicts = TAG_CONFLICTS.get(t_name, [])
        c_str = "、".join(conflicts) if conflicts else "無互斥衝突設定"
        await interaction.response.send_message(f"🏷️ 標籤【{t_name}】目前互斥組包含：`{c_str}`", ephemeral=True)

# -------------------- 指令：/寵物購買 --------------------
@bot.tree.command(name="寵物購買", description="在寵物店購買毛小孩並取名（自帶壽命年限與健康度）")
@app_commands.choices(品種=[
    app_commands.Choice(name="🐕 忠誠柴犬 (壽命 15 年 / 售價 $15,000)", value="柴犬:15:15000"),
    app_commands.Choice(name="🐈 英國短毛貓 (壽命 16 年 / 售價 $18,000)", value="英短貓:16:18000"),
    app_commands.Choice(name="🐩 貴賓犬 (壽命 14 年 / 售價 $12,000)", value="貴賓犬:14:12000"),
    app_commands.Choice(name="🦜 虎皮鸚鵡 (壽命 8 年 / 售價 $6,000)", value="虎皮鸚鵡:8:6000"),
    app_commands.Choice(name="🐰 侏儒兔 (壽命 7 年 / 售價 $5,000)", value="侏儒兔:7:5000")
])
@app_commands.describe(角色名="購買寵物的角色名稱", 寵物自訂暱稱="替寵物取個好聽的名字")
async def buy_pet_cmd(interaction: discord.Interaction, 角色名: str, 品種: app_commands.Choice[str], 寵物自訂暱稱: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    pet_type, life_years_str, price_str = 品種.value.split(":")
    life_years, price = int(life_years_str), int(price_str)
    pet_custom_name = 寵物自訂暱稱.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT cash, bank, user_id FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            row = await cur.fetchone()
            if not row:
                await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
                return
            cash, bank, u_id = row

        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 你只能為自己的角色購買寵物！", ephemeral=True)
            return

        if cash + bank < price:
            await interaction.response.send_message(f"❌ 總資金不足以支付寵物費用 ${price:,}！", ephemeral=True)
            return

        if cash >= price:
            await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (price, g_id, c_name))
        else:
            await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (price - cash, g_id, c_name))

        now = time.time()
        death_ts = now + (life_years * 30 * 86400)
        await db.execute("""
            INSERT INTO character_pets (guild_id, owner_name, pet_type, pet_name, health, lifespan_years, adopted_at, death_time)
            VALUES (?, ?, ?, ?, 500, ?, ?, ?)
        """, (g_id, c_name, pet_type, pet_custom_name, life_years, now, death_ts))
        await db.commit()

    await interaction.response.send_message(
        f"🐾 恭喜 **{c_name}** 認養了一隻【{pet_type}】！\n"
        f"• 寵物暱稱：**{pet_custom_name}**\n"
        f"• 初始健康值：`500 / 500` (每天扣減 5 點，需使用飼料照顧)\n"
        f"• 預估壽命：`{life_years} 年`"
    )

# -------------------- 指令：/喪禮結算 --------------------
@bot.tree.command(name="喪禮結算", description="完成離世寵物悼念文章後回報（結算路人緣、死忠粉與公益邀約）")
@app_commands.describe(角色名="主人角色名稱", 寵物暱稱="離世寵物名字", 悼念貼文連結="悼念文章訊息連結")
async def pet_funeral_settle(interaction: discord.Interaction, 角色名: str, 寵物暱稱: str, 悼念貼文連結: str):
    g_id = interaction.guild_id
    c_name, p_name = 角色名.strip(), 寵物暱稱.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, is_dead, funeral_done FROM character_pets WHERE guild_id = ? AND owner_name = ? AND pet_name = ?", (g_id, c_name, p_name)) as cur:
            pet = await cur.fetchone()
            if not pet:
                await interaction.response.send_message(f"❌ 查無【{c_name}】名下寵物【{p_name}】！", ephemeral=True)
                return
            pet_id, is_dead, funeral_done = pet

        if is_dead == 0:
            await interaction.response.send_message(f"⚠️ 寵物【{p_name}】仍在世健康生活，無法舉辦喪禮！", ephemeral=True)
            return
        if funeral_done == 1:
            await interaction.response.send_message(f"⚠️ 寵物【{p_name}】的喪禮已經結算過，不可重複回報！", ephemeral=True)
            return

        async with db.execute("SELECT stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            st = json.loads((await cur.fetchone())[0] or "{}")

        st["路人緣"] = st.get("路人緣", 0) + 300
        st["死忠粉"] = st.get("死忠粉", 0) + 200
        st["流量熱度"] = st.get("流量熱度", 0) + 250

        charity_offer = ""
        if random.random() <= 0.10:
            charity_offer = "\n🌟 **【意外邀約】** 你的真情流露獲得了 **「愛護動物收容中心・年度公益大使」** 邀約！"

        await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(st, ensure_ascii=False), g_id, c_name))
        await db.execute("UPDATE character_pets SET funeral_done = 1 WHERE id = ?", (pet_id,))
        await db.commit()

    await interaction.response.send_message(
        f"🕯️ **【告別與紀念】**\n**{c_name}** 為寵物【**{p_name}**】舉辦了深情的告別喪禮。\n"
        f"• 獲得屬性：`路人緣 +300` ｜ `死忠粉 +200` ｜ `流量熱度 +250`{charity_offer}"
    )
# -------------------- 指令：/檔案總覽（全面同步新功能） --------------------
class MasterDirectoryView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id

    @discord.ui.button(label="📜 一般指令", style=discord.ButtonStyle.primary, row=0)
    async def cmd_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        text = (
            "**👤 玩家常規指令列表：**\n"
            "• `/檔案建立`：建立玩家角色或玩家自設 NPC\n"
            "• `/查看`：調閱個人/NPC面板、成就、寵物、傳聞與專屬劇情\n"
            "• `/劇情觸發`：滿足門檻後，與官方 NPC 觸發帶立繪與分支的對話劇情\n"
            "• `/社交關注`、`/社交拉黑`：社群動態互動，影響雙方粉絲與黑粉\n"
            "• `/背包`、`/使用`、`/贈予`：道具管理、屬性即時成長與送禮（同鄉加成）\n"
            "• `/商城`、`/售物`：選購官方/二手/公司門市商品，原創作品享才智溢價\n"
            "• `/存錢`、`/取錢`、`/轉錢`：銀行金融交易與角色互轉\n"
            "• `/任務`、`/回報任務`：查看公告看板、回報文章（自動陣營抽稅與地位晉升）\n"
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
            "• `/路人轉官方`：一鍵將熱門動態路人升格為官方 NPC（保留所有數值外觀）\n"
            "• `/劇本設定`：為官方 NPC 錄入多分支劇情劇本、按鈕與解鎖條件\n"
            "• `/社群頻道設定`、`/社群規則管理`：設定社群動態監聽區與表情/關鍵字數值規則\n"
            "• `/大眾路人大量發生中`：全自動抽選姓名、立繪、數值生成路人\n"
            "• `/路人資源補給`：補充路人相冊與姓名、劇本角色席位、代言庫\n"
            "• `/路人生態設定`：設定路人每 48 小時屬性與金錢浮動規則\n"
            "• `/數值登記`：加減數值、自訂新增數值類型、管理隱藏數值\n"
            "• `/任務新增`：發布各類別任務、成就、榮譽與認知度限制\n"
            "• `/地位等級限制`：設定地位順位與晉級標準門檻\n"
            "• `/發布傳聞`：寫下一句傳聞，自動統計累積滿 3 次貼新標籤"
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
            async with db.execute("SELECT name, nationality, age, gender, job FROM characters WHERE guild_id = ? AND is_npc = 3 ORDER BY created_at DESC", (self.guild_id,)) as cur:
                rows = await cur.fetchall()
        lines = [f"• **{r[0]}** [{r[1]}] ({r[2]}歲 / {r[3]}) ｜ {r[4]}" for r in rows]
        p_view = PagedDetailView("🎭 大眾動態路人清單", lines, 0x1ABC9C, page_size=15)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

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
        embed.add_field(name="全體通用特質 (男女通用無年齡限制)", value="、".join(UNIVERSAL_TAGS), inline=False)
        embed.add_field(name="性別與年齡限定", value="少年感 (男<=25)、老幹部 (>=30)、國民初戀 (女<=24)、國民弟弟 (男<=22)、國民妹妹 (女<=22)、國民兒子 (男<=28)、國民女兒 (女<=28)", inline=False)
        conflict_pairs = [f"{k} ⇄ {', '.join(v)}" for k, v in TAG_CONFLICTS.items()]
        embed.add_field(name="互斥衝突組", value="\n".join(conflict_pairs[:8]), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="檔案總覽", description="調閱全系統分類導航總目錄（指令、官方角、路人、玩家、標籤）")
async def master_overview_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📑 系統檔案與指令整合導航中心", description="請點選下方按鈕切換查閱各項名冊、指引與標籤規則：", color=0x2C3E50)
    await interaction.response.send_message(embed=embed, view=MasterDirectoryView(interaction.guild_id), ephemeral=True)

# -------------------- 指令：/路人轉官方 --------------------
@bot.tree.command(name="路人轉官方", description="【管理員專用】將受歡迎的動態路人直接轉為正式官方 NPC（保留所有數值與外觀）")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(路人名字="欲升格轉正的大眾路人姓名")
async def promote_crowd_to_official(interaction: discord.Interaction, 路人名字: str):
    g_id = interaction.guild_id
    t_name = 路人名字.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_npc, image_url, job, nationality, age, gender FROM characters WHERE guild_id = ? AND name = ?", (g_id, t_name)) as cur:
            row = await cur.fetchone()

        if not row:
            await interaction.response.send_message(f"❌ 查無角色【{t_name}】！", ephemeral=True)
            return

        is_npc_val, img_url, job, nat, age, gen = row
        if is_npc_val == 1:
            await interaction.response.send_message(f"ℹ️ 【{t_name}】已經是官方 NPC 了！", ephemeral=True)
            return

        # 更新 is_npc 為 1 (官方 NPC)，勢力歸入官方
        await db.execute("""
            UPDATE characters 
            SET is_npc = 1, faction = CASE WHEN faction = '無' THEN '官方勢力' ELSE faction END
            WHERE guild_id = ? AND name = ?
        """, (g_id, t_name))
        await db.commit()

    embed = discord.Embed(title=f"👑 動態路人正式升格為官方 NPC：【{t_name}】", color=0x9B59B6)
    embed.description = (
        f"角色 **{t_name}** 已順利轉正，正式開放專屬劇情撰寫與攻略互動！\n"
        f"• 身分/職業：`{job}` ｜ 國籍：`{nat}`\n"
        f"• 年齡/性別：`{age} 歲` / `{gen}`"
    )
    if img_url and img_url.startswith("http"):
        embed.set_thumbnail(url=img_url)

    await interaction.response.send_message(embed=embed)
# -------------------- 指令：/劇本設定 --------------------
@bot.tree.command(name="劇本設定", description="【管理員專用】為官方 NPC 錄入專屬互動劇情劇本與開啟條件")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    npc名稱="對應的官方 NPC 全名",
    劇情名稱="此段故事或事件名稱（例如: 雨夜長廊相遇、秘密試鏡指導）",
    開放條件="解鎖門檻（例如: 偶遇>=3次、好感>=50、容貌>=80 等）",
    劇本訊息連結="貼上包含劇本段落與選擇按鈕文字的 Discord 訊息連結"
)
async def set_story_script(
    interaction: discord.Interaction,
    npc名稱: str,
    劇情名稱: str,
    開放條件: str,
    劇本訊息連結: str
):
    g_id = interaction.guild_id
    n_name = npc名稱.strip()
    s_title = 劇情名稱.strip()
    req_str = 開放條件.strip()
    link_str = 劇本訊息連結.strip()

    await interaction.response.defer(ephemeral=True)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_npc FROM characters WHERE guild_id = ? AND name = ?", (g_id, n_name)) as cur:
            npc_row = await cur.fetchone()
        if not npc_row or npc_row[0] != 1:
            await interaction.followup.send(f"❌ 【{n_name}】不是官方 NPC！若為路人請先使用 `/路人轉官方`。", ephemeral=True)
            return

    # 抓取劇本內容
    script_content = ""
    link_m = re.search(r"channels/\d+/(\d+)/(\d+)", link_str)
    if link_m:
        c_id, m_id = int(link_m.group(1)), int(link_m.group(2))
        try:
            ch = interaction.client.get_channel(c_id) or await interaction.client.fetch_channel(c_id)
            msg = await ch.fetch_message(m_id)
            script_content = msg.content
        except Exception as e:
            await interaction.followup.send(f"❌ 讀取訊息失敗：{e}，請確認機器人有權限查看該頻道！", ephemeral=True)
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

    embed = discord.Embed(title=f"📖 NPC 劇情錄入成功：【{n_name}】", color=0x2ECC71)
    embed.add_field(name="事件章節", value=f"《**{s_title}**》", inline=False)
    embed.add_field(name="開放門檻條件", value=f"`{req_str}`", inline=False)
    embed.set_footer(text="玩家可以在個人檔案或 /劇情觸發 中嘗試開啟與攻略。")
    await interaction.followup.send(embed=embed, ephemeral=True)
# -------------------- 指令：/劇情觸發 --------------------
@bot.tree.command(name="劇情觸發", description="嘗試觸發並攻略特定官方 NPC 的專屬劇情互動")
@app_commands.describe(角色名="你的角色全名", npc名稱="欲進行互動攻略的官方 NPC 姓名")
async def trigger_story_cmd(interaction: discord.Interaction, 角色名: str, npc名稱: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    n_name = npc名稱.strip()

    await interaction.response.defer(ephemeral=False)

    async with aiosqlite.connect(DB_PATH) as db:
        # 抓取角色數值與 NPC 頭像
        async with db.execute("SELECT stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()
        async with db.execute("SELECT image_url, is_npc FROM characters WHERE guild_id = ? AND name = ?", (g_id, n_name)) as cur:
            n_row = await cur.fetchone()

        if not c_row or not n_row:
            await interaction.followup.send("❌ 查無此角色或 NPC！", ephemeral=True)
            return

        char_stats = json.loads(c_row[0]) if c_row[0] else {}
        npc_avatar, is_npc = n_row

        # 抓取該 NPC 尚未完成的劇情
        async with db.execute("""
            SELECT s.story_title, s.unlock_condition, s.script_content,
                   COALESCE(p.completed, 0), COALESCE(p.meet_count, 0)
            FROM story_scripts s
            LEFT JOIN character_story_progress p 
                ON s.guild_id = p.guild_id AND s.npc_name = p.npc_name AND s.story_title = p.story_title AND p.char_name = ?
            WHERE s.guild_id = ? AND s.npc_name = ? AND s.is_active = 1
        """, (c_name, g_id, n_name)) as cur:
            available_stories = await cur.fetchall()

        if not available_stories:
            await interaction.followup.send(f"📋 【{n_name}】目前暫無可觸發的劇情事件。", ephemeral=True)
            return

        # 增加偶遇次數
        await db.execute("""
            INSERT INTO character_story_progress (guild_id, char_name, npc_name, story_title, meet_count)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(guild_id, char_name, npc_name, story_title) DO UPDATE SET meet_count = meet_count + 1
        """, (g_id, c_name, n_name, available_stories[0][0]))
        await db.commit()

        # 檢驗解鎖門檻
        target_story = None
        for s_title, cond, script_raw, completed, meet_cnt in available_stories:
            if completed == 1:
                continue

            # 檢驗條件（例如：偶遇>=3、容貌>=80）
            cond_pass = True
            for part in re.split(r"[,，\s]+", cond):
                m = re.search(r"([^\d<>!=]+)([<>!=]+)(\d+)", part)
                if m:
                    k, op, val = m.group(1).strip(), m.group(2), int(m.group(3))
                    cur_val = (meet_cnt + 1) if "偶遇" in k or "次數" in k else char_stats.get(k, 0)
                    if op == ">=" and cur_val < val: cond_pass = False
                    elif op == ">" and cur_val <= val: cond_pass = False
                    elif op == "<=" and cur_val > val: cond_pass = False
            
            if cond_pass:
                target_story = (s_title, script_raw)
                break

    if not target_story:
        await interaction.followup.send(f"🔒 與【{n_name}】打了個照面（偶遇次數累計中），但目前各項條件或數值尚未達到開啟劇情的門檻！")
        return

    story_title, raw_script = target_story
    blocks = parse_story_script_blocks(raw_script)

    if not blocks:
        await interaction.followup.send("⚠️ 劇本解析格式有誤，請通知管理員檢查劇本訊息！", ephemeral=True)
        return

    # 開始播放第一個段落
    first_block = blocks[0]
    view = None
    if first_block.get("choices"):
        view = StoryBranchView(g_id, c_name, n_name, story_title, first_block["choices"], npc_avatar)

    await interaction.followup.send(f"🎬 **【劇情觸發】《{story_title}》**")
    await send_npc_webhook_message(
        interaction.channel,
        first_block.get("speaker") or n_name,
        npc_avatar,
        first_block["text"],
        view=view
    )
# -------------------- 指令：/社群頻道設定 --------------------
@bot.tree.command(name="社群頻道設定", description="【管理員專用】設定或取消特定頻道為「社群平台動態監聽區」")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="新增監聽頻道", value="add"),
    app_commands.Choice(name="移除監聽頻道", value="remove")
])
@app_commands.describe(頻道="指定文字頻道或論壇", 平台名稱="自訂平台名稱（如: 微博動態、推特專區、匿名論壇）")
async def setup_social_channel(interaction: discord.Interaction, 操作: app_commands.Choice[str], 頻道: discord.TextChannel, 平台名稱: str = "微博動態"):
    g_id = interaction.guild_id
    c_id = 頻道.id

    async with aiosqlite.connect(DB_PATH) as db:
        if 操作.value == "add":
            await db.execute("""
                INSERT INTO social_monitor_channels (guild_id, channel_id, platform_name)
                VALUES (?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET platform_name = excluded.platform_name
            """, (g_id, c_id, 平台名稱.strip()))
            msg = f"✅ 已成功將 {頻道.mention} 設定為【**{平台名稱.strip()}**】社群監聽頻道！"
        else:
            await db.execute("DELETE FROM social_monitor_channels WHERE guild_id = ? AND channel_id = ?", (g_id, c_id))
            msg = f"🗑️ 已解除 {頻道.mention} 的社群監聽功能。"
        await db.commit()

    await interaction.response.send_message(msg, ephemeral=True)

# -------------------- 指令：/社群規則管理 --------------------
@bot.tree.command(name="社群規則管理", description="【管理員專用】自訂社群頻道表情/關鍵字對應數值增減")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(類型=[
    app_commands.Choice(name="表情符號 (Reaction)", value="reaction"),
    app_commands.Choice(name="文字關鍵字 (Keyword)", value="keyword")
])
@app_commands.choices(增減對象=[
    app_commands.Choice(name="發帖者 (Author)", value="author"),
    app_commands.Choice(name="留言/互動者 (Actor)", value="actor")
])
@app_commands.describe(
    符號或詞彙="填表情（如 👍, ❤️, 💩）或詞彙（如 塌房, 盛世美顏）",
    數值變更="格式例如: 死忠粉絲數+5 路人緣+1 或 活躍黑粉數+10"
)
async def manage_social_rules(
    interaction: discord.Interaction,
    類型: app_commands.Choice[str],
    增減對象: app_commands.Choice[str],
    符號或詞彙: str,
    數值變更: str
):
    g_id = interaction.guild_id
    trigger_k = 符號或詞彙.strip()
    stat_c = 數值變更.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO social_reaction_rules (guild_id, trigger_type, trigger_key, target_type, stat_changes)
            VALUES (?, ?, ?, ?, ?)
        """, (g_id, 類型.value, trigger_k, 增減對象.value, stat_c))
        await db.commit()

    await interaction.response.send_message(
        f"✅ 成功新增社群規則！\n"
        f"• 觸發媒介：【{類型.name}】`{trigger_k}`\n"
        f"• 影響目標：【{增減對象.name}】\n"
        f"• 數值結算：`{stat_c}`",
        ephemeral=True
    )

# -------------------- 指令：/時間流動設定 --------------------
@bot.tree.command(name="時間流動設定", description="【管理員專用】調整遊戲內時間流速（影響角色長大週期與寵物壽命換算）")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(遊戲一年對應現實天數="現實過幾天等於遊戲過一年？預設為 30 天（填純整數，例如: 30、15、7）")
async def set_time_flow(interaction: discord.Interaction, 遊戲一年對應現實天數: int):
    g_id = interaction.guild_id
    if 遊戲一年對應現實天數 <= 0:
        await interaction.response.send_message("❌ 現實天數必須大於 0！", ephemeral=True)
        return

    days = 遊戲一年對應現實天數
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'days_per_game_year', ?)
            ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
        """, (g_id, str(days), str(days)))
        await db.commit()

    embed = discord.Embed(title="⏳ 時間齒輪已調整", color=0x9B59B6)
    embed.description = (
        f"全城時間流速已更新完畢！\n\n"
        f"• **當前流速標準**：現實 **{days} 天** ＝ 遊戲內 **1 年**\n"
        f"• **角色成長影響**：所有角色與 NPC 每隔 **{days} 天** 自然增長 1 歲\n"
        f"• **寵物壽命連動**：預期壽命將以每 1 歲折合 **{days} 天** 現實天數動態判定\n"
    )
    await interaction.response.send_message(embed=embed)
# -------------------- 指令：/社交關注 與 /社交拉黑 --------------------
@bot.tree.command(name="社交關注", description="在社群網絡上關注目標人物（對方增加 50 死忠粉，自身有概率獲利）")
@app_commands.describe(你的角色名="操作發起者角色", 目標角色名="欲關注的公眾人物或對象")
async def social_follow_cmd(interaction: discord.Interaction, 你的角色名: str, 目標角色名: str):
    g_id = interaction.guild_id
    m_name = 你的角色名.strip()
    t_name = 目標角色名.strip()

    if m_name == t_name:
        await interaction.response.send_message("❌ 你無法關注自己！", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, m_name)) as cur:
            m_row = await cur.fetchone()
        async with db.execute("SELECT stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, t_name)) as cur:
            t_row = await cur.fetchone()

        if not m_row or not t_row:
            await interaction.response.send_message("❌ 查無發起角色或目標對象！", ephemeral=True)
            return

        m_stats = json.loads(m_row[0]) if m_row[0] else {}
        t_stats = json.loads(t_row[0]) if t_row[0] else {}

        # 登記關注關係
        await db.execute("""
            INSERT INTO social_relations (guild_id, from_char, to_char, relation_type, created_at)
            VALUES (?, ?, ?, 'follow', ?)
            ON CONFLICT(guild_id, from_char, to_char) DO UPDATE SET relation_type = 'follow'
        """, (g_id, m_name, t_name, time.time()))

        # 目標增加 50 死忠粉
        t_stats["死忠粉絲數"] = t_stats.get("死忠粉絲數", 0) + 50

        # 自己本身 30% 機率吸粉（獲得同好關注）
        self_msg = ""
        if random.random() <= 0.30:
            gain_fans = random.randint(10, 30)
            m_stats["死忠粉絲數"] = m_stats.get("死忠粉絲數", 0) + gain_fans
            self_msg = f"\n✨ **【粉絲共鳴】** 你的公開關注引來同擔好感，自身死忠粉 **+{gain_fans}** 人！"

        await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(m_stats, ensure_ascii=False), g_id, m_name))
        await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(t_stats, ensure_ascii=False), g_id, t_name))
        await db.commit()

    embed = discord.Embed(title="📲 社群動態：特別關注已送達", color=0x3498DB)
    embed.description = (
        f"**{m_name}** 在社群網絡上關注了 **{t_name}**！\n"
        f"• **{t_name}** 粉絲效應擴散：死忠粉絲數 **+50** 人！{self_msg}"
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="社交拉黑", description="在社群網絡上公開取關並拉黑對象（對方增加 50 黑粉，自身有反噬風險）")
@app_commands.describe(你的角色名="操作發起者角色", 目標角色名="欲拉黑的對象")
async def social_block_cmd(interaction: discord.Interaction, 你的角色名: str, 目標角色名: str):
    g_id = interaction.guild_id
    m_name = 你的角色名.strip()
    t_name = 目標角色名.strip()

    if m_name == t_name:
        await interaction.response.send_message("❌ 你無法拉黑自己！", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, m_name)) as cur:
            m_row = await cur.fetchone()
        async with db.execute("SELECT stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, t_name)) as cur:
            t_row = await cur.fetchone()

        if not m_row or not t_row:
            await interaction.response.send_message("❌ 查無發起角色或目標對象！", ephemeral=True)
            return

        m_stats = json.loads(m_row[0]) if m_row[0] else {}
        t_stats = json.loads(t_row[0]) if t_row[0] else {}

        # 登記拉黑關係
        await db.execute("""
            INSERT INTO social_relations (guild_id, from_char, to_char, relation_type, created_at)
            VALUES (?, ?, ?, 'block', ?)
            ON CONFLICT(guild_id, from_char, to_char) DO UPDATE SET relation_type = 'block'
        """, (g_id, m_name, t_name, time.time()))

        # 目標增加 50 黑粉
        t_stats["活躍黑粉數"] = t_stats.get("活躍黑粉數", 0) + 50

        # 自己本身 25% 機率遭到對方粉圈攻擊（反噬增加黑粉）
        backfire_msg = ""
        if random.random() <= 0.25:
            gain_haters = random.randint(15, 40)
            m_stats["活躍黑粉數"] = m_stats.get("活躍黑粉數", 0) + gain_haters
            backfire_msg = f"\n⚠️ **【粉圈開撕反噬】** 你的公開拉黑引發對方唯粉不滿，自身活躍黑粉 **+{gain_haters}** 人！"

        await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(m_stats, ensure_ascii=False), g_id, m_name))
        await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(t_stats, ensure_ascii=False), g_id, t_name))
        await db.commit()

    embed = discord.Embed(title="🚫 社群動態：拉黑與取關公示", color=0xE74C3C)
    embed.description = (
        f"**{m_name}** 在社群網絡上對 **{t_name}** 執行了公開拉黑！\n"
        f"• **{t_name}** 爭議輿論升級：活躍黑粉數 **+50** 人！{backfire_msg}"
    )
    await interaction.response.send_message(embed=embed)

# -------------------- 清理與強制同步指令 --------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def clean_guild(ctx):
    bot.tree.clear_commands(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send("🧹 伺服器專屬副本指令已清空，僅保留全域 Slash 指令。")

@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    msg = await ctx.send("⏳ 正在強制同步所有指令至本伺服器...")
    try:
        bot.tree.copy_global_to(guild=ctx.guild)
        synced = await bot.tree.sync(guild=ctx.guild)
        await msg.edit(content=f"✅ 強制同步完成！已載入 **{len(synced)}** 個指令。")
    except Exception as e:
        await msg.edit(content=f"❌ 同步失敗: `{e}`")

# -------------------- 啟動與全域同步 --------------------
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
