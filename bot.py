import os
import json
import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread
import random
import string
import uuid

# Настройки
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN", "")
DATA_FILE = "data/users.json"
SQUADS_FILE = "data/squads.json"

# Веб-сервер для Railway
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "✅ Vysotix Bot is running!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run_flask).start()

# Классы и атрибуты
CLASSES = {
    "warrior": {"name": "Воин", "emoji": "⚔️"},
    "archer": {"name": "Лучник", "emoji": "🏹"},
    "mage": {"name": "Маг", "emoji": "🔮"},
    "rogue": {"name": "Разбойник", "emoji": "🗡️"}
}

ATTRS = {
    "str": {"name": "Сила", "emoji": "💪"},
    "int": {"name": "Интеллект", "emoji": "📚"},
    "hp": {"name": "Здоровье", "emoji": "❤️"},
    "agi": {"name": "Ловкость", "emoji": "🤸"},
    "wil": {"name": "Воля", "emoji": "🔥"}
}

# Работа с данными
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
    if not os.path.exists(SQUADS_FILE):
        return {}
    with open(SQUADS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_squads(squads):
    with open(SQUADS_FILE, "w", encoding="utf-8") as f:
        json.dump(squads, f, ensure_ascii=False, indent=2)

def create_user(uid, name, class_key):
    return {
        "name": name,
        "class": class_key,
        "level": 1,
        "xp": 0,
        "attrs": {"str": 0, "int": 0, "hp": 0, "agi": 0, "wil": 0},
        "streak": 0,
        "last_active": str(date.today()),
        "tasks": [],
        "squad_id": None
    }

# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_users()
    
    if uid in users:
        await update.message.reply_text(f"С возвращением, {users[uid]['name']}! Используй /menu")
        return
    
    context.user_data['step'] = 'awaiting_name'
    await update.message.reply_text(
        "⚔️ *Добро пожаловать в Vysotix!*\n\n"
        "Как зовут твоего героя? (напиши имя)",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    step = context.user_data.get('step')
    
    users = load_users()
    
    # Шаг 1: ожидание имени
    if step == 'awaiting_name':
        if len(text) < 2:
            await update.message.reply_text("Имя слишком короткое. Попробуй ещё:")
            return
        
        context.user_data['temp_name'] = text
        
        # Показываем выбор класса
        kb = []
        row = []
        for key, cls in CLASSES.items():
            row.append(InlineKeyboardButton(f"{cls['emoji']} {cls['name']}", callback_data=f"class_{key}"))
            if len(row) == 2:
                kb.append(row)
                row = []
        if row:
            kb.append(row)
        
        await update.message.reply_text(
            f"Отлично, *{text}*! Выбери класс героя:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        context.user_data['step'] = 'awaiting_class'
        return
    
    # Шаг 2: ожидание названия отряда
    if step == 'awaiting_squad_name':
        squad_name = text
        squads = load_squads()
        
        # Генерируем код отряда
        squad_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        squads[squad_id] = {
            "name": squad_name,
            "creator": uid,
            "members": [uid],
            "created": str(date.today())
        }
        save_squads(squads)
        
        # Обновляем пользователя
        users[uid]["squad_id"] = squad_id
        save_users(users)
        
        bot_info = await context.bot.get_me()
        invite_link = f"https://t.me/{bot_info.username}?start=squad_{squad_id}"
        
        await update.message.reply_text(
            f"🏰 *Отряд «{squad_name}» создан!*\n\n"
            f"Код отряда: `{squad_id}`\n\n"
            f"🔗 Отправь эту ссылку сыну, чтобы он вступил:\n"
            f"{invite_link}\n\n"
            f"Используй /menu для управления",
            parse_mode="Markdown"
        )
        
        context.user_data['step'] = None
        return

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = str(query.from_user.id)
    data = query.data
    
    users = load_users()
    
    # Выбор класса
    if data.startswith('class_'):
        class_key = data.replace('class_', '')
        name = context.user_data.get('temp_name', 'Герой')
        
        users[uid] = create_user(uid, name, class_key)
        save_users(users)
        
        context.user_data['step'] = 'awaiting_squad_name'
        
        await query.edit_message_text(
            f"{CLASSES[class_key]['emoji']} *{name}* ({CLASSES[class_key]['name']}) создан!\n\n"
            f"Теперь создай семейный отряд.\n\n"
            f"🏰 *Введи название отряда:*",
            parse_mode="Markdown"
        )
        return
    
    # Создание отряда из меню
    if data == 'create_squad':
        context.user_data['step'] = 'awaiting_squad_name'
        await query.edit_message_text("🏰 Введи название отряда:")
        return
    
    # Показать профиль
    if data == 'profile':
        user = users.get(uid)
        if not user:
            await query.edit_message_text("Сначала создай героя: /start")
            return
        
        cls = CLASSES[user['class']]
        attrs_text = "\n".join([f"{ATTRS[k]['emoji']} {ATTRS[k]['name']}: {v}" for k, v in user['attrs'].items()])
        
        text = (
            f"{cls['emoji']} *{user['name']}* — {cls['name']}\n\n"
            f"⭐ Уровень: {user['level']}\n"
            f"📊 Опыт: {user['xp']}\n"
            f"🔥 Стрик: {user['streak']} дней\n\n"
            f"*Атрибуты:*\n{attrs_text}"
        )
        
        kb = [[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return
    
    # Показать задания
    if data == 'tasks':
        user = users.get(uid)
        if not user:
            await query.edit_message_text("Сначала создай героя: /start")
            return
        
        tasks = user.get('tasks', [])
        today = str(date.today())
        
        if not tasks:
            kb = [[InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")],
                  [InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
            await query.edit_message_text("У тебя пока нет заданий. Добавь первое!", reply_markup=InlineKeyboardMarkup(kb))
            return
        
        kb = []
        for task in tasks:
            is_done = task.get('done_date') == today
            status = "✅" if is_done else "◻️"
            kb.append([InlineKeyboardButton(f"{status} {task['name']}", callback_data=f"done_{task['id']}")])
        
        kb.append([InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
        
        done_count = len([t for t in tasks if t.get('done_date') == today])
        await query.edit_message_text(f"📋 *Задания* ({done_count}/{len(tasks)} выполнено сегодня)", 
                                      reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return
    
    # Добавить задание
    if data == 'add_task':
        context.user_data['adding_task'] = True
        await query.edit_message_text("➕ Введи название задания:")
        return
    
    # Выполнить задание
    if data.startswith('done_'):
        task_id = data.replace('done_', '')
        user = users.get(uid)
        if not user:
            await query.edit_message_text("Ошибка")
            return
        
        today = str(date.today())
        task = next((t for t in user['tasks'] if t['id'] == task_id), None)
        
        if not task:
            await query.edit_message_text("Задание не найдено")
            return
        
        if task.get('done_date') == today:
            await query.answer("Уже выполнено сегодня!", show_alert=True)
            return
        
        # Выполняем задание
        task['done_date'] = today
        user['xp'] += task['xp_gain']
        user['attrs'][task['attr']] += task['attr_gain']
        user['streak'] += 1
        user['last_active'] = today
        
        # Проверка уровня
        xp_needed = user['level'] * 100
        if user['xp'] >= xp_needed:
            user['level'] += 1
            user['xp'] -= xp_needed
            level_up = True
        else:
            level_up = False
        
        save_users(users)
        
        msg = f"✅ {task['name']} выполнено!\n+{task['xp_gain']} опыта"
        if level_up:
            msg += f"\n\n🎉 ПОЗДРАВЛЯЮ! Ты достиг {user['level']} уровня!"
        
        await query.edit_message_text(msg)
        
        # Показываем обновлённый список заданий
        await handle_callback(update, context)
        return
    
    # Показать отряд
    if data == 'squad':
        user = users.get(uid)
        if not user:
            await query.edit_message_text("Сначала создай героя: /start")
            return
        
        squad_id = user.get('squad_id')
        if not squad_id:
            kb = [[InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")],
                  [InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
            await query.edit_message_text("У тебя пока нет отряда. Создай новый!", reply_markup=InlineKeyboardMarkup(kb))
            return
        
        squads = load_squads()
        squad = squads.get(squad_id)
        if not squad:
            await query.edit_message_text("Отряд не найден")
            return
        
        members_text = ""
        for mid in squad['members']:
            m = users.get(mid)
            if m:
                members_text += f"{CLASSES[m['class']]['emoji']} {m['name']} — {m['level']} ур.\n"
        
        await query.edit_message_text(f"🏰 *{squad['name']}*\n\n*Участники:*\n{members_text}", parse_mode="Markdown")
        return
    
    # Меню
    if data == 'menu':
        await show_menu(query, uid, users)

async def show_menu(query, uid, users):
    user = users.get(uid)
    if not user:
        await query.edit_message_text("Сначала создай героя: /start")
        return
    
    kb = [
        [InlineKeyboardButton("👤 Мой герой", callback_data="profile")],
        [InlineKeyboardButton("📋 Задания", callback_data="tasks")],
        [InlineKeyboardButton("🏰 Отряд", callback_data="squad")],
        [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")]
    ]
    
    cls = CLASSES[user['class']]
    await query.edit_message_text(
        f"{cls['emoji']} *{user['name']}* · Уровень {user['level']} · 🔥{user['streak']}\n\nГлавное меню:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_users()
    
    if uid not in users:
        await update.message.reply_text("Сначала создай героя: /start")
        return
    
    kb = [
        [InlineKeyboardButton("👤 Мой герой", callback_data="profile")],
        [InlineKeyboardButton("📋 Задания", callback_data="tasks")],
        [InlineKeyboardButton("🏰 Отряд", callback_data="squad")],
        [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")]
    ]
    
    user = users[uid]
    cls = CLASSES[user['class']]
    await update.message.reply_text(
        f"{cls['emoji']} *{user['name']}* · Уровень {user['level']} · 🔥{user['streak']}\n\nГлавное меню:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def add_task_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('adding_task'):
        return
    
    uid = str(update.effective_user.id)
    task_name = update.message.text.strip()
    
    context.user_data['temp_task_name'] = task_name
    
    kb = [[InlineKeyboardButton(f"{a['emoji']} {a['name']}", callback_data=f"attr_{k}")] for k, a in ATTRS.items()]
    await update.message.reply_text(
        "Какой атрибут качает это задание?",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    context.user_data['adding_task'] = False
    context.user_data['awaiting_attr'] = True

async def task_attr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not context.user_data.get('awaiting_attr'):
        return
    
    attr_key = query.data.replace('attr_', '')
    task_name = context.user_data.get('temp_task_name', 'Задание')
    uid = str(query.from_user.id)
    
    users = load_users()
    user = users.get(uid)
    
    if not user:
        await query.edit_message_text("Ошибка")
        return
    
    new_task = {
        "id": str(uuid.uuid4())[:8],
        "name": task_name,
        "attr": attr_key,
        "xp_gain": 25,
        "attr_gain": 2,
        "done_date": None
    }
    
    user['tasks'].append(new_task)
    save_users(users)
    
    context.user_data['awaiting_attr'] = False
    context.user_data['temp_task_name'] = None
    
    await query.edit_message_text(f"✅ Задание «{task_name}» добавлено!")
    
    # Показываем обновлённые задания
    fake_update = type('obj', (object,), {'callback_query': query})()
    await handle_callback(fake_update, context)

# Запуск бота
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(CallbackQueryHandler(task_attr_callback, pattern="^attr_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Бот Vysotix успешно запущен!")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
