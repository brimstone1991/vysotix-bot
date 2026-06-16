import os
import json
import logging
from datetime import date, timedelta, time as dtime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread
import random
import string
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
TOKEN = os.environ.get("BOT_TOKEN", "")
DATA_FILE = "data/users.json"
SQUADS_FILE = "data/squads.json"
BOSSES_FILE = "data/bosses.json"
REWARD_SHOP_FILE = "data/reward_shop.json"
DAILY_QUESTS_FILE = "data/daily_quests.json"

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

BOSS_POOL = [
    {
        "phases": ["🐉 Дракон Лени", "🔥 Пылающий Дракон", "💀 Дракон Тьмы"],
        "weak_attr": "wil", "hp": 300, "daily_dmg": 15,
        "reward": "🐉 Клык Дракона", "reward_desc": "Редкий аксессуар",
        "flavor": "Пожирает мотивацию. Слаб против Воли.",
    },
    {
        "phases": ["👾 Туманный Великан", "⚡ Великан Бури", "🌑 Великан Хаоса"],
        "weak_attr": "hp", "hp": 400, "daily_dmg": 20,
        "reward": "🌿 Амулет здоровья", "reward_desc": "Даёт здоровье в трудные дни",
        "flavor": "Нарушает режим сна. Слаб против Здоровья.",
    },
    {
        "phases": ["🍔 Король Фастфуда", "🌶️ Огненный Король", "☠️ Король Яда"],
        "weak_attr": "hp", "hp": 350, "daily_dmg": 15,
        "reward": "🥗 Щит Питания", "reward_desc": "Защищает от соблазнов",
        "flavor": "Отравляет привычки питания. Слаб против Здоровья.",
    },
    {
        "phases": ["📱 Повелитель Экранов", "🌀 Вихрь Отвлечений", "🕳️ Чёрная Дыра"],
        "weak_attr": "wil", "hp": 380, "daily_dmg": 18,
        "reward": "🎯 Кольцо фокуса", "reward_desc": "Помогает не отвлекаться",
        "flavor": "Похищает время. Слаб против Воли.",
    },
    {
        "phases": ["📚 Страж Невежества", "🌫️ Туман Забвения", "🧟 Пожиратель Знаний"],
        "weak_attr": "int", "hp": 420, "daily_dmg": 20,
        "reward": "📖 Tome мудреца", "reward_desc": "Артефакт знаний",
        "flavor": "Блокирует развитие. Слаб против Интеллекта.",
    },
]

# ========== ПУЛЫ ЕЖЕДНЕВНЫХ КВЕСТОВ ==========

DAILY_QUEST_POOL = {
    "str": [
        {"name": "Сделай 20 отжиманий",           "xp": 30, "attr_gain": 3},
        {"name": "Сделай 30 приседаний",           "xp": 30, "attr_gain": 3},
        {"name": "Пройди 5000 шагов",              "xp": 35, "attr_gain": 3},
        {"name": "Планка 1 минуту",                "xp": 25, "attr_gain": 2},
        {"name": "10 минут любой тренировки",      "xp": 30, "attr_gain": 3},
        {"name": "15 прыжков на месте",            "xp": 20, "attr_gain": 2},
        {"name": "Подтянись хотя бы 3 раза",       "xp": 35, "attr_gain": 3},
    ],
    "int": [
        {"name": "Прочитай 10 страниц книги",      "xp": 30, "attr_gain": 3},
        {"name": "Посмотри обучающее видео",       "xp": 25, "attr_gain": 2},
        {"name": "Реши 5 задач или упражнений",    "xp": 35, "attr_gain": 3},
        {"name": "Запиши что нового узнал сегодня","xp": 25, "attr_gain": 2},
        {"name": "Выучи 5 новых слов",             "xp": 25, "attr_gain": 2},
        {"name": "Реши головоломку или кроссворд", "xp": 30, "attr_gain": 3},
        {"name": "30 минут без телефона за учёбой","xp": 35, "attr_gain": 3},
    ],
    "hp": [
        {"name": "Ляг спать до 23:00",             "xp": 30, "attr_gain": 3},
        {"name": "Выпей 6 стаканов воды",          "xp": 25, "attr_gain": 2},
        {"name": "Съешь фрукт или овощ",           "xp": 20, "attr_gain": 2},
        {"name": "20 минут на свежем воздухе",     "xp": 30, "attr_gain": 3},
        {"name": "Не ешь сладкое весь день",       "xp": 35, "attr_gain": 3},
        {"name": "Сделай утреннюю зарядку",        "xp": 30, "attr_gain": 3},
        {"name": "Без телефона за 30 мин до сна",  "xp": 30, "attr_gain": 3},
    ],
    "agi": [
        {"name": "Растяжка 10 минут",              "xp": 25, "attr_gain": 2},
        {"name": "Скакалка 5 минут",               "xp": 30, "attr_gain": 3},
        {"name": "Потанцуй 10 минут",              "xp": 25, "attr_gain": 2},
        {"name": "Пройди по прямой линии 20 шагов","xp": 20, "attr_gain": 2},
        {"name": "Активная игра 15 минут",         "xp": 30, "attr_gain": 3},
        {"name": "Порисуй — развивай координацию", "xp": 25, "attr_gain": 2},
        {"name": "10 минут баланс-упражнений",     "xp": 30, "attr_gain": 3},
    ],
    "wil": [
        {"name": "Откажись от одного соблазна",    "xp": 35, "attr_gain": 3},
        {"name": "Сделай то что откладывал",       "xp": 40, "attr_gain": 4},
        {"name": "5 минут медитации или тишины",   "xp": 30, "attr_gain": 3},
        {"name": "Не жалуйся весь день",           "xp": 35, "attr_gain": 3},
        {"name": "Сделай что-то доброе для другого","xp": 30, "attr_gain": 3},
        {"name": "Час без соцсетей и видео",       "xp": 35, "attr_gain": 3},
        {"name": "Закончи начатое дело до конца",  "xp": 35, "attr_gain": 3},
    ],
}

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

