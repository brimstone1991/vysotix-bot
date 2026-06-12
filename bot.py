import os
import json
import logging
from datetime import date
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

# Веб-сервер
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is running"

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run_flask).start()

# Классы
CLASSES = {
    "warrior": "⚔️ Воин",
    "archer": "🏹 Лучник", 
    "mage": "🔮 Маг",
    "rogue": "🗡️ Разбойник"
}

def load_data():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# ========== КОМАНДЫ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    data = load_data()
    
    if uid in data:
        await update.message.reply_text(f"С возвращением, {data[uid]['name']}! Используй /menu")
        return
    
    context.user_data['step'] = 'name'
    await update.message.reply_text("⚔️ Добро пожаловать в Vysotix!\n\nКак зовут твоего героя?")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    data = load_data()
    
    if uid not in data:
        await update.message.reply_text("Сначала создай героя: /start")
        return
    
    user = data[uid]
    kb = [
        [InlineKeyboardButton("👤 Мой герой", callback_data="profile")],
        [InlineKeyboardButton("📋 Задания", callback_data="tasks")],
        [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")],
        [InlineKeyboardButton("🏰 Отряд", callback_data="squad")]
    ]
    
    await update.message.reply_text(
        f"Главное меню\n{user['name']} · Уровень {user['level']}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ========== ОБРАБОТКА ТЕКСТА ==========

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    step = context.user_data.get('step')
    
    # Шаг 1: Имя героя
    if step == 'name':
        if len(text) < 2:
            await update.message.reply_text("Имя слишком короткое. Попробуй ещё:")
            return
        
        context.user_data['temp_name'] = text
        context.user_data['step'] = 'class'
        
        kb = [
            [InlineKeyboardButton("⚔️ Воин", callback_data="class_warrior")],
            [InlineKeyboardButton("🏹 Лучник", callback_data="class_archer")],
            [InlineKeyboardButton("🔮 Маг", callback_data="class_mage")],
            [InlineKeyboardButton("🗡️ Разбойник", callback_data="class_rogue")]
        ]
        
        await update.message.reply_text(f"Отлично, {text}! Выбери класс:", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    # Шаг 2: Название отряда
    if step == 'squad_name':
        squad_name = text
        if len(squad_name) < 2:
            await update.message.reply_text("Название слишком короткое. Попробуй ещё:")
            return
        
        # Генерируем код отряда
        squad_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Сохраняем отряд
        squad_file = "data/squads.json"
        if os.path.exists(squad_file):
            with open(squad_file, "r") as f:
                squads = json.load(f)
        else:
            squads = {}
        
        squads[squad_id] = {
            "name": squad_name,
            "members": [uid],
            "created": str(date.today())
        }
        
        with open(squad_file, "w") as f:
            json.dump(squads, f)
        
        # Обновляем пользователя
        data = load_data()
        data[uid]["squad_id"] = squad_id
        save_data(data)
        
        bot = await context.bot.get_me()
        link = f"https://t.me/{bot.username}?start=squad_{squad_id}"
        
        await update.message.reply_text(
            f"🏰 Отряд '{squad_name}' создан!\n\n"
            f"Код: {squad_id}\n"
            f"Ссылка: {link}\n\n"
            f"Отправь ссылку сыну, чтобы он вступил!\n\n"
            f"/menu - перейти в меню"
        )
        
        context.user_data['step'] = None
        return
    
    # Добавление задания
    if context.user_data.get('adding_task'):
        context.user_data['adding_task'] = False
        context.user_data['temp_task'] = text
        
        kb = [
            [InlineKeyboardButton("💪 Сила", callback_data="attr_str")],
            [InlineKeyboardButton("📚 Интеллект", callback_data="attr_int")],
            [InlineKeyboardButton("❤️ Здоровье", callback_data="attr_hp")],
            [InlineKeyboardButton("🤸 Ловкость", callback_data="attr_agi")],
            [InlineKeyboardButton("🔥 Воля", callback_data="attr_wil")]
        ]
        
        await update.message.reply_text("Какой атрибут качает это задание?", reply_markup=InlineKeyboardMarkup(kb))
        return

# ========== ОБРАБОТКА КНОПОК ==========

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = str(query.from_user.id)
    data = query.data
    users = load_data()
    
    # Выбор класса
    if data.startswith('class_'):
        class_key = data.replace('class_', '')
        name = context.user_data.get('temp_name', 'Герой')
        
        users[uid] = {
            "name": name,
            "class": class_key,
            "level": 1,
            "xp": 0,
            "streak": 0,
            "tasks": [],
            "squad_id": None
        }
        save_data(users)
        
        context.user_data['step'] = 'squad_name'
        
        await query.edit_message_text(
            f"{CLASSES[class_key]} {name} создан!\n\n"
            f"Теперь создай семейный отряд.\n"
            f"Придумай название:"
        )
        return
    
    # Выбор атрибута для задания
    if data.startswith('attr_'):
        attr = data.replace('attr_', '')
        task_name = context.user_data.get('temp_task', 'Задание')
        
        user = users.get(uid)
        if not user:
            await query.edit_message_text("Ошибка")
            return
        
        new_task = {
            "id": str(uuid.uuid4())[:8],
            "name": task_name,
            "attr": attr,
            "xp": 25,
            "done": False
        }
        
        user['tasks'].append(new_task)
        save_data(users)
        
        await query.edit_message_text(f"✅ Задание '{task_name}' добавлено!")
        return
    
    # Показать профиль
    if data == 'profile':
        user = users.get(uid)
        if not user:
            await query.edit_message_text("Ошибка")
            return
        
        text = f"👤 {user['name']}\n⭐ Уровень: {user['level']}\n📊 Опыт: {user['xp']}\n🔥 Стрик: {user['streak']}\n📋 Заданий: {len(user['tasks'])}"
        
        await query.edit_message_text(text)
        return
    
    # Показать задания
    if data == 'tasks':
        user = users.get(uid)
        if not user:
            await query.edit_message_text("Ошибка")
            return
        
        tasks = user.get('tasks', [])
        
        if not tasks:
            await query.edit_message_text("Нет заданий. Добавь через /menu")
            return
        
        kb = []
        for task in tasks:
            status = "✅" if task.get('done') else "◻️"
            kb.append([InlineKeyboardButton(f"{status} {task['name']}", callback_data=f"done_{task['id']}")])
        
        await query.edit_message_text("Твои задания:", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    # Выполнить задание
    if data.startswith('done_'):
        task_id = data.replace('done_', '')
        user = users.get(uid)
        
        if not user:
            await query.edit_message_text("Ошибка")
            return
        
        task = next((t for t in user['tasks'] if t['id'] == task_id), None)
        
        if not task:
            await query.edit_message_text("Задание не найдено")
            return
        
        if task.get('done'):
            await query.answer("Уже выполнено!", show_alert=True)
            return
        
        task['done'] = True
        user['xp'] += task['xp']
        user['streak'] += 1
        
        # Проверка уровня
        if user['xp'] >= user['level'] * 100:
            user['level'] += 1
            level_up = True
        else:
            level_up = False
        
        save_data(users)
        
        msg = f"✅ {task['name']} выполнено! +{task['xp']} опыта"
        if level_up:
            msg += f"\n\n🎉 УРОВЕНЬ {user['level']}!"
        
        await query.edit_message_text(msg)
        return
    
    # Показать отряд
    if data == 'squad':
        user = users.get(uid)
        if not user:
            await query.edit_message_text("Ошибка")
            return
        
        squad_id = user.get('squad_id')
        
        if not squad_id:
            kb = [[InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")]]
            await query.edit_message_text("У тебя нет отряда. Создать?", reply_markup=InlineKeyboardMarkup(kb))
            return
        
        squad_file = "data/squads.json"
        if os.path.exists(squad_file):
            with open(squad_file, "r") as f:
                squads = json.load(f)
        else:
            squads = {}
        
        squad = squads.get(squad_id, {})
        
        text = f"🏰 {squad.get('name', 'Отряд')}\nУчастников: {len(squad.get('members', []))}"
        await query.edit_message_text(text)
        return
    
    # Создать отряд
    if data == 'create_squad':
        context.user_data['step'] = 'squad_name'
        await query.edit_message_text("Придумай название отряда и напиши его:")
        return

# ========== ЗАПУСК ==========

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать игру"),
        BotCommand("menu", "Главное меню"),
    ])

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.post_init = set_commands
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("✅ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
