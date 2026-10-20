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


# -------------------- 資料庫完整初始化 --------------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. 角色表（加入 image_url 支援大頭照）
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
                image_url TEXT DEFAULT '',
                PRIMARY KEY (guild_id, name)
            )
        """)
        # 自動為舊資料庫補上欄位防報錯
        try:
            await db.execute("ALTER TABLE characters ADD COLUMN image_url TEXT DEFAULT ''")
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
        # 3. 官方/二手/各類商店道具表
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
        # 4. 可購置之車輛與房產目錄表
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
        # 5. 個人持有之產權表（車輛與房產）
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
        # 6. 交際傾向關係表
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
        # 8. 審核兩段式紀錄表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                guild_id INTEGER,
                message_link TEXT,
                char_name TEXT,
                audit_count INTEGER DEFAULT 1,
                PRIMARY KEY (guild_id, message_link)
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
        # 11. 陣營成員與貢獻紀錄
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
        # 12. 陣營作品抽成扣款紀錄表（保證單作品扣稅一次）
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
        # 15. 排行榜公式表
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
        # 17. 門票外地簽證時效表
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
        # 18. 大眾路人相冊與姓名資源庫
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
                region TEXT,       -- '東方' 或 '西方'
                name_type TEXT,    -- 'surname' (姓氏) 或 'firstname' (名字)
                gender TEXT DEFAULT '通用',
                val TEXT
            )
        """)
        # 擴充 characters 欄位（國籍、身高）
        try:
            await db.execute("ALTER TABLE characters ADD COLUMN nationality TEXT DEFAULT '本國'")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE characters ADD COLUMN height INTEGER DEFAULT 170")
        except Exception:
            pass
                    # 19. 標籤規則庫（條件與衝突）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tag_rules (
                tag_name TEXT PRIMARY KEY,
                gender_req TEXT DEFAULT '無', -- '男', '女', '無'
                min_age INTEGER DEFAULT 0,
                max_age INTEGER DEFAULT 99,
                conflict_tags TEXT DEFAULT '', -- 逗號隔開的互斥標籤
                is_negative INTEGER DEFAULT 0
            )
        """)
        # 20. 角色傳聞紀錄表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rumors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                char_name TEXT,
                content TEXT,
                created_at REAL
            )
        """)
        # 21. 寵物檔案表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                owner_name TEXT,
                pet_type TEXT,       -- 如: 貓、狗、兔、鳥
                pet_name TEXT,       -- 玩家取的暱稱
                health INTEGER DEFAULT 500,
                lifespan_days INTEGER,
                bought_at REAL,
                status TEXT DEFAULT '活潑健康', -- '活潑健康', '病危', '已故'
                funeral_pending INTEGER DEFAULT 0 -- 1 表示等待辦喪禮
            )
        """)
        # 22. 傳聞關鍵字計數
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rumor_keyword_counts (
                guild_id INTEGER,
                char_name TEXT,
                tag_name TEXT,
                count INTEGER DEFAULT 1,
                PRIMARY KEY (guild_id, char_name, tag_name)
            )
        """)
        await db.commit()
# -------------------- 完整標籤池與互斥設定 --------------------
DEFAULT_TAG_DATA = [
    # 標籤名, 性別限制, 最小年齡, 最大年齡, 互斥標籤字串, 是否負面
    ("初戀臉", "無", 0, 30, "濃顏,厭世感", 0),
    ("厭世感", "無", 0, 99, "元氣犬系,初戀臉", 0),
    ("舞台匠人", "無", 0, 99, "花瓶", 0),
    ("釣系", "無", 18, 99, "老幹部", 0),
    ("全能天才", "無", 0, 99, "文盲,花瓶", 0),
    ("天籟蜜嗓", "無", 0, 99, "", 0),
    ("極致反差", "無", 0, 99, "", 0),
    ("低音砲", "男", 16, 99, "", 0),
    ("古典氣質", "無", 0, 99, "", 0),
    ("漫撕人", "無", 0, 35, "", 0),
    ("高嶺之花", "無", 0, 99, "社恐", 0),
    ("元氣犬系", "無", 0, 28, "厭世感,老幹部", 0),
    ("性感", "無", 18, 99, "少年感", 0),
    ("緋聞纏身", "無", 0, 99, "", 0),
    ("濃顏", "無", 0, 99, "淡顏", 0),
    ("淡顏", "無", 0, 99, "濃顏", 0),
    ("臉蛋天才", "無", 0, 99, "", 0),
    ("少年感", "男", 16, 25, "老幹部,性感", 0),
    ("社恐", "無", 0, 99, "社交悍匪", 0),
    ("社交悍匪", "無", 0, 99, "社恐", 0),
    ("老幹部", "無", 30, 99, "少年感,元氣犬系", 0),
    ("人間清醒", "無", 0, 99, "文盲", 0),
    ("毒舌", "無", 0, 99, "", 0),
    ("劇拋臉", "無", 0, 99, "花瓶", 0),
    ("鬆弛感", "無", 0, 99, "", 0),
    ("百億少年的夢", "女", 18, 35, "", 0),
    ("文盲", "無", 0, 99, "全能天才,人間清醒", 1),
    ("花瓶", "無", 0, 99, "舞台匠人,劇拋臉,全能天才", 1)
]

async def sync_default_tags():
    async with aiosqlite.connect(DB_PATH) as db:
        for t_name, gen, min_a, max_a, confs, neg in DEFAULT_TAG_DATA:
            await db.execute("""
                INSERT INTO tag_rules (tag_name, gender_req, min_age, max_age, conflict_tags, is_negative)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tag_name) DO NOTHING
            """, (t_name, gen, min_a, max_a, confs, neg))
        await db.commit()
# 處理標籤更新（含衝突覆蓋、年齡性別檢驗、上限5個）
async def apply_character_tag(guild_id: int, char_name: str, new_tag: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT age, gender, tags FROM characters WHERE guild_id = ? AND name = ?", (guild_id, char_name)) as cur:
            c_row = await cur.fetchone()
        if not c_row:
            return ""
        age, gender, cur_tags_str = c_row

        async with db.execute("SELECT gender_req, min_age, max_age, conflict_tags FROM tag_rules WHERE tag_name = ?", (new_tag,)) as cur:
            rule = await cur.fetchone()

        if rule:
            g_req, min_a, max_a, conflict_str = rule
            if g_req != '無' and g_req != gender:
                return f"（性別不符【{new_tag}】條件）"
            if not (min_a <= age <= max_a):
                return f"（年齡不符【{new_tag}】範圍）"
            conflicts = [c.strip() for c in conflict_str.split(",") if c.strip()]
        else:
            conflicts = []

        cur_tags = [t.strip() for t in cur_tags_str.split("、") if t.strip()]

        if new_tag in cur_tags:
            return ""

        # 移除衝突標籤
        removed = []
        for c in conflicts:
            if c in cur_tags:
                cur_tags.remove(c)
                removed.append(c)

        # 超過 5 個時擠掉最早的標籤
        if len(cur_tags) >= 5:
            cur_tags.pop(0)

        cur_tags.append(new_tag)
        new_tag_str = "、".join(cur_tags)

        await db.execute("UPDATE characters SET tags = ? WHERE guild_id = ? AND name = ?", (new_tag_str, guild_id, char_name))
        await db.commit()

        remove_notice = f"（互斥頂替掉：`{'/'.join(removed)}`）" if removed else ""
        return f"\n🏷️ **標籤動態蛻變**：傳聞四起！**{char_name}** 獲得了新標籤【**{new_tag}**】！{remove_notice}"

# -------------------- 每 48 小時：全體路人動態行情與數值浮動 --------------------
@tasks.loop(hours=48)
async def crowd_npc_fluctuation_task():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT guild_id FROM characters WHERE is_npc = 3") as cur:
            guild_rows = await cur.fetchall()

        for (g_id,) in guild_rows:
            async with db.execute("SELECT key, value FROM system_settings WHERE guild_id = ?", (g_id,)) as cur:
                settings = dict(await cur.fetchall())

            mode = settings.get("npc_fluct_mode", "percent") # 'percent' 或 'fixed'
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
# -------------------- 寵物狀態每日檢測（扣健康值與壽命檢查） --------------------
@tasks.loop(hours=24)
async def pet_health_decay_task():
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. 每日扣 5 點健康
        await db.execute("UPDATE pets SET health = MAX(0, health - 5) WHERE status != '已故'")
        
        # 2. 檢查健康度歸零或壽命到期
        async with db.execute("SELECT id, guild_id, owner_name, pet_name, lifespan_days, bought_at, health FROM pets WHERE status != '已故'") as cur:
            all_pets = await cur.fetchall()

        for p_id, g_id, owner, pet_name, lifespan, bought_at, hp in all_pets:
            days_passed = (now - bought_at) / 86400.0
            if hp <= 0 or days_passed >= lifespan:
                await db.execute("UPDATE pets SET status = '已故', funeral_pending = 1 WHERE id = ?", (p_id,))
                
                # 發送喪禮通知給玩家
                async with db.execute("SELECT user_id FROM characters WHERE guild_id = ? AND name = ?", (g_id, owner)) as u_cur:
                    u_row = await u_cur.fetchone()
                
                if u_row:
                    user = bot.get_user(u_row[0])
                    if user:
                        try:
                            msg = (
                                f"🕊️ **【寵物離世訃告】**\n"
                                f"親愛的 **{owner}**，你的愛寵【**{pet_name}**】走到了生命的終點，悄悄回汪喵星球了……\n\n"
                                f"是否願意為牠舉辦一場告別喪禮？\n"
                                f"若選擇舉辦，請撰寫一篇喪禮哀悼文章，並在該文章中 `@機器人`。\n"
                                f"結算時將為你賦予大量路人緣與死忠粉絲，並有機會獲得動物公益大使工作邀約。"
                            )
                            await user.send(msg)
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
async def on_message(message: discord.Message):
            # 檢查是否有等待喪禮的寵物
        async with db.execute("SELECT id, pet_name FROM pets WHERE guild_id = ? AND owner_name = (SELECT name FROM characters WHERE user_id = ? LIMIT 1) AND funeral_pending = 1", (g_id, message.author.id)) as p_cur:
            pending_pet = await p_cur.fetchone()

        funeral_bonus = ""
        if pending_pet and any(w in target_text for w in ["喪禮", "告別", "一路好走", "紀念", "悼念", "寵物", pending_pet[1]]):
            pet_id, p_name = pending_pet
            # 結算路人緣、熱度與死忠粉
            await db.execute("""
                UPDATE characters
                SET stats = json_set(
                    json_set(stats, '$.路人緣', CAST(COALESCE(json_extract(stats, '$.路人緣'), 0) + 150 AS INTEGER)),
                    '$.流量熱度', CAST(COALESCE(json_extract(stats, '$.流量熱度'), 0) + 200 AS INTEGER)
                ) WHERE guild_id = ? AND user_id = ?
            """, (g_id, message.author.id))
            await db.execute("UPDATE pets SET funeral_pending = 0 WHERE id = ?", (pet_id,))

            # 10% 機率獲得動物收容所邀約
            if random.random() <= 0.10:
                honor_entry = {"category": "榮譽", "title": "動物保護公益推廣大使", "extra": "善心善意 ｜ 官方特邀"}
                async with db.execute("SELECT works, name FROM characters WHERE guild_id = ? AND user_id = ?", (g_id, message.author.id)) as w_cur:
                    w_row = await w_cur.fetchone()
                    works = json.loads(w_row[0]) if w_row and w_row[0] else []
                    works.append(honor_entry)
                    await db.execute("UPDATE characters SET works = ? WHERE guild_id = ? AND name = ?", (json.dumps(works, ensure_ascii=False), g_id, w_row[1]))
                funeral_bonus = f"\n\n🕯️ **【告別善緣】** 愛寵【{p_name}】的喪禮感動了全城大眾！\n• 獲得：**路人緣 +150**、**流量熱度 +200**\n🌟 **【奇蹟機遇 (10%)】** 觸發！受流光城動物保護基金會邀請，榮獲特聘頭銜：【**動物保護公益推廣大使**】！"
            else:
                funeral_bonus = f"\n\n🕯️ **【愛寵告別】** 圓滿完成了愛寵【{p_name}】的告別喪禮。獲得：**路人緣 +150**、**流量熱度 +200**！"

            await db.commit()

        # 最後將 funeral_bonus 加在回覆訊息尾部
        reply_msg += funeral_bonus

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
    年齡="純數字 (例如: 22)",
    身高="純數字 (單位: cm，例如: 180)",
    性別="性別",
    國籍="角色國籍 (例如: 中國、英國、美籍華裔等)",
    職業身分="職業或目前身分",
    標籤="個人特質標籤 (例如: 實力派, 厭世臉)",
    感情狀況="選填 (例如: 單身, 隱婚, 熱戀中)",
    照片連結="選填：貼上角色立繪或大頭照的圖片網址"
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
    標籤: str,
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
                relationship_status, created_at, is_npc, image_url, height, nationality
            ) VALUES (?, ?, ?, ?, ?, ?, '無', ?, ?, ?, ?, ?, ?, ?)
        """, (
            g_id, interaction.user.id, target_name, 年齡, 性別, 職業身分, 標籤,
            感情狀況, time.time(), is_npc_val, 照片連結.strip(), 身高, 國籍.strip()
        ))
        await db.commit()

    label = "玩家角色" if is_npc_val == 0 else "玩家自製 NPC"
    embed = discord.Embed(title=f"🎉【{label}】建檔成功", color=0x2ECC71)
    embed.add_field(name="姓名與基本資訊", value=f"**{target_name}** ({年齡}歲 / {性別})\n• 身高：`{身高} cm` ｜ 國籍：`{國籍.strip()}`", inline=False)
    embed.add_field(name="身分職業", value=f"{職業身分}", inline=True)
    embed.add_field(name="標籤與感情", value=f"`{標籤}` ｜ {感情狀況}", inline=True)
    if 照片連結.strip().startswith("http"):
        embed.set_thumbnail(url=照片連結.strip())

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="官方npc登記", description="【管理員專用】登記官方全域 NPC 檔案")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    名字="NPC 姓名",
    年齡="年齡",
    身高="純數字 (單位: cm，例如: 185)",
    性別="性別",
    國籍="NPC 國籍",
    職業身分="官方身分或職業",
    標籤="NPC 專屬標籤",
    感情狀況="選填 (預設未知)",
    照片連結="選填：貼上官方 NPC 的形象立繪或頭像連結"
)
async def register_official_npc(
    interaction: discord.Interaction,
    名字: str,
    年齡: int,
    身高: int,
    性別: str,
    國籍: str,
    職業身分: str,
    標籤: str,
    感情狀況: str = "未知",
    照片連結: str = ""
):
    g_id = interaction.guild_id
    target_name = 名字.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO characters (
                guild_id, user_id, name, age, gender, job, faction, tags,
                relationship_status, created_at, is_npc, image_url, height, nationality
            ) VALUES (?, 0, ?, ?, ?, ?, '官方勢力', ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(guild_id, name) DO UPDATE SET
                age = excluded.age, gender = excluded.gender, job = excluded.job,
                tags = excluded.tags, relationship_status = excluded.relationship_status,
                image_url = excluded.image_url, height = excluded.height, nationality = excluded.nationality
        """, (
            g_id, target_name, 年齡, 性別, 職業身分, 標籤,
            感情狀況, time.time(), 照片連結.strip(), 身高, 國籍.strip()
        ))
        await db.commit()

    embed = discord.Embed(title=f"👑 官方 NPC 登記完畢：【{target_name}】", color=0x9B59B6)
    embed.add_field(name="基本檔案", value=f"{年齡}歲 ｜ {性別} ｜ `{身高} cm` ｜ 國籍：`{國籍.strip()}`", inline=False)
    embed.add_field(name="身分與特質", value=f"• 職業：{職業身分}\n• 標籤：`{標籤}`", inline=True)
    if 照片連結.strip().startswith("http"):
        embed.set_thumbnail(url=照片連結.strip())

    await interaction.response.send_message(embed=embed)


