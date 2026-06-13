import os
import json
import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread
import random
import string
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
TOKEN = os.environ.get("BOT_TOKEN", "")
DATA_FILE = "data/users.json"
SQUADS_FILE = "data/squads.json"
BOSSES_FILE = "data/bosses.json"

# ========== FLASK ==========
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Vysotix bot is running"

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    Thread(target=run_flask, daemon=True).start()

# ========== КОНСТАНТЫ ==========

CLASSES = {
    "warrior": {"name": "Воин",      "emoji": "⚔️",  "bonus_attr": "str"},
    "archer":  {"name": "Лучник",    "emoji": "🏹",  "bonus_attr": "agi"},
    "mage":    {"name": "Маг",       "emoji": "🔮",  "bonus_attr": "int"},
    "rogue":   {"name": "Разбойник", "emoji": "🗡️",  "bonus_attr": "wil"},
    "parent":  {"name": "Родитель",  "emoji": "👨‍👩‍👧‍👦", "bonus_attr": "wil"},
}

ATTRS = {
    "str": {"name": "Сила",      "emoji": "💪", "hint": "тренировки, спорт"},
    "int": {"name": "Интеллект", "emoji": "📚", "hint": "чтение, учёба"},
    "hp":  {"name": "Здоровье",  "emoji": "❤️", "hint": "сон, питание, режим"},
    "agi": {"name": "Ловкость",  "emoji": "🤸", "hint": "растяжка, координация"},
    "wil": {"name": "Воля",      "emoji": "🔥", "hint": "сложные привычки"},
}

GEAR_UNLOCKS = {
    2:  "🗡️ Начальное оружие",
    3:  "🛡️ Щит / колчан",
    4:  "🥋 Лёгкий доспех",
    5:  "🧥 Плащ следопыта",
    7:  "💍 Кольцо силы",
    10: "✨ Легендарный облик",
}

XP_TABLE = [0, 100, 200, 350, 500, 700, 950, 1250, 1600, 2000, 2500]

TASK_DIFFICULTY = {
    "easy": {"name": "Лёгкое", "emoji": "⭐", "xp": 20, "attr": 1, "stars": 1},
    "medium": {"name": "Среднее", "emoji": "🌟🌟", "xp": 35, "attr": 2, "stars": 2},
    "hard": {"name": "Сложное", "emoji": "🌟🌟🌟", "xp": 50, "attr": 3, "stars": 3},
}

REWARDS_SHOP = {
    "screen_time": {"name": "📱 30 мин экранного времени", "cost": 5, "desc": "Дополнительные 30 минут"},
    "screen_time_1h": {"name": "📱 1 час экранного времени", "cost": 8, "desc": "Дополнительный час"},
    "sweets": {"name": "🍬 Сладости", "cost": 3, "desc": "Любимое лакомство"},
    "movie": {"name": "🎬 Кино вечером", "cost": 10, "desc": "Выбор фильма на вечер"},
    "game": {"name": "🎮 Игровой вечер", "cost": 12, "desc": "Дополнительное время на игры"},
    "park": {"name": "🌳 Поход в парк", "cost": 15, "desc": "Прогулка в любимом парке"},
    "toy": {"name": "🎁 Новая игрушка", "cost": 25, "desc": "Небольшой подарок на выбор"},
}

BOSS_POOL = [
    {
        "phases": ["🐉 Дракон Лени", "🔥 Пылающий Дракон", "💀 Дракон Тьмы"],
        "weak_attr": "wil", "hp": 300,
        "reward": "🐉 Клык Дракона",
        "reward_desc": "Редкий аксессуар за победу над первым боссом",
        "flavor": "Пожирает мотивацию. Слаб против Воли.",
    },
    {
        "phases": ["👾 Туманный Великан", "⚡ Великан Бури", "🌑 Великан Хаоса"],
        "weak_attr": "hp", "hp": 400,
        "reward": "🌿 Амулет здоровья",
        "reward_desc": "Даёт здоровье даже в самые тёмные дни",
        "flavor": "Нарушает режим сна. Слаб против Здоровья.",
    },
    {
        "phases": ["🍔 Король Фастфуда", "🌶️ Огненный Король", "☠️ Король Яда"],
        "weak_attr": "hp", "hp": 350,
        "reward": "🥗 Щит Питания",
        "reward_desc": "Защищает от соблазнов",
        "flavor": "Отравляет привычки питания. Слаб против Здоровья.",
    },
    {
        "phases": ["📱 Повелитель Экранов", "🌀 Вихрь Отвлечений", "🕳️ Чёрная Дыра"],
        "weak_attr": "wil", "hp": 380,
        "reward": "🎯 Кольцо фокуса",
        "reward_desc": "Помогает не отвлекаться",
        "flavor": "Похищает время. Слаб против Воли.",
    },
    {
        "phases": ["📚 Страж Невежества", "🌫️ Туман Забвения", "🧟 Пожиратель Знаний"],
        "weak_attr": "int", "hp": 420,
        "reward": "📖 Tome мудреца",
        "reward_desc": "Артефакт знаний",
        "flavor": "Блокирует развитие. Слаб против Интеллекта.",
    },
]

# ========== ДАННЫЕ ==========

def load_users():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        users = json.load(f)
    
    # Миграция старых данных
    for uid, user in users.items():
        user.setdefault("stars", 0)
        user.setdefault("reward_history", [])
        user.setdefault("task_templates", [])
        user.setdefault("notify_time", None)
        for task in user.get("assigned_tasks", []):
            task.setdefault("stars_reward", 1)
            task.setdefault("deadline", "")
            task.setdefault("difficulty", "medium")
            task.setdefault("created_date", "")
    
    return users

def save_users(users):
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_squads():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(SQUADS_FILE):
        return {}
    with open(SQUADS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_squads(squads):
    os.makedirs("data", exist_ok=True)
    with open(SQUADS_FILE, "w", encoding="utf-8") as f:
        json.dump(squads, f, ensure_ascii=False, indent=2)

def load_bosses():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(BOSSES_FILE):
        return {}
    with open(BOSSES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_bosses(bosses):
    os.makedirs("data", exist_ok=True)
    with open(BOSSES_FILE, "w", encoding="utf-8") as f:
        json.dump(bosses, f, ensure_ascii=False, indent=2)

def new_user(name, cls_key, role="child"):
    return {
        "name": name,
        "class": cls_key,
        "role": role,
        "level": 1,
        "xp": 0,
        "attrs": {"str": 0, "int": 0, "hp": 0, "agi": 0, "wil": 0},
        "streak": 0,
        "last_done_date": "",
        "tasks": [],
        "assigned_tasks": [],
        "gear": [],
        "squad_id": None,
        "stars": 0,
        "reward_history": [],
        "task_templates": [],
        "notify_time": None,
    }

def xp_needed(lvl):
    if lvl < len(XP_TABLE):
        return XP_TABLE[lvl]
    return XP_TABLE[-1] + (lvl - len(XP_TABLE) + 1) * 600

def update_streak(user):
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))
    last = user.get("last_done_date", "")
    if last == today:
        return
    elif last == yesterday:
        user["streak"] = user.get("streak", 0) + 1
    else:
        user["streak"] = 1
    user["last_done_date"] = today

def add_xp(user, amount):
    user["xp"] += amount
    leveled = False
    while user["xp"] >= xp_needed(user["level"]):
        user["xp"] -= xp_needed(user["level"])
        user["level"] += 1
        leveled = True
        gear = GEAR_UNLOCKS.get(user["level"])
        if gear and gear not in user["gear"]:
            user["gear"].append(gear)
    return leveled

