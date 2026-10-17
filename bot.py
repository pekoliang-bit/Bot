import os
import sys
import subprocess
import json
import time
import threading
import re
from datetime import datetime

# 自動安裝必要套件
try:
    import aiosqlite
    import flask
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
        # 1. 角色表 (含 rank 咖位欄位)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                guild_id INTEGER,
                user_id INTEGER,
                name TEXT,
                age INTEGER,
                gender TEXT,
                job TEXT,
                faction TEXT,
                cash INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                works TEXT DEFAULT '[]',
                created_at REAL,
                stats TEXT DEFAULT '{}',
                ticket_ban_until REAL DEFAULT 0,
                rank TEXT DEFAULT '未定級',
                PRIMARY KEY (guild_id, name)
            )
        """)
        # 2. 背包表
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
        # 3. 商店表
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
                seller TEXT DEFAULT '官方'
            )
        """)
        # 4. NPC 名冊表 (包含 cash, bank, rank 以支援完整金融與咖位)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS npcs (
                guild_id INTEGER,
                name TEXT,
                age INTEGER,
                gender TEXT,
                identity TEXT,
                avatar_url TEXT,
                stats TEXT DEFAULT '{}',
                cash INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                works TEXT DEFAULT '[]',
                rank TEXT DEFAULT '未定級',
                PRIMARY KEY (guild_id, name)
            )
        """)
        # 5. NPC 好感度表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS npc_affection (
                guild_id INTEGER,
                char_name TEXT,
                npc_name TEXT,
                affection INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, char_name, npc_name)
            )
        """)
        # 6. 系統參數表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                guild_id INTEGER,
                key TEXT,
                value TEXT,
                PRIMARY KEY (guild_id, key)
            )
        """)
        # 7. 任務總表 (含 tag_level 等級標籤 與 requirement 限制要求)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                category TEXT,
                title TEXT,
                reward_desc TEXT,
                reward_cash INTEGER DEFAULT 0,
                reward_items TEXT DEFAULT '[]',
                reward_stats TEXT DEFAULT '',
                time_limit TEXT DEFAULT '',
                report_channel_id INTEGER DEFAULT 0,
                tag_level TEXT DEFAULT '',
                requirement TEXT DEFAULT ''
            )
        """)
        # 8. 任務完成記錄表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quest_completions (
                guild_id INTEGER,
                char_name TEXT,
                quest_title TEXT,
                completed_at REAL,
                PRIMARY KEY (guild_id, char_name, quest_title)
            )
        """)
        # 9. 排行榜單表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leaderboards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                name TEXT,
                stat_key TEXT
            )
        """)
        # 10. 活躍門票時效追蹤表
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
        # 11. 咖位等級限制表 (順序數字越小地位越高)
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

        # 資料庫熱升級檢查
        tables_to_check = [
            ("characters", "guild_id INTEGER DEFAULT 0"),
            ("characters", "stats TEXT DEFAULT '{}'"),
            ("characters", "ticket_ban_until REAL DEFAULT 0"),
            ("characters", "rank TEXT DEFAULT '未定級'"),
            ("inventory", "guild_id INTEGER DEFAULT 0"),
            ("shop_items", "guild_id INTEGER DEFAULT 0"),
            ("shop_items", "target_role_id INTEGER DEFAULT 0"),
            ("npcs", "guild_id INTEGER DEFAULT 0"),
            ("npcs", "stats TEXT DEFAULT '{}'"),
            ("npcs", "cash INTEGER DEFAULT 0"),
            ("npcs", "bank INTEGER DEFAULT 0"),
            ("npcs", "works TEXT DEFAULT '[]'"),
            ("npcs", "rank TEXT DEFAULT '未定級'"),
            ("npc_affection", "guild_id INTEGER DEFAULT 0"),
            ("system_settings", "guild_id INTEGER DEFAULT 0"),
            ("quests", "guild_id INTEGER DEFAULT 0"),
            ("quests", "report_channel_id INTEGER DEFAULT 0"),
            ("quests", "tag_level TEXT DEFAULT ''"),
            ("quests", "requirement TEXT DEFAULT ''"),
            ("quest_completions", "guild_id INTEGER DEFAULT 0"),
            ("leaderboards", "guild_id INTEGER DEFAULT 0")
        ]
        for tbl, col_def in tables_to_check:
            try:
                await db.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_def}")
            except Exception:
                pass

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
            await db.execute(f"UPDATE npcs SET bank = CAST(bank * (1 + {rate}) AS INTEGER) WHERE guild_id = ? AND bank > 0", (g_id,))
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

# -------------------- 咖位晉升判定核心模組 --------------------
async def check_and_update_rank(guild_id: int, char_name: str, channel=None):
    """
    全自動檢查角色或 NPC 是否達到更高地位的限制要求。
    若達標且有名額，立即更新並發布升級提示。
    """
    async with aiosqlite.connect(DB_PATH) as db:
        is_npc = False
        async with db.execute("SELECT stats, works, rank FROM characters WHERE guild_id = ? AND name = ?", (guild_id, char_name)) as cur:
            row = await cur.fetchone()
        if not row:
            async with db.execute("SELECT stats, works, rank FROM npcs WHERE guild_id = ? AND name = ?", (guild_id, char_name)) as cur:
                row = await cur.fetchone()
                if row:
                    is_npc = True
        if not row:
            return

        stats = json.loads(row[0]) if row[0] else {}
        works = json.loads(row[1]) if row[1] else []
        current_rank = row[2] or "未定級"

        # 撈取該伺服器所有設定好的咖位限制（依順序由小到大排序：1最高、2次之...）
        async with db.execute("SELECT rank_order, rank_name, work_req, endorse_req, stat_req, max_slots FROM rank_settings WHERE guild_id = ? ORDER BY rank_order ASC", (guild_id,)) as cur:
            ranks = await cur.fetchall()

        if not ranks:
            return

        for r_order, r_name, work_req, endorse_req, stat_req, max_slots in ranks:
            # 1. 檢查名額限制 (max_slots > 0)
            if max_slots > 0:
                async with db.execute("SELECT COUNT(*) FROM characters WHERE guild_id = ? AND rank = ?", (guild_id, r_name)) as c_cur:
                    c_cnt = (await c_cur.fetchone())[0]
                async with db.execute("SELECT COUNT(*) FROM npcs WHERE guild_id = ? AND rank = ?", (guild_id, r_name)) as n_cur:
                    n_cnt = (await n_cur.fetchone())[0]
                if (c_cnt + n_cnt) >= max_slots and current_rank != r_name:
                    continue  # 名額已滿，檢查下一級

            # 2. 檢查數值限制 (例如：商業價值500, 流量熱度400)
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

            # 3. 檢查作品限制 (例如：電視劇2部, S+1部)
            work_pass = True
            if work_req:
                for req_part in re.split(r"[,，\s]+", work_req.strip()):
                    m = re.search(r"([^\d]+)(\d+)", req_part)
                    if m:
                        tag = m.group(1).strip()
                        req_num = int(m.group(2))
                        matched_num = sum(1 for w in works if tag in w.get("category", "") or tag in w.get("extra", "") or tag in w.get("title", ""))
                        if matched_num < req_num:
                            work_pass = False
                            break
            if not work_pass:
                continue

            # 4. 檢查榮譽限制 (例如：奢華2個, 高奢1個)
            endorse_pass = True
            if endorse_req:
                for req_part in re.split(r"[,，\s]+", endorse_req.strip()):
                    m = re.search(r"([^\d]+)(\d+)", req_part)
                    if m:
                        tag = m.group(1).strip()
                        req_num = int(m.group(2))
                        matched_num = sum(1 for w in works if w.get("category") in ["代言", "廣告"] and (tag in w.get("extra", "") or tag in w.get("title", "")))
                        if matched_num < req_num:
                            endorse_pass = False
                            break
            if not endorse_pass:
                continue

            # 條件全符合！判定是否達成晉級
            if current_rank != r_name:
                tbl = "npcs" if is_npc else "characters"
                await db.execute(f"UPDATE {tbl} SET rank = ? WHERE guild_id = ? AND name = ?", (r_name, guild_id, char_name))
                await db.commit()
                tag_label = "［官方 NPC］" if is_npc else ""
                msg = f"🎉✨ **【地位晉升榮耀】** ✨🎉\n恭喜 {tag_label}**{char_name}** 實力大突破，正式晉升至：【**{r_name}**】！🏆"
                if channel:
                    try:
                        await channel.send(msg)
                    except Exception:
                        pass
                print(f"[{datetime.now()}] {char_name} 升階至 {r_name}")
            break

