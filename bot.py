import os
import json
import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN", "")
DATA_FILE = "data/users.json"

# Веб-сервер для Railway
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run_flask).start()

# Загрузка/сохранение данных
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Команда /start
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    data = load_data()
    
    if uid in data["users"]:
        await update.message.reply_text(f"Привет, {data['users'][uid]['name']}! Используй /menu")
        return
    
    ctx.user_data["waiting_name"] = True
    await update.message.reply_text("Привет! Как зовут твоего героя? Напиши имя:")

# Обработка текста (имя героя)
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    data = load_data()
    
    # Если ждём имя
    if ctx.user_data.get("waiting_name"):
        if len(text) < 2:
            await update.message.reply_text("Имя слишком короткое. Попробуй ещё:")
            return
        
        # Сохраняем имя
        data["users"][uid] = {
            "name": text,
            "level": 1,
            "xp": 0,
            "tasks": [],
            "streak": 0
        }
        save_data(data)
        ctx.user_data["waiting_name"] = False
        
        await update.message.reply_text(f"Отлично, {text}! Твой герой создан. Используй /menu")
        return
    
    # Если ждём название отряда
    if ctx.user_data.get("waiting_squad"):
        squad_name = text
        import random, string
        squad_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Сохраняем отряд
        squad_file = "data/squads.json"
        if os.path.exists(squad_file):
            with open(squad_file, "r") as f:
                squads = json.load(f)
        else:
            squads = {}
        
        squads[squad_id] = {"name": squad_name, "creator": uid, "members": [uid]}
        with open(squad_file, "w") as f:
            json.dump(squads, f)
        
        # Сохраняем ID отряда у пользователя
        data = load_data()
        data["users"][uid]["squad_id"] = squad_id
        save_data(data)
        
        ctx.user_data["waiting_squad"] = False
        bot_username = (await update.get_bot().get_me()).username
        
        await update.message.reply_text(
            f"✅ Отряд '{squad_name}' создан!\n\n"
            f"Код отряда: `{squad_id}`\n"
            f"Ссылка: https://t.me/{bot_username}?start={squad_id}\n\n"
            f"Отправь ссылку друзьям! Используй /menu",
            parse_mode="Markdown"
        )
        return

# Команда /menu
async def menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    data = load_data()
    
    if uid not in data["users"]:
        await update.message.reply_text("Сначала создай героя: /start")
        return
    
    kb = [
        [InlineKeyboardButton("👤 Мой герой", callback_data="profile")],
        [InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")],
        [InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")],
    ]
    await update.message.reply_text("Меню:", reply_markup=InlineKeyboardMarkup(kb))

# Обработка кнопок
async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    data = load_data()
    
    if query.data == "profile":
        user = data["users"].get(uid)
        if user:
            await query.edit_message_text(f"👤 *{user['name']}*\n⭐ Уровень: {user['level']}\n🔥 Стрик: {user['streak']} дн.\n📋 Заданий выполнено: {user['xp']}", parse_mode="Markdown")
        else:
            await query.edit_message_text("Ошибка")
    
    elif query.data == "create_squad":
        ctx.user_data["waiting_squad"] = True
        await query.edit_message_text("Введи название отряда:")
    
    elif query.data == "add_task":
        ctx.user_data["adding_task"] = True
        await query.edit_message_text("Введи название задания:")

# Запуск
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("✅ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