def reset_daily_tasks(user):
    today = str(date.today())
    for t in user.get("tasks", []):
        if t.get("done_date") != today:
            t["done"] = False
    for t in user.get("assigned_tasks", []):
        if t.get("done_date") != today:
            t["done"] = False

# ========== БОСС ==========

def get_or_create_boss(squad_id):
    bosses = load_bosses()
    today = str(date.today())
    if squad_id in bosses:
        boss = bosses[squad_id]
        created = boss.get("created", today)
        days_alive = (date.today() - date.fromisoformat(created)).days
        if days_alive < 7 and not boss.get("defeated"):
            return boss, bosses
    template = random.choice(BOSS_POOL)
    boss = {
        "phases": template["phases"],
        "weak_attr": template["weak_attr"],
        "hp_max": template["hp"],
        "hp": template["hp"],
        "reward": template["reward"],
        "reward_desc": template["reward_desc"],
        "flavor": template["flavor"],
        "created": today,
        "deadline": str(date.today() + timedelta(days=7)),
        "defeated": False,
        "damage_log": {},
        "last_hit_date": {},
    }
    bosses[squad_id] = boss
    save_bosses(bosses)
    return boss, bosses

def boss_phase(boss):
    pct = boss["hp"] / boss["hp_max"]
    if pct > 0.66:
        return 0, boss["phases"][0]
    elif pct > 0.33:
        return 1, boss["phases"][1]
    else:
        return 2, boss["phases"][2]

def boss_hp_bar(boss):
    pct = boss["hp"] / boss["hp_max"]
    filled = int(pct * 12)
    return "❤️" * filled + "🖤" * (12 - filled)

