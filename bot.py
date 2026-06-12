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

CLASSES = {
    "warrior": "⚔️ Воин",
    "archer": "🏹 Лучник", 
    "mage": "🔮 Маг",
    "rogue": "🗡️ Разбойник"
}

ATTRS = {
    "str": "💪 Сила",
    "int": "📚 Интеллект",
    "hp": "❤️ Здоровье",
    "agi": "🤸 Ловкость",
    "wil": "🔥 Воля"
}

def load_data():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

async def show_tasks_list(query, uid, users):
    """Показывает список заданий"""
    user = users.get(uid)
    if not user:
        await query.edit_message_text("❌ Ошибка")
        return
    
    tasks = user.get('tasks', [])
    
    if not tasks:
        kb = [[InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")],
              [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "📋 *У тебя пока нет заданий*\n\nДобавь первое задание!",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return
    
    kb = []
    for task in tasks:
        status = "✅" if task.get('done') else "◻️"
        attr_emoji = ATTRS.get(task['attr'], "📌")
        kb.append([InlineKeyboardButton(f"{status} {task['name']} {attr_emoji}", callback_data=f"done_{task['id']}")])
    
    kb.append([InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")])
    kb.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")])
    
    done_count = len([t for t in tasks if t.get('done')])
    
    await query.edit_message_text(
        f"📋 *Твои задания*\n\n✅ Выполнено: {done_count}/{len(tasks)}\n\n👇 Нажми на задание, чтобы отметить:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def show_main_menu(update_obj, uid, users):
    """Показывает главное меню"""
    user = users.get(uid)
    if not user:
        if hasattr(update_obj, 'callback_query'):
            await update_obj.callback_query.edit_message_text("Ошибка")
        else:
            await update_obj.message.reply_text("Ошибка")
        return
    
    kb = [
        [InlineKeyboardButton("👤 Мой герой", callback_data="profile")],
        [InlineKeyboardButton("📋 Задания", callback_data="tasks")],
        [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")],
        [InlineKeyboardButton("🏰 Отряд", callback_data="squad")]
    ]
    
    text = f"🎮 *Главное меню*\n\n{user['name']} · Уровень {user['level']}"
    
    if hasattr(update_obj, 'callback_query'):
        await update_obj.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await update_obj.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ========== КОМАНДЫ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    data = load_data()
    
    if uid in data:
        await show_main_menu(update, uid, data)
        return
    
    context.user_data['step'] = 'name'
    await update.message.reply_text(
        "⚔️ *Добро пожаловать в Vysotix!*\n\nКак зовут твоего героя?",
        parse_mode="Markdown"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    data = load_data()
    
    if uid not in data:
        await update.message.reply_text("Сначала создай героя: /start")
        return
    
    await show_main_menu(update, uid, data)

# ========== ОБРАБОТКА ТЕКСТА ==========

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    step = context.user_data.get('step')
    
    # Шаг 1: Имя героя
    if step == 'name':
        if len(text) < 2:
            await update.message.reply_text("❌ Имя слишком короткое. Попробуй ещё:")
            return
        
        context.user_data['temp_name'] = text
        context.user_data['step'] = 'class'
        
        kb = [
            [InlineKeyboardButton("⚔️ Воин", callback_data="class_warrior")],
            [InlineKeyboardButton("🏹 Лучник", callback_data="class_archer")],
            [InlineKeyboardButton("🔮 Маг", callback_data="class_mage")],
            [InlineKeyboardButton("🗡️ Разбойник", callback_data="class_rogue")]
        ]
        
        await update.message.reply_text(
            f"👋 Отлично, *{text}*! Выбери класс:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return
    
    # Шаг 2: Название отряда
    if step == 'squad_name':
        squad_name = text
        if len(squad_name) < 2:
            await update.message.reply_text("❌ Название слишком короткое. Попробуй ещё:")
            return
        
        squad_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        squad_file = "data/squads.json"
        if os.path.exists(squad_file):
            with open(squad_file, "r", encoding="utf-8") as f:
                squads = json.load(f)
        else:
            squads = {}
        
        squads[squad_id] = {
            "name": squad_name,
            "members": [uid],
            "created": str(date.today())
        }
        
        with open(squad_file, "w", encoding="utf-8") as f:
            json.dump(squads, f)
        
        data = load_data()
        if uid in data:
            data[uid]["squad_id"] = squad_id
            save_data(data)
        
        bot = await context.bot.get_me()
        link = f"https://t.me/{bot.username}?start=squad_{squad_id}"
        
        await update.message.reply_text(
            f"🏰 *Отряд «{squad_name}» создан!*\n\n"
            f"📌 Код: `{squad_id}`\n"
            f"🔗 Ссылка: {link}\n\n"
            f"Отправь ссылку сыну!\n\n"
            f"Используй /menu",
            parse_mode="Markdown"
        )
        
        context.user_data['step'] = None
        return
    
    # Добавление задания - ПОЛУЧАЕМ НАЗВАНИЕ
    if context.user_data.get('awaiting_task_name'):
        task_name = text
        if len(task_name) < 2:
            await update.message.reply_text("❌ Название слишком короткое. Попробуй ещё:")
            return
        
        context.user_data['awaiting_task_name'] = False
        context.user_data['temp_task_name'] = task_name
        
        kb = []
        for key, name in ATTRS.items():
            kb.append([InlineKeyboardButton(name, callback_data=f"task_attr_{key}")])
        
        await update.message.reply_text(
            "📊 *Какой атрибут качает это задание?*",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return

# ========== ОБРАБОТКА КНОПОК ==========

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = str(query.from_user.id)
    data = query.data
    users = load_data()
    
    # ===== ВЫБОР КЛАССА =====
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
            f"{CLASSES[class_key]} *{name}* создан!\n\n"
            f"🏰 *Теперь создай семейный отряд*\n\n"
            f"Придумай название и напиши его:",
            parse_mode="Markdown"
        )
        return
    
    # ===== ДОБАВИТЬ ЗАДАНИЕ (кнопка) =====
    if data == 'add_task':
        context.user_data['awaiting_task_name'] = True
        await query.edit_message_text(
            "➕ *Новое задание*\n\nВведи название задания:",
            parse_mode="Markdown"
        )
        return
    
    # ===== ВЫБОР АТРИБУТА ДЛЯ ЗАДАНИЯ =====
    if data.startswith('task_attr_'):
        attr_key = data.replace('task_attr_', '')
        task_name = context.user_data.get('temp_task_name', 'Задание')
        
        user = users.get(uid)
        if not user:
            await query.edit_message_text("❌ Ошибка: пользователь не найден")
            return
        
        # Создаём задание
        new_task = {
            "id": str(uuid.uuid4())[:8],
            "name": task_name,
            "attr": attr_key,
            "xp": 25,
            "done": False
        }
        
        if 'tasks' not in user:
            user['tasks'] = []
        
        user['tasks'].append(new_task)
        save_data(users)
        
        # Очищаем временные данные
        context.user_data['temp_task_name'] = None
        
        # Показываем обновлённый список заданий
        await show_tasks_list(query, uid, users)
        return
    
    # ===== ПОКАЗАТЬ ПРОФИЛЬ =====
    if data == 'profile':
        user = users.get(uid)
        if not user:
            await query.edit_message_text("❌ Ошибка")
            return
        
        tasks_count = len(user.get('tasks', []))
        tasks_done = len([t for t in user.get('tasks', []) if t.get('done')])
        
        text = (
            f"👤 *{user['name']}*\n\n"
            f"⭐ Уровень: {user['level']}\n"
            f"📊 Опыт: {user['xp']}\n"
            f"🔥 Стрик: {user['streak']} дней\n"
            f"📋 Заданий: {tasks_done}/{tasks_count}"
        )
        
        kb = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return
    
    # ===== ПОКАЗАТЬ ЗАДАНИЯ =====
    if data == 'tasks':
        await show_tasks_list(query, uid, users)
        return
    
    # ===== ВЫПОЛНИТЬ ЗАДАНИЕ =====
    if data.startswith('done_'):
        task_id = data.replace('done_', '')
        user = users.get(uid)
        
        if not user:
            await query.edit_message_text("❌ Ошибка")
            return
        
        task = next((t for t in user['tasks'] if t['id'] == task_id), None)
        
        if not task:
            await query.edit_message_text("❌ Задание не найдено")
            return
        
        if task.get('done'):
            await query.answer("✅ Уже выполнено!", show_alert=True)
            return
        
        # Выполняем задание
        task['done'] = True
        user['xp'] += task['xp']
        user['streak'] = user.get('streak', 0) + 1
        
        # Проверка уровня
        level_up = False
        if user['xp'] >= user['level'] * 100:
            user['level'] += 1
            user['xp'] = user['xp'] - (user['level'] - 1) * 100
            level_up = True
        
        save_data(users)
        
        msg = f"✅ *{task['name']}* выполнено!\n\n➕ +{task['xp']} опыта"
        if level_up:
            msg += f"\n\n🎉 *ПОЗДРАВЛЯЮ!*\nТы достиг {user['level']} уровня!"
        
        await query.edit_message_text(msg, parse_mode="Markdown")
        return
    
    # ===== ПОКАЗАТЬ ОТРЯД =====
    if data == 'squad':
        user = users.get(uid)
        if not user:
            await query.edit_message_text("❌ Ошибка")
            return
        
        squad_id = user.get('squad_id')
        
        if not squad_id:
            kb = [[InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")],
                  [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]]
            await query.edit_message_text(
                "🏰 *У тебя нет отряда*",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown"
            )
            return
        
        squad_file = "data/squads.json"
        if os.path.exists(squad_file):
            with open(squad_file, "r", encoding="utf-8") as f:
                squads = json.load(f)
        else:
            squads = {}
        
        squad = squads.get(squad_id, {})
        
        members_text = ""
        for mid in squad.get('members', []):
            m = users.get(mid)
            if m:
                members_text += f"• {m['name']} (ур. {m['level']})\n"
        
        text = f"🏰 *{squad.get('name', 'Отряд')}*\n\n👨‍👦 *Участники:*\n{members_text}"
        
        kb = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return
    
    # ===== СОЗДАТЬ ОТРЯД =====
    if data == 'create_squad':
        context.user_data['step'] = 'squad_name'
        await query.edit_message_text(
            "🏰 *Создание отряда*\n\nПридумай название и напиши его:",
            parse_mode="Markdown"
        )
        return
    
    # ===== НАЗАД В МЕНЮ =====
    if data == 'back_to_menu':
        await show_main_menu(query, uid, users)
        return

# ========== ЗАПУСК ==========

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "🚀 Начать игру"),
        BotCommand("menu", "🎮 Главное меню"),
    ])

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.post_init = set_commands
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("✅ Бот Vysotix успешно запущен!")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