# 輔助函式：取得下一階升級所需條件敘述
async def get_next_rank_info(guild_id: int, current_rank: str, stats: dict, works: list) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT rank_order, rank_name, work_req, endorse_req, stat_req, max_slots FROM rank_settings WHERE guild_id = ? ORDER BY rank_order ASC", (guild_id,)) as cur:
            ranks = await cur.fetchall()

    if not ranks:
        return "尚未設定任何升級限制。"

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
        return "👑 已達到最高身分等級！"

    r_order, r_name, work_req, endorse_req, stat_req, max_slots = target_rank
    reqs = []
    if work_req: reqs.append(f"成就需求：{work_req}")
    if endorse_req: reqs.append(f"榮譽需求：{endorse_req}")
    if stat_req: reqs.append(f"數值需求：{stat_req}")
    if max_slots > 0: reqs.append(f"席位名額：全服限量 {max_slots} 人")

    return f"【下一目標：{r_name}】\n• " + "\n• ".join(reqs)

# -------------------- 指令：/地位等級限制（管理員專用，增修雙模式） --------------------
@bot.tree.command(name="地位等級限制", description="【管理員專用】設定、新增或修改全服地位晉級標準")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作模式=[
    app_commands.Choice(name="增加（貼上文字/連結自動解析）", value="add"),
    app_commands.Choice(name="修改（手動微調特定順位標準）", value="edit"),
    app_commands.Choice(name="清單檢視（查看當前所有地位門檻）", value="list")
])
@app_commands.describe(
    操作模式="選擇增加、修改或查看地位規則",
    內容或連結="［增加模式］貼上包含順序、成就、榮譽、數值、人數的文字或帖子連結",
    順序="［修改模式］欲修改的咖位級別 (純數字，越小越高)",
    地位等級="［修改模式］地位名稱 (如: 頂流、超級大咖)",
    成就限制="［修改模式］對應成就數量 (如: 電視劇2, 電影1)",
    榮譽限制="［修改模式］榮譽標籤條件 (如: 奢華2, 高奢1)",
    數值限制="［修改模式］數值門檻 (如: 才智500, 容貌300)",
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
            await interaction.response.send_message("📋 本伺服器尚未建立任何地位限制等級！", ephemeral=True)
            return

        embed = discord.Embed(title="👑 地位限制規範一覽表", color=0xF1C40F)
        for r_order, r_name, w_req, e_req, s_req, slots in rows:
            slot_str = f"限量 {slots} 人" if slots > 0 else "名額不限"
            detail = f"• 成就限制：{w_req or '無'}\n• 榮譽限制：{e_req or '無'}\n• 數值限制：{s_req or '無'}\n• 席位限制：{slot_str}"
            embed.add_field(name=f"順序 {r_order} ｜ 【{r_name}】", value=detail, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if mode == "edit":
        if 順序 is None or not 咖位等級:
            await interaction.response.send_message("❌ 修改模式下，**【順序】與【咖位等級】為必填項目**！", ephemeral=True)
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
            """, (g_id, 順序, 咖位等級.strip(), 作品限制.strip(), 代言限制.strip(), 數值限制.strip(), 人數))
            await db.commit()

        await interaction.response.send_message(f"✅ 已成功更新順位 **{順序}** 之咖位【**{咖位等級}**】標準！", ephemeral=True)
        return

    if mode == "add":
        if not 內容或連結:
            await interaction.response.send_message("❌ 增加模式下，請於【內容或連結】欄位貼上包含限制的文字或文章連結！", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        raw_text = 內容或連結

        # 若提供的是 Discord 連結，自動抓取內容
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
        rank_name_match = re.search(r"(?:咖位|名稱|頭銜)[^\w]*([^\n\r,，]+)", raw_text)
        work_match = re.search(r"(?:作品限制|作品需求|影視)[^\n\r:]*[:：]?([^\n\r]+)", raw_text)
        endorse_match = re.search(r"(?:代言限制|代言需求|代言)[^\n\r:]*[:：]?([^\n\r]+)", raw_text)
        stat_match = re.search(r"(?:數值限制|數值需求|屬性)[^\n\r:]*[:：]?([^\n\r]+)", raw_text)
        slots_match = re.search(r"(?:人數|名額|席位)[^\d]*(\d+)", raw_text)

        parsed_order = int(order_match.group(1)) if order_match else 1
        parsed_name = rank_name_match.group(1).strip() if rank_name_match else "未命名咖位"
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
            f"🎉 成功錄入咖位標準！\n"
            f"• 順位：`#{parsed_order}`\n"
            f"• 咖位名稱：**【{parsed_name}】**\n"
            f"• 作品限制：`{parsed_work or '無'}`\n"
            f"• 代言限制：`{parsed_endorse or '無'}`\n"
            f"• 數值限制：`{parsed_stat or '無'}`\n"
            f"• 席位名額：`{parsed_slots if parsed_slots > 0 else '不限'}`"
        )

# -------------------- 指令：/檔案總覽（管理員專用，含角色與 NPC） --------------------
class OverviewSelect(discord.ui.Select):
    def __init__(self, entities: list, guild_id: int):
        self.guild_id = guild_id
        opts = [
            discord.SelectOption(
                label=f"{'[NPC] ' if ent[2] else ''}{ent[0]}",
                description=f"咖位: {ent[1]} ｜ 現金: ${ent[3]:,} ｜ 銀行: ${ent[4]:,}",
                emoji="🎭" if ent[2] else "👤",
                value=f"{'npc' if ent[2] else 'char'}:{ent[0]}"
            ) for ent in entities[:25]
        ]
        super().__init__(placeholder="點選調閱角色或官方 NPC 完整總覽...", options=opts)

    async def callback(self, interaction: discord.Interaction):
        kind, name = self.values[0].split(":", 1)
        async with aiosqlite.connect(DB_PATH) as db:
            if kind == "char":
                async with db.execute("SELECT age, gender, job, faction, cash, bank, works, stats, rank FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, name)) as cur:
                    d = await cur.fetchone()
                avatar = None
            else:
                async with db.execute("SELECT age, gender, identity, '官方勢力', cash, bank, works, stats, rank, avatar_url FROM npcs WHERE guild_id = ? AND name = ?", (self.guild_id, name)) as cur:
                    d = await cur.fetchone()
                avatar = d[9] if d else None

        if not d:
            await interaction.response.send_message("❌ 查無檔案！", ephemeral=True)
            return

        embed = discord.Embed(title=f"🪪 總覽調閱：{name} {'[官方 NPC]' if kind == 'npc' else ''}", color=0x9B59B6)
        embed.add_field(name="基本身份", value=f"• 年齡: {d[0]} 歲\n• 性別: {d[1]}\n• 身分/職業: {d[2]}\n• 勢力: {d[3]}", inline=True)
        embed.add_field(name="財務狀況", value=f"• 現金: ${d[4]:,}\n• 銀行存款: ${d[5]:,}\n• 當前咖位: **【{d[8] or '未定級'}】**", inline=True)

        stats = json.loads(d[7]) if d[7] else {}
        stat_str = " ｜ ".join([f"{k}: **{v:,}**" for k, v in stats.items()]) if stats else "尚未登記任何數值"
        embed.add_field(name="📊 能力數值", value=stat_str, inline=False)

        works = json.loads(d[6]) if d[6] else []
        work_str = "\n".join([f"• 【{w.get('category')}】《{w.get('title')}》({w.get('extra', '')})" for w in works[-5:]]) if works else "無作品或代言紀錄"
        embed.add_field(name="🎬 作品與代言 (最新5筆)", value=work_str, inline=False)

        if avatar:
            embed.set_thumbnail(url=avatar)

        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="檔案總覽", description="【管理員專用】檢視全伺服器所有角色與官方 NPC 總名冊與資產")
@app_commands.default_permissions(administrator=True)
async def admin_overview(interaction: discord.Interaction):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, rank, cash, bank FROM characters WHERE guild_id = ?", (g_id,)) as cur:
            chars = [(r[0], r[1] or "未定級", False, r[2], r[3]) for r in await cur.fetchall()]
        async with db.execute("SELECT name, rank, cash, bank FROM npcs WHERE guild_id = ?", (g_id,)) as cur:
            npcs = [(r[0], r[1] or "未定級", True, r[2], r[3]) for r in await cur.fetchall()]

    all_entities = chars + npcs
    if not all_entities:
        await interaction.response.send_message("📋 本伺服器目前尚未建立任何角色或 NPC！", ephemeral=True)
        return

    embed = discord.Embed(
        title="📑 流光城全體名冊總覽 (管理員後台)",
        description=f"目前共計：**{len(chars)}** 位藝人角色 ｜ **{len(npcs)}** 位官方 NPC\n請由下方選單點選查看個別檔案：",
        color=0x34495E
    )
    view = discord.ui.View()
    view.add_item(OverviewSelect(all_entities, g_id))
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# -------------------- 指令：任務系統（含等級標籤、接取限制與增修雙模式） --------------------
@bot.tree.command(name="任務新增", description="【管理員專用】發布或修改任務（含等級標籤、回報區與接取限制）")
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
    獎勵說明="獎勵文字敘述 (例如：$ 5,000、容貌+10)",
    金錢獎勵="自動匯入銀行的金錢 (可填 0)",
    數值獎勵說明="獲得的數值 (例如: 容貌+10)",
    等級選填="【選填】任務等級/標籤（例如：奢華、高奢、S+、頂級）",
    限制條件="【選填】接取限制（例如：咖位限一線、性別限女、勢力限某派系、容貌>=200）",
    獎勵道具名="自動送入背包的道具名 (選填)",
    獎勵道具數量="自動送入背包的道具數量 (預設 1)",
    限時時間="僅限時任務需填寫，格式：YYYY/M/D HH:MM～YYYY/M/D HH:MM",
    回報頻道="【選填】限定回報的文字頻道/討論串/論壇，留空則全服任意頻道可回報"
)
async def add_quest_cmd(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    選擇欄位: app_commands.Choice[str],
    任務名: str,
    獎勵說明: str,
    金錢獎勵: int = 0,
    數值獎勵說明: str = "",
    等級選填: str = "",
    限制條件: str = "",
    獎勵道具名: str = None,
    獎勵道具數量: int = 1,
    限時時間: str = None,
    回報頻道: discord.abc.GuildChannel = None
):
    g_id = interaction.guild_id
    category = 選擇欄位.value
    time_limit_str = ""

    if category == "限時任務":
        if not 限時時間:
            await interaction.response.send_message("❌ 欄位為【限時任務】時，必須填寫【限時時間】！", ephemeral=True)
            return
        time_limit_str = 限時時間.strip()

    items = []
    if 獎勵道具名:
        items.append({"name": 獎勵道具名.strip(), "amount": 獎勵道具數量})

    rep_ch_id = 回報頻道.id if 回報頻道 else 0

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM quests WHERE guild_id = ? AND title = ?", (g_id, 任務名.strip())) as cur:
            exists = await cur.fetchone()

        if 操作.value == "add":
            if exists:
                await interaction.response.send_message(f"❌ 任務名稱 `{任務名}` 已經存在！若要修改請在【操作】選擇「修改既有任務」。", ephemeral=True)
                return
            await db.execute("""
                INSERT INTO quests (guild_id, category, title, reward_desc, reward_cash, reward_items, reward_stats, time_limit, report_channel_id, tag_level, requirement)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (g_id, category, 任務名.strip(), 獎勵說明.strip(), 金錢獎勵, json.dumps(items, ensure_ascii=False), 數值獎勵說明.strip(), time_limit_str, rep_ch_id, 等級選填.strip(), 限制條件.strip()))
            op_label = "新增"
        else:
            if not exists:
                await interaction.response.send_message(f"❌ 找不到欲修改的任務 `{任務名}`！", ephemeral=True)
                return
            await db.execute("""
                UPDATE quests SET category = ?, reward_desc = ?, reward_cash = ?, reward_items = ?, reward_stats = ?, time_limit = ?, report_channel_id = ?, tag_level = ?, requirement = ?
                WHERE guild_id = ? AND title = ?
            """, (category, 獎勵說明.strip(), 金錢獎勵, json.dumps(items, ensure_ascii=False), 數值獎勵說明.strip(), time_limit_str, rep_ch_id, 等級選填.strip(), 限制條件.strip(), g_id, 任務名.strip()))
            op_label = "修改"

        await db.commit()

    ch_desc = f"\n📍 限定回報區：{回報頻道.mention}" if 回報頻道 else "\n📍 限定回報區：全伺服器皆可"
    tag_desc = f"\n🏷️ 任務標籤等級：【{等級選填}】" if 等級選填 else ""
    req_desc = f"\n🚫 接取限制門檻：【{限制條件}】" if 限制條件 else ""
    await interaction.response.send_message(f"✅ 成功{op_label}任務！\n📌 分類：【{category}】\n🏷️ 任務名：**{任務名}**\n🎁 獎勵：{獎勵說明}{tag_desc}{req_desc}{ch_desc}")

@bot.tree.command(name="回報任務", description="回報已完成的任務文章連結，領取對應獎勵（自動審核限制與累積咖位作品）")
@app_commands.describe(角色名="回報任務的角色名稱", 文章連結="你所發表文章的帖子/討論串或訊息連結")
async def report_quest(interaction: discord.Interaction, 角色名: str, 文章連結: str):
    g_id = interaction.guild_id
    await interaction.response.defer(ephemeral=False)

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. 驗證角色權限與基本檔案
        async with db.execute("SELECT user_id, gender, faction, stats, rank, works FROM characters WHERE guild_id = ? AND name = ?", (g_id, 角色名)) as cur:
            row = await cur.fetchone()
            if not row:
                await interaction.followup.send(f"❌ 查無角色 `{角色名}`！", ephemeral=True)
                return
            u_id, gender, faction, stats_json, rank_name, works_json = row
            if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ 你只能為自己持有的角色回報任務！", ephemeral=True)
                return

    # 2. 解析文章標題與內容
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
        async with db.execute("SELECT title, reward_desc, reward_cash, reward_items, reward_stats, time_limit, report_channel_id, tag_level, requirement FROM quests WHERE guild_id = ?", (g_id,)) as cur:
            all_quests = await cur.fetchall()

        matched_quest = None
        for q in all_quests:
            if q[0] in target_title:
                matched_quest = q
                break

        if not matched_quest:
            await interaction.followup.send(f"❌ 驗證失敗：無法在提供的文章（標題/內容：`{target_title[:30]}`）中匹配到正確的任務名稱！", ephemeral=True)
            return

        q_title, r_desc, r_cash, r_items_json, r_stats, time_limit, req_channel_id, tag_level, requirement = matched_quest

        # 3. 檢查專屬頻道限制
        if req_channel_id and req_channel_id > 0:
            current_ch = interaction.channel
            is_correct = (current_ch.id == req_channel_id) or (hasattr(current_ch, "parent_id") and current_ch.parent_id == req_channel_id)
            if not is_correct:
                await interaction.followup.send(f"❌ 此任務限定在指定的專屬回報區操作！請前往：<#{req_channel_id}>", ephemeral=True)
                return

        # 4. 檢查接取限制 (咖位/性別/勢力/數值)
        char_stats = json.loads(stats_json) if stats_json else {}
        if requirement:
            if "咖位" in requirement and rank_name not in requirement:
                await interaction.followup.send(f"❌ 資格不符：此任務要求【{requirement}】，你當前咖位為【{rank_name}】！", ephemeral=True)
                return
            if "性別" in requirement and gender not in requirement:
                await interaction.followup.send(f"❌ 資格不符：此任務限制性別！", ephemeral=True)
                return
            if "勢力" in requirement and faction not in requirement:
                await interaction.followup.send(f"❌ 資格不符：此任務限制指定勢力參與！", ephemeral=True)
                return

        # 5. 檢查重複與時限
        async with db.execute("SELECT 1 FROM quest_completions WHERE guild_id = ? AND char_name = ? AND quest_title = ?", (g_id, 角色名, q_title)) as cur:
            if await cur.fetchone():
                await interaction.followup.send(f"⚠️ 角色 **{角色名}** 已經完成過任務【{q_title}】，不可重複回報！", ephemeral=True)
                return

        # 6. 發放獎勵
        if r_cash > 0:
            await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (r_cash, g_id, 角色名))

        items = json.loads(r_items_json) if r_items_json else []
        for it in items:
            it_name, it_amt = it.get("name"), it.get("amount", 1)
            async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ? AND giver = '任務獎勵'", (g_id, 角色名, it_name)) as cur:
                inv_row = await cur.fetchone()
                if inv_row:
                    await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (it_amt, inv_row[0]))
                else:
                    await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, ?, '任務獎勵')", (g_id, 角色名, it_name, it_amt))

        # 自動將任務標籤計入代言/代表作品紀錄中，助攻咖位晉級
        works = json.loads(works_json) if works_json else []
        category_tag = "代言" if ("代言" in q_title or "廣告" in q_title or "奢華" in tag_level) else "影視任務"
        works.append({"category": category_tag, "title": q_title, "extra": tag_level})
        await db.execute("UPDATE characters SET works = ? WHERE guild_id = ? AND name = ?", (json.dumps(works, ensure_ascii=False), g_id, 角色名))

        await db.execute("INSERT INTO quest_completions (guild_id, char_name, quest_title, completed_at) VALUES (?, ?, ?, ?)", (g_id, 角色名, q_title, time.time()))
        await db.commit()

    # 7. 自動觸發咖位晉升檢測！
    await check_and_update_rank(g_id, 角色名, interaction.channel)

    stat_text = f"、+ 數值{r_stats}" if r_stats else ""
    tag_info = f"（獲得【{tag_level}】履歷資歷）" if tag_level else ""
    await interaction.followup.send(f"‼️任務確認完成\n獎勵：$ {r_cash:,}{stat_text} {tag_info}\n恭喜 {interaction.user.mention} 的【{角色名}】完成任務《{q_title}》！✅")

