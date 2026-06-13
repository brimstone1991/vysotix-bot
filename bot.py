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
TOKEN = os.environ.get("BOT_TOKEN", "")
DATA_FILE = "data/users.json"
SQUADS_FILE = "data/squads.json"
BOSSES_FILE = "data/bosses.json"

# Flask
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
    "warrior": {"name": "Воин", "emoji": "⚔️"},
    "archer": {"name": "Лучник", "emoji": "🏹"},
    "mage": {"name": "Маг", "emoji": "🔮"},
    "rogue": {"name": "Разбойник", "emoji": "🗡️"},
}

ATTRS = {
    "str": {"name": "Сила", "emoji": "💪", "hint": "тренировки, спорт"},
    "int": {"name": "Интеллект", "emoji": "📚", "hint": "чтение, учёба"},
    "hp": {"name": "Здоровье", "emoji": "❤️", "hint": "сон, питание"},
    "agi": {"name": "Ловкость", "emoji": "🤸", "hint": "растяжка"},
    "wil": {"name": "Воля", "emoji": "🔥", "hint": "сложные привычки"},
}

ROLES = {
    "parent": {"name": "Родитель", "emoji": "👨‍👦", "can_assign": True},
    "child": {"name": "Ребёнок", "emoji": "🧒", "can_assign": False},
}

GEAR_UNLOCKS = {2: "🗡️ Оружие", 3: "🛡️ Щит", 4: "🥋 Доспех", 5: "🧥 Плащ", 7: "💍 Кольцо", 10: "✨ Легенда"}
XP_TABLE = [0, 100, 200, 350, 500, 700, 950, 1250, 1600, 2000]