def load_bosses():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(BOSSES_FILE):
        return {}
    with open(BOSSES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_bosses(bosses):
    os.makedirs("data", exist_ok=True)
    with open(BOSSES_FILE, "w", encoding="utf-8") as f:
        json.dump(bosses, f, ensure_ascii=False, indent=2)

def load_daily_quests():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DAILY_QUESTS_FILE):
        return {}
    with open(DAILY_QUESTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_daily_quests(dq):
    os.makedirs("data", exist_ok=True)
    with open(DAILY_QUESTS_FILE, "w", encoding="utf-8") as f:
        json.dump(dq, f, ensure_ascii=False, indent=2)

def load_reward_shop():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(REWARD_SHOP_FILE):
        default_shop = {
            "items": [
                {"id": "str1", "name": "💪 Тренировка +5 Силы",        "cost": 50, "attr": "str", "amount": 5},
                {"id": "int1", "name": "📚 Книга знаний +5 Интеллекта", "cost": 50, "attr": "int", "amount": 5},
                {"id": "hp1",  "name": "❤️ Витамины +5 Здоровья",       "cost": 50, "attr": "hp",  "amount": 5},
                {"id": "agi1", "name": "🤸 Упражнения +5 Ловкости",     "cost": 50, "attr": "agi", "amount": 5},
                {"id": "wil1", "name": "🔥 Медаль воли +5 Воли",        "cost": 50, "attr": "wil", "amount": 5},
            ]
        }
        save_reward_shop(default_shop)
        return default_shop
    with open(REWARD_SHOP_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_reward_shop(shop):
    os.makedirs("data", exist_ok=True)
    with open(REWARD_SHOP_FILE, "w", encoding="utf-8") as f:
        json.dump(shop, f, ensure_ascii=False, indent=2)

def new_user(name, cls_key, role="child"):
    return {
        "name": name,
        "class": cls_key,
        "role": role,
        "level": 1,
        "xp": 0,
        "attrs": {"str": 0, "int": 0, "hp": 0, "agi": 0, "wil": 0},
        "reward_points": 0,
        "streak": 0,
        "last_done_date": "",
        "tasks": [],
        "assigned_tasks": [],
        "gear": [],
        "squad_id": None,
    }

def xp_needed(lvl):
    if lvl < len(XP_TABLE):
        return XP_TABLE[lvl]
    return XP_TABLE[-1] + (lvl - len(XP_TABLE) + 1) * 600

def update_streak(user):
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))
    last = user.get("last_done_date", "")
    if last == today:
        return
    elif last == yesterday:
        user["streak"] = user.get("streak", 0) + 1
    else:
        user["streak"] = 1
    user["last_done_date"] = today

def add_xp(user, amount):
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
    today = str(date.today())
    for t in user.get("tasks", []):
        if t.get("done_date") != today:
            t["done"] = False
    for t in user.get("assigned_tasks", []):
        if t.get("done_date") != today:
            t["done"] = False

# ========== ЕЖЕДНЕВНЫЕ КВЕСТЫ ==========

def get_daily_quests(uid):
    """Возвращает квесты на сегодня. Генерирует новые если день изменился."""
    today = str(date.today())
    dq_data = load_daily_quests()
    if uid in dq_data and dq_data[uid].get("date") == today:
        return dq_data[uid]["quests"]
    quests = []
    for attr_key, pool in DAILY_QUEST_POOL.items():
        tpl = random.choice(pool)
        quests.append({
            "id": f"dq_{attr_key}",
            "name": tpl["name"],
            "attr": attr_key,
            "xp_gain": tpl["xp"],
            "attr_gain": tpl["attr_gain"],
            "done_date": "",
        })
    dq_data[uid] = {"date": today, "quests": quests}
    save_daily_quests(dq_data)
    return quests

def save_user_quests(uid, quests):
    dq_data = load_daily_quests()
    today = str(date.today())
    dq_data[uid] = {"date": today, "quests": quests}
    save_daily_quests(dq_data)

# ========== БОСС ==========

def get_or_create_boss(squad_id):
    bosses = load_bosses()
    today = str(date.today())
    if squad_id in bosses:
        boss = bosses[squad_id]
        days_alive = (date.today() - date.fromisoformat(boss.get("created", today))).days
        if days_alive < 7 and not boss.get("defeated"):
            return boss, bosses
    template = random.choice(BOSS_POOL)
    boss = {
        "phases": template["phases"],
        "weak_attr": template["weak_attr"],
        "hp_max": template["hp"],
        "hp": template["hp"],
        "daily_dmg": template["daily_dmg"],
        "reward": template["reward"],
        "reward_desc": template["reward_desc"],
        "flavor": template["flavor"],
        "created": today,
        "deadline": str(date.today() + timedelta(days=7)),
        "defeated": False,
        "damage_log": {},
        "last_hit_date": {},
    }
    bosses[squad_id] = boss
    save_bosses(bosses)
    return boss, bosses

def boss_phase(boss):
    pct = boss["hp"] / boss["hp_max"]
    if pct > 0.66:
        return 0, boss["phases"][0]
    elif pct > 0.33:
        return 1, boss["phases"][1]
    else:
        return 2, boss["phases"][2]

def boss_hp_bar(boss):
    pct = boss["hp"] / boss["hp_max"]
    filled = int(pct * 12)
    return "❤️" * filled + "🖤" * (12 - filled)

