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

# Flask
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Vysotix bot is running"

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    Thread(target=run_flask, daemon=True).start()

# Константы
CLASSES = {"warrior": "⚔️ Воин", "archer": "🏹 Лучник", "mage": "🔮 Маг", "rogue": "🗡️ Разбойник"}
ATTRS = {"str": "💪 Сила", "int": "📚 Интеллект", "hp": "❤️ Здоровье", "agi": "🤸 Ловкость", "wil": "🔥 Воля"}

# Данные
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

def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def new_user(name, class_key):
    return {
        "name": name,
        "class": class_key,
        "level": 1,
        "xp": 0,
        "attrs": {"str": 0, "int": 0, "hp": 0, "agi": 0, "wil": 0},
        "streak": 0,
        "last_active": str(date.today()),
        "tasks": [],
        "assigned_tasks": [],
        "squad_id": None,
    }

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
    pending = len([t for t in user.get("assigned_tasks", []) if t.get("done_date") != today])
    
    kb = [
        [InlineKeyboardButton("👤 Мой герой", callback_data="profile"), InlineKeyboardButton("📋 Задания", callback_data="tasks")],
        [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task"), InlineKeyboardButton("🏰 Отряд", callback_data="squad")],
    ]
    text = f"{CLASSES[user['class']]} *{user['name']}* · Ур.{user['level']} · 🔥{user['streak']}\n✅ Сегодня: {done}/{total}"
    if pending:
        text += f"\n👨‍👦 Заданий от родителей: {pending}"
    
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
    await update.message.reply_text("⚔️ *Vysotix*\n\nКак зовут твоего героя?", parse_mode="Markdown")

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await show_menu(update, uid)

# ========== ТЕКСТ ==========
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    step = ctx.user_data.get("step")
    
    # Имя героя
    if step == "name":
        if len(text) < 2:
            await update.message.reply_text("Имя слишком короткое:")
            return
        ctx.user_data["temp_name"] = text
        ctx.user_data["step"] = "class"
        kb = [[InlineKeyboardButton(v, callback_data=f"class_{k}")] for k, v in CLASSES.items()]
        await update.message.reply_text(f"Выбери класс для *{text}*:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return
    
    # Название отряда
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
            save_users(users)
        ctx.user_data["step"] = None
        await update.message.reply_text(
            f"🏰 *Отряд «{text}» создан!*\nКод: `{squad_id}`\n\nОтправь код тому, кого хочешь пригласить.\n/menu",
            parse_mode="Markdown"
        )
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
            if uid not in squads[squad_code]["members"]:
                squads[squad_code]["members"].append(uid)
            save_users(users)
            save_squads(squads)
            await update.message.reply_text(f"✅ Вступил в *{squads[squad_code]['name']}*!\n/menu", parse_mode="Markdown")
        else:
            ctx.user_data["pending_squad"] = squad_code
            await update.message.reply_text("Сначала создай героя: /start")
        ctx.user_data["awaiting_squad_code"] = False
        return
    
    # Добавление задания (своего)
    if ctx.user_data.get("awaiting_task_name"):
        if len(text) < 2:
            await update.message.reply_text("Название слишком короткое:")
            return
        ctx.user_data["temp_task_name"] = text
        ctx.user_data["awaiting_task_name"] = False
        ctx.user_data["awaiting_attr"] = True
        kb = [[InlineKeyboardButton(v, callback_data=f"task_attr_{k}")] for k, v in ATTRS.items()]
        await update.message.reply_text("Какой атрибут?", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    # Название задания для ребёнка
    if ctx.user_data.get("awaiting_assign_task_name"):
        if len(text) < 2:
            await update.message.reply_text("Название слишком короткое:")
            return
        ctx.user_data["temp_assign_task_name"] = text
        ctx.user_data["awaiting_assign_task_name"] = False
        ctx.user_data["awaiting_assign_attr"] = True
        kb = [[InlineKeyboardButton(v, callback_data=f"assign_attr_{k}")] for k, v in ATTRS.items()]
        await update.message.reply_text("Какой атрибут?", reply_markup=InlineKeyboardMarkup(kb))
        return

# ========== ЗАДАНИЯ ==========
async def show_tasks(query, uid):
    users = load_users()
    user = users.get(uid)
    if not user:
        await query.edit_message_text("Ошибка")
        return
    
    today = str(date.today())
    own_tasks = user.get("tasks", [])
    assigned_tasks = user.get("assigned_tasks", [])
    
    kb = []
    for t in own_tasks:
        is_done = t.get("done_date") == today
        status = "✅" if is_done else "◻️"
        attr = ATTRS.get(t["attr"], "📌")
        kb.append([InlineKeyboardButton(f"{status} {t['name']} {attr}", callback_data=f"done_{t['id']}")])
    
    for t in assigned_tasks:
        is_done = t.get("done_date") == today
        status = "✅" if is_done else "◻️"
        attr = ATTRS.get(t["attr"], "📌")
        parent = t.get("assigned_by_name", "родитель")
        kb.append([InlineKeyboardButton(f"{status} {t['name']} {attr} (от {parent})", callback_data=f"adone_{t['id']}")])
    
    if not own_tasks and not assigned_tasks:
        kb.append([InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")])
    
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
    
    own_done = len([t for t in own_tasks if t.get("done_date") == today])
    asgn_done = len([t for t in assigned_tasks if t.get("done_date") == today])
    
    text = f"📋 *Задания*\n\n✅ Свои: {own_done}/{len(own_tasks)}\n✅ От родителей: {asgn_done}/{len(assigned_tasks)}"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ========== CALLBACKS ==========
async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    data = query.data
    users = load_users()
    user = users.get(uid)
    
    print(f"DEBUG: {data}")  # ОТЛАДКА
    
    # Меню
    if data == "menu":
        await show_menu(query, uid, edit=True)
        return
    
    # Выбор класса
    if data.startswith("class_"):
        class_key = data.replace("class_", "")
        name = ctx.user_data.get("temp_name", "Герой")
        users[uid] = new_user(name, class_key)
        save_users(users)
        
        kb = [
            [InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")],
            [InlineKeyboardButton("🔗 Вступить по коду", callback_data="join_squad")],
        ]
        await query.edit_message_text(f"{CLASSES[class_key]} *{name}* создан!\n\nСоздай или вступи в отряд:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return
    
    if not user:
        await query.edit_message_text("Создай героя: /start")
        return
    
    # Профиль
    if data == "profile":
        attrs = "\n".join([f"{ATTRS[k]}: {v}" for k, v in user["attrs"].items()])
        text = f"👤 *{user['name']}* {CLASSES[user['class']]}\n⭐ Уровень {user['level']}\n📊 Опыт: {user['xp']}\n🔥 Стрик: {user['streak']}\n\n{attrs}"
        kb = [[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
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
    
    # Выбор атрибута для своего задания
    if data.startswith("task_attr_"):
        attr_key = data.replace("task_attr_", "")
        task_name = ctx.user_data.get("temp_task_name", "Задание")
        task = {"id": str(uuid.uuid4())[:8], "name": task_name, "attr": attr_key, "xp_gain": 25, "attr_gain": 2, "done_date": ""}
        user.setdefault("tasks", []).append(task)
        save_users(users)
        ctx.user_data["temp_task_name"] = None
        await query.edit_message_text(f"✅ Задание *{task_name}* добавлено!", parse_mode="Markdown")
        await show_tasks(query, uid)
        return
    
    # Выполнить своё задание
    if data.startswith("done_"):
        task_id = data.replace("done_", "")
        today = str(date.today())
        task = next((t for t in user.get("tasks", []) if t["id"] == task_id), None)
        if not task or task.get("done_date") == today:
            await query.answer("Нельзя выполнить", show_alert=True)
            return
        task["done_date"] = today
        user["attrs"][task["attr"]] += task["attr_gain"]
        user["xp"] += task["xp_gain"]
        user["streak"] += 1
        user["last_active"] = today
        if user["xp"] >= user["level"] * 100:
            user["level"] += 1
            user["xp"] = 0
        save_users(users)
        await query.edit_message_text(f"✅ {task['name']} выполнено! +{task['xp_gain']} опыта", parse_mode="Markdown")
        await show_tasks(query, uid)
        return
    
    # Выполнить задание от родителя
    if data.startswith("adone_"):
        task_id = data.replace("adone_", "")
        today = str(date.today())
        task = next((t for t in user.get("assigned_tasks", []) if t["id"] == task_id), None)
        if not task or task.get("done_date") == today:
            await query.answer("Нельзя выполнить", show_alert=True)
            return
        task["done_date"] = today
        user["attrs"][task["attr"]] += task.get("attr_gain", 2)
        user["xp"] += task.get("xp_gain", 30)
        user["streak"] += 1
        user["last_active"] = today
        if user["xp"] >= user["level"] * 100:
            user["level"] += 1
            user["xp"] = 0
        save_users(users)
        
        # Уведомляем родителя
        if task.get("assigned_by"):
            try:
                await query.get_bot().send_message(chat_id=int(task["assigned_by"]), text=f"👨‍👦 *{user['name']}* выполнил задание!\n✅ {task['name']}", parse_mode="Markdown")
            except:
                pass
        
        await query.edit_message_text(f"✅ {task['name']} выполнено! +{task.get('xp_gain', 30)} опыта", parse_mode="Markdown")
        await show_tasks(query, uid)
        return
    
    # Отряд
    if data == "squad":
        squad_id = user.get("squad_id")
        squads = load_squads()
        if not squad_id or squad_id not in squads:
            kb = [[InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")], [InlineKeyboardButton("🔗 Вступить по коду", callback_data="join_squad")], [InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
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
    
    # ===== ГЛАВНОЕ: ДАТЬ ЗАДАНИЕ =====
    if data.startswith("assign_to_"):
        target_uid = data.replace("assign_to_", "")
        target_user = users.get(target_uid)
        if not target_user:
            await query.answer("Участник не найден", show_alert=True)
            return
        ctx.user_data["assign_target_uid"] = target_uid
        ctx.user_data["awaiting_assign_task_name"] = True
        await query.edit_message_text(f"📝 *Задание для {target_user['name']}*\n\nВведи название:", parse_mode="Markdown")
        return
    
    # Выбор атрибута для задания ребёнку
    if data.startswith("assign_attr_"):
        attr_key = data.replace("assign_attr_", "")
        target_uid = ctx.user_data.get("assign_target_uid")
        task_name = ctx.user_data.get("temp_assign_task_name", "Задание")
        
        target_user = users.get(target_uid)
        if not target_user:
            await query.edit_message_text("Ошибка")
            return
        
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
        
        # Уведомляем
        try:
            await query.get_bot().send_message(chat_id=int(target_uid), text=f"👨‍👦 *{user['name']}* дал задание!\n\n📋 *{task_name}*\nВыполни в /menu → Задания", parse_mode="Markdown")
        except:
            pass
        
        await query.edit_message_text(f"✅ Задание *{task_name}* дано {target_user['name']}!")
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
            attr = ATTRS.get(t["attr"], "📌")
            task_lines += f"{status} {t['name']} {attr}\n"
        
        kb = [[InlineKeyboardButton(f"📝 Дать задание {target_user['name']}", callback_data=f"assign_to_{target_uid}")], [InlineKeyboardButton("◀️ Назад", callback_data="squad")]]
        
        await query.edit_message_text(
            f"{CLASSES[target_user['class']]} *{target_user['name']}* — Ур.{target_user['level']}\n\n"
            f"*Задания от родителей:*\n{task_lines if task_lines else 'Нет'}\n\n"
            f"✅ Выполнено: {asgn_done}/{len(assigned)}",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

async def show_squad_menu(query, uid, squad_id):
    users = load_users()
    squads = load_squads()
    squad = squads.get(squad_id, {})
    members_text = ""
    kb = []
    
    for mid in squad.get("members", []):
        m = users.get(mid)
        if not m:
            continue
        members_text += f"{CLASSES[m['class']]} *{m['name']}* — Ур.{m['level']}\n"
        if mid != uid:
            kb.append([InlineKeyboardButton(f"👁 {m['name']}", callback_data=f"view_member_{mid}")])
    
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
    
    await query.edit_message_text(
        f"🏰 *{squad['name']}*\n\n{members_text}\n\nКод: `{squad_id}`",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

# Запуск
async def post_init(app):
    await app.bot.set_my_commands([BotCommand("start", "Начать игру"), BotCommand("menu", "Главное меню")])

def main():
    app = Application.builder().token(TOKEN).build()
    app.post_init = post_init
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
