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
                # 已通關：字體縮小且呈灰色弱化顯示
                embed.add_field(
                    name=f"-# ✔️ 《{title}》（已通關圓滿）",
                    value=f"-# • 門檻要求：`{cond}`",
                    inline=False
                )
            else:
                # 未完成：醒目發光高亮展示
                embed.add_field(
                    name=f"🌟 **《{title}》**【可攻略/未解鎖】",
                    value=f"• 解鎖門檻：`{cond}`\n• 觸發指令：`/劇情觸發 角色名:你的名字 npc名稱:{self.char_name}`",
                    inline=False
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)
# -------------------- 通用角色卡片渲染函式（動態分頁與世界觀名詞替換） --------------------
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

    # 讀取世界觀自定義名詞
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

    # ==================== 第 1 頁：基本資訊與資產 ====================
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

    # ==================== 第 2 頁：能力數值面板 ====================
    embed2 = discord.Embed(
        title=f"📊 {tag_prefix}【{target_name}】{stage_str} {terms.get('page2_title', '能力面板')} (2/2)",
        color=final_color
    )
    stats = json.loads(stats_json) if stats_json else {}

    # 1. 第一組數值（預設：商業名氣 / 威望功名）
    group1_name = terms.get("section_stat_group1", "商業名氣")
    lines_group1 = [
        f"• 流量熱度：**{stats.get('流量熱度', 0):,}**",
        f"• 商業價值：**{stats.get('商業價值', 0):,}**",
        f"• 影響指數：**{stats.get('影響指數', 0):,}**",
        f"• 路人緣：**{stats.get('路人緣', 0):,}**",
        f"• 公關：**{stats.get('公關', 0):,}**"
    ]
    embed2.add_field(name=f"📈 {group1_name}", value="\n".join(lines_group1), inline=False)

    # 2. 第二組數值（預設：藝能實力 / 武學修為）
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

    # 3. 社群/人脈動態
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
# -------------------- ProfileUpdateStepView（鎖定數值與身材，純個資修改） --------------------
class ProfileUpdateStepView(discord.ui.View):
    def __init__(self, char_name: str, guild_id: int, is_admin: bool):
        super().__init__(timeout=180)
        self.char_name = char_name
        self.guild_id = guild_id
        self.is_admin = is_admin

    @discord.ui.button(label="📝 個資資料變更", style=discord.ButtonStyle.primary, row=0)
    async def update_base(self, interaction: discord.Interaction, button: discord.ui.Button):
        parent_view = self

        class FieldSelect(discord.ui.Select):
            def __init__(self):
                opts = [
                    discord.SelectOption(label="資歷時長", value="debut_years", description="修改入行/修行年資 (純數字，0 代表無資歷新人)", emoji="🌟"),
                    discord.SelectOption(label="稱號 / 藝名 / 道號", value="stage_name", description="修改對外名號或藝名", emoji="🏷️"),
                    discord.SelectOption(label="職業 / 身分", value="job", description="修改當前職業或門派身分", emoji="💼"),
                    discord.SelectOption(label="感情狀況", value="relationship_status", description="修改感情狀態 (例如: 單身、隱婚、道侶在側)", emoji="💌"),
                    discord.SelectOption(label="CP / 道侶伴侶", value="cp_info", description="格式: 角色名/關係 (例如: 某某/道侶)", emoji="💕"),
                    discord.SelectOption(label="專屬代表色", value="theme_color", description="設定個人卡片 16 進位色碼 (如 #FF69B4)", emoji="🎨"),
                    discord.SelectOption(label="特質標籤", value="tags", description="修改外號與標籤 (以頓號或空格隔開，最多 2 個)", emoji="🔖")
                ]
                super().__init__(placeholder="請選擇欲修改的項目（身高/體重/數值需透過動作或道具變更）...", options=opts)

            async def callback(self, s_inter: discord.Interaction):
                chosen_field = self.values[0]

                class ValueModal(discord.ui.Modal):
                    def __init__(self, target_field: str, field_label: str):
                        super().__init__(title=f"修改【{parent_view.char_name}】{field_label}")
                        self.target_field = target_field
                        self.field_label = field_label

                        hint_map = {
                            "debut_years": "請填寫年數（例如 5 代表資歷 5 年，填 0 代表無資歷新人）",
                            "stage_name": "請填寫新的對外稱號、道號或藝名",
                            "job": "請填寫新的身分或職業名稱",
                            "relationship_status": "例如: 單身、熱戀中、隱婚傳聞、求道無心",
                            "cp_info": "格式: 名字/關係（例如: 顧清/道侶）",
                            "theme_color": "請填寫 16 進位色碼（例如 #FF69B4）",
                            "tags": "例如: 神顏、實力派（最多兩個）"
                        }

                        self.val_input = discord.ui.TextInput(
                            label=f"請輸入新的【{field_label}】內容",
                            placeholder=hint_map.get(target_field, "請輸入新內容"),
                            min_length=1,
                            max_length=60
                        )
                        self.add_item(self.val_input)

                    async def on_submit(self, m_inter: discord.Interaction):
                        new_text = self.val_input.value.strip()

                        async with aiosqlite.connect(DB_PATH) as db:
                            if self.target_field == "debut_years":
                                match_num = re.search(r"\d+", new_text)
                                if not match_num:
                                    await m_inter.response.send_message("❌ 資歷請輸入純數字年份！（例如 0、5、10）", ephemeral=True)
                                    return
                                y_val = int(match_num.group())

                                async with db.execute("SELECT age FROM characters WHERE guild_id = ? AND name = ?", (parent_view.guild_id, parent_view.char_name)) as cur:
                                    c_row = await cur.fetchone()
                                    cur_age = c_row[0] if (c_row and c_row[0]) else 20

                                d_age = max(1, cur_age - y_val) if y_val > 0 else cur_age
                                await db.execute("""
                                    UPDATE characters 
                                    SET debut_years = ?, debut_age = ? 
                                    WHERE guild_id = ? AND name = ?
                                """, (y_val, d_age, parent_view.guild_id, parent_view.char_name))
                                await db.commit()

                                title_text = await get_debut_title_async(parent_view.guild_id, y_val, d_age)
                                await m_inter.response.send_message(f"✅ 【{parent_view.char_name}】的資歷已更新為 **{y_val} 年**！\n🌟 當前稱謂：**{title_text}**", ephemeral=True)
                                return

                            elif self.target_field == "stage_name":
                                await db.execute("UPDATE characters SET stage_name = ? WHERE guild_id = ? AND name = ?", (new_text, parent_view.guild_id, parent_view.char_name))
                            elif self.target_field == "job":
                                await db.execute("UPDATE characters SET job = ? WHERE guild_id = ? AND name = ?", (new_text, parent_view.guild_id, parent_view.char_name))
                            elif self.target_field == "relationship_status":
                                await db.execute("UPDATE characters SET relationship_status = ? WHERE guild_id = ? AND name = ?", (new_text, parent_view.guild_id, parent_view.char_name))
                            elif self.target_field == "theme_color":
                                await db.execute("UPDATE characters SET theme_color = ? WHERE guild_id = ? AND name = ?", (new_text, parent_view.guild_id, parent_view.char_name))
                            elif self.target_field == "tags":
                                await db.execute("UPDATE characters SET tags = ? WHERE guild_id = ? AND name = ?", (new_text, parent_view.guild_id, parent_view.char_name))
                            elif self.target_field == "cp_info":
                                parts = re.split(r"[/,，\s]+", new_text)
                                cp_obj = {"target": parts[0], "relation": parts[1] if len(parts) > 1 else "伴侶", "affection": 100}
                                await db.execute("UPDATE characters SET cp_info = ? WHERE guild_id = ? AND name = ?", (json.dumps(cp_obj, ensure_ascii=False), parent_view.guild_id, parent_view.char_name))

                            await db.commit()

                        await m_inter.response.send_message(f"✅ 成功將【{parent_view.char_name}】的 **{self.field_label}** 更新為：`{new_text}`！", ephemeral=True)

                label_lookup = {
                    "debut_years": "資歷時長",
                    "stage_name": "稱號/藝名",
                    "job": "職業身分",
                    "relationship_status": "感情狀況",
                    "cp_info": "CP道侶",
                    "theme_color": "專屬代表色",
                    "tags": "特質標籤"
                }
                await s_inter.response.send_modal(ValueModal(chosen_field, label_lookup.get(chosen_field, "資料")))

        select_view = discord.ui.View(timeout=180)
        select_view.add_item(FieldSelect())
        await interaction.response.send_message(f"📋 請選擇欲為【{self.char_name}】修改的個資項目：", view=select_view, ephemeral=True)

    @discord.ui.button(label="🏆 歷練成就登記", style=discord.ButtonStyle.success, row=0)
    async def update_achievement(self, interaction: discord.Interaction, button: discord.ui.Button):
        class AchieveModal(discord.ui.Modal, title=f"登記【{self.char_name}】歷練成就"):
            category = discord.ui.TextInput(label="分類 (影視/重大事件/秘境/戰役等)", placeholder="例如: 電影 或 宗門大比")
            title = discord.ui.TextInput(label="作品/事件名稱", placeholder="例如: 楚門的世界 或 萬劍破陣")
            role_type = discord.ui.TextInput(label="參與身分/備註", placeholder="例如: 主演、魁首、主力")

            async def on_submit(m_self, inter: discord.Interaction):
                entry = {
                    "category": "成就",
                    "type": m_self.category.value.strip(),
                    "title": m_self.title.value.strip(),
                    "extra": m_self.role_type.value.strip()
                }
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT works FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                        row = await cur.fetchone()
                        works = json.loads(row[0]) if (row and row[0]) else []
                    works.append(entry)
                    await db.execute("UPDATE characters SET works = ? WHERE guild_id = ? AND name = ?", (json.dumps(works, ensure_ascii=False), self.guild_id, self.char_name))
                    await db.commit()

                await check_and_update_rank(self.guild_id, self.char_name, inter.channel)
                await inter.response.send_message(f"✅ 成功為 **{self.char_name}** 登記歷練：【{entry['type']}】《{entry['title']}》（{entry['extra']}）！", ephemeral=True)

        await interaction.response.send_modal(AchieveModal())

    @discord.ui.button(label="🎖️ 榮譽頭銜登記", style=discord.ButtonStyle.secondary, row=1)
    async def update_honor(self, interaction: discord.Interaction, button: discord.ui.Button):
        class HonorModal(discord.ui.Modal, title=f"登記【{self.char_name}】榮譽頭銜"):
            name = discord.ui.TextInput(label="榮譽名稱 / 代言品牌 / 功勳", placeholder="例如: 香奈兒代言 或 護國封邑")
            level = discord.ui.TextInput(label="品級 / 級別", placeholder="例如: 頂級、奢華、特等")
            title_name = discord.ui.TextInput(label="授予頭銜", placeholder="例如: 品牌大使 / 名譽長老")

            async def on_submit(m_self, inter: discord.Interaction):
                entry = {
                    "category": "榮譽",
                    "title": m_self.name.value.strip(),
                    "extra": f"{m_self.level.value.strip()} ｜ {m_self.title_name.value.strip()}"
                }
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT works FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                        row = await cur.fetchone()
                        works = json.loads(row[0]) if (row and row[0]) else []
                    works.append(entry)
                    await db.execute("UPDATE characters SET works = ? WHERE guild_id = ? AND name = ?", (json.dumps(works, ensure_ascii=False), self.guild_id, self.char_name))
                    await db.commit()

                await check_and_update_rank(self.guild_id, self.char_name, inter.channel)
                await inter.response.send_message(f"✅ 成功為 **{self.char_name}** 登記榮譽：【{entry['title']}】（{entry['extra']}）！", ephemeral=True)

        await interaction.response.send_modal(HonorModal())

    @discord.ui.button(label="💬 交際傾向調整", style=discord.ButtonStyle.danger, row=1)
    async def update_relationship(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'tendency_list'", (self.guild_id,)) as cur:
                row = await cur.fetchone()
                tendencies = json.loads(row[0]) if row and row[0] else ["傾心", "好奇", "觀察", "痴迷", "友好", "敵對", "利用"]

        class RelationModal(discord.ui.Modal, title=f"變更【{self.char_name}】交際傾向"):
            target = discord.ui.TextInput(label="目標對象全名", placeholder="輸入對方全名")
            tendency = discord.ui.TextInput(label=f"交際傾向 ({'/'.join(tendencies[:6])})", placeholder="輸入傾向詞彙")
            status = discord.ui.TextInput(label="狀況敘述 (可選)", placeholder="例如: 暗中照拂、誓不兩立", required=False)

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
# -------------------- 定時預約廣播與全自動發獎排程 --------------------
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

                # 1. 金錢發放
                if r_cash > 0:
                    await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (r_cash, g_id, c_name))

                # 2. 道具發放
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

                # 3. 屬性加成
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