# -------------------- 金融與銀行（全面支援角色與 NPC） --------------------
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
        async with db.execute("SELECT cash FROM characters WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
            is_char = await cur.fetchone() is not None

        if is_char:
            await db.execute("UPDATE characters SET cash = cash + ? WHERE guild_id = ? AND name = ?", (金額, g_id, target_name))
        else:
            async with db.execute("SELECT cash FROM npcs WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
                is_npc = await cur.fetchone() is not None
            if is_npc:
                await db.execute("UPDATE npcs SET cash = cash + ? WHERE guild_id = ? AND name = ?", (金額, g_id, target_name))
            else:
                await interaction.response.send_message(f"❌ 查無名為 `{target_name}` 的角色或官方 NPC！", ephemeral=True)
                return

        await db.commit()

    await interaction.response.send_message(f"💵 薪水 **${金額:,}** 已成功發放並入帳至【**{target_name}**】的手頭現金！")

@bot.tree.command(name="轉錢", description="將手頭現金轉帳給其他角色或官方 NPC")
@app_commands.describe(轉出者="發起轉帳的名字 (你的角色或 NPC)", 接收者="收款人的名字 (角色或 NPC)", 金額="轉帳金額")
async def transfer(interaction: discord.Interaction, 轉出者: str, 接收者: str, 金額: int):
    g_id = interaction.guild_id
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額需大於 0！", ephemeral=True)
        return

    sender = 轉出者.strip()
    receiver = 接收者.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. 檢查轉出方
        async with db.execute("SELECT user_id, cash FROM characters WHERE guild_id = ? AND name = ?", (g_id, sender)) as cur:
            s_row = await cur.fetchone()

        s_is_npc = False
        if s_row:
            if s_row[0] != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 你只能操作自己持有的角色進行轉帳！", ephemeral=True)
                return
            s_cash = s_row[1]
        else:
            async with db.execute("SELECT cash FROM npcs WHERE guild_id = ? AND name = ?", (g_id, sender)) as cur:
                npc_row = await cur.fetchone()
            if npc_row and interaction.user.guild_permissions.administrator:
                s_is_npc = True
                s_cash = npc_row[0]
            else:
                await interaction.response.send_message("❌ 查無轉出對象，或權限不足無法操作 NPC 帳戶！", ephemeral=True)
                return

        if s_cash < 金額:
            await interaction.response.send_message(f"❌ 現金不足！目前手頭僅有 ${s_cash:,}。", ephemeral=True)
            return

        # 2. 檢查接收方
        async with db.execute("SELECT 1 FROM characters WHERE guild_id = ? AND name = ?", (g_id, receiver)) as cur:
            r_is_char = await cur.fetchone() is not None

        r_is_npc = False
        if not r_is_char:
            async with db.execute("SELECT 1 FROM npcs WHERE guild_id = ? AND name = ?", (g_id, receiver)) as cur:
                r_is_npc = await cur.fetchone() is not None

        if not r_is_char and not r_is_npc:
            await interaction.response.send_message(f"❌ 查無接收對象【{receiver}】！", ephemeral=True)
            return

        # 3. 執行扣款與入帳
        s_tbl = "npcs" if s_is_npc else "characters"
        r_tbl = "npcs" if r_is_npc else "characters"
        await db.execute(f"UPDATE {s_tbl} SET cash = cash - ? WHERE guild_id = ? AND name = ?", (金額, g_id, sender))
        await db.execute(f"UPDATE {r_tbl} SET cash = cash + ? WHERE guild_id = ? AND name = ?", (金額, g_id, receiver))
        await db.commit()

    await interaction.response.send_message(f"💸 **{sender}** 成功轉帳 **${金額:,}** 給 **{receiver}**！")

@bot.tree.command(name="存錢", description="將手頭現金存入銀行（支援角色與 NPC）")
async def deposit(interaction: discord.Interaction, 名字: str, 金額: int):
    g_id = interaction.guild_id
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額需大於 0！", ephemeral=True)
        return

    target = 名字.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, cash FROM characters WHERE guild_id = ? AND name = ?", (g_id, target)) as cur:
            row = await cur.fetchone()

        is_npc = False
        if row:
            if row[0] != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 你只能為自己的角色存錢！", ephemeral=True)
                return
            cash = row[1]
        else:
            async with db.execute("SELECT cash FROM npcs WHERE guild_id = ? AND name = ?", (g_id, target)) as cur:
                n_row = await cur.fetchone()
            if n_row and interaction.user.guild_permissions.administrator:
                is_npc = True
                cash = n_row[0]
            else:
                await interaction.response.send_message("❌ 查無對象或權限不足！", ephemeral=True)
                return

        if cash < 金額:
            await interaction.response.send_message(f"❌ 現金不足！目前僅有 ${cash:,}。", ephemeral=True)
            return

        tbl = "npcs" if is_npc else "characters"
        await db.execute(f"UPDATE {tbl} SET cash = cash - ?, bank = bank + ? WHERE guild_id = ? AND name = ?", (金額, 金額, g_id, target))
        await db.commit()

    await interaction.response.send_message(f"🏦 **{target}** 成功將 **${金額:,}** 存入銀行帳戶！")

@bot.tree.command(name="取錢", description="從銀行提取現金（支援角色與 NPC）")
async def withdraw(interaction: discord.Interaction, 名字: str, 金額: int):
    g_id = interaction.guild_id
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額需大於 0！", ephemeral=True)
        return

    target = 名字.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, target)) as cur:
            row = await cur.fetchone()

        is_npc = False
        if row:
            if row[0] != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 你只能為自己的角色提款！", ephemeral=True)
                return
            bank = row[1]
        else:
            async with db.execute("SELECT bank FROM npcs WHERE guild_id = ? AND name = ?", (g_id, target)) as cur:
                n_row = await cur.fetchone()
            if n_row and interaction.user.guild_permissions.administrator:
                is_npc = True
                bank = n_row[0]
            else:
                await interaction.response.send_message("❌ 查無對象或權限不足！", ephemeral=True)
                return

        if bank < 金額:
            await interaction.response.send_message(f"❌ 存款不足！當前存款僅有 ${bank:,}。", ephemeral=True)
            return

        tbl = "npcs" if is_npc else "characters"
        await db.execute(f"UPDATE {tbl} SET bank = bank - ?, cash = cash + ? WHERE guild_id = ? AND name = ?", (金額, 金額, g_id, target))
        await db.commit()

    await interaction.response.send_message(f"💵 **{target}** 成功從銀行提領 **${金額:,}** 現金！")