# Полный пул боссов (как в исходной полной версии)
BOSS_POOL = [
    {
        "phases": ["🐉 Дракон Лени", "🔥 Пылающий Дракон", "💀 Дракон Тьмы"],
        "weak_attr": "wil", "hp": 300,
        "reward": "🐉 Клык Дракона",
        "reward_desc": "Редкий аксессуар за победу",
        "flavor": "Пожирает мотивацию. Слаб против Воли.",
    },
    {
        "phases": ["👾 Туманный Великан", "⚡ Великан Бури", "🌑 Великан Хаоса"],
        "weak_attr": "hp", "hp": 400,
        "reward": "🌿 Амулет здоровья",
        "reward_desc": "Даёт здоровье в тёмные дни",
        "flavor": "Нарушает режим сна. Слаб против Здоровья.",
    },
    {
        "phases": ["🍔 Король Фастфуда", "🌶️ Огненный Король", "☠️ Король Яда"],
        "weak_attr": "hp", "hp": 350,
        "reward": "🥗 Щит Питания",
        "reward_desc": "Защищает от соблазнов",
        "flavor": "Отравляет привычки питания.",
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
        return json.load(f)

def save_users(users):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_squads():
    if not os.path.exists(SQUADS_FILE):
        return {}
    with open(SQUADS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_squads(squads):
    with open(SQUADS_FILE, "w", encoding="utf-8") as f:
        json.dump(squads, f, ensure_ascii=False, indent=2)

def load_bosses():
    if not os.path.exists(BOSSES_FILE):
        return {}
    with open(BOSSES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_bosses(bosses):
    with open(BOSSES_FILE, "w", encoding="utf-8") as f:
        json.dump(bosses, f, ensure_ascii=False, indent=2)

def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

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
        if user["level"] in GEAR_UNLOCKS:
            user["gear"].append(GEAR_UNLOCKS[user["level"]])
    return leveled

def reset_daily_tasks(user):
    today = str(date.today())
    for t in user.get("tasks", []):
        if t.get("done_date") != today:
            t["done"] = False
    for t in user.get("assigned_tasks", []):
        if t.get("done_date") != today:
            t["done"] = False

# ========== БОСС (полная механика) ==========
def get_or_create_boss(squad_id):
    bosses = load_bosses()
    today = str(date.today())
    # Если босс уже есть и не побеждён, возвращаем его
    if squad_id in bosses:
        boss = bosses[squad_id]
        created = boss.get("created", today)
        days_alive = (date.today() - date.fromisoformat(created)).days
        if days_alive < 7 and not boss.get("defeated"):
            return boss, bosses
    # Создаём нового случайного босса
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
            top_text += f"  {CLASSES[m['class']]['emoji']} {m['name']}: {dmg} урона\n"
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

# ========== КАРТОЧКА ГЕРОЯ ==========
def char_card(user):
    cls = CLASSES[user["class"]]
    role_emoji = ROLES[user["role"]]["emoji"]
    xp_max = xp_needed(user["level"])
    filled = int((user["xp"] / xp_max) * 10) if xp_max > 0 else 0
    bar = "█" * filled + "░" * (10 - filled)
    attrs = "\n".join([f"{ATTRS[k]['emoji']} {ATTRS[k]['name']}: {v}" for k, v in user["attrs"].items()])
    today = str(date.today())
    done = len([t for t in user.get("tasks", []) if t.get("done_date") == today])
    assigned_done = len([t for t in user.get("assigned_tasks", []) if t.get("done_date") == today])
    return (
        f"{cls['emoji']} *{user['name']}* {role_emoji}\n"
        f"⭐ Уровень {user['level']} 🔥 Стрик {user['streak']}\n"
        f"Опыт: {user['xp']}/{xp_max}\n`{bar}`\n\n"
        f"*Атрибуты:*\n{attrs}\n\n"
        f"*Снаряжение:*\n" + "\n".join(user.get("gear", [])) + "\n\n"
        f"✅ Свои: {done}/{len(user.get('tasks', []))}\n"
        f"👨‍👦 От родителей: {assigned_done}/{len(user.get('assigned_tasks', []))}"
    )

# ========== МЕНЮ ==========
async def show_menu(target, uid, edit=False):
    users = load_users()
    user = users.get(uid)
    if not user:
        msg = "Создай героя: /start"
        if edit:
            await target.edit_message_text(msg)
        else:
            await target.message.reply_text(msg)
        return

    today = str(date.today())
    done = len([t for t in user.get("tasks", []) if t.get("done_date") == today])
    total = len(user.get("tasks", []))
    pending_assigned = len([t for t in user.get("assigned_tasks", []) if t.get("done_date") != today])

    # Проверка статуса босса для отображения в меню
    squad_id = user.get("squad_id")
    boss_line = ""
    if squad_id:
        boss, _ = get_or_create_boss(squad_id)
        if not boss["defeated"]:
            _, phase_name = boss_phase(boss)
            pct = int(boss["hp"] / boss["hp_max"] * 100)
            boss_line = f"\n⚔️ Рейд: {phase_name} — {pct}% HP"

    kb = [
        [InlineKeyboardButton("👤 Мой герой", callback_data="profile"),
         InlineKeyboardButton("📋 Задания", callback_data="tasks")],
        [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task"),
         InlineKeyboardButton("🏰 Отряд", callback_data="squad")],
        [InlineKeyboardButton("⚔️ Босс рейд", callback_data="boss")],  # добавлена кнопка босса
    ]
    role_emoji = ROLES[user["role"]]["emoji"]
    text = f"{CLASSES[user['class']]['emoji']} *{user['name']}* {role_emoji} · Ур.{user['level']} · 🔥{user['streak']}\n✅ Сегодня: {done}/{total}"
    if pending_assigned:
        text += f"\n👨‍👦 Заданий от родителей: {pending_assigned}"
    if boss_line:
        text += boss_line

    markup = InlineKeyboardMarkup(kb)
    if edit:
        await target.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await target.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")

# ========== КОМАНДЫ ==========
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_users()
    if uid in users:
        await show_menu(update, uid)
        return
    ctx.user_data["step"] = "name"
    await update.message.reply_text(
        "⚔️ *Vysotix*\n\nКак зовут твоего героя?",
        parse_mode="Markdown"
    )

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await show_menu(update, uid)

# ========== ТЕКСТ ==========
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    step = ctx.user_data.get("step")

    # Шаг 1: Имя
    if step == "name":
        if len(text) < 2:
            await update.message.reply_text("Имя слишком короткое:")
            return
        ctx.user_data["temp_name"] = text
        ctx.user_data["step"] = "class"
        kb = [[InlineKeyboardButton(f"{v['emoji']} {v['name']}", callback_data=f"class_{k}")] for k, v in CLASSES.items()]
        await update.message.reply_text(
            f"Отлично, *{text}*! Выбери класс героя:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    # Шаг 2: Название отряда
    if step == "squad_name":
        if len(text) < 2:
            await update.message.reply_text("Название слишком короткое:")
            return
        squad_id = generate_code()
        squads = load_squads()
        squads[squad_id] = {"name": text, "members": [uid], "created": str(date.today()), "creator": uid}
        save_squads(squads)
        users = load_users()
        if uid in users:
            users[uid]["squad_id"] = squad_id
            users[uid]["role"] = "parent"   # создатель – родитель
            save_users(users)
        ctx.user_data["step"] = None
        await update.message.reply_text(
            f"🏰 *Отряд «{text}» создан!*\nКод: `{squad_id}`\n\n"
            f"Ты стал *Родителем* в этом отряде.\n"
            f"Теперь ты можешь давать задания и сражаться с боссами!\n\n"
            f"Отправь код тому, кого хочешь пригласить.\n/menu",
            parse_mode="Markdown"
        )
        return

    # Добавление своего задания
    if ctx.user_data.get("awaiting_task_name"):
        if len(text) < 2:
            await update.message.reply_text("Название слишком короткое:")
            return
        ctx.user_data["temp_task_name"] = text
        ctx.user_data["awaiting_task_name"] = False
        ctx.user_data["awaiting_attr"] = True
        kb = [[InlineKeyboardButton(f"{a['emoji']} {a['name']}", callback_data=f"task_attr_{k}")] for k, a in ATTRS.items()]
        await update.message.reply_text("Какой атрибут качает это задание?", reply_markup=InlineKeyboardMarkup(kb))
        return

    # Вступление в отряд
    if ctx.user_data.get("awaiting_squad_code"):
        squad_code = text.upper()
        squads = load_squads()
        if squad_code not in squads:
            await update.message.reply_text("Код не найден. Попробуй ещё:")
            return
        users = load_users()
        if uid in users:
            old = users[uid].get("squad_id")
            if old and old in squads and uid in squads[old]["members"]:
                squads[old]["members"].remove(uid)
            users[uid]["squad_id"] = squad_code
            users[uid]["role"] = "child"
            if uid not in squads[squad_code]["members"]:
                squads[squad_code]["members"].append(uid)
            save_users(users)
            save_squads(squads)
            await update.message.reply_text(
                f"✅ Ты вступил в отряд *{squads[squad_code]['name']}*!\n"
                f"Твоя роль: *Ребёнок* 🧒\n\n/menu",
                parse_mode="Markdown"
            )
        else:
            ctx.user_data["pending_squad"] = squad_code
            await update.message.reply_text("Сначала создай героя: /start")
        ctx.user_data["awaiting_squad_code"] = False
        return

    # Назначение задания (только для родителей)
    if ctx.user_data.get("awaiting_assign_task_name"):
        if len(text) < 2:
            await update.message.reply_text("Название слишком короткое:")
            return
        ctx.user_data["temp_assign_task_name"] = text
        ctx.user_data["awaiting_assign_task_name"] = False
        ctx.user_data["awaiting_assign_attr"] = True
        kb = [[InlineKeyboardButton(f"{a['emoji']} {a['name']}", callback_data=f"assign_attr_{k}")] for k, a in ATTRS.items()]
        await update.message.reply_text("Какой атрибут?", reply_markup=InlineKeyboardMarkup(kb))
        return

# ========== ЗАДАНИЯ (с отображением слабости босса) ==========
async def show_tasks(query, uid):
    users = load_users()
    user = users.get(uid)
    if not user:
        await query.edit_message_text("Ошибка")
        return

    today = str(date.today())
    own_tasks = user.get("tasks", [])
    assigned_tasks = user.get("assigned_tasks", [])

    # Определяем слабость текущего босса (для отметки заданий)
    squad_id = user.get("squad_id")
    weak_attr = None
    if squad_id:
        boss, _ = get_or_create_boss(squad_id)
        if not boss.get("defeated", False):
            weak_attr = boss.get("weak_attr")

    kb = []

    # Свои задания
    for t in own_tasks:
        is_done = t.get("done_date") == today
        status = "✅" if is_done else "◻️"
        a = ATTRS.get(t["attr"], {"emoji": "📌"})
        bonus = " ⚡" if weak_attr and t["attr"] == weak_attr else ""
        kb.append([InlineKeyboardButton(f"{status} {t['name']} {a['emoji']}{bonus}", callback_data=f"done_{t['id']}")])

    # Задания от родителей
    if assigned_tasks:
        if own_tasks:
            kb.append([InlineKeyboardButton("── 👨‍👦 От родителей ──", callback_data="noop")])
        for t in assigned_tasks:
            is_done = t.get("done_date") == today
            status = "✅" if is_done else "◻️"
            a = ATTRS.get(t["attr"], {"emoji": "📌"})
            bonus = " ⚡" if weak_attr and t["attr"] == weak_attr else ""
            parent = t.get("assigned_by_name", "родитель")
            kb.append([InlineKeyboardButton(f"{status} {t['name']} {a['emoji']}{bonus} (от {parent})", callback_data=f"adone_{t['id']}")])

    if not own_tasks and not assigned_tasks:
        kb.append([InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")])

    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])

    own_done = len([t for t in own_tasks if t.get("done_date") == today])
    asgn_done = len([t for t in assigned_tasks if t.get("done_date") == today])

    text = f"📋 *Задания*\n\n✅ Свои: {own_done}/{len(own_tasks)}\n✅ От родителей: {asgn_done}/{len(assigned_tasks)}"
    if weak_attr:
        text += f"\n\n⚡ *Слабость босса:* {ATTRS[weak_attr]['emoji']} {ATTRS[weak_attr]['name']}"

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ========== ОТРЯД ==========
async def show_squad_menu(query, uid, squad_id):
    users = load_users()
    squads = load_squads()
    squad = squads.get(squad_id, {})
    user = users.get(uid)
    is_parent = (user.get("role") == "parent")
    today = str(date.today())
    members_text = ""
    kb = []

    for mid in squad.get("members", []):
        m = users.get(mid)
        if not m:
            continue
        role_emoji = ROLES[m.get("role", "child")]["emoji"]
        pending = len([t for t in m.get("assigned_tasks", []) if t.get("done_date") != today])
        members_text += f"{CLASSES[m['class']]['emoji']} *{m['name']}* {role_emoji} — Ур.{m['level']}"
        if pending:
            members_text += f" 📋{pending}"
        members_text += "\n"

        if mid != uid:
            kb.append([InlineKeyboardButton(f"👁 {m['name']}", callback_data=f"view_member_{mid}")])
            # Кнопка "Дать задание" только для родителей
            if is_parent:
                kb.append([InlineKeyboardButton(f"📝 Дать задание {m['name']}", callback_data=f"assign_to_{mid}")])

    # Показываем создателя отряда
    creator_id = squad.get("creator")
    if creator_id and creator_id in users:
        creator_name = users[creator_id]["name"]
        members_text += f"\n👑 *Создатель отряда:* {creator_name}\n"

    kb.append([InlineKeyboardButton("🔑 Код отряда", callback_data="show_code")])
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])

    await query.edit_message_text(
        f"🏰 *{squad['name']}*\n\n{members_text}\n\n"
        f"💡 *Создатель отряда может назначать роли:*\n"
        f"   • Родитель 👨‍👦 — может давать задания\n"
        f"   • Ребёнок 🧒 — получает задания\n\n"
        f"Код: `{squad_id}`",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

# ========== CALLBACKS ==========
async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    data = query.data
    users = load_users()
    user = users.get(uid)

    # Меню
    if data == "menu":
        await show_menu(query, uid, edit=True)
        return

    # Выбор класса
    if data.startswith("class_"):
        cls_key = data.replace("class_", "")
        name = ctx.user_data.get("temp_name", "Герой")
        users[uid] = new_user(name, cls_key, "child")
        pending = ctx.user_data.get("pending_squad")
        if pending:
            squads = load_squads()
            if pending in squads:
                users[uid]["squad_id"] = pending
                if uid not in squads[pending]["members"]:
                    squads[pending]["members"].append(uid)
                save_squads(squads)
            ctx.user_data["pending_squad"] = None
        save_users(users)
        kb = [
            [InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")],
            [InlineKeyboardButton("🔗 Вступить по коду", callback_data="join_squad")],
        ]
        await query.edit_message_text(
            f"{CLASSES[cls_key]['emoji']} *{name}* создан!\n\nТеперь создай или вступи в отряд:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    if not user:
        await query.edit_message_text("Сначала создай героя: /start")
        return

    # Профиль
    if data == "profile":
        kb = [[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
        await query.edit_message_text(char_card(user), reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    # Задания
    if data == "tasks":
        await show_tasks(query, uid)
        return

    # Добавить задание
    if data == "add_task":
        ctx.user_data["awaiting_task_name"] = True
        await query.edit_message_text("➕ Введи название задания:")
        return

    # Выбор атрибута для СВОЕГО задания
    if data.startswith("task_attr_"):
        attr_key = data.replace("task_attr_", "")
        task_name = ctx.user_data.get("temp_task_name", "Задание")
        task = {
            "id": str(uuid.uuid4())[:8],
            "name": task_name,
            "attr": attr_key,
            "xp_gain": 25,
            "attr_gain": 2,
            "done_date": ""
        }
        user.setdefault("tasks", []).append(task)
        save_users(users)
        ctx.user_data["temp_task_name"] = None
        ctx.user_data["awaiting_attr"] = False
        await query.edit_message_text(f"✅ Задание *{task_name}* добавлено!", parse_mode="Markdown")
        await show_tasks(query, uid)
        return

    # Выполнить СВОЁ задание (с уроном боссу)
    if data.startswith("done_"):
        task_id = data.replace("done_", "")
        today = str(date.today())
        task = next((t for t in user.get("tasks", []) if t["id"] == task_id), None)
        if not task or task.get("done_date") == today:
            await query.answer("Нельзя выполнить", show_alert=True)
            return
        task["done_date"] = today
        user["attrs"][task["attr"]] += task["attr_gain"]
        update_streak(user)
        leveled = add_xp(user, task["xp_gain"])
        boss_msg = await apply_boss_damage(uid, task["attr"], user, users, query)
        save_users(users)
        msg = f"✅ *{task['name']}*\n+{task['xp_gain']} опыта{boss_msg}"
        if leveled:
            msg += f"\n\n🎉 *Уровень {user['level']}!*"
        await query.edit_message_text(msg, parse_mode="Markdown")
        await show_tasks(query, uid)
        return

    # Выполнить ЗАДАНИЕ ОТ РОДИТЕЛЯ (с уроном боссу)
    if data.startswith("adone_"):
        task_id = data.replace("adone_", "")
        today = str(date.today())
        task = next((t for t in user.get("assigned_tasks", []) if t["id"] == task_id), None)
        if not task or task.get("done_date") == today:
            await query.answer("Нельзя выполнить", show_alert=True)
            return
        task["done_date"] = today
        user["attrs"][task["attr"]] += task.get("attr_gain", 2)
        update_streak(user)
        leveled = add_xp(user, task.get("xp_gain", 30))
        boss_msg = await apply_boss_damage(uid, task["attr"], user, users, query)
        save_users(users)
        if task.get("assigned_by"):
            try:
                await query.get_bot().send_message(
                    chat_id=int(task["assigned_by"]),
                    text=f"👨‍👦 *{user['name']}* выполнил задание!\n✅ {task['name']}",
                    parse_mode="Markdown"
                )
            except:
                pass
        msg = f"✅ *{task['name']}* (от {task.get('assigned_by_name', 'родителя')})\n+{task.get('xp_gain', 30)} опыта{boss_msg}"
        if leveled:
            msg += f"\n\n🎉 *Уровень {user['level']}!*"
        await query.edit_message_text(msg, parse_mode="Markdown")
        await show_tasks(query, uid)
        return

    # Отряд
    if data == "squad":
        squad_id = user.get("squad_id")
        squads = load_squads()
        if not squad_id or squad_id not in squads:
            kb = [
                [InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")],
                [InlineKeyboardButton("🔗 Вступить по коду", callback_data="join_squad")],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu")],
            ]
            await query.edit_message_text("У тебя нет отряда.", reply_markup=InlineKeyboardMarkup(kb))
            return
        await show_squad_menu(query, uid, squad_id)
        return

    if data == "create_squad":
        ctx.user_data["step"] = "squad_name"
        await query.edit_message_text("🏰 Введи название отряда:")
        return

    if data == "join_squad":
        ctx.user_data["awaiting_squad_code"] = True
        await query.edit_message_text("🔗 Введи код отряда (6 символов):")
        return

    # НАЗНАЧИТЬ ЗАДАНИЕ (только для родителей)
    if data.startswith("assign_to_"):
        if user.get("role") != "parent":
            await query.answer("Только родители могут давать задания!", show_alert=True)
            return
        target_uid = data.replace("assign_to_", "")
        target_user = users.get(target_uid)
        if not target_user:
            await query.answer("Участник не найден", show_alert=True)
            return
        if target_uid == uid:
            await query.answer("Нельзя дать задание себе!", show_alert=True)
            return
        ctx.user_data["assign_target_uid"] = target_uid
        ctx.user_data["awaiting_assign_task_name"] = True
        await query.edit_message_text(f"📝 Задание для *{target_user['name']}*\n\nВведи название:", parse_mode="Markdown")
        return

    # Выбор атрибута для назначенного задания
    if data.startswith("assign_attr_"):
        attr_key = data.replace("assign_attr_", "")
        target_uid = ctx.user_data.get("assign_target_uid")
        task_name = ctx.user_data.get("temp_assign_task_name", "Задание")
        if not target_uid or target_uid not in users:
            await query.edit_message_text("Ошибка")
            return
        target_user = users[target_uid]
        task = {
            "id": str(uuid.uuid4())[:8],
            "name": task_name,
            "attr": attr_key,
            "xp_gain": 30,
            "attr_gain": 2,
            "done_date": "",
            "assigned_by": uid,
            "assigned_by_name": user["name"],
        }
        target_user.setdefault("assigned_tasks", []).append(task)
        save_users(users)
        ctx.user_data["temp_assign_task_name"] = None
        ctx.user_data["assign_target_uid"] = None
        ctx.user_data["awaiting_assign_attr"] = False
        try:
            await query.get_bot().send_message(
                chat_id=int(target_uid),
                text=f"👨‍👦 *{user['name']}* дал задание!\n\n📋 *{task_name}*\nВыполни в /menu → Задания",
                parse_mode="Markdown"
            )
        except:
            pass
        await query.edit_message_text(f"✅ Задание *{task_name}* дано {target_user['name']}!")
        return

    # НАЗНАЧИТЬ РОЛЬ (только для создателя отряда)
    if data.startswith("set_role_parent_"):
        target_uid = data.replace("set_role_parent_", "")
        await set_user_role(query, uid, target_uid, "parent")
        return

    if data.startswith("set_role_child_"):
        target_uid = data.replace("set_role_child_", "")
        await set_user_role(query, uid, target_uid, "child")
        return

    # Просмотр участника
    if data.startswith("view_member_"):
        target_uid = data.replace("view_member_", "")
        target_user = users.get(target_uid)
        if not target_user:
            await query.answer("Участник не найден", show_alert=True)
            return
        today = str(date.today())
        assigned = target_user.get("assigned_tasks", [])
        asgn_done = len([t for t in assigned if t.get("done_date") == today])
        task_lines = ""
        for t in assigned:
            status = "✅" if t.get("done_date") == today else "◻️"
            a = ATTRS.get(t["attr"], {"emoji": "📌"})
            task_lines += f"{status} {t['name']} {a['emoji']}\n"
        kb = []
        if user.get("role") == "parent":
            kb.append([InlineKeyboardButton(f"📝 Дать задание {target_user['name']}", callback_data=f"assign_to_{target_uid}")])
        squad_id = user.get("squad_id")
        squads = load_squads()
        if squad_id and squads.get(squad_id, {}).get("creator") == uid and target_uid != uid:
            current_role = target_user.get("role", "child")
            kb.append([InlineKeyboardButton("── Назначить роль ──", callback_data="noop")])
            if current_role != "parent":
                kb.append([InlineKeyboardButton("👨‍👦 Сделать Родителем", callback_data=f"set_role_parent_{target_uid}")])
            if current_role != "child":
                kb.append([InlineKeyboardButton("🧒 Сделать Ребёнком", callback_data=f"set_role_child_{target_uid}")])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="squad")])
        role_emoji = ROLES[target_user.get("role", "child")]["emoji"]
        await query.edit_message_text(
            f"{CLASSES[target_user['class']]['emoji']} *{target_user['name']}* {role_emoji} — Ур.{target_user['level']}\n\n"
            f"*Задания от родителей:*\n{task_lines if task_lines else 'Нет'}\n\n"
            f"✅ Выполнено сегодня: {asgn_done}/{len(assigned)}",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    # БОСС РЕЙД
    if data == "boss":
        squad_id = user.get("squad_id")
        if not squad_id:
            kb = [[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
            await query.edit_message_text("⚔️ Для рейда нужен отряд.", reply_markup=InlineKeyboardMarkup(kb))
            return
        boss, _ = get_or_create_boss(squad_id)
        squads = load_squads()
        squad = squads.get(squad_id, {})
        if boss["defeated"]:
            kb = [[InlineKeyboardButton("🔄 Следующий босс", callback_data="boss_next")], [InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
            await query.edit_message_text(
                f"🏆 *Босс повержён!*\n\nНаграда: {boss['reward']}\n{boss['reward_desc']}\n\nГотов к следующему?",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown"
            )
            return
        card = boss_card(boss, squad_id, users, squad.get("members", []))
        kb = [[InlineKeyboardButton("📋 Выполнить задание", callback_data="tasks")], [InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
        await query.edit_message_text(f"⚔️ *Рейд отряда*\n\n{card}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    if data == "boss_next":
        squad_id = user.get("squad_id")
        if squad_id:
            bosses = load_bosses()
            if squad_id in bosses:
                del bosses[squad_id]
                save_bosses(bosses)
            # Создаём нового босса при следующем заходе в рейд
            await query.edit_message_text("🔄 Новый босс появится после обновления страницы. Нажмите «Босс рейд» снова.")
        return

    if data == "show_code":
        squad_id = user.get("squad_id")
        if squad_id:
            await query.edit_message_text(f"🔑 Код вашего отряда: `{squad_id}`", parse_mode="Markdown")
        else:
            await query.edit_message_text("У вас нет отряда.")
        return

async def set_user_role(query, caller_uid, target_uid, new_role):
    users = load_users()
    caller = users.get(caller_uid)
    target = users.get(target_uid)
    if not caller or not target:
        await query.answer("Ошибка", show_alert=True)
        return
    squad_id = caller.get("squad_id")
    squads = load_squads()
    if not squad_id or squads.get(squad_id, {}).get("creator") != caller_uid:
        await query.answer("Только создатель отряда может назначать роли!", show_alert=True)
        return
    target["role"] = new_role
    save_users(users)
    role_emoji = ROLES[new_role]["emoji"]
    await query.edit_message_text(
        f"✅ *{target['name']}* теперь {ROLES[new_role]['name']} {role_emoji}!",
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