def calc_damage(task_attr, boss_weak_attr, user_attr_val):
    base = 8 + min(user_attr_val // 5, 12)
    if task_attr == boss_weak_attr:
        base = int(base * 1.5)
    return base

def boss_card(boss, squad_id, users_data, squad_members):
    phase_idx, phase_name = boss_phase(boss)
    hp_bar = boss_hp_bar(boss)
    days_left = (date.fromisoformat(boss["deadline"]) - date.today()).days
    weak_attr = ATTRS[boss["weak_attr"]]
    dmg_log = boss.get("damage_log", {})
    top = sorted(dmg_log.items(), key=lambda x: x[1], reverse=True)
    top_text = ""
    for mid, dmg in top[:3]:
        m = users_data.get(mid)
        if m:
            top_text += f"  {CLASSES.get(m['class'], CLASSES['warrior'])['emoji']} {m['name']}: {dmg} урона\n"
    phase_stars = "⭐" * (phase_idx + 1)
    return (
        f"{phase_name} {phase_stars}\n\n"
        f"{hp_bar}\n"
        f"HP: {boss['hp']} / {boss['hp_max']}\n\n"
        f"_{boss['flavor']}_\n\n"
        f"⚡ Слабость: {weak_attr['emoji']} {weak_attr['name']} — +50% урон!\n"
        f"⏳ До конца рейда: {max(0, days_left)} дн.\n\n"
        f"*Урон отряда:*\n{top_text if top_text else '  пока нет урона'}"
    )

# ========== КАРТОЧКА ГЕРОЯ ==========

def char_card(user):
    cls = CLASSES.get(user["class"], CLASSES["warrior"])
    lvl = user["level"]
    xp = user["xp"]
    xp_max = xp_needed(lvl)
    filled = int((xp / xp_max) * 10) if xp_max > 0 else 0
    bar = "█" * filled + "░" * (10 - filled)
    attrs_lines = ""
    for key, a in ATTRS.items():
        val = user["attrs"].get(key, 0)
        dots = min(val // 3, 10)
        mini = "●" * dots + "○" * (10 - dots)
        attrs_lines += f"{a['emoji']} {a['name']:<12} {val:>3}  {mini}\n"
    gear_text = "\n".join(f"  {g}" for g in user["gear"]) if user["gear"] else "  пока нет"
    today = str(date.today())
    done_today = len([t for t in user.get("tasks", []) if t.get("done_date") == today])
    total = len(user.get("tasks", []))
    
    role_label = "Родитель 👨‍👩‍👧‍👦" if user.get("role") == "parent" else "Ребенок 🧒"
    
    card = (
        f"{cls['emoji']} *{user['name']}* — {cls['name']} ({role_label})\n"
        f"⭐ Уровень {lvl}   🔥 Стрик {user.get('streak', 0)} дн.\n"
        f"Опыт: {xp} / {xp_max}\n"
        f"`{bar}`\n\n"
        f"*Атрибуты:*\n`{attrs_lines}`\n"
        f"*Снаряжение:*\n{gear_text}\n\n"
        f"✅ Свои задания: {done_today}/{total}\n"
    )
    if user.get("role") != "parent":
        done_assigned = len([t for t in user.get("assigned_tasks", []) if t.get("done_date") == today])
        total_assigned = len(user.get("assigned_tasks", []))
        card += f"👨👦 От родителей: {done_assigned}/{total_assigned}\n"
        card += f"🌟 Звёзды: {user.get('stars', 0)}"
    return card

# ========== ГЛАВНОЕ МЕНЮ ==========

async def show_menu(target, uid, edit=False):
    users = load_users()
    user = users.get(uid)
    if not user:
        text = "Сначала создай героя: /start"
        if edit:
            await target.edit_message_text(text)
        else:
            await target.message.reply_text(text)
        return

    role = user.get("role", "child")

    if role == "parent":
        cls = CLASSES.get(user["class"], CLASSES["warrior"])
        today = str(date.today())
        done_today = len([t for t in user.get("tasks", []) if t.get("done_date") == today])
        total = len(user.get("tasks", []))
        
        squad_id = user.get("squad_id")
        squads = load_squads()
        
        children_info = ""
        children_list = []
        if squad_id and squad_id in squads:
            squad = squads[squad_id]
            for mid in squad.get("members", []):
                if mid == uid:
                    continue
                m = users.get(mid)
                if m and m.get("role") == "child":
                    children_list.append(mid)
                    m_cls = CLASSES.get(m["class"], {"emoji": "🧒", "name": "Ребенок"})
                    m_done_today = len([t for t in m.get("tasks", []) if t.get("done_date") == today])
                    m_done_assigned = len([t for t in m.get("assigned_tasks", []) if t.get("done_date") == today])
                    m_total = len(m.get("tasks", []))
                    m_total_assigned = len(m.get("assigned_tasks", []))
                    children_info += (
                        f"  {m_cls['emoji']} *{m['name']}* (Ур. {m['level']}): "
                        f"свои {m_done_today}/{m_total} | от родителей {m_done_assigned}/{m_total_assigned} | 🌟{m.get('stars', 0)}\n"
                    )
        if children_info:
            children_info = f"\n*🧒 Дети:*\n{children_info}"
            
        boss_line = ""
        if squad_id:
            boss, _ = get_or_create_boss(squad_id)
            if not boss["defeated"]:
                _, phase_name = boss_phase(boss)
                pct = int(boss["hp"] / boss["hp_max"] * 100)
                boss_line = f"\n⚔️ Рейд: {phase_name} — {pct}% HP"
        
        kb = [
            [InlineKeyboardButton("👤 Мой герой", callback_data="profile"),
             InlineKeyboardButton("📋 Мои задания", callback_data="tasks")],
            [InlineKeyboardButton("➕ Моё задание", callback_data="add_task"),
             InlineKeyboardButton("🏰 Отряд", callback_data="squad")],
        ]
        
        if children_list:
            kb.insert(1, [InlineKeyboardButton("👨‍👧 Задания детям", callback_data="assign_menu")])
            
        kb.append([InlineKeyboardButton("⚔️ Босс рейд", callback_data="boss")])
        
        text = (
            f"👨‍👩‍👧‍👦 *Родитель {user['name']}* ({cls['name']}) · Ур. {user['level']} · 🔥 {user.get('streak', 0)}\n"
            f"✅ Свои задания сегодня: {done_today}/{total}"
            f"{children_info}"
            f"{boss_line}"
        )
        markup = InlineKeyboardMarkup(kb)
    else:
        cls = CLASSES.get(user["class"], CLASSES["warrior"])
        today = str(date.today())
        done_today = len([t for t in user.get("tasks", []) if t.get("done_date") == today])
        done_assigned = len([t for t in user.get("assigned_tasks", []) if t.get("done_date") == today])
        total = len(user.get("tasks", []))
        total_assigned = len(user.get("assigned_tasks", []))
        stars = user.get("stars", 0)

        squad_id = user.get("squad_id")
        boss_line = ""
        if squad_id:
            boss, _ = get_or_create_boss(squad_id)
            if not boss["defeated"]:
                _, phase_name = boss_phase(boss)
                pct = int(boss["hp"] / boss["hp_max"] * 100)
                boss_line = f"\n⚔️ Рейд: {phase_name} — {pct}% HP"

        assigned_line = ""
        if total_assigned > 0:
            pending = total_assigned - done_assigned
            if pending > 0:
                assigned_line = f"\n👨👦 Заданий от родителей: {pending} ждут выполнения"

        kb = [
            [InlineKeyboardButton("👤 Мой герой", callback_data="profile"),
             InlineKeyboardButton("📋 Задания", callback_data="tasks")],
            [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task"),
             InlineKeyboardButton("🏰 Отряд", callback_data="squad")],
            [InlineKeyboardButton("🌟 Магазин наград", callback_data="reward_shop")],
            [InlineKeyboardButton("⚔️ Босс рейд", callback_data="boss")],
        ]
        text = (
            f"{cls['emoji']} *{user['name']}* · Ур. {user['level']} · 🔥 {user.get('streak', 0)}\n"
            f"🌟 Звёзды: {stars}\n"
            f"✅ Сегодня: {done_today}/{total}"
            f"{assigned_line}"
            f"{boss_line}"
        )
        markup = InlineKeyboardMarkup(kb)

    if edit:
        await target.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await target.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")

# ========== МЕНЮ НАЗНАЧЕНИЯ ЗАДАНИЙ ==========

async def show_assign_menu(query, uid):
    """Показывает меню выбора ребенка для назначения задания"""
    users = load_users()
    user = users.get(uid)
    
    if not user or user.get("role") != "parent":
        await query.edit_message_text("Эта функция доступна только родителям!")
        return
    
    squad_id = user.get("squad_id")
    if not squad_id:
        await query.edit_message_text(
            "У вас нет отряда! Создайте отряд и добавьте детей.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu")]])
        )
        return
    
    squads = load_squads()
    squad = squads.get(squad_id, {})
    members = squad.get("members", [])
    
    children = []
    for mid in members:
        if mid == uid:
            continue
        m = users.get(mid)
        if m and m.get("role") == "child":
            children.append((mid, m))
    
    if not children:
        await query.edit_message_text(
            "В отряде нет детей! Добавьте ребенка в отряд.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu")]])
        )
        return
    
    kb = []
    today = str(date.today())
    
    for child_id, child in children:
        assigned_tasks = child.get("assigned_tasks", [])
        done_today = len([t for t in assigned_tasks if t.get("done_date") == today])
        pending = len(assigned_tasks) - done_today
        
        status = f"📋 {len(assigned_tasks)} заданий"
        if pending > 0:
            status += f" · ⏳ {pending} ждут"
        else:
            status += " · ✅ все выполнены"
        
        kb.append([InlineKeyboardButton(
            f"👤 {child['name']} (Ур.{child['level']}) · 🌟{child.get('stars', 0)} - {status}",
            callback_data=f"assign_to_{child_id}"
        )])
    
    kb.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="menu")])
    
    await query.edit_message_text(
        "👨‍👧 *Назначить задание*\n\nВыберите ребенка:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

# ========== КОМАНДЫ ==========

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    args = ctx.args
    if args and args[0].startswith("squad_"):
        squad_id = args[0].replace("squad_", "")
        users = load_users()
        squads = load_squads()
        if uid in users and squad_id in squads:
            users[uid]["squad_id"] = squad_id
            if uid not in squads[squad_id]["members"]:
                squads[squad_id]["members"].append(uid)
            save_users(users)
            save_squads(squads)
            await update.message.reply_text(
                f"⚔️ Ты вступил в отряд *{squads[squad_id]['name']}*!",
                parse_mode="Markdown"
            )
            await show_menu(update, uid)
            return
        elif uid not in users:
            ctx.user_data["pending_squad"] = squad_id

    users = load_users()
    if uid in users:
        reset_daily_tasks(users[uid])
        save_users(users)
        await show_menu(update, uid)
        return

    if args and args[0].isalnum() and len(args[0]) == 6:
        ctx.user_data["pending_squad_code"] = args[0]
    
    ctx.user_data.clear()
    ctx.user_data["step"] = "choose_role"
    kb = [
        [InlineKeyboardButton("Родитель 👨‍👩‍👧‍👦", callback_data="role_parent")],
        [InlineKeyboardButton("Ребенок 🧒", callback_data="role_child")]
    ]
    await update.message.reply_text(
        "⚔️ *Добро пожаловать в Vysotix!*\n\n"
        "Здесь привычки прокачивают твоего героя.\n\n"
        "Выберите вашу роль в игре:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_users()
    if uid in users:
        reset_daily_tasks(users[uid])
        save_users(users)
    await show_menu(update, uid)

# ========== ТЕКСТ ==========

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    step = ctx.user_data.get("step")
    
    logger.info(f"handle_text: uid={uid}, step={step}, text={text}")

    # ВАЖНО: проверки step должны быть ПЕРВЫМИ
    if step == "squad_name":
        logger.info(f"Creating squad with name: {text}")
        if len(text) < 2:
            await update.message.reply_text("Название слишком короткое. Придумай название подлиннее:")
            return
        
        squad_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        squads = load_squads()
        users = load_users()
        
        squads[squad_id] = {"name": text, "members": [uid], "created": str(date.today())}
        save_squads(squads)
        logger.info(f"Squad created: {squad_id}")
        
        if uid not in users:
            logger.error(f"User {uid} not found in users!")
            await update.message.reply_text("Ошибка: сначала создай героя с помощью /start")
            ctx.user_data.clear()
            return
        
        users[uid]["squad_id"] = squad_id
        save_users(users)
        logger.info(f"User {uid} updated with squad_id {squad_id}")
        
        bot_me = await ctx.bot.get_me()
        link = f"https://t.me/{bot_me.username}?start=squad_{squad_id}"
        
        ctx.user_data.clear()
        
        await update.message.reply_text(
            f"🏰 *Отряд «{text}» создан!*\n\n"
            f"🔑 Код для вступления: `{squad_id}`\n\n"
            f"🔗 Ссылка-приглашение:\n{link}\n\n"
            f"*Отправь этот код ребенку, чтобы он вступил в отряд!*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎮 В главное меню", callback_data="menu")]
            ]),
            parse_mode="Markdown"
        )
        
        await show_menu(update, uid)
        return

    if step == "enter_squad_code":
        code = text.strip().upper()
        if len(code) != 6 or not code.isalnum():
            await update.message.reply_text(
                "❌ Код должен быть 6 символов (буквы и цифры).\n\nПопробуй ещё раз:"
            )
            return
        squads = load_squads()
        if code in squads:
            users = load_users()
            if uid in users:
                users[uid]["squad_id"] = code
                if uid not in squads[code]["members"]:
                    squads[code]["members"].append(uid)
                save_users(users)
                save_squads(squads)
                ctx.user_data.clear()
                await update.message.reply_text(
                    f"✅ Ты вступил в отряд *{squads[code]['name']}*!",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎮 В меню", callback_data="menu")]]),
                    parse_mode="Markdown"
                )
                await show_menu(update, uid)
            else:
                await update.message.reply_text("Ошибка: герой не найден. Используй /start")
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Попробовать снова", callback_data="join_squad_by_code")],
                [InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")]
            ])
            await update.message.reply_text(
                f"❌ Отряд с кодом `{code}` не найден.\n\nПроверь код или создай новый отряд.",
                reply_markup=kb,
                parse_mode="Markdown"
            )
        return

    if step == "name":
        if len(text) < 2 or len(text) > 20:
            await update.message.reply_text("Имя должно быть от 2 до 20 символов:")
            return
        ctx.user_data["temp_name"] = text
        ctx.user_data["step"] = "class"
        kb = [[InlineKeyboardButton(f"{v['emoji']} {v['name']}", callback_data=f"class_{k}")]
              for k, v in CLASSES.items() if k != "parent"]
        await update.message.reply_text(
            f"Отлично, *{text}*! Выбери класс героя:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    # Затем проверки awaiting_ состояний
    if ctx.user_data.get("awaiting_task_name"):
        if len(text) < 2:
            await update.message.reply_text("Название слишком короткое:")
            return
        ctx.user_data["temp_task_name"] = text
        ctx.user_data["awaiting_task_name"] = False
        kb = [[InlineKeyboardButton(f"{a['emoji']} {a['name']} — {a['hint']}", callback_data=f"tattr_{k}")]
              for k, a in ATTRS.items()]
        await update.message.reply_text(
            "Какой атрибут качает это задание?",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    if ctx.user_data.get("awaiting_assign_task_name"):
        if len(text) < 2:
            await update.message.reply_text("Название слишком короткое:")
            return
            
        users = load_users()
        user = users.get(uid)
        if not user or user.get("role") != "parent":
            await update.message.reply_text("Только родители могут давать задания!")
            ctx.user_data.pop("awaiting_assign_task_name", None)
            ctx.user_data.pop("assign_target_uid", None)
            ctx.user_data.pop("task_difficulty", None)
            return

        ctx.user_data["temp_assign_task_name"] = text
        ctx.user_data["awaiting_assign_task_name"] = False
        
        kb = [[InlineKeyboardButton(f"{a['emoji']} {a['name']} — {a['hint']}", callback_data=f"aattr_{k}")]
              for k, a in ATTRS.items()]
        kb.append([InlineKeyboardButton("◀️ Отмена", callback_data="cancel_assign")])
        
        await update.message.reply_text(
            "Какой атрибут качает это задание?",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

# ========== CALLBACKS ==========

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    data = query.data
    logger.info(f"Callback: uid={uid}, data={data}")
    
    users = load_users()
    user = users.get(uid)

    # --- Меню ---
    if data == "menu":
        if uid in users:
            reset_daily_tasks(users[uid])
            save_users(users)
        await show_menu(query, uid, edit=True)
        return

    # --- Выбор роли ---
    if data == "role_parent":
        ctx.user_data["temp_role"] = "parent"
        ctx.user_data["step"] = "name"
        await query.edit_message_text("Как вас зовут? (Имя родителя):")
        return
        
    if data == "role_child":
        ctx.user_data["temp_role"] = "child"
        ctx.user_data["step"] = "name"
        await query.edit_message_text("Как зовут твоего героя? (Имя ребенка):")
        return

    # --- Выбор класса ---
    if data.startswith("class_"):
        cls_key = data.replace("class_", "")
        name = ctx.user_data.get("temp_name", "Герой")
        role = ctx.user_data.get("temp_role", "child")
        users[uid] = new_user(name, cls_key, role=role)
        save_users(users)
        logger.info(f"User {uid} created with class {cls_key} and role {role}")
        
        pending_code = ctx.user_data.get("pending_squad_code")
        if pending_code:
            squads = load_squads()
            if pending_code in squads:
                users[uid]["squad_id"] = pending_code
                if uid not in squads[pending_code]["members"]:
                    squads[pending_code]["members"].append(uid)
                save_squads(squads)
                save_users(users)
                ctx.user_data.clear()
                await query.edit_message_text(
                    f"{CLASSES.get(cls_key, CLASSES['warrior'])['emoji']} Герой *{name}* ({CLASSES.get(cls_key, CLASSES['warrior'])['name']}) создан!\n\n"
                    f"✅ Ты вступил в отряд *{squads[pending_code]['name']}*!",
                    parse_mode="Markdown"
                )
                await show_menu(query, uid, edit=True)
                return

        pending_squad = ctx.user_data.get("pending_squad")
        if pending_squad:
            squads = load_squads()
            if pending_squad in squads:
                users[uid]["squad_id"] = pending_squad
                if uid not in squads[pending_squad]["members"]:
                    squads[pending_squad]["members"].append(uid)
                save_squads(squads)
                save_users(users)
                ctx.user_data.clear()
                await query.edit_message_text(
                    f"{CLASSES.get(cls_key, CLASSES['warrior'])['emoji']} Герой *{name}* ({CLASSES.get(cls_key, CLASSES['warrior'])['name']}) создан!\n\n"
                    f"✅ Ты вступил в отряд *{squads[pending_squad]['name']}*!",
                    parse_mode="Markdown"
                )
                await show_menu(query, uid, edit=True)
                return
        
        ctx.user_data.pop("temp_name", None)
        ctx.user_data.pop("temp_role", None)
        ctx.user_data.pop("step", None)
        
        kb = [
            [InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad_after_hero")],
            [InlineKeyboardButton("🔑 Вступить по коду", callback_data="join_squad_by_code")],
            [InlineKeyboardButton("🎮 Пропустить", callback_data="menu")],
        ]
        await query.edit_message_text(
            f"{CLASSES.get(cls_key, CLASSES['warrior'])['emoji']} Герой *{name}* ({CLASSES.get(cls_key, CLASSES['warrior'])['name']}) создан!\n\n"
            f"Теперь выбери действие:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    # --- Создать отряд после создания героя ---
    if data == "create_squad_after_hero":
        logger.info(f"create_squad_after_hero: setting step=squad_name for user {uid}")
        ctx.user_data.clear()
        ctx.user_data["step"] = "squad_name"
        await query.edit_message_text(
            "🏰 Придумай название отряда и напиши его:\n\n"
            "_Например: «Семья Ивановых», «Отряд богатырей»_",
            parse_mode="Markdown"
        )
        return
    
    # --- Вступить в отряд по коду ---
    if data == "join_squad_by_code":
        ctx.user_data.clear()
        ctx.user_data["step"] = "enter_squad_code"
        await query.edit_message_text(
            "🔑 Введи 6-значный код отряда:\n\n"
            "*(код можно найти в разделе отряда у создателя)*",
            parse_mode="Markdown"
        )
        return

    if not user:
        await query.edit_message_text("Сначала создай героя: /start")
        return

    # --- Профиль ---
    if data == "profile":
        reset_daily_tasks(user)
        save_users(users)
        kb = [[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
        await query.edit_message_text(
            char_card(user),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    # --- Задания ---
    if data == "tasks":
        reset_daily_tasks(user)
        save_users(users)
        await show_tasks_menu(query, uid)
        return

    if data == "add_task":
        ctx.user_data.clear()
        ctx.user_data["awaiting_task_name"] = True
        await query.edit_message_text(
            "➕ *Новое задание*\n\nВведи название задания:",
            parse_mode="Markdown"
        )
        return

    if data.startswith("tattr_"):
        attr_key = data.replace("tattr_", "")
        task_name = ctx.user_data.get("temp_task_name", "Задание")
        task = {
            "id": str(uuid.uuid4())[:8],
            "name": task_name,
            "attr": attr_key,
            "xp_gain": 25,
            "attr_gain": 2,
            "done": False,
            "done_date": "",
        }
        user.setdefault("tasks", []).append(task)
        save_users(users)
        ctx.user_data.pop("temp_task_name", None)
        ctx.user_data.pop("awaiting_task_name", None)
        await show_tasks_menu(query, uid)
        return

    # --- Меню назначения заданий ---
    if data == "assign_menu":
        await show_assign_menu(query, uid)
        return

    # --- Назначить задание конкретному ребенку ---
    if data.startswith("assign_to_"):
        target_uid = data.replace("assign_to_", "")
        target_user = users.get(target_uid)
        if not target_user:
            await query.answer("Ребенок не найден", show_alert=True)
            return
            
        if user.get("role") != "parent":
            await query.answer("Только родители могут давать задания!", show_alert=True)
            return
        
        ctx.user_data["assign_target_uid"] = target_uid
        
        kb = []
        for diff_key, diff in TASK_DIFFICULTY.items():
            kb.append([InlineKeyboardButton(
                f"{diff['emoji']} {diff['name']} (+{diff['xp']} XP, +{diff['attr']} атр, {diff['stars']}🌟)",
                callback_data=f"set_diff_{diff_key}"
            )])
        
        kb.append([InlineKeyboardButton("📋 Из шаблона", callback_data="from_template")])
        kb.append([InlineKeyboardButton("👁 Посмотреть задания", callback_data=f"view_member_{target_uid}")])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="assign_menu")])
        
        target_cls = CLASSES.get(target_user["class"], CLASSES["warrior"])
        today = str(date.today())
        assigned = target_user.get("assigned_tasks", [])
        done = len([t for t in assigned if t.get("done_date") == today])
        
        await query.edit_message_text(
            f"👤 *{target_user['name']}* ({target_cls['name']}) · Ур.{target_user['level']}\n"
            f"🌟 Звёзд: {target_user.get('stars', 0)}\n\n"
            f"📋 Заданий от вас: {len(assigned)}\n"
            f"✅ Выполнено сегодня: {done}/{len(assigned)}\n\n"
            f"*Выберите сложность задания:*",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    # --- Выбор сложности задания ---
    if data.startswith("set_diff_"):
        diff_key = data.replace("set_diff_", "")
        diff = TASK_DIFFICULTY.get(diff_key)
        if not diff:
            await query.answer("Ошибка сложности", show_alert=True)
            return
        
        target_uid = ctx.user_data.get("assign_target_uid")
        if not target_uid or target_uid not in users:
            await query.answer("Ошибка: ребенок не выбран", show_alert=True)
            return
        
        ctx.user_data["task_difficulty"] = diff_key
        ctx.user_data["awaiting_assign_task_name"] = True
        
        target_user = users[target_uid]
        await query.edit_message_text(
            f"📝 *Новое {diff['name'].lower()} задание для {target_user['name']}*\n\n"
            f"Напишите название задания:\n"
            f"_{diff['emoji']} +{diff['xp']} XP | +{diff['attr']} к атрибуту | +{diff['stars']}🌟_",
            parse_mode="Markdown"
        )
        return

    # --- Из шаблона ---
    if data == "from_template":
        target_uid = ctx.user_data.get("assign_target_uid")
        target_user = users.get(target_uid)
        templates = user.get("task_templates", [])
        
        if not templates:
            await query.answer("У вас нет сохранённых шаблонов", show_alert=True)
            return
        
        kb = []
        for i, tmpl in enumerate(templates):
            diff = TASK_DIFFICULTY.get(tmpl.get("difficulty", "medium"), TASK_DIFFICULTY["medium"])
            kb.append([InlineKeyboardButton(
                f"{tmpl['name']} {diff['emoji']}",
                callback_data=f"use_tmpl_{i}"
            )])
        
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data=f"assign_to_{target_uid}")])
        
        await query.edit_message_text(
            f"📋 *Шаблоны заданий*\n\nВыберите шаблон для {target_user['name']}:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    # --- Использование шаблона ---
    if data.startswith("use_tmpl_"):
        idx = int(data.replace("use_tmpl_", ""))
        templates = user.get("task_templates", [])
        if idx >= len(templates):
            await query.answer("Шаблон не найден", show_alert=True)
            return
        
        tmpl = templates[idx]
        target_uid = ctx.user_data.get("assign_target_uid")
        
        if not target_uid or target_uid not in users:
            await query.edit_message_text("Ошибка. Попробуй снова.")
            return
        
        target_user = users[target_uid]
        diff = TASK_DIFFICULTY.get(tmpl.get("difficulty", "medium"), TASK_DIFFICULTY["medium"])
        
        task = {
            "id": str(uuid.uuid4())[:8],
            "name": tmpl["name"],
            "attr": tmpl["attr"],
            "xp_gain": diff["xp"],
            "attr_gain": diff["attr"],
            "stars_reward": diff["stars"],
            "done": False,
            "done_date": "",
            "deadline": str(date.today()),
            "difficulty": tmpl.get("difficulty", "medium"),
            "assigned_by": uid,
            "assigned_by_name": user["name"],
            "created_date": str(date.today()),
        }
        
        target_user.setdefault("assigned_tasks", []).append(task)
        save_users(users)
        
        attr = ATTRS[tmpl["attr"]]
        
        try:
            await query.bot.send_message(
                chat_id=int(target_uid),
                text=(
                    f"👨‍👦 *{user['name']}* назначил тебе задание!\n\n"
                    f"📋 *{tmpl['name']}*\n"
                    f"{attr['emoji']} {attr['name']}\n"
                    f"{diff['emoji']} +{diff['xp']} XP | +{diff['stars']}🌟\n"
                    f"⏰ Выполнить сегодня\n\n"
                    f"Открой /menu → Задания чтобы выполнить его."
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error sending message to child: {e}")
        
        kb = [
            [InlineKeyboardButton("📝 Дать ещё задание", callback_data=f"assign_to_{target_uid}")],
            [InlineKeyboardButton("🎮 В главное меню", callback_data="menu")],
        ]
        
        await query.edit_message_text(
            f"✅ *Задание из шаблона назначено!*\n\n"
            f"👤 {target_user['name']}\n"
            f"📋 {tmpl['name']}\n"
            f"{attr['emoji']} Атрибут: {attr['name']}\n"
            f"{diff['emoji']} Сложность: {diff['name']}\n"
            f"🌟 +{diff['stars']} звёзд при выполнении\n"
            f"⏰ Срок: сегодня",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    # --- Выполнить своё задание ---
    if data.startswith("done_"):
        task_id = data.replace("done_", "")
        today = str(date.today())
        task = next((t for t in user.get("tasks", []) if t["id"] == task_id), None)
        if not task:
            await query.answer("Задание не найдено", show_alert=True)
            return
        if task.get("done_date") == today:
            await query.answer("Уже выполнено сегодня ✅", show_alert=True)
            return
        task["done"] = True
        task["done_date"] = today
        xp = task["xp_gain"]
        attr_key = task["attr"]
        user["attrs"][attr_key] = user["attrs"].get(attr_key, 0) + task["attr_gain"]
        update_streak(user)
        leveled = add_xp(user, xp)
        boss_msg = await apply_boss_damage(uid, attr_key, user, users, query)
        save_users(users)
        attr = ATTRS[attr_key]
        msg = (
            f"✅ *{task['name']}*\n\n"
            f"{attr['emoji']} {attr['name']} +{task['attr_gain']} · ⭐ +{xp} опыта\n"
            f"🔥 Стрик: {user['streak']} дн."
            f"{boss_msg}"
        )
        if leveled:
            gear = GEAR_UNLOCKS.get(user["level"], "")
            msg += f"\n\n🎉 *Уровень {user['level']}!*"
            if gear:
                msg += f"\nПолучено: {gear}"
        kb = [[InlineKeyboardButton("◀️ К заданиям", callback_data="tasks")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    # --- Выполнить назначенное задание ---
    if data.startswith("adone_"):
        task_id = data.replace("adone_", "")
        today = str(date.today())
        task = next((t for t in user.get("assigned_tasks", []) if t["id"] == task_id), None)
        if not task:
            await query.answer("Задание не найдено", show_alert=True)
            return
        if task.get("done_date") == today:
            await query.answer("Уже выполнено сегодня ✅", show_alert=True)
            return
        
        deadline = task.get("deadline", today)
        if today > deadline:
            await query.answer("⏰ Срок выполнения истёк!", show_alert=True)
            return
        
        task["done"] = True
        task["done_date"] = today
        xp = task.get("xp_gain", 30)
        attr_key = task["attr"]
        stars_earned = task.get("stars_reward", 1)
        
        user["attrs"][attr_key] = user["attrs"].get(attr_key, 0) + task.get("attr_gain", 2)
        user["stars"] = user.get("stars", 0) + stars_earned
        update_streak(user)
        leveled = add_xp(user, xp)
        boss_msg = await apply_boss_damage(uid, attr_key, user, users, query)
        save_users(users)

        assigner_uid = task.get("assigned_by")
        if assigner_uid:
            try:
                await query.bot.send_message(
                    chat_id=int(assigner_uid),
                    text=(
                        f"✅ *{user['name']}* выполнил ваше задание!\n\n"
                        f"📋 {task['name']}\n"
                        f"{ATTRS[attr_key]['emoji']} {ATTRS[attr_key]['name']} +{task.get('attr_gain', 2)}\n"
                        f"🌟 +{stars_earned} звёзд (всего: {user.get('stars', 0)})"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error notifying parent: {e}")

        attr = ATTRS[attr_key]
        deadline_bonus = ""
        if deadline == today:
            deadline_bonus = "\n⚡ *Бонус за выполнение день в день!*"
        
        msg = (
            f"✅ *{task['name']}*\n"
            f"_(задание от {task.get('assigned_by_name', 'Родителя')})_\n\n"
            f"{attr['emoji']} {attr['name']} +{task.get('attr_gain', 2)} · ⭐ +{xp} опыта\n"
            f"🌟 +{stars_earned} звёзд (всего: {user.get('stars', 0)})\n"
            f"🔥 Стрик: {user['streak']} дн."
            f"{deadline_bonus}"
            f"{boss_msg}"
        )
        if leveled:
            gear = GEAR_UNLOCKS.get(user["level"], "")
            msg += f"\n\n🎉 *Уровень {user['level']}!*"
            if gear:
                msg += f"\nПолучено: {gear}"
        
        kb = [
            [InlineKeyboardButton("◀️ К заданиям", callback_data="tasks")],
            [InlineKeyboardButton("🌟 Магазин наград", callback_data="reward_shop")],
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    # --- Выбор атрибута для назначенного задания ---
    if data.startswith("aattr_"):
        attr_key = data.replace("aattr_", "")
        target_uid = ctx.user_data.get("assign_target_uid")
        task_name = ctx.user_data.get("temp_assign_task_name", "")
        diff_key = ctx.user_data.get("task_difficulty", "medium")
        diff = TASK_DIFFICULTY.get(diff_key, TASK_DIFFICULTY["medium"])
        
        if not target_uid or target_uid not in users:
            await query.edit_message_text("Ошибка. Попробуй снова из меню заданий.")
            return
        
        if not task_name:
            await query.edit_message_text("Ошибка: название задания потерялось. Попробуйте снова.")
            return
            
        if user.get("role") != "parent":
            await query.edit_message_text("Только родители могут давать задания!")
            return
        
        target_user = users[target_uid]
        deadline = str(date.today())
        
        task = {
            "id": str(uuid.uuid4())[:8],
            "name": task_name,
            "attr": attr_key,
            "xp_gain": diff["xp"],
            "attr_gain": diff["attr"],
            "stars_reward": diff["stars"],
            "done": False,
            "done_date": "",
            "deadline": deadline,
            "difficulty": diff_key,
            "assigned_by": uid,
            "assigned_by_name": user["name"],
            "created_date": str(date.today()),
        }
        target_user.setdefault("assigned_tasks", []).append(task)
        
        template = {
            "name": task_name,
            "attr": attr_key,
            "difficulty": diff_key,
            "deadline_days": 0,
        }
        if template not in user.get("task_templates", []):
            user.setdefault("task_templates", []).append(template)
        
        save_users(users)
        
        ctx.user_data.pop("temp_assign_task_name", None)
        ctx.user_data.pop("task_difficulty", None)
        ctx.user_data.pop("assign_target_uid", None)
        ctx.user_data.pop("awaiting_assign_task_name", None)
        
        attr = ATTRS[attr_key]
        
        try:
            await query.bot.send_message(
                chat_id=int(target_uid),
                text=(
                    f"👨‍👦 *{user['name']}* назначил тебе задание!\n\n"
                    f"📋 *{task_name}*\n"
                    f"{attr['emoji']} {attr['name']}\n"
                    f"{diff['emoji']} +{diff['xp']} XP | +{diff['stars']}🌟\n"
                    f"⏰ Выполнить сегодня\n\n"
                    f"Открой /menu → Задания чтобы выполнить его."
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error sending message to child: {e}")
        
        kb = [
            [InlineKeyboardButton("📝 Дать ещё задание", callback_data=f"assign_to_{target_uid}")],
            [InlineKeyboardButton("🌟 Магазин наград", callback_data="reward_shop")],
            [InlineKeyboardButton("🎮 В главное меню", callback_data="menu")],
        ]
        
        await query.edit_message_text(
            f"✅ *Задание назначено!*\n\n"
            f"👤 {target_user['name']}\n"
            f"📋 {task_name}\n"
            f"{attr['emoji']} Атрибут: {attr['name']}\n"
            f"{diff['emoji']} Сложность: {diff['name']}\n"
            f"🌟 +{diff['stars']} звёзд при выполнении\n"
            f"⏰ Срок: сегодня\n\n"
            f"📋 Сохранено в шаблоны!",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    # --- Отмена назначения ---
    if data == "cancel_assign":
        ctx.user_data.pop("temp_assign_task_name", None)
        ctx.user_data.pop("task_difficulty", None)
        ctx.user_data.pop("awaiting_assign_task_name", None)
        await show_assign_menu(query, uid)
        return

    # --- Магазин наград ---
    if data == "reward_shop":
        stars = user.get("stars", 0)
        
        kb = []
        for reward_id, reward in REWARDS_SHOP.items():
            can_buy = "✅" if stars >= reward["cost"] else "🔒"
            kb.append([InlineKeyboardButton(
                f"{can_buy} {reward['name']} — {reward['cost']}🌟",
                callback_data=f"buy_{reward_id}"
            )])
        
        kb.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="menu")])
        
        await query.edit_message_text(
            f"🌟 *Магазин наград*\n\n"
            f"Ваши звёзды: {stars}🌟\n\n"
            f"*Доступные награды:*\n"
            f"_(Выполняйте задания родителей, чтобы получать звёзды)_",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    # --- Покупка награды ---
    if data.startswith("buy_"):
        reward_id = data.replace("buy_", "")
        reward = REWARDS_SHOP.get(reward_id)
        
        if not reward:
            await query.answer("Награда не найдена", show_alert=True)
            return
        
        stars = user.get("stars", 0)
        if stars < reward["cost"]:
            await query.answer(f"Недостаточно звёзд! Нужно {reward['cost']}🌟", show_alert=True)
            return
        
        user["stars"] = stars - reward["cost"]
        user.setdefault("reward_history", []).append({
            "name": reward["name"],
            "cost": reward["cost"],
            "date": str(date.today()),
        })
        save_users(users)
        
        squad_id = user.get("squad_id")
        if squad_id:
            squads = load_squads()
            squad = squads.get(squad_id, {})
            for mid in squad.get("members", []):
                m = users.get(mid)
                if m and m.get("role") == "parent":
                    try:
                        await query.bot.send_message(
                            chat_id=int(mid),
                            text=(
                                f"🌟 *{user['name']}* хочет получить награду!\n\n"
                                f"🎁 {reward['name']}\n"
                                f"Стоимость: {reward['cost']}🌟\n\n"
                                f"Не забудьте выдать награду!"
                            ),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Error notifying parent about reward: {e}")
        
        await query.edit_message_text(
            f"🎉 *Награда куплена!*\n\n"
            f"🎁 {reward['name']}\n"
            f"🌟 Потрачено: {reward['cost']} звёзд\n"
            f"Осталось: {user.get('stars', 0)}🌟\n\n"
            f"Родитель получил уведомление. Ожидайте награду!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ В магазин", callback_data="reward_shop")],
                [InlineKeyboardButton("🎮 В меню", callback_data="menu")],
            ]),
            parse_mode="Markdown"
        )
        return

    # --- Отряд ---
    if data == "squad":
        squad_id = user.get("squad_id")
        squads = load_squads()
        if not squad_id or squad_id not in squads:
            kb = [
                [InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")],
                [InlineKeyboardButton("🔑 Вступить по коду", callback_data="join_squad_by_code")],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu")],
            ]
            await query.edit_message_text(
                "🏰 У тебя пока нет отряда.\n\nСоздай свой или вступи по коду:",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return
        await show_squad_menu(query, uid, squad_id)
        return

    if data == "create_squad":
        logger.info(f"create_squad: setting step=squad_name for user {uid}")
        ctx.user_data.clear()
        ctx.user_data["step"] = "squad_name"
        await query.edit_message_text(
            "🏰 Придумай название отряда и напиши его:\n\n"
            "_Например: «Семья Ивановых», «Отряд богатырей»_",
            parse_mode="Markdown"
        )
        return

    # --- Просмотр заданий участника ---
    if data.startswith("view_member_"):
        target_uid = data.replace("view_member_", "")
        target_user = users.get(target_uid)
        if not target_user:
            await query.answer("Участник не найден", show_alert=True)
            return
            
        target_role = target_user.get("role", "child")
        today = str(date.today())
        own_tasks = target_user.get("tasks", [])
        assigned = target_user.get("assigned_tasks", [])
        own_done = len([t for t in own_tasks if t.get("done_date") == today])
        cls = CLASSES.get(target_user["class"], CLASSES["warrior"])

        task_lines = ""
        for t in own_tasks:
            status = "✅" if t.get("done_date") == today else "◻️"
            a = ATTRS[t["attr"]]
            task_lines += f"{status} {t['name']} {a['emoji']}\n"
            
        asgn_done = 0
        if target_role != "parent":
            asgn_done = len([t for t in assigned if t.get("done_date") == today])
            for t in assigned:
                status = "✅" if t.get("done_date") == today else "◻️"
                a = ATTRS[t["attr"]]
                deadline = t.get("deadline", "")
                deadline_info = ""
                if deadline and t.get("done_date") != today:
                    days_left = (date.fromisoformat(deadline) - date.today()).days
                    if days_left <= 0:
                        deadline_info = " ⏰"
                    else:
                        deadline_info = f" 📅{days_left}дн"
                task_lines += f"{status} {t['name']} {a['emoji']} 👨👦{deadline_info}\n"

        kb = []
        if user.get("role") == "parent" and target_role == "child":
            kb.append([InlineKeyboardButton(f"➕ Дать задание {target_user['name']}", callback_data=f"assign_to_{target_uid}")])
            
        kb.append([InlineKeyboardButton("◀️ Назад в отряд", callback_data="squad")])
        
        role_label = "Родитель 👨‍👩‍👧‍👦" if target_role == "parent" else "Ребенок 🧒"
        summary = f"Свои: {own_done}/{len(own_tasks)}"
        if target_role != "parent":
            summary += f" · От родителей: {asgn_done}/{len(assigned)}"
            
        await query.edit_message_text(
            f"{cls['emoji']} *{target_user['name']}* — Ур.{target_user['level']} ({role_label})\n"
            f"🌟 Звёзды: {target_user.get('stars', 0)}\n"
            f"🔥 Стрик: {target_user.get('streak', 0)} дн.\n\n"
            f"*Задания сегодня:*\n"
            f"{summary}\n\n"
            f"{task_lines if task_lines else 'Нет заданий'}",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    # --- Босс ---
    if data == "boss":
        squad_id = user.get("squad_id")
        if not squad_id:
            kb = [[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
            await query.edit_message_text(
                "⚔️ Для рейда нужен отряд.",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return
        boss, _ = get_or_create_boss(squad_id)
        squads = load_squads()
        squad = squads.get(squad_id, {})
        if boss["defeated"]:
            kb = [
                [InlineKeyboardButton("🔄 Следующий босс", callback_data="boss_next")],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu")],
            ]
            await query.edit_message_text(
                f"🏆 *Босс повержён!*\n\n"
                f"Награда: {boss['reward']}\n{boss['reward_desc']}\n\nГотов к следующему?",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown"
            )
            return
        card = boss_card(boss, squad_id, users, squad.get("members", []))
        
        kb = [
            [InlineKeyboardButton("📋 Выполнить задание", callback_data="tasks")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu")]
        ]
        
        await query.edit_message_text(
            f"⚔️ *Рейд отряда*\n\n{card}",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    if data == "boss_next":
        squad_id = user.get("squad_id")
        if squad_id:
            bosses = load_bosses()
            if squad_id in bosses:
                del bosses[squad_id]
                save_bosses(bosses)
            boss, _ = get_or_create_boss(squad_id)
            squads = load_squads()
            squad = squads.get(squad_id, {})
            card = boss_card(boss, squad_id, users, squad.get("members", []))
            
            kb = [
                [InlineKeyboardButton("📋 Выполнить задание", callback_data="tasks")],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu")]
            ]
            
            await query.edit_message_text(
                f"⚔️ *Новый рейд начался!*\n\n{card}",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown"
            )
        return

# ========== ВСПОМОГАТЕЛЬНЫЕ ==========

async def apply_boss_damage(uid, attr_key, user, users, query):
    squad_id = user.get("squad_id")
    if not squad_id:
        return ""
    boss, bosses = get_or_create_boss(squad_id)
    if boss["defeated"]:
        return ""
    attr_val = user["attrs"].get(attr_key, 0)
    dmg = calc_damage(attr_key, boss["weak_attr"], attr_val)
    boss["hp"] = max(0, boss["hp"] - dmg)
    boss.setdefault("damage_log", {})[uid] = boss["damage_log"].get(uid, 0) + dmg
    boss.setdefault("last_hit_date", {})[uid] = str(date.today())
    _, phase_name = boss_phase(boss)
    if attr_key == boss["weak_attr"]:
        msg = f"\n⚡ *Критический удар!* {phase_name} −{dmg} HP"
    else:
        msg = f"\n⚔️ {phase_name} −{dmg} HP"
    if boss["hp"] <= 0:
        boss["defeated"] = True
        reward = boss["reward"]
        squads = load_squads()
        squad = squads.get(squad_id, {})
        for mid in squad.get("members", []):
            m = users.get(mid)
            if m and reward not in m.get("gear", []):
                m.setdefault("gear", []).append(reward)
        msg += f"\n\n🏆 *БОСС ПОВЕРЖЁН!*\nВесь отряд получает: {reward}"
    save_bosses(bosses)
    return msg

async def show_squad_menu(query, uid, squad_id):
    users = load_users()
    squads = load_squads()
    squad = squads.get(squad_id, {})
    today = str(date.today())
    
    current_user = users.get(uid, {})
    current_role = current_user.get("role", "child")
    
    members_text = ""
    kb = []
    for mid in squad.get("members", []):
        m = users.get(mid)
        if not m:
            continue
        
        m_role = m.get("role", "child")
        role_label = "Родитель 👨‍👩‍👧‍👦" if m_role == "parent" else "Ребенок 🧒"
        cls = CLASSES.get(m["class"], CLASSES["warrior"])
        
        own_done = len([t for t in m.get("tasks", []) if t.get("done_date") == today])
        own_total = len(m.get("tasks", []))
        
        if m_role == "parent":
            members_text += (
                f"{cls['emoji']} *{m['name']}* — Ур.{m['level']} · {role_label} · 🔥{m.get('streak',0)}\n"
                f"  ✅ {own_done}/{own_total} сегодня\n\n"
            )
        else:
            asgn_done = len([t for t in m.get("assigned_tasks", []) if t.get("done_date") == today])
            asgn_total = len(m.get("assigned_tasks", []))
            members_text += (
                f"{cls['emoji']} *{m['name']}* — Ур.{m['level']} · {role_label} · 🔥{m.get('streak',0)} · 🌟{m.get('stars', 0)}\n"
                f"  ✅ {own_done}/{own_total} · 👨👦 {asgn_done}/{asgn_total}\n\n"
            )
            
        if mid != uid:
            if current_role == "parent" and m_role == "child":
                kb.append([InlineKeyboardButton(
                    f"👁 {m['name']} · дать задание",
                    callback_data=f"view_member_{mid}"
                )])
            else:
                kb.append([InlineKeyboardButton(
                    f"👁 {m['name']} · профиль",
                    callback_data=f"view_member_{mid}"
                )])

    bot_me = await query.bot.get_me()
    link = f"https://t.me/{bot_me.username}?start=squad_{squad_id}"
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])

    await query.edit_message_text(
        f"🏰 *{squad['name']}*\n\n{members_text}🔗 Пригласить:\n`{link}`\n\n🔑 Код для вступления: `{squad_id}`",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def show_tasks_menu(query, uid):
    users = load_users()
    user = users.get(uid)
    role = user.get("role", "child")
        
    today = str(date.today())
    own_tasks = user.get("tasks", [])
    assigned_tasks = user.get("assigned_tasks", []) if role != "parent" else []

    squad_id = user.get("squad_id")
    boss_hint = ""
    weak_attr = None
    if squad_id:
        boss, _ = get_or_create_boss(squad_id)
        if not boss["defeated"]:
            weak = ATTRS[boss["weak_attr"]]
            weak_attr = boss["weak_attr"]
            boss_hint = f"\n⚡ Слабость босса: {weak['emoji']} {weak['name']}"

    kb = []

    if own_tasks:
        for t in own_tasks:
            is_done = t.get("done_date") == today
            a = ATTRS[t["attr"]]
            status = "✅" if is_done else "◻️"
            bonus = " ⚡" if weak_attr and t["attr"] == weak_attr else ""
            kb.append([InlineKeyboardButton(
                f"{status} {t['name']} {a['emoji']}{bonus}",
                callback_data=f"done_{t['id']}"
            )])

    if role != "parent" and assigned_tasks:
        kb.append([InlineKeyboardButton("── 👨👦 От родителей ──", callback_data="noop")])
        for t in assigned_tasks:
            is_done = t.get("done_date") == today
            a = ATTRS[t["attr"]]
            status = "✅" if is_done else "◻️"
            bonus = " ⚡" if weak_attr and t["attr"] == weak_attr else ""
            
            deadline = t.get("deadline", "")
            deadline_info = ""
            if deadline and not is_done:
                days_left = (date.fromisoformat(deadline) - date.today()).days
                if days_left <= 0:
                    deadline_info = " ⏰"
                elif days_left == 1:
                    deadline_info = " 📅завтра"
                else:
                    deadline_info = f" 📅{days_left}дн"
            
            kb.append([InlineKeyboardButton(
                f"{status} {t['name']} {a['emoji']}{bonus}{deadline_info}",
                callback_data=f"adone_{t['id']}"
            )])

    if not own_tasks and not assigned_tasks:
        kb.append([InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
        await query.edit_message_text(
            "📋 Пока нет заданий. Добавь первое!",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    kb.append([InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")])
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])

    own_done = len([t for t in own_tasks if t.get("done_date") == today])
    summary = f"📋 *Задания* — свои {own_done}/{len(own_tasks)}"
    
    if role != "parent" and assigned_tasks:
        asgn_done = len([t for t in assigned_tasks if t.get("done_date") == today])
        summary += f" · от родителей {asgn_done}/{len(assigned_tasks)}"
        
    summary += boss_hint

    await query.edit_message_text(
        summary,
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

# ========== ЗАПУСК ==========

async def post_init(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать игру"),
        BotCommand("menu", "Главное меню"),
    ])

def main():
    app = Application.builder().token(TOKEN).build()
    app.post_init = post_init
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ Vysotix запущен")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
