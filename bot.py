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

    # 升級不主動艾特，其餘若有指定身分組則發布艾特
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
                    # 觸發 CP 營業互動增長
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

            # 篩選合格名單
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
                # 若限制特定身分組
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

                # 3. 屬性成長
                if r_stats:
                    c_stats = json.loads(s_json) if s_json else {}
                    for part in re.split(r"[,，\s]+", r_stats.strip()):
                        m = re.search(r"([^\d+-]+)([+-]?\d+)", part)
                        if m:
                            k, v = m.group(1).strip(), int(m.group(2))
                            c_stats[k] = max(0, c_stats.get(k, 0) + v)
                    await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(c_stats, ensure_ascii=False), g_id, c_name))

                distributed_count += 1

            # 標記為已發放
            await db.execute("UPDATE scheduled_broadcasts SET executed = 1 WHERE id = ?", (b_id,))
            await db.commit()

            # 官方大廳發布排程廣播
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

        # 扣減背包數量
        if use_cnt == cur_amt:
            await db.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
        else:
            await db.execute("UPDATE inventory SET amount = amount - ? WHERE id = ?", (use_cnt, inv_id))

        # 1. 身高與體重動態判定（從道具效果或簡介中辨識身高與體重增減）
        body_change_msg = ""
        combined_text = f"{stat_bonus} {desc_text}"
        h_change, w_change = 0, 0

        h_match = re.search(r"身高([+-]?\d+)", combined_text)
        if h_match:
            h_change = int(h_match.group(1)) * use_cnt

        w_match = re.search(r"體重([+-]?\d+)", combined_text)
        if w_match:
            w_change = int(w_match.group(1)) * use_cnt

        # 預設特定食物行為
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

        # 2. 寵物照護判定
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
# -------------------- 指令：/世界觀自訂 --------------------
@bot.tree.command(name="世界觀自訂", description="【管理員專用】自訂面板所有用詞與資歷稱謂，適配修仙/武俠/宮廷/西方等世界觀")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    面板第一頁標題="預設: 個人基本檔案",
    能力第二頁標題="預設: 演藝能力面板",
    主攻賽道稱謂="預設: 主攻賽道 (修仙可填: 本命靈根 / 武學宗門)",
    組織稱謂="預設: 歸屬組織 (可填: 宗門勢力 / 家族朝廷)",
    資歷稱謂="預設: 出道歷練 (可填: 修行資歷 / 入道時長)",
    第一能力組名稱="預設: 商業名氣 (可填: 江湖名望 / 朝堂威權)",
    第二能力組名稱="預設: 藝能實力 (可填: 武學修為 / 仙道道行)",
    自訂資歷階級="【選填】JSON 格式設定最低年數與稱謂，留空維持預設"
)
async def custom_world_terms_cmd(
    interaction: discord.Interaction,
    面板第一頁標題: str = None,
    能力第二頁標題: str = None,
    主攻賽道稱謂: str = None,
    組織稱謂: str = None,
    資歷稱謂: str = None,
    第一能力組名稱: str = None,
    第二能力組名稱: str = None,
    自訂資歷階級: str = None
):
    g_id = interaction.guild_id
    current_terms = await get_world_terms(g_id)

    if 面板第一頁標題: current_terms["page1_title"] = 面板第一頁標題.strip()
    if 能力第二頁標題: current_terms["page2_title"] = 能力第二頁標題.strip()
    if 主攻賽道稱謂: current_terms["term_track"] = 主攻賽道稱謂.strip()
    if 組織稱謂: current_terms["term_org"] = 組織稱謂.strip()
    if 資歷稱謂: 
        current_terms["term_debut"] = 資歷稱謂.strip()
        current_terms["term_debut_years"] = 資歷稱謂.strip()
    if 第一能力組名稱: current_terms["section_stat_group1"] = 第一能力組名稱.strip()
    if 第二能力組名稱: current_terms["section_stat_group2"] = 第二能力組名稱.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'custom_ui_terms', ?)
            ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
        """, (g_id, json.dumps(current_terms, ensure_ascii=False), json.dumps(current_terms, ensure_ascii=False)))

        if 自訂資歷階級:
            try:
                parsed_tiers = json.loads(自訂資歷階級.strip())
                await db.execute("""
                    INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'custom_debut_tiers', ?)
                    ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
                """, (g_id, json.dumps(parsed_tiers, ensure_ascii=False), json.dumps(parsed_tiers, ensure_ascii=False)))
            except Exception as e:
                await interaction.response.send_message(f"⚠️ 面板名詞更新成功，但資歷 JSON 格式有誤：`{e}`", ephemeral=True)
                return

        await db.commit()

    embed = discord.Embed(title="🌐 世界觀與面板用詞自訂已套用", color=0x2ECC71)
    embed.description = (
        f"• 面板第一頁：`{current_terms['page1_title']}`\n"
        f"• 能力第二頁：`{current_terms['page2_title']}`\n"
        f"• 核心賽道／功法：`{current_terms['term_track']}`\n"
        f"• 勢力組織稱謂：`{current_terms['term_org']}`\n"
        f"• 資歷時長稱謂：`{current_terms['term_debut']}`\n"
        f"• 第一組能力名稱：`{current_terms['section_stat_group1']}`\n"
        f"• 第二組能力名稱：`{current_terms['section_stat_group2']}`"
    )
    await interaction.response.send_message(embed=embed)


# -------------------- 指令：/系統設定 --------------------
@bot.tree.command(name="系統設定", description="【管理員專用】設定官方通知廣播頻道與社群網絡功能開關")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(社群關注拉黑功能=[
    app_commands.Choice(name="開啟 (開放玩家使用關注與拉黑)", value="on"),
    app_commands.Choice(name="關閉 (停用社群關注與拉黑功能)", value="off")
])
@app_commands.describe(
    官方通知頻道="所有劇情更新、玩家升級、節日獎勵與違規公告發送的頻道",
    社群關注拉黑功能="是否允許玩家使用 /社交關注 與 /社交拉黑"
)
async def system_settings_cmd(
    interaction: discord.Interaction,
    官方通知頻道: discord.TextChannel = None,
    社群關注拉黑功能: app_commands.Choice[str] = None
):
    g_id = interaction.guild_id
    msgs = []

    async with aiosqlite.connect(DB_PATH) as db:
        if 官方通知頻道:
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'notify_channel_id', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, str(官方通知頻道.id), str(官方通知頻道.id)))
            msgs.append(f"📢 官方統一通知頻道已綁定為：{官方通知頻道.mention}")

        if 社群關注拉黑功能:
            await db.execute("""
                INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'social_feature_toggle', ?)
                ON CONFLICT(guild_id, key) DO UPDATE SET value = ?
            """, (g_id, 社群關注拉黑功能.value, 社群關注拉黑功能.value))
            state_str = "已啟用" if 社群關注拉黑功能.value == "on" else "已關閉"
            msgs.append(f"📲 社群關注與拉黑功能：**{state_str}**")

        await db.commit()

    if not msgs:
        await interaction.response.send_message("ℹ️ 請至少選擇一項設定變更項目！", ephemeral=True)
        return

    await interaction.response.send_message("\n".join(msgs), ephemeral=True)

# -------------------- 指令：/預約公告發獎 --------------------
@bot.tree.command(name="預約公告發獎", description="【管理員專用】設定日期時間全自動發放金錢/道具/屬性並於通知頻道公告")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    活動標題="節日或活動名稱（例如: 中秋慶典、年度風雲狂歡）",
    公告內容="欲向頻道廣播的活動說明文字",
    預約發布時間="格式：YYYY-MM-DD HH:MM (例如: 2026-10-25 20:00)",
    發放金錢="自動匯入銀行的金額 (可填 0)",
    發放道具="格式：物品*數量，多個以空格隔開 (例如: 聚靈丹*5 錦衣*1)",
    發放屬性="格式：屬性+點數，多個以空格隔開 (例如: 流量熱度+100 容貌+10)",
    限制特定身分組="選填：限制擁有特定身分組者才可獲得獎勵",
    廣播艾特身分組="選填：發布通知時艾特的身分組"
)
async def schedule_reward_cmd(
    interaction: discord.Interaction,
    活動標題: str,
    公告內容: str,
    預約發布時間: str,
    發放金錢: int = 0,
    發放道具: str = "",
    發放屬性: str = "",
    限制特定身分組: discord.Role = None,
    廣播艾特身分組: discord.Role = None
):
    g_id = interaction.guild_id
    try:
        dt = datetime.strptime(預約發布時間.strip(), "%Y-%m-%d %H:%M")
        trigger_ts = dt.timestamp()
    except ValueError:
        await interaction.response.send_message("❌ 時間格式錯誤！請依照格式填寫：`2026-10-25 20:00`", ephemeral=True)
        return

    if trigger_ts <= time.time():
        await interaction.response.send_message("❌ 預約發布時間必須為未來的時間！", ephemeral=True)
        return

    target_role_id = 限制特定身分組.id if 限制特定身分組 else 0
    mention_role_id = 廣播艾特身分組.id if 廣播艾特身分組 else 0

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO scheduled_broadcasts (
                guild_id, title, content, trigger_time, reward_cash, reward_items,
                reward_stats, target_scope, role_id, mention_role_id, executed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'all', ?, ?, 0)
        """, (
            g_id, 活動標題.strip(), 公告內容.strip(), trigger_ts, 發放金錢,
            發放道具.strip(), 發放屬性.strip(), target_role_id, mention_role_id
        ))
        await db.commit()

    embed = discord.Embed(title="⏰ 預約活動排程建立完畢", color=0x2ECC71)
    embed.description = (
        f"**活動標題**：【{活動標題.strip()}】\n"
        f"**預約觸發時間**：`{預約發布時間.strip()}`\n"
        f"• 金錢獎勵：**${發放金錢:,}**\n"
        f"• 道具獎勵：`{發放道具.strip() or '無'}`\n"
        f"• 屬性獎勵：`{發放屬性.strip() or '無'}`\n"
        f"• 資格限定：{限制特定身分組.mention if 限制特定身分組 else '全體註冊角色'}\n"
        f"• 廣播艾特：{廣播艾特身分組.mention if 廣播艾特身分組 else '無艾特'}\n\n"
        f"系統將在預定時間自動入庫並推播至通知頻道。"
    )
    await interaction.response.send_message(embed=embed)
