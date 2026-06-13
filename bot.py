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

def xp_needed(lvl):
    if lvl < len(XP_TABLE):
        return XP_TABLE[lvl]
    return XP_TABLE[-1] + (lvl - len(XP_TABLE) + 1) * 600

# ========== ДАННЫЕ ==========

def load_users():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

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

def new_user(name, cls_key):
    return {
        "name": name,
        "class": cls_key,
        "level": 1,
        "xp": 0,
        "attrs": {"str": 0, "int": 0, "hp": 0, "agi": 0, "wil": 0},
        "streak": 0,
        "last_done_date": "",
        "tasks": [],
        "gear": [],
        "squad_id": None,
    }

def update_streak(user):
    """Обновляет стрик: +1 если вчера было выполнение, сбрасывает если пропуск"""
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))
    last = user.get("last_done_date", "")
    if last == today:
        pass  # уже обновляли сегодня
    elif last == yesterday:
        user["streak"] = user.get("streak", 0) + 1
    elif last != today:
        if last:  # не первый день
            user["streak"] = 1
        else:
            user["streak"] = 1
    user["last_done_date"] = today

def add_xp(user, amount):
    """Добавляет опыт, возвращает True если был level up"""
    cls_bonus = CLASSES[user["class"]]["bonus_attr"]
    # Бонус 20% к атрибуту класса при получении опыта
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
    """Сбрасывает выполнение заданий для нового дня"""
    today = str(date.today())
    for t in user.get("tasks", []):
        if t.get("done_date") != today:
            t["done"] = False

# ========== ОТОБРАЖЕНИЕ ==========

def char_card(user):
    cls = CLASSES[user["class"]]
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

    return (
        f"{cls['emoji']} *{user['name']}* — {cls['name']}\n"
        f"⭐ Уровень {lvl}   🔥 Стрик {user.get('streak', 0)} дн.\n"
        f"Опыт: {xp} / {xp_max}\n"
        f"`{bar}`\n\n"
        f"*Атрибуты:*\n`{attrs_lines}`\n"
        f"*Снаряжение:*\n{gear_text}\n\n"
        f"✅ Сегодня: {done_today} / {total} заданий"
    )

# ========== МЕНЮ ==========

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

    cls = CLASSES[user["class"]]
    today = str(date.today())
    done_today = len([t for t in user.get("tasks", []) if t.get("done_date") == today])
    total = len(user.get("tasks", []))

    kb = [
        [InlineKeyboardButton("👤 Мой герой", callback_data="profile"),
         InlineKeyboardButton("📋 Задания", callback_data="tasks")],
        [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task"),
         InlineKeyboardButton("🏰 Отряд", callback_data="squad")],
    ]
    text = (
        f"{cls['emoji']} *{user['name']}* · Ур. {user['level']} · 🔥 {user.get('streak',0)}\n"
        f"✅ Сегодня: {done_today}/{total} заданий"
    )
    markup = InlineKeyboardMarkup(kb)
    if edit:
        await target.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await target.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")

# ========== КОМАНДЫ ==========

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    args = ctx.args

    # Вступление в отряд по ссылке
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
            squad_name = squads[squad_id]["name"]
            await update.message.reply_text(
                f"⚔️ Ты вступил в отряд *{squad_name}*!",
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

    ctx.user_data["step"] = "name"
    await update.message.reply_text(
        "⚔️ *Добро пожаловать в Vysotix!*\n\n"
        "Здесь привычки прокачивают твоего героя.\n\n"
        "Как зовут твоего героя?",
        parse_mode="Markdown"
    )

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_users()
    if uid in users:
        reset_daily_tasks(users[uid])
        save_users(users)
    await show_menu(update, uid)

# ========== ТЕКСТОВЫЕ СООБЩЕНИЯ ==========

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    step = ctx.user_data.get("step")

    # --- Имя героя ---
    if step == "name":
        if len(text) < 2 or len(text) > 20:
            await update.message.reply_text("Имя должно быть от 2 до 20 символов:")
            return
        ctx.user_data["temp_name"] = text
        ctx.user_data["step"] = "class"
        kb = [[InlineKeyboardButton(f"{v['emoji']} {v['name']}", callback_data=f"class_{k}")]
              for k, v in CLASSES.items()]
        await update.message.reply_text(
            f"Отлично, *{text}*! Выбери класс героя:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    # --- Название отряда ---
    if step == "squad_name":
        if len(text) < 2:
            await update.message.reply_text("Название слишком короткое:")
            return
        squad_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        squads = load_squads()
        squads[squad_id] = {"name": text, "members": [uid], "created": str(date.today())}
        save_squads(squads)

        users = load_users()
        if uid in users:
            users[uid]["squad_id"] = squad_id
            save_users(users)

        bot_me = await ctx.bot.get_me()
        link = f"https://t.me/{bot_me.username}?start=squad_{squad_id}"
        ctx.user_data["step"] = None

        await update.message.reply_text(
            f"🏰 *Отряд «{text}» создан!*\n\n"
            f"Код: `{squad_id}`\n\n"
            f"🔗 Ссылка для сына:\n{link}\n\n"
            f"Отправь ему эту ссылку — он сразу попадёт в ваш отряд.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎮 В меню", callback_data="menu")]]),
            parse_mode="Markdown"
        )
        return

    # --- Название нового задания ---
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