# -------------------- 指令：/檔案更新（完整階層流程） --------------------
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
                f"3️⃣ **查看任務列表**：使用 `/任務` 查看全城看板，完成新手任務！\n\n"
                f"*管理員提示：二次使用本指令即可自動套算數值並發放初始金幣。*"
            )
            await interaction.response.send_message(embed=embed)

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

# -------------------- 指令：/資產系統（車房選購、扣款入庫與公司創立/加入） --------------------
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

# -------------------- 指令：/公司（含品牌門市設立與上架） --------------------
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

        # 1. 年度經營結算
        async def run_cb(inter: discord.Interaction):
            revenue = random.randint(50000, 200000)
            cost = int(revenue * 0.3)
            profit = revenue - cost
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE companies SET balance = balance + ? WHERE id = ?", (profit, comp_id))
                await db.commit()
            await inter.response.send_message(f"📊 【{comp_name}】年度經營結算：\n• 總營收：+${revenue:,}\n• 營運支出：-${cost:,}\n• 實質盈餘入庫：**+${profit:,}**！")

        # 2. 規則修正
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
                    await m_inter.response.send_message(f"✅ 公司規章已更新！分成比例調整為 `{int(s_val*100)}%`，收納身分限制為 `{j_val or '無限制'}`！", ephemeral=True)

            await inter.response.send_modal(RuleModal())

        # 3. 設立/管理旗下品牌商店與商品上架
        async def shop_cb(inter: discord.Interaction):
            class AddProductModal(discord.ui.Modal, title=f"【{comp_name}】品牌門市商品上架"):
                p_name = discord.ui.TextInput(label="商品名稱", placeholder="例如: 聯名訂製香水、高階訓練教程")
                p_price = discord.ui.TextInput(label="販售單價 (純數字)", placeholder="例如: 15000")
                p_desc = discord.ui.TextInput(label="商品介紹", placeholder="例如: 使用後散發迷人氣質")
                p_bonus = discord.ui.TextInput(label="使用獲得數值 (選填)", placeholder="例如: 容貌+15、商業價值+10", required=False)
                p_aff = discord.ui.TextInput(label="贈予好感加成 (純數字，選填)", placeholder="例如: 10", required=False)

                async def on_submit(m_self, m_inter: discord.Interaction):
                    try:
                        price = int(m_self.p_price.value.strip())
                        if price <= 0: raise ValueError
                    except ValueError:
                        await m_inter.response.send_message("❌ 販售單價必須為大於 0 的正整數！", ephemeral=True)
                        return

                    aff = int(m_self.p_aff.value.strip()) if m_self.p_aff.value.strip().isdigit() else 0
                    prod_name = m_self.p_name.value.strip()
                    prod_desc = m_self.p_desc.value.strip()
                    prod_bonus = m_self.p_bonus.value.strip()

                    shop_title = f"{comp_name}旗艦店"
                    async with aiosqlite.connect(DB_PATH) as db:
                        # 登記至商店清單，賣家標記為公司名稱
                        await db.execute("""
                            INSERT INTO shop_items (guild_id, shop_name, name, price, description, stat_bonus, affinity_bonus, usable, seller)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                        """, (g_id, shop_title, prod_name, price, prod_desc, prod_bonus, aff, comp_name))
                        await db.commit()

                    await m_inter.response.send_message(
                        f"🎉 成功在【{shop_title}】上架新商品！\n"
                        f"📦 商品名稱：**{prod_name}** ｜ 價格：**${price:,}**\n"
                        f"✨ 數值效果：`{prod_bonus or '無'}` ｜ 好感加成：`+{aff}`\n"
                        f"全服成員已可在 `/商城` 中挑選並購買你的商品，貨款將自動匯入公司金庫！"
                    )

            await inter.response.send_modal(AddProductModal())

        # 4. 提領利潤
        async def withdraw_cb(inter: discord.Interaction):
            class WithdrawModal(discord.ui.Modal, title=f"提領【{comp_name}】營運盈餘"):
                amount_input = discord.ui.TextInput(label=f"提領金額 (當前金庫: ${balance:,})", placeholder="輸入欲轉入個人銀行的金額")

                async def on_submit(m_self, m_inter: discord.Interaction):
                    try:
                        amt = int(m_self.amount_input.value.strip())
                        if amt <= 0 or amt > balance: raise ValueError
                    except ValueError:
                        await m_inter.response.send_message(f"❌ 請輸入正確金額（不得大於金庫儲備 ${balance:,}）！", ephemeral=True)
                        return

                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("UPDATE companies SET balance = balance - ? WHERE id = ?", (amt, comp_id))
                        await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (amt, g_id, my_char))
                        await db.commit()

                    await m_inter.response.send_message(f"💰 成功從公司金庫提領 **${amt:,}**，已全額匯入負責人 **{my_char}** 的個人銀行帳戶！")

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
            f"• 招募職業門檻：`{allowed_jobs or '全職業開放'}`\n\n"
            f"點選 **「🏪 設立/管理旗下商店」** 可直接對外販售自製商品或獨家周邊賺取巨額利潤！"
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(f"ℹ️ 角色 **{my_char}** 目前名下無自主創立的公司，暫無法開啟商業管理後台。", ephemeral=True)