def calc_damage(task_attr, boss_weak_attr, user_attr_val):
    base = 8 + min(user_attr_val // 5, 12)
    if task_attr == boss_weak_attr:
        base = int(base * 1.5)
    return base

def boss_card(boss, squad_id, users_data, squad_members):
    phase_idx, phase_name = boss_phase(boss)
    hp_bar = boss_hp_bar(boss)
    days_left = (date.fromisoformat(boss["deadline"]) - date.today()).days
    weak_attr = ATTRS[boss["weak_attr"]]
    top = sorted(boss.get("damage_log", {}).items(), key=lambda x: x[1], reverse=True)
    top_text = ""
    for mid, dmg in top[:3]:
        m = users_data.get(mid)
        if m:
            cls = CLASSES.get(m["class"], list(CLASSES.values())[0])
            top_text += f"  {cls['emoji']} {m['name']}: {dmg} урона\n"
    return (
        f"{'⭐' * (phase_idx+1)} {phase_name}\n\n"
        f"{hp_bar}\n"
        f"HP: {boss['hp']} / {boss['hp_max']}\n\n"
        f"_{boss['flavor']}_\n\n"
        f"⚡ Слабость: {weak_attr['emoji']} {weak_attr['name']} — +50% урон!\n"
        f"💀 Урон за пропуск квестов: {boss.get('daily_dmg', 15)} HP герою\n"
        f"⏳ До конца рейда: {max(0, days_left)} дн.\n\n"
        f"*Урон отряда:*\n{top_text or '  пока нет урона'}"
    )

# ========== КАРТОЧКА ГЕРОЯ ==========

def char_card(user):
    cls = CLASSES.get(user["class"], list(CLASSES.values())[0])
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
    role = user.get("role", "child")
    role_label = "Родитель 👨‍👩‍👧‍👦" if role == "parent" else "Ребёнок 🧒"
    card = (
        f"{cls['emoji']} *{user['name']}* — {cls['name']} ({role_label})\n"
        f"⭐ Уровень {lvl}   🔥 Стрик {user.get('streak', 0)} дн.\n"
        f"🏆 Очки наград: {user.get('reward_points', 0)}\n"
        f"Опыт: {xp} / {xp_max}\n"
        f"`{bar}`\n\n"
        f"*Атрибуты:*\n`{attrs_lines}`\n"
        f"*Снаряжение:*\n{gear_text}\n\n"
        f"✅ Свои задания: {done_today}/{total}"
    )
    if role != "parent":
        done_assigned = len([t for t in user.get("assigned_tasks", []) if t.get("done_date") == today])
        total_assigned = len(user.get("assigned_tasks", []))
        card += f"\n👨‍👦 От родителей: {done_assigned}/{total_assigned}"
    return card

# ========== НОЧНАЯ АТАКА БОССА ==========

async def nightly_boss_attack(context):
    """Запускается в 00:05. Герои не выполнившие ни одного квеста получают урон от босса."""
    logger.info("Nightly boss attack running")
    users = load_users()
    squads = load_squads()
    yesterday = str(date.today() - timedelta(days=1))
    changed = False

    for uid, user in users.items():
        squad_id = user.get("squad_id")
        if not squad_id:
            continue
        boss, bosses = get_or_create_boss(squad_id)
        if boss["defeated"]:
            continue

        # Проверяем квесты за вчера
        dq_data = load_daily_quests()
        user_dq = dq_data.get(uid, {})
        quests_yesterday = user_dq.get("quests", []) if user_dq.get("date") == yesterday else []
        done_count = len([q for q in quests_yesterday if q.get("done_date") == yesterday])

        if done_count == 0:
            dmg = boss.get("daily_dmg", 15)
            msg = (
                f"💀 *{boss['phases'][0]}* атакует!\n\n"
                f"Вчера не было выполнено ни одного квеста.\n"
                f"Герой получает *{dmg} урона*!\n\n"
                f"Не забудь выполнить квесты сегодня — /menu"
            )
            try:
                await context.bot.send_message(chat_id=int(uid), text=msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Boss attack notify error {uid}: {e}")
            changed = True

    if changed:
        save_users(users)

# ========== ГЛАВНОЕ МЕНЮ ==========

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

    role = user.get("role", "child")
    cls = CLASSES.get(user["class"], list(CLASSES.values())[0])
    today = str(date.today())
    done_today = len([t for t in user.get("tasks", []) if t.get("done_date") == today])
    total = len(user.get("tasks", []))
    squad_id = user.get("squad_id")

    # Квесты дня
    dq = get_daily_quests(uid)
    dq_done = len([q for q in dq if q.get("done_date") == today])
    dq_total = len(dq)

    boss_line = ""
    if squad_id:
        boss, _ = get_or_create_boss(squad_id)
        if not boss["defeated"]:
            _, phase_name = boss_phase(boss)
            pct = int(boss["hp"] / boss["hp_max"] * 100)
            boss_line = f"\n⚔️ Рейд: {phase_name} — {pct}% HP"

    if role == "parent":
        squads = load_squads()
        children_info = ""
        children_list = []
        if squad_id and squad_id in squads:
            for mid in squads[squad_id].get("members", []):
                if mid == uid:
                    continue
                m = users.get(mid)
                if m and m.get("role") != "parent":
                    children_list.append(mid)
                    m_cls = CLASSES.get(m["class"], list(CLASSES.values())[0])
                    m_dq = get_daily_quests(mid)
                    m_dq_done = len([q for q in m_dq if q.get("done_date") == today])
                    m_done = len([t for t in m.get("tasks", []) if t.get("done_date") == today])
                    m_asgn_done = len([t for t in m.get("assigned_tasks", []) if t.get("done_date") == today])
                    m_total = len(m.get("tasks", []))
                    m_asgn_total = len(m.get("assigned_tasks", []))
                    children_info += (
                        f"  {m_cls['emoji']} *{m['name']}* Ур.{m['level']} · "
                        f"🌟{m_dq_done}/{len(m_dq)} · ✅{m_done}/{m_total} · 👨‍👦{m_asgn_done}/{m_asgn_total}\n"
                    )
        if children_info:
            children_info = f"\n*Дети:*\n{children_info}"

        kb = [
            [InlineKeyboardButton("👤 Мой герой", callback_data="profile"),
             InlineKeyboardButton("🌟 Квесты дня", callback_data="daily_quests")],
            [InlineKeyboardButton("📋 Мои задания", callback_data="tasks"),
             InlineKeyboardButton("🏰 Отряд", callback_data="squad")],
        ]
        if children_list:
            kb.append([InlineKeyboardButton("👨‍👧 Задания детям", callback_data="assign_menu")])
            kb.append([InlineKeyboardButton("🏆 Управление наградами", callback_data="parent_rewards_menu")])
        kb.append([InlineKeyboardButton("⚔️ Босс рейд", callback_data="boss")])

        text = (
            f"👨‍👩‍👧‍👦 *{user['name']}* ({cls['name']}) · Ур.{user['level']} · 🔥{user.get('streak',0)}\n"
            f"🌟 Квесты дня: {dq_done}/{dq_total} · ✅ Задания: {done_today}/{total}"
            f"{children_info}{boss_line}"
        )
    else:
        done_assigned = len([t for t in user.get("assigned_tasks", []) if t.get("done_date") == today])
        total_assigned = len(user.get("assigned_tasks", []))
        assigned_line = ""
        if total_assigned > 0 and (total_assigned - done_assigned) > 0:
            assigned_line = f"\n👨‍👦 От родителей: {total_assigned - done_assigned} ждут"

        kb = [
            [InlineKeyboardButton("👤 Мой герой", callback_data="profile"),
             InlineKeyboardButton("🌟 Квесты дня", callback_data="daily_quests")],
            [InlineKeyboardButton("📋 Задания", callback_data="tasks"),
             InlineKeyboardButton("🏰 Отряд", callback_data="squad")],
            [InlineKeyboardButton("🛒 Магазин наград", callback_data="shop"),
             InlineKeyboardButton("⚔️ Босс рейд", callback_data="boss")],
        ]
        text = (
            f"{cls['emoji']} *{user['name']}* · Ур.{user['level']} · 🔥{user.get('streak',0)}\n"
            f"🏆 {user.get('reward_points', 0)} · 🌟 Квесты: {dq_done}/{dq_total} · ✅ {done_today}/{total}"
            f"{assigned_line}{boss_line}"
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
            await update.message.reply_text(
                f"⚔️ Ты вступил в отряд *{squads[squad_id]['name']}*!",
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

    kb = [
        [InlineKeyboardButton("Родитель 👨‍👩‍👧‍👦", callback_data="role_parent")],
        [InlineKeyboardButton("Ребёнок 🧒", callback_data="role_child")],
    ]
    await update.message.reply_text(
        "⚔️ *Добро пожаловать в Vysotix!*\n\n"
        "Здесь привычки прокачивают твоего героя.\n"
        "Каждый день — 5 квестов на разные атрибуты.\n"
        "Не выполнишь — босс атакует!\n\n"
        "Выбери роль:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_users()
    if uid in users:
        reset_daily_tasks(users[uid])
        save_users(users)
    await show_menu(update, uid)

# ========== ТЕКСТ ==========

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    step = ctx.user_data.get("step")

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
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )
        return

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
        ctx.user_data["step"] = None
        await update.message.reply_text(
            f"🏰 *Отряд «{text}» создан!*\n\n🔑 Код: `{squad_id}`\n\nДай код участникам.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎮 В меню", callback_data="menu")]]),
            parse_mode="Markdown"
        )
        return

    if step == "enter_squad_code":
        code = text.strip().upper()
        squads = load_squads()
        if code not in squads:
            await update.message.reply_text(
                f"❌ Отряд `{code}` не найден. Попробуй ещё раз:", parse_mode="Markdown")
            return
        users = load_users()
        if uid in users:
            users[uid]["squad_id"] = code
            if uid not in squads[code]["members"]:
                squads[code]["members"].append(uid)
            save_users(users)
            save_squads(squads)
        ctx.user_data["step"] = None
        await update.message.reply_text(
            f"✅ Ты вступил в отряд *{squads[code]['name']}*!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎮 В меню", callback_data="menu")]]),
            parse_mode="Markdown"
        )
        return

    if ctx.user_data.get("awaiting_task_name"):
        if len(text) < 2:
            await update.message.reply_text("Название слишком короткое:")
            return
        ctx.user_data["temp_task_name"] = text
        ctx.user_data["awaiting_task_name"] = False
        kb = [[InlineKeyboardButton(f"{a['emoji']} {a['name']} — {a['hint']}", callback_data=f"tattr_{k}")]
              for k, a in ATTRS.items()]
        await update.message.reply_text("Какой атрибут качает это задание?", reply_markup=InlineKeyboardMarkup(kb))
        return

    if ctx.user_data.get("awaiting_assign_task_name"):
        if len(text) < 2:
            await update.message.reply_text("Название слишком короткое:")
            return
        ctx.user_data["temp_assign_task_name"] = text
        ctx.user_data["awaiting_assign_task_name"] = False
        kb = [[InlineKeyboardButton(f"{a['emoji']} {a['name']} — {a['hint']}", callback_data=f"aattr_{k}")]
              for k, a in ATTRS.items()]
        await update.message.reply_text("Какой атрибут качает это задание?", reply_markup=InlineKeyboardMarkup(kb))
        return

    shop_step = ctx.user_data.get("shop_add_step")
    if shop_step == "name":
        ctx.user_data["shop_temp_name"] = text
        ctx.user_data["shop_add_step"] = "attr"
        kb = [[InlineKeyboardButton(f"{a['emoji']} {a['name']}", callback_data=f"shop_attr_{k}")]
              for k, a in ATTRS.items()]
        await update.message.reply_text("Какой атрибут даёт этот товар?", reply_markup=InlineKeyboardMarkup(kb))
        return
    if shop_step == "cost":
        try:
            ctx.user_data["shop_temp_cost"] = int(text)
            ctx.user_data["shop_add_step"] = "amount"
            await update.message.reply_text("Сколько единиц атрибута?")
        except ValueError:
            await update.message.reply_text("Введи число:")
        return
    if shop_step == "amount":
        try:
            amount = int(text)
            shop = load_reward_shop()
            shop["items"].append({
                "id": str(uuid.uuid4())[:8],
                "name": ctx.user_data["shop_temp_name"],
                "cost": ctx.user_data["shop_temp_cost"],
                "attr": ctx.user_data["shop_temp_attr"],
                "amount": amount,
            })
            save_reward_shop(shop)
            ctx.user_data["shop_add_step"] = None
            await update.message.reply_text(
                f"✅ Товар добавлен!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Магазин", callback_data="manage_shop")]])
            )
        except ValueError:
            await update.message.reply_text("Введи число:")
        return