# -------------------- 資料庫 Schema 擴充 --------------------
async def extend_database_tables():
    async with aiosqlite.connect(DB_PATH) as db:
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
# -------------------- 指令：/使用（支援道具吃喝動態增減身高與體重） --------------------
@bot.tree.command(name="使用", description="使用背包中的道具（支援飲食身材增減、屬性提升、門票簽證或餵食寵物）")
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

        # 1. 身高與體重動態增減
        body_change_msg = ""
        combined_text = f"{stat_bonus} {desc_text}"
        h_change, w_change = 0, 0

        h_match = re.search(r"身高([+-]?\d+)", combined_text)
        if h_match:
            h_change = int(h_match.group(1)) * use_cnt

        w_match = re.search(r"體重([+-]?\d+)", combined_text)
        if w_match:
            w_change = int(w_match.group(1)) * use_cnt

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
            if warn_text:
                body_change_msg += f"\n{warn_text}"

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

        # 3. 屬性數值加成
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
# -------------------- 指令：/世界觀自訂（支援多詞彙空白隔開，不限數量） --------------------
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
# -------------------- 指令：/違規懲戒（含數值扣除、撕卡與全服遺產瓜分拍賣） --------------------
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
        # 1. 檢驗目標角色
        async with db.execute("SELECT cash, bank, stats, theme_color FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()

        if not c_row:
            await interaction.followup.send(f"❌ 查無受懲處角色【{c_name}】！請確認角色全名。", ephemeral=True)
            return

        cash, bank, stats_json, t_color = c_row
        stats = json.loads(stats_json) if stats_json else {}

        # 2. 登記警告檔案
        await db.execute("""
            INSERT INTO character_warnings (
                guild_id, user_id, char_name, rule_clause, reason, evidence_link, admin_name, warned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (g_id, u_id, c_name, clause, reason_text, evidence_url, interaction.user.display_name, time.time()))

        async with db.execute("SELECT COUNT(*) FROM character_warnings WHERE guild_id = ? AND user_id = ?", (g_id, u_id)) as cur:
            warn_count = (await cur.fetchone())[0]

        punishment_details = []
        is_ban_and_rip = (action == "kick_ban") or (warn_count >= 3)

        # ==================== 第 1、2 次警告：數值百分比扣除 ====================
        if not is_ban_and_rip:
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

        # ==================== 第 3 次警告／直接封殺：全服瓜分與拍賣 ====================
        else:
            # 1. 統計玩家角色 (is_npc=0) 與 官方NPC (is_npc=1)
            async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND is_npc IN (0, 1) AND name != ?", (g_id, c_name)) as ben_cur:
                beneficiaries = [r[0] for r in await ben_cur.fetchall()]

            total_beneficiaries = len(beneficiaries)
            total_legacy_pool_money = cash + bank

            # 2. 背包物品折算與拍賣流轉
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
                    # 無法折算 ➔ 正式寫入全服拍賣行，起標 $1,000，每次最低加價 $200，拍賣期 48 小時
                    auc_end_time = time.time() + (48 * 3600)
                    await db.execute("""
                        INSERT INTO auction_house (
                            guild_id, item_name, amount, seller_name,
                            current_bid, min_increment, created_at, end_time, is_closed
                        ) VALUES (?, ?, ?, '違規撕卡清算', 1000, 200, ?, ?, 0)
                    """, (g_id, it_name, it_amt, time.time(), auc_end_time))
                    auction_items.append(f"• **{it_name}** ×{it_amt} (起拍價 $1,000，結標倒數 48 小時)")


            total_legacy_pool_money += liquidated_items_money

            # 3. 全服遺產金錢均分
            share_money_per_char = 0
            if total_beneficiaries > 0 and total_legacy_pool_money > 0:
                share_money_per_char = max(1, total_legacy_pool_money // total_beneficiaries)
                await db.execute("""
                    UPDATE characters SET bank = bank + ? 
                    WHERE guild_id = ? AND is_npc IN (0, 1) AND name != ?
                """, (share_money_per_char, g_id, c_name))

            # 4. 全服屬性瓜分（不足均分系統保底給予 1 點）
            stat_distributions = []
            if total_beneficiaries > 0 and stats:
                for k, v in stats.items():
                    if isinstance(v, (int, float)) and v > 0:
                        per_stat = max(1, v // total_beneficiaries)  # 不足均分則系統自動補足保底發放 1 點
                        for b_name in beneficiaries:
                            async with db.execute("SELECT stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, b_name)) as b_cur:
                                b_row = await b_cur.fetchone()
                                b_st = json.loads(b_row[0]) if (b_row and b_row[0]) else {}
                                b_st[k] = b_st.get(k, 0) + per_stat
                                await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(b_st, ensure_ascii=False), g_id, b_name))
                        stat_distributions.append(f"{k} +{per_stat}")

            # 5. 撕卡銷毀：徹底刪除背包、資產與該角色檔案
            await db.execute("DELETE FROM inventory WHERE guild_id = ? AND owner_name = ?", (g_id, c_name))
            await db.execute("DELETE FROM personal_assets WHERE guild_id = ? AND owner_name = ?", (g_id, c_name))
            await db.execute("DELETE FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name))
            await db.commit()

            # 6. 強制驅逐成員
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

    # ==================== 構建官方通報 Embed ====================
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

    # 私訊違規者
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

    # 廣播發布
    await broadcast_event(interaction.guild, "penalty", public_embed)
    await interaction.followup.send(embed=public_embed)
# -------------------- 拍賣行資料庫 Schema 擴充 --------------------
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

# -------------------- 拍賣行結標自動發放排程 --------------------
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
                # 物品正式送入得標者背包
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
# -------------------- 指令：/拍賣行 --------------------
@bot.tree.command(name="拍賣行", description="查閱全服拍賣會拍品清單（包含撕卡遺產特殊物品、當前最高出價者）")
async def auction_list_cmd(interaction: discord.Interaction):
    g_id = interaction.guild_id
    now_ts = time.time()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id, item_name, amount, current_bid, highest_bidder_char, min_increment, end_time
            FROM auction_house
            WHERE guild_id = ? AND is_closed = 0 AND end_time > ?
            ORDER BY end_time ASC
        """, (g_id, now_ts)) as cur:
            items = await cur.fetchall()

    if not items:
        await interaction.response.send_message("🏛️ 目前拍賣行暫無拍品展示。有違規撕卡或官方特別流轉時將自動在此開啟！", ephemeral=True)
        return

    embed = discord.Embed(title="🏛️ 全城拍賣行・專屬競標會場", color=0xD4AF37)
    embed.description = "每項競拍每次加價最低 **+$200**，出價自動暫扣款項，若被他人超車將原路秒退！\n"

    for a_id, it_name, it_amt, cur_bid, bidder, inc, end_t in items[:15]:
        remain_min = max(1, int((end_t - now_ts) // 60))
        bidder_str = f"**{bidder}**" if bidder else "尚無出價"
        embed.add_field(
            name=f"📦 [ID: {a_id}] {it_name} ×{it_amt}",
            value=(
                f"• 當前價格：**${cur_bid:,}**\n"
                f"• 最高出價人：{bidder_str}\n"
                f"• 結標倒數：約 `{remain_min}` 分鐘\n"
                f"• 下次最低出價：**${cur_bid + inc:,}**"
            ),
            inline=False
        )
    embed.set_footer(text="競拍指令：/拍賣競標 拍品id:編號 角色名:你的角色 出價金額:數字")
    await interaction.response.send_message(embed=embed)


# -------------------- 指令：/拍賣競標 --------------------
@bot.tree.command(name="拍賣競標", description="在拍賣行對指定拍品出價（每次最低加價 $200，被超車全額自動退款）")
@app_commands.describe(
    拍品id="拍賣行列表中的 [ID: 編號]",
    角色名="發起競拍的自己角色",
    出價金額="欲出的拍賣金幣 (必須大於當前最高價 + $200)"
)
async def bid_auction_cmd(interaction: discord.Interaction, 拍品id: int, 角色名: str, 出價金額: int):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    bid_amt = 出價金額

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. 檢驗角色
        async with db.execute("SELECT user_id, cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            char_row = await cur.fetchone()

        if not char_row:
            await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
            return

        u_id, cash, bank = char_row
        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 你只能為自己的角色發起競拍！", ephemeral=True)
            return

        if cash + bank < bid_amt:
            await interaction.response.send_message(f"❌ 資金不足！你目前的現金與銀行總額為 **${cash + bank:,}**，不足以出價 **${bid_amt:,}**！", ephemeral=True)
            return

        # 2. 檢驗拍賣品
        async with db.execute("""
            SELECT item_name, current_bid, highest_bidder_char, highest_bidder_uid, min_increment, end_time, is_closed
            FROM auction_house WHERE id = ? AND guild_id = ?
        """, (拍品id, g_id)) as cur:
            auc = await cur.fetchone()

        if not auc or auc[6] == 1 or auc[5] <= time.time():
            await interaction.response.send_message("❌ 該拍品不存在或已結標關閉！", ephemeral=True)
            return

        it_name, cur_bid, prev_bidder_char, prev_bidder_uid, min_inc, end_t, _ = auc

        min_req_bid = cur_bid + min_inc
        if bid_amt < min_req_bid:
            await interaction.response.send_message(
                f"❌ 出價過低！目前最高價為 **${cur_bid:,}**，每次加價至少 **+${min_inc:,}**（最低出價需為 **${min_req_bid:,}**）！",
                ephemeral=True
            )
            return

        # 3. 前一位最高出價者秒退款
        if prev_bidder_char and prev_bidder_uid > 0:
            await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (cur_bid, g_id, prev_bidder_char))

        # 4. 扣減當前出價者款項
        if cash >= bid_amt:
            await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (bid_amt, g_id, c_name))
        else:
            rem = bid_amt - cash
            await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (rem, g_id, c_name))

        # 5. 更新拍賣狀態
        await db.execute("""
            UPDATE auction_house
            SET current_bid = ?, highest_bidder_char = ?, highest_bidder_uid = ?
            WHERE id = ?
        """, (bid_amt, c_name, interaction.user.id, 拍品id))
        await db.commit()

    refund_str = f"（前最高出價人 **{prev_bidder_char}** 的 ${cur_bid:,} 已原額退還銀行）" if prev_bidder_char else ""
    await interaction.response.send_message(
        f"🔨 **【出價成功】** **{c_name}** 成功以 **${bid_amt:,}** 領先【{it_name}】的競標！{refund_str}"
    )
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

            # 扣除款項
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

            # 注入公司或賣家帳戶
            if seller_name != "官方":
                async with db.execute("SELECT id FROM companies WHERE guild_id = ? AND name = ?", (self.guild_id, seller_name)) as comp_cur:
                    comp_match = await comp_cur.fetchone()
                if comp_match:
                    await db.execute("UPDATE companies SET balance = balance + ? WHERE id = ?", (total_cost, comp_match[0]))
                else:
                    await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (total_cost, self.guild_id, seller_name))

            # 行動點特殊充值 vs 一般入背包
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
# -------------------- 指令：/商城 --------------------
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
                # ==================== 官方商城：直接放置行動點快捷按鈕 ====================
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
                            f"• 用途：用於 `/動作` 進行排練（1~15數值）、私教訓練、打工兼職或應酬\n"
                            f"• 每年清算：現實每月（遊戲每年）重置一次，不跨年保留\n\n"
                            f"👇 請點擊下方綠色按鈕填入欲購買數量："
                        ),
                        color=0x2ECC71
                    )
                    await inter.response.send_message(embed=embed, view=OfficialView(), ephemeral=True)
                    return

                # ==================== 其他常規專區 ====================
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
# -------------------- 指令：/動作設定 --------------------
@bot.tree.command(name="動作設定", description="【管理員專用】設定地點動作（消耗AP/金錢、排練1~15數值、人脈1~5好感、身材增減）")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="新增/覆蓋動作日程", value="save"),
    app_commands.Choice(name="刪除既有動作", value="delete")
])
@app_commands.describe(
    操作="選擇新增或刪除動作",
    分類="地點分類名稱（例如: 練習室、健身中心、綜合醫院、深夜酒館、修煉密室）",
    動作名稱="具體動作行為（例如: 名師私教、兼職打工、閉關排練、喝酒應酬）",
    說明描述="點選時看到的說明文字",
    消耗行動點="需消耗的行動點 (預設 1)",
    花費金錢="需扣除的金錢 (填 0 為免費)",
    獲得金錢="打工兼職可賺取的金錢 (填 0 為無酬勞)",
    健康增減="扣除填負數 (如喝酒 -10)，恢復填正數 (如去醫院 +30，休息 +15)",
    固定數值增減="固定屬性變動 (格式如: 容貌+5 才智+10 身高+1 體重-1)",
    排練隨機數值賽道="單純消耗AP排練隨機獲得 1~15 點的屬性名稱，以空格隔開 (例如: 演繹 唱跳 劍道)",
    特殊際遇獎勵="獲得人脈(好感1~5)或道具 (格式: 物品*數量 或 人脈:知名製作人)"
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
    特殊際遇獎勵: str = ""
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
            獲得金錢, 健康增減, 固定數值增減.strip(), 排練隨機數值賽道.strip(), 特殊際遇獎勵.strip()
        ))
        await db.commit()

    embed = discord.Embed(title="📍 日常日程動作設定成功", color=0x2ECC71)
    embed.description = f"**地點分類**：【{cat}】\n**動作名稱**：**{act}**\n• 簡述：`{說明描述.strip()}`"
    embed.add_field(name="消耗與成本", value=f"• 消耗行動點：`{消耗行動點} AP`\n• 消耗金錢：`${花費金錢:,}`", inline=True)
    embed.add_field(name="收益與體能", value=f"• 打工收入：`${獲得金錢:,}`\n• 健康增減：`{健康增減:+}`", inline=True)
    if 固定數值增減.strip():
        embed.add_field(name="固定屬性/身材", value=f"`{固定數值增減.strip()}`", inline=False)
    if 排練隨機數值賽道.strip():
        embed.add_field(name="隨機排練 (1~15點)", value=f"`{排練隨機數值賽道.strip()}`", inline=False)
    if 特殊際遇獎勵.strip():
        embed.add_field(name="特殊際遇/人脈 (好感1~5)", value=f"`{特殊際遇獎勵.strip()}`", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# -------------------- 指令：/發布傳聞 --------------------
@bot.tree.command(name="發布傳聞", description="【管理員專用】針對角色發布坊間傳聞（同關鍵字累積滿 3 次自動貼上新標籤）")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(角色名="目標角色姓名", 傳聞內容="寫下一句傳聞文字")
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

    bonus_msg = f"\n🔥 **【輿論發酵】** 傳聞發酵！【{c_name}】被貼上全新標籤：`{new_tag_added}`！（當前標籤：`{new_tags_str}`）" if tag_changed else ""
    await interaction.response.send_message(f"📢 圈內傳聞已記錄至【{c_name}】檔案中：\n> *「{r_text}」*{bonus_msg}")
# -------------------- 指令：/任務新增 --------------------
@bot.tree.command(name="任務新增", description="【管理員專用】發布全新任務並設定獎勵與時間")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(選擇欄位=[
    app_commands.Choice(name="新手任務", value="新手任務"),
    app_commands.Choice(name="一般任務", value="一般任務"),
    app_commands.Choice(name="限時任務", value="限時任務"),
    app_commands.Choice(name="特殊任務", value="特殊任務")
])
@app_commands.describe(
    選擇欄位="選擇任務分類",
    任務名="任務名稱（玩家回報文章需包含此名稱）",
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


# -------------------- 指令：/回報任務（含未出道新人正式出道機制） --------------------
@bot.tree.command(name="回報任務", description="回報已完成的通告、活動或日常任務，結算酬勞、數值並檢驗出道與晉級")
@app_commands.describe(
    角色名="欲領取通告任務獎勵的角色名稱",
    任務名稱="已接取或完成的任務/通告名稱",
    證明內容="文字結算、對戲討論串連結或工作截圖說明"
)
async def report_mission(
    interaction: discord.Interaction,
    角色名: str,
    任務名稱: str,
    證明內容: str = "已按要求完成演藝通告"
):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    m_name = 任務名稱.strip()
    await interaction.response.defer(ephemeral=False)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT user_id, age, debut_years, debut_age, cash, bank, stats, faction
            FROM characters WHERE guild_id = ? AND name = ?
        """, (g_id, c_name)) as cur:
            char_row = await cur.fetchone()

        if not char_row:
            await interaction.followup.send(f"❌ 查無角色【{c_name}】！", ephemeral=True)
            return

        u_id, cur_age, d_years, d_age, cash, bank, stats_json, faction_name = char_row

        if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ 你只能為自己的角色回報通告任務！", ephemeral=True)
            return

        # 抓取任務設定
        async with db.execute("""
            SELECT id, reward_cash, reward_stats, reward_items
            FROM quests WHERE guild_id = ? AND title = ?
        """, (g_id, m_name)) as q_cur:
            q_row = await q_cur.fetchone()

        if q_row:
            _, rew_money, stat_bonus, item_json = q_row
            items_list = json.loads(item_json) if item_json else []
        else:
            rew_money = 5000
            stat_bonus = "流量熱度+15 影響指數+10"
            items_list = []

        stats = json.loads(stats_json) if stats_json else {}

        # 陣營公款抽稅結算
        tax_deducted = 0
        faction_note = ""
        if faction_name and faction_name not in ["無", "官方勢力"]:
            async with db.execute("SELECT tax_rate FROM factions WHERE guild_id = ? AND name = ?", (g_id, faction_name)) as f_cur:
                f_row = await f_cur.fetchone()
                tax_rate = f_row[0] if (f_row and f_row[0]) else 0.1
                tax_deducted = int(rew_money * tax_rate)
                player_gain_money = rew_money - tax_deducted
                await db.execute("UPDATE factions SET treasury = treasury + ? WHERE guild_id = ? AND name = ?", (tax_deducted, g_id, faction_name))
                faction_note = f"\n🏛️ 所屬【{faction_name}】抽稅 ({int(tax_rate*100)}%): `${tax_deducted:,}`（已納入公款）"
        else:
            player_gain_money = rew_money

        # 屬性成長
        gained_stats_list = []
        if stat_bonus:
            for part in re.split(r"[,，、\s]+", stat_bonus):
                match = re.search(r"([^\d+-]+)([+-]?\d+)", part)
                if match:
                    k, v = match.group(1).strip(), int(match.group(2))
                    stats[k] = max(0, stats.get(k, 0) + v)
                    sign = "+" if v >= 0 else ""
                    gained_stats_list.append(f"{k} {sign}{v}")

        # 道具獎勵
        item_note = ""
        if items_list:
            item_msgs = []
            for it in items_list:
                it_name = it.get("name")
                it_amt = it.get("amount", 1)
                async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, c_name, it_name)) as inv_cur:
                    exists_item = await inv_cur.fetchone()
                    if exists_item:
                        await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (it_amt, exists_item[0]))
                    else:
                        await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, ?, '任務通告報酬')", (g_id, c_name, it_name, it_amt))
                item_msgs.append(f"`{it_name} ×{it_amt}`")
            item_note = f"\n📦 獲得道具報酬：{', '.join(item_msgs)}"

        # 未出道新人／無資歷者「接下任務確立身分／正式出道」
        debut_announcement = ""
        if not d_years or d_years <= 0:
            debut_age_val = cur_age if cur_age else 20
            await db.execute("""
                UPDATE characters
                SET debut_years = 1, debut_age = ?
                WHERE guild_id = ? AND name = ?
            """, (debut_age_val, g_id, c_name))
            debut_announcement = f"\n\n🌟 **【正式出道／確立身分】**\n恭喜 **{c_name}** 順利完成首個任務通告，正式確立身分！初露鋒芒（於 {debut_age_val} 歲入行）！"

        # 登記完成紀錄
        await db.execute("""
            INSERT INTO quest_completions (guild_id, char_name, quest_title, completed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, char_name, quest_title) DO UPDATE SET completed_at = excluded.completed_at
        """, (g_id, c_name, m_name, time.time()))

        await db.execute("""
            UPDATE characters
            SET bank = bank + ?, stats = ?
            WHERE guild_id = ? AND name = ?
        """, (player_gain_money, json.dumps(stats, ensure_ascii=False), g_id, c_name))
        await db.commit()

    await check_and_update_rank(g_id, c_name, interaction.channel)

    embed = discord.Embed(title=f"🎬 任務回報結算：【{c_name}】", color=0x2ECC71)
    embed.description = (
        f"**完成任務**：【{m_name}】\n"
        f"**成果證明**：`{證明內容.strip()}`\n\n"
        f"💰 **酬勞入帳**：**+${player_gain_money:,}** (實領入銀行){faction_note}{item_note}\n"
        f"📈 **能力增長**：{', '.join(gained_stats_list) if gained_stats_list else '經驗累積'}"
        f"{debut_announcement}"
    )
    await interaction.followup.send(embed=embed)
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
    if age_m: data["age"] = max(16, min(60, int(age_m.group(1))))

    sex_m = re.search(r"性別[／/]?性向[：:]\s*([^\n\r]+)", content)
    if sex_m:
        parts = re.split(r"[／/\s]+", sex_m.group(1).strip())
        data["gender"] = parts[0].strip() if parts else "女"
        data["orientation"] = parts[1].strip() if len(parts) > 1 else "保密"

    nat_m = re.search(r"國籍[：:]\s*([^\n\r]+)", content)
    if nat_m: data["nationality"] = re.split(r"[，,\s（(]", nat_m.group(1).strip())[0].strip()

    rel_m = re.search(r"感情[：:]\s*([^\n\r]+)", content)
    if rel_m: data["relationship_status"] = rel_m.group(1).strip()

    hw_m = re.search(r"身高[／/]?體重[：:]\s*([^\n\r]+)", content)
    if hw_m:
        nums = re.findall(r"\d+", hw_m.group(1))
        if len(nums) >= 2:
            data["height"] = int(nums[0])
            data["weight"] = int(nums[1])

    stat_keys = [
        "容貌", "才智", "流量熱度", "商業價值", "路人緣", "公關", "影響指數", "個人才藝",
        "唱跳", "演繹", "主持", "歌唱", "綜藝"
    ]
    st = {}
    tracks = ["唱跳", "演繹", "主持", "歌唱", "綜藝"]
    detected_main_track = None

    for sk in stat_keys:
        sk_m = re.search(rf"(?:主攻)?{sk}[^\d\n\r]*(\d+)", content)
        st[sk] = int(sk_m.group(1)) if sk_m else 50

    track_m = re.search(r"主攻(?:賽道)?[^\n\r:：]*[:：]\s*([^\n\r]+)", content)
    if track_m:
        for vt in tracks:
            if vt in track_m.group(1):
                detected_main_track = vt
                break

    if not detected_main_track:
        for vt in tracks:
            if re.search(rf"主攻{vt}", content):
                detected_main_track = vt
                break

    if not detected_main_track:
        track_scores = {t: st.get(t, 50) for t in tracks}
        detected_main_track = max(track_scores, key=track_scores.get)

    data["primary_track"] = detected_main_track
    st["死忠粉絲數"] = 0
    st["活躍黑粉數"] = 0
    st["大眾認知度"] = 0
    data["stats"] = st
    return data


# -------------------- 指令：/審核通過 --------------------
@bot.tree.command(name="審核通過", description="【管理員專用】人設單兩段式審核：一審指引打勾，二審自動按公式秘密核發初始金幣")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(類別=[
    app_commands.Choice(name="自身角色 (玩家本人持有)", value="player"),
    app_commands.Choice(name="玩家 NPC (玩家自設配角)", value="player_npc"),
    app_commands.Choice(name="官方 NPC (全域公共人物)", value="official_npc")
])
@app_commands.describe(
    類別="選擇審核的人設類型",
    角色名="【選填】若已知角色名可填寫，留空則自動從人設單爬取",
    人設單文章連結="【選填】貼上人設帖子連結，留空則自動抓取本討論串貼文",
    隱藏算式明細="是否向公開頻道隱藏具體乘算明細（預設為是，玩家只見總金額）"
)
async def audit_pass_cmd(
    interaction: discord.Interaction,
    類別: app_commands.Choice[str],
    角色名: str = None,
    人設單文章連結: str = None,
    隱藏算式明細: bool = True
):
    g_id = interaction.guild_id
    ch = interaction.channel
    await interaction.response.defer(ephemeral=False)

    try:
        target_content, post_author_id = "", 0
        if 人設單文章連結:
            link_m = re.search(r"channels/\d+/(\d+)(?:/(\d+))?", 人設單文章連結.strip())
            if link_m:
                c_id = int(link_m.group(1))
                m_id = int(link_m.group(2)) if link_m.group(2) else None
                fetch_ch = interaction.client.get_channel(c_id) or await interaction.client.fetch_channel(c_id)
                if isinstance(fetch_ch, discord.Thread):
                    first_msg = await fetch_ch.fetch_message(fetch_ch.id)
                    target_content = first_msg.content
                    post_author_id = first_msg.author.id
                elif m_id:
                    m = await fetch_ch.fetch_message(m_id)
                    target_content = m.content
                    post_author_id = m.author.id
        elif isinstance(ch, discord.Thread):
            try:
                starter = await ch.parent.fetch_message(ch.id) if hasattr(ch, "parent") else None
                if not starter: starter = await ch.fetch_message(ch.id)
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
            await interaction.followup.send("❌ 無法偵測到角色姓名！請確認人設格式，或手動填入【角色名】參數。", ephemeral=True)
            return

        thread_id = ch.id if isinstance(ch, discord.Thread) else 0
        is_npc_code = 0 if 類別.value == "player" else (2 if 類別.value == "player_npc" else 1)
        faction_default = "官方勢力" if 類別.value == "official_npc" else "無"

        async with aiosqlite.connect(DB_PATH) as db:
            current_count = 0
            if thread_id:
                async with db.execute("SELECT audit_count FROM profile_audits WHERE guild_id = ? AND thread_id = ?", (g_id, thread_id)) as a_cur:
                    rec = await a_cur.fetchone()
                    current_count = rec[0] if rec else 0

            # ==================== 一審階段 ====================
            if current_count == 0:
                if thread_id:
                    await db.execute("""
                        INSERT INTO profile_audits (guild_id, thread_id, char_name, audit_count, status)
                        VALUES (?, ?, ?, 1, '初審通過')
                        ON CONFLICT(guild_id, thread_id) DO UPDATE SET audit_count = 1, status = '初審通過', char_name = excluded.char_name
                    """, (g_id, thread_id, c_name))
                    await db.commit()

                owner_mention = f"<@{post_author_id}>" if post_author_id > 0 else ""
                embed = discord.Embed(
                    title=f"📝【{c_name}】人設初審通過（1/2）",
                    description=(
                        f"審核管理員：{interaction.user.mention}\n"
                        f"審核類別：**【{類別.name}】**\n\n"
                        f"1、使用 `/查看`、`/背包` 確認檔案已登記\n"
                        f"2、使用 `/任務` 查看角色任務看板\n"
                        f"3、使用 `/檔案更新` 可自由調整代表色與感情/身分\n"
                        f"4、稍後二審完畢將自動發放獎勵金幣並給予身分組！\n\n"
                        f"**以上！都確定無誤後請按本訊息 ✅**"
                    ),
                    color=0xF1C40F
                )
                sent_msg = await interaction.followup.send(content=owner_mention, embed=embed)
                if 類別.value == "official_npc":
                    try: await sent_msg.add_reaction("✅")
                    except Exception: pass
                return

            # ==================== 二審（終審）階段 ====================
            elif current_count == 1:
                if thread_id:
                    await db.execute("UPDATE profile_audits SET audit_count = 2, status = '終審完畢' WHERE guild_id = ? AND thread_id = ?", (g_id, thread_id))

                st = parsed.get("stats", {})
                v_hot, v_comm = int(st.get("流量熱度", 50)), int(st.get("商業價值", 50))
                v_passer, v_pr = int(st.get("路人緣", 50)), int(st.get("公關", 50))
                v_infl, v_face = int(st.get("影響指數", 50)), int(st.get("容貌", 50))
                v_iq, v_art = int(st.get("才智", 50)), int(st.get("個人才藝", 50))
                v_tracks = sum(int(st.get(t, 50)) for t in ["唱跳", "演繹", "主持", "歌唱", "綜藝"])

                m_hot, m_comm = v_hot * 80, v_comm * 100
                m_passer, m_pr = v_passer * 30, v_pr * 20
                m_infl, m_face = v_infl * 50, v_face * 40
                m_iq, m_tracks, m_art = v_iq * 20, v_tracks * 30, v_art * 40
                total_initial_cash = m_hot + m_comm + m_passer + m_pr + m_infl + m_face + m_iq + m_tracks + m_art

                h = int(parsed.get("height", 175))
                w = int(parsed.get("weight", 55))
                f_health, f_app, bmi_val, warn_bmi = check_bmi_impact(h, w, 100, v_face)
                st["容貌"] = f_app

                assigned_uid = 0 if is_npc_code == 1 else (post_author_id if post_author_id > 0 else interaction.user.id)

                await db.execute("""
                    INSERT INTO characters (
                        guild_id, user_id, name, stage_name, age, gender, job, faction,
                        tags, relationship_status, created_at, is_npc, height, weight,
                        nationality, education, orientation, primary_track, char_health,
                        affiliation_type, affiliation_name, cash, bank, stats
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 10000, ?, ?)
                    ON CONFLICT(guild_id, name) DO UPDATE SET
                        stage_name = excluded.stage_name, age = excluded.age, gender = excluded.gender,
                        job = excluded.job, height = excluded.height, weight = excluded.weight,
                        char_health = excluded.char_health, primary_track = excluded.primary_track,
                        stats = excluded.stats, bank = bank + excluded.bank, is_npc = excluded.is_npc
                """, (
                    g_id, assigned_uid, c_name, parsed.get("stage_name", c_name),
                    parsed.get("age", 22), parsed.get("gender", "女"), parsed.get("job", "新人"),
                    faction_default, parsed.get("tags", ""), parsed.get("relationship_status", "單身"),
                    time.time(), is_npc_code, h, w, parsed.get("nationality", "本國"),
                    parsed.get("education", "大學"), parsed.get("orientation", "保密"),
                    parsed.get("primary_track", "常規"), f_health,
                    parsed.get("affiliation_type", "單打獨鬥"), parsed.get("affiliation_name", "無"),
                    total_initial_cash, json.dumps(st, ensure_ascii=False)
                ))
                await db.commit()

                owner_mention = f"<@{assigned_uid}>" if assigned_uid > 0 else ""
                embed = discord.Embed(
                    title=f"🎉【{c_name}】終審通過，正式入籍！",
                    description=(
                        f"受審角色：**{c_name}**（稱號: {parsed.get('stage_name', '無')}）\n"
                        f"審核類別：**【{類別.name}】** ｜ 終審官：{interaction.user.mention}\n\n"
                        f"• 主攻賽道：【**{parsed.get('primary_track', '常規')}**】\n"
                        f"• 身材體態：`{h} cm` / `{w} kg` (BMI: `{bmi_val}`)\n"
                        f"• 初始健康度：❤️ **{f_health} / 100**\n\n"
                        f"💰 **核算資產入帳：**\n"
                        f"• 零用金（現金）：**$10,000**\n"
                        f"• 評級核發金（已入銀行）：**${total_initial_cash:,}**"
                    ),
                    color=0x2ECC71
                )
                if warn_bmi: embed.add_field(name="⚠️ 身材體態指數提醒", value=warn_bmi, inline=False)

                calc_text = (
                    f"```yaml\n"
                    f"【初始資產核定明細 — {c_name}】\n"
                    f"・流量熱度：({v_hot}) × 80 ＝ ${m_hot:,}\n"
                    f"・商業價值：({v_comm}) × 100 ＝ ${m_comm:,}\n"
                    f"・路人緣：({v_passer}) × 30 ＝ ${m_passer:,}\n"
                    f"・公關：({v_pr}) × 20 ＝ ${m_pr:,}\n"
                    f"・影響指數：({v_infl}) × 50 ＝ ${m_infl:,}\n"
                    f"・容貌：({v_face}) × 40 ＝ ${m_face:,}\n"
                    f"・才智：({v_iq}) × 20 ＝ ${m_iq:,}\n"
                    f"・賽道加總：({v_tracks}) × 30 ＝ ${m_tracks:,}\n"
                    f"・個人才藝：({v_art}) × 40 ＝ ${m_art:,}\n"
                    f"-----------------------------------------------\n"
                    f"＝ 初始發放總金幣：${total_initial_cash:,}\n"
                    f"```"
                )

                if not 隱藏算式明細:
                    embed.add_field(name="📊 審核金幣計算清單", value=calc_text, inline=False)
                    await interaction.followup.send(content=owner_mention, embed=embed)
                else:
                    await interaction.followup.send(content=owner_mention, embed=embed)
                    try: await interaction.user.send(calc_text)
                    except Exception: pass
                return
            else:
                await interaction.followup.send(f"⚠️ 角色【{c_name}】早已通過雙重審核！", ephemeral=True)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ 審核執行錯誤：`{e}`", ephemeral=True)
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


# -------------------- 指令：/檔案建立 --------------------
@bot.tree.command(name="檔案建立", description="建立玩家個人角色或自設配角檔案")
@app_commands.choices(類別=[
    app_commands.Choice(name="玩家角色", value="0"),
    app_commands.Choice(name="玩家自設 NPC", value="2")
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
    label = "玩家角色" if is_npc_val == 0 else "自設配角 NPC"
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


# -------------------- 指令：/檔案更新 --------------------
@bot.tree.command(name="檔案更新", description="更新個人角色、自設配角或官方NPC的個資資料")
@app_commands.choices(類別=[
    app_commands.Choice(name="自身角色", value="角色"),
    app_commands.Choice(name="玩家自設 NPC", value="玩家npc"),
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
            @discord.ui.select(placeholder="請選擇欲更新的檔案...", options=[discord.SelectOption(label=c, value=c) for c in candidates[:25]])
            async def select_callback(self, inter: discord.Interaction, select: discord.ui.Select):
                view = ProfileUpdateStepView(select.values[0], g_id, is_admin)
                await inter.response.send_message(f"⚙️ 正在更新【{select.values[0]}】的檔案，請點選下方操作：", view=view, ephemeral=True)

        await interaction.response.send_message("請先選擇要更新的角色檔案：", view=CharPickView(), ephemeral=True)
    else:
        char_name = candidates[0]
        view = ProfileUpdateStepView(char_name, g_id, is_admin)
        await interaction.response.send_message(f"⚙️ 正在更新【{char_name}】的檔案，請點選下方操作：", view=view, ephemeral=True)
# -------------------- 指令：/存錢、/取錢、/轉錢 --------------------
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


@bot.tree.command(name="轉錢", description="將手頭現金轉帳給其他角色")
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


# -------------------- 指令：/售物 --------------------
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


# -------------------- 指令：/陣營 --------------------
@bot.tree.command(name="陣營", description="陣營主控台：捐獻公款、查看金庫排名或購買全體激勵加成")
@app_commands.choices(操作=[
    app_commands.Choice(name="查看現況與金庫排名", value="view"),
    app_commands.Choice(name="捐獻資金至陣營金庫", value="donate"),
    app_commands.Choice(name="動用公款啟動全體激勵Buff", value="buy"),
    app_commands.Choice(name="脫離陣營(需賠付違約金)", value="exit"),
    app_commands.Choice(name="加入指定陣營", value="join")
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
            async with db.execute("SELECT treasury, desc FROM factions WHERE guild_id = ? AND name = ?", (g_id, my_faction)) as cur:
                f_info = await cur.fetchone()
            async with db.execute("SELECT char_name, contribution FROM faction_members WHERE guild_id = ? AND faction_name = ? ORDER BY contribution DESC LIMIT 5", (g_id, my_faction)) as cur:
                rankings = await cur.fetchall()

        treasury, desc = f_info if f_info else (0, "世界觀官方勢力")
        embed = discord.Embed(title=f"🚩 勢力陣營面板：【{my_faction}】", color=0xE74C3C)
        embed.description = f"{desc}\n\n💰 **陣營金庫儲備公款**：${treasury:,}"
        rank_lines = [f"`#{i+1}` **{r[0]}** ｜ 貢獻度: {r[1]:,}" for i, r in enumerate(rankings)]
        embed.add_field(name="🏆 陣營內部貢獻前五名", value="\n".join(rank_lines) if rank_lines else "暫無貢獻紀錄", inline=False)
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

        await interaction.response.send_message(f"🚩✨ 動用陣營公款 **${cost:,}** 啟動全陣營激勵！【{my_faction}】全體成員個人銀行帳戶各入帳福利獎金 **$10,000**！")

    elif op == "exit":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT exit_fee FROM factions WHERE guild_id = ? AND name = ?", (g_id, my_faction)) as cur:
                f_row = await cur.fetchone()
                exit_fee = f_row[0] if f_row else 5000

            if cash < exit_fee:
                await interaction.response.send_message(f"❌ 現金不足以支付違約金！需要手頭現金 **${exit_fee:,}**。", ephemeral=True)
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


# -------------------- 指令：/背包 --------------------
@bot.tree.command(name="背包", description="查看角色隨身背包物品、數量與來源途徑")
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
        embed.add_field(name=f"📦 {name} × {amt}", value=f"來源: `{giver}`", inline=True)

    await interaction.response.send_message(embed=embed)
# -------------------- 指令清理與強制同步 --------------------
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
# -------------------- 資料庫完整初始化（包含所有資料表） --------------------
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

# -------------------- 系統就緒啟動與定時排程掛載 --------------------
@bot.event
async def on_ready():
    # 1. 資料庫完整建表與更新
    await init_db()
    await extend_database_tables()
    await init_auction_table()

    # 2. 啟動背景定時任務
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

    # 3. 全域指令同步
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
