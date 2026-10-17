import os
import sys
import subprocess
import json
import time
import threading
import re
from datetime import datetime

# 自動安裝必要套件 (支援 PostgreSQL asyncpg)
try:
    import asyncpg
    import flask
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "asyncpg", "flask", "discord.py"])
    import asyncpg
    import flask

import discord
from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask

# -------------------- 輕量假網頁（防 Render 斷線） --------------------
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Showbiz Bot Cloud DB Service is Live!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# -------------------- 基礎設定與常數 --------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None

async def get_db_pool():
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL)
    return db_pool

# -------------------- 安全算式計算核心 --------------------
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

# -------------------- 資料庫初始化 --------------------
async def init_db():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # 1. 角色表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                guild_id BIGINT,
                user_id BIGINT,
                name TEXT,
                age INT,
                gender TEXT,
                job TEXT,
                faction TEXT,
                cash BIGINT DEFAULT 0,
                bank BIGINT DEFAULT 0,
                works TEXT DEFAULT '[]',
                created_at DOUBLE PRECISION,
                stats TEXT DEFAULT '{}',
                ticket_ban_until DOUBLE PRECISION DEFAULT 0,
                rank_order INT DEFAULT 99,
                rank_name TEXT DEFAULT '無名新人',
                PRIMARY KEY (guild_id, name)
            );
        """)
        # 2. 背包表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT,
                owner_name TEXT,
                item_name TEXT,
                amount INT,
                giver TEXT DEFAULT '系統商城'
            );
        """)
        # 3. 商店表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT,
                shop_name TEXT,
                name TEXT,
                price BIGINT,
                description TEXT,
                stat_bonus TEXT,
                affinity_bonus INT DEFAULT 0,
                usable INT DEFAULT 1,
                target_role_id BIGINT DEFAULT 0,
                seller TEXT DEFAULT '官方'
            );
        """)
        # 4. NPC 名冊表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS npcs (
                guild_id BIGINT,
                name TEXT,
                age INT,
                gender TEXT,
                identity TEXT,
                avatar_url TEXT,
                cash BIGINT DEFAULT 0,
                bank BIGINT DEFAULT 0,
                works TEXT DEFAULT '[]',
                stats TEXT DEFAULT '{}',
                rank_order INT DEFAULT 99,
                rank_name TEXT DEFAULT '業界前輩',
                PRIMARY KEY (guild_id, name)
            );
        """)
        # 5. NPC 好感度表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS npc_affection (
                guild_id BIGINT,
                char_name TEXT,
                npc_name TEXT,
                affection INT DEFAULT 0,
                PRIMARY KEY (guild_id, char_name, npc_name)
            );
        """)
        # 6. 系統參數表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                guild_id BIGINT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (guild_id, key)
            );
        """)
        # 7. 任務總表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS quests (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT,
                category TEXT,
                title TEXT,
                reward_desc TEXT,
                reward_cash BIGINT DEFAULT 0,
                reward_items TEXT DEFAULT '[]',
                reward_stats TEXT DEFAULT '',
                time_limit TEXT DEFAULT '',
                report_channel_id BIGINT DEFAULT 0,
                level_tag TEXT DEFAULT '',
                requirements TEXT DEFAULT ''
            );
        """)
        # 8. 任務完成記錄表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS quest_completions (
                guild_id BIGINT,
                char_name TEXT,
                quest_title TEXT,
                level_tag TEXT DEFAULT '',
                completed_at DOUBLE PRECISION,
                PRIMARY KEY (guild_id, char_name, quest_title)
            );
        """)
        # 9. 排行榜單表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS leaderboards (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT,
                name TEXT,
                stat_key TEXT
            );
        """)
        # 10. 活躍門票表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS active_tickets (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT,
                char_name TEXT,
                user_id BIGINT,
                role_id BIGINT,
                ticket_name TEXT,
                start_time DOUBLE PRECISION,
                expire_time DOUBLE PRECISION
            );
        """)
        # 11. 咖位等級限制表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rank_limits (
                guild_id BIGINT,
                rank_order INT,
                rank_name TEXT,
                work_req TEXT DEFAULT '',
                endorse_req TEXT DEFAULT '',
                stat_req TEXT DEFAULT '',
                max_members INT DEFAULT 0,
                PRIMARY KEY (guild_id, rank_order)
            );
        """)

        # 資料表欄位防呆熱升級
        alter_stmts = [
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS rank_order INT DEFAULT 99;",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS rank_name TEXT DEFAULT '無名新人';",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS cash BIGINT DEFAULT 0;",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS bank BIGINT DEFAULT 0;",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS works TEXT DEFAULT '[]';",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS rank_order INT DEFAULT 99;",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS rank_name TEXT DEFAULT '業界前輩';",
            "ALTER TABLE quests ADD COLUMN IF NOT EXISTS level_tag TEXT DEFAULT '';",
            "ALTER TABLE quests ADD COLUMN IF NOT EXISTS requirements TEXT DEFAULT '';",
            "ALTER TABLE quest_completions ADD COLUMN IF NOT EXISTS level_tag TEXT DEFAULT '';"
        ]
        for stmt in alter_stmts:
            try:
                await conn.execute(stmt)
            except Exception:
                pass

# -------------------- 咖位檢測與自動升級邏輯 --------------------
async def check_and_promote_rank(guild_id: int, target_name: str, channel: discord.abc.Messageable = None):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        char_row = await conn.fetchrow("SELECT * FROM characters WHERE guild_id = $1 AND name = $2", guild_id, target_name)
        is_npc = False
        if not char_row:
            char_row = await conn.fetchrow("SELECT * FROM npcs WHERE guild_id = $1 AND name = $2", guild_id, target_name)
            is_npc = True

        if not char_row:
            return

        current_order = char_row['rank_order'] or 99
        ranks = await conn.fetch("SELECT * FROM rank_limits WHERE guild_id = $1 ORDER BY rank_order ASC", guild_id)
        if not ranks:
            return

        works = json.loads(char_row['works']) if char_row['works'] else []
        stats = json.loads(char_row['stats']) if char_row['stats'] else {}

        done_tags = await conn.fetch("SELECT level_tag FROM quest_completions WHERE guild_id = $1 AND char_name = $2", guild_id, target_name)
        completed_tags = [r['level_tag'] for r in done_tags if r['level_tag']]

        for rk in ranks:
            r_order = rk['rank_order']
            r_name = rk['rank_name']

            if r_order >= current_order:
                continue

            if rk['max_members'] > 0:
                c_cnt = await conn.fetchval("SELECT COUNT(*) FROM characters WHERE guild_id = $1 AND rank_order = $2", guild_id, r_order)
                n_cnt = await conn.fetchval("SELECT COUNT(*) FROM npcs WHERE guild_id = $1 AND rank_order = $2", guild_id, r_order)
                if (c_cnt + n_cnt) >= rk['max_members']:
                    continue

            qualified = True

            # 1. 作品限制檢核
            if rk['work_req']:
                req_num_match = re.search(r"(\d+)", rk['work_req'])
                req_count = int(req_num_match.group(1)) if req_num_match else 1
                type_match = re.findall(r"(電視劇|電影|短劇|舞台劇|MV|演唱會)", rk['work_req'])
                if type_match:
                    actual_cnt = sum(1 for w in works if any(t in w.get('category', '') for t in type_match))
                else:
                    actual_cnt = len(works)
                if actual_cnt < req_count:
                    qualified = False

            # 2. 代言標籤限制檢核
            if qualified and rk['endorse_req']:
                req_endorse_match = re.search(r"(\d+)", rk['endorse_req'])
                req_endorse_cnt = int(req_endorse_match.group(1)) if req_endorse_match else 1
                tag_keywords = [re.sub(r"[\d\s個部項次]+", "", t).strip() for t in re.split(r"[,/、\s]+", rk['endorse_req']) if t.strip()]
                tag_keywords = [t for t in tag_keywords if t]
                actual_endorse = sum(1 for tag in completed_tags if any(k in tag for k in tag_keywords))
                if actual_endorse < req_endorse_cnt:
                    qualified = False

            # 3. 數值限制檢核
            if qualified and rk['stat_req']:
                conditions = re.split(r"[,/、&；;\s]+", rk['stat_req'])
                for cond in conditions:
                    m = re.match(r"([^\d><=+ -]+)\s*([><=]+|\+)?\s*(\d+)", cond.strip())
                    if m:
                        s_name = m.group(1).strip()
                        s_op = m.group(2) if m.group(2) else ">="
                        s_target = int(m.group(3))
                        curr_val = stats.get(s_name, 0)
                        if ">" in s_op and curr_val < s_target:
                            qualified = False
                            break
                        elif "<" in s_op and curr_val > s_target:
                            qualified = False
                            break
                        elif curr_val < s_target:
                            qualified = False
                            break

            if qualified:
                tbl = "npcs" if is_npc else "characters"
                await conn.execute(f"UPDATE {tbl} SET rank_order = $1, rank_name = $2 WHERE guild_id = $3 AND name = $4", r_order, r_name, guild_id, target_name)
                
                tag_str = "［NPC］" if is_npc else ""
                msg = f"🎊 **【演藝圈頭條・咖位躍升】** 恭喜 {tag_str}**{target_name}** 實力資歷全數達標，咖位正式晉升至 👑 **【{r_name}】**！"
                if channel:
                    await channel.send(msg)
                print(msg)
                break

# -------------------- 定時任務 --------------------
@tasks.loop(hours=24)
async def daily_interest():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        guild_rows = await conn.fetch("SELECT DISTINCT guild_id FROM characters")
        for g_record in guild_rows:
            g_id = g_record['guild_id']
            row = await conn.fetchrow("SELECT value FROM system_settings WHERE guild_id = $1 AND key = 'interest_rate'", g_id)
            rate = float(row['value']) if row else 0.05
            await conn.execute(f"UPDATE characters SET bank = CAST(bank * (1 + {rate}) AS BIGINT) WHERE guild_id = $1 AND bank > 0", g_id)
            await conn.execute(f"UPDATE npcs SET bank = CAST(bank * (1 + {rate}) AS BIGINT) WHERE guild_id = $1 AND bank > 0", g_id)

@tasks.loop(hours=1)
async def check_ticket_expiration():
    now = time.time()
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        expired = await conn.fetch("SELECT id, char_name, user_id, guild_id, role_id, ticket_name FROM active_tickets WHERE expire_time <= $1", now)
        for record in expired:
            rec_id, c_name, u_id, g_id, r_id = record['id'], record['char_name'], record['user_id'], record['guild_id'], record['role_id']
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
            await conn.execute("UPDATE characters SET ticket_ban_until = $1 WHERE guild_id = $2 AND name = $3", ban_until, g_id, c_name)
            await conn.execute("DELETE FROM active_tickets WHERE id = $1", rec_id)

@tasks.loop(hours=24)
async def monthly_age_up():
    now = time.time()
    one_month = 30 * 86400
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT guild_id, name, age, created_at FROM characters")
        for r in rows:
            if r['created_at']:
                months_passed = int((now - r['created_at']) // one_month)
                if months_passed > 0:
                    await conn.execute(
                        "UPDATE characters SET age = age + 1, created_at = created_at + $1 WHERE guild_id = $2 AND name = $3",
                        one_month, r['guild_id'], r['name']
                    )

# -------------------- UI 互動元件 --------------------
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
            if qty <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ 請輸入大於 0 的整數！", ephemeral=True)
            return

        total_cost = self.price * qty
        now = time.time()
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT cash, ticket_ban_until FROM characters WHERE guild_id = $1 AND name = $2", self.guild_id, self.buyer)
            if not user or user['cash'] < total_cost:
                await interaction.response.send_message(f"❌ 現金不足！需要 ${total_cost:,}，當前僅有 ${user['cash'] if user else 0:,}。", ephemeral=True)
                return

            s_item = await conn.fetchrow("SELECT shop_name, target_role_id, seller FROM shop_items WHERE guild_id = $1 AND id = $2", self.guild_id, self.item_id)
            if not s_item:
                await interaction.response.send_message("❌ 查無此商品！", ephemeral=True)
                return

            if (s_item['shop_name'] == "票務系統" or (s_item['target_role_id'] and s_item['target_role_id'] > 0)):
                if user['ticket_ban_until'] and user['ticket_ban_until'] > now:
                    remain_hours = int((user['ticket_ban_until'] - now) / 3600)
                    await interaction.response.send_message(f"🚫 該角色因先前逾期未返回遭遣返，目前處於購票懲罰期！尚餘 **{remain_hours}** 小時禁止購票。", ephemeral=True)
                    return

            await conn.execute("UPDATE characters SET cash = cash - $1 WHERE guild_id = $2 AND name = $3", total_cost, self.guild_id, self.buyer)
            if s_item['seller'] != '官方':
                seller_is_npc = await conn.fetchrow("SELECT name FROM npcs WHERE guild_id = $1 AND name = $2", self.guild_id, s_item['seller'])
                tbl = "npcs" if seller_is_npc else "characters"
                await conn.execute(f"UPDATE {tbl} SET cash = cash + $1 WHERE guild_id = $2 AND name = $3", total_cost, self.guild_id, s_item['seller'])

            inv_row = await conn.fetchrow("SELECT id, amount FROM inventory WHERE guild_id = $1 AND owner_name = $2 AND item_name = $3", self.guild_id, self.buyer, self.item_name)
            if inv_row:
                await conn.execute("UPDATE inventory SET amount = amount + $1 WHERE id = $2", qty, inv_row['id'])
            else:
                await conn.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES ($1, $2, $3, $4, '系統商城')", self.guild_id, self.buyer, self.item_name, qty)

            if s_item['seller'] != '官方':
                await conn.execute("DELETE FROM shop_items WHERE guild_id = $1 AND id = $2", self.guild_id, self.item_id)

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
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                items = await conn.fetch("SELECT id, name, price, description, stat_bonus, seller, target_role_id FROM shop_items WHERE guild_id = $1 AND shop_name = $2", self.guild_id, shop_name)

            if not items:
                await interaction.response.send_message(f"🏪 **{shop_name}** 目前無任何商品。", ephemeral=True)
                return

            embed = discord.Embed(title=f"🏪 商城 — 【{shop_name}】", color=0x2ECC71 if shop_name == "票務系統" else 0xD4AF37)
            item_select_view = discord.ui.View(timeout=120)

            options = []
            for item in items[:25]:
                label_extra = f" (賣家: {item['seller']})" if item['seller'] != '官方' else ""
                role_tag = " ｜ 🗺️ 包含地圖身分組" if item['target_role_id'] > 0 else ""
                embed.add_field(name=f"📦 {item['name']} — ${item['price']:,}{label_extra}{role_tag}", value=f"簡介: {item['description']}\n加成: {item['stat_bonus']}", inline=False)
                options.append(discord.SelectOption(label=f"{item['name']} (${item['price']:,})", value=str(item['id']), description=item['description'][:50]))

            select = discord.ui.Select(placeholder="選擇欲購買商品/門票...", options=options)
            
            async def select_callback(inter: discord.Interaction):
                selected_id = int(select.values[0])
                for it in items:
                    if it['id'] == selected_id:
                        await inter.response.send_modal(BuyModal(selected_id, it['name'], it['price'], self.char_name, self.guild_id))
                        break

            select.callback = select_callback
            item_select_view.add_item(select)
            await interaction.response.send_message(embed=embed, view=item_select_view, ephemeral=True)

        return callback

class WorkRegisterModal(discord.ui.Modal, title="作品檔案登記"):
    def __init__(self, char_name: str, category: str, guild_id: int):
        super().__init__()
        self.char_name = char_name
        self.category = category
        self.guild_id = guild_id

        self.work_title = discord.ui.TextInput(label="作品名稱", placeholder="輸入作品名稱")
        self.add_item(self.work_title)

        if category in ["電視劇", "電影", "短劇", "舞台劇"]:
            self.role_info = discord.ui.TextInput(label="番位 & 角色名", placeholder="例如：領銜主演 / 飾演 顧淮安")
            self.add_item(self.role_info)
        elif category in ["廣告", "代言", "其他"]:
            self.desc_info = discord.ui.TextInput(label="代言商品 / 簡介", placeholder="例如：品牌全球代言人 / 香水推廣", style=discord.TextStyle.paragraph)
            self.add_item(self.desc_info)

    async def on_submit(self, interaction: discord.Interaction):
        extra_val = getattr(self, 'role_info', getattr(self, 'desc_info', None))
        work_entry = {
            "category": self.category,
            "title": self.work_title.value,
            "extra": extra_val.value if extra_val else ""
        }

        pool = await get_db_pool()
        async with pool.acquire() as conn:
            char_row = await conn.fetchrow("SELECT works FROM characters WHERE guild_id = $1 AND name = $2", self.guild_id, self.char_name)
            is_npc = False
            if not char_row:
                char_row = await conn.fetchrow("SELECT works FROM npcs WHERE guild_id = $1 AND name = $2", self.guild_id, self.char_name)
                is_npc = True

            works = json.loads(char_row['works']) if char_row and char_row['works'] else []
            works.append(work_entry)
            tbl = "npcs" if is_npc else "characters"
            await conn.execute(f"UPDATE {tbl} SET works = $1 WHERE guild_id = $2 AND name = $3", json.dumps(works, ensure_ascii=False), self.guild_id, self.char_name)

        await interaction.response.send_message(f"✅ 已成功為 **{self.char_name}** 登記作品：【{self.category}】《{self.work_title.value}》！", ephemeral=True)
        await check_and_promote_rank(self.guild_id, self.char_name, interaction.channel)

# -------------------- 玩家指令：檔案建立、更新、查看 --------------------
@bot.tree.command(name="檔案建立", description="建立自己的角色檔案")
async def create_profile(interaction: discord.Interaction, 名字: str, 年齡: int, 性別: str, 職業: str, 勢力: str):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchrow("SELECT name FROM characters WHERE guild_id = $1 AND name = $2", g_id, 名字)
        if exists:
            await interaction.response.send_message(f"❌ 角色名 **{名字}** 已存在於本伺服器！", ephemeral=True)
            return

        lowest_rank = await conn.fetchrow("SELECT rank_order, rank_name FROM rank_limits WHERE guild_id = $1 ORDER BY rank_order DESC LIMIT 1", g_id)
        r_order = lowest_rank['rank_order'] if lowest_rank else 99
        r_name = lowest_rank['rank_name'] if lowest_rank else '無名新人'

        await conn.execute("""
            INSERT INTO characters (guild_id, user_id, name, age, gender, job, faction, cash, bank, works, created_at, stats, ticket_ban_until, rank_order, rank_name)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 0, 0, '[]', $8, '{}', 0, $9, $10)
        """, g_id, interaction.user.id, 名字, 年齡, 性別, 職業, 勢力, time.time(), r_order, r_name)

    await interaction.response.send_message(f"🎉 角色 **{名字}** 檔案建立成功！當前咖位：【{r_name}】。")

class UpdateProfileSelect(discord.ui.Select):
    def __init__(self, char_name: str, guild_id: int):
        self.char_name = char_name
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="更新基礎資料 (名字/性別/職業/勢力)", value="base"),
            discord.SelectOption(label="電視劇", value="電視劇"),
            discord.SelectOption(label="電影", value="電影"),
            discord.SelectOption(label="短劇", value="短劇"),
            discord.SelectOption(label="舞台劇", value="舞台劇"),
            discord.SelectOption(label="MV", value="MV"),
            discord.SelectOption(label="演唱會", value="演唱會"),
            discord.SelectOption(label="廣告", value="廣告"),
            discord.SelectOption(label="代言", value="代言"),
            discord.SelectOption(label="其他", value="其他"),
        ]
        super().__init__(placeholder="選擇欲修改項或登記作品類別...", options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        if choice == "base":
            class BaseModal(discord.ui.Modal, title="修改角色基本資料"):
                new_name = discord.ui.TextInput(label="名字", default=self.char_name)
                gender = discord.ui.TextInput(label="性別")
                job = discord.ui.TextInput(label="職業")
                faction = discord.ui.TextInput(label="勢力")

                async def on_submit(m_self, inter: discord.Interaction):
                    pool = await get_db_pool()
                    async with pool.acquire() as conn:
                        await conn.execute("UPDATE characters SET name = $1, gender = $2, job = $3, faction = $4 WHERE guild_id = $5 AND name = $6",
                                         m_self.new_name.value, m_self.gender.value, m_self.job.value, m_self.faction.value, self.guild_id, self.char_name)
                    await inter.response.send_message("✅ 角色資料更新完成！", ephemeral=True)

            await interaction.response.send_modal(BaseModal())
        else:
            await interaction.response.send_modal(WorkRegisterModal(self.char_name, choice, self.guild_id))

@bot.tree.command(name="檔案更新", description="更新角色資料或登記演藝作品")
async def update_profile(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    view = discord.ui.View()
    view.add_item(UpdateProfileSelect(角色名, g_id))
    await interaction.response.send_message(f"📝 請選擇 **{角色名}** 要登記或更新的項目：", view=view, ephemeral=True)

@bot.tree.command(name="查看", description="查看角色完整檔案、當前咖位與下一級所需內容")
async def view_profile(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        char = await conn.fetchrow("SELECT * FROM characters WHERE guild_id = $1 AND name = $2", g_id, 角色名)
        if not char:
            await interaction.response.send_message(f"❌ 查無角色 **{角色名}**！", ephemeral=True)
            return

        aff_rows = await conn.fetch("SELECT npc_name, affection FROM npc_affection WHERE guild_id = $1 AND char_name = $2", g_id, 角色名)
        ticket_row = await conn.fetchrow("SELECT ticket_name, expire_time FROM active_tickets WHERE guild_id = $1 AND char_name = $2", g_id, 角色名)
        
        # 取得下一階級咖位需求
        curr_order = char['rank_order'] or 99
        next_rank = await conn.fetchrow("SELECT * FROM rank_limits WHERE guild_id = $1 AND rank_order < $2 ORDER BY rank_order DESC LIMIT 1", g_id, curr_order)

    embed = discord.Embed(title=f"🪪【{角色名}】個人檔案", color=0xE67E22)
    embed.add_field(name="基本信息", value=f"• 年齡：{char['age']} 歲\n• 性別：{char['gender']}\n• 職業：{char['job']}\n• 勢力：{char['faction']}", inline=True)
    embed.add_field(name="財務狀態", value=f"• 現金：${char['cash']:,}\n• 銀行：${char['bank']:,}", inline=True)
    
    # 咖位展示與升級所需
    rank_disp = char['rank_name'] if char['rank_name'] else '無名新人'
    if next_rank:
        req_lines = []
        if next_rank['work_req']: req_lines.append(f"作品: {next_rank['work_req']}")
        if next_rank['endorse_req']: req_lines.append(f"代言: {next_rank['endorse_req']}")
        if next_rank['stat_req']: req_lines.append(f"數值: {next_rank['stat_req']}")
        quota_str = f" (名額限 {next_rank['max_members']} 人)" if next_rank['max_members'] > 0 else ""
        next_info = f"下一階 👑 **【{next_rank['rank_name']}】**{quota_str}\n  └ 需達成：{' ｜ '.join(req_lines) if req_lines else '無特殊限制'}"
    else:
        next_info = "👑 已登上業界巔峰頂流，受萬人景仰！"

    embed.add_field(name="👑 當前咖位", value=f"**【{rank_disp}】** (順序 #{curr_order})\n{next_info}", inline=False)

    now = time.time()
    if ticket_row:
        remain_hours = max(0, int((ticket_row['expire_time'] - now) / 3600))
        embed.add_field(name="🗺️ 當前地圖簽證", value=f"• 門票：**{ticket_row['ticket_name']}** ｜ 尚餘 **{remain_hours}** 小時", inline=False)
    elif char['ticket_ban_until'] and char['ticket_ban_until'] > now:
        ban_remain = int((char['ticket_ban_until'] - now) / 3600)
        embed.add_field(name="⚠️ 票務懲罰中", value=f"強制遣返懲罰期，尚餘 **{ban_remain}** 小時禁止購票！", inline=False)

    stats = json.loads(char['stats']) if char['stats'] else {}
    if stats:
        embed.add_field(name="📊 各項數值能力", value=" ｜ ".join([f"• {k}: **{v}**" for k, v in stats.items()]), inline=False)

    works = json.loads(char['works']) if char['works'] else []
    if works:
        work_texts = [f"• 【{w['category']}】《{w['title']}》({w.get('extra', '')})" for w in works[-5:]]
        embed.add_field(name="代表作品 (最新5筆)", value="\n".join(work_texts), inline=False)

    if aff_rows:
        embed.add_field(name="NPC 好感度", value="\n".join([f"• **{r['npc_name']}**：💖 {r['affection']}" for r in aff_rows]), inline=False)

    await interaction.response.send_message(embed=embed)

# -------------------- 背包與商城系統 --------------------
@bot.tree.command(name="商城", description="選擇商城並購買商品")
async def shop(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        char_row = await conn.fetchrow("SELECT name FROM characters WHERE guild_id = $1 AND name = $2", g_id, 角色名)
        if not char_row:
            await interaction.response.send_message("❌ 查無此角色檔案！", ephemeral=True)
            return

        shop_rows = await conn.fetch("SELECT DISTINCT shop_name FROM shop_items WHERE guild_id = $1", g_id)
        shops = [r['shop_name'] for r in shop_rows]

    for default_s in ["票務系統", "二手"]:
        if default_s not in shops:
            shops.append(default_s)

    view = ShopSelectView(角色名, shops, g_id)
    await interaction.response.send_message(f"🏬 請選擇 **{角色名}** 想進入的商店：", view=view, ephemeral=True)

@bot.tree.command(name="背包", description="查看角色背包物品與來源")
async def inventory(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        items = await conn.fetch("SELECT item_name, amount, giver FROM inventory WHERE guild_id = $1 AND owner_name = $2", g_id, 角色名)

    if not items:
        await interaction.response.send_message(f"🎒 **{角色名}** 的背包目前沒有物品。", ephemeral=True)
        return

    embed = discord.Embed(title=f"🎒【{角色名}】的背包清單", color=0x3498DB)
    for row in items:
        embed.add_field(name=f"📦 {row['item_name']} × {row['amount']}", value=f"來源/贈予人: {row['giver']}", inline=True)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="使用", description="使用背包中的道具，數值自動累計；門票將派發身分組")
async def use_item(interaction: discord.Interaction, 角色名: str, 物品名: str):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        inv = await conn.fetchrow("SELECT id, amount FROM inventory WHERE guild_id = $1 AND owner_name = $2 AND item_name = $3", g_id, 角色名, 物品名)
        if not inv or inv['amount'] <= 0:
            await interaction.response.send_message("❌ 背包中沒有該物品或數量不足！", ephemeral=True)
            return

        item_info = await conn.fetchrow("SELECT usable, stat_bonus, target_role_id FROM shop_items WHERE guild_id = $1 AND name = $2", g_id, 物品名)
        if not item_info or item_info['usable'] == 0:
            await interaction.response.send_message(f"⚠️ **{物品名}** 為不可使用之物品！", ephemeral=True)
            return

        role_msg = ""
        now = time.time()
        target_role_id = item_info['target_role_id']
        if target_role_id and target_role_id > 0:
            role = interaction.guild.get_role(target_role_id)
            if role:
                try:
                    await interaction.user.add_roles(role, reason=f"使用門票【{物品名}】")
                    role_msg = f"\n🗺️ 已獲得大地圖身分組 **【{role.name}】**！"
                except Exception as e:
                    role_msg = f"\n⚠️ 身分組派發失敗：{e}"

            expire_at = now + (336 * 3600)
            await conn.execute("""
                INSERT INTO active_tickets (guild_id, char_name, user_id, role_id, ticket_name, start_time, expire_time)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, g_id, 角色名, interaction.user.id, target_role_id, 物品名, now, expire_at)
            role_msg += f"\n⏰ **簽證有效時間：336 小時**。請在到期前使用 `/返回原本地圖`，否則將強制遣返並**限制 300 小時不得購票**！"

        if inv['amount'] == 1:
            await conn.execute("DELETE FROM inventory WHERE id = $1", inv['id'])
        else:
            await conn.execute("UPDATE inventory SET amount = amount - 1 WHERE id = $1", inv['id'])

        stat_delta_msg = ""
        bonus_str = item_info['stat_bonus']
        stat_match = re.search(r"([^\d+-]+)\s*([+-]?\d+)", bonus_str)
        if stat_match:
            stat_name = stat_match.group(1).strip()
            stat_val = int(stat_match.group(2))

            char_row = await conn.fetchrow("SELECT stats FROM characters WHERE guild_id = $1 AND name = $2", g_id, 角色名)
            stats = json.loads(char_row['stats']) if char_row and char_row['stats'] else {}
            stats[stat_name] = stats.get(stat_name, 0) + stat_val
            await conn.execute("UPDATE characters SET stats = $1 WHERE guild_id = $2 AND name = $3", json.dumps(stats, ensure_ascii=False), g_id, 角色名)
            stat_delta_msg = f"\n📊 **{stat_name}** 已自動更新至 **{stats[stat_name]}**！"

    await interaction.response.send_message(f"✨ **{角色名}** 使用了 **{物品名}**！獲得加成：【{bonus_str}】{stat_delta_msg}（剩餘: {inv['amount'] - 1}）{role_msg}")
    await check_and_promote_rank(g_id, 角色名, interaction.channel)

