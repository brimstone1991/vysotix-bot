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
CHOOSING_NAME, CHOOSING_CLASS, CREATING_SQUAD, JOINING_SQUAD, AFTER_SQUAD = range(5)
ADDING_TASK_NAME, ADDING_TASK_ATTR = range(10, 12)

CLASSES = {
    "warrior": {"name": "Воин", "emoji": "⚔️", "bonus": "Сила"},
    "archer":  {"name": "Лучник", "emoji": "🏹", "bonus": "Ловкость"},
    "mage":    {"name": "Маг",   "emoji": "🔮", "bonus": "Интеллект"},
    "rogue":   {"name": "Разбойник", "emoji": "🗡️", "bonus": "Воля"},
}

ATTRS = {
    "str": {"name": "Сила", "emoji": "💪"},
    "int": {"name": "Интеллект", "emoji": "📚"},
    "hp":  {"name": "Здоровье", "emoji": "❤️"},
    "agi": {"name": "Ловкость", "emoji": "🤸"},
    "wil": {"name": "Воля", "emoji": "🔥"},
}

XP_PER_LEVEL = [0, 100, 200, 350, 500, 700, 950, 1250, 1600, 2000]
GEAR_BY_LEVEL = {2: ["Начальное оружие"], 3: ["Щит"], 4: ["Доспех"], 5: ["Плащ"], 7: ["Кольцо"], 10: ["Легендарный облик"]}

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
        "name": name, "class": cls_key, "level": 1, "xp": 0,
        "attrs": {"str": 0, "int": 0, "hp": 0, "agi": 0, "wil": 0},
        "streak": 0, "last_active": str(date.today()), "tasks_done": 0,
        "squad_id": None, "tasks": [], "gear": []
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
        if user["level"] in GEAR_BY_LEVEL:
            user["gear"].extend(GEAR_BY_LEVEL[user["level"]])
    return leveled

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    data = load_data()
    user = get_user(data, uid)
    
    if user:
        await update.message.reply_text(f"С возвращением, {user['name']}! Используй /menu")
        return ConversationHandler.END
    
    await update.message.reply_text("⚔️ *Добро пожаловать в Vysotix!*\n\nКак зовут твоего героя?", parse_mode="Markdown")
    return CHOOSING_NAME