# ========== CALLBACK КНОПКИ ==========

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    data = query.data

    users = load_users()
    user = users.get(uid)

    # --- Меню ---
    if data == "menu":
        if uid in users:
            reset_daily_tasks(users[uid])
            save_users(users)
        await show_menu(query, uid, edit=True)
        return

    # --- Выбор класса ---
    if data.startswith("class_"):
        cls_key = data.replace("class_", "")
        name = ctx.user_data.get("temp_name", "Герой")
        users[uid] = new_user(name, cls_key)

        # Если ждёт вступление в отряд
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
        cls = CLASSES[cls_key]
        ctx.user_data["step"] = "squad_name"
        await query.edit_message_text(
            f"{cls['emoji']} Герой *{name}* ({cls['name']}) создан!\n\n"
            f"Теперь создай семейный отряд.\n\nКак назовёшь отряд?",
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

    # --- Добавить задание ---
    if data == "add_task":
        ctx.user_data["awaiting_task_name"] = True
        await query.edit_message_text(
            "➕ *Новое задание*\n\nВведи название задания:",
            parse_mode="Markdown"
        )
        return

    # --- Выбор атрибута задания ---
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
        if "tasks" not in user:
            user["tasks"] = []
        user["tasks"].append(task)
        save_users(users)
        ctx.user_data["temp_task_name"] = None
        await show_tasks_menu(query, uid)
        return

    # --- Выполнить задание ---
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
        attr_gain = task["attr_gain"]
        user["attrs"][attr_key] = user["attrs"].get(attr_key, 0) + attr_gain
        update_streak(user)
        leveled = add_xp(user, xp)
        save_users(users)

        attr = ATTRS[attr_key]
        msg = f"✅ *{task['name']}*\n\n{attr['emoji']} {attr['name']} +{attr_gain} · ⭐ +{xp} опыта\n🔥 Стрик: {user['streak']} дн."
        if leveled:
            gear = GEAR_UNLOCKS.get(user["level"], "")
            msg += f"\n\n🎉 *Уровень {user['level']}!*"
            if gear:
                msg += f"\nПолучено: {gear}"

        kb = [[InlineKeyboardButton("◀️ К заданиям", callback_data="tasks")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    # --- Удалить задание ---
    if data.startswith("del_"):
        task_id = data.replace("del_", "")
        user["tasks"] = [t for t in user.get("tasks", []) if t["id"] != task_id]
        save_users(users)
        await show_tasks_menu(query, uid)
        return

    # --- Отряд ---
    if data == "squad":
        squad_id = user.get("squad_id")
        squads = load_squads()

        if not squad_id or squad_id not in squads:
            kb = [
                [InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu")],
            ]
            await query.edit_message_text(
                "🏰 У тебя пока нет отряда.\n\nСоздай свой!",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return

        squad = squads[squad_id]
        today = str(date.today())
        members_text = ""
        for mid in squad.get("members", []):
            m = users.get(mid)
            if not m:
                continue
            cls = CLASSES[m["class"]]
            done_today = len([t for t in m.get("tasks", []) if t.get("done_date") == today])
            total = len(m.get("tasks", []))
            members_text += f"{cls['emoji']} *{m['name']}* — Ур.{m['level']} · ✅{done_today}/{total}\n"

        bot_me = await ctx.bot.get_me()
        link = f"https://t.me/{bot_me.username}?start=squad_{squad_id}"

        kb = [[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
        await query.edit_message_text(
            f"🏰 *{squad['name']}*\n\n{members_text}\n🔗 Ссылка:\n`{link}`",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

    # --- Создать отряд ---
    if data == "create_squad":
        ctx.user_data["step"] = "squad_name"
        await query.edit_message_text(
            "🏰 Придумай название отряда и напиши его:",
        )
        return

async def show_tasks_menu(query, uid):
    users = load_users()
    user = users.get(uid)
    today = str(date.today())
    tasks = user.get("tasks", [])

    if not tasks:
        kb = [
            [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu")],
        ]
        await query.edit_message_text(
            "📋 Пока нет заданий. Добавь первое!",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    kb = []
    for t in tasks:
        is_done = t.get("done_date") == today
        a = ATTRS[t["attr"]]
        status = "✅" if is_done else "◻️"
        kb.append([InlineKeyboardButton(
            f"{status} {t['name']} {a['emoji']}",
            callback_data=f"done_{t['id']}"
        )])

    kb.append([InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")])
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])

    done_today = len([t for t in tasks if t.get("done_date") == today])
    await query.edit_message_text(
        f"📋 *Задания* — выполнено {done_today}/{len(tasks)}",
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