@bot.tree.command(name="返回原本地圖", description="主動結束地圖旅行並收回身分組（免除遣返懲罰）")
async def return_home(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        ticket = await conn.fetchrow("SELECT id, role_id, ticket_name FROM active_tickets WHERE guild_id = $1 AND char_name = $2", g_id, 角色名)
        if not ticket:
            await interaction.response.send_message(f"ℹ️ 角色 **{角色名}** 目前並無啟用中的外地簽證或門票身分組！", ephemeral=True)
            return

        role = interaction.guild.get_role(ticket['role_id'])
        if role:
            try:
                await interaction.user.remove_roles(role, reason="玩家主動返回原本地圖")
            except Exception:
                pass

        await conn.execute("DELETE FROM active_tickets WHERE id = $1", ticket['id'])

    await interaction.response.send_message(f"🏠 **{角色名}** 已順利返回原本地圖！已安全繳回門票身分組，無任何懲罰。")

@bot.tree.command(name="贈予", description="贈送物品給其他玩家或 NPC")
async def gift_item(interaction: discord.Interaction, 角色名: str, 對象名: str, 物品名: str, 數量: int):
    g_id = interaction.guild_id
    if 數量 <= 0:
        await interaction.response.send_message("❌ 數量需大於 0！", ephemeral=True)
        return

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        inv = await conn.fetchrow("SELECT id, amount FROM inventory WHERE guild_id = $1 AND owner_name = $2 AND item_name = $3", g_id, 角色名, 物品名)
        if not inv or inv['amount'] < 數量:
            await interaction.response.send_message("❌ 背包中該物品數量不足！", ephemeral=True)
            return

        is_npc = await conn.fetchrow("SELECT name FROM npcs WHERE guild_id = $1 AND name = $2", g_id, 對象名) is not None

        if inv['amount'] == 數量:
            await conn.execute("DELETE FROM inventory WHERE id = $1", inv['id'])
        else:
            await conn.execute("UPDATE inventory SET amount = amount - $1 WHERE id = $2", 數量, inv['id'])

        extra_msg = ""
        if is_npc:
            item_row = await conn.fetchrow("SELECT affinity_bonus FROM shop_items WHERE guild_id = $1 AND name = $2", g_id, 物品名)
            single_aff = item_row['affinity_bonus'] if item_row else 10
            total_aff = single_aff * 數量

            await conn.execute("""
                INSERT INTO npc_affection (guild_id, char_name, npc_name, affection)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT(guild_id, char_name, npc_name) DO UPDATE SET affection = npc_affection.affection + $5
            """, g_id, 角色名, 對象名, total_aff, total_aff)
            extra_msg = f"\n💖 NPC **{對象名}** 對你的好感度增加了 **+{total_aff}**！"
        else:
            target_inv = await conn.fetchrow("SELECT id, amount FROM inventory WHERE guild_id = $1 AND owner_name = $2 AND item_name = $3", g_id, 對象名, 物品名)
            if target_inv:
                await conn.execute("UPDATE inventory SET amount = amount + $1 WHERE id = $2", 數量, target_inv['id'])
            else:
                await conn.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES ($1, $2, $3, $4, $5)", g_id, 對象名, 物品名, 數量, 角色名)

    await interaction.response.send_message(f"🎁 **{角色名}** 贈送了 **{物品名}** ×{數量} 給 **{對象名}**！{extra_msg}")

# -------------------- NPC 查看系統 (支援咖位展示) --------------------
class NPCSelectDropdown(discord.ui.Select):
    def __init__(self, npcs, guild_id: int):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(
                label=npc['name'], 
                description=f"{npc['age']}歲 ｜ {npc['gender']} ｜ {npc['identity'][:20]}", 
                emoji="👤"
            ) for npc in npcs[:25]
        ]
        super().__init__(placeholder="點此選擇欲查看檔案的官方 NPC...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await render_npc_profile(interaction, self.values[0], self.guild_id)

class NPCSelectView(discord.ui.View):
    def __init__(self, npcs, guild_id: int):
        super().__init__(timeout=180)
        self.add_item(NPCSelectDropdown(npcs, guild_id))

async def render_npc_profile(interaction: discord.Interaction, npc_name: str, guild_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        npc_info = await conn.fetchrow("SELECT * FROM npcs WHERE guild_id = $1 AND name = $2", guild_id, npc_name)
        if not npc_info:
            await interaction.response.send_message(f"❌ 查無官方 NPC `{npc_name}`！", ephemeral=True)
            return

        favor_records = await conn.fetch("SELECT char_name, affection FROM npc_affection WHERE guild_id = $1 AND npc_name = $2 AND affection > 0 ORDER BY affection DESC LIMIT 10", guild_id, npc_name)
        curr_order = npc_info['rank_order'] or 99
        next_rank = await conn.fetchrow("SELECT * FROM rank_limits WHERE guild_id = $1 AND rank_order < $2 ORDER BY rank_order DESC LIMIT 1", guild_id, curr_order)

    embed = discord.Embed(title=f"🎭 官方 NPC 檔案：{npc_info['name']}", color=0xE91E63)
    embed.add_field(name="基本資訊", value=f"• 年齡：{npc_info['age']} 歲\n• 性別：{npc_info['gender']}\n• 身分：{npc_info['identity']}", inline=False)
    embed.add_field(name="財務狀態", value=f"• 現金：${npc_info['cash']:,}\n• 銀行：${npc_info['bank']:,}", inline=True)

    r_title = npc_info['rank_name'] if npc_info['rank_name'] else '業界前輩'
    next_info = f"下一階 👑 **【{next_rank['rank_name']}】**" if next_rank else "👑 業界至尊地位"
    embed.add_field(name="👑 當前咖位", value=f"**【{r_title}】** (順序 #{curr_order})\n{next_info}", inline=True)

    if npc_info['avatar_url']:
        embed.set_thumbnail(url=npc_info['avatar_url'])

    npc_stats = json.loads(npc_info['stats']) if npc_info['stats'] else {}
    if npc_stats:
        embed.add_field(name="📊 各項數值能力", value=" ｜ ".join([f"• {k}: **{v:,}**" for k, v in npc_stats.items()]), inline=False)

    if favor_records:
        rank_emojis = ["🥇", "🥈", "🥉"]
        ranking_lines = []
        for index, r in enumerate(favor_records):
            rank_tag = rank_emojis[index] if index < 3 else f"`#{index + 1}`"
            ranking_lines.append(f"{rank_tag} **{r['char_name']}** ｜ 💖 **{r['affection']:,}** 點")
        embed.add_field(name="🏆 角色好感度排行榜 (TOP 10)", value="\n".join(ranking_lines), inline=False)

    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="npc查看", description="查看已登記的官方 NPC 列表名冊或指定 NPC 詳細檔案")
@app_commands.describe(npc名稱="可選填：輸入特定 NPC 姓名，留空則開啟全 NPC 選單")
async def view_npc_cmd(interaction: discord.Interaction, npc名稱: str = None):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        all_npcs = await conn.fetch("SELECT name, age, gender, identity, avatar_url, stats FROM npcs WHERE guild_id = $1", g_id)

    if not all_npcs:
        await interaction.response.send_message("📋 目前本伺服器尚未登記任何官方 NPC！", ephemeral=True)
        return

    if npc名稱:
        await render_npc_profile(interaction, npc名稱.strip(), g_id)
        return

    embed = discord.Embed(title="👥 流光城官方 NPC 名錄大廳", description="請點選下方選單查看各 NPC 個人檔案與好感度榜：", color=0x9B59B6)
    for npc in all_npcs:
        embed.add_field(name=f"👤 {npc['name']} ({npc['age']}歲 / {npc['gender']})", value=f"身分：{npc['identity']}", inline=True)

    await interaction.response.send_message(embed=embed, view=NPCSelectView(all_npcs, g_id), ephemeral=True)

# -------------------- 銀行、二手與金錢指令 (全面支援 NPC) --------------------
@bot.tree.command(name="售物", description="將擁有物品放上［二手］商城販售")
async def sell_item(interaction: discord.Interaction, 角色名: str, 物品名: str, 價格: int):
    g_id = interaction.guild_id
    if 價格 <= 0:
        await interaction.response.send_message("❌ 販售價格必須大於 0！", ephemeral=True)
        return

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        inv = await conn.fetchrow("SELECT id, amount FROM inventory WHERE guild_id = $1 AND owner_name = $2 AND item_name = $3", g_id, 角色名, 物品名)
        if not inv or inv['amount'] <= 0:
            await interaction.response.send_message("❌ 背包中查無此物品！", ephemeral=True)
            return

        if inv['amount'] == 1:
            await conn.execute("DELETE FROM inventory WHERE id = $1", inv['id'])
        else:
            await conn.execute("UPDATE inventory SET amount = amount - 1 WHERE id = $1", inv['id'])

        await conn.execute("""
            INSERT INTO shop_items (guild_id, shop_name, name, price, description, stat_bonus, affinity_bonus, usable, target_role_id, seller)
            VALUES ($1, '二手', $2, $3, '玩家自售物品', '無加成', 0, 1, 0, $4)
        """, g_id, 物品名, 價格, 角色名)

    await interaction.response.send_message(f"🏷️ 已將 **{物品名}** 上架至【二手】商城，定價為 **${價格:,}**！")

@bot.tree.command(name="存錢", description="將現金存入銀行 (角色與 NPC 皆可用)")
@app_commands.describe(名字="角色或 NPC 名字", 金額="欲存入銀行的現金金額")
async def deposit(interaction: discord.Interaction, 名字: str, 金額: int):
    g_id = interaction.guild_id
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額需大於 0！", ephemeral=True)
        return

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT cash FROM characters WHERE guild_id = $1 AND name = $2", g_id, 名字)
        tbl = "characters"
        if not user:
            user = await conn.fetchrow("SELECT cash FROM npcs WHERE guild_id = $1 AND name = $2", g_id, 名字)
            tbl = "npcs"

        if not user or user['cash'] < 金額:
            await interaction.response.send_message(f"❌ 現金不足！當前僅有 ${user['cash'] if user else 0:,}。", ephemeral=True)
            return

        await conn.execute(f"UPDATE {tbl} SET cash = cash - $1, bank = bank + $2 WHERE guild_id = $3 AND name = $4", 金額, 金額, g_id, 名字)

    await interaction.response.send_message(f"🏦 **{名字}** 成功存入 **${金額:,}**！")

@bot.tree.command(name="取錢", description="從銀行取出金錢 (角色與 NPC 皆可用)")
@app_commands.describe(名字="角色或 NPC 名字", 金額="欲自銀行提領的金額")
async def withdraw(interaction: discord.Interaction, 名字: str, 金額: int):
    g_id = interaction.guild_id
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額需大於 0！", ephemeral=True)
        return

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT bank FROM characters WHERE guild_id = $1 AND name = $2", g_id, 名字)
        tbl = "characters"
        if not user:
            user = await conn.fetchrow("SELECT bank FROM npcs WHERE guild_id = $1 AND name = $2", g_id, 名字)
            tbl = "npcs"

        if not user or user['bank'] < 金額:
            await interaction.response.send_message(f"❌ 存款不足！當前僅有 ${user['bank'] if user else 0:,}。", ephemeral=True)
            return

        await conn.execute(f"UPDATE {tbl} SET bank = bank - $1, cash = cash + $2 WHERE guild_id = $3 AND name = $4", 金額, 金額, g_id, 名字)

    await interaction.response.send_message(f"💵 **{名字}** 成功自銀行提款 **${金額:,}**！")

@bot.tree.command(name="轉錢", description="轉帳給其他角色或 NPC (雙向互通支援)")
@app_commands.describe(付款方="付款的角色或 NPC 名字", 收款方="收款的角色或 NPC 名字", 金額="轉帳金額")
async def transfer(interaction: discord.Interaction, 付款方: str, 收款方: str, 金額: int):
    g_id = interaction.guild_id
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額需大於 0！", ephemeral=True)
        return

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        sender = await conn.fetchrow("SELECT cash FROM characters WHERE guild_id = $1 AND name = $2", g_id, 付款方)
        s_tbl = "characters"
        if not sender:
            sender = await conn.fetchrow("SELECT cash FROM npcs WHERE guild_id = $1 AND name = $2", g_id, 付款方)
            s_tbl = "npcs"

        if not sender or sender['cash'] < 金額:
            await interaction.response.send_message(f"❌ 付款方【{付款方}】現金不足！", ephemeral=True)
            return

        receiver = await conn.fetchrow("SELECT name FROM characters WHERE guild_id = $1 AND name = $2", g_id, 收款方)
        r_tbl = "characters"
        if not receiver:
            receiver = await conn.fetchrow("SELECT name FROM npcs WHERE guild_id = $1 AND name = $2", g_id, 收款方)
            r_tbl = "npcs"

        if not receiver:
            await interaction.response.send_message(f"❌ 找不到受款對象 **{收款方}**！", ephemeral=True)
            return

        await conn.execute(f"UPDATE {s_tbl} SET cash = cash - $1 WHERE guild_id = $2 AND name = $3", 金額, g_id, 付款方)
        await conn.execute(f"UPDATE {r_tbl} SET cash = cash + $1 WHERE guild_id = $2 AND name = $3", 金額, g_id, 收款方)

    await interaction.response.send_message(f"💸 **{付款方}** 成功轉帳 **${金額:,}** 給 **{收款方}**！")

# -------------------- 任務與回報系統 (含等級與資格過濾) --------------------
@bot.tree.command(name="任務", description="查看角色當前完成與未完成的各類任務")
@app_commands.describe(角色名="欲查詢任務的角色名稱")
async def view_quests(interaction: discord.Interaction, 角色名: str):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        char_row = await conn.fetchrow("SELECT * FROM characters WHERE guild_id = $1 AND name = $2", g_id, 角色名)
        if not char_row:
            await interaction.response.send_message(f"❌ 查無角色 `{角色名}`！", ephemeral=True)
            return

        all_quests = await conn.fetch("SELECT * FROM quests WHERE guild_id = $1 ORDER BY id ASC", g_id)
        done_rows = await conn.fetch("SELECT quest_title FROM quest_completions WHERE guild_id = $1 AND char_name = $2", g_id, 角色名)
        done_titles = {r['quest_title'] for r in done_rows}

    if not all_quests:
        await interaction.response.send_message("📋 目前本伺服器尚未發布任何任務！", ephemeral=True)
        return

    categories = ["新手任務", "一般任務", "限時任務", "特殊任務"]
    embed = discord.Embed(title=f"📜【{角色名}】的任務清單", description="任務完成後標記 ✅，請至各任務指定回報區提交！", color=0xF1C40F)

    for cat in categories:
        cat_quests = [q for q in all_quests if q['category'] == cat]
        if not cat_quests:
            embed.add_field(name=f"📌 {cat}欄", value="暫無任務", inline=False)
            continue

        lines = []
        for q in cat_quests:
            status = "✅" if q['title'] in done_titles else "❌"
            tag_str = f" `[{q['level_tag']}]`" if q['level_tag'] else ""
            limit_str = f" ⏳ `{q['time_limit']}`" if q['time_limit'] else ""
            req_str = f"\n     ⚠️ 資格要求：`{q['requirements']}`" if q['requirements'] else ""
            ch_str = f" 📍 <#{q['report_channel_id']}>" if q['report_channel_id'] > 0 else ""
            lines.append(f"• **{q['title']}**{tag_str}{limit_str}{ch_str}\n  └ 獎勵：{q['reward_desc']} ［{status}］{req_str}")
        
        embed.add_field(name=f"📌 {cat}欄", value="\n".join(lines), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="回報任務", description="回報已完成的任務文章連結，領取對應獎勵")
@app_commands.describe(角色名="回報任務的角色名稱", 文章連結="你所發表文章的帖子/討論串或訊息連結")
async def report_quest(interaction: discord.Interaction, 角色名: str, 文章連結: str):
    g_id = interaction.guild_id
    await interaction.response.defer(ephemeral=False)

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        char_row = await conn.fetchrow("SELECT * FROM characters WHERE guild_id = $1 AND name = $2", g_id, 角色名)
        if not char_row:
            await interaction.followup.send(f"❌ 查無角色 `{角色名}`！", ephemeral=True)
            return
        if char_row['user_id'] != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ 你只能為自己持有的角色回報任務！", ephemeral=True)
            return

    link_match = re.search(r"channels/\d+/(\d+)(?:/(\d+))?", 文章連結)
    if not link_match:
        await interaction.followup.send("❌ 無法識別文章連結格式，請確認是否為正確的 Discord 連結！", ephemeral=True)
        return

    target_channel_id = int(link_match.group(1))
    target_msg_id = int(link_match.group(2)) if link_match.group(2) else None
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

    async with pool.acquire() as conn:
        all_quests = await conn.fetch("SELECT * FROM quests WHERE guild_id = $1", g_id)
        matched_quest = None
        for q in all_quests:
            if q['title'] in target_title:
                matched_quest = q
                break

        if not matched_quest:
            await interaction.followup.send(f"❌ 驗證失敗：無法在文章中匹配到正確的任務名稱！", ephemeral=True)
            return

        # 檢驗專屬回報頻道
        if matched_quest['report_channel_id'] and matched_quest['report_channel_id'] > 0:
            current_ch = interaction.channel
            is_correct_place = (current_ch.id == matched_quest['report_channel_id']) or (hasattr(current_ch, "parent_id") and current_ch.parent_id == matched_quest['report_channel_id'])
            if not is_correct_place:
                await interaction.followup.send(f"❌ 此任務限定在專屬回報區：<#{matched_quest['report_channel_id']}>", ephemeral=True)
                return

        # 檢驗任務接取限制
        if matched_quest['requirements']:
            req_items = re.split(r"[,/、&；;\s]+", matched_quest['requirements'])
            char_stats = json.loads(char_row['stats']) if char_row['stats'] else {}
            for r_item in req_items:
                r_item = r_item.strip()
                if "咖位" in r_item and char_row['rank_name'] not in r_item:
                    await interaction.followup.send(f"❌ 資格不符：角色咖位未達【{r_item}】！", ephemeral=True)
                    return
                if "身分" in r_item or "職業" in r_item:
                    if char_row['job'] not in r_item:
                        await interaction.followup.send(f"❌ 資格不符：限職業【{r_item}】！", ephemeral=True)
                        return
                if "性別" in r_item and char_row['gender'] not in r_item:
                    await interaction.followup.send(f"❌ 資格不符：限性別【{r_item}】！", ephemeral=True)
                    return
                if "勢力" in r_item and char_row['faction'] not in r_item:
                    await interaction.followup.send(f"❌ 資格不符：限勢力【{r_item}】！", ephemeral=True)
                    return

        # 檢驗限時
        if matched_quest['time_limit'] and "～" in matched_quest['time_limit']:
            try:
                end_str = matched_quest['time_limit'].split("～")[1].strip()
                if datetime.now() > datetime.strptime(end_str, "%Y/%m/%d %H:%M"):
                    await interaction.followup.send(f"❌ 該任務已於 `{end_str}` 截止！", ephemeral=True)
                    return
            except Exception:
                pass

        done = await conn.fetchrow("SELECT 1 FROM quest_completions WHERE guild_id = $1 AND char_name = $2 AND quest_title = $3", g_id, 角色名, matched_quest['title'])
        if done:
            await interaction.followup.send(f"⚠️ 角色 **{角色名}** 已完成過此任務，不可重複回報！", ephemeral=True)
            return

        if matched_quest['reward_cash'] > 0:
            await conn.execute("UPDATE characters SET bank = bank + $1 WHERE guild_id = $2 AND name = $3", matched_quest['reward_cash'], g_id, 角色名)

        items = json.loads(matched_quest['reward_items']) if matched_quest['reward_items'] else []
        for it in items:
            it_name, it_amt = it.get("name"), it.get("amount", 1)
            inv_row = await conn.fetchrow("SELECT id FROM inventory WHERE guild_id = $1 AND owner_name = $2 AND item_name = $3", g_id, 角色名, it_name)
            if inv_row:
                await conn.execute("UPDATE inventory SET amount = amount + $1 WHERE id = $2", it_amt, inv_row['id'])
            else:
                await conn.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES ($1, $2, $3, $4, '任務獎勵')", g_id, 角色名, it_name, it_amt)

        await conn.execute("""
            INSERT INTO quest_completions (guild_id, char_name, quest_title, level_tag, completed_at)
            VALUES ($1, $2, $3, $4, $5)
        """, g_id, 角色名, matched_quest['title'], matched_quest['level_tag'], time.time())

    tag_msg = f" ｜ 標籤：`{matched_quest['level_tag']}`" if matched_quest['level_tag'] else ""
    stat_text = f"、+ 數值{matched_quest['reward_stats']}" if matched_quest['reward_stats'] else ""
    await interaction.followup.send(f"‼️ 任務確認完成\n獎勵：$ {matched_quest['reward_cash']:,}{stat_text}{tag_msg}\n恭喜 {interaction.user.mention} 的【{角色名}】完成任務《{matched_quest['title']}》！✅")
    await check_and_promote_rank(g_id, 角色名, interaction.channel)

# -------------------- 管理員專用指令 (均嚴格限制權限) --------------------

@bot.tree.command(name="檔案總覽", description="【管理員專用】列出本伺服器所有角色與 NPC 檔案名冊")
@app_commands.default_permissions(administrator=True)
async def admin_overview(interaction: discord.Interaction):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        chars = await conn.fetch("SELECT name, age, gender, job, faction, cash, bank, rank_name FROM characters WHERE guild_id = $1 ORDER BY rank_order ASC", g_id)
        npcs = await conn.fetch("SELECT name, age, gender, identity, cash, bank, rank_name FROM npcs WHERE guild_id = $1 ORDER BY rank_order ASC", g_id)

    embed = discord.Embed(title=f"📋【{interaction.guild.name}】全服藝人與 NPC 名錄總覽", color=0x9B59B6)
    
    char_lines = [f"• **{c['name']}** ｜ 👑 {c['rank_name']} ｜ {c['age']}歲 / {c['gender']} / {c['job']} ｜ 現金:${c['cash']:,} / 銀行:${c['bank']:,}" for c in chars]
    embed.add_field(name=f"👥 玩家角色清單 ({len(chars)} 位)", value="\n".join(char_lines[:15]) if char_lines else "目前尚無角色", inline=False)

    npc_lines = [f"• 👤 **{n['name']}** ｜ 👑 {n['rank_name']} ｜ {n['age']}歲 / {n['gender']} / {n['identity']} ｜ 現金:${n['cash']:,} / 銀行:${n['bank']:,}" for n in npcs]
    embed.add_field(name=f"🎭 官方 NPC 名冊 ({len(npcs)} 位)", value="\n".join(npc_lines[:15]) if npc_lines else "目前尚無 NPC", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="咖位等級限制", description="【管理員專用】設定咖位階級、作品、代言與數值限制（支援連結解析與修改）")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作選項=[
    app_commands.Choice(name="增加（貼上限制連結自動解析）", value="add"),
    app_commands.Choice(name="修改（手動微調指定級別條件）", value="modify"),
])
@app_commands.describe(
    操作選項="選擇增加或修改",
    順序="咖位數字級別 (1最頂流、2、3次之...)",
    咖位等級="階級名稱 (如: 頂流天王、一線大咖)",
    作品限制="如: 5部電影、2部電視劇 (修改模式填寫)",
    代言限制="如: 2個奢華、1個全球代言 (修改模式填寫)",
    數值限制="如: 商業價值>200、容貌>150 (修改模式填寫)",
    人數限制="名額上限 (0代表無限制)",
    限制內容連結="貼上包含規則帖子的連結 (增加模式填寫，自動抓取解析)"
)
async def manage_rank_limit(
    interaction: discord.Interaction,
    操作選項: app_commands.Choice[str],
    順序: int,
    咖位等級: str,
    作品限制: str = "",
    代言限制: str = "",
    數值限制: str = "",
    人數限制: int = 0,
    限制內容連結: str = None
):
    g_id = interaction.guild_id
    pool = await get_db_pool()

    if 操作選項.value == "add" and 限制內容連結:
        link_match = re.search(r"channels/\d+/(\d+)(?:/(\d+))?", 限制內容連結)
        if link_match:
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
            except Exception:
                pass

            w_m = re.search(r"作品(?:限制)?[:：]\s*([^\n\r]+)", post_content)
            if w_m: 作品限制 = w_m.group(1).strip()
            e_m = re.search(r"代言(?:限制)?[:：]\s*([^\n\r]+)", post_content)
            if e_m: 代言限制 = e_m.group(1).strip()
            s_m = re.search(r"數值(?:限制)?[:：]\s*([^\n\r]+)", post_content)
            if s_m: 數值限制 = s_m.group(1).strip()
            num_m = re.search(r"人數(?:限制)?[:：]\s*(\d+)", post_content)
            if num_m: 人數限制 = int(num_m.group(1))

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO rank_limits (guild_id, rank_order, rank_name, work_req, endorse_req, stat_req, max_members)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (guild_id, rank_order) DO UPDATE SET
                rank_name = $3,
                work_req = $4,
                endorse_req = $5,
                stat_req = $6,
                max_members = $7;
        """, g_id, 順序, 咖位等級.strip(), 作品限制.strip(), 代言限制.strip(), 數值限制.strip(), 人數限制)

    quota_txt = f"{人數限制} 人" if 人數限制 > 0 else "無限制"
    await interaction.response.send_message(
        f"✅ 成功儲存咖位階級！\n👑 順序：**#{順序}** ｜ 稱號：**【{咖位等級}】**\n"
        f"🎬 作品條件：{作品限制 if 作品限制 else '無'}\n"
        f"🏷️ 代言條件：{代言限制 if 代言限制 else '無'}\n"
        f"📊 數值條件：{數值限制 if 數值限制 else '無'}\n"
        f"👥 名額上限：{quota_txt}"
    )

@bot.tree.command(name="任務新增", description="【管理員專用】發布全新任務並設定獎勵、標籤與資格限制")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(選擇欄位=[
    app_commands.Choice(name="新手任務", value="新手任務"),
    app_commands.Choice(name="一般任務", value="一般任務"),
    app_commands.Choice(name="限時任務", value="限時任務"),
    app_commands.Choice(name="特殊任務", value="特殊任務"),
])
async def add_quest(
    interaction: discord.Interaction,
    選擇欄位: app_commands.Choice[str],
    任務名: str,
    獎勵說明: str,
    等級: str = "",
    限制: str = "",
    金錢獎勵: int = 0,
    數值獎勵說明: str = "",
    獎勵道具名: str = None,
    獎勵道具數量: int = 1,
    限時時間: str = None,
    回報頻道: discord.abc.GuildChannel = None
):
    g_id = interaction.guild_id
    category = 選擇欄位.value
    time_limit_str = 限時時間.strip() if 限時時間 else ""

    items = []
    if 獎勵道具名:
        items.append({"name": 獎勵道具名.strip(), "amount": 獎勵道具數量})

    rep_ch_id = 回報頻道.id if 回報頻道 else 0
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute("""
                INSERT INTO quests (guild_id, category, title, reward_desc, reward_cash, reward_items, reward_stats, time_limit, report_channel_id, level_tag, requirements)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """, g_id, category, 任務名.strip(), 獎勵說明.strip(), 金錢獎勵, json.dumps(items, ensure_ascii=False), 數值獎勵說明.strip(), time_limit_str, rep_ch_id, 等級.strip(), 限制.strip())
        except Exception:
            await interaction.response.send_message(f"❌ 任務名稱 `{任務名}` 已經存在！", ephemeral=True)
            return

    tag_txt = f"\n🏷️ 任務標籤/等級：`{等級}`" if 等級 else ""
    req_txt = f"\n⚠️ 資格限制：`{限制}`" if 限制 else ""
    await interaction.response.send_message(f"✅ 成功發布任務！\n📌 分類：【{category}】 ｜ 🏷️ 任務名：**{任務名}**{tag_txt}{req_txt}")

@bot.tree.command(name="任務修改", description="【管理員專用】修改既有任務的獎勵、標籤、限制與回報區")
@app_commands.default_permissions(administrator=True)
async def modify_quest(
    interaction: discord.Interaction,
    任務名: str,
    新獎勵說明: str = None,
    新等級: str = None,
    新限制: str = None,
    新金錢獎勵: int = None,
    新回報頻道: discord.abc.GuildChannel = None
):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        q = await conn.fetchrow("SELECT * FROM quests WHERE guild_id = $1 AND title = $2", g_id, 任務名.strip())
        if not q:
            await interaction.response.send_message(f"❌ 查無名為 `{任務名}` 的任務！", ephemeral=True)
            return

        desc = 新獎勵說明 if 新獎勵說明 is not None else q['reward_desc']
        tag = 新等級 if 新等級 is not None else q['level_tag']
        req = 新限制 if 新限制 is not None else q['requirements']
        cash = 新金錢獎勵 if 新金錢獎勵 is not None else q['reward_cash']
        ch_id = 新回報頻道.id if 新回報頻道 else q['report_channel_id']

        await conn.execute("""
            UPDATE quests SET reward_desc = $1, level_tag = $2, requirements = $3, reward_cash = $4, report_channel_id = $5
            WHERE guild_id = $6 AND title = $7
        """, desc, tag, req, cash, ch_id, g_id, 任務名.strip())

    await interaction.response.send_message(f"✅ 任務 **《{任務名}》** 資料已順利修改完成！")

@bot.tree.command(name="商店與物品增加", description="【管理員專用】新增商店商品或地圖票券")
@app_commands.default_permissions(administrator=True)
async def add_shop_item(
    interaction: discord.Interaction, 
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
            await interaction.response.send_message("❌ 建立【門票】時，必須指定「對應地圖身分組」！", ephemeral=True)
            return
        role_id = 對應地圖身分組.id
        if 商店 != "票務系統": 商店 = "票務系統"

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO shop_items (guild_id, shop_name, name, price, description, stat_bonus, affinity_bonus, usable, target_role_id, seller)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, '官方')
        """, g_id, 商店, 商品名, 價格, 簡介, 增加數值, 增加好感, usable_val, role_id)

    role_info = f"\n🗺️ 綁定身分組：{對應地圖身分組.mention}" if role_id > 0 else ""
    await interaction.response.send_message(f"✅ 已在【{商店}】新增商品：**{商品名}**！{role_info}")

