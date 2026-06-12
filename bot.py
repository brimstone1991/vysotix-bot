import os
import json
import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from flask import Flask
from threading import Thread

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
DATA_FILE = "data/users.json"

# Состояния
CHOOSING_NAME, CHOOSING_CLASS, CREATING_SQUAD, JOINING_SQUAD = range(4)
ADDING_TASK_NAME, ADDING_TASK_ATTR = range(10, 12)

CLASSES = {
    "warrior": {"name": "Воин", "emoji": "⚔️", "color": "purple", "bonus": "Сила"},
    "archer":  {"name": "Лучник", "emoji": "🏹", "color": "amber",  "bonus": "Ловкость"},
    "mage":    {"name": "Маг",   "emoji": "🔮", "color": "blue",   "bonus": "Интеллект"},
    "rogue":   {"name": "Разбойник", "emoji": "🗡️", "color": "green", "bonus": "Воля"},
}

ATTRS = {
    "str": {"name": "Сила",       "emoji": "💪", "hint": "тренировки, спорт"},
    "int": {"name": "Интеллект",  "emoji": "📚", "hint": "чтение, учёба"},
    "hp":  {"name": "Здоровье",   "emoji": "❤️", "hint": "сон, питание, режим"},
    "agi": {"name": "Ловкость",   "emoji": "🤸", "hint": "растяжка, координация"},
    "wil": {"name": "Воля",       "emoji": "🔥", "hint": "сложные и дискомфортные задачи"},
}

XP_PER_LEVEL = [0, 100, 200, 350, 500, 700, 950, 1250, 1600, 2000]

GEAR_BY_LEVEL = {
    1: [],
    2: ["Начальное оружие"],
    3: ["Щит / колчан"],
    4: ["Доспех"],
    5: ["Плащ"],
    7: ["Кольцо силы"],
    10: ["Легендарный облик"],
}

# ========== РАБОТА С ДАННЫМИ ==========
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "squads": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(data, uid):
    return data["users"].get(str(uid))

def new_user(name, cls_key):
    return {
        "name": name,
        "class": cls_key,
        "level": 1,
        "xp": 0,
        "attrs": {"str": 0, "int": 0, "hp": 0, "agi": 0, "wil": 0},
        "streak": 0,
        "last_active": str(date.today()),
        "tasks_done": 0,
        "squad_id": None,
        "tasks": [],
        "gear": [],
    }

def xp_for_level(lvl):
    if lvl - 1 < len(XP_PER_LEVEL):
        return XP_PER_LEVEL[lvl - 1]
    return XP_PER_LEVEL[-1] + (lvl - len(XP_PER_LEVEL)) * 500

def add_xp(user, amount):
    user["xp"] += amount
    leveled = False
    while user["xp"] >= xp_for_level(user["level"] + 1):
        user["xp"] -= xp_for_level(user["level"] + 1)
        user["level"] += 1
        leveled = True
        new_gear = GEAR_BY_LEVEL.get(user["level"], [])
        user["gear"].extend(new_gear)
    return leveled