# -------------------- 個人檔案與 NPC 檔案（含當前咖位與下一階目標） --------------------
@bot.tree.command(name="查看", description="查看角色完整檔案、當前咖位、晉升需求與地圖簽證")
async def view_profile(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    target_name = 角色名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT age, gender, job, faction, cash, bank, works, stats, ticket_ban_until, rank FROM characters WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
            char = await cur.fetchone()

        if not char:
            await interaction.response.send_message(f"❌ 查無角色 **{target_name}**！", ephemeral=True)
            return

        age, gender, job, faction, cash, bank, works_json, stats_json, ban_until, rank_name = char

        async with db.execute("SELECT npc_name, affection FROM npc_affection WHERE guild_id = ? AND char_name = ?", (g_id, target_name)) as cur:
            aff_rows = await cur.fetchall()

        async with db.execute("SELECT ticket_name, expire_time FROM active_tickets WHERE guild_id = ? AND char_name = ?", (g_id, target_name)) as cur:
            ticket_row = await cur.fetchone()

    stats = json.loads(stats_json) if stats_json else {}
    works = json.loads(works_json) if works_json else []
    rank_name = rank_name or "未定級"

    embed = discord.Embed(title=f"🪪【{target_name}】個人藝人檔案", color=0xE67E22)
    embed.add_field(name="基本信息", value=f"• 年齡：{age} 歲\n• 性別：{gender}\n• 職業：{job}\n• 勢力：{faction}", inline=True)
    embed.add_field(name="資產狀況", value=f"• 手頭現金：${cash:,}\n• 銀行存款：${bank:,}", inline=True)

    # 咖位晉升情報
    next_rank_desc = await get_next_rank_info(g_id, rank_name, stats, works)
    embed.add_field(name=f"👑 當前業界咖位：【{rank_name}】", value=next_rank_desc, inline=False)

    now = time.time()
    if ticket_row:
        remain_hours = max(0, int((ticket_row[1] - now) / 3600))
        embed.add_field(name="🗺️ 當前地圖簽證", value=f"• 使用中門票：**{ticket_row[0]}**\n• 剩餘時限：約 **{remain_hours}** 小時（逾期強制遣返）", inline=False)
    elif ban_until and ban_until > now:
        ban_remain = int((ban_until - now) / 3600)
        embed.add_field(name="⚠️ 票務懲罰中", value=f"尚餘 **{ban_remain}** 小時禁止購票！", inline=False)

    if stats:
        stat_texts = [f"• {k}: **{v:,}**" for k, v in stats.items()]
        embed.add_field(name="📊 數值屬性", value=" ｜ ".join(stat_texts), inline=False)

    if works:
        work_texts = [f"• 【{w.get('category')}】《{w.get('title')}》({w.get('extra', '')})" for w in works[-5:]]
        embed.add_field(name="🎬 代表作品與代言 (最新5筆)", value="\n".join(work_texts), inline=False)

    if aff_rows:
        aff_texts = [f"• **{npc}**：💖 {aff}" for npc, aff in aff_rows]
        embed.add_field(name="NPC 羈絆好感度", value="\n".join(aff_texts), inline=False)

    await interaction.response.send_message(embed=embed)

async def render_npc_profile(interaction: discord.Interaction, npc_name: str, guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, age, gender, identity, avatar_url, stats, cash, bank, works, rank FROM npcs WHERE guild_id = ? AND name = ?", (guild_id, npc_name)) as cur:
            npc_info = await cur.fetchone()

        if not npc_info:
            await interaction.response.send_message(f"❌ 查無官方 NPC `{npc_name}`！", ephemeral=True)
            return

        name, age, gender, identity, avatar_url, stats_json, cash, bank, works_json, rank_name = npc_info
        async with db.execute(
            "SELECT char_name, affection FROM npc_affection WHERE guild_id = ? AND npc_name = ? AND affection > 0 ORDER BY affection DESC LIMIT 10",
            (guild_id, npc_name)
        ) as cur:
            favor_records = await cur.fetchall()

    stats = json.loads(stats_json) if stats_json else {}
    works = json.loads(works_json) if works_json else []
    rank_name = rank_name or "未定級"

    embed = discord.Embed(title=f"🎭 官方 NPC 檔案：{name}", color=0xE91E63)
    embed.add_field(name="基本資訊", value=f"• 年齡：{age} 歲\n• 性別：{gender}\n• 身分：{identity}", inline=True)
    embed.add_field(name="財務狀態", value=f"• 現金：${cash:,}\n• 存款：${bank:,}", inline=True)

    next_rank_desc = await get_next_rank_info(guild_id, rank_name, stats, works)
    embed.add_field(name=f"👑 當前咖位階級：【{rank_name}】", value=next_rank_desc, inline=False)

    if stats:
        stat_texts = [f"• {k}: **{v:,}**" for k, v in stats.items()]
        embed.add_field(name="📊 能力數值", value=" ｜ ".join(stat_texts), inline=False)

    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    if not favor_records:
        favor_desc = "目前尚無藝人與該 NPC 建立好感羈絆。"
    else:
        medals = ["🥇", "🥈", "🥉"]
        ranking_lines = [f"{medals[idx] if idx < 3 else f'`#{idx+1}`'} **{cname}** ｜ 💖 **{favor:,}** 點" for idx, (cname, favor) in enumerate(favor_records)]
        favor_desc = "\n".join(ranking_lines)

    embed.add_field(name="🏆 好感度羈絆排行 (TOP 10)", value=favor_desc, inline=False)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

# -------------------- 指令：管理員專用功能（支援修改選項 + Slash 自動隱藏） --------------------
@bot.tree.command(name="商店與物品管理", description="【管理員專用】新增或修改官方商城、票務門票商品")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="新增商品", value="add"),
    app_commands.Choice(name="修改既有商品", value="edit")
])
@app_commands.describe(
    操作="選擇新增或修改商品",
    商店="分類名稱（若是門票請填「票務系統」）",
    商品名="商品名稱",
    價格="販售單價",
    簡介="商品說明",
    增加數值="使用時獲得的效果提示 (如: 容貌+10)",
    增加好感="贈送增加的好感度點數",
    可否使用="是否可直接被使用",
    是否為門票="是否為大地圖門票",
    對應地圖身分組="若是門票，必須指定獲得的身分組"
)
async def manage_shop_item(
    interaction: discord.Interaction,
    操作: app_commands.Choice[str],
    商店: str,
    商品名: str,
    價格: int,
    簡介: str,
    增加數值: str,
    增加好感: int,
    可否使用: bool,
    是否為門票: bool = False,
    對應地圖身分組: discord.Role = None
):
    g_id = interaction.guild_id
    usable_val = 1 if 可否使用 else 0
    role_id = 0

    if 是否為門票:
        if not 對應地圖身分組:
            await interaction.response.send_message("❌ 門票必須指定【對應地圖身分組】！", ephemeral=True)
            return
        role_id = 對應地圖身分組.id
        if 商店 != "票務系統":
            商店 = "票務系統"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM shop_items WHERE guild_id = ? AND name = ?", (g_id, 商品名.strip())) as cur:
            exists = await cur.fetchone()

        if 操作.value == "add":
            if exists:
                await interaction.response.send_message(f"❌ 商品 `{商品名}` 已存在！若要調整請選「修改既有商品」。", ephemeral=True)
                return
            await db.execute("""
                INSERT INTO shop_items (guild_id, shop_name, name, price, description, stat_bonus, affinity_bonus, usable, target_role_id, seller)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '官方')
            """, (g_id, 商店, 商品名.strip(), 價格, 簡介, 增加數值, 增加好感, usable_val, role_id))
            op_str = "新增"
        else:
            if not exists:
                await interaction.response.send_message(f"❌ 查無欲修改的商品 `{商品名}`！", ephemeral=True)
                return
            await db.execute("""
                UPDATE shop_items SET shop_name = ?, price = ?, description = ?, stat_bonus = ?, affinity_bonus = ?, usable = ?, target_role_id = ?
                WHERE guild_id = ? AND name = ?
            """, (商店, 價格, 簡介, 增加數值, 增加好感, usable_val, role_id, g_id, 商品名.strip()))
            op_str = "修改"

        await db.commit()

    role_info = f"\n🗺️ 門票身分組：{對應地圖身分組.mention}" if role_id > 0 else ""
    await interaction.response.send_message(f"✅ 管理員已成功{op_str}商品：**{商品名}**（定價：${價格:,}）！{role_info}")