# -------------------- 指令：/商店與物品管理（管理員設定官方商品與門票） --------------------
@bot.tree.command(name="商店與物品管理", description="【管理員專用】上架、修改商城商品、資產或門票身分組")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(操作=[
    app_commands.Choice(name="上架/新增商品", value="add"),
    app_commands.Choice(name="修改既有商品", value="edit"),
    app_commands.Choice(name="下架商品", value="remove")
])
@app_commands.describe(
    操作="選擇執行的動作",
    商店="商品歸屬商店（例如: 官方商城, 票務系統, 藥品專櫃）",
    商品名="物品名稱",
    價格="售價 (純數字)",
    簡介="商品介紹",
    增加數值="使用時加成的數值 (例如: 容貌+10、實力+5)",
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

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM shop_items WHERE guild_id = ? AND shop_name = ? AND name = ?", (g_id, s_name, i_name)) as cur:
            exists = await cur.fetchone()

        if op == "remove":
            if not exists:
                await interaction.response.send_message(f"❌ 查無【{s_name}】的商品【{i_name}】！", ephemeral=True)
                return
            await db.execute("DELETE FROM shop_items WHERE id = ?", (exists[0],))
            await db.commit()
            await interaction.response.send_message(f"🗑️ 已成功將【{i_name}】從【{s_name}】下架！", ephemeral=True)
            return

        if 價格 <= 0:
            await interaction.response.send_message("❌ 商品價格必須大於 0！", ephemeral=True)
            return

        if op == "add":
            if exists:
                await interaction.response.send_message(f"❌ 【{s_name}】已有同名商品【{i_name}】！若要調整請選修改。", ephemeral=True)
                return
            await db.execute("""
                INSERT INTO shop_items (guild_id, shop_name, name, price, description, stat_bonus, affinity_bonus, usable, target_role_id, seller)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '官方')
            """, (g_id, s_name, i_name, 價格, 簡介.strip(), 增加數值.strip(), 增加好感, 可否使用, role_id))
            action_str = "上架"
        else:
            if not exists:
                await interaction.response.send_message(f"❌ 查無欲修改的商品【{i_name}】！", ephemeral=True)
                return
            await db.execute("""
                UPDATE shop_items SET price = ?, description = ?, stat_bonus = ?, affinity_bonus = ?, usable = ?, target_role_id = ?
                WHERE id = ?
            """, (價格, 簡介.strip(), 增加數值.strip(), 增加好感, 可否使用, role_id, exists[0]))
            action_str = "修改"

        await db.commit()

    ticket_text = f"（🎫 綁定身分組: {對應地圖身分組.mention}）" if role_id > 0 else ""
    await interaction.response.send_message(
        f"✅ 成功{action_str}商品！\n"
        f"🏪 所屬專區：【{s_name}】\n"
        f"📦 商品名稱：**{i_name}** ｜ 價格：**${價格:,}** {ticket_text}\n"
        f"✨ 數值效果：`{增加數值 or '無'}` ｜ 好感加成：`+{增加好感}`"
    )

# -------------------- 指令：/商城（支援官方、二手與名下公司專賣店購物收益） --------------------
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

        # 動態列出所有已設立的商店專區（含官方商城、二手、各家公司旗艦店）
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

                # 自動扣款：手頭現金優先，不足由銀行存款補齊
                if cash >= price:
                    await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (price, g_id, c_name))
                else:
                    remain = price - cash
                    await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (remain, g_id, c_name))

                seller_info = ""
                # 判斷貨款流向：
                # 1. 公司門市售賣：直接將貨款匯入公司金庫
                async with db.execute("SELECT id FROM companies WHERE guild_id = ? AND name = ?", (g_id, seller)) as c_cur:
                    comp_match = await c_cur.fetchone()

                if comp_match:
                    await db.execute("UPDATE companies SET balance = balance + ? WHERE id = ?", (price, comp_match[0]))
                    seller_info = f"\n🏢 貨款 **${price:,}** 已全額匯入【**{seller}**】公司金庫！"
                elif seller != "官方":
                    # 2. 玩家二手寄售：貨款匯入個人帳戶並下架
                    await db.execute("UPDATE characters SET bank = bank + ? WHERE guild_id = ? AND name = ?", (price, g_id, seller))
                    await db.execute("DELETE FROM shop_items WHERE id = ?", (item_id,))
                    seller_info = f"\n🏷️ 貨款已轉入原賣家 **{seller}** 銀行帳戶！"

                # 放入購買者背包
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


