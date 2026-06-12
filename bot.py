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

# ========== ГЛАВНОЕ МЕНЮ ==========
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id=None):
    uid = user_id or str(update.effective_user.id)
    users = load_users()
    
    if uid not in users:
        msg = "⚠️ *Ты ещё не создал героя!*\n\nНапиши /start чтобы начать игру"
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")
        return
    
    user = users[uid]
    cls = CLASSES[user['class']]
    
    kb = [
        [InlineKeyboardButton("👤 Мой герой", callback_data="profile")],
        [InlineKeyboardButton("📋 Задания", callback_data="tasks")],
        [InlineKeyboardButton("🏰 Отряд", callback_data="squad")],
        [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")]
    ]
    
    text = f"{cls['emoji']} *{user['name']}* · Уровень {user['level']} · 🔥{user['streak']}\n\n🎮 *Главное меню:*"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ========== КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_users()
    
    # Если пользователь уже есть - показываем меню
    if uid in users:
        await main_menu(update, context)
        return
    
    # Нет пользователя - начинаем регистрацию
    context.user_data['reg_name'] = None
    context.user_data['reg_class'] = None
    context.user_data['reg_step'] = 'name'
    
    await update.message.reply_text(
        "⚔️ *Добро пожаловать в Vysotix!*\n\n"
        "Это семейная RPG, где привычки прокачивают героя.\n\n"
        "🌟 *Как зовут твоего героя?*\n(напиши имя, 2-20 символов)",
        parse_mode="Markdown"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)

# ========== ОБРАБОТКА ТЕКСТА ==========
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    
    users = load_users()
    
    # ===== РЕГИСТРАЦИЯ: ШАГ 1 - ИМЯ =====
    if context.user_data.get('reg_step') == 'name':
        if len(text) < 2 or len(text) > 20:
            await update.message.reply_text("❌ Имя должно быть от 2 до 20 символов. Попробуй ещё:")
            return
        
        context.user_data['reg_name'] = text
        context.user_data['reg_step'] = 'class'
        
        kb = [
            [InlineKeyboardButton("⚔️ Воин", callback_data="reg_class_warrior")],
            [InlineKeyboardButton("🏹 Лучник", callback_data="reg_class_archer")],
            [InlineKeyboardButton("🔮 Маг", callback_data="reg_class_mage")],
            [InlineKeyboardButton("🗡️ Разбойник", callback_data="reg_class_rogue")]
        ]
        
        await update.message.reply_text(
            f"👋 Привет, *{text}*!\n\nВыбери класс своего героя:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return
    
    # ===== СОЗДАНИЕ ОТРЯДА =====
    if context.user_data.get('creating_squad'):
        squad_name = text
        
        if len(squad_name) < 2:
            await update.message.reply_text("❌ Название отряда слишком короткое. Попробуй ещё:")
            return
        
        squads = load_squads()
        squad_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        squads[squad_id] = {
            "name": squad_name,
            "creator": uid,
            "members": [uid],
            "created": str(date.today())
        }
        save_squads(squads)
        
        # Обновляем пользователя
        users = load_users()
        if uid in users:
            users[uid]["squad_id"] = squad_id
            save_users(users)
        
        bot_info = await context.bot.get_me()
        invite_link = f"https://t.me/{bot_info.username}?start=squad_{squad_id}"
        
        await update.message.reply_text(
            f"🏰 *Отряд «{squad_name}» создан!*\n\n"
            f"📌 Код отряда: `{squad_id}`\n\n"
            f"🔗 *Отправь эту ссылку сыну:*\n{invite_link}\n\n"
            f"👇 Нажми на кнопку, чтобы перейти в меню",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Перейти в меню", callback_data="menu")]]),
            parse_mode="Markdown"
        )
        
        context.user_data['creating_squad'] = False
        context.user_data['reg_step'] = None
        return
    
    # ===== ДОБАВЛЕНИЕ ЗАДАНИЯ =====
    if context.user_data.get('adding_task'):
        task_name = text
        
        if len(task_name) < 2:
            await update.message.reply_text("❌ Название задания слишком короткое. Попробуй ещё:")
            return
        
        context.user_data['temp_task_name'] = task_name
        context.user_data['adding_task'] = False
        context.user_data['awaiting_attr'] = True
        
        kb = [[InlineKeyboardButton(f"{a['emoji']} {a['name']}", callback_data=f"task_attr_{k}")] for k, a in ATTRS.items()]
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
    
    users = load_users()
    
    # ===== РЕГИСТРАЦИЯ: ВЫБОР КЛАССА =====
    if data.startswith('reg_class_'):
        class_key = data.replace('reg_class_', '')
        name = context.user_data.get('reg_name', 'Герой')
        
        # Создаём пользователя
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
        
        context.user_data['creating_squad'] = True
        context.user_data['reg_step'] = None
        
        await query.edit_message_text(
            f"{CLASSES[class_key]['emoji']} *{name}* ({CLASSES[class_key]['name']}) создан!\n\n"
            f"🏰 *Теперь создай семейный отряд*\n\n"
            f"Придумай название для вашего отряда.\n\n"
            f"✏️ *Введи название отряда:*",
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
        
        await query.edit_message_text(f"✅ *Задание «{task_name}» добавлено!*", parse_mode="Markdown")
        
        # Показываем задания
        await show_tasks(query, uid, users)
        return
    
    # ===== ВЫПОЛНИТЬ ЗАДАНИЕ =====
    if data.startswith('done_'):
        task_id = data.replace('done_', '')
        user = users.get(uid)
        if not user:
            await query.edit_message_text("❌ Ошибка")
            return
        
        today = str(date.today())
        task = next((t for t in user['tasks'] if t['id'] == task_id), None)
        
        if not task:
            await query.edit_message_text("❌ Задание не найдено")
            return
        
        if task.get('done_date') == today:
            await query.answer("✅ Уже выполнено сегодня!", show_alert=True)
            return
        
        # Выполняем задание
        task['done_date'] = today
        user['xp'] += task['xp_gain']
        user['attrs'][task['attr']] += task['attr_gain']
        user['streak'] += 1
        user['last_active'] = today
        
        # Проверка уровня (100 опыта на уровень)
        level_up = False
        if user['xp'] >= user['level'] * 100:
            user['level'] += 1
            level_up = True
        
        save_users(users)
        
        msg = f"✅ *{task['name']}* выполнено!\n\n➕ +{task['xp_gain']} опыта\n📈 +{task['attr_gain']} {ATTRS[task['attr']]['name']}"
        
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
            await query.edit_message_text("❌ Сначала создай героя: /start")
            return
        
        cls = CLASSES[user['class']]
        attrs_text = "\n".join([f"{ATTRS[k]['emoji']} {ATTRS[k]['name']}: {v}" for k, v in user['attrs'].items()])
        
        xp_needed = user['level'] * 100
        progress = int((user['xp'] / xp_needed) * 10) if xp_needed > 0 else 0
        bar = "█" * progress + "░" * (10 - progress)
        
        text = (
            f"{cls['emoji']} *{user['name']}* — {cls['name']}\n\n"
            f"⭐ *Уровень:* {user['level']}\n"
            f"📊 *Опыт:* {user['xp']}/{xp_needed}\n"
            f"`{bar}`\n"
            f"🔥 *Стрик:* {user['streak']} дней\n\n"
            f"*📈 Атрибуты:*\n{attrs_text}"
        )
        
        kb = [[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
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
            await query.edit_message_text("❌ Сначала создай героя: /start")
            return
        
        squad_id = user.get('squad_id')
        if not squad_id:
            kb = [[InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")],
                  [InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
            await query.edit_message_text(
                "🏰 *У тебя пока нет отряда*\n\nСоздай свой отряд!",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown"
            )
            return
        
        squads = load_squads()
        squad = squads.get(squad_id)
        if not squad:
            await query.edit_message_text("❌ Отряд не найден")
            return
        
        members_text = ""
        for mid in squad['members']:
            m = users.get(mid)
            if m:
                members_text += f"{CLASSES[m['class']]['emoji']} *{m['name']}* — {m['level']} ур.\n"
        
        bot_info = await context.bot.get_me()
        invite_link = f"https://t.me/{bot_info.username}?start=squad_{squad_id}"
        
        kb = [[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
        
        await query.edit_message_text(
            f"🏰 *{squad['name']}*\n\n*👨‍👦 Участники:*\n{members_text}\n\n"
            f"🔗 *Ссылка для приглашения:*\n`{invite_link}`",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return
    
    # ===== СОЗДАТЬ ОТРЯД =====
    if data == 'create_squad':
        context.user_data['creating_squad'] = True
        await query.edit_message_text(
            "🏰 *Создание отряда*\n\n"
            "Придумай название для вашего семейного отряда.\n\n"
            "✏️ *Введи название отряда:*",
            parse_mode="Markdown"
        )
        return
    
    # ===== ГЛАВНОЕ МЕНЮ =====
    if data == 'menu':
        await main_menu(query, context, uid)

async def show_tasks(query, uid, users):
    user = users.get(uid)
    if not user:
        await query.edit_message_text("❌ Сначала создай героя: /start")
        return
    
    tasks = user.get('tasks', [])
    today = str(date.today())
    
    if not tasks:
        kb = [[InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")],
              [InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
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
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
    
    done_count = len([t for t in tasks if t.get('done_date') == today])
    
    await query.edit_message_text(
        f"📋 *Твои задания*\n\n"
        f"✅ Выполнено сегодня: {done_count}/{len(tasks)}\n\n"
        f"👇 Нажми на задание, чтобы отметить его выполненным:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

# ========== УСТАНОВКА КОМАНД В ИНТЕРФЕЙСЕ ==========
async def set_bot_commands(app):
    commands = [
        BotCommand("start", "🚀 Начать игру / Создать героя"),
        BotCommand("menu", "🎮 Главное меню"),
    ]
    await app.bot.set_my_commands(commands)

# ========== ЗАПУСК ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.post_init = set_bot_commands
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("✅ Бот Vysotix успешно запущен!")
    print("📌 Команды /start и /menu отображаются в интерфейсе Telegram")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