@bot.tree.command(name="npc登記與修改", description="【管理員專用】登記全新 NPC 或修改既有 NPC 設定")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="新增 NPC", value="add"),
    app_commands.Choice(name="修改既有 NPC", value="edit")
])
@app_commands.describe(操作="選擇新增或修改 NPC 資料", 名字="NPC 姓名", 年齡="年齡", 性別="性別", 身分="背景設定", 圖像連結="肖像圖片網址")
async def register_or_edit_npc(interaction: discord.Interaction, 操作: app_commands.Choice[str], 名字: str, 年齡: int, 性別: str, 身分: str, 圖像連結: str):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO npcs (guild_id, name, age, gender, identity, avatar_url, stats, cash, bank, works, rank)
            VALUES (?, ?, ?, ?, ?, ?, '{}', 0, 0, '[]', '未定級')
            ON CONFLICT(guild_id, name) DO UPDATE SET age = ?, gender = ?, identity = ?, avatar_url = ?
        """, (g_id, 名字.strip(), 年齡, 性別, 身分, 圖像連結, 年齡, 性別, 身分, 圖像連結))
        await db.commit()

    embed = discord.Embed(title=f"👤 NPC 資料更新/登記完成：{名字}", color=0x9B59B6)
    embed.add_field(name="基本信息", value=f"{年齡} 歲 / {性別} / {身分}", inline=False)
    embed.set_thumbnail(url=圖像連結)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="榜單管理", description="【管理員專用】新增或修改全城排行榜單公式")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="新增榜單", value="add"),
    app_commands.Choice(name="修改既有榜單", value="edit")
])
@app_commands.describe(操作="選擇新增或修改榜單", 榜單名字="榜單名稱", 相關數值="計算公式或屬性 (例如: 商業價值 * 1.5 + 影響指數)")
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
    數值名稱="增加的數值項目 (例如: 容貌、商業價值)",
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
    is_npc = False

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
            row = await cur.fetchone()

        if not row:
            async with db.execute("SELECT stats FROM npcs WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
                row = await cur.fetchone()
                if row:
                    is_npc = True

        if not row:
            await interaction.response.send_message(f"❌ 查無名為 `{target_name}` 的角色或 NPC！", ephemeral=True)
            return

        stats = json.loads(row[0]) if row[0] else {}
        reward_msgs = []

        tbl = "npcs" if is_npc else "characters"
        if 金錢 > 0:
            await db.execute(f"UPDATE {tbl} SET bank = bank + ? WHERE guild_id = ? AND name = ?", (金錢, g_id, target_name))
            reward_msgs.append(f"💰 銀行存款 +${金錢:,}")

        if 物品名稱 and not is_npc:
            async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ? AND giver = '管理員獎勵'", (g_id, target_name, 物品名稱)) as cur:
                inv_row = await cur.fetchone()
                if inv_row:
                    await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (物品數量, inv_row[0]))
                else:
                    await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, ?, '管理員獎勵')", (g_id, target_name, 物品名稱, 物品數量))
            reward_msgs.append(f"📦 物品 **{物品名稱}** ×{物品數量}")

        if 數值名稱 and 數值點數 != 0:
            stats[數值名稱] = stats.get(數值名稱, 0) + 數值點數
            await db.execute(f"UPDATE {tbl} SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(stats, ensure_ascii=False), g_id, target_name))
            reward_msgs.append(f"✨ 數值【{數值名稱}】+{數值點數} (總計: {stats[數值名稱]})")

        await db.commit()

    # 檢查是否觸發咖位晉升
    await check_and_update_rank(g_id, target_name, interaction.channel)

    detail = " ｜ ".join(reward_msgs) if reward_msgs else "無實質資產變動"
    await interaction.response.send_message(f"🎁 管理員已成功為【{target_name}】發放資源：\n{detail}")

# -------------------- 其他玩家常規指令 --------------------
@bot.tree.command(name="檔案建立", description="建立自己的藝人角色檔案")
async def create_profile(interaction: discord.Interaction, 名字: str, 年齡: int, 性別: str, 職業: str, 勢力: str):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND name = ?", (g_id, 名字.strip())) as cur:
            if await cur.fetchone():
                await interaction.response.send_message(f"❌ 角色名 **{名字}** 已存在！", ephemeral=True)
                return

        await db.execute("""
            INSERT INTO characters (guild_id, user_id, name, age, gender, job, faction, cash, bank, works, created_at, stats, ticket_ban_until, rank)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, '[]', ?, '{}', 0, '未定級')
        """, (g_id, interaction.user.id, 名字.strip(), 年齡, 性別, 職業, 勢力, time.time()))
        await db.commit()

    await interaction.response.send_message(f"🎉 角色 **{名字}** 檔案建立成功！初始咖位為【未定級】。")

# 算式核心
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
                    async with db.execute("SELECT name, stats, rank FROM characters WHERE guild_id = ?", (parent_guild,)) as cur:
                        player_chars = await cur.fetchall()
                    async with db.execute("SELECT name, stats, rank FROM npcs WHERE guild_id = ?", (parent_guild,)) as cur:
                        npc_chars = await cur.fetchall()

                ranked = []
                for name, s_json, r_name in player_chars:
                    st = json.loads(s_json) if s_json else {}
                    ranked.append((name, eval_stat_formula(formula, st), False, r_name))

                for name, s_json, r_name in npc_chars:
                    st = json.loads(s_json) if s_json else {}
                    ranked.append((name, eval_stat_formula(formula, st), True, r_name))

                ranked.sort(key=lambda x: x[1], reverse=True)

                embed = discord.Embed(title=f"🏆【{b_name}】全城實力排行 (含 NPC)", color=0xF1C40F)
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
            async with db.execute("SELECT name, stats FROM npcs WHERE guild_id = ?", (self.guild_id,)) as cur:
                all_npcs = await cur.fetchall()

        combined_names = {c[0] for c in all_chars} | {n[0] for n in all_npcs}
        if self.target_char not in combined_names:
            await interaction.response.send_message(f"❌ 查無名為 `{self.target_char}` 的角色或 NPC！", ephemeral=True)
            return

        embed = discord.Embed(title=f"📊【{self.target_char}】各榜單排行成績", color=0x3498DB)
        lines = []

        for b_name, formula in boards:
            ranked = []
            for name, s_json in all_chars:
                ranked.append((name, eval_stat_formula(formula, json.loads(s_json) if s_json else {})))
            for name, s_json in all_npcs:
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

@bot.tree.command(name="排行查詢", description="查詢各項名人榜單或查看個人/NPC 的各項榜單名次")
@app_commands.describe(名字="若要查看個人或 NPC 排名，請填寫對應名稱")
async def rank_query(interaction: discord.Interaction, 名字: str = None):
    view = LeaderboardView(target_char=名字, guild_id=interaction.guild_id)
    await interaction.response.send_message("🏆 請選擇你想查看的排行形式：", view=view, ephemeral=True)

@bot.tree.command(name="數值登記", description="為角色或官方 NPC 登記/調整數值，或貼上人設單連結自動解析")
@app_commands.describe(
    名字="欲變更數值的角色或 NPC 名稱",
    數值="欲變更的數值名稱（若貼人設單請填'自動'或留空）",
    數字="增減數值點數（例如 10 或 -5，人設單模式填 0）",
    人設單連結="貼上包含人設單內容的帖子/討論串或訊息連結"
)
async def register_stats_cmd(interaction: discord.Interaction, 名字: str, 數值: str = "自動", 數字: int = 0, 人設單連結: str = None):
    g_id = interaction.guild_id
    await interaction.response.defer(ephemeral=True)

    target_name = 名字.strip()
    is_npc = False
    stats_json = "{}"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
            row = await cur.fetchone()

        if row:
            u_id, stats_json = row
            if u_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ 你只能為自己持有的角色登記數值！", ephemeral=True)
                return
        else:
            async with db.execute("SELECT stats FROM npcs WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
                npc_row = await cur.fetchone()

            if npc_row:
                if not interaction.user.guild_permissions.administrator:
                    await interaction.followup.send("❌ 僅管理員可為官方 NPC 登記數值！", ephemeral=True)
                    return
                is_npc = True
                stats_json = npc_row[0] if npc_row[0] else "{}"
            else:
                await interaction.followup.send(f"❌ 查無 `{target_name}`！", ephemeral=True)
                return

        char_stats = json.loads(stats_json) if stats_json else {}

        if 人設單連結:
            link_match = re.search(r"channels/\d+/(\d+)(?:/(\d+))?", 人設單連結)
            if not link_match:
                await interaction.followup.send("❌ 人設單連結格式不正確！", ephemeral=True)
                return

            c_id = int(link_match.group(1))
            m_id = int(link_match.group(2)) if link_match.group(2) else None
            post_content = ""
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
            except Exception as e:
                await interaction.followup.send(f"❌ 無法讀取文章：`{e}`", ephemeral=True)
                return

            stat_patterns = [
                r"(流量熱度|商業價值|路人緣|公關力|公關|影響指數|容貌|才智|健康值|死忠粉絲數|活躍黑粉數)[^\d]*(\d+)",
                r"(唱跳|演繹|主持|歌唱|綜藝|個人才藝|技能|才藝)[^\d]*(\d+)"
            ]
            added_records = []
            for pattern in stat_patterns:
                for match_key, match_val in re.findall(pattern, post_content):
                    std_key = "公關" if match_key == "公關力" else match_key
                    char_stats[std_key] = int(match_val)
                    added_records.append(f"{std_key}:{match_val}")

            tbl = "npcs" if is_npc else "characters"
            await db.execute(f"UPDATE {tbl} SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(char_stats, ensure_ascii=False), g_id, target_name))
            await db.commit()

            await check_and_update_rank(g_id, target_name, interaction.channel)
            await interaction.followup.send(f"🎉 **{target_name}** 人設單數值已自動同步完畢！\n📊 錄入數值：{', '.join(added_records[:8])}")
            return

        if 數值 == "自動":
            await interaction.followup.send("❌ 請填寫欲增減的【數值名稱】或貼上【人設單連結】！", ephemeral=True)
            return

        char_stats[數值] = char_stats.get(數值, 0) + 數字
        tbl = "npcs" if is_npc else "characters"
        await db.execute(f"UPDATE {tbl} SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(char_stats, ensure_ascii=False), g_id, target_name))
        await db.commit()

    await check_and_update_rank(g_id, target_name, interaction.channel)
    sign = "+" if 數字 >= 0 else ""
    await interaction.followup.send(f"✅ 已為 **{target_name}** 更新數值！【{數值} {sign}{數字}】（當前值：{char_stats[數值]}）")

# -------------------- 商城與背包 --------------------
class BuyModal(discord.ui.Modal, title="購買商品確認"):
    def __init__(self, item_id: int, item_name: str, price: int, buyer: str, guild_id: int):
        super().__init__()
        self.item_id = item_id
        self.item_name = item_name
        self.price = price
        self.buyer = buyer
        self.guild_id = guild_id

    amount = discord.ui.TextInput(label="購買數量", default="1", min_length=1, max_length=4)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.amount.value)
            if qty <= 0: raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ 請輸入大於 0 的整數！", ephemeral=True)
            return

        total_cost = self.price * qty
        now = time.time()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT cash, ticket_ban_until FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.buyer)) as cur:
                user = await cur.fetchone()
                if not user or user[0] < total_cost:
                    await interaction.response.send_message(f"❌ 現金不足！需要 ${total_cost:,}，當前僅有 ${user[0] if user else 0:,}。", ephemeral=True)
                    return
                cash, ticket_ban_until = user

            async with db.execute("SELECT shop_name, target_role_id, seller FROM shop_items WHERE guild_id = ? AND id = ?", (self.guild_id, self.item_id)) as cur:
                s_item = await cur.fetchone()
                shop_name, target_role_id, seller = s_item

            if (shop_name == "票務系統" or (target_role_id and target_role_id > 0)):
                if ticket_ban_until and ticket_ban_until > now:
                    remain_hours = int((ticket_ban_until - now) / 3600)
                    await interaction.response.send_message(f"🚫 該角色因先前逾期未歸遭遣返，目前尚餘 **{remain_hours}** 小時禁止購票！", ephemeral=True)
                    return

            await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (total_cost, self.guild_id, self.buyer))
            if seller != '官方':
                await db.execute("UPDATE characters SET cash = cash + ? WHERE guild_id = ? AND name = ?", (total_cost, self.guild_id, seller))

            async with db.execute("SELECT id, amount FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (self.guild_id, self.buyer, self.item_name)) as cur:
                inv_row = await cur.fetchone()
                if inv_row:
                    await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (qty, inv_row[0]))
                else:
                    await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, ?, '系統商城')", (self.guild_id, self.buyer, self.item_name, qty))

            if seller != '官方':
                await db.execute("DELETE FROM shop_items WHERE guild_id = ? AND id = ?", (self.guild_id, self.item_id))

            await db.commit()

        await interaction.response.send_message(f"✅ 成功購買 **{self.item_name}** ×{qty}！共扣款 **${total_cost:,}**。")

class ShopSelectView(discord.ui.View):
    def __init__(self, char_name: str, shops: list, guild_id: int):
        super().__init__(timeout=120)
        self.char_name = char_name
        self.guild_id = guild_id
        for shop in shops:
            button = discord.ui.Button(label=shop, style=discord.ButtonStyle.success if shop == "票務系統" else discord.ButtonStyle.primary)
            button.callback = self.make_callback(shop)
            self.add_item(button)

    def make_callback(self, shop_name):
        async def callback(interaction: discord.Interaction):
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT id, name, price, description, stat_bonus, seller, target_role_id FROM shop_items WHERE guild_id = ? AND shop_name = ?", (self.guild_id, shop_name)) as cur:
                    items = await cur.fetchall()

            if not items:
                await interaction.response.send_message(f"🏪 **{shop_name}** 目前無任何商品。", ephemeral=True)
                return

            embed = discord.Embed(title=f"🏪 商城 — 【{shop_name}】", color=0x2ECC71 if shop_name == "票務系統" else 0xD4AF37)
            item_select_view = discord.ui.View(timeout=120)
            options = []
            for item in items[:25]:
                item_id, i_name, price, desc, stat, seller, role_id = item
                label_extra = f" (賣家: {seller})" if seller != '官方' else ""
                role_tag = " ｜ 🗺️ 包含地圖身分組" if role_id > 0 else ""
                embed.add_field(name=f"📦 {i_name} — ${price:,}{label_extra}{role_tag}", value=f"簡介: {desc}\n加成: {stat}", inline=False)
                options.append(discord.SelectOption(label=f"{i_name} (${price:,})", value=str(item_id), description=desc[:50]))

            select = discord.ui.Select(placeholder="選擇欲購買商品/門票...", options=options)
            async def select_callback(inter: discord.Interaction):
                selected_id = int(select.values[0])
                for it in items:
                    if it[0] == selected_id:
                        await inter.response.send_modal(BuyModal(selected_id, it[1], it[2], self.char_name, self.guild_id))
                        break

            select.callback = select_callback
            item_select_view.add_item(select)
            await interaction.response.send_message(embed=embed, view=item_select_view, ephemeral=True)

        return callback

@bot.tree.command(name="商城", description="進入商城選單購買商品或票券")
async def shop(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND name = ?", (g_id, 角色名)) as cur:
            if not await cur.fetchone():
                await interaction.response.send_message("❌ 查無此角色檔案！", ephemeral=True)
                return

        async with db.execute("SELECT DISTINCT shop_name FROM shop_items WHERE guild_id = ?", (g_id,)) as cur:
            shops = [row[0] for row in await cur.fetchall()]

    for default_s in ["票務系統", "二手"]:
        if default_s not in shops:
            shops.append(default_s)

    view = ShopSelectView(角色名, shops, g_id)
    await interaction.response.send_message(f"🏬 請選擇 **{角色名}** 想進入的專區：", view=view, ephemeral=True)

@bot.tree.command(name="背包", description="查看角色背包物品與來源")
async def inventory(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT item_name, amount, giver FROM inventory WHERE guild_id = ? AND owner_name = ?", (g_id, 角色名)) as cur:
            items = await cur.fetchall()

    if not items:
        await interaction.response.send_message(f"🎒 **{角色名}** 的背包目前沒有物品。", ephemeral=True)
        return

    embed = discord.Embed(title=f"🎒【{角色名}】的背包清單", color=0x3498DB)
    for name, amt, giver in items:
        embed.add_field(name=f"📦 {name} × {amt}", value=f"來源/贈予人: {giver}", inline=True)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="使用", description="使用背包中的道具；門票將派發身分組（限期 336 小時）")
async def use_item(interaction: discord.Interaction, 角色名: str, 物品名: str):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, amount FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, 角色名, 物品名)) as cur:
            inv = await cur.fetchone()
            if not inv or inv[1] <= 0:
                await interaction.response.send_message("❌ 背包中沒有該物品或數量不足！", ephemeral=True)
                return

        async with db.execute("SELECT usable, stat_bonus, target_role_id FROM shop_items WHERE guild_id = ? AND name = ?", (g_id, 物品名)) as cur:
            item_info = await cur.fetchone()
            if not item_info or item_info[0] == 0:
                await interaction.response.send_message(f"⚠️ **{物品名}** 為不可使用之物品！", ephemeral=True)
                return
            usable, bonus_str, target_role_id = item_info

        role_msg = ""
        now = time.time()
        if target_role_id and target_role_id > 0:
            role = interaction.guild.get_role(target_role_id)
            if role:
                try:
                    await interaction.user.add_roles(role, reason=f"使用門票【{物品名}】")
                    role_msg = f"\n🗺️ 已獲得大地圖身分組 **【{role.name}】**！"
                except Exception as e:
                    role_msg = f"\n⚠️ 身分組派發失敗：{e}"

            expire_at = now + (336 * 3600)
            await db.execute("""
                INSERT INTO active_tickets (guild_id, char_name, user_id, role_id, ticket_name, start_time, expire_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (g_id, 角色名, interaction.user.id, target_role_id, 物品名, now, expire_at))
            role_msg += f"\n⏰ **簽證停留時間：336 小時（兩週）**。請在到期前使用 `/返回原本地圖`，否則將強制遣返並**限制 300 小時不得購票**！"

        if inv[1] == 1:
            await db.execute("DELETE FROM inventory WHERE id = ?", (inv[0],))
        else:
            await db.execute("UPDATE inventory SET amount = amount - 1 WHERE id = ?", (inv[0],))

        stat_delta_msg = ""
        stat_match = re.search(r"([^\d+-]+)\s*([+-]?\d+)", bonus_str)
        if stat_match:
            stat_name = stat_match.group(1).strip()
            stat_val = int(stat_match.group(2))

            async with db.execute("SELECT stats FROM characters WHERE guild_id = ? AND name = ?", (g_id, 角色名)) as cur:
                char_row = await cur.fetchone()
                stats = json.loads(char_row[0]) if char_row and char_row[0] else {}

            stats[stat_name] = stats.get(stat_name, 0) + stat_val
            await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(stats, ensure_ascii=False), g_id, 角色名))
            stat_delta_msg = f"\n📊 **{stat_name}** 已自動更新至 **{stats[stat_name]}**！"

        await db.commit()

    await check_and_update_rank(g_id, 角色名, interaction.channel)
    await interaction.response.send_message(f"✨ **{角色名}** 使用了 **{物品名}**！獲得效果：【{bonus_str}】{stat_delta_msg}（剩餘: {inv[1] - 1}）{role_msg}")