async def got_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("Имя слишком короткое. Попробуй ещё раз:")
        return CHOOSING_NAME
    
    ctx.user_data["hero_name"] = name
    kb = [[InlineKeyboardButton(f"{v['emoji']} {v['name']}", callback_data=f"class_{k}") for k, v in CLASSES.items()]]
    await update.message.reply_text(f"Отлично, *{name}*! Выбери класс:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return CHOOSING_CLASS

async def got_class(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cls_key = query.data.replace("class_", "")
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
        f"✅ Герой *{name}* создан!\n\nТеперь создай или вступи в отряд:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )
    return AFTER_SQUAD

async def squad_create(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏰 Введи название отряда:")
    return CREATING_SQUAD

async def got_squad_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    squad_name = update.message.text.strip()
    uid = str(update.effective_user.id)
    data = load_data()
    
    import random, string
    squad_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    data["squads"][squad_id] = {"name": squad_name, "members": [uid], "created": str(date.today())}
    data["users"][uid]["squad_id"] = squad_id
    save_data(data)
    
    bot_username = (await update.get_bot().get_me()).username
    await update.message.reply_text(
        f"🏰 Отряд *{squad_name}* создан!\n\nКод: `{squad_id}`\nСсылка: https://t.me/{bot_username}?start=join_{squad_id}\n\nИспользуй /menu",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def squad_join_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔗 Введи код отряда:")
    return JOINING_SQUAD

async def got_squad_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    uid = str(update.effective_user.id)
    data = load_data()
    
    if code not in data["squads"]:
        await update.message.reply_text("Отряд не найден. Попробуй ещё раз:")
        return JOINING_SQUAD
    
    squad = data["squads"][code]
    if uid not in squad["members"]:
        squad["members"].append(uid)
    data["users"][uid]["squad_id"] = code
    save_data(data)
    
    await update.message.reply_text(f"✅ Ты вступил в отряд *{squad['name']}*!\n\nИспользуй /menu", parse_mode="Markdown")
    return ConversationHandler.END

async def handle_start_with_args(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.args and ctx.args[0].startswith("join_"):
        squad_id = ctx.args[0].replace("join_", "")
        uid = str(update.effective_user.id)
        data = load_data()
        user = get_user(data, uid)
        
        if not user:
            await update.message.reply_text("Сначала создай героя: /start")
            return ConversationHandler.END
        
        if squad_id in data["squads"]:
            squad = data["squads"][squad_id]
            if uid not in squad["members"]:
                squad["members"].append(uid)
            user["squad_id"] = squad_id
            save_data(data)
            await update.message.reply_text(f"✅ Ты вступил в отряд *{squad['name']}*!", parse_mode="Markdown")
        return ConversationHandler.END
    return await start(update, ctx)

async def menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    data = load_data()
    user = get_user(data, uid)
    
    if not user:
        await update.message.reply_text("Сначала зарегистрируйся: /start")
        return
    
    kb = [
        [InlineKeyboardButton("👤 Мой герой", callback_data="show_char"), InlineKeyboardButton("📋 Задания", callback_data="show_tasks")],
        [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task"), InlineKeyboardButton("🏰 Отряд", callback_data="show_squad")],
    ]
    await update.message.reply_text(f"Главное меню", reply_markup=InlineKeyboardMarkup(kb))

async def show_char(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    data = load_data()
    user = get_user(data, uid)
    
    if not user:
        await query.edit_message_text("Ошибка")
        return
    
    cls = CLASSES[user["class"]]
    text = f"{cls['emoji']} *{user['name']}* - {cls['name']}\nУровень: {user['level']}\nОпыт: {user['xp']}\nСтрик: {user['streak']} дн."
    kb = [[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    data = load_data()
    user = get_user(data, uid)
    today = str(date.today())
    tasks = user.get("tasks", [])
    done_today = [t for t in tasks if t.get("done_date") == today]
    
    if not tasks:
        kb = [[InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")], [InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]]
        await query.edit_message_text("Нет заданий", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    kb = []
    for t in tasks:
        is_done = t.get("done_date") == today
        label = f"{'✅' if is_done else '◻️'} {t['name']}"
        kb.append([InlineKeyboardButton(label, callback_data=f"do_task_{t['id']}")])
    
    kb.append([InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")])
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="back_menu")])
    await query.edit_message_text(f"Задания: {len(done_today)}/{len(tasks)}", reply_markup=InlineKeyboardMarkup(kb))

async def do_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = query.data.replace("do_task_", "")
    uid = str(query.from_user.id)
    data = load_data()
    user = get_user(data, uid)
    today = str(date.today())
    
    task = next((t for t in user["tasks"] if t["id"] == task_id), None)
    if not task or task.get("done_date") == today:
        await query.answer("Нельзя выполнить", show_alert=True)
        return
    
    task["done_date"] = today
    user["attrs"][task["attr"]] += task["attr_gain"]
    user["tasks_done"] += 1
    user["streak"] = user.get("streak", 0) + 1
    user["last_active"] = today
    add_xp(user, task["xp_gain"])
    save_data(data)
    
    await query.edit_message_text(f"✅ {task['name']} выполнено!\n+{task['xp_gain']} опыта")
    await show_tasks(update, ctx)

async def add_task_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введи название задания:")
    return ADDING_TASK_NAME

async def got_task_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new_task_name"] = update.message.text.strip()
    kb = [[InlineKeyboardButton(f"{a['emoji']} {a['name']}", callback_data=f"tattr_{k}")] for k, a in ATTRS.items()]
    await update.message.reply_text("Какой атрибут?", reply_markup=InlineKeyboardMarkup(kb))
    return ADDING_TASK_ATTR

async def got_task_attr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    attr_key = query.data.replace("tattr_", "")
    name = ctx.user_data.get("new_task_name", "Задание")
    uid = str(query.from_user.id)
    data = load_data()
    user = get_user(data, uid)
    
    import uuid
    user["tasks"].append({
        "id": str(uuid.uuid4())[:8], "name": name, "attr": attr_key,
        "xp_gain": 25, "attr_gain": 2, "done_date": None
    })
    save_data(data)
    
    await query.edit_message_text(f"✅ Задание добавлено!")
    await show_tasks(update, ctx)
    return ConversationHandler.END

async def show_squad(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    data = load_data()
    user = get_user(data, uid)
    
    squad_id = user.get("squad_id")
    if not squad_id or squad_id not in data["squads"]:
        kb = [[InlineKeyboardButton("🏰 Создать отряд", callback_data="squad_create"), InlineKeyboardButton("🔗 Вступить", callback_data="squad_join")], [InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]]
        await query.edit_message_text("Нет отряда", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    squad = data["squads"][squad_id]
    members = "\n".join([f"- {data['users'].get(mid, {}).get('name', '?')}" for mid in squad["members"]])
    await query.edit_message_text(f"Отряд: {squad['name']}\nУчастники:\n{members}")

async def back_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await menu(update, ctx)

# Веб-сервер для Railway
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run_flask).start()

def main():
    app = Application.builder().token(TOKEN).build()
    
    # Основной разговор
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", handle_start_with_args)],
        states={
            CHOOSING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            CHOOSING_CLASS: [CallbackQueryHandler(got_class, pattern="^class_")],
            AFTER_SQUAD: [
                CallbackQueryHandler(squad_create, pattern="^squad_create$"),
                CallbackQueryHandler(squad_join_prompt, pattern="^squad_join$"),
            ],
            CREATING_SQUAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_squad_name)],
            JOINING_SQUAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_squad_code)],
        },
        fallbacks=[CommandHandler("start", handle_start_with_args)],
    )
    
    # Разговор для добавления задания
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
    
    print("✅ Bot started!")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