@bot.tree.command(name="商店與物品修改", description="【管理員專用】修改既有商店商品價格、加成或身分組")
@app_commands.default_permissions(administrator=True)
async def modify_shop_item(
    interaction: discord.Interaction,
    商品名: str,
    新價格: int = None,
    新簡介: str = None,
    新增加數值: str = None,
    新增加好感: int = None,
    新對應身分組: discord.Role = None
):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        item = await conn.fetchrow("SELECT * FROM shop_items WHERE guild_id = $1 AND name = $2", g_id, 商品名.strip())
        if not item:
            await interaction.response.send_message(f"❌ 查無名為 `{商品名}` 的商品！", ephemeral=True)
            return

        price = 新價格 if 新價格 is not None else item['price']
        desc = 新簡介 if 新簡介 is not None else item['description']
        stat = 新增加數值 if 新增加數值 is not None else item['stat_bonus']
        aff = 新增加好感 if 新增加好感 is not None else item['affinity_bonus']
        role_id = 新對應身分組.id if 新對應身分組 else item['target_role_id']

        await conn.execute("""
            UPDATE shop_items SET price = $1, description = $2, stat_bonus = $3, affinity_bonus = $4, target_role_id = $5
            WHERE guild_id = $6 AND name = $7
        """, price, desc, stat, aff, role_id, g_id, 商品名.strip())

    await interaction.response.send_message(f"✅ 商品 **【{商品名}】** 設定已順利更新！")