# -------------------- 指令：/售物 與 /背包 --------------------
@bot.tree.command(name="售物", description="將背包擁有的物品放上［二手］商城寄售")
@app_commands.describe(角色名="賣家角色名稱", 物品名="背包中的物品名稱", 價格="自訂寄售價格")
async def sell_item(interaction: discord.Interaction, 角色名: str, 物品名: str, 價格: int):
    g_id = interaction.guild_id
    if 價格 <= 0:
        await interaction.response.send_message("❌ 販售價格必須大於 0！", ephemeral=True)
        return

    c_name = 角色名.strip()
    i_name = 物品名.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, amount FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, c_name, i_name)) as cur:
            inv = await cur.fetchone()
            if not inv or inv[1] <= 0:
                await interaction.response.send_message(f"❌ 背包中查無物品【{i_name}】！", ephemeral=True)
                return

        if inv[1] == 1:
            await db.execute("DELETE FROM inventory WHERE id = ?", (inv[0],))
        else:
            await db.execute("UPDATE inventory SET amount = amount - 1 WHERE id = ?", (inv[0],))

        await db.execute("""
            INSERT INTO shop_items (guild_id, shop_name, name, price, description, stat_bonus, affinity_bonus, usable, target_role_id, seller)
            VALUES (?, '二手', ?, ?, '玩家自售二手物', '無額外加成', 0, 1, 0, ?)
        """, (g_id, i_name, 價格, c_name))
        await db.commit()

    await interaction.response.send_message(f"🏷️ **{c_name}** 已將 **{i_name}** 成功上架至【二手】商城，定價為 **${價格:,}**！")

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
# -------------------- 指令：/使用（支援單次、批量、［全部］一鍵使用與寵物餵食） --------------------
@bot.tree.command(name="使用", description="使用背包中的道具（支援批量或填［全部］，可指定餵食照料寵物）")
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

        # 解析使用數量
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

        async with db.execute("SELECT stat_bonus, usable, target_role_id FROM shop_items WHERE guild_id = ? AND name = ?", (g_id, i_name)) as cur:
            item_info = await cur.fetchone()

        stat_bonus = item_info[0] if item_info else ""
        usable = item_info[1] if item_info else 1
        role_id = item_info[2] if item_info else 0

        if usable == 0:
            await interaction.response.send_message(f"ℹ️ 道具【{i_name}】為純收藏紀念品，無法直接使用。", ephemeral=True)
            return

        now = time.time()
        # 門票時效身分組處理（若有設定身分組）
        if role_id > 0:
            if now < ticket_ban:
                rem_h = int((ticket_ban - now) / 3600)
                await interaction.response.send_message(f"🚫 該角色先前曾逾期未歸，仍在禁令懲罰中！剩餘懲罰時間：**{rem_h}** 小時。", ephemeral=True)
                return

            role = interaction.guild.get_role(role_id)
            if role:
                try:
                    await interaction.user.add_roles(role, reason="使用大地圖門票成功出境")
                except Exception:
                    pass

            expire_at = now + (336 * 3600) # 兩週時效
            await db.execute("""
                INSERT INTO active_tickets (guild_id, char_name, user_id, role_id, ticket_name, start_time, expire_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (g_id, c_name, interaction.user.id, role_id, i_name, now, expire_at))

        # 扣減背包庫存
        if use_cnt == cur_amt:
            await db.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
        else:
            await db.execute("UPDATE inventory SET amount = amount - ? WHERE id = ?", (use_cnt, inv_id))

        # 寵物餵養照料判定
        pet_msg = ""
        if 餵食目標寵物:
            p_name = 餵食目標寵物.strip()
            async with db.execute("SELECT id, pet_type, health, status FROM pets WHERE guild_id = ? AND owner_name = ? AND pet_name = ?", (g_id, c_name, p_name)) as p_cur:
                pet_row = await p_cur.fetchone()

            if not pet_row:
                pet_msg = f"\n⚠️ 找不到名為【{p_name}】的寵物！"
            elif pet_row[3] == "已故":
                pet_msg = f"\n⚠️ 愛寵【{p_name}】已經離世，無法繼續照料。"
            else:
                p_id, p_type, hp, p_status = pet_row
                # 飼料匹配判定：若道具名稱不含該寵物種類且非通用，視為餵錯
                if p_type not in i_name and ("通用" not in i_name):
                    new_hp = max(0, hp - 20 * use_cnt)
                    await db.execute("UPDATE pets SET health = ? WHERE id = ?", (new_hp, p_id))
                    pet_msg = f"\n🚨 **【餵食意外！】** 飼料類型不匹配！【{p_name}】（{p_type}）食用後腸胃不適，健康度重扣 **-{20 * use_cnt}** 點（當前健康: {new_hp}/500）！"
                else:
                    new_hp = min(500, hp + 25 * use_cnt)
                    await db.execute("UPDATE pets SET health = ? WHERE id = ?", (new_hp, p_id))
                    pet_msg = f"\n🐾 **【悉心照料】** 成功為【{p_name}】使用了 {i_name} ×{use_cnt}！健康度恢復至 **{new_hp}/500** 點！"

        # 角色屬性數值加成（依使用數量等比倍增）
        applied_stats = []
        if stat_bonus:
            char_stats = json.loads(stats_json) if stats_json else {}
            for part in re.split(r"[,，、\s]+", stat_bonus):
                m = re.search(r"([^\d+-]+)([+-]?\d+)", part)
                if m:
                    s_name = m.group(1).strip()
                    s_delta = int(m.group(2)) * use_cnt
                    char_stats[s_name] = char_stats.get(s_name, 0) + s_delta
                    applied_stats.append(f"{s_name} {s_delta:+}")
            await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(char_stats, ensure_ascii=False), g_id, c_name))

        await db.commit()

    if stat_bonus:
        await check_and_update_rank(g_id, c_name, interaction.channel)

    extra_msg = f"\n🎫 已啟用外地簽證身分組！有效停留時間為 **336 小時（兩週）**，請記得在期限前使用 `/返回原本地圖`！" if role_id > 0 else ""
    bonus_msg = f"\n📊 角色屬性加成：`{'、'.join(applied_stats)}`" if applied_stats else ""
    await interaction.response.send_message(f"✨ **{c_name}** 成功使用了道具【**{i_name}**】×{use_cnt}！{bonus_msg}{extra_msg}{pet_msg}")


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

# -------------------- 指令：/贈予（贈送道具給角色或 NPC，增加好感度） --------------------
@bot.tree.command(name="贈予", description="將背包道具轉交給其他角色或 NPC（贈送 NPC 自動增加羈絆好感度）")
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
        async with db.execute("SELECT user_id FROM characters WHERE guild_id = ? AND name = ?", (g_id, sender)) as cur:
            s_row = await cur.fetchone()
            if not s_row:
                await interaction.response.send_message(f"❌ 查無轉出角色【{sender}】！", ephemeral=True)
                return
            if s_row[0] != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 你只能為自己的角色操作道具！", ephemeral=True)
                return

        async with db.execute("SELECT is_npc FROM characters WHERE guild_id = ? AND name = ?", (g_id, receiver)) as cur:
            r_row = await cur.fetchone()
            if not r_row:
                await interaction.response.send_message(f"❌ 查無接收對象【{receiver}】！", ephemeral=True)
                return
            is_npc_target = r_row[0] > 0

        async with db.execute("SELECT id, amount FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, sender, i_name)) as cur:
            inv = await cur.fetchone()
            if not inv or inv[1] < 數量:
                await interaction.response.send_message(f"❌ 背包內【{i_name}】數量不足，無法贈送！", ephemeral=True)
                return
            inv_id, current_amt = inv

        # 扣減背包
        if current_amt == 數量:
            await db.execute("DELETE FROM inventory WHERE id = ?", (inv_id,))
        else:
            await db.execute("UPDATE inventory SET amount = amount - ? WHERE id = ?", (數量, inv_id))

        # 送入接收者背包
        async with db.execute("SELECT id FROM inventory WHERE guild_id = ? AND owner_name = ? AND item_name = ?", (g_id, receiver, i_name)) as cur:
            r_inv = await cur.fetchone()
            if r_inv:
                await db.execute("UPDATE inventory SET amount = amount + ? WHERE id = ?", (數量, r_inv[0]))
            else:
                await db.execute("INSERT INTO inventory (guild_id, owner_name, item_name, amount, giver) VALUES (?, ?, ?, ?, ?)", (g_id, receiver, i_name, 數量, f"{sender} 贈送"))

        # 若是贈送給 NPC，自動提升好感度羈絆
        bonus_msg = ""
        if is_npc_target:
            async with db.execute("SELECT affinity_bonus FROM shop_items WHERE guild_id = ? AND name = ?", (g_id, i_name)) as cur:
                aff_row = await cur.fetchone()
                aff_points = (aff_row[0] if (aff_row and aff_row[0] > 0) else 5) * 數量

            await db.execute("""
                INSERT INTO relationships (guild_id, from_char, to_char, affection, status_desc)
                VALUES (?, ?, ?, ?, '深受感動')
                ON CONFLICT(guild_id, from_char, to_char) DO UPDATE SET affection = affection + ?, status_desc = '備受禮遇'
            """, (g_id, receiver, sender, aff_points, aff_points))
            bonus_msg = f"\n💖 官方 NPC **{receiver}** 對 **{sender}** 的好感度羈絆提升了 **+{aff_points}** 點！"

        await db.commit()

    await interaction.response.send_message(f"🎁 **{sender}** 成功將 **{i_name}** ×{數量} 贈送給了 **{receiver}**！{bonus_msg}")
    # -------------------- 查看系統：獨立翻頁視窗（成就、榮譽、交際） --------------------
class PagedDetailView(discord.ui.View):
    def __init__(self, title: str, items: list, color: int):
        super().__init__(timeout=120)
        self.title = title
        self.items = items
        self.color = color
        self.page = 0
        self.max_page = max(0, (len(items) - 1) // 10)

    def get_embed(self):
        start = self.page * 10
        end = start + 10
        slice_items = self.items[start:end]

        embed = discord.Embed(title=f"{self.title} (第 {self.page+1}/{self.max_page+1} 頁)", color=self.color)
        embed.description = "\n".join(slice_items) if slice_items else "暫無相關資料紀錄。"
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

class ProfileMainView(discord.ui.View):
    def __init__(self, char_name: str, guild_id: int):
        super().__init__(timeout=180)
        self.char_name = char_name
        self.guild_id = guild_id

    @discord.ui.button(label="🏆 成就列表", style=discord.ButtonStyle.primary)
    async def view_achieves(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT works FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                works = json.loads((await cur.fetchone())[0] or "[]")
        items = [f"• 【{w.get('type', '歷練')}】《{w.get('title')}》— 擔任: {w.get('extra', '參演')}" for w in works if w.get("category") == "成就"]
        p_view = PagedDetailView(f"🏆【{self.char_name}】歷練成就清單", items, 0xF1C40F)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

    @discord.ui.button(label="🎖️ 榮譽列表", style=discord.ButtonStyle.success)
    async def view_honors(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT works FROM characters WHERE guild_id = ? AND name = ?", (self.guild_id, self.char_name)) as cur:
                works = json.loads((await cur.fetchone())[0] or "[]")
        items = [f"• 🎖️《{w.get('title')}》— 備註: {w.get('extra', '榮譽認證')}" for w in works if w.get("category") == "榮譽"]
        p_view = PagedDetailView(f"🎖️【{self.char_name}】獲頒榮譽與代言", items, 0x2ECC71)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

    @discord.ui.button(label="💬 交際現況", style=discord.ButtonStyle.danger)
    async def view_relationships(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT to_char, tendency, affection, status_desc FROM relationships WHERE guild_id = ? AND from_char = ?", (self.guild_id, self.char_name)) as cur:
                rows = await cur.fetchall()
        items = [f"• 對象：**{to_c}** ｜ 傾向：【{t}】 ｜ 羈絆：💖{aff} ｜ 狀況：`{desc}`" for to_c, t, aff, desc in rows]
        p_view = PagedDetailView(f"💬【{self.char_name}】社交網絡與傾向", items, 0xE91E63)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)

# -------------------- 指令：/查看（限玩家自設角色與玩家自設 NPC） --------------------
@bot.tree.command(name="查看", description="調閱玩家角色或玩家自設 NPC 詳細檔案與資產面板")
@app_commands.describe(名字="玩家自設角色或自設 NPC 姓名")
async def view_char_cmd(interaction: discord.Interaction, 名字: str):
    g_id = interaction.guild_id
    target_name = 名字.strip()
    await interaction.response.defer(ephemeral=False)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT age, gender, job, faction, tags, relationship_status,
                   cp_info, cash, bank, stats, rank, company_id, is_npc, image_url, height, nationality
            FROM characters WHERE guild_id = ? AND name = ?
        """, (g_id, target_name)) as cur:
            row = await cur.fetchone()

        if not row:
            await interaction.followup.send(f"❌ 查無檔案【{target_name}】！", ephemeral=True)
            return

        age, gender, job, faction, tags, rel_status, cp_json, cash, bank, stats_json, rank_name, comp_id, is_npc_val, img_url, height, nationality = row

        # 權責區隔：如果是官方 NPC (1) 或 大眾路人 (3)，引導至 /npc查看
        if is_npc_val in [1, 3]:
            npc_type = "官方 NPC" if is_npc_val == 1 else "大眾路人"
            await interaction.followup.send(f"ℹ️ 【{target_name}】屬於**{npc_type}**，請使用 `/npc查看` 進行查閱！", ephemeral=True)
            return

        async with db.execute("SELECT asset_type, asset_name, price FROM personal_assets WHERE guild_id = ? AND owner_name = ?", (g_id, target_name)) as a_cur:
            assets = await a_cur.fetchall()
        async with db.execute("SELECT name, type_name FROM companies WHERE guild_id = ? AND creator_name = ?", (g_id, target_name)) as c_cur:
            comps = await c_cur.fetchall()

    cp_obj = json.loads(cp_json) if cp_json else {}
    cp_text = f"💕 CP: **{cp_obj.get('target')}** ({cp_obj.get('relation')})" if cp_obj.get("target") else "無"

    tag_prefix = "［玩家自設 NPC］" if is_npc_val == 2 else "［玩家角色］"
    h_display = f"{height} cm" if height else "未填寫"
    nat_display = nationality if nationality else "本國"

    embed = discord.Embed(title=f"🪪 {tag_prefix}【{target_name}】個人資料面板", color=0xE67E22)
    embed.add_field(
        name="基本身分",
        value=(
            f"• 國籍/性別: {nat_display} / {gender}\n"
            f"• 年齡/身高: {age}歲 / {h_display}\n"
            f"• 身分/職業: {job}\n"
            f"• 所屬勢力: {faction}\n"
            f"• 特質標籤: `{tags or '無'}`"
        ),
        inline=True
    )
    embed.add_field(name="情感狀態", value=f"• 感情: {rel_status}\n• {cp_text}", inline=True)
    embed.add_field(name="資產與地位", value=f"• 當前地位: **【{rank_name or '未定級'}】**\n• 現金: ${cash:,} ｜ 銀行: ${bank:,}", inline=False)

    asset_lines = [f"• [{a[0]}] {a[1]} (${a[2]:,})" for a a in assets]
    if comps:
        for c in comps: asset_lines.append(f"• [名下公司] {c[0]} ({c[1]})")
    embed.add_field(name="🚗 房產、車輛與公司資產", value="\n".join(asset_lines) if asset_lines else "名下尚無固定資產", inline=False)

    stats = json.loads(stats_json) if stats_json else {}
    stat_texts = [f"{k}: **{v}**" for k, v in stats.items()]
    embed.add_field(name="📊 核心數值", value=" ｜ ".join(stat_texts[:10]) if stat_texts else "尚未登記任何數值", inline=False)

    if img_url and img_url.startswith("http"):
        embed.set_thumbnail(url=img_url)

    view = ProfileMainView(target_name, g_id)
    await interaction.followup.send(embed=embed, view=view)


