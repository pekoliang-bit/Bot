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

# -------------------- 輕量假網頁（防 Render 斷線） --------------------
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is alive and running!"

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

# -------------------- 資料庫初始化 --------------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. 角色表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                guild_id INTEGER,
                user_id INTEGER,
                name TEXT,
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
                PRIMARY KEY (guild_id, name)
            )
        """)
        # 2. 背包與二手
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
        # 3. 官方/二手商店
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                shop_name TEXT,
                name TEXT,
                price INTEGER,
                description TEXT,
                stat_bonus TEXT,
                affinity_bonus INTEGER DEFAULT 0,
                usable INTEGER DEFAULT 1,
                target_role_id INTEGER DEFAULT 0,
                seller TEXT DEFAULT '官方',
                asset_type TEXT DEFAULT '一般',
                faction_name TEXT DEFAULT ''
            )
        """)
        # 4. 交際傾向關係表
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
        # 5. 系統設定
        await db.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                guild_id INTEGER,
                key TEXT,
                value TEXT,
                PRIMARY KEY (guild_id, key)
            )
        """)
        # 6. 審核兩段式紀錄表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                guild_id INTEGER,
                message_link TEXT,
                char_name TEXT,
                audit_count INTEGER DEFAULT 1,
                PRIMARY KEY (guild_id, message_link)
            )
        """)
        # 7. 資產產權表（玩家已購買的車輛與房產）
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
        # 8. 可購資產總表（管理員上架供人挑選購買的車房清單）
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
        # 9. 公司體系表
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
        # 10. 陣營總表
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
        # 11. 陣營貢獻紀錄表
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
        # 12. 陣營作品抽成查核表
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quest_completions (
                guild_id INTEGER,
                char_name TEXT,
                quest_title TEXT,
                completed_at REAL,
                PRIMARY KEY (guild_id, char_name, quest_title)
            )
        """)
        # 14. 地位等級限制表
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
        # 15. 排行榜單表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leaderboards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                name TEXT,
                stat_key TEXT
            )
        """)
        # 16. 抽獎獎項資料表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lottery_pools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                lottery_name TEXT,
                allowed_role_id INTEGER DEFAULT 0,
                item_name TEXT,
                initial_count INTEGER DEFAULT 1,
                remaining_count INTEGER DEFAULT 1,
                can_repeat INTEGER DEFAULT 1
            )
        """)
        # 17. 門票時效
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
    one_month = 30 * 86400
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT guild_id, name, age, created_at FROM characters") as cur:
            rows = await cur.fetchall()
            for g_id, name, age, created_at in rows:
                months_passed = int((now - created_at) // one_month)
                if months_passed > 0:
                    await db.execute(
                        "UPDATE characters SET age = age + 1, created_at = created_at + ? WHERE guild_id = ? AND name = ?",
                        (one_month, g_id, name)
                    )
        await db.commit()

# -------------------- 陣營作品自動扣稅核心函式 --------------------
async def process_faction_tax(guild_id: int, char_name: str, work_title: str, gross_reward: int, channel=None):
    if gross_reward <= 0:
        return ""

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM work_tax_logs WHERE guild_id = ? AND char_name = ? AND work_title = ?",
            (guild_id, char_name, work_title)
        ) as cur:
            if await cur.fetchone():
                return ""

        async with db.execute("SELECT faction FROM characters WHERE guild_id = ? AND name = ?", (guild_id, char_name)) as cur:
            c_row = await cur.fetchone()
            if not c_row or c_row[0] in ["無", "官方勢力", ""]:
                return ""
            faction_name = c_row[0]

        async with db.execute("SELECT tax_rate FROM factions WHERE guild_id = ? AND name = ?", (guild_id, faction_name)) as cur:
            f_row = await cur.fetchone()
            if not f_row:
                return ""
            tax_rate = f_row[0]

        tax_amount = int(gross_reward * tax_rate)
        if tax_amount <= 0:
            return ""

        await db.execute("UPDATE characters SET bank = bank - ? WHERE guild_id = ? AND name = ?", (tax_amount, guild_id, char_name))
        await db.execute("UPDATE factions SET treasury = treasury + ? WHERE guild_id = ? AND name = ?", (tax_amount, guild_id, faction_name))
        await db.execute("""
            INSERT INTO faction_members (guild_id, faction_name, char_name, contribution)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, faction_name, char_name) DO UPDATE SET contribution = contribution + ?
        """, (guild_id, faction_name, char_name, tax_amount, tax_amount))

        await db.execute(
            "INSERT INTO work_tax_logs (guild_id, char_name, work_title, tax_paid, paid_at) VALUES (?, ?, ?, ?, ?)",
            (guild_id, char_name, work_title, tax_amount, time.time())
        )
        await db.commit()

    return f"\n🏛️ **陣營抽成**：作品《{work_title}》收益已核發，陣營【{faction_name}】扣繳 {int(tax_rate*100)}% 稅款 **${tax_amount:,}** 注入公款！"

# -------------------- 地位晉升判定核心 --------------------
async def check_and_update_rank(guild_id: int, char_name: str, channel=None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT stats, works, rank, is_npc FROM characters WHERE guild_id = ? AND name = ?", (guild_id, char_name)) as cur:
            row = await cur.fetchone()
        if not row:
            return

        stats = json.loads(row[0]) if row[0] else {}
        works = json.loads(row[1]) if row[1] else []
        current_rank = row[2] or "未定級"
        is_npc_val = row[3]

        async with db.execute("SELECT rank_order, rank_name, work_req, endorse_req, stat_req, max_slots FROM rank_settings WHERE guild_id = ? ORDER BY rank_order ASC", (guild_id,)) as cur:
            ranks = await cur.fetchall()

        if not ranks:
            return

        for r_order, r_name, work_req, endorse_req, stat_req, max_slots in ranks:
            if max_slots > 0:
                async with db.execute("SELECT COUNT(*) FROM characters WHERE guild_id = ? AND rank = ?", (guild_id, r_name)) as c_cur:
                    c_cnt = (await c_cur.fetchone())[0]
                if c_cnt >= max_slots and current_rank != r_name:
                    continue

            stat_pass = True
            if stat_req:
                for req_part in re.split(r"[,，\s]+", stat_req.strip()):
                    m = re.search(r"([^\d]+)(\d+)", req_part)
                    if m:
                        s_name = m.group(1).strip()
                        s_val = int(m.group(2))
                        if stats.get(s_name, 0) < s_val:
                            stat_pass = False
                            break
            if not stat_pass:
                continue

            work_pass = True
            if work_req:
                for req_part in re.split(r"[,，\s]+", work_req.strip()):
                    m = re.search(r"([^\d]+)(\d+)", req_part)
                    if m:
                        tag = m.group(1).strip()
                        req_num = int(m.group(2))
                        matched_num = sum(1 for w in works if w.get("category") == "成就" and (tag in w.get("title", "") or tag in w.get("extra", "")))
                        if matched_num < req_num:
                            work_pass = False
                            break
            if not work_pass:
                continue

            endorse_pass = True
            if endorse_req:
                for req_part in re.split(r"[,，\s]+", endorse_req.strip()):
                    m = re.search(r"([^\d]+)(\d+)", req_part)
                    if m:
                        tag = m.group(1).strip()
                        req_num = int(m.group(2))
                        matched_num = sum(1 for w in works if w.get("category") == "榮譽" and (tag in w.get("title", "") or tag in w.get("extra", "")))
                        if matched_num < req_num:
                            endorse_pass = False
                            break
            if not endorse_pass:
                continue

            if current_rank != r_name:
                await db.execute("UPDATE characters SET rank = ? WHERE guild_id = ? AND name = ?", (r_name, guild_id, char_name))
                await db.commit()
                tag_label = "［NPC］" if is_npc_val > 0 else ""
                msg = f"🎉✨ **【地位晉升榮耀】** ✨🎉\n恭喜 {tag_label}**{char_name}** 實力大突破，正式晉升業界地位至：【**{r_name}**】！🏆"
                if channel:
                    try:
                        await channel.send(msg)
                    except Exception:
                        pass
            break

async def get_next_rank_info(guild_id: int, current_rank: str, stats: dict, works: list) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT rank_order, rank_name, work_req, endorse_req, stat_req, max_slots FROM rank_settings WHERE guild_id = ? ORDER BY rank_order ASC", (guild_id,)) as cur:
            ranks = await cur.fetchall()

    if not ranks:
        return "尚未設定任何地位升級限制。"

    curr_order = 999
    for r in ranks:
        if r[1] == current_rank:
            curr_order = r[0]
            break

    target_rank = None
    for r in reversed(ranks):
        if r[0] < curr_order:
            target_rank = r
            break

    if not target_rank:
        return "👑 已達到本城最高地位等級！"

    r_order, r_name, work_req, endorse_req, stat_req, max_slots = target_rank
    reqs = []
    if work_req: reqs.append(f"成就需求：{work_req}")
    if endorse_req: reqs.append(f"榮譽需求：{endorse_req}")
    if stat_req: reqs.append(f"數值需求：{stat_req}")
    if max_slots > 0: reqs.append(f"席位名額：全服限量 {max_slots} 人")

    return f"【下一目標：{r_name}】\n• " + "\n• ".join(reqs)

# -------------------- 字數統計輔助 --------------------
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

# -------------------- 訊息監聽：@機器人 自動字數結算 --------------------
@bot.event
async def on_message(message: discord.Message):
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

        reply_msg = (
            f"字數：{word_count} 字\n"
            f"共計金錢：{total_money:,} {unit}"
        )
        await message.reply(reply_msg, mention_author=True)

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
    貨幣單位="自訂金錢單位（例如：元、銀子、銅錢、流光幣，預設為元）",
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
# -------------------- 指令：抽獎系統 --------------------
@bot.tree.command(name="新增抽獎", description="【管理員專用】在伺服器發布全新的獎項抽獎池")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    獎項="抽獎池名稱（玩家必須在同名的討論串/帖子中抽獎）",
    獎品內容="抽中時獲得的道具或獎品名稱",
    數量="獎品數量 (純整數)",
    獎品可否重複="若為 False，每次抽中庫存自動 -1，抽完即止",
    可抽獎的身分組="限制特定身分組可抽，留空則全服成員無限制"
)
async def add_lottery(
    interaction: discord.Interaction,
    獎項: str,
    獎品內容: str,
    數量: int,
    獎品可否重複: bool,
    可抽獎的身分組: discord.Role = None
):
    g_id = interaction.guild_id
    if 數量 <= 0:
        await interaction.response.send_message("❌ 獎品數量必須大於 0！", ephemeral=True)
        return

    can_rep = 1 if 獎品可否重複 else 0
    role_id = 可抽獎的身分組.id if 可抽獎的身分組 else 0

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO lottery_pools (guild_id, lottery_name, allowed_role_id, item_name, initial_count, remaining_count, can_repeat)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (g_id, 獎項.strip(), role_id, 獎品內容.strip(), 數量, 數量, can_rep))
        await db.commit()

    role_str = 可抽獎的身分組.mention if 可抽獎的身分組 else "全體無限制"
    rep_str = "是（無限抽）" if 獎品可否重複 else "否（抽完自動扣減）"

    embed = discord.Embed(title="🎉 新增抽獎獎項發布成功", color=0xE74C3C)
    embed.add_field(name="獎項名稱", value=f"**{獎項.strip()}**", inline=False)
    embed.add_field(name="獎品內容", value=f"{獎品內容.strip()} × {數量}", inline=True)
    embed.add_field(name="抽獎資格", value=role_str, inline=True)
    embed.add_field(name="可否重複", value=rep_str, inline=True)
    embed.set_footer(text=f"提示：請至同名討論串【{獎項.strip()}】中輸入 /我要抽獎")
    await interaction.response.send_message(embed=embed)

class LotteryViewDropdown(discord.ui.Select):
    def __init__(self, pools):
        options = [
            discord.SelectOption(
                label=p[0],
                description=f"獎品: {p[2]} ｜ 剩餘: {p[4]}/{p[3]}",
                emoji="🎁"
            ) for p in pools[:25]
        ]
        super().__init__(placeholder="點選查看特定獎項的詳細庫存與條件...", options=options)
        self.pools = pools

    async def callback(self, interaction: discord.Interaction):
        selected_name = self.values[0]
        for p in self.pools:
            if p[0] == selected_name:
                role_str = f"<@&{p[1]}>" if p[1] > 0 else "無限制"
                rep_str = "可重複" if p[5] == 1 else "不可重複 (抽完截止)"
                embed = discord.Embed(title=f"🎁 抽獎詳情：【{p[0]}】", color=0xF39C12)
                embed.add_field(name="包含獎品", value=f"**{p[2]}**", inline=False)
                embed.add_field(name="目前庫存情況", value=f"剩餘 **{p[4]}** 件 / 初始共 {p[3]} 件", inline=True)
                embed.add_field(name="身分組限制", value=role_str, inline=True)
                embed.add_field(name="重複性質", value=rep_str, inline=True)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

@bot.tree.command(name="查看獎項", description="查看本伺服器目前所有發布中的抽獎活動與剩餘數量")
async def view_lottery(interaction: discord.Interaction):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT lottery_name, allowed_role_id, item_name, initial_count, remaining_count, can_repeat FROM lottery_pools WHERE guild_id = ?", (g_id,)) as cur:
            pools = await cur.fetchall()

    if not pools:
        await interaction.response.send_message("📋 目前本伺服器尚未舉辦任何抽獎活動！", ephemeral=True)
        return

    embed = discord.Embed(title="🎊 抽獎活動一覽", description="請由下方選單點選各獎項查閱詳細規則與庫存：", color=0xF1C40F)
    for p in pools[:10]:
        r_info = f"<@&{p[1]}>" if p[1] > 0 else "全員可抽"
        status = f"剩餘 {p[4]} 件" if (p[5] == 0) else "名額不限"
        embed.add_field(name=f"🎯 {p[0]}", value=f"獎品：{p[2]}\n資格：{r_info} ｜ {status}", inline=False)

    view = discord.ui.View()
    view.add_item(LotteryViewDropdown(pools))
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="我要抽獎", description="在對應獎項的討論串中進行抽獎（討論串名需與獎項名相同）")
async def play_lottery(interaction: discord.Interaction):
    g_id = interaction.guild_id
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message("❌ **【我要抽獎】只能在專屬的獎項討論串內使用！**", ephemeral=True)
        return

    thread_name = interaction.channel.name.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, lottery_name, allowed_role_id, item_name, remaining_count, can_repeat FROM lottery_pools WHERE guild_id = ? AND lottery_name = ?",
            (g_id, thread_name)
        ) as cur:
            pool = await cur.fetchone()

        if not pool:
            await interaction.response.send_message(f"❌ 查無與當前討論串【**{thread_name}**】同名的抽獎活動！", ephemeral=True)
            return

        pool_id, l_name, req_role, item_name, rem_count, can_rep = pool

        if req_role > 0:
            user_role_ids = [r.id for r in interaction.user.roles]
            if req_role not in user_role_ids:
                await interaction.response.send_message(f"🚫 資格不符！本獎項限定持有身分組 <@&{req_role}> 才能抽取。", ephemeral=True)
                return

        if can_rep == 0 and rem_count <= 0:
            await interaction.response.send_message(f"😢 很遺憾，【{l_name}】的所有獎品已經被全數抽完，活動已結束！", ephemeral=True)
            return

        if can_rep == 0:
            await db.execute("UPDATE lottery_pools SET remaining_count = remaining_count - 1 WHERE id = ?", (pool_id,))
            new_rem = rem_count - 1
        else:
            new_rem = rem_count

        await db.commit()

    rem_msg = f"（本獎品為不可重複限量品，全場尚餘 **{new_rem}** 件！）" if can_rep == 0 else ""
    await interaction.response.send_message(f"🎰✨ **【幸運開獎】** ✨🎰\n恭喜 {interaction.user.mention} 成功在【{l_name}】抽中了：\n🎁 **{item_name}**！{rem_msg}")

# -------------------- 指令：/檔案建立 & /官方npc登記 --------------------
@bot.tree.command(name="檔案建立", description="建立玩家個人藝人角色或個人NPC檔案")
@app_commands.choices(類別=[
    app_commands.Choice(name="玩家角色", value="0"),
    app_commands.Choice(name="玩家NPC", value="2")
])
@app_commands.describe(
    名字="角色全名",
    年齡="純數字",
    性別="性別",
    職業身分="職業或目前身分",
    標籤="個人特質標籤 (例如: 實力派, 厭世臉)",
    感情狀況="選填 (例如: 單身, 隱婚, 熱戀中)"
)
async def create_profile(
    interaction: discord.Interaction,
    類別: app_commands.Choice[str],
    名字: str,
    年齡: int,
    性別: str,
    職業身分: str,
    標籤: str,
    感情狀況: str = "單身"
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
            INSERT INTO characters (guild_id, user_id, name, age, gender, job, faction, tags, relationship_status, created_at, is_npc)
            VALUES (?, ?, ?, ?, ?, ?, '無', ?, ?, ?, ?)
        """, (g_id, interaction.user.id, target_name, 年齡, 性別, 職業身分, 標籤, 感情狀況, time.time(), is_npc_val))
        await db.commit()

    label = "玩家角色" if is_npc_val == 0 else "玩家自製 NPC"
    await interaction.response.send_message(f"🎉 【{label}】**{target_name}** 建立成功！\n• 標籤：`{標籤}` ｜ 感情狀態：`{感情狀況}`")