@bot.tree.command(name="返回原本地圖", description="主動結束地圖旅行並收回身分組（免除遣返懲罰）")
async def return_home(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, role_id FROM active_tickets WHERE guild_id = ? AND char_name = ?", (g_id, 角色名)) as cur:
            ticket = await cur.fetchone()
            if not ticket:
                await interaction.response.send_message(f"ℹ️ 角色 **{角色名}** 目前並無啟用中的外地簽證或門票身分組！", ephemeral=True)
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

    await interaction.response.send_message(f"🏠 **{角色名}** 已順利返回原本地圖！已安全繳回門票身分組，無任何懲罰。")

@bot.tree.command(name="售物", description="將擁有物品放上［二手］商城販售")
async def sell_item(interaction: discord.Interaction, 角色名: str, 物品名: str, 價格: int):
    g_id = interaction.guild_id
    if 價格 <= 0:
        await interaction.response.send_message("❌ 販售價格必須大於 0！", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, amount FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, 角色名, 物品名)) as cur:
            inv = await cur.fetchone()
            if not inv or inv[1] <= 0:
                await interaction.response.send_message("❌ 背包中查無此物品！", ephemeral=True)
                return

        if inv[1] == 1:
            await db.execute("DELETE FROM inventory WHERE id = ?", (inv[0],))
        else:
            await db.execute("UPDATE inventory SET amount = amount - 1 WHERE id = ?", (inv[0],))

        await db.execute("""
            INSERT INTO shop_items (guild_id, shop_name, name, price, description, stat_bonus, affinity_bonus, usable, target_role_id, seller)
            VALUES (?, '二手', ?, ?, '玩家自售物品', '無加成', 0, 1, 0, ?)
        """, (g_id, 物品名, 價格, 角色名))
        await db.commit()

    await interaction.response.send_message(f"🏷️ 已將 **{物品名}** 上架至【二手】商城，定價為 **${價格:,}**！")