def char_card(user):
    cls = CLASSES[user["class"]]
    lvl = user["level"]
    xp = user["xp"]
    xp_need = xp_for_level(lvl + 1)
    bar_filled = int((xp / xp_need) * 10) if xp_need > 0 else 0
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    attrs_lines = ""
    for key, a in ATTRS.items():
        val = user["attrs"][key]
        mini = "▰" * min(val // 5, 10) + "▱" * max(0, 10 - val // 5)
        attrs_lines += f"{a['emoji']} {a['name']:12} {val:3}  {mini}\n"

    gear = "\n".join(f"  ✦ {g}" for g in user["gear"]) if user["gear"] else "  пусто"

    return (
        f"{cls['emoji']} *{user['name']}* — {cls['name']}\n"
        f"⭐ Уровень {lvl}  |  🔥 Стрик {user['streak']} дн.\n"
        f"Опыт: {xp}/{xp_need}\n"
        f"`{bar}`\n\n"
        f"*Атрибуты:*\n"
        f"`{attrs_lines}`\n"
        f"*Снаряжение:*\n{gear}\n\n"
        f"📋 Выполнено заданий: {user['tasks_done']}"
    )

# ========== ОБРАБОТЧИКИ ==========
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = str(update.effective_user.id)
    user = get_user(data, uid)

    if user:
        await update.message.reply_text(f"С возвращением, {user['name']}! Используй /menu", parse_mode="Markdown")
        return ConversationHandler.END

    await update.message.reply_text(
        "⚔️ *Добро пожаловать в Vysotix!*\n\nСемейная RPG где привычки прокачивают твоего героя.\n\nКак зовут твоего героя?",
        parse_mode="Markdown"
    )
    return CHOOSING_NAME

async def got_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2 or len(name) > 20:
        await update.message.reply_text("Имя должно быть от 2 до 20 символов. Попробуй ещё раз:")
        return CHOOSING_NAME
    ctx.user_data["hero_name"] = name

    kb = [[InlineKeyboardButton(f"{v['emoji']} {v['name']}", callback_data=f"class_{k}") for k, v in CLASSES.items()]]
    await update.message.reply_text(f"Отлично, *{name}*! Выбери класс героя:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return CHOOSING_CLASS

async def got_class(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cls_key = query.data.replace("class_", "")
    cls = CLASSES[cls_key]
    name = ctx.user_data["hero_name"]

    data = load_data()
    uid = str(query.from_user.id)
    data["users"][uid] = new_user(name, cls_key)
    save_data(data)

    kb = [[
        InlineKeyboardButton("🏰 Создать отряд", callback_data="squad_create"),
        InlineKeyboardButton("🔗 Вступить в отряд", callback_data="squad_join"),
    ]]
    await query.edit_message_text(
        f"{cls['emoji']} Герой *{name}* ({cls['name']}) создан!\n\nБонусный атрибут класса: {cls['bonus']}\n\nТеперь создай семейный отряд или вступи в существующий:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )
    return CHOOSING_CLASS

async def squad_create(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏰 Введи название отряда (например: *Семья Подвысоцких*):", parse_mode="Markdown")
    return CREATING_SQUAD

async def got_squad_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    squad_name = update.message.text.strip()
    data = load_data()
    uid = str(update.effective_user.id)

    import random, string
    squad_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    data["squads"][squad_id] = {
        "name": squad_name,
        "members": [uid],
        "created": str(date.today()),
    }
    data["users"][uid]["squad_id"] = squad_id
    save_data(data)

    bot_username = (await update.get_bot().get_me()).username
    invite_link = f"https://t.me/{bot_username}?start=join_{squad_id}"

    await update.message.reply_text(
        f"🏰 Отряд *{squad_name}* создан!\n\nКод отряда: `{squad_id}`\n\nОтправь ссылку чтобы вступить:\n{invite_link}\n\nИспользуй /menu для управления.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def squad_join_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔗 Введи код отряда (6 символов):")
    return JOINING_SQUAD

async def got_squad_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    data = load_data()
    uid = str(update.effective_user.id)

    if code not in data["squads"]:
        await update.message.reply_text("Отряд не найден. Проверь код и попробуй ещё раз:")
        return JOINING_SQUAD

    squad = data["squads"][code]
    if uid not in squad["members"]:
        squad["members"].append(uid)
    data["users"][uid]["squad_id"] = code
    save_data(data)

    await update.message.reply_text(f"⚔️ Ты вступил в отряд *{squad['name']}*!\n\nИспользуй /menu для управления.", parse_mode="Markdown")
    return ConversationHandler.END

async def handle_start_with_args(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if args and args[0].startswith("join_"):
        squad_id = args[0].replace("join_", "")
        data = load_data()
        uid = str(update.effective_user.id)
        user = get_user(data, uid)
        if not user:
            ctx.user_data["pending_squad"] = squad_id
            await update.message.reply_text("⚔️ Тебя приглашают в семейный отряд!\n\nСначала создай героя. Как его зовут?")
            return CHOOSING_NAME
        if squad_id in data["squads"]:
            squad = data["squads"][squad_id]
            if uid not in squad["members"]:
                squad["members"].append(uid)
            user["squad_id"] = squad_id
            save_data(data)
            await update.message.reply_text(f"⚔️ Ты вступил в отряд *{squad['name']}*!", parse_mode="Markdown")
        return ConversationHandler.END
    return await start(update, ctx)

async def menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = str(update.effective_user.id)
    user = get_user(data, uid)
    if not user:
        await update.message.reply_text("Сначала зарегистрируйся: /start")
        return

    kb = [
        [InlineKeyboardButton("👤 Мой герой", callback_data="show_char"), InlineKeyboardButton("📋 Задания", callback_data="show_tasks")],
        [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task"), InlineKeyboardButton("🏰 Отряд", callback_data="show_squad")],
    ]
    cls = CLASSES[user["class"]]
    await update.message.reply_text(f"{cls['emoji']} *{user['name']}* · Ур.{user['level']} · 🔥{user['streak']}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_char(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    uid = str(query.from_user.id)
    user = get_user(data, uid)
    if not user:
        await query.edit_message_text("Сначала зарегистрируйся: /start")
        return
    kb = [[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]]
    await query.edit_message_text(char_card(user), reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    uid = str(query.from_user.id)
    user = get_user(data, uid)
    today = str(date.today())
    tasks = user.get("tasks", [])
    done_today = [t for t in tasks if t.get("done_date") == today]

    if not tasks:
        kb = [[InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")], [InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]]
        await query.edit_message_text("📋 У тебя пока нет заданий.\n\nДобавь первое задание!", reply_markup=InlineKeyboardMarkup(kb))
        return

    kb = []
    for t in tasks:
        is_done = t.get("done_date") == today
        attr = ATTRS[t["attr"]]
        label = f"{'✅' if is_done else '◻️'} {t['name']} · {attr['emoji']}+{t['xp_gain']}"
        kb.append([InlineKeyboardButton(label, callback_data=f"do_task_{t['id']}")])

    kb.append([InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")])
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="back_menu")])

    await query.edit_message_text(f"📋 *Задания на сегодня*\n\nВыполнено: {len(done_today)}/{len(tasks)}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def do_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = query.data.replace("do_task_", "")
    data = load_data()
    uid = str(query.from_user.id)
    user = get_user(data, uid)
    today = str(date.today())

    task = next((t for t in user["tasks"] if t["id"] == task_id), None)
    if not task or task.get("done_date") == today:
        await query.answer("Нельзя выполнить задание", show_alert=True)
        return

    task["done_date"] = today
    user["attrs"][task["attr"]] += task["attr_gain"]
    user["tasks_done"] += 1

    last = user.get("last_active", "")
    yesterday = str(date.today() - timedelta(days=1))
    if last == yesterday:
        user["streak"] += 1
    elif last != today:
        user["streak"] = 1
    user["last_active"] = today

    leveled = add_xp(user, task["xp_gain"])
    save_data(data)

    attr = ATTRS[task["attr"]]
    msg = f"✅ *{task['name']}*\n\n+{task['xp_gain']} опыта · {attr['emoji']} {attr['name']} +{task['attr_gain']}"
    if leveled:
        msg += f"\n\n🎉 *Уровень повышен! Ур. {user['level']}*"

    kb = [[InlineKeyboardButton("◀️ К заданиям", callback_data="show_tasks")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def add_task_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("➕ *Новое задание*\n\nВведи название задания:", parse_mode="Markdown")
    return ADDING_TASK_NAME

async def got_task_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new_task_name"] = update.message.text.strip()
    kb = [[InlineKeyboardButton(f"{a['emoji']} {a['name']}", callback_data=f"tattr_{k}")] for k, a in ATTRS.items()]
    await update.message.reply_text("Какой атрибут качает это задание?", reply_markup=InlineKeyboardMarkup(kb))
    return ADDING_TASK_ATTR

async def got_task_attr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    attr_key = query.data.replace("tattr_", "")
    name = ctx.user_data.get("new_task_name", "Задание")

    data = load_data()
    uid = str(query.from_user.id)
    user = get_user(data, uid)

    import uuid
    task = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "attr": attr_key,
        "xp_gain": 25,
        "attr_gain": 2,
        "done_date": None,
    }
    user["tasks"].append(task)
    save_data(data)

    attr = ATTRS[attr_key]
    kb = [[InlineKeyboardButton("📋 К заданиям", callback_data="show_tasks")]]
    await query.edit_message_text(f"✅ Задание добавлено!\n\n*{name}*\n{attr['emoji']} {attr['name']} +2 · +25 опыта", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return ConversationHandler.END

async def show_squad(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    uid = str(query.from_user.id)
    user = get_user(data, uid)

    squad_id = user.get("squad_id")
    if not squad_id or squad_id not in data["squads"]:
        kb = [[InlineKeyboardButton("🏰 Создать отряд", callback_data="squad_create"), InlineKeyboardButton("🔗 Вступить", callback_data="squad_join")], [InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]]
        await query.edit_message_text("У тебя пока нет отряда.", reply_markup=InlineKeyboardMarkup(kb))
        return

    squad = data["squads"][squad_id]
    members_text = ""
    today = str(date.today())
    for mid in squad["members"]:
        m = data["users"].get(mid)
        if m:
            cls = CLASSES[m["class"]]
            done = len([t for t in m.get("tasks", []) if t.get("done_date") == today])
            total = len(m.get("tasks", []))
            members_text += f"{cls['emoji']} *{m['name']}* — Ур.{m['level']} · ✅{done}/{total} сегодня\n"

    bot_username = (await query.get_bot().get_me()).username
    invite = f"https://t.me/{bot_username}?start=join_{squad_id}"
    kb = [[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]]
    await query.edit_message_text(f"🏰 *{squad['name']}*\n\n{members_text}\n🔗 Ссылка для приглашения:\n`{invite}`", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def back_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    uid = str(query.from_user.id)
    user = get_user(data, uid)
    cls = CLASSES[user["class"]]
    kb = [
        [InlineKeyboardButton("👤 Мой герой", callback_data="show_char"), InlineKeyboardButton("📋 Задания", callback_data="show_tasks")],
        [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task"), InlineKeyboardButton("🏰 Отряд", callback_data="show_squad")],
    ]
    await query.edit_message_text(f"{cls['emoji']} *{user['name']}* · Ур.{user['level']} · 🔥{user['streak']}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ========== ВЕБ-СЕРВЕР ==========
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "🤖 Vysotix Bot is running on Railway!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080, debug=False)

def keep_alive():
    Thread(target=run_flask).start()

# ========== ЗАПУСК ==========
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", handle_start_with_args)],
        states={
            CHOOSING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            CHOOSING_CLASS: [
                CallbackQueryHandler(got_class, pattern="^class_"),
                CallbackQueryHandler(squad_create, pattern="^squad_create$"),
                CallbackQueryHandler(squad_join_prompt, pattern="^squad_join$"),
            ],
            CREATING_SQUAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_squad_name)],
            JOINING_SQUAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_squad_code)],
        },
        fallbacks=[CommandHandler("start", handle_start_with_args)],
    )

    add_task_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_task_start, pattern="^add_task$")],
        states={
            ADDING_TASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_task_name)],
            ADDING_TASK_ATTR: [CallbackQueryHandler(got_task_attr, pattern="^tattr_")],
        },
        fallbacks=[],
    )

    app.add_handler(conv)
    app.add_handler(add_task_conv)
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(show_char, pattern="^show_char$"))
    app.add_handler(CallbackQueryHandler(show_tasks, pattern="^show_tasks$"))
    app.add_handler(CallbackQueryHandler(do_task, pattern="^do_task_"))
    app.add_handler(CallbackQueryHandler(show_squad, pattern="^show_squad$"))
    app.add_handler(CallbackQueryHandler(back_menu, pattern="^back_menu$"))
    app.add_handler(CallbackQueryHandler(squad_create, pattern="^squad_create$"))
    app.add_handler(CallbackQueryHandler(squad_join_prompt, pattern="^squad_join$"))

    print("✅ Vysotix Bot started on Railway!")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