@bot.tree.command(name="npc登記", description="【管理員專用】登記全新 NPC 資料")
@app_commands.default_permissions(administrator=True)
async def register_npc(interaction: discord.Interaction, 名字: str, 年齡: int, 性別: str, 身分: str, 圖像連結: str):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO npcs (guild_id, name, age, gender, identity, avatar_url, cash, bank, works, stats, rank_order, rank_name)
            VALUES ($1, $2, $3, $4, $5, $6, 0, 0, '[]', '{}', 99, '業界前輩')
            ON CONFLICT(guild_id, name) DO UPDATE SET age=$3, gender=$4, identity=$5, avatar_url=$6
        """, g_id, 名字, 年齡, 性別, 身分, 圖像連結)

    embed = discord.Embed(title=f"👤 NPC 資料登記完成：{名字}", color=0x9B59B6)
    embed.add_field(name="基本信息", value=f"{年齡} 歲 / {性別} / {身分}", inline=False)
    embed.set_thumbnail(url=圖像連結)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="npc修改", description="【管理員專用】修改既有 NPC 的基本資料或圖像")
@app_commands.default_permissions(administrator=True)
async def modify_npc(
    interaction: discord.Interaction,
    名字: str,
    新年齡: int = None,
    新性別: str = None,
    新身分: str = None,
    新圖像連結: str = None,
    新咖位稱號: str = None,
    新咖位順序: int = None
):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        npc = await conn.fetchrow("SELECT * FROM npcs WHERE guild_id = $1 AND name = $2", g_id, 名字.strip())
        if not npc:
            await interaction.response.send_message(f"❌ 查無名為 `{名字}` 的 NPC！", ephemeral=True)
            return

        age = 新年齡 if 新年齡 is not None else npc['age']
        gender = 新性別 if 新性別 is not None else npc['gender']
        ident = 新身分 if 新身分 is not None else npc['identity']
        avatar = 新圖像連結 if 新圖像連結 is not None else npc['avatar_url']
        r_name = 新咖位稱號 if 新咖位稱號 is not None else npc['rank_name']
        r_order = 新咖位順序 if 新咖位順序 is not None else npc['rank_order']

        await conn.execute("""
            UPDATE npcs SET age = $1, gender = $2, identity = $3, avatar_url = $4, rank_name = $5, rank_order = $6
            WHERE guild_id = $7 AND name = $8
        """, age, gender, ident, avatar, r_name, r_order, g_id, 名字.strip())

    await interaction.response.send_message(f"✅ NPC **{名字}** 資料修改成功！")

@bot.tree.command(name="薪水", description="【管理員專用】發放薪水入角色或 NPC 的手頭現金 (無須綁定身分)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(名字="發薪對象（玩家角色名或 NPC 名字皆可）", 金額="發放的薪水金額 (純整數)")
async def salary_cmd(interaction: discord.Interaction, 名字: str, 金額: int):
    g_id = interaction.guild_id
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額必須大於 0！", ephemeral=True)
        return

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        target = await conn.fetchrow("SELECT name FROM characters WHERE guild_id = $1 AND name = $2", g_id, 名字.strip())
        tbl = "characters"
        if not target:
            target = await conn.fetchrow("SELECT name FROM npcs WHERE guild_id = $1 AND name = $2", g_id, 名字.strip())
            tbl = "npcs"

        if not target:
            await interaction.response.send_message(f"❌ 查無名為 `{名字}` 的角色或 NPC！", ephemeral=True)
            return

        await conn.execute(f"UPDATE {tbl} SET cash = cash + $1 WHERE guild_id = $2 AND name = $3", 金額, g_id, 名字.strip())

    await interaction.response.send_message(f"💵 薪水 **${金額:,}** 已成功匯入【{名字}】的現金錢包！")

@bot.tree.command(name="利息調整", description="【管理員專用】每 168 小時調整一次利率")
@app_commands.default_permissions(administrator=True)
async def set_interest(interaction: discord.Interaction, 利率百分比: float):
    g_id = interaction.guild_id
    now = time.time()
    one_week = 168 * 3600

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM system_settings WHERE guild_id = $1 AND key = 'last_rate_update'", g_id)
        last_update = float(row['value']) if row else 0

        if now - last_update < one_week:
            remain_h = int((one_week - (now - last_update)) / 3600)
            await interaction.response.send_message(f"⏳ 利率調整冷卻中！還需等待約 **{remain_h}** 小時。", ephemeral=True)
            return

        new_rate = 利率百分比 / 100.0
        await conn.execute("INSERT INTO system_settings (guild_id, key, value) VALUES ($1, 'interest_rate', $2) ON CONFLICT(guild_id, key) DO UPDATE SET value = $2", g_id, str(new_rate))
        await conn.execute("INSERT INTO system_settings (guild_id, key, value) VALUES ($1, 'last_rate_update', $2) ON CONFLICT(guild_id, key) DO UPDATE SET value = $2", g_id, str(now))

    await interaction.response.send_message(f"📈 銀行利率已調整為 **{利率百分比}%**！")

@bot.tree.command(name="數值登記", description="為角色或 NPC 登記/調整數值，或貼人設單自動解析")
@app_commands.describe(名字="角色或 NPC 名稱", 數值="數值名稱 (貼人設單填'自動')", 數字="增減點數 (人設單填 0)", 人設單連結="帖子/訊息連結")
async def register_stats_cmd(
    interaction: discord.Interaction,
    名字: str,
    數值: str = "自動",
    數字: int = 0,
    人設單連結: str = None
):
    g_id = interaction.guild_id
    await interaction.response.defer(ephemeral=True)

    target_name = 名字.strip()
    is_npc = False
    stats_json = "{}"

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id, stats FROM characters WHERE guild_id = $1 AND name = $2", g_id, target_name)
        if row:
            if row['user_id'] != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ 你只能為自己持有的角色登記數值！", ephemeral=True)
                return
            stats_json = row['stats']
        else:
            npc_row = await conn.fetchrow("SELECT stats FROM npcs WHERE guild_id = $1 AND name = $2", g_id, target_name)
            if npc_row:
                if not interaction.user.guild_permissions.administrator:
                    await interaction.followup.send("❌ 僅伺服器管理員可為官方 NPC 登記數值！", ephemeral=True)
                    return
                is_npc = True
                stats_json = npc_row['stats'] if npc_row['stats'] else "{}"
            else:
                await interaction.followup.send(f"❌ 查無名為 `{target_name}` 的角色或官方 NPC！", ephemeral=True)
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
                await interaction.followup.send(f"❌ 無法讀取文章內容：`{e}`", ephemeral=True)
                return

            if not is_npc:
                cash_match = re.search(r"(?:流光幣|現金|持有金錢)[^\d]*(\d+)", post_content)
                if cash_match:
                    await conn.execute("UPDATE characters SET cash = $1 WHERE guild_id = $2 AND name = $3", int(cash_match.group(1)), g_id, target_name)

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
            await conn.execute(f"UPDATE {tbl} SET stats = $1 WHERE guild_id = $2 AND name = $3", json.dumps(char_stats, ensure_ascii=False), g_id, target_name)

            tag = "［NPC］" if is_npc else ""
            await interaction.followup.send(f"🎉 {tag}**{target_name}** 人設單數值已自動同步完畢！\n📊 錄入：{'、'.join(added_records[:8])} 等。")
            await check_and_promote_rank(g_id, target_name, interaction.channel)
            return

        if 數值 == "自動":
            await interaction.followup.send("❌ 請輸入數值名稱或貼上人設單連結！", ephemeral=True)
            return

        char_stats[數值] = char_stats.get(數值, 0) + 數字
        tbl = "npcs" if is_npc else "characters"
        await conn.execute(f"UPDATE {tbl} SET stats = $1 WHERE guild_id = $2 AND name = $3", json.dumps(char_stats, ensure_ascii=False), g_id, target_name)

        tag = "［NPC］" if is_npc else ""
        sign = "+" if 數字 >= 0 else ""
        await interaction.followup.send(f"✅ 已為 {tag}**{target_name}** 更新數值！【{數值} {sign}{數字}】（當前值：{char_stats[數值]}）")
        await check_and_promote_rank(g_id, target_name, interaction.channel)

@bot.tree.command(name="新增榜單", description="【管理員專用】新增全城競爭排行榜單 (可放算式)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(榜單名字="榜單名稱", 相關數值="排名計算屬性或算式 (例如: 商業價值 * 1.5 + 影響指數 * 2)")
async def create_leaderboard(interaction: discord.Interaction, 榜單名字: str, 相關數值: str):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO leaderboards (guild_id, name, stat_key) VALUES ($1, $2, $3)", g_id, 榜單名字.strip(), 相關數值.strip())

    await interaction.response.send_message(f"🏆 成功建立榜單：**【{榜單名字}】**（依據：`{相關數值}`）！")

class LeaderboardView(discord.ui.View):
    def __init__(self, target_char: str = None, guild_id: int = None):
        super().__init__(timeout=180)
        self.target_char = target_char
        self.guild_id = guild_id

    @discord.ui.button(label="📜 完整榜單", style=discord.ButtonStyle.primary)
    async def full_board(self, interaction: discord.Interaction, button: discord.ui.Button):
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            boards = await conn.fetch("SELECT name, stat_key FROM leaderboards WHERE guild_id = $1", self.guild_id)

        if not boards:
            await interaction.response.send_message("📋 目前本伺服器尚未建立任何榜單！", ephemeral=True)
            return

        parent_guild = self.guild_id

        class BoardSelect(discord.ui.Select):
            def __init__(self):
                opts = [
                    discord.SelectOption(label=b['name'], description=f"依據：{b['stat_key'][:50]}", value=f"{b['name']}:{b['stat_key']}")
                    for b in boards[:25]
                ]
                super().__init__(placeholder="請選擇欲調閱的排行榜單...", options=opts)

            async def callback(self, inter: discord.Interaction):
                b_name, formula = self.values[0].split(":", 1)
                p = await get_db_pool()
                async with p.acquire() as conn:
                    player_chars = await conn.fetch("SELECT name, stats FROM characters WHERE guild_id = $1", parent_guild)
                    npc_chars = await conn.fetch("SELECT name, stats FROM npcs WHERE guild_id = $1", parent_guild)

                ranked = []
                for r in player_chars:
                    st = json.loads(r['stats']) if r['stats'] else {}
                    ranked.append((r['name'], eval_stat_formula(formula, st), False))

                for r in npc_chars:
                    st = json.loads(r['stats']) if r['stats'] else {}
                    ranked.append((r['name'], eval_stat_formula(formula, st), True))

                ranked.sort(key=lambda x: x[1], reverse=True)

                embed = discord.Embed(title=f"🏆【{b_name}】全城排名 (含 NPC)", color=0xF1C40F)
                lines = []
                medals = ["🥇", "🥈", "🥉"]
                for i, (cname, val, is_npc) in enumerate(ranked[:15]):
                    prefix = medals[i] if i < 3 else f"`#{i+1}`"
                    npc_tag = " `[NPC]`" if is_npc else ""
                    lines.append(f"{prefix} **{cname}**{npc_tag} ｜ 總積分：**{val:,}**")

                embed.description = "\n".join(lines) if lines else "暫無數據"
                embed.set_footer(text=f"計分公式：{formula} ｜ 標註 [NPC] 為城內官方 NPC。")
                await inter.response.send_message(embed=embed, ephemeral=True)

        v = discord.ui.View()
        v.add_item(BoardSelect())
        await interaction.response.send_message("請選擇想查閱的榜單：", view=v, ephemeral=True)

    @discord.ui.button(label="👤 個人/NPC 排名", style=discord.ButtonStyle.secondary)
    async def personal_rank(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.target_char:
            await interaction.response.send_message("⚠️ 請於發送指令時指定【名字】，以便查詢該角色或 NPC 的名次！", ephemeral=True)
            return

        pool = await get_db_pool()
        async with pool.acquire() as conn:
            boards = await conn.fetch("SELECT name, stat_key FROM leaderboards WHERE guild_id = $1", self.guild_id)
            all_chars = await conn.fetch("SELECT name, stats FROM characters WHERE guild_id = $1", self.guild_id)
            all_npcs = await conn.fetch("SELECT name, stats FROM npcs WHERE guild_id = $1", self.guild_id)

        if not boards:
            await interaction.response.send_message("📋 尚未建立任何榜單！", ephemeral=True)
            return

        combined_names = {c['name'] for c in all_chars} | {n['name'] for n in all_npcs}
        if self.target_char not in combined_names:
            await interaction.response.send_message(f"❌ 查無名為 `{self.target_char}` 的角色或 NPC！", ephemeral=True)
            return

        embed = discord.Embed(title=f"📊【{self.target_char}】各榜單排行成績", color=0x3498DB)
        lines = []

        for b in boards:
            b_name, formula = b['name'], b['stat_key']
            ranked = []
            for r in all_chars:
                st = json.loads(r['stats']) if r['stats'] else {}
                ranked.append((r['name'], eval_stat_formula(formula, st)))
            for r in all_npcs:
                st = json.loads(r['stats']) if r['stats'] else {}
                ranked.append((r['name'], eval_stat_formula(formula, st)))

            ranked.sort(key=lambda x: x[1], reverse=True)

            rank_pos = "未入榜"
            val = 0
            for idx, (cname, score) in enumerate(ranked):
                if cname == self.target_char:
                    rank_pos = f"第 **{idx + 1}** 名"
                    val = score
                    break
            lines.append(f"• **{b_name}**：{rank_pos} ｜ 得分：`{val:,}`")

        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="排行查詢", description="查詢各項名人榜單或查看個人/NPC 的各項榜單名次")
@app_commands.describe(名字="若要查看個人或 NPC 排名，請填寫對應名稱")
async def rank_query(interaction: discord.Interaction, 名字: str = None):
    view = LeaderboardView(target_char=名字, guild_id=interaction.guild_id)
    await interaction.response.send_message("🏆 請選擇你想查看的排行形式：", view=view, ephemeral=True)

@bot.tree.command(name="獎勵登記", description="【管理員專用】下發綜合獎勵（金錢入銀行、物品入背包、數值加總）")
@app_commands.default_permissions(administrator=True)
async def admin_reward(
    interaction: discord.Interaction,
    角色名: str,
    金錢: int = 0,
    物品名稱: str = None,
    物品數量: int = 1,
    數值名稱: str = None,
    數值點數: int = 0
):
    g_id = interaction.guild_id
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        char_row = await conn.fetchrow("SELECT stats FROM characters WHERE guild_id = $1 AND name = $2", g_id, 角色名)
        tbl = "characters"
        if not char_row:
            char_row = await conn.fetchrow("SELECT stats FROM npcs WHERE guild_id = $1 AND name = $2", g_id, 角色名)
            tbl = "npcs"

        if not char_row:
            await interaction.response.send_message(f"❌ 查無角色或 NPC `{角色名}`！", ephemeral=True)
            return

        stats = json.loads(char_row['stats']) if char_row['stats'] else {}
        reward_msgs = []

        if 金錢 > 0:
            await conn.execute(f"UPDATE {tbl} SET bank = bank + $1 WHERE guild_id = $2 AND name = $3", 金錢, g_id, 角色名)
            reward_msgs.append(f"💰 銀行存款 +${金錢:,}")

        if 物品名稱:
            inv_row = await conn.fetchrow("SELECT id FROM inventory WHERE guild_id = $1 AND owner_name = $2 AND item_name = $3", g_id, 角色名, 物品名稱)
            if inv_row:
                await conn.execute("UPDATE inventory SET amount = amount + $1 WHERE id = $2", 物品數量, inv_row['id'])
            else:
                await conn.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES ($1, $2, $3, $4, '管理員獎勵')", g_id, 角色名, 物品名稱, 物品數量)
            reward_msgs.append(f"📦 物品 **{物品名稱}** ×{物品數量}")

        if 數值名稱 and 數值點數 != 0:
            stats[數值名稱] = stats.get(數值名稱, 0) + 數值點數
            await conn.execute(f"UPDATE {tbl} SET stats = $1 WHERE guild_id = $2 AND name = $3", json.dumps(stats, ensure_ascii=False), g_id, 角色名)
            reward_msgs.append(f"✨ 數值【{數值名稱}】+{數值點數} (總計: {stats[數值名稱]})")

    await interaction.response.send_message(f"🎁 管理員已成功為【{角色名}】發放獎勵：\n{' ｜ '.join(reward_msgs) if reward_msgs else '無實質資產發放'}")
    await check_and_promote_rank(g_id, 角色名, interaction.channel)

# -------------------- 清理與同步指令 --------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def clean_guild(ctx):
    bot.tree.clear_commands(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send("🧹 重複指令已清空！伺服器專屬副本已刪除。")

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

# -------------------- 啟動事件 --------------------
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
        print(f"====================================")
    except Exception as e:
        print(f"❌ 同步指令失敗: {e}")

    print(f"流光城系統已就緒（完整咖位與管理員權限控制版）：{bot.user}")

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