# -------------------- 指令：/npc查看（官方 NPC 與 大眾路人 分類大廳） --------------------
async def render_npc_profile(interaction: discord.Interaction, target_name: str):
    """渲染 NPC 專屬面板輔助函式"""
    g_id = interaction.guild_id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT age, gender, job, faction, tags, relationship_status,
                   cp_info, cash, bank, stats, rank, company_id, is_npc, image_url, height, nationality
            FROM characters WHERE guild_id = ? AND name = ?
        """, (g_id, target_name)) as cur:
            row = await cur.fetchone()

        if not row:
            await interaction.followup.send(f"❌ 查無檔案【{target_name}】！", ephemeral=True)
            return

        age, gender, job, faction, tags, rel_status, cp_json, cash, bank, stats_json, rank_name, comp_id, is_npc_val, img_url, height, nationality = row

    tag_prefix = "［官方 NPC］" if is_npc_val == 1 else "［大眾路人］"
    h_display = f"{height} cm" if height else "未填寫"
    nat_display = nationality if nationality else "本國"

    embed = discord.Embed(title=f"🎭 {tag_prefix}【{target_name}】資料面板", color=0x9B59B6 if is_npc_val == 1 else 0x1ABC9C)
    embed.add_field(
        name="基本履歷",
        value=(
            f"• 國籍/性別: {nat_display} / {gender}\n"
            f"• 年齡/身高: {age}歲 / {h_display}\n"
            f"• 身分/職業: {job}\n"
            f"• 所屬勢力: {faction}\n"
            f"• 特質標籤: `{tags or '無'}`"
        ),
        inline=True
    )
    embed.add_field(name="情感狀態", value=f"• 感情: {rel_status}", inline=True)
    embed.add_field(name="資產與地位", value=f"• 當前地位: **【{rank_name or '未定級'}】**\n• 現金: ${cash:,} ｜ 銀行: ${bank:,}", inline=False)

    stats = json.loads(stats_json) if stats_json else {}
    stat_texts = [f"{k}: **{v}**" for k, v in stats.items()]
    embed.add_field(name="📊 核心數值", value=" ｜ ".join(stat_texts[:10]) if stat_texts else "尚未登記任何數值", inline=False)

    if img_url and img_url.startswith("http"):
        embed.set_thumbnail(url=img_url)

    view = ProfileMainView(target_name, g_id)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    @discord.ui.button(label="🐾 專屬寵物", style=discord.ButtonStyle.secondary)
    async def view_pets(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT pet_type, pet_name, health, status FROM pets WHERE guild_id = ? AND owner_name = ?", (self.guild_id, self.char_name)) as cur:
                pets = await cur.fetchall()

        if not pets:
            await interaction.response.send_message(f"🐾 **{self.char_name}** 目前名下未飼養任何寵物。", ephemeral=True)
            return

        embed = discord.Embed(title=f"🐾【{self.char_name}】的寵物樂園", color=0x2ECC71)
        for p_type, p_name, hp, status in pets:
            status_emoji = "💚" if hp > 200 else ("⚠️" if hp > 0 else "🪦")
            embed.add_field(
                name=f"【{p_type}】{p_name}",
                value=f"• 健康值：`{hp}/500` {status_emoji}\n• 當前狀態：`{status}`",
                inline=True
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📰 耳聞傳聞", style=discord.ButtonStyle.secondary)
    async def view_rumors(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT content, created_at FROM rumors WHERE guild_id = ? AND char_name = ? ORDER BY id DESC", (self.guild_id, self.char_name)) as cur:
                rumors = await cur.fetchall()

        if not rumors:
            await interaction.response.send_message(f"📰 目前坊間尚未流傳任何關於 **{self.char_name}** 的傳聞八卦。", ephemeral=True)
            return

        items = [f"• 「{r[0]}」 ── *({time.strftime('%Y/%m/%d', time.localtime(r[1]))})*" for r in rumors]
        p_view = PagedDetailView(f"📰【{self.char_name}】坊間八卦與傳聞", items, 0x95A5A6)
        await interaction.response.send_message(embed=p_view.get_embed(), view=p_view, ephemeral=True)


class NPCLobbyView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id

    @discord.ui.button(label="👑 官方 NPC 名冊", style=discord.ButtonStyle.primary)
    async def official_npcs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name, age, gender, job FROM characters WHERE guild_id = ? AND is_npc = 1", (self.guild_id,)) as cur:
                npcs = await cur.fetchall()

        if not npcs:
            await interaction.followup.send("📋 目前伺服器尚未登記任何【官方 NPC】！", ephemeral=True)
            return

        class OfficialDropdown(discord.ui.Select):
            def __init__(self):
                opts = [discord.SelectOption(label=n[0], description=f"{n[1]}歲 ｜ {n[2]} ｜ {n[3]}", emoji="👑") for n in npcs[:25]]
                super().__init__(placeholder="點選調閱指定官方 NPC 檔案...", options=opts)

            async def callback(self, inter: discord.Interaction):
                await inter.response.defer(ephemeral=True)
                await render_npc_profile(inter, self.values[0])

        sub_view = discord.ui.View()
        sub_view.add_item(OfficialDropdown())
        embed = discord.Embed(title="👑 官方重要 NPC 列表", description="請自下方選單挑選欲查閱的官方 NPC：", color=0x9B59B6)
        for n in npcs[:10]:
            embed.add_field(name=f"👤 {n[0]}", value=f"{n[1]}歲 / {n[2]} ｜ 身分: {n[3]}", inline=True)

        await interaction.followup.send(embed=embed, view=sub_view, ephemeral=True)

    @discord.ui.button(label="🎭 大眾路人名錄", style=discord.ButtonStyle.success)
    async def crowd_npcs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name, age, gender, job, nationality FROM characters WHERE guild_id = ? AND is_npc = 3 ORDER BY created_at DESC", (self.guild_id,)) as cur:
                crowds = await cur.fetchall()

        if not crowds:
            await interaction.followup.send("📋 目前伺服器尚未生成任何【大眾路人】！可請管理員使用 `/大眾路人大量發生中` 生成。", ephemeral=True)
            return

        class CrowdDropdown(discord.ui.Select):
            def __init__(self):
                opts = [discord.SelectOption(label=c[0], description=f"國籍:{c[4]} ｜ {c[1]}歲 ｜ {c[3]}", emoji="🎭") for c in crowds[:25]]
                super().__init__(placeholder="點選調閱大眾路人角色檔案...", options=opts)

            async def callback(self, inter: discord.Interaction):
                await inter.response.defer(ephemeral=True)
                await render_npc_profile(inter, self.values[0])

        sub_view = discord.ui.View()
        sub_view.add_item(CrowdDropdown())
        embed = discord.Embed(title="🎭 大眾路人名錄大廳", description=f"全城現有大眾路人：**{len(crowds)}** 位（每48小時動態浮動行情）", color=0x1ABC9C)
        for c in crowds[:10]:
            embed.add_field(name=f"👤 {c[0]} ({c[4]} / {c[2]})", value=f"{c[1]}歲 ｜ 職業: {c[3]}", inline=True)

        await interaction.followup.send(embed=embed, view=sub_view, ephemeral=True)


@bot.tree.command(name="npc查看", description="開啟 NPC 大廳（可切換官方 NPC 或大眾路人名單）")
async def view_npc_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="👥 NPC 服務大廳",
        description="請點選下方按鈕，選擇你想查閱的名冊類別：\n\n• 👑 **官方 NPC 名冊**：各勢力重要領袖、官方代表人物\n• 🎭 **大眾路人名錄**：參與全城競爭與行情浮動的演藝圈路人",
        color=0x34495E
    )
    view = NPCLobbyView(interaction.guild_id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# -------------------- 指令：/數值登記 --------------------
@bot.tree.command(name="數值登記", description="為角色或 NPC 登記/微調數值（支援一次多項調整）")
@app_commands.choices(類別=[
    app_commands.Choice(name="官方 NPC", value="官方npc"),
    app_commands.Choice(name="玩家自設 NPC", value="玩家npc"),
    app_commands.Choice(name="自身角色", value="角色")
])
@app_commands.describe(
    名字="角色或 NPC 姓名",
    數值調整串="一般調整用，例如: 容貌50、才智-10、商業價值100",
    人設單連結="【限初次建檔填單用】貼上人設帖子/討論串連結自動爬取"
)
async def register_stats_multi(
    interaction: discord.Interaction,
    類別: app_commands.Choice[str],
    名字: str,
    數值調整串: str = None,
    人設單連結: str = None
):
    g_id = interaction.guild_id
    target_name = 名字.strip()
    is_admin = interaction.user.guild_permissions.administrator

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, stats, is_npc FROM characters WHERE guild_id = ? AND name = ?", (g_id, target_name)) as cur:
            row = await cur.fetchone()

        if not row:
            await interaction.response.send_message(f"❌ 查無【{target_name}】！", ephemeral=True)
            return

        u_id, stats_json, is_npc_val = row
        if not is_admin and u_id != interaction.user.id:
            await interaction.response.send_message("❌ 你無權操作此角色數值！", ephemeral=True)
            return

        char_stats = json.loads(stats_json) if stats_json else {}

        if 人設單連結:
            await interaction.response.defer(ephemeral=True)
            link_match = re.search(r"channels/\d+/(\d+)(?:/(\d+))?", 人設單連結)
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

            for k, v in re.findall(r"([^\d\s:：,，]+)\s*[:：]?\s*(\d+)", post_content):
                if k not in ["現金", "金錢", "年齡", "順序"]:
                    char_stats[k] = int(v)

            await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(char_stats, ensure_ascii=False), g_id, target_name))
            await db.commit()
            await interaction.followup.send(f"🎉 已自人設單同步【{target_name}】的各項初始數值！", ephemeral=True)
            return

        if not 數值調整串:
            await interaction.response.send_message("❌ 請填入【數值調整串】（例如：容貌50、才智-10）！", ephemeral=True)
            return

        changes = []
        for part in re.split(r"[,，、\s]+", 數值調整串.strip()):
            m = re.search(r"([^\d+-]+)([+-]?\d+)", part)
            if m:
                s_name = m.group(1).strip()
                s_delta = int(m.group(2))
                char_stats[s_name] = char_stats.get(s_name, 0) + s_delta
                sign = "+" if s_delta >= 0 else ""
                changes.append(f"{s_name} {sign}{s_delta}")

        await db.execute("UPDATE characters SET stats = ? WHERE guild_id = ? AND name = ?", (json.dumps(char_stats, ensure_ascii=False), g_id, target_name))
        await db.commit()

    await check_and_update_rank(g_id, target_name, interaction.channel)
    await interaction.response.send_message(f"✅ 【{target_name}】數值更新完畢：`{'、'.join(changes)}`！")

# -------------------- 指令：/地位等級限制 --------------------
@bot.tree.command(name="地位等級限制", description="【管理員專用】設定、新增或修改全城地位晉級標準")
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
    地位等級="［修改模式］地位名稱 (如: 頂峰領袖、傳奇大師)",
    成就限制="［修改模式］成就條件 (如: 史詩歷練2, 終極冒險1)",
    榮譽限制="［修改模式］榮譽標籤條件 (如: 奢華2, 傳說1)",
    數值限制="［修改模式］數值門檻 (如: 商業價值500, 實力300)",
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
# -------------------- 指令：/任務新增 與 /回報任務（含作品陣營自動抽成） --------------------
@bot.tree.command(name="任務新增", description="【管理員專用】發布或修改任務（含成就/榮譽選填）")
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
    金錢獎勵="自動匯入銀行的金錢 (可填 0)",
    數值獎勵="【選填】獲得的數值 (例如: 容貌+10、商業價值+20)",
    成就="【選填】完成時賦予的成就名稱或標籤",
    榮譽="【選填】完成時賦予的榮譽稱號或等級（例如：奢華、傳說、S級）",
    限制條件="【選填】接取門檻（例如：地位限一線、性別限女、勢力限指定組織）",
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
    金錢獎勵: int = 0,
    數值獎勵: str = "",
    成就: str = "",
    榮譽: str = "",
    限制條件: str = "",
    獎勵道具名: str = None,
    獎勵道具數量: int = 1,
    限時時間: str = None,
    回報頻道: discord.abc.GuildChannel = None
):
    g_id = interaction.guild_id
    category = 選擇欄位.value
    time_limit_str = 限時時間.strip() if (category == "限時任務" and 限時時間) else ""
    items = [{"name": 獎勵道具名.strip(), "amount": 獎勵道具數量}] if 獎勵道具名 else []
    rep_ch_id = 回報頻道.id if 回報頻道 else 0

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM quests WHERE guild_id = ? AND title = ?", (g_id, 任務名.strip())) as cur:
            exists = await cur.fetchone()

        if 操作.value == "add":
            if exists:
                await interaction.response.send_message(f"❌ 任務名稱 `{任務名}` 已經存在！", ephemeral=True)
                return
            await db.execute("""
                INSERT INTO quests (guild_id, category, title, reward_cash, reward_items, reward_stats, achievement, honor, requirement, time_limit, report_channel_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (g_id, category, 任務名.strip(), 金錢獎勵, json.dumps(items, ensure_ascii=False), 數值獎勵.strip(), 成就.strip(), 榮譽.strip(), 限制條件.strip(), time_limit_str, rep_ch_id))
            op_label = "新增"
        else:
            if not exists:
                await interaction.response.send_message(f"❌ 找不到欲修改的任務 `{任務名}`！", ephemeral=True)
                return
            await db.execute("""
                UPDATE quests SET category = ?, reward_cash = ?, reward_items = ?, reward_stats = ?, achievement = ?, honor = ?, requirement = ?, time_limit = ?, report_channel_id = ?
                WHERE guild_id = ? AND title = ?
            """, (category, 金錢獎勵, json.dumps(items, ensure_ascii=False), 數值獎勵.strip(), 成就.strip(), 榮譽.strip(), 限制條件.strip(), time_limit_str, rep_ch_id, g_id, 任務名.strip()))
            op_label = "修改"

        await db.commit()

    rewards_list = []
    if 金錢獎勵 > 0: rewards_list.append(f"${金錢獎勵:,}")
    if 數值獎勵: rewards_list.append(f"{數值獎勵}")
    if 獎勵道具名: rewards_list.append(f"{獎勵道具名}×{獎勵道具數量}")
    reward_summary = " ｜ ".join(rewards_list) if rewards_list else "無實質物資獎勵"

    achieve_desc = f"\n🏆 成就獎勵：【{成就}】" if 成就 else ""
    honor_desc = f"\n🎖️ 榮譽稱號：【{榮譽}】" if 榮譽 else ""
    req_desc = f"\n🚫 接取限制門檻：【{限制條件}】" if 限制條件 else ""
    ch_desc = f"\n📍 限定回報區：{回報頻道.mention}" if 回報頻道 else "\n📍 限定回報區：全伺服器皆可"

    await interaction.response.send_message(f"✅ 成功{op_label}任務！\n📌 分類：【{category}】\n🏷️ 任務名：**{任務名}**\n🎁 獎勵：{reward_summary}{achieve_desc}{honor_desc}{req_desc}{ch_desc}")