# ========== CALLBACKS ==========

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    data = query.data
    users = load_users()
    user = users.get(uid)

    if data == "noop":
        return

    if data == "menu":
        if uid in users:
            reset_daily_tasks(users[uid])
            save_users(users)
        await show_menu(query, uid, edit=True)
        return

    if data == "role_parent":
        ctx.user_data["temp_role"] = "parent"
        ctx.user_data["step"] = "name"
        await query.edit_message_text("Как вас зовут?")
        return

    if data == "role_child":
        ctx.user_data["temp_role"] = "child"
        ctx.user_data["step"] = "name"
        await query.edit_message_text("Как зовут твоего героя?")
        return

    if data.startswith("class_"):
        cls_key = data.replace("class_", "")
        name = ctx.user_data.get("temp_name", "Герой")
        role = ctx.user_data.get("temp_role", "child")
        users[uid] = new_user(name, cls_key, role=role)
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
        if users[uid].get("squad_id"):
            await show_menu(query, uid, edit=True)
            return
        cls = CLASSES[cls_key]
        kb = [
            [InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")],
            [InlineKeyboardButton("🔑 Вступить по коду", callback_data="join_squad_by_code")],
        ]
        await query.edit_message_text(
            f"{cls['emoji']} Герой *{name}* ({cls['name']}) создан!\n\nПрисоединись к отряду:",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )
        return

    if not user:
        await query.edit_message_text("Сначала создай героя: /start")
        return

    if data == "profile":
        reset_daily_tasks(user)
        save_users(users)
        kb = [[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]
        await query.edit_message_text(char_card(user), reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    # ========== ЕЖЕДНЕВНЫЕ КВЕСТЫ ==========

    if data == "daily_quests":
        today = str(date.today())
        dq = get_daily_quests(uid)
        squad_id = user.get("squad_id")
        weak_attr = None
        boss_hint = ""
        if squad_id:
            boss, _ = get_or_create_boss(squad_id)
            if not boss["defeated"]:
                weak_attr = boss["weak_attr"]
                w = ATTRS[weak_attr]
                boss_hint = f"\n⚡ Слабость босса: {w['emoji']} {w['name']} — двойной урон!"
        done_count = len([q for q in dq if q.get("done_date") == today])
        kb = []
        for q in dq:
            is_done = q.get("done_date") == today
            a = ATTRS[q["attr"]]
            bonus = " ⚡" if weak_attr and q["attr"] == weak_attr else ""
            kb.append([InlineKeyboardButton(
                f"{'✅' if is_done else '◻️'} {q['name']} {a['emoji']}{bonus}",
                callback_data=f"dqdone_{q['id']}"
            )])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
        all_done = done_count == len(dq)
        footer = "\n\n🎉 *Все квесты выполнены! +50 XP +10 🏆 бонус!*" if all_done else \
                 f"\n\n⚠️ Не выполненные квесты — ночная атака босса!"
        await query.edit_message_text(
            f"🌟 *Квесты дня* — {done_count}/{len(dq)}{boss_hint}{footer}",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )
        return

    if data.startswith("dqdone_"):
        quest_id = data.replace("dqdone_", "")
        today = str(date.today())
        dq = get_daily_quests(uid)
        quest = next((q for q in dq if q["id"] == quest_id), None)
        if not quest:
            await query.answer("Квест не найден", show_alert=True)
            return
        if quest.get("done_date") == today:
            await query.answer("Уже выполнено ✅", show_alert=True)
            return
        quest["done_date"] = today
        xp = quest["xp_gain"]
        attr_key = quest["attr"]
        user["attrs"][attr_key] = user["attrs"].get(attr_key, 0) + quest["attr_gain"]
        update_streak(user)
        leveled = add_xp(user, xp)
        user["reward_points"] = user.get("reward_points", 0) + 5
        save_user_quests(uid, dq)
        boss_msg = await apply_boss_damage(uid, attr_key, user, users, query)
        # Бонус за все квесты
        done_all = all(q.get("done_date") == today for q in dq)
        if done_all:
            add_xp(user, 50)
            user["reward_points"] = user.get("reward_points", 0) + 10
        save_users(users)
        attr = ATTRS[attr_key]
        msg = (
            f"✅ *{quest['name']}*\n\n"
            f"{attr['emoji']} {attr['name']} +{quest['attr_gain']} · ⭐ +{xp} · 🏆 +5\n"
            f"🔥 Стрик: {user['streak']} дн."
            f"{boss_msg}"
        )
        if done_all:
            msg += "\n\n🎉 *Все квесты дня выполнены!*\n+50 XP · +10 🏆 бонус!"
        if leveled:
            gear = GEAR_UNLOCKS.get(user["level"], "")
            msg += f"\n\n🎉 *Уровень {user['level']}!*"
            if gear:
                msg += f"\nПолучено: {gear}"
        kb = [[InlineKeyboardButton("◀️ К квестам", callback_data="daily_quests")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    # ========== ЗАДАНИЯ ==========

    if data == "tasks":
        reset_daily_tasks(user)
        save_users(users)
        await show_tasks_menu(query, uid)
        return

    if data == "add_task":
        ctx.user_data["awaiting_task_name"] = True
        await query.edit_message_text("➕ *Новое задание*\n\nВведи название задания:", parse_mode="Markdown")
        return

    if data.startswith("tattr_"):
        attr_key = data.replace("tattr_", "")
        task_name = ctx.user_data.get("temp_task_name", "Задание")
        task = {
            "id": str(uuid.uuid4())[:8],
            "name": task_name, "attr": attr_key,
            "xp_gain": 25, "attr_gain": 2,
            "done": False, "done_date": "",
        }
        user.setdefault("tasks", []).append(task)
        save_users(users)
        ctx.user_data["temp_task_name"] = None
        await show_tasks_menu(query, uid)
        return

    if data.startswith("done_"):
        task_id = data.replace("done_", "")
        today = str(date.today())
        task = next((t for t in user.get("tasks", []) if t["id"] == task_id), None)
        if not task:
            await query.answer("Задание не найдено", show_alert=True)
            return
        if task.get("done_date") == today:
            await query.answer("Уже выполнено ✅", show_alert=True)
            return
        task["done"] = True
        task["done_date"] = today
        user["attrs"][task["attr"]] = user["attrs"].get(task["attr"], 0) + task["attr_gain"]
        update_streak(user)
        leveled = add_xp(user, task["xp_gain"])
        user["reward_points"] = user.get("reward_points", 0) + 5
        boss_msg = await apply_boss_damage(uid, task["attr"], user, users, query)
        save_users(users)
        attr = ATTRS[task["attr"]]
        msg = (
            f"✅ *{task['name']}*\n\n"
            f"{attr['emoji']} {attr['name']} +{task['attr_gain']} · ⭐ +{task['xp_gain']} · 🏆 +5\n"
            f"🔥 Стрик: {user['streak']} дн.{boss_msg}"
        )
        if leveled:
            gear = GEAR_UNLOCKS.get(user["level"], "")
            msg += f"\n\n🎉 *Уровень {user['level']}!*"
            if gear:
                msg += f"\nПолучено: {gear}"
        kb = [[InlineKeyboardButton("◀️ К заданиям", callback_data="tasks")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    if data.startswith("adone_"):
        task_id = data.replace("adone_", "")
        today = str(date.today())
        task = next((t for t in user.get("assigned_tasks", []) if t["id"] == task_id), None)
        if not task:
            await query.answer("Задание не найдено", show_alert=True)
            return
        if task.get("done_date") == today:
            await query.answer("Уже выполнено ✅", show_alert=True)
            return
        task["done"] = True
        task["done_date"] = today
        xp = task.get("xp_gain", 30)
        attr_key = task["attr"]
        user["attrs"][attr_key] = user["attrs"].get(attr_key, 0) + task.get("attr_gain", 2)
        update_streak(user)
        leveled = add_xp(user, xp)
        user["reward_points"] = user.get("reward_points", 0) + 5
        boss_msg = await apply_boss_damage(uid, attr_key, user, users, query)
        save_users(users)
        assigner_uid = task.get("assigned_by")
        if assigner_uid:
            try:
                await query.get_bot().send_message(
                    chat_id=int(assigner_uid),
                    text=(
                        f"🧒 *{user['name']}* выполнил задание!\n\n"
                        f"✅ {task['name']}\n"
                        f"{ATTRS[attr_key]['emoji']} +{task.get('attr_gain',2)} · 🏆 +5"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Notify parent error: {e}")
        attr = ATTRS[attr_key]
        msg = (
            f"✅ *{task['name']}*\n_(от {task.get('assigned_by_name','родителя')})_\n\n"
            f"{attr['emoji']} +{task.get('attr_gain',2)} · ⭐ +{xp} · 🏆 +5\n"
            f"🔥 Стрик: {user['streak']} дн.{boss_msg}"
        )
        if leveled:
            gear = GEAR_UNLOCKS.get(user["level"], "")
            msg += f"\n\n🎉 *Уровень {user['level']}!*"
            if gear:
                msg += f"\nПолучено: {gear}"
        kb = [[InlineKeyboardButton("◀️ К заданиям", callback_data="tasks")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    # ========== ОТРЯД ==========

    if data == "squad":
        squad_id = user.get("squad_id")
        squads = load_squads()
        if not squad_id or squad_id not in squads:
            kb = [
                [InlineKeyboardButton("🏰 Создать отряд", callback_data="create_squad")],
                [InlineKeyboardButton("🔑 Вступить по коду", callback_data="join_squad_by_code")],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu")],
            ]
            await query.edit_message_text("🏰 У тебя пока нет отряда.", reply_markup=InlineKeyboardMarkup(kb))
            return
        await show_squad_menu(query, uid, squad_id)
        return

    if data == "create_squad":
        ctx.user_data["step"] = "squad_name"
        await query.edit_message_text("🏰 Придумай название отряда и напиши его:")
        return

    if data == "join_squad_by_code":
        ctx.user_data["step"] = "enter_squad_code"
        await query.edit_message_text(
            "🔑 Введи 6-значный код отряда:\n\n_Например: AB3X7K_",
            parse_mode="Markdown"
        )
        return

    if data == "assign_menu":
        await show_assign_menu(query, uid)
        return

    if data.startswith("assign_to_"):
        target_uid = data.replace("assign_to_", "")
        target_user = users.get(target_uid)
        if not target_user:
            await query.answer("Участник не найден", show_alert=True)
            return
        ctx.user_data["assign_target_uid"] = target_uid
        ctx.user_data["awaiting_assign_task_name"] = True
        await query.edit_message_text(
            f"📝 Задание для *{target_user['name']}*\n\nВведи название:", parse_mode="Markdown")
        return

    if data.startswith("aattr_"):
        attr_key = data.replace("aattr_", "")
        target_uid = ctx.user_data.get("assign_target_uid")
        task_name = ctx.user_data.get("temp_assign_task_name", "Задание")
        if not target_uid or target_uid not in users:
            await query.edit_message_text("Ошибка. Попробуй снова.")
            return
        target_user = users[target_uid]
        task = {
            "id": str(uuid.uuid4())[:8],
            "name": task_name, "attr": attr_key,
            "xp_gain": 30, "attr_gain": 2,
            "done": False, "done_date": "",
            "assigned_by": uid, "assigned_by_name": user["name"],
        }
        target_user.setdefault("assigned_tasks", []).append(task)
        save_users(users)
        ctx.user_data["temp_assign_task_name"] = None
        ctx.user_data["assign_target_uid"] = None
        attr = ATTRS[attr_key]
        try:
            await query.get_bot().send_message(
                chat_id=int(target_uid),
                text=f"👨‍👦 *{user['name']}* назначил задание!\n\n📋 {task_name}\n{attr['emoji']} {attr['name']} · ⭐+30 · 🏆+5\n\n/menu → Задания",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Notify child error: {e}")
        kb = [
            [InlineKeyboardButton("📝 Ещё задание", callback_data=f"assign_to_{target_uid}")],
            [InlineKeyboardButton("🎮 В меню", callback_data="menu")],
        ]
        await query.edit_message_text(
            f"✅ *{task_name}* назначено {target_user['name']}!",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )
        return

    if data.startswith("view_member_"):
        target_uid = data.replace("view_member_", "")
        target_user = users.get(target_uid)
        if not target_user:
            await query.answer("Участник не найден", show_alert=True)
            return
        today = str(date.today())
        dq = get_daily_quests(target_uid)
        dq_done = len([q for q in dq if q.get("done_date") == today])
        own_tasks = target_user.get("tasks", [])
        assigned = target_user.get("assigned_tasks", [])
        own_done = len([t for t in own_tasks if t.get("done_date") == today])
        asgn_done = len([t for t in assigned if t.get("done_date") == today])
        cls = CLASSES.get(target_user["class"], list(CLASSES.values())[0])
        kb = []
        if user.get("role") == "parent":
            kb.append([InlineKeyboardButton("➕ Дать задание", callback_data=f"assign_to_{target_uid}")])
            kb.append([InlineKeyboardButton("🏆 Начислить очки", callback_data=f"parent_reward_{target_uid}")])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="squad")])
        await query.edit_message_text(
            f"{cls['emoji']} *{target_user['name']}* — Ур.{target_user['level']}\n"
            f"🔥 Стрик: {target_user.get('streak',0)} · 🏆 {target_user.get('reward_points',0)}\n\n"
            f"🌟 Квесты дня: {dq_done}/{len(dq)}\n"
            f"✅ Свои: {own_done}/{len(own_tasks)} · 👨‍👦 От родителей: {asgn_done}/{len(assigned)}",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )
        return

    # ========== БОСС ==========

    if data == "boss":
        squad_id = user.get("squad_id")
        if not squad_id:
            await query.edit_message_text(
                "⚔️ Для рейда нужен отряд.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu")]])
            )
            return
        boss, _ = get_or_create_boss(squad_id)
        squads = load_squads()
        squad = squads.get(squad_id, {})
        if boss["defeated"]:
            kb = [
                [InlineKeyboardButton("🔄 Следующий босс", callback_data="boss_next")],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu")],
            ]
            await query.edit_message_text(
                f"🏆 *Босс повержён!*\n\n{boss['reward']}\n{boss['reward_desc']}\n\nГотов к следующему?",
                reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
            )
            return
        card = boss_card(boss, squad_id, users, squad.get("members", []))
        kb = [
            [InlineKeyboardButton("🌟 Выполнить квест", callback_data="daily_quests")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu")],
        ]
        await query.edit_message_text(f"⚔️ *Рейд отряда*\n\n{card}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    if data == "boss_next":
        squad_id = user.get("squad_id")
        if squad_id:
            bosses = load_bosses()
            if squad_id in bosses:
                del bosses[squad_id]
                save_bosses(bosses)
            boss, _ = get_or_create_boss(squad_id)
            squads = load_squads()
            card = boss_card(boss, squad_id, users, squads.get(squad_id, {}).get("members", []))
            kb = [
                [InlineKeyboardButton("🌟 Выполнить квест", callback_data="daily_quests")],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu")],
            ]
            await query.edit_message_text(f"⚔️ *Новый рейд!*\n\n{card}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    # ========== МАГАЗИН ==========

    if data == "shop":
        await show_shop(query, uid)
        return

    if data.startswith("buy_"):
        await handle_buy(query, uid, data.replace("buy_", ""))
        return

    if data == "parent_rewards_menu":
        await show_parent_rewards_menu(query, uid)
        return

    if data.startswith("parent_reward_"):
        await show_give_points_menu(query, uid, data.replace("parent_reward_", ""))
        return

    if data.startswith("give_points_"):
        rest = data[len("give_points_"):]
        last_under = rest.rfind("_")
        child_id = rest[:last_under]
        amount = int(rest[last_under + 1:])
        await do_give_points(query, uid, child_id, amount)
        return

    if data == "manage_shop":
        await show_manage_shop(query, uid)
        return

    if data == "shop_add_item":
        ctx.user_data["shop_add_step"] = "name"
        await query.edit_message_text("➕ Введи название товара:")
        return

    if data.startswith("shop_attr_"):
        ctx.user_data["shop_temp_attr"] = data.replace("shop_attr_", "")
        ctx.user_data["shop_add_step"] = "cost"
        await query.edit_message_text("Стоимость в 🏆 очках?")
        return

    if data == "shop_remove_item":
        shop = load_reward_shop()
        kb = [[InlineKeyboardButton(f"🗑 {i['name']}", callback_data=f"remove_item_{i['id']}")]
              for i in shop.get("items", [])]
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="manage_shop")])
        await query.edit_message_text("Выбери товар для удаления:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("remove_item_"):
        shop = load_reward_shop()
        shop["items"] = [i for i in shop["items"] if i["id"] != data.replace("remove_item_", "")]
        save_reward_shop(shop)
        await query.edit_message_text(
            "✅ Товар удалён!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Магазин", callback_data="manage_shop")]])
        )
        return

# ========== ВСПОМОГАТЕЛЬНЫЕ ==========

async def apply_boss_damage(uid, attr_key, user, users, query):
    squad_id = user.get("squad_id")
    if not squad_id:
        return ""
    boss, bosses = get_or_create_boss(squad_id)
    if boss["defeated"]:
        return ""
    attr_val = user["attrs"].get(attr_key, 0)
    dmg = calc_damage(attr_key, boss["weak_attr"], attr_val)
    boss["hp"] = max(0, boss["hp"] - dmg)
    boss.setdefault("damage_log", {})[uid] = boss["damage_log"].get(uid, 0) + dmg
    boss.setdefault("last_hit_date", {})[uid] = str(date.today())
    _, phase_name = boss_phase(boss)
    msg = f"\n⚡ *Крит!* {phase_name} −{dmg} HP" if attr_key == boss["weak_attr"] else f"\n⚔️ {phase_name} −{dmg} HP"
    if boss["hp"] <= 0:
        boss["defeated"] = True
        squads = load_squads()
        for mid in squads.get(squad_id, {}).get("members", []):
            m = users.get(mid)
            if m and boss["reward"] not in m.get("gear", []):
                m.setdefault("gear", []).append(boss["reward"])
        msg += f"\n\n🏆 *БОСС ПОВЕРЖЁН!* Весь отряд получает: {boss['reward']}"
    save_bosses(bosses)
    return msg

async def show_assign_menu(query, uid):
    users = load_users()
    user = users.get(uid)
    squad_id = user.get("squad_id") if user else None
    squads = load_squads()
    today = str(date.today())
    children = []
    if squad_id and squad_id in squads:
        for mid in squads[squad_id].get("members", []):
            if mid == uid:
                continue
            m = users.get(mid)
            if m and m.get("role") != "parent":
                children.append((mid, m))
    if not children:
        await query.edit_message_text(
            "В отряде нет детей.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu")]])
        )
        return
    kb = []
    for cid, child in children:
        dq = get_daily_quests(cid)
        dq_done = len([q for q in dq if q.get("done_date") == today])
        asgn = child.get("assigned_tasks", [])
        asgn_done = len([t for t in asgn if t.get("done_date") == today])
        kb.append([InlineKeyboardButton(
            f"👤 {child['name']} Ур.{child['level']} · 🌟{dq_done}/{len(dq)} · 🏆{child.get('reward_points',0)}",
            callback_data=f"assign_to_{cid}"
        )])
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
    await query.edit_message_text(
        "👨‍👧 *Назначить задание*\n\nВыбери ребёнка:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )

async def show_squad_menu(query, uid, squad_id):
    users = load_users()
    squads = load_squads()
    squad = squads.get(squad_id, {})
    today = str(date.today())
    current_role = users.get(uid, {}).get("role", "child")
    members_text = ""
    kb = []
    for mid in squad.get("members", []):
        m = users.get(mid)
        if not m:
            continue
        cls = CLASSES.get(m["class"], list(CLASSES.values())[0])
        m_role = m.get("role", "child")
        role_emoji = "👨‍👩‍👧‍👦" if m_role == "parent" else "🧒"
        dq = get_daily_quests(mid)
        dq_done = len([q for q in dq if q.get("done_date") == today])
        own_done = len([t for t in m.get("tasks", []) if t.get("done_date") == today])
        own_total = len(m.get("tasks", []))
        members_text += (
            f"{cls['emoji']} *{m['name']}* {role_emoji} Ур.{m['level']} · 🔥{m.get('streak',0)}\n"
            f"  🌟{dq_done}/{len(dq)} · ✅{own_done}/{own_total} · 🏆{m.get('reward_points',0)}\n"
        )
        if mid != uid:
            label = f"👁 {m['name']} · дать задание" if current_role == "parent" and m_role != "parent" else f"👁 {m['name']}"
            kb.append([InlineKeyboardButton(label, callback_data=f"view_member_{mid}")])
    bot_me = await query.get_bot().get_me()
    link = f"https://t.me/{bot_me.username}?start=squad_{squad_id}"
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
    await query.edit_message_text(
        f"🏰 *{squad['name']}*\n\n{members_text}\n🔑 Код: `{squad_id}`\n🔗 `{link}`",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )

async def show_tasks_menu(query, uid):
    users = load_users()
    user = users.get(uid)
    role = user.get("role", "child")
    today = str(date.today())
    own_tasks = user.get("tasks", [])
    assigned_tasks = user.get("assigned_tasks", []) if role != "parent" else []
    squad_id = user.get("squad_id")
    weak_attr = None
    boss_hint = ""
    if squad_id:
        boss, _ = get_or_create_boss(squad_id)
        if not boss["defeated"]:
            weak_attr = boss["weak_attr"]
            boss_hint = f"\n⚡ Слабость босса: {ATTRS[weak_attr]['emoji']} {ATTRS[weak_attr]['name']}"
    kb = []
    for t in own_tasks:
        is_done = t.get("done_date") == today
        a = ATTRS[t["attr"]]
        bonus = " ⚡" if weak_attr and t["attr"] == weak_attr else ""
        kb.append([InlineKeyboardButton(
            f"{'✅' if is_done else '◻️'} {t['name']} {a['emoji']}{bonus}",
            callback_data=f"done_{t['id']}"
        )])
    if assigned_tasks:
        kb.append([InlineKeyboardButton("── 👨‍👦 От родителей ──", callback_data="noop")])
        for t in assigned_tasks:
            is_done = t.get("done_date") == today
            a = ATTRS[t["attr"]]
            bonus = " ⚡" if weak_attr and t["attr"] == weak_attr else ""
            kb.append([InlineKeyboardButton(
                f"{'✅' if is_done else '◻️'} {t['name']} {a['emoji']}{bonus}",
                callback_data=f"adone_{t['id']}"
            )])
    if not own_tasks and not assigned_tasks:
        kb.append([InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")])
        kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
        await query.edit_message_text("📋 Пока нет заданий. Добавь первое!", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb.append([InlineKeyboardButton("➕ Добавить задание", callback_data="add_task")])
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
    own_done = len([t for t in own_tasks if t.get("done_date") == today])
    summary = f"📋 *Задания* — {own_done}/{len(own_tasks)}{boss_hint}"
    await query.edit_message_text(summary, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_shop(query, uid):
    users = load_users()
    user = users.get(uid)
    shop = load_reward_shop()
    items = shop.get("items", [])
    if not items:
        await query.edit_message_text("🛒 Магазин пуст.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]))
        return
    text = f"🛒 *Магазин наград*\nУ тебя: {user.get('reward_points', 0)} 🏆\n\n"
    kb = []
    for item in items:
        text += f"*{item['name']}* — {item['cost']} 🏆\n"
        kb.append([InlineKeyboardButton(f"Купить ({item['cost']}🏆)", callback_data=f"buy_{item['id']}")])
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def handle_buy(query, uid, item_id):
    users = load_users()
    user = users.get(uid)
    shop = load_reward_shop()
    item = next((i for i in shop.get("items", []) if i["id"] == item_id), None)
    if not item:
        await query.answer("Товар не найден", show_alert=True)
        return
    if user.get("reward_points", 0) < item["cost"]:
        await query.answer(f"Не хватает очков! Нужно {item['cost']} 🏆", show_alert=True)
        return
    user["reward_points"] -= item["cost"]
    user["attrs"][item["attr"]] = user["attrs"].get(item["attr"], 0) + item["amount"]
    save_users(users)
    attr = ATTRS[item["attr"]]
    await query.edit_message_text(
        f"✅ *Куплено!*\n\n{item['name']}\n{attr['emoji']} +{item['amount']}\n🏆 Осталось: {user['reward_points']}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В меню", callback_data="menu")]]),
        parse_mode="Markdown"
    )

async def show_parent_rewards_menu(query, uid):
    users = load_users()
    user = users.get(uid)
    squad_id = user.get("squad_id") if user else None
    squads = load_squads()
    children = []
    if squad_id and squad_id in squads:
        for mid in squads[squad_id].get("members", []):
            if mid == uid:
                continue
            m = users.get(mid)
            if m and m.get("role") != "parent":
                children.append((mid, m))
    if not children:
        await query.edit_message_text("Нет детей.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]))
        return
    kb = [[InlineKeyboardButton(f"🏆 {c['name']} — {c.get('reward_points',0)}", callback_data=f"parent_reward_{cid}")]
          for cid, c in children]
    kb.append([InlineKeyboardButton("🛒 Магазин наград", callback_data="manage_shop")])
    kb.append([InlineKeyboardButton("◀️ Назад", callback_data="menu")])
    await query.edit_message_text("🏆 *Управление наградами*\n\nВыбери ребёнка:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def show_give_points_menu(query, uid, child_id):
    users = load_users()
    child = users.get(child_id)
    if not child:
        await query.answer("Не найден", show_alert=True)
        return
    kb = [
        [InlineKeyboardButton("+10 🏆", callback_data=f"give_points_{child_id}_10"),
         InlineKeyboardButton("+25 🏆", callback_data=f"give_points_{child_id}_25")],
        [InlineKeyboardButton("+50 🏆", callback_data=f"give_points_{child_id}_50"),
         InlineKeyboardButton("+100 🏆", callback_data=f"give_points_{child_id}_100")],
        [InlineKeyboardButton("◀️ Назад", callback_data="parent_rewards_menu")],
    ]
    await query.edit_message_text(
        f"🏆 Начислить *{child['name']}*\n\nБаланс: {child.get('reward_points',0)} 🏆",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )

async def do_give_points(query, parent_uid, child_id, amount):
    users = load_users()
    parent = users.get(parent_uid)
    child = users.get(child_id)
    if not child:
        await query.answer("Не найден", show_alert=True)
        return
    child["reward_points"] = child.get("reward_points", 0) + amount
    save_users(users)
    try:
        await query.get_bot().send_message(
            chat_id=int(child_id),
            text=f"🎉 *{parent['name']}* начислил *{amount} 🏆*!\nТеперь у тебя {child['reward_points']} 🏆. Загляни в 🛒 Магазин!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Notify child error: {e}")
    await query.edit_message_text(
        f"✅ Начислено *{amount} 🏆* → {child['name']}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="parent_rewards_menu")]]),
        parse_mode="Markdown"
    )

async def show_manage_shop(query, uid):
    shop = load_reward_shop()
    items = shop.get("items", [])
    text = "🛒 *Управление магазином*\n\n"
    for item in items:
        text += f"• {item['name']} — {item['cost']}🏆 → +{item['amount']} {ATTRS[item['attr']]['emoji']}\n"
    if not items:
        text += "Нет товаров\n"
    kb = [
        [InlineKeyboardButton("➕ Добавить товар", callback_data="shop_add_item")],
        [InlineKeyboardButton("🗑 Удалить товар", callback_data="shop_remove_item")],
        [InlineKeyboardButton("◀️ Назад", callback_data="parent_rewards_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ========== ЗАПУСК ==========

async def post_init(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать игру"),
        BotCommand("menu", "Главное меню"),
    ])
    # Ночная атака босса в 00:05
    app.job_queue.run_daily(
        nightly_boss_attack,
        time=dtime(hour=0, minute=5),
        name="nightly_boss_attack"
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.post_init = post_init
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ Vysotix запущен с ежедневными квестами")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
