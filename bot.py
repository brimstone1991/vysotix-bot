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

# Веб-сервер для Railway
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "✅ Vysotix Bot is running!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run_flask).start()

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

# ========== ГЛАВНОЕ МЕНЮ (КНОПКИ ВНИЗУ) ==========
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id=None):
    """Показывает главное меню с инлайн-кнопками"""
    uid = user_id or str(update.effective_user.id)
    users = load_users()
    
    if uid not in users:
        if update.callback_query:
            await update.callback_query.edit_message_text("Сначала создай героя: /start")
        else:
            await update.message.reply_text("Сначала создай героя: /start")
        return
    
    user = users[uid]
    cls = CLASSES[user['class']]
    
    kb = [
        [InlineKeyboardButton("👤 Мой герой", callback_data="profile")],
        [InlineKeyboardButton("📋 Задания", callback_data="tasks")],
        [InlineKeyboardButton("🏰 Отряд", callback_data="squad")],
        [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")]
    ]
    
    text = f"{cls['emoji']} *{user['name']}* · Уровень {user['level']} · 🔥{user['streak']}\n\nГлавное меню:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ========== КОМАНДЫ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_users()
    
    if uid in users:
        await show_main_menu(update, context)
        return
    
    context.user_data['step'] = 'awaiting_name'
    await update.message.reply_text(
        "⚔️ *Добро пожаловать в Vysotix!*\n\n"
        "Это семейная RPG, где привычки прокачивают твоего героя.\n\n"
        "🎮 *Как зовут твоего героя?* (напиши имя)",
        parse_mode="Markdown"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context)

# ========== ОБРАБОТКА ВСЕХ ТЕКСТОВЫХ СООБЩЕНИЙ ==========

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    step = context.user_data.get('step')
    
    # ===== ШАГ 1: ОЖИДАНИЕ ИМЕНИ =====
    if step == 'awaiting_name':
        if len(text) < 2:
            await update.message.reply_text("Имя слишком короткое. Попробуй ещё:")
            return
        
        context.user_data['temp_name'] = text
        context.user_data['step'] = 'awaiting_class'
        
        kb = [
            [InlineKeyboardButton("⚔️ Воин", callback_data="class_warrior")],
            [InlineKeyboardButton("🏹 Лучник", callback_data="class_archer")],
            [InlineKeyboardButton("🔮 Маг", callback_data="class_mage")],
            [InlineKeyboardButton("🗡️ Разбойник", callback_data="class_rogue")]
        ]
        
        await update.message.reply_text(
            f"Отлично, *{text}*! Выбери класс героя:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return
    
    # ===== ШАГ 2: ОЖИДАНИЕ НАЗВАНИЯ ОТРЯДА =====
    if step == 'awaiting_squad_name':
        squad_name = text
        squads = load_squads()
        
        squad_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        squads[squad_id] = {
            "name": squad_name,
            "creator": uid,
            "members": [uid],
            "created": str(date.today())
        }
        save_squads(squads)
        
        users = load_users()
        if uid in users:
            users[uid]["squad_id"] = squad_id
            save_users(users)
        
        bot_info = await context.bot.get_me()
        invite_link = f"https://t.me/{bot_info.username}?start=squad_{squad_id}"
        
        await update.message.reply_text(
            f"🏰 *Отряд «{squad_name}» создан!*\n\n"
            f"📌 Код отряда: `{squad_id}`\n\n"
            f"🔗 Отправь эту ссылку сыну, чтобы он вступил:\n"
            f"{invite_link}\n\n"
            f"👇 *Нажми на кнопку ниже, чтобы перейти в меню*",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Перейти в меню", callback_data="menu")]]),
            parse_mode="Markdown"
        )
        
        context.user_data['step'] = None
        return
    
    # ===== ДОБАВЛЕНИЕ ЗАДАНИЯ =====
    if context.user_data.get('adding_task'):
        context.user_data['adding_task'] = False
        context.user_data['temp_task_name'] = text
        context.user_data['awaiting_attr'] = True
        
        kb = [[InlineKeyboardButton(f"{a['emoji']} {a['name']}", callback_data=f"attr_{k}")] for k, a in ATTRS.items()]
        await update.message.reply_text(
            "Какой атрибут качает это задание?",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

# ========== ОБРАБОТКА КНОПОК ==========

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = str(query.from_user.id)
    data = query.data
    
    users = load_users()
    
    # ===== ВЫБОР КЛАССА =====
    if data.startswith('class_'):
        class_key = data.replace('class_', '')
        name = context.user_data.get('temp_name', 'Герой')
        
        users[uid] = {
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
        save_users(users)
        
        context.user_data['step'] = 'awaiting_squad_name'
        
        await query.edit_message_text(
            f"{CLASSES[class_key]['emoji']} *{name}* ({CLASSES[class_key]['name']}) создан!\n\n"
            f"🏰 *Придумай название для семейного отряда*\n\n"
            f"Например: «Семья Подвысоцких», «Бобры», «Могучие воины»\n\n"
            f"✏️ *Введи название отряда:*",
            parse_mode="Markdown"
        )
        return
    
    # ===== ВЫБОР АТРИБУТА ДЛЯ ЗАДАНИЯ =====
    if data.startswith('attr_'):
        attr_key = data.replace('attr_', '')
        task_name = context.user_data.get('temp_task_name', 'Задание')
        
        user = users.get(uid)
        if not user:
            await query.edit_message_text("Ошибка: пользователь не найден")
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
        
        # Показываем задания
        await show_tasks(query, uid, users)
        return
    
    # ===== ВЫПОЛНИТЬ ЗАДАНИЕ =====
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
        
        task['done_date'] = today
        user['xp'] += task['xp_gain']
        user['attrs'][task['attr']] += task['attr_gain']
        user['streak'] += 1
        user['last_active'] = today
        
        # Проверка уровня
        xp_needed = user['level'] * 100
        level_up = False
        if user['xp'] >= xp_needed:
            user['level'] += 1
            user['xp'] -= xp_needed
            level_up = True
        
        save_users(users)
        
        msg = f"✅ *{task['name']}* выполнено!\n\n+{task['xp_gain']} опыта"
        if level_up:
            msg += f"\n\n🎉 *ПОЗДРАВЛЯЮ!*\nТы достиг {user['level']} уровня!"
        
        await query.edit_message_text(msg, parse_mode="Markdown")
        
        # Показываем обновлённые задания
        await show_tasks(query, uid, users)
        return
    
    # ===== ПРОФИЛЬ =====
    if data == 'profile':
        user = users.get(uid)
        if not user:
            await query.edit_message_text("Сначала создай героя: /start")
            return
        
        cls = CLASSES[user['class']]
        attrs_text = "\n".join([f"{ATTRS[k]['emoji']} {ATTRS[k]['name']}: {v}" for k, v in user['attrs'].items()])
        
        # Прогресс до следующего уровня
        xp_needed = user['level'] * 100
        progress = int((user['xp'] / xp_needed) * 10)
        bar = "█" * progress + "░" * (10 - progress)
        
        text = (
            f"{cls['emoji']} *{user['name']}* — {cls['name']}\n\n"
            f"⭐ *Уровень:* {user['level']}\n"
            f"📊 *Опыт:* {user['xp']}/{xp_needed}\n"
            f"`{bar}`\n"
            f"🔥 *Стрик:* {user['streak']} дней\n\n"
            f"*📈 Атрибуты:*\n{attrs_text}"
        )
        
        kb = [[InlineKeyboardButton("◀️ Назад в меню", callback_data="menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return
    
    # ===== ПОКАЗАТЬ ЗАДАНИЯ =====
    if data == 'tasks':
        await show_tasks(query, uid, users)
        return
    
    # ===== ДОБАВИТЬ ЗАДАНИЕ =====
    if data == 'add_task':
        context.user_data['adding_task'] = True
        await query.edit_message_text("➕ *Введи название задания:*", parse_mode="Markdown")
        return
    
    # ===== ПОКАЗАТЬ ОТРЯД =====
    if data == 'squad':
        user = users.get(uid)
        if not user:
            await query.edit_message_text("Сначала создай героя: /start")
            return
        
        squad_id = user.get('squad_id')
        if not squad_id:
            kb = [[InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")],
                  [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu")]]
            await query.edit_message_text(
                "🏰 *У тебя пока нет отряда*\n\nСоздай свой отряд, чтобы присоединиться к семье!",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown"
            )
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
                members_text += f"{CLASSES[m['class']]['emoji']} *{m['name']}* — {m['level']} уровень\n"
        
        bot_info = await context.bot.get_me()
        invite_link = f"https://t.me/{bot_info.username}?start=squad_{squad_id}"
        
        kb = [
            [InlineKeyboardButton("🔗 Скопировать ссылку", callback_data=f"copy_{squad_id}")],
            [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu")]
        ]
        
        await query.edit_message_text(
            f"🏰 *{squad['name']}*\n\n*👨‍👦 Участники:*\n{members_text}\n\n"
            f"🔗 *Ссылка для приглашения:*\n`{invite_link}`",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return
    
    # ===== СОЗДАТЬ ОТРЯД =====
    if data == 'create_squad':
        context.user_data['step'] = 'awaiting_squad_name'
        await query.edit_message_text(
            "🏰 *Создание отряда*\n\n"
            "Придумай название для вашего семейного отряда.\n\n"
            "✏️ *Введи название отряда:*",
            parse_mode="Markdown"
        )
        return
    
    # ===== ГЛАВНОЕ МЕНЮ =====
    if data == 'menu':
        await show_main_menu(query, context, uid)
        return

async def show_tasks(query, uid, users):
    user = users.get(uid)
    if not user:
        await query.edit_message_text("Сначала создай героя: /start")
        return
    
    tasks = user.get('tasks', [])
    today = str(date.today())
    
    if not tasks:
        kb = [[InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")],
              [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu")]]
        await query.edit_message_text(
            "📋 *У тебя пока нет заданий*\n\nДобавь своё первое задание!",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return
    
    kb = []
    for task in tasks:
        is_done = task.get('done_date') == today
        status = "✅" if is_done else "◻️"
        attr_emoji = ATTRS.get(task['attr'], {'emoji': '📌'})['emoji']
        kb.append([InlineKeyboardButton(f"{status} {task['name']} {attr_emoji}", callback_data=f"done_{task['id']}")])
    
    kb.append([InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")])
    kb.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="menu")])
    
    done_count = len([t for t in tasks if t.get('done_date') == today])
    total_xp = sum([t['xp_gain'] for t in tasks if t.get('done_date') == today])
    
    await query.edit_message_text(
        f"📋 *Твои задания*\n\n"
        f"✅ Выполнено сегодня: {done_count}/{len(tasks)}\n"
        f"📊 Опыта получено: {total_xp}\n\n"
        f"Нажми на задание, чтобы отметить его выполненным:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

# ========== ЗАПУСК ==========

async def set_bot_commands(app):
    """Устанавливает кнопки-команды в интерфейсе Telegram"""
    commands = [
        BotCommand("start", "🚀 Начать игру / Создать героя"),
        BotCommand("menu", "🎮 Главное меню"),
    ]
    await app.bot.set_my_commands(commands)

def main():
    app = Application.builder().token(TOKEN).build()
    
    # Устанавливаем команды в интерфейсе
    app.post_init = set_bot_commands
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Бот Vysotix успешно запущен!")
    print("📌 Команды /start и /menu теперь отображаются в интерфейсе Telegram")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