@bot.tree.command(name="回報任務", description="回報任務文章連結，領取獎勵（自動完成陣營抽成並檢測地位）")
@app_commands.describe(角色名="回報任務的角色名稱", 文章連結="你所發表文章的帖子/討論串或訊息連結")
async def report_quest(interaction: discord.Interaction, 角色名: str, 文章連結: str):
    g_id = interaction.guild_id
    await interaction.response.defer(ephemeral=False)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, gender, faction, stats, rank, works FROM characters WHERE guild_id = ? AND name = ?", (g_id, 角色名)) as cur:
            row = await cur.fetchone()
            if not row:
                await interaction.followup.send(f"❌ 查無角色 `{角色名}`！", ephemeral=True)
                return
            u_id, gender, faction, stats_json, rank_name, works_json = row
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
        async with db.execute("SELECT title, reward_cash, reward_items, reward_stats, achievement, honor, requirement, time_limit, report_channel_id FROM quests WHERE guild_id = ?", (g_id,)) as cur:
            all_quests = await cur.fetchall()

        matched_quest = None
        for q in all_quests:
            if q[0] in target_title:
                matched_quest = q
                break

        if not matched_quest:
            await interaction.followup.send(f"❌ 驗證失敗：無法在文章標題中匹配到正確的任務名稱！", ephemeral=True)
            return

        q_title, r_cash, r_items_json, r_stats, achieve_val, honor_val, requirement, time_limit, req_channel_id = matched_quest

        if req_channel_id and req_channel_id > 0:
            current_ch = interaction.channel
            is_correct = (current_ch.id == req_channel_id) or (hasattr(current_ch, "parent_id") and current_ch.parent_id == req_channel_id)
            if not is_correct:
                await interaction.followup.send(f"❌ 此任務限定在指定的專屬回報區操作！請前往：<#{req_channel_id}>", ephemeral=True)
                return

        char_stats = json.loads(stats_json) if stats_json else {}
        if requirement:
            if "地位" in requirement and rank_name not in requirement:
                await interaction.followup.send(f"❌ 資格不符：此任務要求【{requirement}】，你當前地位為【{rank_name}】！", ephemeral=True)
                return
            if "性別" in requirement and gender not in requirement:
                await interaction.followup.send(f"❌ 資格不符：此任務限制性別！", ephemeral=True)
                return
            if "勢力" in requirement and faction not in requirement:
                await interaction.followup.send(f"❌ 資格不符：此任務限制指定勢力參與！", ephemeral=True)
                return

        async with db.execute("SELECT 1 FROM quest_completions WHERE guild_id = ? AND char_name = ? AND quest_title = ?", (g_id, 角色名, q_title)) as cur:
            if await cur.fetchone():
                await interaction.followup.send(f"⚠️ 角色 **{角色名}** 已經完成過任務【{q_title}】，不可重複回報！", ephemeral=True)
                return

        # 1. 獎勵金幣先全額匯入銀行
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

        works = json.loads(works_json) if works_json else []
        if achieve_val:
            works.append({"category": "成就", "title": q_title, "extra": achieve_val})
        if honor_val:
            works.append({"category": "榮譽", "title": q_title, "extra": honor_val})
        if not achieve_val and not honor_val:
            works.append({"category": "成就", "title": q_title, "extra": "一般完成"})

        await db.execute("UPDATE characters SET works = ? WHERE guild_id = ? AND name = ?", (json.dumps(works, ensure_ascii=False), g_id, 角色名))
        await db.execute("INSERT INTO quest_completions (guild_id, char_name, quest_title, completed_at) VALUES (?, ?, ?, ?)", (g_id, 角色名, q_title, time.time()))
        await db.commit()

    # 2. 自動扣繳陣營抽成（每個作品/任務只會扣繳一次）
    tax_info = await process_faction_tax(g_id, 角色名, q_title, r_cash, interaction.channel)

    # 3. 自動觸發地位晉升檢測
    await check_and_update_rank(g_id, 角色名, interaction.channel)

    earned = []
    if r_cash > 0: earned.append(f"$ {r_cash:,}")
    if r_stats: earned.append(f"+ 數值{r_stats}")
    if achieve_val: earned.append(f"獲得成就【{achieve_val}】")
    if honor_val: earned.append(f"獲得榮譽【{honor_val}】")
    earned_str = " ｜ ".join(earned)

    await interaction.followup.send(f"‼️任務確認完成\n獎勵：{earned_str}{tax_info}\n恭喜 {interaction.user.mention} 的【{角色名}】完成任務《{q_title}》！✅")

# -------------------- 指令：/任務（看板檢視） --------------------
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

            await db.execute("UPDATE factions SET treasury = treasury - ? WHERE guild_id = ? AND name = ?", (cost, g_id, my_faction))
            await db.execute("""
                UPDATE characters
                SET bank = bank + 10000
                WHERE guild_id = ? AND faction = ?
            """, (g_id, my_faction))
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