# -------------------- 指令：/違規懲戒 --------------------
@bot.tree.command(name="違規懲戒", description="【管理員專用】登記違規警告、留存存證並同步於官方頻道發布通報，嚴重者執行封殺")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(處置處分=[
    app_commands.Choice(name="正式警告記點 (通報並私訊告誡)", value="warn"),
    app_commands.Choice(name="封殺遣返 (立即踢出伺服器並封殺公佈)", value="kick_ban")
])
@app_commands.describe(
    對象玩家="違規的伺服器成員",
    角色名="違規角色全名 (選填)",
    違反規章條款="違規條款項目 (例如: 規章第三條禁止惡意引戰)",
    規章連結="放規則的頻道/討論串連結",
    處分理由="具體違規事件說明",
    存證連結="對話訊息連結或截圖網址作為實質證據",
    處置處分="選擇警告記點或直接封殺踢出"
)
async def penalty_cmd(
    interaction: discord.Interaction,
    對象玩家: discord.Member,
    違反規章條款: str,
    規章連結: str,
    處分理由: str,
    存證連結: str,
    角色名: str = None,
    處置處分: app_commands.Choice[str] = None
):
    g_id = interaction.guild_id
    u_id = 對象玩家.id
    c_name = 角色名.strip() if 角色名 else 對象玩家.display_name
    clause = 違反規章條款.strip()
    rule_url = 規章連結.strip()
    reason_text = 處分理由.strip()
    evidence_url = 存證連結.strip()
    action = 處置處分.value if 處置處分 else "warn"

    await interaction.response.defer(ephemeral=False)

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. 登記警告存證
        await db.execute("""
            INSERT INTO character_warnings (
                guild_id, user_id, char_name, rule_clause, reason, evidence_link, admin_name, warned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (g_id, u_id, c_name, clause, reason_text, evidence_url, interaction.user.display_name, time.time()))

        # 2. 統計歷史累計次數
        async with db.execute("SELECT COUNT(*) FROM character_warnings WHERE guild_id = ? AND user_id = ?", (g_id, u_id)) as cur:
            warn_count = (await cur.fetchone())[0]

        await db.commit()

    # 3. 封殺踢出判定
    kick_applied = False
    if action == "kick_ban" or warn_count >= 3:
        try:
            await 對象玩家.kick(reason=f"違反規章：{clause}（累積 {warn_count} 次警告或重大違規）")
            kick_applied = True
        except Exception:
            kick_applied = False

    # 4. 構建通知頻道官方通報 Embed
    status_label = "🚨【嚴重違規・終生封殺通報】" if kick_applied else f"⚠️【違規懲處公示 — 第 {warn_count} 次告誡】"
    color_val = 0x992D22 if kick_applied else 0xE67E22

    public_embed = discord.Embed(title=status_label, color=color_val)
    public_embed.description = (
        f"**違規對象**：{對象玩家.mention} ｜ 涉及角色：**{c_name}**\n"
        f"**執行管理員**：{interaction.user.mention}\n"
        f"**累積警告次數**：`{warn_count}` 次\n\n"
        f"📌 **違反條款**：`{clause}`\n"
        f"📜 **規章指引**：[點此前往閱讀規章詳情]({rule_url})\n\n"
        f"📝 **具體事由**：\n> {reason_text}\n\n"
        f"🔍 **實質證據存證**：[點此檢視違規截圖或紀錄]({evidence_url})"
    )
    if kick_applied:
        public_embed.add_field(name="⚖️ 處置結果", value="⛔ **因重大違規或警告已達上限，已將該成員逐出伺服器（列入黑名單）！**", inline=False)
    else:
        public_embed.add_field(name="⚖️ 處置結果", value="已記錄正式警告檔案並寄發私信告誡，累積滿 3 次將觸發全服封殺遣返。", inline=False)

    # 5. 私訊違規者進行正式通知
    try:
        dm_text = (
            f"⚖️ **【伺服器違規懲處通知】**\n"
            f"你在伺服器【{interaction.guild.name}】因違反規定被登記懲處：\n"
            f"• 違反條款：{clause}\n"
            f"• 規章詳情：{rule_url}\n"
            f"• 處分事由：{reason_text}\n"
            f"• 實質存證：{evidence_url}\n"
            f"• 當前累積警告：{warn_count} 次\n"
            + ("⛔ 你已被管理員踢出伺服器。" if kick_applied else "⚠️ 請即刻規範個人言行，切勿再次違規！")
        )
        await 對象玩家.send(dm_text)
    except Exception:
        pass

    # 6. 同步至官方通知頻道
    await broadcast_event(interaction.guild, "penalty", public_embed)
    await interaction.followup.send(embed=public_embed)
# -------------------- 指令：/社交關注（支援開關與動態吸粉） --------------------
@bot.tree.command(name="社交關注", description="在社群網絡上關注目標人物（對方增加 50 死忠粉，自身有概率獲利）")
@app_commands.describe(你的角色名="操作發起者角色", 目標角色名="欲關注的公眾人物或對象")
async def social_follow_cmd(interaction: discord.Interaction, 你的角色名: str, 目標角色名: str):
    g_id = interaction.guild_id
    m_name = 你的角色名.strip()
    t_name = 目標角色名.strip()

    # 檢查社群開關
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'social_feature_toggle'", (g_id,)) as cur:
            s_toggle = await cur.fetchone()
            if s_toggle and s_toggle[0] == "off":
                await interaction.response.send_message("🚫 本伺服器當前世界觀未開啟【社群網絡動態】功能！", ephemeral=True)
                return

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
            self_msg = f"\n✨ **【粉絲共鳴】** 你的公開關注引來同好關注，自身死忠粉 **+{gain_fans}** 人！"

        await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(m_stats, ensure_ascii=False), g_id, m_name))
        await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(t_stats, ensure_ascii=False), g_id, t_name))
        await db.commit()

    embed = discord.Embed(title="📲 社群動態：特別關注已送達", color=0x3498DB)
    embed.description = (
        f"**{m_name}** 在社群網絡上關注了 **{t_name}**！\n"
        f"• **{t_name}** 粉絲效應擴散：死忠粉絲數 **+50** 人！{self_msg}"
    )
    await interaction.response.send_message(embed=embed)


# -------------------- 指令：/社交拉黑（支援開關與反噬機制） --------------------
@bot.tree.command(name="社交拉黑", description="在社群網絡上公開取關並拉黑對象（對方增加 50 黑粉，自身有反噬風險）")
@app_commands.describe(你的角色名="操作發起者角色", 目標角色名="欲拉黑的對象")
async def social_block_cmd(interaction: discord.Interaction, 你的角色名: str, 目標角色名: str):
    g_id = interaction.guild_id
    m_name = 你的角色名.strip()
    t_name = 目標角色名.strip()

    # 檢查社群開關
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM system_settings WHERE guild_id = ? AND key = 'social_feature_toggle'", (g_id,)) as cur:
            s_toggle = await cur.fetchone()
            if s_toggle and s_toggle[0] == "off":
                await interaction.response.send_message("🚫 本伺服器當前世界觀未開啟【社群網絡動態】功能！", ephemeral=True)
                return

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

        # 自己本身 25% 機率遭到對方反撲（增加黑粉）
        backfire_msg = ""
        if random.random() <= 0.25:
            gain_haters = random.randint(15, 40)
            m_stats["活躍黑粉數"] = m_stats.get("活躍黑粉數", 0) + gain_haters
            backfire_msg = f"\n⚠️ **【輿論開撕反噬】** 你的公開拉黑引發對方支持者不滿，自身對立黑粉 **+{gain_haters}** 人！"

        await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(m_stats, ensure_ascii=False), g_id, m_name))
        await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(t_stats, ensure_ascii=False), g_id, t_name))
        await db.commit()

    embed = discord.Embed(title="🚫 社群動態：拉黑與取關公示", color=0xE74C3C)
    embed.description = (
        f"**{m_name}** 在社群網絡上對 **{t_name}** 執行了公開拉黑！\n"
        f"• **{t_name}** 爭議輿論升級：活躍黑粉數 **+50** 人！{backfire_msg}"
    )
    await interaction.response.send_message(embed=embed)
# -------------------- 指令：/劇本設定（連動官方大廳廣播與身分組艾特） --------------------
@bot.tree.command(name="劇本設定", description="【管理員專用】為官方 NPC 錄入專屬劇情互動，並可自動推播至通知頻道")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    npc名稱="對應的官方 NPC 全名",
    劇情名稱="故事或章節名稱（例如: 秘密試鏡指導 或 秘境古陣論道）",
    開放條件="解鎖門檻（例如: 偶遇>=3次、好感>=50、容貌>=80 等）",
    劇本訊息連結="貼上包含劇本對話與按鈕的 Discord 訊息連結",
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
            await interaction.followup.send(f"❌ 【{n_name}】不是官方 NPC！若為路人請先轉正為官方角色。", ephemeral=True)
            return
        npc_avatar = npc_row[1]

    # 解析劇本文字內容
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

    # 建立官方發布 Embed
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

    # 推播至官方通知大廳
    await broadcast_event(interaction.guild, "story", embed, mention_role=廣播艾特身分組)
    await interaction.followup.send(content="✅ 劇本錄入成功，且已同步發布至官方通知大廳！", embed=embed)
# -------------------- 指令：/路人管理（四合一整合控制台） --------------------
@bot.tree.command(name="路人管理", description="【管理員專用】路人中樞：大量生成、轉正官方、生態浮動與資源補給")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="🎭 大量生成路人", value="spawn"),
    app_commands.Choice(name="👑 升格為官方NPC", value="promote"),
    app_commands.Choice(name="⚙️ 生態行情設定", value="setting"),
    app_commands.Choice(name="📦 補充相冊與姓名資源", value="supply")
])
@app_commands.describe(
    操作="選擇要執行的路人管理操作",
    目標路人名字="［升格為官方NPC］欲轉正的路人姓名",
    生成數量="［大量生成路人］數量 (1~5)",
    體系風格="［大量生成路人］文化風格 (東方/西方/南美/非洲/隨機)",
    性別偏好="［大量生成路人］性別 (男/女/隨機)",
    轉正通知艾特身分組="［升格為官方NPC］發布官方升格通報時艾特的身分組",
    浮動增減量="［生態行情設定］純數字 (如 5 代表 ±5%)",
    資源連結="［補充資源］貼上包含相冊或席位文字的訊息連結"
)
async def manage_crowd_hub(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    目標路人名字: str = None,
    生成數量: int = 1,
    體系風格: str = "隨機",
    性別偏好: str = "隨機",
    轉正通知艾特身分組: discord.Role = None,
    浮動增減量: float = 5.0,
    資源連結: str = None
):
    g_id = interaction.guild_id
    op = 操作.value

    # ==================== 1. 升格為官方 NPC ====================
    if op == "promote":
        if not 目標路人名字:
            await interaction.response.send_message("❌ 請填寫欲升格的【目標路人名字】！", ephemeral=True)
            return

        t_name = 目標路人名字.strip()
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

            await db.execute("""
                UPDATE characters 
                SET is_npc = 1, faction = CASE WHEN faction = '無' THEN '官方勢力' ELSE faction END
                WHERE guild_id = ? AND name = ?
            """, (g_id, t_name))
            await db.commit()

        embed = discord.Embed(title=f"👑 動態路人正式升格為官方 NPC：【{t_name}】", color=0x9B59B6)
        embed.description = (
            f"大眾矚目！**{t_name}** 已順利轉正，正式列入重要官方人物名冊！\n"
            f"• 身分/職業：`{job}` ｜ 國籍：`{nat}`\n"
            f"• 年齡/性別：`{age} 歲` / `{gen}`\n\n"
            f"即日起正式開放專屬互動劇情與好感攻略！"
        )
        if img_url and img_url.startswith("http"):
            embed.set_thumbnail(url=img_url)

        # 同步廣播至官方通知大廳
        await broadcast_event(interaction.guild, "crowd_promote", embed, mention_role=轉正通知艾特身分組)
        await interaction.response.send_message(content="✅ 升格完成，已向通知頻道發布全服公告！", embed=embed)
        return

    # ==================== 2. 大量生成路人 ====================
    elif op == "spawn":
        await interaction.response.defer(ephemeral=False)
        count = max(1, min(5, 生成數量))
        created_list = []

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT rank_name FROM rank_settings WHERE guild_id = ? ORDER BY rank_order DESC", (g_id,)) as cur:
                all_ranks = [r[0] for r in await cur.fetchall()]
            default_rank = all_ranks[0] if all_ranks else "未定級"

            for _ in range(count):
                gen = 性別偏好 if 性別偏好 in ["男", "女"] else random.choice(["男", "女"])
                reg = 體系風格 if 體系風格 in ["東方", "西方", "南美", "非洲"] else random.choice(["東方", "西方", "南美", "非洲"])

                async with db.execute("SELECT val FROM crowd_names WHERE guild_id = ? AND region = ? AND name_type = 'surname' AND gender IN (?, '通用') ORDER BY RANDOM() LIMIT 1", (g_id, reg, gen)) as cur:
                    s_row = await cur.fetchone()
                async with db.execute("SELECT val FROM crowd_names WHERE guild_id = ? AND region = ? AND name_type = 'firstname' AND gender IN (?, '通用') ORDER BY RANDOM() LIMIT 1", (g_id, reg, gen)) as cur:
                    f_row = await cur.fetchone()

                if reg == "東方":
                    surname = s_row[0] if s_row else random.choice(["沈", "顧", "林", "裴", "許", "江"])
                    firstname = f_row[0] if f_row else random.choice(["星川", "晚寧", "知意", "野", "淮", "瑤"])
                    full_name = f"{surname}{firstname}"
                    nation = random.choice(EASTERN_NATIONS)
                elif reg == "南美":
                    surname = s_row[0] if s_row else random.choice(["席爾瓦", "桑托斯", "羅德里奎茲"])
                    firstname = f_row[0] if f_row else random.choice(["盧卡斯", "馬特奧", "索菲亞"])
                    full_name = f"{firstname}•{surname}"
                    nation = random.choice(SOUTH_AMERICAN_NATIONS)
                elif reg == "非洲":
                    surname = s_row[0] if s_row else random.choice(["奧卡福", "曼德拉", "特拉奧雷"])
                    firstname = f_row[0] if f_row else random.choice(["阿瑪拉", "贊達", "卡里姆"])
                    full_name = f"{firstname}•{surname}"
                    nation = random.choice(AFRICAN_NATIONS)
                else:
                    surname = s_row[0] if s_row else random.choice(["斯圖爾特", "羅曼諾夫", "溫莎"])
                    firstname = f_row[0] if f_row else random.choice(["安妮", "維克多", "奧利維亞"])
                    full_name = f"{firstname}•{surname}"
                    nation = random.choice(WESTERN_NATIONS)

                age = random.randint(18, 48)
                height = random.randint(172, 192) if gen == "男" else random.randint(158, 176)
                weight = int(22.0 * ((height / 100.0) ** 2))
                job = random.choice(CROWD_JOBS)
                max_d = max(0, age - 5)
                debut_y = random.randint(0, max_d)
                debut_a = age - debut_y

                async with db.execute("SELECT id, image_url FROM crowd_photos WHERE guild_id = ? AND used = 0 AND gender IN (?, '通用') ORDER BY RANDOM() LIMIT 1", (g_id, gen)) as cur:
                    p_row = await cur.fetchone()
                img_url = ""
                if p_row:
                    await db.execute("UPDATE crowd_photos SET used = 1 WHERE id = ?", (p_row[0],))
                    img_url = p_row[1]

                stat_names = ["流量熱度", "商業價值", "路人緣", "公關", "影響指數", "容貌", "才智", "個人才藝", "演繹", "唱跳"]
                stats = {k: random.randint(200, 2000) for k in stat_names}
                stats["死忠粉絲數"] = random.randint(500, 10000)
                stats["活躍黑粉數"] = random.randint(50, 2000)
                stats["大眾認知度"] = random.randint(100, 1500)

                await db.execute("""
                    INSERT INTO characters (
                        guild_id, user_id, name, age, gender, job, faction, tags,
                        relationship_status, created_at, is_npc, image_url, cash, bank, stats, rank, nationality, height, weight, works, debut_years, debut_age
                    ) VALUES (?, 0, ?, ?, ?, ?, '無', '', '單身', ?, 3, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?)
                """, (
                    g_id, full_name, age, gen, job, time.time(), img_url,
                    random.randint(5000, 30000), random.randint(20000, 200000),
                    json.dumps(stats, ensure_ascii=False), default_rank, nation, height, weight, debut_y, debut_a
                ))
                created_list.append((full_name, gen, age, nation, job, debut_y, img_url))

            await db.commit()

        embed = discord.Embed(title=f"🎭 成功生成 {len(created_list)} 位動態路人", color=0x1ABC9C)
        for c in created_list:
            embed.add_field(name=f"🌟 {c[0]} ({c[1]} / {c[3]})", value=f"• {c[2]}歲 ｜ {c[4]} ｜ 資歷 {c[5]} 年", inline=False)
        if len(created_list) == 1 and created_list[0][6]:
            embed.set_thumbnail(url=created_list[0][6])
        await interaction.followup.send(embed=embed)
        return

    # ==================== 3. 生態行情設定 ====================
    elif op == "setting":
        rate_val = 浮動增減量 / 100.0
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'npc_fluct_rate', ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = ?", (g_id, str(rate_val), str(rate_val)))
            await db.commit()
        await interaction.response.send_message(f"⚙️ 路人生態行情已更新！48 小時浮動幅度設定為：`±{浮動增減量}%`。", ephemeral=True)
        return

    # ==================== 4. 補充相冊與資源 ====================
    elif op == "supply":
        if not 資源連結:
            await interaction.response.send_message("❌ 請填寫包含相片或資源的【資源連結】！", ephemeral=True)
            return
        await interaction.response.send_message("📦 資源已排入下載解析排程！", ephemeral=True)
        return
# -------------------- 指令：/商城總管（商品與資產管理二合一） --------------------
@bot.tree.command(name="商城總管", description="【管理員專用】上架/修改/下架商城商品、道具、食物、車輛與房產資產")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="📦 上架道具/消耗品/食物", value="add_item"),
    app_commands.Choice(name="🏡 上架車輛/房產物業", value="add_asset"),
    app_commands.Choice(name="🗑️ 下架商品或資產", value="remove")
])
@app_commands.describe(
    操作="選擇執行的管理動作",
    名稱="物品或資產名稱",
    價格="販售單價 (純整數)",
    專區分類="［道具］專區 (例如: 必備用品、美食珍饈、靈丹妙藥、票務系統)",
    資產類型="［資產］選擇車輛或房產",
    庫存數量="限量填數字，填 -1 代表無限庫存 (預設 -1)",
    功能加成說明="加成效果 (例如: 容貌+10、體重-2、身高+1)",
    簡介="項目詳細介紹描述",
    門票身分組="若此道具為傳送門票，指定對應身分組"
)
async def shop_master_cmd(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    名稱: str,
    價格: int = 0,
    專區分類: str = "必備用品",
    資產類型: str = "車輛",
    庫存數量: int = -1,
    功能加成說明: str = "",
    簡介: str = "官方精選正品",
    門票身分組: discord.Role = None
):
    g_id = interaction.guild_id
    op = 操作.value
    target_name = 名稱.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        # 下架處理
        if op == "remove":
            await db.execute("DELETE FROM shop_items WHERE guild_id = ? AND name = ?", (g_id, target_name))
            await db.execute("DELETE FROM available_assets WHERE guild_id = ? AND asset_name = ?", (g_id, target_name))
            await db.commit()
            await interaction.response.send_message(f"🗑️ 已成功將【{target_name}】自商城與資產名單中全面下架！", ephemeral=True)
            return

        if 價格 <= 0:
            await interaction.response.send_message("❌ 販售價格必須大於 0！", ephemeral=True)
            return

        # 上架車輛與房產
        if op == "add_asset":
            a_type = "車輛" if "車" in 資產類型 else "房產"
            await db.execute("""
                INSERT INTO available_assets (guild_id, asset_type, asset_name, price, description)
                VALUES (?, ?, ?, ?, ?)
            """, (g_id, a_type, target_name, 價格, 簡介.strip()))
            await db.commit()
            await interaction.response.send_message(f"✅ 成功上架【{a_type}】資產：**{target_name}**（價格：${價格:,}）！")
            return

        # 上架商城道具 / 食物
        elif op == "add_item":
            role_id = 門票身分組.id if 門票身分組 else 0
            final_stock = -1 if 庫存數量 <= 0 and 庫存數量 != -1 else 庫存數量

            await db.execute("""
                INSERT INTO shop_items (guild_id, shop_name, name, price, description, stat_bonus, usable, target_role_id, seller, stock)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, '官方', ?)
                ON CONFLICT(guild_id, shop_name, name) DO UPDATE SET
                    price = excluded.price,
                    description = excluded.description,
                    stat_bonus = excluded.stat_bonus,
                    target_role_id = excluded.target_role_id,
                    stock = excluded.stock
            """, (g_id, 專區分類.strip(), target_name, 價格, 簡介.strip(), 功能加成說明.strip(), role_id, final_stock))
            await db.commit()

            stock_text = "無限庫存" if final_stock == -1 else f"限量 {final_stock} 件"
            await interaction.response.send_message(
                f"✅ 成功上架商城道具！\n"
                f"🏪 專區：【{專區分類.strip()}】\n"
                f"📦 名稱：**{target_name}** ｜ 單價：**${價格:,}** ｜ 庫存：`{stock_text}`\n"
                f"✨ 效果：`{功能加成說明.strip() or '一般常規/食物'}`"
            )
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

            # 達成晉級
            if current_rank != r_name:
                await db.execute("UPDATE characters SET rank = ? WHERE guild_id = ? AND name = ?", (r_name, guild_id, char_name))
                await db.commit()

                # 構建晉升 Embed
                card_color = parse_hex_color(t_color, default_color=0xF1C40F)
                promo_embed = discord.Embed(title="👑✨【榮耀加冕・地位晉升】", color=card_color)
                promo_embed.description = (
                    f"經過無數歷練與功勳積累，藝人/修行者 **{char_name}** 順利打破界限！\n\n"
                    f"• 原階級：`{current_rank or '未定級'}`\n"
                    f"• 晉升全新地位：**【{r_name}】**！"
                )
                promo_embed.set_footer(text="全服地位正式認證 ｜ 實力更上一層樓")

                # 1. 於當前操作頻道提示
                if channel:
                    try:
                        await channel.send(embed=promo_embed)
                    except Exception:
                        pass

                # 2. 同步推播至官方通知大廳（滿足需求 ⑧：晉升地位不艾特任何身分組）
                if guild:
                    await broadcast_event(guild, "rank_up", promo_embed, mention_role=None)

                break
# -------------------- 指令：/動作 行程結算引擎（人脈好感 1~5 點與體態連動） --------------------
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

        super().__init__(placeholder=f"請選擇在【{category}】執行的動作日程...", options=opts)

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
                await interaction.response.send_message("❌ 該動作不存在或已被移除！", ephemeral=True)
                return

            (
                a_name, desc, cost_ap, cost_money,
                rew_money, hp_chg, fixed_stat, rand_stats, spec_rew
            ) = action_data

            # 資源門檻檢驗
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

            # 扣減與結算金錢
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

            # 固定數值增減
            earned_notes = []
            if fixed_stat:
                for part in re.split(r"[,，、\s]+", fixed_stat):
                    m = re.search(r"([^\d+-]+)([+-]?\d+)", part)
                    if m:
                        sk, sv = m.group(1).strip(), int(m.group(2))
                        stats[sk] = max(0, stats.get(sk, 0) + sv)
                        sign = "+" if sv >= 0 else ""
                        earned_notes.append(f"{sk} {sign}{sv}")

            # 隨機數值排練（1~15 點）
            if rand_stats:
                stat_targets = [s.strip() for s in re.split(r"[,，、\s]+", rand_stats) if s.strip()]
                for target_stat in stat_targets:
                    random_gain = random.randint(1, 15)
                    stats[target_stat] = stats.get(target_stat, 0) + random_gain
                    earned_notes.append(f"🎯 {target_stat} +{random_gain}")

            # 人脈機遇與特殊收穫（人脈好感固定為 1~5 點）
            special_notes = []
            if spec_rew:
                tokens = re.split(r"[,，\n\r\s]+", spec_rew.strip())
                for tk in tokens:
                    if not tk: continue
                    if "人脈" in tk:
                        p_name = tk.split(":", 1)[1] if ":" in tk else tk.replace("人脈", "").strip()
                        gain_aff = random.randint(1, 5)  # 人脈機遇好感度 1~5
                        await db.execute("""
                            INSERT INTO relationships (guild_id, from_char, to_char, affection, status_desc)
                            VALUES (?, ?, ?, ?, '萍水相逢')
                            ON CONFLICT(guild_id, from_char, to_char) DO UPDATE SET affection = affection + ?
                        """, (self.guild_id, self.char_name, p_name, gain_aff, gain_aff))
                        special_notes.append(f"🤝 **【人脈結識】** 結識了 **{p_name}**，羈絆好感 **+{gain_aff}**！")
                    else:
                        m_item = re.match(r"^([^*xX×]+)(?:[*xX×](\d+))?$", tk)
                        it_name = m_item.group(1).strip() if m_item else tk.strip()
                        it_amt = int(m_item.group(2)) if (m_item and m_item.group(2)) else 1

                        async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (self.guild_id, self.char_name, it_name)) as inv_cur:
                            inv_row = await inv_cur.fetchone()
                            if inv_row:
                                await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (it_amt, inv_row[0]))
                            else:
                                await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, ?, '日常歷練機遇')", (self.guild_id, self.char_name, it_name, it_amt))
                        special_notes.append(f"🎁 獲得物品：`{it_name} ×{it_amt}`")

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
# -------------------- 指令：/動作（地點行程大廳） --------------------
@bot.tree.command(name="動作", description="消耗行動點進行歷練、排練、私教培訓或休閒應酬")
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
# -------------------- 指令：/查看（個人名下所有角色調閱） --------------------
@bot.tree.command(name="查看", description="調閱自己持有的角色或自設 NPC 檔案面板（自動列出個人名下所有角色）")
async def view_char_cmd(interaction: discord.Interaction):
    g_id = interaction.guild_id
    u_id = interaction.user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT name, is_npc, job, rank FROM characters 
            WHERE guild_id = ? AND user_id = ? AND is_npc IN (0, 2)
            ORDER BY is_npc ASC, created_at ASC
        """, (g_id, u_id)) as cur:
            my_characters = await cur.fetchall()

    if not my_characters:
        await interaction.response.send_message("❌ 你在此伺服器尚未建立任何角色！請先使用 `/檔案建立`。", ephemeral=True)
        return

    if len(my_characters) == 1:
        await render_character_card(interaction, my_characters[0][0], ephemeral=False)
        return

    class MyCharSelect(discord.ui.Select):
        def __init__(self):
            opts = [
                discord.SelectOption(
                    label=c[0],
                    description=f"[{'自設NPC' if c[1] == 2 else '角色'}] {c[2]} ｜ 地位: 【{c[3]}】",
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


# -------------------- 指令：/npc查看（官方NPC與大眾路人大廳） --------------------
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
            await interaction.response.send_message("📋 目前伺服器尚未生成任何【大眾路人】！可使用 `/路人管理` 生成。", ephemeral=True)
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

@bot.tree.command(name="npc查看", description="開啟 NPC 查閱大廳（按鈕切換官方 NPC 或大眾路人）")
async def view_npc_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="👥 NPC 檔案查閱大廳",
        description="請點選下方按鈕挑選官方人物或動態路人：",
        color=0x34495E
    )
    await interaction.response.send_message(embed=embed, view=NPCLobbySelectView(interaction.guild_id), ephemeral=True)
# -------------------- 指令：/檔案總覽（系統導航中心） --------------------
class MasterDirectoryView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id

    @discord.ui.button(label="📜 玩家指令", style=discord.ButtonStyle.primary, row=0)
    async def cmd_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        text = (
            "**👤 玩家常規指令列表：**\n"
            "• `/檔案建立`：建立玩家角色或玩家自設 NPC\n"
            "• `/查看`：調閱個人名下角色/自設NPC面板、成就、寵物與傳聞\n"
            "• `/npc查看`：開啟官方 NPC 或大眾路人查閱大廳\n"
            "• `/動作`：消耗行動點執行打工、上課、排練或應酬（體態、數值與人脈 1~5 點增長）\n"
            "• `/劇情觸發`：滿足門檻後，觸發官方 NPC 專屬劇情\n"
            "• `/社交關注`、`/社交拉黑`：社群動態互動（依後台開關生效）\n"
            "• `/背包`、`/使用`、`/贈予`：道具管理、身材飲食增減、餵食寵物與同鄉好感贈禮\n"
            "• `/商城`、`/售物`：購買商品/行動點、二手寄售（創作作品享才智溢價）\n"
            "• `/存錢`、`/取錢`、`/轉錢`：金融交易與角色互轉\n"
            "• `/任務`、`/回報任務`：查看公告看板、回報演藝任務（自動結算、陣營抽稅與晉升）\n"
            "• `/陣營`：查看所屬陣營、捐獻公款、購買全體加成或退出\n"
            "• `/寵物購買`、`/喪禮結算`：認養毛小孩與身後悼念結算"
        )
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="🛡️ 管理員指令", style=discord.ButtonStyle.danger, row=0)
    async def cmd_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        text = (
            "**👑 管理員整合控制指令：**\n"
            "• `/世界觀自訂`：置換全服面板詞彙與資歷階級\n"
            "• `/系統設定`：綁定通知頻道、管理社群關注拉黑開關\n"
            "• `/預約公告發獎`：排程指定日期自動發送金錢/道具/屬性並於頻道廣播\n"
            "• `/違規懲戒`：連動規章條款與存證網址發布告誡，重大違規執行封殺踢出\n"
            "• `/路人管理`：大量生成路人、轉正官方NPC、調整生態浮動與補給資源\n"
            "• `/商城總管`：上架/下架道具、飲食、車輛與房產資產\n"
            "• `/劇本設定`：錄入官方 NPC 專屬攻略劇情（自動發布至通知頻道）\n"
            "• `/審核通過`：人設單兩段式審核與初始金幣結算"
        )
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="🏷️ 標籤庫", style=discord.ButtonStyle.secondary, row=1)
    async def view_all_tags(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🏷️ 全體特色標籤一覽表", color=0xF39C12)
        embed.add_field(name="通用特質", value="、".join(UNIVERSAL_TAGS), inline=False)
        conflict_pairs = [f"{k} ⇄ {', '.join(v)}" for k, v in TAG_CONFLICTS.items()]
        embed.add_field(name="互斥衝突組", value="\n".join(conflict_pairs[:8]), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="檔案總覽", description="調閱全系統分類導航總目錄（指令、路人、玩家、標籤）")
async def master_overview_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📑 系統檔案與指令整合導航中心", description="請點選下方按鈕切換查閱各項名冊、指引與標籤規則：", color=0x2C3E50)
    await interaction.response.send_message(embed=embed, view=MasterDirectoryView(interaction.guild_id), ephemeral=True)
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
        await db.commit()

# -------------------- 系統就緒啟動與定時排程掛載 --------------------
@bot.event
async def on_ready():
    await init_db()
    await extend_database_tables()

    # 啟動背景定時任務
    if not daily_interest.is_running(): daily_interest.start()
    if not monthly_age_up.is_running(): monthly_age_up.start()
    if not check_ticket_expiration.is_running(): check_ticket_expiration.start()
    if not daily_pet_routine.is_running(): daily_pet_routine.start()
    if not crowd_npc_fluctuation_task.is_running(): crowd_npc_fluctuation_task.start()
    if not weekly_fans_and_haters_settlement.is_running(): weekly_fans_and_haters_settlement.start()
    if not yearly_action_points_reset.is_running(): yearly_action_points_reset.start()
    if not check_scheduled_broadcasts_task.is_running(): check_scheduled_broadcasts_task.start()

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
