# ========== ДОСТИЖЕНИЯ ==========
# Подключи этот файл в main.py:
#   from achievements import ACHIEVEMENTS, check_achievements, achievements_card

ACHIEVEMENTS = [
    # Стрик
    {"id": "streak_3",    "name": "🔥 Первый огонь",      "desc": "3 дня подряд",         "check": lambda u, _: u.get("streak", 0) >= 3},
    {"id": "streak_7",    "name": "🔥 Недельный воин",     "desc": "7 дней подряд",         "check": lambda u, _: u.get("streak", 0) >= 7},
    {"id": "streak_30",   "name": "🔥 Несгибаемый",        "desc": "30 дней подряд",        "check": lambda u, _: u.get("streak", 0) >= 30},

    # Уровни
    {"id": "level_5",     "name": "⭐ Опытный герой",      "desc": "Достичь 5 уровня",      "check": lambda u, _: u.get("level", 1) >= 5},
    {"id": "level_10",    "name": "⭐ Легенда",             "desc": "Достичь 10 уровня",     "check": lambda u, _: u.get("level", 1) >= 10},

    # Атрибуты
    {"id": "attr_50",     "name": "💎 Мастер навыка",      "desc": "Любой атрибут ≥ 50",    "check": lambda u, _: any(v >= 50 for v in u.get("attrs", {}).values())},
    {"id": "attr_all_10", "name": "⚖️ Гармония",           "desc": "Все атрибуты ≥ 10",     "check": lambda u, _: all(u.get("attrs", {}).get(k, 0) >= 10 for k in ["str","int","hp","agi","wil"])},

    # Задания
    {"id": "tasks_10",    "name": "✅ Трудяга",             "desc": "Выполнить 10 заданий",  "check": lambda u, ctx: ctx.get("total_done", 0) >= 10},
    {"id": "tasks_50",    "name": "✅ Ветеран труда",       "desc": "Выполнить 50 заданий",  "check": lambda u, ctx: ctx.get("total_done", 0) >= 50},
    {"id": "tasks_100",   "name": "✅ Сотня побед",         "desc": "Выполнить 100 заданий", "check": lambda u, ctx: ctx.get("total_done", 0) >= 100},

    # Отряд
    {"id": "squad_join",  "name": "🏰 В отряде сила",      "desc": "Вступить в отряд",      "check": lambda u, _: bool(u.get("squad_id"))},

    # Босс
    {"id": "boss_hit",    "name": "⚔️ Первая кровь",       "desc": "Нанести урон боссу",    "check": lambda u, ctx: ctx.get("boss_hit", False)},
    {"id": "boss_kill",   "name": "🏆 Убийца боссов",      "desc": "Победить босса",        "check": lambda u, ctx: ctx.get("boss_killed", False)},

    # Снаряжение
    {"id": "gear_1",      "name": "🗡️ Вооружён",           "desc": "Получить первое снаряжение", "check": lambda u, _: len(u.get("gear", [])) >= 1},
    {"id": "gear_5",      "name": "✨ Полный комплект",    "desc": "Получить 5 предметов снаряжения", "check": lambda u, _: len(u.get("gear", [])) >= 5},
]

# Вспомогательный счётчик — суммирует done_date по всем заданиям
def count_total_done(user):
    done = set()
    for t in user.get("tasks", []):
        if t.get("done_date"):
            done.add(("own", t["id"], t["done_date"]))
    for t in user.get("assigned_tasks", []):
        if t.get("done_date"):
            done.add(("asgn", t["id"], t["done_date"]))
    return len(done)

def check_achievements(user, extra_ctx=None):
    """
    Проверяет достижения и возвращает список НОВЫХ (только что полученных).
    Мутирует user["achievements"] — вызывай до save_users().
    extra_ctx: dict с доп. флагами, например {"boss_hit": True, "boss_killed": True}
    """
    if "achievements" not in user:
        user["achievements"] = []

    ctx = {"total_done": count_total_done(user)}
    if extra_ctx:
        ctx.update(extra_ctx)

    earned = user["achievements"]
    new_achievements = []

    for ach in ACHIEVEMENTS:
        if ach["id"] in earned:
            continue
        try:
            if ach["check"](user, ctx):
                earned.append(ach["id"])
                new_achievements.append(ach)
        except Exception:
            pass

    return new_achievements

def achievements_card(user):
    """Возвращает строку с прогрессом по достижениям для отображения."""
    earned_ids = set(user.get("achievements", []))
    total = len(ACHIEVEMENTS)
    earned = len(earned_ids)

    lines = []
    for ach in ACHIEVEMENTS:
        icon = "✅" if ach["id"] in earned_ids else "🔒"
        lines.append(f"{icon} {ach['name']} — {ach['desc']}")

    bar_filled = int(earned / total * 10) if total else 0
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    header = f"🏅 *Достижения* {earned}/{total}\n`{bar}`\n\n"
    return header + "\n".join(lines)

def format_new_achievements(new_achs):
    """Формирует сообщение о новых ачивках."""
    if not new_achs:
        return ""
    lines = "\n".join(f"  {a['name']} — {a['desc']}" for a in new_achs)
    return f"\n\n🏅 *Новые достижения:*\n{lines}"