@bot.tree.command(name="官方npc登記", description="【管理員專用】登記官方全域 NPC 檔案")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    名字="NPC 姓名",
    年齡="年齡",
    性別="性別",
    職業身分="官方身分或職業",
    標籤="NPC 專屬標籤",
    感情狀況="選填 (預設未知)"
)
async def register_official_npc(
    interaction: discord.Interaction,
    名字: str,
    年齡: int,
    性別: str,
    職業身分: str,
    標籤: str,
    感情狀況: str = "未知"
):
    g_id = interaction.guild_id
    target_name = 名字.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO characters (guild_id, user_id, name, age, gender, job, faction, tags, relationship_status, created_at, is_npc)
            VALUES (?, 0, ?, ?, ?, ?, '官方勢力', ?, ?, ?, 1)
            ON CONFLICT(guild_id, name) DO UPDATE SET
                age = excluded.age, gender = excluded.gender, job = excluded.job, tags = excluded.tags, relationship_status = excluded.relationship_status
        """, (g_id, target_name, 年齡, 性別, 職業身分, 標籤, 感情狀況, time.time()))
        await db.commit()

    await interaction.response.send_message(f"👑 官方 NPC **{target_name}** 登記完畢！")

# -------------------- 指令：/檔案更新（含作品抽成觸發） --------------------
class ProfileUpdateStepView(discord.ui.View):
    def __init__(self, char_name: str, guild_id: int, is_admin: bool):
        super().__init__(timeout=180)
        self.char_name = char_name
        self.guild_id = guild_id
        self.is_admin = is_admin

    @discord.ui.button(label="📝 個資更新", style=discord.ButtonStyle.primary)
    async def update_base(self, interaction: discord.Interaction, button: discord.ui.Button):
        class BaseModal(discord.ui.Modal, title=f"更新【{self.char_name}】個人資料"):
            field_choice = discord.ui.TextInput(label="欲修改欄位 (職業/標籤/感情狀況/CP)", placeholder="例如: 感情狀況 或 CP")
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
                await inter.response.send_message(f"💞 已更新 **{self.char_name}** $\\rightarrow$ **{t_name}** 的交際傾向為【{t_val}】（狀態：{s_val}）！", ephemeral=True)

        await interaction.response.send_modal(RelationModal())

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

# -------------------- 指令：/審核通過（兩段式自動結算） --------------------
@bot.tree.command(name="審核通過", description="【管理員專用】審核人設帖：第一次出導引，第二次同單結算金錢，嚴禁第三次")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(文章連結="人設單文章訊息或討論串連結", 角色名="對應審核的角色名稱")
async def audit_pass_cmd(interaction: discord.Interaction, 文章連結: str, 角色名: str):
    g_id = interaction.guild_id
    link = 文章連結.strip()
    c_name = 角色名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT audit_count FROM audit_logs WHERE guild_id = ? AND message_link = ?", (g_id, link)) as cur:
            row = await cur.fetchone()

        if row:
            count = row[0]
            if count >= 2:
                await interaction.response.send_message("🚫 **該人設單已通過二次結算，不得重複執行第三次審核！**", ephemeral=True)
                return

            await interaction.response.defer()
            link_match = re.search(r"channels/\d+/(\d+)(?:/(\d+))?", link)
            post_content = ""
            if link_match:
                c_id = int(link_match.group(1))
                m_id = int(link_match.group(2)) if link_match.group(2) else None
                try:
                    ch = interaction.client.get_channel(c_id) or await interaction.client.fetch_channel(c_id)
                    if isinstance(ch, discord.Thread):
                        first_msg = None
                        async for msg in ch.history(limit=5, oldest_first=True):
                            first_msg = msg
                            break
                        post_content = first_msg.content if first_msg else ch.name
                    elif m_id:
                        msg = await ch.fetch_message(m_id)
                        post_content = msg.content
                except Exception:
                    pass

            def extract_val(pattern):
                m = re.search(pattern, post_content)
                return int(m.group(1)) if m else 0

            hot = extract_val(r"流量熱度[^\d]*(\d+)")
            comm = extract_val(r"商業價值[^\d]*(\d+)")
            passer = extract_val(r"路人緣[^\d]*(\d+)")
            pr = extract_val(r"公關[^\d]*(\d+)")
            infl = extract_val(r"影響指數[^\d]*(\d+)")
            face = extract_val(r"容貌[^\d]*(\d+)")
            iq = extract_val(r"才智[^\d]*(\d+)")
            art = extract_val(r"個人才藝[^\d]*(\d+)")

            tracks = sum([
                extract_val(r"唱跳[^\d]*(\d+)"),
                extract_val(r"演繹[^\d]*(\d+)"),
                extract_val(r"主持[^\d]*(\d+)"),
                extract_val(r"歌唱[^\d]*(\d+)"),
                extract_val(r"綜藝[^\d]*(\d+)")
            ])

            total_money = (
                hot * 80 +
                comm * 100 +
                passer * 30 +
                pr * 20 +
                infl * 50 +
                face * 40 +
                iq * 20 +
                tracks * 30 +
                art * 40
            )

            await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (total_money, g_id, c_name))
            await db.execute("UPDATE audit_logs SET audit_count = 2 WHERE guild_id = ? AND message_link = ?", (g_id, link))
            await db.commit()

            await interaction.followup.send(
                f"✅ **審核結算完成（第二次核定）**\n"
                f"🎉 已成功為角色【{c_name}】核發初始金幣 **${total_money:,}** 直入銀行戶頭！\n"
                f"（該單據已封存，無法再執行第三次結算）"
            )
        else:
            await db.execute("INSERT INTO audit_logs (guild_id, message_link, char_name, audit_count) VALUES (?, ?, ?, 1)", (g_id, link, c_name))
            await db.commit()

            embed = discord.Embed(title=f"📜 人設單初步審核通過：【{c_name}】", color=0x3498DB)
            embed.description = (
                f"恭喜通過初步審核！請依照下列步驟盡速完成建檔：\n\n"
                f"1️⃣ **建立檔案**：使用 `/檔案建立` 建立個人身分與標籤。\n"
                f"2️⃣ **登記數值 & 作品**：使用 `/數值登記` 貼上人設單自動解析數值，並用 `/檔案更新` 補充歷練。\n"
                f"3️⃣ **查看任務列表**：使用 `/任務` 查看全城看板，接取委託開啟生涯！\n\n"
                f"*管理員提示：二次使用本指令即可自動套算數值並發放初始金幣。*"
            )
            await interaction.response.send_message(embed=embed)

# -------------------- 指令：/資產系統更新（新增上架車房價格與功能維護） --------------------
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
    隱藏公司系統="僅在操作為【設定是否隱藏公司】時選擇"
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

# -------------------- 指令：/資產系統（選購車房、自動扣款、產權入庫） --------------------
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

            # 自動扣款優先順序：手頭現金扣除，現金不足由銀行存款補齊
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

            # 登記至個人產權表
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

    embed = discord.Embed(title=f"🏙️ 流光城資產與產權管理中心 — 操作人：【{c_name}】", description="請點選下方按鈕選購車輛、物業或進行公司設立：", color=0x34495E)
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
        btn_create_comp = discord.ui.Button(label="🏗️ 創建公司", style=discord.ButtonStyle.danger)

        async def create_comp_cb(inter: discord.Interaction):
            class CreateCompanyModal(discord.ui.Modal, title="創立全新公司/工作室"):
                comp_name = discord.ui.TextInput(label="公司名稱")
                purpose = discord.ui.TextInput(label="用途宗旨", placeholder="例如: 影視製作、藝人經紀")
                comp_type = discord.ui.TextInput(label="類型 (個人工作室/影業/經紀公司等)")
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
                            await m_inter.response.send_message(f"📩 多人股份有限公司【{c_comp_name}】申請已送出！", ephemeral=True)

            await inter.response.send_modal(CreateCompanyModal())

        btn_create_comp.callback = create_comp_cb
        view.add_item(discord.ui.Button(label="🏢 加入公司", style=discord.ButtonStyle.secondary))
        view.add_item(btn_create_comp)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
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
            await interaction.response.send_message("📋 目前本伺服器尚未建立任何榜單！", ephemeral=True)
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

# -------------------- 指令：管理員後台專區 --------------------
@bot.tree.command(name="檔案總覽", description="【管理員專用】檢視全伺服器所有角色與官方 NPC 總名冊與資產")
@app_commands.default_permissions(administrator=True)
async def admin_overview(interaction: discord.Interaction):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, rank, cash, bank, is_npc FROM characters WHERE guild_id = ?", (g_id,)) as cur:
            all_entities = await cur.fetchall()

    if not all_entities:
        await interaction.response.send_message("📋 本伺服器目前尚未建立任何角色或 NPC！", ephemeral=True)
        return

    class OverviewSelect(discord.ui.Select):
        def __init__(self):
            opts = [
                discord.SelectOption(
                    label=f"{'[NPC] ' if ent[4] > 0 else ''}{ent[0]}",
                    description=f"地位: {ent[1]} ｜ 現金: ${ent[2]:,} ｜ 銀行: ${ent[3]:,}",
                    emoji="🎭" if ent[4] > 0 else "👤",
                    value=ent[0]
                ) for ent in all_entities[:25]
            ]
            super().__init__(placeholder="點選調閱角色或 NPC 完整檔案...", options=opts)

        async def callback(self, inter: discord.Interaction):
            await view_char_cmd(inter, self.values[0])

    embed = discord.Embed(
        title="📑 全體名冊總覽 (管理員後台)",
        description=f"目前伺服器共計建檔：**{len(all_entities)}** 個角色與 NPC",
        color=0x34495E
    )
    view = discord.ui.View()
    view.add_item(OverviewSelect())
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
# -------------------- 指令：/陣營 與 /陣營管理 --------------------
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
    簡介: str = "流光城自治勢力",
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

@bot.tree.command(name="陣營排行", description="查看全伺服器各大陣營金庫與實力總積分排行榜")
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
# -------------------- 指令：管理員榜單、利息與獎勵調整 --------------------
@bot.tree.command(name="榜單管理", description="【管理員專用】新增或修改全城排行榜單公式")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="新增榜單", value="add"),
    app_commands.Choice(name="修改既有榜單", value="edit")
])
@app_commands.describe(操作="選擇新增或修改榜單", 榜單名字="榜單名稱", 相關數值="計算公式或屬性 (例如: 實力 * 1.5 + 聲望)")
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

@bot.tree.command(name="利息調整", description="【管理員專用】每 168 小時調整一次銀行利率")
@app_commands.default_permissions(administrator=True)
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

    await interaction.response.send_message(f"📈 本伺服器銀行利率已調整為 **{利率百分比}%**！")

@bot.tree.command(name="獎勵登記", description="【管理員專用】下發綜合獎勵（金錢入銀行、物品入背包、數值加總）")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    名字="角色或 NPC 名稱",
    金錢="匯入銀行的金額 (可填 0)",
    物品名稱="直接匯入背包的道具名 (選填)",
    物品數量="匯入背包的數量 (預設 1)",
    數值名稱="增加的數值項目 (例如: 實力、聲望)",
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

# -------------------- 清理與同步指令 --------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def clean_guild(ctx):
    bot.tree.clear_commands(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send("🧹 重複指令已清空！伺服器專屬副本已刪除，僅保留單一全域指令。")

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

# -------------------- 啟動與全域同步（含 Token 嚴格防呆） --------------------
@bot.event
async def on_ready():
    await init_db()
    if not daily_interest.is_running(): daily_interest.start()
    if not monthly_age_up.is_running(): monthly_age_up.start()
    if not check_ticket_expiration.is_running(): check_ticket_expiration.start()

    try:
        synced = await bot.tree.sync()
        print(f"====================================")
        print(f"🎉 成功同步了 {len(synced)} 個 Slash 指令！")
        for cmd in synced:
            print(f"📌 指令: /{cmd.name}")
        print(f"====================================")
    except Exception as e:
        print(f"❌ 指令同步失敗: {e}")

    print(f"流光城系統已就緒：{bot.user}")

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