@bot.tree.command(name="贈予", description="贈送背包道具給其他角色或官方 NPC")
async def gift_item(interaction: discord.Interaction, 角色名: str, 對象名: str, 物品名: str, 數量: int):
    g_id = interaction.guild_id
    if 數量 <= 0:
        await interaction.response.send_message("❌ 數量需大於 0！", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, amount FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, 角色名, 物品名)) as cur:
            inv = await cur.fetchone()
            if not inv or inv[1] < 數量:
                await interaction.response.send_message("❌ 背包中該物品數量不足！", ephemeral=True)
                return

        async with db.execute("SELECT name FROM npcs WHERE guild_id = ? AND name = ?", (g_id, 對象名)) as cur:
            is_npc = await cur.fetchone() is not None

        if inv[1] == 數量:
            await db.execute("DELETE FROM inventory WHERE id = ?", (inv[0],))
        else:
            await db.execute("UPDATE inventory SET amount = amount - ? WHERE id = ?", (數量, inv[0]))

        extra_msg = ""
        if is_npc:
            async with db.execute("SELECT affinity_bonus FROM shop_items WHERE guild_id = ? AND name = ?", (g_id, 物品名)) as cur:
                item_row = await cur.fetchone()
                single_aff = item_row[0] if item_row else 10
            total_aff = single_aff * 數量

            await db.execute("""
                INSERT INTO npc_affection (guild_id, char_name, npc_name, affection)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, char_name, npc_name) DO UPDATE SET affection = affection + ?
            """, (g_id, 角色名, 對象名, total_aff, total_aff))
            extra_msg = f"\n💖 NPC **{對象名}** 對你的好感度增加了 **+{total_aff}**！"
        else:
            async with db.execute("SELECT id, amount FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ? AND giver = ?", (g_id, 對象名, 物品名, 角色名)) as cur:
                target_inv = await cur.fetchone()
                if target_inv:
                    await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (數量, target_inv[0]))
                else:
                    await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, ?, ?)", (g_id, 對象名, 物品名, 數量, 角色名))

        await db.commit()

    await interaction.response.send_message(f"🎁 **{角色名}** 贈送了 **{物品名}** ×{數量} 給 **{對象名}**！{extra_msg}")