# -------------------- 指令：/陣營排行 --------------------
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
# -------------------- 指令：/路人資源補給 --------------------
@bot.tree.command(name="路人資源補給", description="【管理員專用】批次新增路人專用相片與東西方姓名庫")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(地區分類=[
    app_commands.Choice(name="東方 (姓在名前，如: 許國偉)", value="東方"),
    app_commands.Choice(name="西方 (名•姓，如: 安妮•斯圖爾特)", value="西方")
])
@app_commands.choices(適用性別=[
    app_commands.Choice(name="通用", value="通用"),
    app_commands.Choice(name="男", value="男"),
    app_commands.Choice(name="女", value="女")
])
@app_commands.describe(
    地區分類="選擇姓名所屬體系",
    適用性別="這些姓名或照片主要適用的性別",
    新增照片檔案="可直接上傳一張相片入庫",
    姓氏串="多個姓氏以空白隔開 (例如: 許 黃 張 李 或 史密斯 斯圖爾特)",
    名字串="多個名字以空白隔開 (例如: 國偉 小艾 安妮 巧)",
    貼文或相冊連結="選填：貼上 Discord 討論串/訊息連結，自動爬取其中的圖片與文字"
)
async def supply_crowd_resources(
    interaction: discord.Interaction,
    地區分類: app_commands.Choice[str],
    適用性別: app_commands.Choice[str],
    新增照片檔案: discord.Attachment = None,
    姓氏串: str = None,
    名字串: str = None,
    貼文或相冊連結: str = None
):
    g_id = interaction.guild_id
    await interaction.response.defer(ephemeral=True)

    region = 地區分類.value
    gen = 適用性別.value
    added_photos = 0
    added_surnames = 0
    added_firstnames = 0

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. 處理直接上傳的單張相片
        if 新增照片檔案:
            await db.execute("INSERT INTO crowd_photos (guild_id, image_url, gender) VALUES (?, ?, ?)", (g_id, 新增照片檔案.url, gen))
            added_photos += 1

        # 2. 處理外部連結（抓取 Discord 貼文內的所有圖片附件與文字）
        if 貼文或相冊連結:
            link_match = re.search(r"channels/\d+/(\d+)(?:/(\d+))?", 貼文或相冊連結)
            if link_match:
                c_id = int(link_match.group(1))
                m_id = int(link_match.group(2)) if link_match.group(2) else None
                try:
                    ch = interaction.client.get_channel(c_id) or await interaction.client.fetch_channel(c_id)
                    messages = []
                    if isinstance(ch, discord.Thread):
                        async for msg in ch.history(limit=20):
                            messages.append(msg)
                    elif m_id:
                        messages.append(await ch.fetch_message(m_id))

                    for m in messages:
                        # 抓取圖片附件
                        for att in m.attachments:
                            if any(att.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']):
                                await db.execute("INSERT INTO crowd_photos (guild_id, image_url, gender) VALUES (?, ?, ?)", (g_id, att.url, gen))
                                added_photos += 1
                        # 若內容有寫 姓氏: 或 名字:
                        s_m = re.search(r"姓氏[^\n\r:：]*[:：]([^\n\r]+)", m.content)
                        if s_m:
                            for s in s_m.group(1).split():
                                await db.execute("INSERT INTO crowd_names (guild_id, region, name_type, gender, val) VALUES (?, ?, 'surname', ?, ?)", (g_id, region, gen, s.strip()))
                                added_surnames += 1
                        f_m = re.search(r"名字[^\n\r:：]*[:：]([^\n\r]+)", m.content)
                        if f_m:
                            for f in f_m.group(1).split():
                                await db.execute("INSERT INTO crowd_names (guild_id, region, name_type, gender, val) VALUES (?, ?, 'firstname', ?, ?)", (g_id, region, gen, f.strip()))
                                added_firstnames += 1
                except Exception:
                    pass

        # 3. 處理文字輸入欄位的姓氏與名字
        if 姓氏串:
            for s in re.split(r"[,，\s]+", 姓氏串.strip()):
                if s:
                    await db.execute("INSERT INTO crowd_names (guild_id, region, name_type, gender, val) VALUES (?, ?, 'surname', ?, ?)", (g_id, region, gen, s))
                    added_surnames += 1

        if 名字串:
            for f in re.split(r"[,，\s]+", 名字串.strip()):
                if f:
                    await db.execute("INSERT INTO crowd_names (guild_id, region, name_type, gender, val) VALUES (?, ?, 'firstname', ?, ?)", (g_id, region, gen, f))
                    added_firstnames += 1

        # 查詢目前未使用的照片剩餘庫存
        async with db.execute("SELECT COUNT(*) FROM crowd_photos WHERE guild_id = ? AND used = 0", (g_id,)) as cur:
            rem_photos = (await cur.fetchone())[0]

        await db.commit()

    embed = discord.Embed(title="📦 大眾路人資源入庫成功", color=0x3498DB)
    embed.add_field(name="新增成果", value=f"• 照片入庫：**+{added_photos}** 張\n• 姓氏入庫：**+{added_surnames}** 個\n• 名字入庫：**+{added_firstnames}** 個", inline=False)
    embed.add_field(name="當前相冊總庫存", value=f"剩餘 **{rem_photos}** 張未使用相片", inline=True)
    if rem_photos <= 5:
        embed.set_footer(text="⚠️ 注意：未使用的相冊庫存已不足 5 張，請盡快補充！")
    await interaction.followup.send(embed=embed, ephemeral=True)
WESTERN_NATIONS = ["美國", "英國", "法國", "德國", "義大利", "俄羅斯", "西班牙", "加拿大", "澳大利亞", "瑞典", "波蘭", "捷克", "冰島", "丹麥", "希臘", "愛爾蘭", "紐西蘭", "葡萄牙", "比利時", "瑞士",  "挪威", "芬蘭", "荷蘭", "匈牙利", "羅馬尼亞", "保加利亞", "立陶宛", "烏克蘭"]
EASTERN_NATIONS = ["中國", "日本", "韓國", "新加坡", "馬來西亞", "泰國", "越南", "菲律賓", "蒙古國", "印度", "緬甸", "馬爾地夫", "杜拜", "土耳其", "尼泊爾", "印尼", "汶萊", "柬埔寨", "卡達", "阿拉伯", "哈薩克", "不丹", "斯里蘭卡", "孟加拉", "寮國", "東帝汶"]
SOUTH_AMERICAN_NATIONS = ["巴西", "阿根廷", "智利", "哥倫比亞", "秘魯", "烏拉圭", "墨西哥","委內瑞拉", "巴拉圭", "蓋亞那", "玻利維亞", "厄瓜多"]
AFRICAN_NATIONS = ["埃及", "南非", "奈及利亞", "肯亞", "摩洛哥", "衣索比亞","象牙海岸", "剛果", "喀麥隆", "維德角", "獅子山", "尼日", "布基納法索", "賴比瑞亞"]
CROWD_JOBS = ["演員", "特技演員", "模特", "歌手", "偶像", "綜藝咖", "短劇演員", "舞者", "網紅", "星二代", "經紀人", "導演"]
CROWD_TAGS_POOL = ["初戀臉", "厭世感", "舞台匠人", "釣系", "全能ACE", "天籟蜜嗓", "極致反差", "低音砲", "古典氣質", "漫撕男", "高嶺之花", "元氣犬系"]
CROWD_RELATIONS = ["單身", "單身（事業腦）", "單身（前任成群）", "暗戀同台前輩", "地下戀愛中", "曖昧期", "隱婚傳聞中", "私生活混亂", "變態"]

# -------------------- 指令：/大眾路人大量發生中 --------------------
@bot.tree.command(name="大眾路人大量發生中", description="【管理員專用】從相冊與姓名池全自動抽取並生成路人角")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(體系偏好=[
    app_commands.Choice(name="隨機混血／全文化混抽", value="random"),
    app_commands.Choice(name="限定東方風格", value="東方"),
    app_commands.Choice(name="限定西方風格", value="西方"),
    app_commands.Choice(name="限定南美風格 (名•姓)", value="南美"),
    app_commands.Choice(name="限定非洲風格", value="非洲")
])

@app_commands.choices(性別偏好=[
    app_commands.Choice(name="隨機性別", value="隨機"),
    app_commands.Choice(name="男", value="男"),
    app_commands.Choice(name="女", value="女")
])
@app_commands.describe(
    生成數量="一次生成的路人數量 (預設 1，上限 5)",
    體系偏好="選擇姓名與國籍文化風格",
    性別偏好="指定性別或交由系統隨機"
)
async def spawn_crowd_batch(
    interaction: discord.Interaction,
    生成數量: int = 1,
    體系偏好: app_commands.Choice[str] = None,
    性別偏好: app_commands.Choice[str] = None
):
    g_id = interaction.guild_id
    await interaction.response.defer(ephemeral=False)
    count = max(1, min(5, 生成數量))

    created_list = []
    low_photo_warn = False
    rem_photos = 0

    async with aiosqlite.connect(DB_PATH) as db:
        # 取出可用的地位等級標準
        async with db.execute("SELECT rank_name FROM rank_settings WHERE guild_id = ? ORDER BY rank_order DESC", (g_id,)) as cur:
            all_ranks = [r[0] for r in await cur.fetchall()]
        default_rank = all_ranks[0] if all_ranks else "未定級"

        for _ in range(count):
            # 1. 決定性別
            if 性別偏好 and 性別偏好.value != "隨機":
                gen = 性別偏好.value
            else:
                gen = random.choice(["男", "女"])

            # 2. 決定文化風格與姓名組合
            chosen_reg = 體系偏好.value if (體系偏好 and 體系偏好.value != "random") else random.choice(["東方", "西方", "南美", "非洲"])

            # 抓取姓氏
            async with db.execute("SELECT val FROM crowd_names WHERE guild_id = ? AND region = ? AND name_type = 'surname' AND gender IN (?, '通用') ORDER BY RANDOM() LIMIT 1", (g_id, chosen_reg, gen)) as cur:
                s_row = await cur.fetchone()
            # 抓取名字
            async with db.execute("SELECT val FROM crowd_names WHERE guild_id = ? AND region = ? AND name_type = 'firstname' AND gender IN (?, '通用') ORDER BY RANDOM() LIMIT 1", (g_id, chosen_reg, gen)) as cur:
                f_row = await cur.fetchone()

            if chosen_reg == "東方":
                surname = s_row[0] if s_row else random.choice(["沈", "顧", "林", "裴", "許", "江"])
                firstname = f_row[0] if f_row else random.choice(["星川", "晚寧", "知意", "野", "淮", "瑤"])
                full_name = f"{surname}{firstname}"
                nation = random.choice(EASTERN_NATIONS)
            elif chosen_reg == "南美":
                surname = s_row[0] if s_row else random.choice(["席爾瓦", "桑托斯", "羅德里奎茲", "費南德茲", "莫拉萊斯"])
                firstname = f_row[0] if f_row else random.choice(["盧卡斯", "馬特奧", "瓦倫蒂娜", "卡蜜拉", "索菲亞"])
                full_name = f"{firstname}•{surname}"
                nation = random.choice(SOUTH_AMERICAN_NATIONS)
            elif chosen_reg == "非洲":
                surname = s_row[0] if s_row else random.choice(["奧卡福", "曼德拉", "特拉奧雷", "迪奧普", "哈桑"])
                firstname = f_row[0] if f_row else random.choice(["阿瑪拉", "贊達", "卡里姆", "法圖", "塔里克"])
                full_name = f"{firstname}•{surname}" if random.random() > 0.5 else f"{surname}{firstname}"
                nation = random.choice(AFRICAN_NATIONS)
            else:
                surname = s_row[0] if s_row else random.choice(["斯圖爾特", "羅曼諾夫", "卡佩", "溫莎", "布朗"])
                firstname = f_row[0] if f_row else random.choice(["安妮", "維克多", "伊蓮", "亞瑟", "奧利維亞"])
                full_name = f"{firstname}•{surname}"
                nation = random.choice(WESTERN_NATIONS)

            # 檢查重名
            async with db.execute("SELECT 1 FROM characters WHERE guild_id = ? AND name = ?", (g_id, full_name)) as cur:
                if await cur.fetchone():
                    full_name += f"_{random.randint(10, 99)}"

            # 3. 抽取相片（優先匹配該性別或通用）
            async with db.execute("SELECT id, image_url FROM crowd_photos WHERE guild_id = ? AND used = 0 AND gender IN (?, '通用') ORDER BY RANDOM() LIMIT 1", (g_id, gen)) as cur:
                p_row = await cur.fetchone()

            img_url = ""
            if p_row:
                p_id, img_url = p_row
                await db.execute("UPDATE crowd_photos SET used = 1 WHERE id = ?", (p_id,))
            else:
                # 若性別庫空了，試著取任意一張未使用的
                async with db.execute("SELECT id, image_url FROM crowd_photos WHERE guild_id = ? AND used = 0 ORDER BY RANDOM() LIMIT 1", (g_id,)) as cur:
                    fallback_p = await cur.fetchone()
                    if fallback_p:
                        await db.execute("UPDATE crowd_photos SET used = 1 WHERE id = ?", (fallback_p[0],))
                        img_url = fallback_p[1]

            # 4. 年齡、身高、身分、特質
            age = random.randint(16, 50)
            height = random.randint(172, 192) if gen == "男" else random.randint(158, 176)
            job = random.choice(CROWD_JOBS)
            tags = "、".join(random.sample(CROWD_TAGS_POOL, k=random.randint(2, 3)))
            relationship = random.choice(CROWD_RELATIONS)

            # 5. 初始金錢與核心數值（單項初始最高 2500）
            init_cash = random.randint(5000, 40000)
            init_bank = random.randint(20000, 200000)
            stat_names = ["流量熱度", "商業價值", "路人緣", "公關", "影響指數", "容貌", "才智", "個人才藝", "演繹", "唱跳"]
            stats = {k: random.randint(300, 2500) for k in stat_names}

            # 寫入角色資料表（is_npc = 3 標記為大眾動態路人）
            await db.execute("""
                INSERT INTO characters (
                    guild_id, user_id, name, age, gender, job, faction, tags,
                    relationship_status, created_at, is_npc, image_url, cash, bank, stats, rank, nationality, height
                ) VALUES (?, 0, ?, ?, ?, ?, '無', ?, ?, ?, 3, ?, ?, ?, ?, ?, ?, ?)
            """, (
                g_id, full_name, age, gen, job, tags,
                relationship, time.time(), img_url, init_cash, init_bank, json.dumps(stats, ensure_ascii=False), default_rank, nation, height
            ))
            created_list.append((full_name, gen, age, height, nation, job, default_rank, img_url))

        # 檢查照片庫存剩餘數
        async with db.execute("SELECT COUNT(*) FROM crowd_photos WHERE guild_id = ? AND used = 0", (g_id,)) as cur:
            rem_photos = (await cur.fetchone())[0]
            if rem_photos <= 5:
                low_photo_warn = True

        await db.commit()

    # 輸出生成卡片
    if len(created_list) == 1:
        c = created_list[0]
        embed = discord.Embed(title=f"🌟 大眾路人登場！【{c[0]}】", color=0x1ABC9C)
        embed.description = f"演藝圈新人已正式錄入名冊，即刻參與全城生態！"
        embed.add_field(name="基本履歷", value=f"• 國籍：`{c[4]}` ｜ 性別：`{c[1]}`\n• 年齡：`{c[2]} 歲` ｜ 身高：`{c[3]} cm`\n• 職業：`{c[5]}` ｜ 地位：**【{c[6]}】**", inline=False)
        if c[7]:
            embed.set_thumbnail(url=c[7])
    else:
        embed = discord.Embed(title=f"👥 大量發生完畢！成功生成 {len(created_list)} 位路人角色", color=0x1ABC9C)
        for c in created_list:
            embed.add_field(name=f"🎭 {c[0]} ({c[1]} / {c[4]})", value=f"{c[2]}歲・{c[3]}cm ｜ {c[5]} ｜ 【{c[6]}】", inline=False)

    warn_msg = f"\n\n🚨 **【系統警告：相冊庫存即將見底！】**\n目前未使用的照片僅剩 **{rem_photos}** 張，請管理員盡快使用 `/路人資源補給` 補充！" if low_photo_warn else ""
    await interaction.followup.send(content=warn_msg if low_photo_warn else None, embed=embed)
# -------------------- 指令：/發布傳聞 --------------------
@bot.tree.command(name="發布傳聞", description="【管理員專用】針對角色或貼文留下傳聞（累積滿三次關鍵字自動生成/更迭標籤）")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(角色名="傳聞主角姓名", 傳聞內容="寫下一句傳聞（例如: 聽說他最近私底下超級社恐，連招呼都不敢打）")
async def add_rumor_cmd(interaction: discord.Interaction, 角色名: str, 傳聞內容: str):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    content = 傳聞內容.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            if not await cur.fetchone():
                await interaction.response.send_message(f"❌ 查無角色【{c_name}】！", ephemeral=True)
                return

        # 紀錄傳聞歷史
        await db.execute("INSERT INTO rumors (guild_id, char_name, content, created_at) VALUES (?, ?, ?, ?)", (g_id, c_name, content, time.time()))

        # 比對標籤關鍵字
        async with db.execute("SELECT tag_name FROM tag_rules") as t_cur:
            all_tags = [r[0] for r in await t_cur.fetchall()]

        tag_evolve_msg = ""
        for tag in all_tags:
            if tag in content:
                await db.execute("""
                    INSERT INTO rumor_keyword_counts (guild_id, char_name, tag_name, count)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(guild_id, char_name, tag_name) DO UPDATE SET count = count + 1
                """, (g_id, c_name, tag))

                async with db.execute("SELECT count FROM rumor_keyword_counts WHERE guild_id = ? AND char_name = ? AND tag_name = ?", (g_id, c_name, tag)) as count_cur:
                    cnt = (await count_cur.fetchone())[0]

                if cnt >= 3:
                    # 達成三次關鍵字，重置並賦予標籤
                    await db.execute("UPDATE rumor_keyword_counts SET count = 0 WHERE guild_id = ? AND char_name = ? AND tag_name = ?", (g_id, c_name, tag))
                    tag_evolve_msg += await apply_character_tag(g_id, c_name, tag)

        await db.commit()

    await interaction.response.send_message(f"📢 **【流光城八卦小報】**\n傳聞發布成功：*「{content}」* ➔ 牽涉對象：**{c_name}**{tag_evolve_msg}")
# -------------------- 指令：/標籤與衝突管理 --------------------
@bot.tree.command(name="標籤與衝突管理", description="【管理員專用】新增、設定標籤條件與衝突覆蓋規則")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(性別限制=[
    app_commands.Choice(name="無限制", value="無"),
    app_commands.Choice(name="限定男", value="男"),
    app_commands.Choice(name="限定女", value="女")
])
@app_commands.describe(
    標籤名稱="欲建立的標籤名稱 (例如: 國民初戀)",
    性別限制="該標籤適用的性別",
    最小年齡="例如: 16 (0為不限)",
    最大年齡="例如: 25 (99為不限)",
    互斥衝突標籤="以逗號隔開 (當獲得此標籤時，這些衝突標籤會被刪除/覆蓋)",
    是否為負面標籤="1為負面標籤，0為普通/正面"
)
async def manage_tags_cmd(
    interaction: discord.Interaction,
    標籤名稱: str,
    性別限制: app_commands.Choice[str],
    最小年齡: int = 0,
    最大年齡: int = 99,
    互斥衝突標籤: str = "",
    是否為負面標籤: int = 0
):
    g_id = interaction.guild_id
    t_name = 標籤名稱.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO tag_rules (tag_name, gender_req, min_age, max_age, conflict_tags, is_negative)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tag_name) DO UPDATE SET
                gender_req = excluded.gender_req,
                min_age = excluded.min_age,
                max_age = excluded.max_age,
                conflict_tags = excluded.conflict_tags,
                is_negative = excluded.is_negative
        """, (t_name, 性別限制.value, 最小年齡, 最大年齡, 互斥衝突標籤.strip(), 是否為負面標籤))
        await db.commit()

    await interaction.response.send_message(
        f"✅ 標籤規則設定成功！\n"
        f"🏷️ 標籤：**【{t_name}】**\n"
        f"• 限制條件：`{性別限制.name}` ｜ 年齡：`{最小年齡}～{最大年齡} 歲`\n"
        f"• 衝突互斥：`{互斥衝突標籤 or '無'}` ｜ 屬性：`{'負面' if 是否為負面標籤 else '正面/特質'}`"
    )

# -------------------- 指令：/路人生態設定 --------------------
@bot.tree.command(name="路人生態設定", description="【管理員專用】調整大眾路人每 48 小時的數值與金錢浮動規則")
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
    增減量="填純數字。若選百分比，填 5 代表 ±5%；若選固定點數，填 50 代表 ±50 點",
    單項最高上限="數值浮動的最高天花板（預設 3000）"
)
async def setting_crowd_npc(
    interaction: discord.Interaction,
    計算模式: app_commands.Choice[str],
    增減量: float,
    金錢是否浮動: app_commands.Choice[str],
    單項最高上限: int = 3000
):
    g_id = interaction.guild_id
    rate_val = (增減量 / 100.0) if 計算模式.value == "percent" else 增減量

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'npc_fluct_mode', ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = ?", (g_id, 計算模式.value, 計算模式.value))
        await db.execute("INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'npc_fluct_rate', ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = ?", (g_id, str(rate_val), str(rate_val)))
        await db.execute("INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'npc_fluct_money', ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = ?", (g_id, 金錢是否浮動.value, 金錢是否浮動.value))
        await db.execute("INSERT INTO system_settings (guild_id, key, value) VALUES (?, 'npc_fluct_cap', ?) ON CONFLICT(guild_id, key) DO UPDATE SET value = ?", (g_id, str(單項最高上限), str(單項最高上限)))
        await db.commit()

    unit_desc = f"±{增減量}%" if 計算模式.value == "percent" else f"±{int(增減量)} 點"
    embed = discord.Embed(title="⚙️ 大眾路人生態行情已更新", color=0x2ECC71)
    embed.add_field(name="48小時波動機制", value=f"【{計算模式.name}】（幅度：`{unit_desc}`）", inline=False)
    embed.add_field(name="金錢資產連動", value="已開啟" if 金錢是否浮動.value == "1" else "已關閉", inline=True)
    embed.add_field(name="屬性天花板", value=f"最高 {單項最高上限} 點", inline=True)
    await interaction.response.send_message(embed=embed)
# -------------------- 指令：/寵物中心 --------------------
@bot.tree.command(name="寵物中心", description="為角色置辦寵物（自訂暱稱，具有壽命與健康值系統）")
@app_commands.choices(寵物類別=[
    app_commands.Choice(name="布偶貓 (壽命: 15年 / 售價: $30,000)", value="貓:15:30000"),
    app_commands.Choice(name="柴犬 (壽命: 12年 / 售價: $25,000)", value="狗:12:25000"),
    app_commands.Choice(name="垂耳兔 (壽命: 8年 / 售價: $12,000)", value="兔:8:12000"),
    app_commands.Choice(name="玄鳳鸚鵡 (壽命: 18年 / 售價: $18,000)", value="鳥:18:18000")
])
@app_commands.describe(角色名="欲領養寵物的角色名稱", 寵物類別="選擇心儀的寵物品種", 寵物暱稱="為牠取一個名字")
async def buy_pet_cmd(
    interaction: discord.Interaction,
    角色名: str,
    寵物類別: app_commands.Choice[str],
    寵物暱稱: str
):
    g_id = interaction.guild_id
    c_name = 角色名.strip()
    p_name = 寵物暱稱.strip()

    p_type, lifespan_years, price_str = 寵物類別.value.split(":")
    lifespan_days = int(lifespan_years) * 365 # 真實天數換算
    price = int(price_str)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT cash, bank FROM characters WHERE guild_id = ? AND name = ?", (g_id, c_name)) as cur:
            c_row = await cur.fetchone()
            if not c_row:
                await interaction.response.send_message("❌ 查無此角色！", ephemeral=True)
                return
            cash, bank = c_row

        if cash + bank < price:
            await interaction.response.send_message(f"❌ 總資產不足以支付領養費用 **${price:,}**！", ephemeral=True)
            return

        # 自動扣款
        if cash >= price:
            await db.execute("UPDATE characters SET cash = cash - ? WHERE guild_id = ? AND name = ?", (price, g_id, c_name))
        else:
            remain = price - cash
            await db.execute("UPDATE characters SET cash = 0, bank = bank - ? WHERE guild_id = ? AND name = ?", (remain, g_id, c_name))

        # 寫入寵物表
        await db.execute("""
            INSERT INTO pets (guild_id, owner_name, pet_type, pet_name, health, lifespan_days, bought_at, status)
            VALUES (?, ?, ?, ?, 500, ?, ?, '活潑健康')
        """, (g_id, c_name, p_type, p_name, lifespan_days, time.time()))
        await db.commit()

    await interaction.response.send_message(
        f"🎉 領養手續辦妥！\n"
        f"恭喜 **{c_name}** 正式迎來新家人：【{p_type}】**{p_name}**！\n"
        f"• 預估壽命：**{lifespan_years} 年**\n"
        f"• 初始健康值：**500/500**（每天會自然扣減 5 點，請記得於商城採購專屬飼料照料）！"
    )

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