@bot.tree.command(name="任務", description="查看角色當前完成與未完成的任務看板")
async def view_quests(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM characters WHERE guild_id = ? AND name = ?", (g_id, 角色名)) as cur:
            if not await cur.fetchone():
                await interaction.response.send_message(f"❌ 查無角色 `{角色名}`！", ephemeral=True)
                return

        async with db.execute("SELECT category, title, reward_desc, time_limit, report_channel_id, tag_level, requirement FROM quests WHERE guild_id = ? ORDER BY id ASC", (g_id,)) as cur:
            all_quests = await cur.fetchall()

        async with db.execute("SELECT quest_title FROM quest_completions WHERE guild_id = ? AND char_name = ?", (g_id, 角色名)) as cur:
            done_titles = {row[0] for row in await cur.fetchall()}

    if not all_quests:
        await interaction.response.send_message("📋 目前本伺服器尚未發布任何任務！", ephemeral=True)
        return

    categories = ["新手任務", "一般任務", "限時任務", "特殊任務"]
    embed = discord.Embed(title=f"📜【{角色名}】的任務清單看板", color=0xF1C40F)

    for cat in categories:
        cat_quests = [q for q in all_quests if q[0] == cat]
        if not cat_quests:
            embed.add_field(name=f"📌 {cat}欄", value="暫無任務", inline=False)
            continue

        lines = []
        for _, title, reward_desc, time_limit, r_ch_id, tag_level, requirement in cat_quests:
            status = "✅" if title in done_titles else "❌"
            limit_str = f" ⏳ `{time_limit}`" if time_limit else ""
            ch_str = f" 📍 <#{r_ch_id}>" if r_ch_id > 0 else ""
            tag_str = f" 🏷️ `[{tag_level}]`" if tag_level else ""
            req_str = f" 🚫 限`{requirement}`" if requirement else ""
            lines.append(f"• **{title}**{tag_str}{req_str}{limit_str}{ch_str}\n  └ 獎勵：{reward_desc} ［{status}］")

        embed.add_field(name=f"📌 {cat}欄", value="\n".join(lines), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

class NPCSelectDropdown(discord.ui.Select):
    def __init__(self, npcs, guild_id: int):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label=npc[0], description=f"{npc[1]}歲 ｜ {npc[2]} ｜ {npc[3][:20]}", emoji="👤")
            for npc in npcs[:25]
        ]
        super().__init__(placeholder="點此選擇欲查看檔案的官方 NPC...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await render_npc_profile(interaction, self.values[0], self.guild_id)

@bot.tree.command(name="npc查看", description="查看已登記的官方 NPC 名冊大廳或個別檔案")
@app_commands.describe(npc名稱="可選填：輸入特定 NPC 姓名，留空則開啟全選單")
async def view_npc_cmd(interaction: discord.Interaction, npc名稱: str = None):
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, age, gender, identity, avatar_url FROM npcs WHERE guild_id = ?", (g_id,)) as cur:
            all_npcs = await cur.fetchall()

    if not all_npcs:
        await interaction.response.send_message("📋 目前本伺服器尚未登記任何官方 NPC！", ephemeral=True)
        return

    if npc名稱:
        await render_npc_profile(interaction, npc名稱.strip(), g_id)
        return

    embed = discord.Embed(title="👥 流光城官方 NPC 名錄大廳", description="請點選下方選單調閱各 NPC 個人檔案：", color=0x9B59B6)
    for npc in all_npcs:
        embed.add_field(name=f"👤 {npc[0]} ({npc[1]}歲 / {npc[2]})", value=f"身分：{npc[3]}", inline=True)

    view = discord.ui.View(timeout=180)
    view.add_item(NPCSelectDropdown(all_npcs, g_id))
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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

# -------------------- 啟動與全域同步 --------------------
@bot.event
async def on_ready():
    await init_db()
    if not daily_interest.is_running():
        daily_interest.start()
    if not monthly_age_up.is_running():
        monthly_age_up.start()
    if not check_ticket_expiration.is_running():
        check_ticket_expiration.start()

    try:
        synced = await bot.tree.sync()
        print(f"====================================")
        print(f"🎉 成功同步了 {len(synced)} 個 Slash 指令！")
        for cmd in synced:
            print(f"📌 指令: /{cmd.name}")
        print(f"====================================")
    except Exception as e:
        print(f"❌ 同步指令失敗: {e}")

    print(f"流光城系統已就緒：{bot.user}")

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
